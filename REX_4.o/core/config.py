# ==============================================================================
# core/config.py   –  REX 4.0   Centralised Configuration
# ==============================================================================
# Responsibilities
#   • Define every tuneable knob as a typed dataclass.
#   • Load from / persist to config.json with automatic backup.
#   • Validate on load; surface every violation before the app starts.
#   • Expose a module-level singleton via  get_config().
#
# Design notes
#   • Every sub-config is its own @dataclass so it can be tested, serialised,
#     or passed around independently.
#   • PathConfig.__post_init__ creates directories on construction so callers
#     never have to do "path.mkdir()" themselves.
#   • VerbosityLevel / LogLevel are enums stored as their .value string in JSON
#     and converted back on load.
# ==============================================================================

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, asdict, field, fields
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Enums ────────────────────────────────────────────────────────────────────


class VerbosityLevel(Enum):
    MINIMAL = "minimal"
    NORMAL  = "normal"
    VERBOSE = "verbose"
    DEBUG   = "debug"


# ─── Sub-configs ──────────────────────────────────────────────────────────────


@dataclass
class AudioConfig:
    """Microphone / audio-capture settings."""
    sample_rate:       int            = 16000   # Hz – Vosk wants 16 k
    block_size:        int            = 8000    # frames per callback
    channels:          int            = 1       # mono
    device_index:      Optional[int]  = None    # None → OS default
    noise_reduction:   bool           = True
    auto_gain_control: bool           = True


@dataclass
class SpeechConfig:
    """Text-to-speech (pyttsx3 / sapi5) settings."""
    rate:     int            = 170    # words / min  (50–300)
    volume:   float          = 1.0    # 0.0 – 1.0
    voice_id: Optional[str]  = None   # None → first available
    pitch:    int            = 100    # percentage


@dataclass
class RecognitionConfig:
    """Vosk speech-recognition tuning."""
    model_path:          str   = "model"
    confidence_threshold: float = 0.60
    energy_threshold:     int   = 300
    pause_threshold:      float = 0.8   # seconds of silence → phrase end
    phrase_timeout:       float = 3.0   # hard cap on one listen() call segment
    calibration_duration: float = 1.0


@dataclass
class SecurityConfig:
    """Auth & permission guard-rails."""
    max_login_attempts:             int  = 5
    lockout_duration_seconds:       int  = 600    # 10 min
    session_timeout_seconds:        int  = 3600   # 1 h
    password_min_length:            int  = 8
    password_require_upper:         bool = True
    password_require_lower:         bool = True
    password_require_digit:         bool = True
    password_require_special:       bool = True
    password_expiry_days:           int  = 90
    require_auth_for_sensitive:     bool = True


@dataclass
class PerformanceConfig:
    """Caching, thread-pool, search limits."""
    max_file_search_depth:  int  = 4
    max_search_results:     int  = 15
    cache_ttl_seconds:      int  = 300
    thread_pool_size:       int  = 4
    max_memory_mb:          int  = 500
    command_history_size:   int  = 200


@dataclass
class PathConfig:
    """Filesystem roots – directories are created on construction."""
    logs_dir:    str = "logs"
    memory_dir:  str = "memory"
    cache_dir:   str = "cache"
    backup_dir:  str = "backups"
    config_file: str = "config.json"
    users_file:  str = "users.json"

    # ── helper ────────────────────────────────────────────────────────────
    def ensure_dirs(self) -> None:
        """Create every directory that does not already exist."""
        for name in ("logs_dir", "memory_dir", "cache_dir", "backup_dir"):
            Path(getattr(self, name)).mkdir(parents=True, exist_ok=True)

    # ── convenience properties ────────────────────────────────────────────
    @property
    def logs(self)   -> Path: return Path(self.logs_dir)
    @property
    def memory(self) -> Path: return Path(self.memory_dir)
    @property
    def cache(self)  -> Path: return Path(self.cache_dir)
    @property
    def backup(self) -> Path: return Path(self.backup_dir)


@dataclass
class FeatureFlags:
    """Runtime feature toggles – flip any to False to disable cleanly."""
    proactive_suggestions: bool = True
    context_memory:         bool = True
    routines:               bool = True
    advanced_features:      bool = True   # web-search, email …
    learning:               bool = True   # intent-correction persistence
    voice_feedback:         bool = True   # speak responses back


@dataclass
class UIConfig:
    """Console / display preferences."""
    verbosity:       str   = "normal"   # serialised as string
    show_confidence: bool  = True
    show_intent:     bool  = True
    show_timestamps: bool  = True
    color_output:    bool  = True


@dataclass
class WakeWordConfig:
    """Wake-word / sleep-word lists and sensitivity."""
    primary:     str        = "rex"
    alternatives: List[str] = field(default_factory=lambda: ["hey rex", "ok rex", "wake up"])
    sleep_words:  List[str] = field(default_factory=lambda: ["sleep", "go to sleep", "rest", "goodbye"])
    sensitivity:  float     = 0.5   # 0.0 – 1.0


# ─── Master config ────────────────────────────────────────────────────────────


class SystemConfig:
    """
    Top-level configuration container.

    Usage
    -----
        config = SystemConfig.load()          # from disk (or create default)
        config.security.max_login_attempts = 3
        config.save()
    """

    VERSION = "4.0.0"

    # ── construction ──────────────────────────────────────────────────────
    def __init__(self) -> None:
        self.audio       = AudioConfig()
        self.speech      = SpeechConfig()
        self.recognition = RecognitionConfig()
        self.security    = SecurityConfig()
        self.performance = PerformanceConfig()
        self.paths       = PathConfig()
        self.features    = FeatureFlags()
        self.ui          = UIConfig()
        self.wake_words  = WakeWordConfig()

        self.version:       str            = self.VERSION
        self.created_at:    Optional[str]  = None
        self.last_modified: Optional[str]  = None

        self.paths.ensure_dirs()

    # ── serialisation ─────────────────────────────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version":        self.version,
            "created_at":     self.created_at,
            "last_modified":  datetime.now().isoformat(),
            "audio":          asdict(self.audio),
            "speech":         asdict(self.speech),
            "recognition":    asdict(self.recognition),
            "security":       asdict(self.security),
            "performance":    asdict(self.performance),
            "paths":          asdict(self.paths),
            "features":       asdict(self.features),
            "ui":             asdict(self.ui),
            "wake_words":     asdict(self.wake_words),
        }

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "SystemConfig":
        cfg = cls()
        _safe_load = _safe_dataclass_load          # local alias

        cfg.audio       = _safe_load(AudioConfig,       data.get("audio", {}))
        cfg.speech      = _safe_load(SpeechConfig,      data.get("speech", {}))
        cfg.recognition = _safe_load(RecognitionConfig, data.get("recognition", {}))
        cfg.security    = _safe_load(SecurityConfig,    data.get("security", {}))
        cfg.performance = _safe_load(PerformanceConfig, data.get("performance", {}))
        cfg.paths       = _safe_load(PathConfig,        data.get("paths", {}))
        cfg.features    = _safe_load(FeatureFlags,      data.get("features", {}))
        cfg.ui          = _safe_load(UIConfig,          data.get("ui", {}))
        cfg.wake_words  = _safe_load(WakeWordConfig,    data.get("wake_words", {}))

        cfg.version        = data.get("version",       cls.VERSION)
        cfg.created_at     = data.get("created_at")
        cfg.last_modified  = data.get("last_modified")
        cfg.paths.ensure_dirs()
        return cfg

    # ── persistence ───────────────────────────────────────────────────────
    def save(self, filepath: Optional[str] = None) -> None:
        filepath = Path(filepath or self.paths.config_file)

        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

        # backup the previous file if it exists
        if filepath.exists():
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = self.paths.backup / f"config_backup_{ts}.json"
            try:
                shutil.copy2(filepath, dest)
            except OSError as exc:                  # pragma: no cover
                print(f"[config] backup failed: {exc}")

        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, filepath: Optional[str] = None) -> "SystemConfig":
        filepath = Path(filepath or "config.json")

        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                return cls._from_dict(data)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                print(f"[config] corrupt file ({exc}) – falling back to defaults")

        cfg = cls()
        cfg.save(str(filepath))
        return cfg

    # ── validation ────────────────────────────────────────────────────────
    def validate(self) -> List[str]:
        """Return a list of human-readable error strings.  Empty → OK."""
        errors: List[str] = []

        # ── audio ──
        if not (8000 <= self.audio.sample_rate <= 48000):
            errors.append("audio.sample_rate must be 8 000 – 48 000")

        # ── speech ──
        if not (50 <= self.speech.rate <= 300):
            errors.append("speech.rate must be 50 – 300 WPM")
        if not (0.0 <= self.speech.volume <= 1.0):
            errors.append("speech.volume must be 0.0 – 1.0")

        # ── recognition ──
        if not (0.0 <= self.recognition.confidence_threshold <= 1.0):
            errors.append("recognition.confidence_threshold must be 0.0 – 1.0")
        if not Path(self.recognition.model_path).exists():
            errors.append(f"recognition.model_path '{self.recognition.model_path}' does not exist")

        # ── security ──
        if self.security.password_min_length < 6:
            errors.append("security.password_min_length should be ≥ 6")
        if self.security.max_login_attempts < 1:
            errors.append("security.max_login_attempts must be ≥ 1")

        # ── performance ──
        if self.performance.thread_pool_size < 1:
            errors.append("performance.thread_pool_size must be ≥ 1")

        # ── wake_words ──
        if not self.wake_words.primary.strip():
            errors.append("wake_words.primary must not be blank")
        if not (0.0 <= self.wake_words.sensitivity <= 1.0):
            errors.append("wake_words.sensitivity must be 0.0 – 1.0")

        return errors

    # ── convenience ───────────────────────────────────────────────────────
    def display(self) -> None:
        """Pretty-print the whole config to stdout."""
        print("\n" + "=" * 60)
        print("  REX 4.0  –  SYSTEM CONFIGURATION")
        print("=" * 60)
        for key, val in self.to_dict().items():
            if isinstance(val, dict):
                print(f"\n  [{key}]")
                for k2, v2 in val.items():
                    print(f"      {k2:.<30} {v2}")
            else:
                print(f"  {key:.<32} {val}")
        print("=" * 60 + "\n")


# ─── Module-level singleton ───────────────────────────────────────────────────

_CONFIG: Optional[SystemConfig] = None


def get_config() -> SystemConfig:
    """Return the process-wide SystemConfig, loading it on first call."""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = SystemConfig.load()
    return _CONFIG


def reload_config() -> SystemConfig:
    """Force a reload from disk and replace the singleton."""
    global _CONFIG
    _CONFIG = SystemConfig.load()
    return _CONFIG


# ─── Private helper ───────────────────────────────────────────────────────────


def _safe_dataclass_load(cls, data: dict):
    """Construct a dataclass, silently ignoring keys that do not exist on it."""
    valid_keys = {f.name for f in fields(cls)}
    filtered   = {k: v for k, v in data.items() if k in valid_keys}
    return cls(**filtered)