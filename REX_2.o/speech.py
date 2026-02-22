# ============================================
# FILE: speech.py
# ============================================
import pyttsx3
import time
import threading

_speaking = threading.Event()

def speak(text):
    """
    Reinitialize engine each time to avoid audio conflicts
    Ensures clean audio device access
    """
    _speaking.set()
    print("REX:", text)
    
    try:
        engine = pyttsx3.init('sapi5')
        engine.setProperty("rate", 170)
        engine.say(text)
        engine.runAndWait()
        del engine
    except Exception as e:
        print(f"TTS Error: {e}")
    
    time.sleep(0.3)
    _speaking.clear()

def is_speaking():
    return _speaking.is_set()