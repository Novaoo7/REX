#!/usr/bin/env python3
# test_google.py - Check Google Speech installation

print("\n" + "=" * 70)
print("  Testing Google Speech Recognition Installation")
print("=" * 70 + "\n")

# Test 1: SpeechRecognition
print("[1/2] Checking SpeechRecognition...")
try:
    import speech_recognition as sr
    print(f"      ✓ speech_recognition installed (version {sr.__version__})")
except ImportError as e:
    print(f"      ✗ speech_recognition NOT installed")
    print(f"      Error: {e}")
    print(f"\n      Install with: pip install SpeechRecognition")
    exit(1)

# Test 2: PyAudio
print("\n[2/2] Checking PyAudio...")
try:
    import pyaudio
    print(f"      ✓ pyaudio installed (version {pyaudio.__version__})")
except ImportError as e:
    print(f"      ✗ pyaudio NOT installed")
    print(f"      Error: {e}")
    print(f"\n      Install with one of these:")
    print(f"      • pip install pyaudio")
    print(f"      • pip install pipwin && pipwin install pyaudio")
    print(f"      • Download .whl from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio")
    exit(1)

# Test 3: Can create Recognizer?
print("\n[3/3] Testing Google Speech API...")
try:
    r = sr.Recognizer()
    m = sr.Microphone()
    print(f"      ✓ Google Speech API ready")
    print(f"      ✓ Microphone detected: {m.device_index}")
except Exception as e:
    print(f"      ✗ Failed to initialize")
    print(f"      Error: {e}")
    exit(1)

print("\n" + "=" * 70)
print("  ✓ Google Speech Recognition is fully installed!")
print("=" * 70)
print("\n  REX will now use Google when online.")
print("  Run: python REX_4.o.py\n")