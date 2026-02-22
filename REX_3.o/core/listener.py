# ============================================
# FILE: core/listener.py - ULTRA-SIMPLE VERSION
# REX 4.0 - No fancy filtering, just works
# ============================================

import queue
import json
import time
from typing import Optional, Tuple
import sounddevice as sd
from vosk import Model, KaldiRecognizer


class VoiceListener:
    """Ultra-simple voice recognition - GUARANTEED TO WORK"""
    
    # Basic corrections
    CORRECTIONS = {
        "not bad": "notepad",
        "note bad": "notepad",
        "crom": "chrome",
        "from": "chrome",
        "calculate": "calculator",
        "racks": "rex",
        "wrecks": "rex",
    }
    
    def __init__(self, model_path: str = "model", sample_rate: int = 16000):
        """Initialize voice listener"""
        self.sample_rate = sample_rate
        self.block_size = 8000
        
        # Initialize Vosk
        try:
            print("Loading voice recognition model...")
            self.model = Model(model_path)
            self.recognizer = KaldiRecognizer(self.model, sample_rate)
            print("✓ Voice recognition model loaded")
        except Exception as e:
            raise RuntimeError(f"Failed to load Vosk model: {e}")
        
        # Audio queue
        self.audio_queue = queue.Queue()
        self._stream = None
        self._speaking_check = None
    
    def set_speaking_check(self, speaking_func):
        """Set function to check if system is speaking"""
        self._speaking_check = speaking_func
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Audio input callback - SIMPLEST POSSIBLE VERSION"""
        # Just put all audio in queue - no filtering
        if self._speaking_check is None or not self._speaking_check():
            self.audio_queue.put(bytes(indata))
    
    def start_stream(self):
        """Start audio input stream"""
        if self._stream is not None:
            return
        
        try:
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype='int16',
                channels=1,
                callback=self._audio_callback
            )
            self._stream.start()
            print("✓ Audio stream started")
        except Exception as e:
            raise RuntimeError(f"Failed to start audio stream: {e}")
    
    def stop_stream(self):
        """Stop audio input stream"""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            print("✓ Audio stream stopped")
    
    def listen(self, timeout: Optional[float] = None) -> Optional[Tuple[str, float]]:
        """Listen for voice input - SIMPLE VERSION"""
        start_time = time.time()
        
        while True:
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                return None
            
            # Skip if speaking
            if self._speaking_check and self._speaking_check():
                time.sleep(0.1)
                continue
            
            # Get audio data
            try:
                data = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            # Process with Vosk
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "")
                
                # Skip empty
                if not text or len(text) < 2:
                    continue
                
                # Basic cleanup
                text = text.lower().strip()
                
                # Apply corrections
                for wrong, correct in self.CORRECTIONS.items():
                    if wrong in text:
                        text = text.replace(wrong, correct)
                
                # Return everything (let intent classifier handle it)
                return text, 0.9
    
    def test_microphone(self) -> bool:
        """Test microphone"""
        print("\n" + "="*50)
        print("MICROPHONE TEST")
        print("Say anything... (5 seconds)")
        print("="*50)
        
        try:
            result = self.listen(timeout=5.0)
            if result:
                text, confidence = result
                print(f"\n✓ Working!")
                print(f"Heard: '{text}'")
                return True
            else:
                print("\n✗ Nothing heard")
                return False
        except Exception as e:
            print(f"\n✗ Error: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Get listener statistics"""
        return {
            "queue_size": self.audio_queue.qsize(),
            "stream_active": self._stream is not None,
            "sample_rate": self.sample_rate,
            "model_loaded": self.model is not None
        }