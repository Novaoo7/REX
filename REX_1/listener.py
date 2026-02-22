import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import json
import time
import threading
from collections import deque

SAMPLE_RATE = 16000
BLOCK_SIZE = 8000
MAX_QUEUE_SIZE = 50

model = Model("model")
recognizer = KaldiRecognizer(model, SAMPLE_RATE)

audio_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
_stream = None
_stream_paused = threading.Event()
_stream_lock = threading.Lock()

confidence_history = deque(maxlen=10)

def audio_callback(indata, frames, time_info, status):
    from speech import is_speaking
    if _stream_paused.is_set() or is_speaking():
        return

    try:
        audio_queue.put_nowait(bytes(indata))
    except queue.Full:
        try:
            audio_queue.get_nowait()
            audio_queue.put_nowait(bytes(indata))
        except:
            pass

def start_stream():
    global _stream
    with _stream_lock:
        if _stream is None:
            _stream = sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                dtype='int16',
                channels=1,
                callback=audio_callback
            )
            _stream.start()
            _stream_paused.clear()

def stop_stream():
    global _stream
    with _stream_lock:
        if _stream:
            _stream.stop()
            _stream.close()
            _stream = None

def pause_stream():
    _stream_paused.set()
    time.sleep(0.1)

def resume_stream():
    time.sleep(0.3)
    _stream_paused.clear()

def clear_audio_buffer():
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
        except:
            break

def get_queue_status():
    return {
        "size": audio_queue.qsize(),
        "max_size": MAX_QUEUE_SIZE,
        "utilization": audio_queue.qsize() / MAX_QUEUE_SIZE
    }

def listen(timeout=None):
    from speech import is_speaking

    start_time = time.time()
    while True:
        if timeout and (time.time() - start_time) > timeout:
            return None

        if is_speaking() or _stream_paused.is_set():
            time.sleep(0.1)
            continue

        try:
            data = audio_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        if recognizer.AcceptWaveform(data):
            result = json.loads(recognizer.Result())
            text = result.get("text", "").strip().lower()
            if text:
                return text, 0.8, "UNKNOWN", {}
