# ==============================================================================
# core/speech.py   –  REX 4.0   Text-to-Speech Engine
# ==============================================================================
# Design
#   • A background worker thread pulls messages off a PriorityQueue and feeds
#     them to pyttsx3.  The main thread never blocks on TTS.
#   • Five priority tiers (URGENT … LOWEST); URGENT can interrupt whatever is
#     currently being spoken.
#   • If pyttsx3 raises an exception the worker retries up to MAX_RETRIES
#     before giving up on that message and moving on.
#   • SpeechFormatter is a pure-function helper that pre-processes text for
#     better TTS output (expand abbreviations, ordinals, …).
# ==============================================================================

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, List, Optional

import pyttsx3

from core.config import get_config
from core.logger import get_logger, LogCategory


# ─── Priority ─────────────────────────────────────────────────────────────────


class Priority(IntEnum):
    URGENT  = 0   # alerts, errors  – may interrupt
    HIGH    = 1   # important replies
    NORMAL  = 2   # standard reply
    LOW     = 3   # supplementary info
    LOWEST  = 4   # optional / background


# ─── Message ──────────────────────────────────────────────────────────────────


@dataclass(order=True)
class _SpeechMessage:
    """Wrapper so PriorityQueue can order by (priority, timestamp)."""
    priority:  int                          # sort key 1
    timestamp: float                        # sort key 2  (FIFO within same prio)
    # ── payload (not compared) ────────────────────────────────────────────
    text:      str            = field(compare=False, default="")
    interrupt: bool           = field(compare=False, default=False)
    callback:  Optional[Callable] = field(compare=False, default=None)


# ─── Engine ───────────────────────────────────────────────────────────────────


class SpeechEngine:
    """
    Non-blocking, priority-driven TTS engine.

    Usage
    -----
        engine = SpeechEngine()
        engine.speak("Hello")                           # normal priority
        engine.speak("Watch out!", Priority.URGENT)     # interrupts current
    """

    MAX_RETRIES = 3

    def __init__(self) -> None:
        cfg = get_config()
        self._logger = get_logger()

        # pyttsx3 state  – must be created on the *worker* thread (Windows COM)
        self._engine: Optional[pyttsx3.Engine] = None
        self._rate   = cfg.speech.rate
        self._volume = cfg.speech.volume
        self._voice  = cfg.speech.voice_id

        # synchronisation
        self._queue:      queue.PriorityQueue[_SpeechMessage] = queue.PriorityQueue()
        self._is_speaking = threading.Event()     # set while TTS is active
        self._stop_flag   = threading.Event()     # set once to kill worker
        self._interrupt   = threading.Event()     # set to abort current utterance

        # stats
        self._total_spoken = 0
        self._errors       = 0
        self._lock         = threading.Lock()

        # start worker
        self._worker_thread = threading.Thread(target=self._worker, daemon=True, name="REX-TTS")
        self._worker_thread.start()

    # ── pyttsx3 bootstrap (called on worker thread) ──────────────────────
    def _init_engine(self) -> None:
        try:
            self._engine = pyttsx3.init("sapi5")
            self._engine.setProperty("rate",   self._rate)
            self._engine.setProperty("volume", self._volume)
            if self._voice:
                self._engine.setProperty("voice", self._voice)
        except Exception as exc:                  # pragma: no cover
            self._logger.error(LogCategory.SPEECH, f"pyttsx3 init failed: {exc}")
            self._engine = None

    # ── worker loop ───────────────────────────────────────────────────────
    def _worker(self) -> None:
        self._init_engine()

        while not self._stop_flag.is_set():
            try:
                msg = self._queue.get(timeout=0.4)
            except queue.Empty:
                continue

            # poison pill
            if msg.text is None:
                break

            # honour interrupt flag (set by speak with interrupt=True)
            if self._interrupt.is_set():
                self._interrupt.clear()
                # re-queue the *new* urgent message that caused the interrupt
                # It is already in the queue because speak() put it there after
                # setting the flag, so we just skip the current msg.
                continue

            self._is_speaking.set()
            success = self._speak_once(msg.text)
            self._is_speaking.clear()

            if success:
                with self._lock:
                    self._total_spoken += 1
                if msg.callback:
                    try:
                        msg.callback()
                    except Exception:       # pragma: no cover
                        pass
            # on failure _speak_once already logged & counted

    def _speak_once(self, text: str) -> bool:
        """Try up to MAX_RETRIES.  Returns True on success."""
        for attempt in range(self.MAX_RETRIES):
            if self._interrupt.is_set():
                return False
            try:
                if self._engine is None:
                    self._init_engine()
                if self._engine is None:
                    return False
                self._engine.say(text)
                self._engine.runAndWait()
                return True
            except Exception as exc:
                self._logger.warning(LogCategory.SPEECH,
                                     f"TTS attempt {attempt + 1} failed: {exc}")
                # try to re-init for next attempt
                self._engine = None
                self._init_engine()

        with self._lock:
            self._errors += 1
        self._logger.error(LogCategory.SPEECH, f"TTS gave up after {self.MAX_RETRIES} retries: '{text[:60]}'")
        return False

    # ── public API ────────────────────────────────────────────────────────
    def speak(self, text: str, priority: Priority = Priority.NORMAL,
              interrupt: bool = False, callback: Optional[Callable] = None) -> bool:
        """
        Enqueue *text* for speaking.  Returns True if enqueued.

        If *interrupt* is True and something is currently playing, set the
        interrupt flag so the worker skips the remainder of the current
        utterance before picking up this one.
        """
        if not text or not text.strip():
            return False
        text = text.strip()

        if interrupt and self._is_speaking.is_set():
            self._interrupt.set()
            # give worker a moment to notice
            time.sleep(0.05)

        self._queue.put(_SpeechMessage(
            priority=int(priority),
            timestamp=time.time(),
            text=text,
            interrupt=interrupt,
            callback=callback,
        ))
        return True

    # ── convenience shortcuts ─────────────────────────────────────────────
    def speak_urgent(self, text: str) -> bool:
        return self.speak(text, Priority.URGENT, interrupt=True)

    def speak_important(self, text: str) -> bool:
        return self.speak(text, Priority.HIGH)

    def speak_background(self, text: str) -> bool:
        return self.speak(text, Priority.LOW)

    # ── state queries ─────────────────────────────────────────────────────
    def is_speaking(self) -> bool:
        return self._is_speaking.is_set()

    def queue_size(self) -> int:
        return self._queue.qsize()

    def wait_until_done(self, timeout: Optional[float] = None) -> bool:
        """Block until the queue drains.  Returns False on timeout."""
        deadline = time.time() + (timeout or 9999)
        while self.is_speaking() or self.queue_size() > 0:
            if time.time() > deadline:
                return False
            time.sleep(0.1)
        return True

    # ── runtime tuning ────────────────────────────────────────────────────
    def set_rate(self, wpm: int) -> None:
        self._rate = max(50, min(300, wpm))
        if self._engine:
            try:
                self._engine.setProperty("rate", self._rate)
            except Exception:       # pragma: no cover
                pass

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, vol))
        if self._engine:
            try:
                self._engine.setProperty("volume", self._volume)
            except Exception:       # pragma: no cover
                pass

    def set_voice(self, voice_id: str) -> None:
        self._voice = voice_id
        if self._engine:
            try:
                self._engine.setProperty("voice", voice_id)
            except Exception:       # pragma: no cover
                pass

    def get_available_voices(self) -> List[dict]:
        if self._engine is None:
            return []
        try:
            return [
                {"id": v.id, "name": v.name, "languages": v.languages, "gender": v.gender}
                for v in self._engine.getProperty("voices")
            ]
        except Exception:
            return []

    # ── queue management ──────────────────────────────────────────────────
    def clear_queue(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    # ── stats ─────────────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_spoken": self._total_spoken,
                "errors":       self._errors,
                "queue_size":   self.queue_size(),
                "is_speaking":  self.is_speaking(),
                "rate":         self._rate,
                "volume":       self._volume,
            }

    # ── lifecycle ─────────────────────────────────────────────────────────
    def shutdown(self) -> None:
        self.clear_queue()
        self._stop_flag.set()
        # poison pill
        self._queue.put(_SpeechMessage(priority=0, timestamp=0, text=None))
        self._worker_thread.join(timeout=3)
        if self._engine:
            try:
                self._engine.stop()
            except Exception:       # pragma: no cover
                pass


# ─── Utility: text pre-processing ─────────────────────────────────────────────


class SpeechFormatter:
    """Static helpers that make raw text sound better when spoken."""

    ABBREVIATIONS = {
        "e.g.": "for example", "i.e.": "that is", "etc.": "and so on",
        "vs.":  "versus",      "&":    "and",
        "Mr.":  "Mister",      "Mrs.": "Missus", "Ms.":  "Miss",
        "Dr.":  "Doctor",      "Prof.":"Professor",
        "%":    "percent",     "$":    "dollars", "€":    "euros",
    }

    @staticmethod
    def expand(text: str) -> str:
        for abbr, full in SpeechFormatter.ABBREVIATIONS.items():
            text = text.replace(abbr, full)
        return text

    @staticmethod
    def format_time(hour: int, minute: int) -> str:
        period = "A M" if hour < 12 else "P M"
        h      = hour % 12 or 12
        if minute == 0:
            return f"{h} o'clock {period}"
        if minute < 10:
            return f"{h} oh {minute} {period}"
        return f"{h} {minute} {period}"

    @staticmethod
    def format_list(items: List[str], conjunction: str = "and") -> str:
        if not items:         return ""
        if len(items) == 1:   return items[0]
        if len(items) == 2:   return f"{items[0]} {conjunction} {items[1]}"
        return ", ".join(items[:-1]) + f", {conjunction} {items[-1]}"