# ==============================================================================
# commands/system_control.py   –  REX 4.0   OS-Level Commands
# ==============================================================================
# Design
#   • App lookup uses a two-tier strategy:
#       1. An in-memory cache (TTL-based) of previously found paths.
#       2. A static KNOWN_APPS dict for the most common Windows apps so we
#          don't have to search the filesystem every time.
#       3. Fallback: subprocess call to "where.exe" (fast Windows equivalent
#          of `which`).
#   • File search walks the filesystem but respects max_search_depth and
#     max_search_results from config, and skips known-noisy directories
#     (Windows, Program Files internals, etc.).
#   • Volume / brightness use ctypes / COM where possible; fallback to
#     subprocess calls (e.g. powershell) so the code works even without
#     admin privileges.
#   • Every public method returns a CommandResult; never raises.
# ==============================================================================

from __future__ import annotations

import os
import subprocess
import time
import ctypes
from pathlib import Path
from typing import Any, Dict, Optional

from commands.types     import CommandResult
from core.intent        import IntentResult
from core.config        import get_config
from core.logger        import get_logger, LogCategory


# ─── Known apps ───────────────────────────────────────────────────────────────
# Fastest possible lookup: no filesystem IO at all.

KNOWN_APPS: Dict[str, str] = {
    # browsers
    "chrome":         "chrome",
    "google chrome":  "chrome",
    "firefox":        "firefox",
    "edge":           "msedge",
    "microsoft edge": "msedge",
    "safari":         "safari",
    # productivity
    "notepad":        "notepad",
    "calculator":     "calc",
    "calc":           "calc",
    "file explorer":  "explorer",
    "explorer":       "explorer",
    "task manager":   "taskmgr",
    "settings":       "ms-settings:",
    # office
    "word":           "winword",
    "excel":          "excel",
    "powerpoint":     "powerpnt",
    "outlook":        "outlook",
    # media
    "vlc":            "vlc",
    "spotify":        "spotify",
    "discord":        "discord",
    # dev
    "cmd":            "cmd",
    "command prompt": "cmd",
    "powershell":     "powershell",
    "visual studio code": "code",
    "vscode":         "code",
    "vs code":        "code",
    # misc
    "paint":          "mspaint",
    "snipping tool":  "SnippingTool",
    "control panel":  "control",
    "device manager": "devmgmt.msc",
    "disk management":"diskmgmt.msc",
    "event viewer":   "eventvwr.msc",
}

# Directories to skip during file-search (noisy / system internals)
_SKIP_DIRS = {
    "windows", "program files", "programdata", "appdata",
    "temp", "cache", "node_modules", ".git", "__pycache__",
}


# ─── Cache ────────────────────────────────────────────────────────────────────


class _AppCache:
    """Simple TTL cache for resolved app paths."""

    def __init__(self, ttl: int = 300) -> None:
        self._store: Dict[str, tuple] = {}   # name → (path, timestamp)
        self._ttl = ttl

    def get(self, name: str) -> Optional[str]:
        entry = self._store.get(name.lower())
        if entry and (time.time() - entry[1]) < self._ttl:
            return entry[0]
        if entry:
            del self._store[name.lower()]
        return None

    def put(self, name: str, path: str) -> None:
        self._store[name.lower()] = (path, time.time())


# ─── SystemCommands ───────────────────────────────────────────────────────────


class SystemCommands:
    """
    Handles every OS-level command REX can execute.
    """

    def __init__(self) -> None:
        self._logger = get_logger()
        self._cfg    = get_config()
        self._cache  = _AppCache(ttl=self._cfg.performance.cache_ttl_seconds)

    # ── app open ──────────────────────────────────────────────────────────
    def open_app(self, intent: IntentResult, _token: str) -> CommandResult:
        app_name = intent.parameters.get("app_name", "").strip()
        if not app_name:
            return _fail("Which application would you like me to open?")

        resolved = self._resolve_app(app_name)
        if resolved is None:
            return _fail(f"I couldn't find '{app_name}'. Make sure it is installed.")

        try:
            subprocess.Popen(resolved, shell=True,
                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            self._logger.info(LogCategory.COMMAND, f"Opened app: {app_name} → {resolved}")
            return _ok(f"Opening {app_name}.")
        except Exception as exc:
            self._logger.error(LogCategory.COMMAND, f"Failed to open {app_name}: {exc}")
            return _fail(f"I had trouble opening {app_name}. {exc}")

    # ── app close ─────────────────────────────────────────────────────────
    def close_app(self, intent: IntentResult, _token: str) -> CommandResult:
        app_name = intent.parameters.get("app_name", "").strip()
        if not app_name:
            return _fail("Which application would you like me to close?")

        # resolve to the executable name that taskkill expects
        exe = KNOWN_APPS.get(app_name.lower(), app_name)
        # add .exe if missing
        if not exe.endswith((".exe", ".com", ".msc")):
            exe += ".exe"

        try:
            subprocess.run(["taskkill", "/f", "/im", exe],
                           capture_output=True, timeout=5)
            self._logger.info(LogCategory.COMMAND, f"Closed app: {app_name}")
            return _ok(f"Closing {app_name}.")
        except subprocess.TimeoutExpired:
            return _fail(f"Timed out trying to close {app_name}.")
        except Exception as exc:
            return _fail(f"I couldn't close {app_name}. {exc}")

    # ── window management ─────────────────────────────────────────────────
    def minimize_window(self, _intent: IntentResult, _token: str) -> CommandResult:
        _send_key_combo("super+d")   # show desktop (minimises all)
        return _ok("Minimised all windows.")

    def maximize_window(self, _intent: IntentResult, _token: str) -> CommandResult:
        _send_key_combo("alt+F10")   # maximise focused window (works in most apps)
        return _ok("Maximised the current window.")

    def switch_window(self, intent: IntentResult, _token: str) -> CommandResult:
        target = intent.parameters.get("app_name", "").strip()
        if target:
            # best-effort: open it (it will come to front if already running)
            resolved = self._resolve_app(target)
            if resolved:
                try:
                    subprocess.Popen(resolved, shell=True)
                    return _ok(f"Switching to {target}.")
                except Exception as exc:
                    return _fail(str(exc))
        # fallback: alt-tab
        _send_key_combo("alt+tab")
        return _ok("Switching windows.")

    # ── file ops ──────────────────────────────────────────────────────────
    def open_file(self, intent: IntentResult, _token: str) -> CommandResult:
        name = intent.parameters.get("file_name", "").strip()
        if not name:
            return _fail("Which file would you like me to open?")

        found = self._find_file(name)
        if found is None:
            return _fail(f"I couldn't find a file named '{name}'.")

        try:
            subprocess.Popen(["start", "", str(found)], shell=True)
            self._logger.info(LogCategory.COMMAND, f"Opened file: {found}")
            return _ok(f"Opening {found.name}.")
        except Exception as exc:
            return _fail(f"Error opening file: {exc}")

    def search_file(self, intent: IntentResult, _token: str) -> CommandResult:
        name = intent.parameters.get("file_name", "").strip()
        if not name:
            return _fail("What file are you looking for?")

        found = self._find_file(name)
        if found:
            return _ok(f"Found it: {found}")
        return _fail(f"I couldn't find '{name}' on this computer.")

    def open_folder(self, intent: IntentResult, _token: str) -> CommandResult:
        name = intent.parameters.get("folder_name", "").strip()
        if not name:
            return _fail("Which folder would you like me to open?")

        # common folder aliases
        aliases = {
            "desktop":    Path.home() / "Desktop",
            "documents":  Path.home() / "Documents",
            "downloads":  Path.home() / "Downloads",
            "pictures":   Path.home() / "Pictures",
            "music":      Path.home() / "Music",
            "videos":     Path.home() / "Videos",
            "home":       Path.home(),
            "user":       Path.home(),
            "this pc":    Path("C:\\"),
            "c drive":    Path("C:\\"),
            "d drive":    Path("D:\\"),
        }
        target = aliases.get(name.lower(), Path.home() / name)
        if target.exists():
            subprocess.Popen(["explorer", str(target)])
            return _ok(f"Opening {target}.")
        return _fail(f"I can't find the folder '{name}'.")

    # ── system power ──────────────────────────────────────────────────────
    def shutdown_system(self, _intent: IntentResult, _token: str) -> CommandResult:
        # REX exits; the main loop will handle the actual os shutdown
        return _ok("Shutting down the computer. Goodbye!", data={"action": "os_shutdown"})

    def restart_system(self, _intent: IntentResult, _token: str) -> CommandResult:
        return _ok("Restarting the computer now.", data={"action": "os_restart"})

    def sleep_system(self, _intent: IntentResult, _token: str) -> CommandResult:
        return _ok("Putting the computer to sleep.", data={"action": "os_sleep"})

    def lock_system(self, _intent: IntentResult, _token: str) -> CommandResult:
        try:
            ctypes.windll.kernel32.LockWorkStation()
            return _ok("Computer locked.")
        except Exception as exc:
            self._logger.error(LogCategory.COMMAND, f"Lock failed: {exc}")
            return _fail(f"Couldn't lock the computer: {exc}")

    # ── volume ────────────────────────────────────────────────────────────
    def volume_control(self, intent: IntentResult, _token: str) -> CommandResult:
        action = intent.parameters.get("action", "")
        amount = intent.parameters.get("amount", 10)   # default 10 %

        if action == "mute":
            _run_ps("Set-AudioVolume -Mute $true", fallback="volume /mute")
            return _ok("Volume muted.")
        if action == "unmute":
            _run_ps("Set-AudioVolume -Mute $false", fallback="volume /unmute")
            return _ok("Volume unmuted.")
        if action == "increase":
            # Windows volume keys via powershell / nircmd if available
            _run_ps(None, fallback=f"nircmd setvolume relative {amount * 655}")
            return _ok(f"Volume increased by {amount} percent.")
        if action == "decrease":
            _run_ps(None, fallback=f"nircmd setvolume relative {-amount * 655}")
            return _ok(f"Volume decreased by {amount} percent.")

        return _fail("Please say volume up, volume down, mute, or unmute.")

    # ── brightness ────────────────────────────────────────────────────────
    def brightness_control(self, intent: IntentResult, _token: str) -> CommandResult:
        action = intent.parameters.get("action", "")
        amount = intent.parameters.get("amount", 10)

        # PowerShell WMI approach (works on laptops with WMI brightness support)
        if action == "increase":
            _run_ps(
                f"$b = Get-WmiObject -Namespace root\\wmi -Class Backlight; "
                f"$b.Brightness = [math]::Min($b.MaxBrightness, $b.Brightness + {amount}); "
                f"$b.Put()"
            )
            return _ok(f"Brightness increased by {amount}.")
        if action == "decrease":
            _run_ps(
                f"$b = Get-WmiObject -Namespace root\\wmi -Class Backlight; "
                f"$b.Brightness = [math]::Max(0, $b.Brightness - {amount}); "
                f"$b.Put()"
            )
            return _ok(f"Brightness decreased by {amount}.")
        return _fail("Please say brighter or dimmer.")

    # ── internal helpers ──────────────────────────────────────────────────
    def _resolve_app(self, name: str) -> Optional[str]:
        """Return a shell-callable string for *name*, or None."""
        key = name.lower().strip()

        # 1. cache hit
        cached = self._cache.get(key)
        if cached:
            return cached

        # 2. known-apps table
        if key in KNOWN_APPS:
            self._cache.put(key, KNOWN_APPS[key])
            return KNOWN_APPS[key]

        # 3. "where.exe" (Windows PATH search)
        try:
            proc = subprocess.run(
                ["where", name],
                capture_output=True, text=True, timeout=3,
            )
            if proc.returncode == 0:
                path = proc.stdout.strip().splitlines()[0]
                self._cache.put(key, path)
                return path
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # 4. last resort – maybe it's a .exe we can just try
        self._logger.debug(LogCategory.COMMAND, f"App not resolved: '{name}'")
        return None

    def _find_file(self, name: str, start_dir: Optional[Path] = None) -> Optional[Path]:
        """
        Walk from *start_dir* (default: user home) up to max_search_depth
        looking for *name* (case-insensitive, supports * glob).
        """
        root       = start_dir or Path.home()
        max_depth  = self._cfg.performance.max_file_search_depth
        max_hits   = self._cfg.performance.max_search_results
        name_lower = name.lower()

        for depth, (dirpath, dirnames, filenames) in enumerate(os.walk(root)):
            if depth > max_depth:
                dirnames.clear()
                continue

            # prune noisy directories
            dirnames[:] = [d for d in dirnames if d.lower() not in _SKIP_DIRS]

            for fname in filenames:
                if name_lower in fname.lower():
                    return Path(dirpath) / fname

        return None


# ─── Module-level convenience ─────────────────────────────────────────────────


def _ok(msg: str, data: Optional[Dict[str, Any]] = None) -> CommandResult:
    return CommandResult(success=True, message=msg, data=data or {})


def _fail(msg: str) -> CommandResult:
    return CommandResult(success=False, message=msg, error=msg)


def _send_key_combo(combo: str) -> None:
    """Fire a keyboard shortcut via PowerShell (no external dep)."""
    # Map our notation to PowerShell -KeyCombination names
    _map = {
        "super+d":  "[System.Windows.Forms.SendKeys]::SendWait(\"%{d}\")",
        "alt+F10":  "[System.Windows.Forms.SendKeys]::SendWait(\"%{F10}\")",
        "alt+tab":  "[System.Windows.Forms.SendKeys]::SendWait(\"%{TAB}\")",
    }
    ps_cmd = _map.get(combo)
    if ps_cmd:
        _run_ps(ps_cmd)


def _run_ps(cmd: Optional[str], fallback: Optional[str] = None) -> None:
    """Run a PowerShell one-liner; if *cmd* is None use *fallback* via shell."""
    if cmd:
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                capture_output=True, timeout=5,
            )
            return
        except Exception:
            pass
    if fallback:
        try:
            subprocess.run(fallback, shell=True, capture_output=True, timeout=5)
        except Exception:
            pass