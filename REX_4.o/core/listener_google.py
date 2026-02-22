# ==============================================================================
# core/listener_google.py   –  REX 4.0   Google Speech Recognition
# ==============================================================================
# Alternative to Vosk - uses Google's cloud API for 95-98% accuracy.
# Requires internet connection but FREE up to 50 requests/day.
#
# To use this instead of Vosk:
#   1. pip install SpeechRecognition pyaudio
#   2. In main.py: from core.listener_google import GoogleVoiceListener
#   3. Change: listener = GoogleVoiceListener()
# ==============================================================================

from __future__ import annotations

import time
import queue
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional

import speech_recognition as sr
import numpy as np

from core.config import get_config
from core.logger import get_logger, LogCategory


@dataclass
class RecognitionResult:
    text:         str
    confidence:   float
    timestamp:    float
    alternatives: List[str]


class GoogleVoiceListener:
    """
    Google Speech Recognition listener - much more accurate than Vosk.
    
    Pros:
    - 95-98% accuracy (vs 75-85% for Vosk small)
    - Handles accents better
    - Better with background noise
    - Free up to 50 requests/day
    
    Cons:
    - Requires internet connection
    - Sends audio to Google servers (privacy concern)
    - Rate limited
    
    Usage:
        listener = GoogleVoiceListener()
        listener.calibrate(duration=2.0)
        result = listener.listen(timeout=10.0)
    """
    
    def __init__(self, speaking_check: Optional[Callable[[], bool]] = None):
        self._cfg    = get_config()
        self._logger = get_logger()
        
        # Google recognizer
        self._recognizer = sr.Recognizer()
        self._microphone = sr.Microphone(
            sample_rate=self._cfg.audio.sample_rate,
        )
        
        # Speaking check (to avoid echo)
        self._is_speaking = speaking_check or (lambda: False)
        
        # Stats
        self._total_recognised = 0
        self._errors          = 0
        
        self._logger.info(LogCategory.SYSTEM, "GoogleVoiceListener initialized")
    
    def calibrate(self, duration: float = 1.5) -> float:
        """
        Adjust for ambient noise. Google handles this automatically but we
        still call it for consistency with Vosk listener.
        """
        self._logger.info(LogCategory.AUDIO, f"Calibrating for {duration}s...")
        
        with self._microphone as source:
            self._recognizer.adjust_for_ambient_noise(source, duration=duration)
        
        # Google doesn't expose the threshold but we return a dummy value
        threshold = 300.0
        self._logger.info(LogCategory.AUDIO, f"Calibration complete")
        return threshold
    
    def listen(self, timeout: float = 10.0, phrase_timeout: float = 3.0) -> Optional[RecognitionResult]:
        """
        Listen for a phrase and recognize it using Google Speech API.
        
        Returns:
            RecognitionResult if speech detected, None if timeout.
        """
        # Skip if TTS is speaking
        if self._is_speaking():
            return None
        
        try:
            with self._microphone as source:
                self._logger.debug(LogCategory.AUDIO, "Listening...")
                
                # Listen with timeout
                audio = self._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_timeout
                )
            
            # Send to Google for recognition
            self._logger.debug(LogCategory.AUDIO, "Recognizing with Google...")
            
            try:
                # Use recognize_google (free tier)
                result = self._recognizer.recognize_google(
                    audio,
                    show_all=True,  # Get alternatives
                    language="en-US"
                )
                
                if not result or not result.get("alternative"):
                    self._logger.warning(LogCategory.AUDIO, "No recognition results")
                    return None
                
                # Extract best result
                alternatives = result["alternative"]
                best = alternatives[0]
                
                text = best.get("transcript", "")
                confidence = best.get("confidence", 0.95)  # Google doesn't always return this
                
                # Get alternative transcripts
                alt_texts = [alt.get("transcript", "") for alt in alternatives[1:4]]
                
                if not text:
                    return None
                
                self._total_recognised += 1
                
                self._logger.info(
                    LogCategory.AUDIO,
                    f"Recognized: '{text}' (conf={confidence:.2f})"
                )
                
                return RecognitionResult(
                    text=text,
                    confidence=confidence,
                    timestamp=time.time(),
                    alternatives=alt_texts
                )
                
            except sr.UnknownValueError:
                self._logger.warning(LogCategory.AUDIO, "Google could not understand audio")
                self._errors += 1
                return None
            
            except sr.RequestError as e:
                self._logger.error(LogCategory.ERROR, f"Google API error: {e}")
                self._errors += 1
                return None
        
        except sr.WaitTimeoutError:
            # Normal timeout - no speech detected
            return None
        
        except Exception as exc:
            self._logger.error(LogCategory.ERROR, f"Listen error: {exc}")
            self._errors += 1
            return None
    
    def get_stats(self) -> dict:
        """Return recognition statistics."""
        return {
            "total_recognised": self._total_recognised,
            "errors":          self._errors,
            "energy_threshold": 0.0,  # Not applicable for Google
            "calibrated":      True,
        }
    
    def shutdown(self) -> None:
        """Clean shutdown."""
        self._logger.info(LogCategory.SYSTEM, "GoogleVoiceListener shutdown")


# Corrections dict - same as Vosk listener for consistency
DEFAULT_CORRECTIONS = {
    "note bad":      "notepad",
    "not bad":       "notepad",
    "no pad":        "notepad",
    "node pad":      "notepad",
    "crom":          "chrome",
    "from":          "chrome",
    "crime":         "chrome",
    "racks":         "rex",
    "wrecks":        "rex",
    "recs":          "rex",
    "hey wrecks":    "hey rex",
    "hey racks":     "hey rex",
    "firefox":       "firefox",
    "fire fox":      "firefox",
    "vs code":       "vscode",
    "visual studio": "vscode",
    "be code":       "vscode",
    "discord":       "discord",
    "this cord":     "discord",
}