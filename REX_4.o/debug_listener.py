#!/usr/bin/env python3
# ==============================================================================
# debug_listener.py   –  REX 4.0   Voice Recognition Debugger
# ==============================================================================
# This tool shows you EXACTLY what REX hears when you speak, including:
#   • Raw audio levels (real-time meter)
#   • Voice Activity Detection (when REX thinks you're speaking)
#   • Vosk partial results (what it's hearing as you speak)
#   • Final recognized text
#   • Confidence scores
#   • Intent classification
#
# Usage:
#   python debug_listener.py
#
# Press Ctrl+C to exit
# ==============================================================================

import sys
from pathlib import Path

# Add REX to path
rex_root = Path(__file__).parent.resolve()
if str(rex_root) not in sys.path:
    sys.path.insert(0, str(rex_root))

import time
from core.config import get_config
from core.listener import VoiceListener
from core.intent import IntentClassifier

# Color codes for terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def clear_line():
    """Clear current line in terminal"""
    print('\r' + ' ' * 100 + '\r', end='', flush=True)

def print_header():
    """Print debug header"""
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}{Colors.CYAN}  REX 4.0 - Voice Recognition Debugger{Colors.END}")
    print("=" * 80)
    print(f"\n{Colors.YELLOW}This tool shows you what REX hears in real-time.{Colors.END}")
    print(f"{Colors.YELLOW}Speak normally into your microphone.{Colors.END}")
    print(f"{Colors.YELLOW}Press Ctrl+C to exit.{Colors.END}\n")

def print_audio_meter(energy: float, threshold: float):
    """Display a visual audio level meter"""
    bar_length = 50
    max_energy = threshold * 3  # Scale to 3x threshold
    filled = int((energy / max_energy) * bar_length)
    filled = min(filled, bar_length)
    
    # Color based on level
    if energy < threshold * 0.5:
        color = Colors.BLUE
        status = "QUIET"
    elif energy < threshold:
        color = Colors.CYAN
        status = "NOISE"
    else:
        color = Colors.GREEN
        status = "SPEAKING"
    
    bar = "█" * filled + "░" * (bar_length - filled)
    print(f"\r{color}[{bar}] {status:8} Energy: {energy:6.1f} / Threshold: {threshold:6.1f}{Colors.END}", 
          end='', flush=True)

def main():
    print_header()
    
    # Load config
    print(f"{Colors.CYAN}Loading configuration...{Colors.END}")
    config = get_config()
    
    # Initialize listener
    print(f"{Colors.CYAN}Initializing voice listener...{Colors.END}")
    listener = VoiceListener()
    
    # Initialize intent classifier
    print(f"{Colors.CYAN}Loading intent classifier...{Colors.END}")
    classifier = IntentClassifier()
    
    # Calibrate
    print(f"\n{Colors.YELLOW}Calibrating microphone... (stay quiet for 2 seconds){Colors.END}")
    threshold = listener.calibrate(duration=2.0)
    print(f"{Colors.GREEN}✓ Calibration complete! Threshold: {threshold:.1f}{Colors.END}\n")
    
    # Start monitoring
    print("=" * 80)
    print(f"{Colors.BOLD}MONITORING - Speak into your microphone{Colors.END}")
    print("=" * 80 + "\n")
    
    # Open audio stream
    listener._ensure_stream()
    
    session_count = 1
    
    try:
        while True:
            # Show audio levels in real-time
            for _ in range(10):  # Check levels 10 times before listening
                try:
                    # Peek at audio queue without removing
                    if not listener._audio_q.empty():
                        energy = listener._energy_threshold * 1.5  # Approximate
                    else:
                        energy = listener._energy_threshold * 0.5
                    
                    print_audio_meter(energy, listener._energy_threshold)
                    time.sleep(0.1)
                except KeyboardInterrupt:
                    raise
                except Exception:
                    pass
            
            # Listen for a phrase
            clear_line()
            print(f"\n{Colors.CYAN}[Session #{session_count}] Listening for speech...{Colors.END}")
            
            result = listener.listen(timeout=10.0, phrase_timeout=3.0)
            
            if result is None:
                print(f"{Colors.YELLOW}  ⏱  Timeout - no speech detected{Colors.END}\n")
                continue
            
            # Display results
            print(f"\n{Colors.GREEN}{'─' * 80}{Colors.END}")
            print(f"{Colors.BOLD}RECOGNIZED:{Colors.END}")
            print(f"  {Colors.CYAN}Text:{Colors.END}       {Colors.BOLD}\"{result.text}\"{Colors.END}")
            print(f"  {Colors.CYAN}Confidence:{Colors.END} {result.confidence:.2%}")
            print(f"  {Colors.CYAN}Timestamp:{Colors.END}  {time.strftime('%H:%M:%S', time.localtime(result.timestamp))}")
            
            if result.alternatives:
                print(f"  {Colors.CYAN}Alternatives:{Colors.END} {', '.join(result.alternatives[:3])}")
            
            # Classify intent
            intent_result = classifier.classify(result.text)
            
            print(f"\n{Colors.BOLD}INTENT CLASSIFICATION:{Colors.END}")
            print(f"  {Colors.CYAN}Intent:{Colors.END}     {Colors.YELLOW}{intent_result.intent.value}{Colors.END}")
            print(f"  {Colors.CYAN}Confidence:{Colors.END} {intent_result.confidence:.2%}")
            
            if intent_result.parameters:
                print(f"  {Colors.CYAN}Parameters:{Colors.END}")
                for key, val in intent_result.parameters.items():
                    print(f"    • {key}: {Colors.GREEN}{val}{Colors.END}")
            
            if intent_result.alternatives:
                print(f"  {Colors.CYAN}Alt intents:{Colors.END}")
                for alt_intent, alt_conf in intent_result.alternatives[:3]:
                    print(f"    • {alt_intent.value} ({alt_conf:.2%})")
            
            print(f"{Colors.GREEN}{'─' * 80}{Colors.END}\n")
            
            session_count += 1
            
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.END}")
    finally:
        # Cleanup
        print(f"\n{Colors.CYAN}Shutting down...{Colors.END}")
        listener.shutdown()
        
        # Stats
        stats = listener.get_stats()
        print(f"\n{Colors.BOLD}SESSION STATISTICS:{Colors.END}")
        print(f"  Total recognized: {stats['total_recognised']}")
        print(f"  Errors:          {stats['errors']}")
        print(f"  Final threshold: {stats['energy_threshold']:.1f}")
        print(f"\n{Colors.GREEN}✓ Debugger closed{Colors.END}\n")

if __name__ == "__main__":
    main()