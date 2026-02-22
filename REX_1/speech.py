import pyttsx3
import time
import threading
from enum import Enum

class VoiceMode(Enum):
    NORMAL = "normal"
    ALERT = "alert"
    CALM = "calm"

class JarvisTTS:

    def __init__(self):
        self._speaking = threading.Event()

    def speak(self, text, mode=None):
        self._speaking.set()
        print("REX:", text)

        try:
            from listener import pause_stream
            pause_stream()

            engine = pyttsx3.init('sapi5')
            engine.setProperty("rate", 170)
            engine.say(text)
            engine.runAndWait()
            del engine

        except Exception as e:
            print("TTS Error:", e)

        time.sleep(0.5)
        self._speaking.clear()

        from listener import resume_stream
        resume_stream()

    def is_speaking(self):
        return self._speaking.is_set()

_jarvis_tts = JarvisTTS()

def speak(text, mode=None):
    _jarvis_tts.speak(text, mode)

def calm(text):
    speak(text)

def alert(text):
    speak(text)

def is_speaking():
    return _jarvis_tts.is_speaking()
