# ============================================
# FILE: core/speech.py
# REX 3.0 - Optimized Speech Engine
# ============================================

import queue
import threading
import time
from typing import Optional
import pyttsx3


class SpeechEngine:
    """Thread-safe speech engine with queue and priority support"""
    
    def __init__(self, rate: int = 170, volume: float = 1.0):
        """
        Initialize speech engine
        
        Args:
            rate: Speech rate (words per minute)
            volume: Volume level (0.0 to 1.0)
        """
        self._queue = queue.PriorityQueue()
        self._speaking = threading.Event()
        self._running = threading.Event()
        self._running.set()
        self._paused = threading.Event()
        
        self.rate = rate
        self.volume = volume
        
        # Start worker thread
        self._worker_thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="SpeechWorker"
        )
        self._worker_thread.start()
        
        print("✓ Speech engine initialized")
    
    def _worker(self):
        """Background worker for text-to-speech"""
        try:
            engine = pyttsx3.init('sapi5')
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
            
            while self._running.is_set():
                try:
                    # Wait for pause to be cleared
                    while self._paused.is_set() and self._running.is_set():
                        time.sleep(0.1)
                    
                    # Get next item (priority, text)
                    priority, text = self._queue.get(timeout=0.5)
                    
                    if text is None:
                        break
                    
                    # Speak the text
                    self._speaking.set()
                    print(f"REX: {text}")
                    
                    engine.say(text)
                    engine.runAndWait()
                    
                    self._speaking.clear()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"TTS Worker Error: {e}")
                    self._speaking.clear()
            
            # Cleanup
            engine.stop()
            
        except Exception as e:
            print(f"TTS Engine initialization failed: {e}")
    
    def speak(self, text: str, priority: int = 5):
        """
        Queue text for speaking
        
        Args:
            text: Text to speak
            priority: Priority level (0=highest, 10=lowest)
        """
        if not text or not isinstance(text, str):
            return
        
        self._queue.put((priority, text))
    
    def speak_urgent(self, text: str):
        """Speak with high priority (interrupts normal speech)"""
        self.speak(text, priority=0)
    
    def is_speaking(self) -> bool:
        """Check if currently speaking"""
        return self._speaking.is_set()
    
    def wait_until_done(self, timeout: Optional[float] = None):
        """Wait until speech is complete"""
        start_time = time.time()
        
        while self.is_speaking():
            if timeout and (time.time() - start_time) > timeout:
                return False
            time.sleep(0.1)
        
        return True
    
    def pause(self):
        """Pause speech output"""
        self._paused.set()
    
    def resume(self):
        """Resume speech output"""
        self._paused.clear()
    
    def clear_queue(self):
        """Clear all pending speech"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
    
    def set_rate(self, rate: int):
        """Change speech rate"""
        self.rate = rate
        # Note: Will take effect on next engine restart
    
    def set_volume(self, volume: float):
        """Change volume (0.0 to 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
    
    def get_queue_size(self) -> int:
        """Get number of items in queue"""
        return self._queue.qsize()
    
    def shutdown(self):
        """Gracefully shutdown speech engine"""
        print("Shutting down speech engine...")
        
        # Clear queue
        self.clear_queue()
        
        # Stop worker
        self._running.clear()
        self._queue.put((0, None))
        
        # Wait for thread to finish
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2)
        
        print("✓ Speech engine stopped")


# ============================================
# SPEECH UTILITIES
# ============================================

class SpeechFormatter:
    """Format text for better speech output"""
    
    @staticmethod
    def format_time(hour: int, minute: int) -> str:
        """Format time for speech"""
        period = "AM" if hour < 12 else "PM"
        display_hour = hour if hour <= 12 else hour - 12
        if display_hour == 0:
            display_hour = 12
        
        if minute == 0:
            return f"{display_hour} {period}"
        else:
            return f"{display_hour} {minute:02d} {period}"
    
    @staticmethod
    def format_date(date_str: str) -> str:
        """Format date for speech"""
        from datetime import datetime
        
        try:
            date_obj = datetime.fromisoformat(date_str)
            return date_obj.strftime("%B %d, %Y")
        except:
            return date_str
    
    @staticmethod
    def format_number(num: int) -> str:
        """Format large numbers for speech"""
        if num < 1000:
            return str(num)
        elif num < 1000000:
            return f"{num/1000:.1f} thousand"
        elif num < 1000000000:
            return f"{num/1000000:.1f} million"
        else:
            return f"{num/1000000000:.1f} billion"
    
    @staticmethod
    def abbreviate(text: str) -> str:
        """Expand common abbreviations for better speech"""
        replacements = {
            "e.g.": "for example",
            "i.e.": "that is",
            "etc.": "etcetera",
            "Mr.": "Mister",
            "Mrs.": "Misses",
            "Dr.": "Doctor",
            "vs.": "versus",
            "&": "and",
        }
        
        for abbr, expansion in replacements.items():
            text = text.replace(abbr, expansion)
        
        return text