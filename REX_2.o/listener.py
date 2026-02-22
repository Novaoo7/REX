# ============================================
# FILE: listener.py - FIXED
# ============================================
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import json
import time

# ----------- CONFIG -----------
SAMPLE_RATE = 16000
BLOCK_SIZE = 8000

# ----------- COMMON CORRECTIONS -----------
COMMON_CORRECTIONS = {
    "not bad": "notepad",
    "note bad": "notepad",
    "north pad": "notepad",
    "note pad": "notepad",
    "note book": "notepad",
    
    "chrome browser": "chrome",
    "google chrome": "chrome",
    "crom": "chrome",
    
    "calculator": "calc",
    "calculate": "calc",
    "cal": "calc",
    
    "shut down": "shutdown",
    "power off": "shutdown",
    "turn off": "shutdown",
    
    "close rex": "shutdown rex",
    "quit": "exit",
    
    "good morning": "hello",
    "good evening": "hello",
    "what's up": "hello"
}

# ----------- LOW CONFIDENCE DETECTION -----------
LOW_CONFIDENCE_KEYWORDS = [
    "not bad", "note bad", "north pad", "note book",
    "unknown", "something", "crom", "cal"
]

def normalize_command(text: str) -> str:
    """
    Cleans and corrects recognized speech
    Fixes common misheard words
    """
    text = text.lower().strip()
    
    # Apply corrections
    for wrong, correct in COMMON_CORRECTIONS.items():
        if wrong in text:
            text = text.replace(wrong, correct)
    
    return text

def is_low_confidence(text: str) -> bool:
    """
    Detects if the recognized command is likely incorrect
    """
    for word in LOW_CONFIDENCE_KEYWORDS:
        if word in text:
            return True
    return False

# ----------- VOSK GRAMMAR -----------
COMMAND_GRAMMAR = [
    # Wake/Sleep
    "rex", "wake up", "hey rex", "sleep", "go to sleep", "rest",
    
    # Greetings
    "hello", "hi", "hey", "greetings",
    
    # Time/Date
    "time", "current time", "what time", "tell me the time",
    "date", "today", "yesterday", "what date",
    
    # Basic Apps
    "open notepad", "start notepad", "launch notepad",
    "open chrome", "start chrome", "launch chrome",
    "open browser", "open google",
    "open calculator", "open calc", "start calc",
    
    # Close Apps
    "close notepad", "close chrome", "close browser",
    "close calculator", "close calc", "close vscode",
    "close code", "close edge", "close it", "close that",
    
    # System Control
    "open file", "open folder", "create folder", "delete file",
    "open camera", "start camera", "test microphone", "test mic",
    "open settings", "open control panel", "open task manager",
    
    # Routines
    "morning routine", "work mode", "sleep mode",
    
    # Logs
    "show all logs", "list logs", "open logs", "search logs",
    
    # Confirmations
    "yes", "yeah", "no", "confirm", "cancel", "sure", "ok", "okay", "authorize",
    
    # Numbers
    "one", "two", "three", "four", "five",
    
    # Exit - IMPORTANT
    "shutdown rex", "exit", "quit rex", "close rex"
]

grammar_json = str(COMMAND_GRAMMAR).replace("'", '"')

# Keywords for filtering
KEYWORDS = [
    "rex", "wake", "sleep", "rest", "hello", "hi", "hey", "greetings",
    "time", "date", "today", "yesterday",
    "open", "close", "start", "launch", "exit", "shutdown", "quit",
    "create", "make", "delete", "remove", "new",
    "notepad", "chrome", "browser", "google", "vscode", "code",
    "calculator", "calc", "edge", "file", "folder", "application",
    "settings", "control", "panel", "task", "manager", "camera", "microphone", "mic",
    "logs", "search", "show", "list", "view", "find",
    "yes", "yeah", "no", "confirm", "cancel", "sure", "ok", "okay", "authorize",
    "what", "tell", "current", "test", "routine", "mode"
]

# ----------- SETUP -----------
model = Model("model")
recognizer = KaldiRecognizer(model, SAMPLE_RATE, grammar_json)
audio_queue = queue.Queue()
_stream = None

def audio_callback(indata, frames, time_info, status):
    """Only capture audio when not speaking"""
    from speech import is_speaking
    if not is_speaking():
        audio_queue.put(bytes(indata))

# ----------- FILTER LOGIC -----------
def is_valid_command(text):
    """
    Filters noise and invalid commands
    """
    if not text or len(text) < 2 or len(text) > 100:
        return False
    
    # Must contain at least one known keyword
    for word in KEYWORDS:
        if word in text:
            return True
    
    return False

# ----------- STREAM MANAGEMENT -----------
def start_stream():
    """Initialize the audio stream"""
    global _stream
    _stream = sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        dtype='int16',
        channels=1,
        callback=audio_callback
    )
    _stream.start()

def stop_stream():
    """Stop the audio stream"""
    global _stream
    if _stream:
        _stream.stop()
        _stream.close()

# ----------- LISTEN FUNCTION -----------
def listen():
    """
    Listen for voice input and return transcribed text
    """
    from speech import is_speaking
    
    while True:
        if is_speaking():
            time.sleep(0.1)
            continue
        
        try:
            data = audio_queue.get(timeout=0.1)
        except queue.Empty:
            continue
        
        if recognizer.AcceptWaveform(data):
            result = json.loads(recognizer.Result())
            raw_text = result.get("text", "")
            text = normalize_command(raw_text)
            
            if is_valid_command(text):
                confidence = not is_low_confidence(raw_text)
                return text, confidence
            else:
                continue