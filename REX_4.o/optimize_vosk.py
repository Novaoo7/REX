#!/usr/bin/env python3
# ==============================================================================
# optimize_vosk.py   –  REX 4.0   Vosk Recognition Optimizer
# ==============================================================================
# This script helps you find the BEST settings for Vosk recognition by:
#   1. Testing different confidence thresholds
#   2. Testing different energy thresholds
#   3. Showing you what works best for YOUR voice and environment
#
# Usage:
#   python optimize_vosk.py
# ==============================================================================

import sys
from pathlib import Path

# Add REX to path
rex_root = Path(__file__).parent.resolve()
if str(rex_root) not in sys.path:
    sys.path.insert(0, str(rex_root))

import json
import time
from core.config import get_config
from core.listener import VoiceListener

print("\n" + "=" * 80)
print("  REX 4.0 - Vosk Recognition Optimizer")
print("=" * 80)
print("\nThis tool will help you find the best settings for YOUR voice.\n")

# Test phrases
TEST_PHRASES = [
    "open chrome",
    "what time is it",
    "close notepad",
    "volume up",
    "search for python tutorials",
    "remind me in 10 minutes",
    "lock computer",
    "what's the date",
]

def test_recognition():
    """Interactive test to optimize settings."""
    
    config = get_config()
    
    print("=" * 80)
    print("STEP 1: Baseline Test")
    print("=" * 80)
    print(f"\nCurrent settings:")
    print(f"  Confidence threshold: {config.recognition.confidence_threshold:.2f}")
    print(f"  Sample rate: {config.audio.sample_rate} Hz")
    
    listener = VoiceListener()
    
    print("\nCalibrating microphone...")
    threshold = listener.calibrate(duration=2.0)
    print(f"✓ Energy threshold set to: {threshold:.1f}")
    
    print("\n" + "=" * 80)
    print("STEP 2: Recognition Test")
    print("=" * 80)
    print(f"\nI will show you {len(TEST_PHRASES)} test phrases.")
    print("Say each phrase clearly into your microphone.")
    print("I'll tell you what I heard and the confidence score.\n")
    
    input("Press Enter when ready to start...")
    
    results = []
    
    for i, phrase in enumerate(TEST_PHRASES, 1):
        print(f"\n[{i}/{len(TEST_PHRASES)}] Say: \"{phrase}\"")
        print("Listening...", end=" ", flush=True)
        
        result = listener.listen(timeout=15.0, phrase_timeout=5.0)
        
        if result is None:
            print("✗ Timeout - nothing heard")
            results.append({
                "expected": phrase,
                "heard": None,
                "confidence": 0.0,
                "correct": False
            })
            continue
        
        # Check if it matches
        heard = result.text.lower()
        expected = phrase.lower()
        
        # Fuzzy match (allow some variation)
        words_expected = set(expected.split())
        words_heard = set(heard.split())
        overlap = len(words_expected & words_heard)
        total = len(words_expected)
        match_ratio = overlap / total if total > 0 else 0
        
        correct = match_ratio >= 0.7  # 70% word overlap = correct
        
        symbol = "✓" if correct else "✗"
        
        print(f"{symbol} Heard: \"{heard}\" (confidence: {result.confidence:.1%})")
        
        if not correct:
            print(f"  Expected: \"{phrase}\"")
        
        results.append({
            "expected": phrase,
            "heard": heard,
            "confidence": result.confidence,
            "correct": correct,
            "match_ratio": match_ratio
        })
        
        time.sleep(0.5)
    
    # Analysis
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    correct_count = sum(1 for r in results if r["correct"])
    total_count = len(results)
    accuracy = (correct_count / total_count) * 100 if total_count > 0 else 0
    
    avg_confidence = sum(r["confidence"] for r in results if r["heard"]) / len([r for r in results if r["heard"]]) if results else 0
    
    print(f"\nAccuracy: {correct_count}/{total_count} ({accuracy:.1f}%)")
    print(f"Average confidence: {avg_confidence:.1%}")
    
    # Detailed breakdown
    print("\nDetailed Results:")
    for i, r in enumerate(results, 1):
        symbol = "✓" if r["correct"] else "✗"
        heard = r["heard"] if r["heard"] else "(nothing)"
        print(f"  {symbol} #{i}: \"{r['expected']}\" → \"{heard}\" ({r['confidence']:.1%})")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if accuracy >= 90:
        print("\n✓ Excellent! Your settings are working great.")
        print("  No changes needed.")
    
    elif accuracy >= 75:
        print("\n✓ Good accuracy. Minor improvements possible:")
        
        if avg_confidence < 0.7:
            print("\n  1. Lower confidence threshold:")
            new_threshold = max(0.5, config.recognition.confidence_threshold - 0.1)
            print(f"     In config.json, set:")
            print(f'     "confidence_threshold": {new_threshold:.2f}')
        
        print("\n  2. Speak more clearly and slower")
        print("  3. Reduce background noise")
    
    else:
        print("\n⚠ Low accuracy detected. Here's how to improve:\n")
        
        print("OPTION 1: Upgrade Vosk Model (RECOMMENDED)")
        print("  Current: vosk-model-small-en-us-0.15 (50 MB)")
        print("  Upgrade to: vosk-model-en-us-0.22-lgraph (130 MB)")
        print("  Download: https://alphacephei.com/vosk/models")
        print("  Expected accuracy: 90%+\n")
        
        print("OPTION 2: Switch to Google Speech Recognition")
        print("  Accuracy: 95-98%")
        print("  Setup: See GOOGLE_SETUP.md")
        print("  Note: Requires internet connection\n")
        
        print("OPTION 3: Adjust Settings")
        
        if avg_confidence < 0.6:
            new_threshold = 0.5
            print(f"\n  • Lower confidence threshold to {new_threshold}")
            print(f'    In config.json: "confidence_threshold": {new_threshold}')
        
        print("\n  • Improve audio quality:")
        print("    - Use a better microphone")
        print("    - Reduce background noise")
        print("    - Speak 6-12 inches from microphone")
        print("    - Speak clearly and at normal pace")
    
    # Save results
    results_file = Path("recognition_test_results.json")
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": time.time(),
            "accuracy": accuracy,
            "avg_confidence": avg_confidence,
            "energy_threshold": threshold,
            "results": results,
            "config": {
                "model_path": config.recognition.model_path,
                "confidence_threshold": config.recognition.confidence_threshold,
                "sample_rate": config.audio.sample_rate,
            }
        }, f, indent=2)
    
    print(f"\n✓ Results saved to: {results_file}")
    
    listener.shutdown()
    
    print("\n" + "=" * 80)
    print()

if __name__ == "__main__":
    try:
        test_recognition()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()