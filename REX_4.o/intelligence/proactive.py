# ==============================================================================
# intelligence/proactive.py   –  REX 4.0   Proactive Suggestions Engine
# ==============================================================================
# Design
#   • A background thread that wakes every TICK_INTERVAL (default 60 s) and:
#       1. Checks for due reminders → speaks them urgently
#       2. Analyzes the recent conversation context → makes suggestions
#   • Suggestions are based on simple heuristics:
#       - Time of day: suggest "morning" routine at 8 am, etc.
#       - App usage patterns: if user always opens Chrome + VSCode together,
#         offer a routine.
#       - Idle time: if no interaction for 30 min, ask if they want to sleep.
#   • Suggestions are non-blocking: they add an urgent TTS message but do not
#     pause the main loop.  The user can ignore them.
# ==============================================================================

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.config import get_config
from core.logger import get_logger, LogCategory


# ─── Suggestion ───────────────────────────────────────────────────────────────


class Suggestion:
    def __init__(self, text: str, action: Optional[str] = None) -> None:
        self.text   = text
        self.action = action   # e.g. "run_routine:morning"


# ─── ProactiveEngine ──────────────────────────────────────────────────────────


class ProactiveEngine:
    """
    Background engine that monitors state and makes proactive suggestions.

    Usage
    -----
        engine = ProactiveEngine(speech_callback=speech.speak_urgent)
        engine.start()
        # ... later ...
        engine.stop()
    """

    TICK_INTERVAL = 60   # seconds between checks

    def __init__(self, speech_callback=None) -> None:
        """
        Parameters
        ----------
        speech_callback   A callable(str) that speaks text urgently.
        """
        self._logger   = get_logger()
        self._cfg      = get_config()
        self._speak    = speech_callback or (lambda _: None)

        self._stop_flag = threading.Event()
        self._thread:   Optional[threading.Thread] = None
        self._last_interaction = time.time()

    # ── lifecycle ─────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="REX-Proactive")
        self._thread.start()
        self._logger.info(LogCategory.SYSTEM, "ProactiveEngine started")

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop_flag.set()
        self._thread.join(timeout=3)
        self._thread = None
        self._logger.info(LogCategory.SYSTEM, "ProactiveEngine stopped")

    def mark_interaction(self) -> None:
        """Called by the main loop whenever the user speaks."""
        self._last_interaction = time.time()

    # ── background worker ─────────────────────────────────────────────────
    def _worker(self) -> None:
        while not self._stop_flag.is_set():
            try:
                self._tick()
            except Exception as exc:
                self._logger.error(LogCategory.ERROR, f"Proactive tick error: {exc}")

            # sleep in short bursts so stop() doesn't have to wait the full interval
            for _ in range(self.TICK_INTERVAL):
                if self._stop_flag.is_set():
                    break
                time.sleep(1)

    def _tick(self) -> None:
        """One iteration: check reminders, analyze context, make suggestions."""
        # 1. Reminders
        self._check_reminders()

        # 2. Time-based suggestions
        self._check_time_suggestions()

        # 3. Idle detection
        self._check_idle()

    # ── reminder checking ─────────────────────────────────────────────────
    def _check_reminders(self) -> None:
        from commands.advanced_features import _load_reminders, _save_reminders

        reminders = _load_reminders()
        now       = time.time()
        triggered = []

        for r in reminders:
            if r.triggered:
                continue
            if r.due_at <= now:
                self._speak(f"Reminder: {r.text}")
                self._logger.info(LogCategory.SYSTEM, f"Reminder triggered: {r.text}")
                r.triggered = True
                triggered.append(r)

        if triggered:
            _save_reminders(reminders)

    # ── time-based suggestions ────────────────────────────────────────────
    def _check_time_suggestions(self) -> None:
        """Suggest routines based on time of day."""
        hour = datetime.now().hour

        # only suggest once per hour (crude debounce)
        suggestion_path = Path(self._cfg.paths.cache_dir) / "last_suggestion.json"
        suggestion_path.parent.mkdir(parents=True, exist_ok=True)

        last_hour = -1
        if suggestion_path.exists():
            try:
                last_hour = json.loads(suggestion_path.read_text()).get("hour", -1)
            except (json.JSONDecodeError, OSError):
                pass

        if last_hour == hour:
            return   # already suggested this hour

        # Morning: 8–10 am
        if 8 <= hour < 10:
            self._speak("Good morning! Would you like me to run your morning routine?")
            suggestion_path.write_text(json.dumps({"hour": hour}))

        # Lunch: 12–1 pm
        elif 12 <= hour < 13:
            self._speak("It's lunchtime. Don't forget to take a break!")
            suggestion_path.write_text(json.dumps({"hour": hour}))

        # Evening: 6–8 pm
        elif 18 <= hour < 20:
            self._speak("Good evening! Would you like me to run your evening routine?")
            suggestion_path.write_text(json.dumps({"hour": hour}))

        # Night: 10 pm – midnight
        elif 22 <= hour < 24:
            self._speak("It's getting late. Would you like me to put the computer to sleep?")
            suggestion_path.write_text(json.dumps({"hour": hour}))

    # ── idle detection ────────────────────────────────────────────────────
    def _check_idle(self) -> None:
        """Suggest sleep if the user has been idle for > 30 min."""
        idle_seconds = time.time() - self._last_interaction
        if idle_seconds > 1800:   # 30 min
            self._speak("You've been idle for a while. Would you like me to put the computer to sleep?")
            # reset so we don't spam
            self._last_interaction = time.time()