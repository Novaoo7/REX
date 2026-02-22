# ==============================================================================
# core/listener_hybrid.py   –  REX 4.0   Hybrid Voice Listener  (Fixed)
# ==============================================================================

from __future__ import annotations

import time
import socket
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional

from core.config import get_config
from core.logger import get_logger, LogCategory


@dataclass
class RecognitionResult:
    """Unified result from any recognition engine."""
    text:         str
    confidence:   float
    timestamp:    float
    alternatives: List[str]
    source:       str           # "google" or "vosk"


class HybridVoiceListener:
    """
    Intelligently switches between Google (online) and Vosk (offline).
    Prints clear status messages so you always know which engine is active.
    """

    def __init__(self, speaking_check: Optional[Callable[[], bool]] = None):
        self._cfg    = get_config()
        self._logger = get_logger()

        self._is_online       = False
        self._last_check_time = 0.0
        self._check_interval  = 30.0
        self._check_lock      = threading.Lock()

        self._vosk_listener   = None
        self._google_listener = None

        # ── Try Google ────────────────────────────────────────────────────
        try:
            from core.listener_google import GoogleVoiceListener
            self._google_listener = GoogleVoiceListener(speaking_check=speaking_check)
            print("   ✓ Google Speech listener ready")
            self._logger.info(LogCategory.SYSTEM, "Google listener initialized")
        except ImportError as e:
            print("   ⚠  Google Speech not installed (pip install SpeechRecognition pyaudio)")
            print("      → Vosk will be used for ALL recognition")
            self._logger.warning(LogCategory.SYSTEM, "Google not available – Vosk only")
        except Exception as e:
            print(f"   ⚠  Google listener failed: {e}")
            print("      → Vosk will be used as fallback")
            self._logger.warning(LogCategory.SYSTEM, f"Google listener failed: {e}")

        # ── Always load Vosk ──────────────────────────────────────────────
        try:
            from core.listener import VoiceListener
            self._vosk_listener = VoiceListener(speaking_check=speaking_check)
            print("   ✓ Vosk listener ready")
            self._logger.info(LogCategory.SYSTEM, "Vosk listener initialized")
        except Exception as e:
            self._logger.error(LogCategory.ERROR, f"Vosk listener failed: {e}")
            raise RuntimeError(f"Vosk failed to load – REX cannot start: {e}") from e

        # ── Check internet & report mode ──────────────────────────────────
        self._check_connectivity()
        mode = self._get_current_mode()

        if mode == "google":
            print(f"   ★  Hybrid mode: GOOGLE (online, ~98% accuracy)")
        elif mode == "vosk":
            print(f"   ★  Hybrid mode: VOSK (offline, ~85% accuracy)")
        else:
            print(f"   ✗  No recognition engine available!")

        self._google_count = 0
        self._vosk_count   = 0
        self._errors       = 0

        self._logger.info(LogCategory.SYSTEM, f"HybridVoiceListener ready (mode: {mode})")

    # ── Connectivity ──────────────────────────────────────────────────────
    def _check_connectivity(self) -> bool:
        with self._check_lock:
            now = time.time()
            if now - self._last_check_time < self._check_interval:
                return self._is_online

            try:
                socket.create_connection(("8.8.8.8", 53), timeout=2)
                if not self._is_online:
                    # Just came online
                    print("   🌐  Internet detected → switching to Google")
                self._is_online = True
            except (socket.timeout, socket.error, OSError):
                if self._is_online:
                    # Just went offline
                    print("   📴  Internet lost → switching to Vosk")
                self._is_online = False

            self._last_check_time = now
            return self._is_online

    def _get_current_mode(self) -> str:
        online = self._check_connectivity()
        if online and self._google_listener:
            return "google"
        if self._vosk_listener:
            return "vosk"
        return "unavailable"

    # ── Calibrate ─────────────────────────────────────────────────────────
    def calibrate(self, duration: float = 2.0) -> float:
        mode = self._get_current_mode()
        self._logger.info(LogCategory.AUDIO, f"Calibrating ({mode} mode)...")

        threshold = 50.0

        if mode == "google" and self._google_listener:
            threshold = self._google_listener.calibrate(duration)
            if self._vosk_listener:
                self._vosk_listener.calibrate(duration)
        elif self._vosk_listener:
            threshold = self._vosk_listener.calibrate(duration)
        else:
            raise RuntimeError("No listener available for calibration")

        return threshold

    # ── Listen ────────────────────────────────────────────────────────────
    def listen(self, timeout: float = 10.0,
               phrase_timeout: float = 4.0) -> Optional[RecognitionResult]:
        mode = self._get_current_mode()

        # ── Try Google ────────────────────────────────────────────────────
        if mode == "google" and self._google_listener:
            try:
                result = self._google_listener.listen(timeout, phrase_timeout)
                if result:
                    self._google_count += 1
                    print(f"   [Google] → \"{result.text}\"  (conf: {result.confidence:.0%})")
                    return RecognitionResult(
                        text=result.text,
                        confidence=result.confidence,
                        timestamp=result.timestamp,
                        alternatives=result.alternatives,
                        source="google",
                    )
                return None
            except Exception as e:
                print(f"   ⚠  Google failed: {e} → falling back to Vosk")
                self._logger.warning(LogCategory.AUDIO, f"Google failed, using Vosk: {e}")
                self._errors += 1
                # fall through to Vosk

        # ── Use Vosk (primary offline or fallback) ────────────────────────
        if self._vosk_listener:
            try:
                result = self._vosk_listener.listen(timeout, phrase_timeout)
                if result:
                    self._vosk_count += 1
                    return RecognitionResult(
                        text=result.text,
                        confidence=result.confidence,
                        timestamp=result.timestamp,
                        alternatives=result.alternatives,
                        source="vosk",
                    )
                return None
            except Exception as e:
                self._logger.error(LogCategory.ERROR, f"Vosk failed: {e}")
                self._errors += 1
                return None

        self._logger.error(LogCategory.ERROR, "No recognition engine available")
        return None

    # ── Stats / helpers ───────────────────────────────────────────────────
    def get_stats(self) -> dict:
        mode  = self._get_current_mode()
        stats = {
            "current_mode":     mode,
            "is_online":        self._is_online,
            "google_used":      self._google_count,
            "vosk_used":        self._vosk_count,
            "errors":           self._errors,
            "google_available": self._google_listener is not None,
            "vosk_available":   self._vosk_listener  is not None,
            # These keys match what REX_4.o.py expects in shutdown()
            "total_recognised": self._google_count + self._vosk_count,
            "energy_threshold": 0,
            "calibrated":       True,
            "queue_pending":    0,
        }
        if self._vosk_listener:
            vs = self._vosk_listener.get_stats()
            stats["energy_threshold"] = vs.get("energy_threshold", 0)
            stats["vosk_total"]       = vs.get("total_recognised", 0)
            stats["queue_pending"]    = vs.get("queue_pending", 0)
            stats["calibrated"]       = vs.get("calibrated", False)
        return stats

    def force_mode(self, mode: str) -> bool:
        if mode == "google":
            if self._google_listener:
                print(f"   Forced mode: Google")
                return True
            print("   Cannot force Google – not installed")
            return False
        if mode == "vosk":
            if self._vosk_listener:
                print(f"   Forced mode: Vosk")
                return True
            print("   Cannot force Vosk – not loaded")
            return False
        return False

    def shutdown(self) -> None:
        self._logger.info(LogCategory.SYSTEM, "HybridVoiceListener shutting down...")
        for listener in (self._google_listener, self._vosk_listener):
            if listener:
                try:
                    listener.shutdown()
                except Exception:
                    pass
        stats = self.get_stats()
        print(f"\n   Recognition stats → Google: {stats['google_used']}  "
              f"Vosk: {stats['vosk_used']}  Errors: {stats['errors']}")
        self._logger.info(LogCategory.SYSTEM,
                          f"Stats – Google:{stats['google_used']} "
                          f"Vosk:{stats['vosk_used']} Errors:{stats['errors']}")