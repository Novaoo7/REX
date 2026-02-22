# ============================================
# FILE: REX.py - Main System
# Realistic Experimental eXecutor
# ============================================

import sys
import datetime
import time
from pathlib import Path

# Import REX components (UNCHANGED)
from speech import speak, alert, calm, VoiceMode
from listener import (listen, start_stream, stop_stream, clear_audio_buffer,
                     get_queue_status)
from commands import handle_command, CommandResult
from logger import log_action, cleanup_old_logs, get_statistics
from auth import authenticate

# ASCII Art
REX_LOGO = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║        ██████╗ ███████╗██╗  ██╗                               ║
║        ██╔══██╗██╔════╝╚██╗██╔╝                               ║
║        ██████╔╝█████╗   ╚███╔╝                                ║
║        ██╔══██╗██╔══╝   ██╔██╗                                ║
║        ██║  ██║███████╗██╔╝ ██╗                               ║
║        ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝                               ║
║                                                               ║
║        Realistic Experimental eXecutor                        ║
║                    Version 2.0                                ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""

class RexSystem:
    """
    REX - Intelligent Voice Assistant
    """
    
    def __init__(self):
        self.state = "OFFLINE"
        self.user_name = None
        self.user_role = None
        self.session_start = datetime.datetime.now()
        self.command_count = 0
        
        # State machine
        self.states = {
            "OFFLINE": self._state_offline,
            "SLEEP": self._state_sleep,
            "ACTIVE": self._state_active,
            "WAITING_INPUT": self._state_waiting_input,
        }
        
        # State timeout management
        self.state_timestamp = datetime.datetime.now()
        self.STATE_TIMEOUT = 15  # seconds
        self.waiting_for = None
        self.input_data = {}
    
    def initialize(self):
        """System initialization"""
        print(REX_LOGO)
        print("Initializing REX systems...\n")
        
        # Create necessary directories
        Path("logs").mkdir(exist_ok=True)
        Path("memory").mkdir(exist_ok=True)
        
        # Cleanup old logs
        cleanup_old_logs()
        
        # Authenticate user
        print("🔐 Authentication required\n")
        self.user_name, self.user_role = authenticate()
        
        if not self.user_name:
            print("\n❌ Authentication failed")
            return False
        
        print("\n" + "="*65)
        print("✅ REX systems online and ready")
        print("="*65 + "\n")
        
        # Initialize voice system
        start_stream()
        log_action("SYSTEM", f"REX initialized - User: {self.user_name} ({self.user_role})")
        
        # Welcome message
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"
        
        speak(f"{greeting}, {self.user_name}. REX is online and ready to assist", 
              mode=VoiceMode.NORMAL)
        
        # Security briefing
        if self.user_role == "admin":
            speak("All systems accessible. Full administrative control granted")
        elif self.user_role == "user":
            speak("Standard access level. Most operations available")
        else:
            speak("Limited access granted. Read-only operations available")
        
        # Initial state
        self.state = "SLEEP"
        calm("I am in standby mode. Say REX to wake me")
        
        return True
    
    def run(self):
        """Main system loop"""
        try:
            while True:
                # Check state timeout
                self._check_state_timeout()
                
                # Execute current state
                state_handler = self.states.get(self.state, self._state_active)
                state_handler()
                
                # Small delay to prevent CPU overload
                time.sleep(0.05)
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Keyboard interrupt detected")
            self.shutdown()
        
        except Exception as e:
            print(f"\n\n🚨 Critical error: {e}")
            log_action("ERROR", f"Critical system error: {e}", level="CRITICAL")
            self.shutdown()
    
    def _state_offline(self):
        """Offline state - should not reach here"""
        print("System offline")
        time.sleep(1)
    
    def _state_sleep(self):
        """Sleep state - waiting for wake word"""
        result = listen(timeout=1)
        
        if not result:
            return
        
        text, confidence, intent, entities = result
        
        # Only respond to wake word
        if intent == "WAKE" or "rex" in text.lower():
            self.state = "ACTIVE"
            self.state_timestamp = datetime.datetime.now()
            
            speak("Systems active. How may I help you?", mode=VoiceMode.NORMAL)
            log_action("SYSTEM", "REX activated")
            
            # Clear any accumulated audio
            clear_audio_buffer()
    
    def _state_active(self):
        """Active state - listening for commands"""
        result = listen(timeout=1)
        
        if not result:
            return
        
        text, confidence, intent, entities = result
        
        print(f"\n{'='*65}")
        print(f"🎤 You: {text}")
        print(f"🎯 Intent: {intent} | Confidence: {confidence:.2f}")
        if entities:
            print(f"📦 Entities: {entities}")
        print(f"{'='*65}\n")
        
        self.command_count += 1
        
        # Handle command
        result_code, data = handle_command(
            text, intent, entities, confidence,
            self.user_name, self.user_role,
            listen_func=listen
        )
        
        # Process result
        if result_code == CommandResult.EXIT:
            self.shutdown()
            return
        
        elif result_code == CommandResult.CONTINUE:
            # State change requested
            if data and "state_change" in data:
                new_state = data["state_change"]
                self.state = new_state
                self.state_timestamp = datetime.datetime.now()
                log_action("SYSTEM", f"State changed to: {new_state}")
        
        elif result_code == CommandResult.NEED_INPUT:
            # Switch to waiting for input
            self.state = "WAITING_INPUT"
            self.state_timestamp = datetime.datetime.now()
            self.waiting_for = data.get("expecting")
            log_action("SYSTEM", f"Waiting for: {self.waiting_for}")
        
        # Update state timestamp
        self.state_timestamp = datetime.datetime.now()
    
    def _state_waiting_input(self):
        """Waiting for specific input from user"""
        result = listen(timeout=1)
        
        if not result:
            return
        
        text, confidence, intent, entities = result
        
        print(f"🎤 Input: {text}")
        
        # Check for cancellation
        if intent == "CANCEL":
            speak("Cancelled")
            self.state = "ACTIVE"
            self.waiting_for = None
            return
        
        # Process input based on what we're waiting for
        if self.waiting_for == "log_date":
            self._process_log_date_input(text)
        
        elif self.waiting_for == "log_search_keyword":
            self._process_log_search_input(text)
        
        elif self.waiting_for == "app_name":
            self._process_app_name_input(text, entities)
        
        # Return to active state
        self.state = "ACTIVE"
        self.state_timestamp = datetime.datetime.now()
        self.waiting_for = None
    
    def _process_log_date_input(self, text: str):
        from logger import open_logs
        
        if "today" in text:
            date_str = datetime.date.today().isoformat()
        elif "yesterday" in text:
            yesterday = datetime.date.today() - datetime.timedelta(days=1)
            date_str = yesterday.isoformat()
        else:
            date_str = text.replace(" ", "-")
        
        if open_logs(date_str):
            speak(f"Opening logs for {date_str}")
        else:
            speak(f"No logs found for {date_str}")
    
    def _process_log_search_input(self, text: str):
        from logger import search_logs
        
        keyword = text.strip()
        results = search_logs(keyword, days=7)
        
        if results:
            speak(f"Found {len(results)} days with logs containing {keyword}")
        else:
            speak(f"No logs found containing {keyword}")
    
    def _process_app_name_input(self, text: str, entities: dict):
        app_name = entities.get("apps", text.strip())
        
        handle_command(
            f"open {app_name}", "OPEN_APP", {"apps": app_name}, 0.9,
            self.user_name, self.user_role, listen_func=listen
        )
    
    def _check_state_timeout(self):
        if self.state in ["ACTIVE", "SLEEP"]:
            return
        
        elapsed = (datetime.datetime.now() - self.state_timestamp).seconds
        
        if elapsed > self.STATE_TIMEOUT:
            speak("Timeout. Returning to active mode", mode=VoiceMode.ALERT)
            log_action("SYSTEM", f"State timeout: {self.state}")
            self.state = "ACTIVE"
            self.state_timestamp = datetime.datetime.now()
            self.waiting_for = None
    
    def shutdown(self):
        print("\n" + "="*65)
        print("Shutting down REX systems...")
        print("="*65 + "\n")
        
        session_duration = datetime.datetime.now() - self.session_start
        minutes = int(session_duration.total_seconds() / 60)
        
        speak("Shutting down all systems", mode=VoiceMode.CALM)
        
        stop_stream()
        
        log_action("SYSTEM", 
                  f"REX shutdown - Session: {minutes} min, Commands: {self.command_count}",
                  level="INFO")
        
        speak("All systems offline. Goodbye sir", mode=VoiceMode.CALM)
        
        sys.exit(0)

# ============================================
# MAIN ENTRY POINT
# ============================================

def main():
    rex = RexSystem()
    
    if rex.initialize():
        rex.run()
    else:
        print("Failed to initialize REX")
        sys.exit(1)

if __name__ == "__main__":
    main()
