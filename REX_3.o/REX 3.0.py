# ============================================
# FILE: main.py - FIXED VERSION
# REX 3.0 - No More Hanging!
# ============================================

import sys
import time
import signal
from pathlib import Path

# Core modules
from core.config import SystemConfig
from core.logger import Logger, log_action
from core.speech import SpeechEngine
from core.listener import VoiceListener
from core.auth import AuthenticationManager
from core.intent import IntentClassifier
from core.history import CommandHistory, CommandRecord

# Intelligence modules
from intelligence.context_memory import ContextMemory
from intelligence.conversation import ConversationManager
from intelligence.routines import RoutineManager
from intelligence.proactive import ProactiveAssistant

# Command modules
from commands.handler import CommandHandler
from commands.system_control import SystemController
from commands.advanced_features import AdvancedFeatures


class REXAssistant:
    """REX 3.0 - FIXED VERSION"""
    
    def __init__(self):
        print("=" * 60)
        print("REX 3.0 - Voice Assistant")
        print("Initializing...")
        print("=" * 60)
        
        # Load configuration
        self.config = SystemConfig.load()
        
        # Initialize logger
        self.logger = Logger(self.config.logs_dir)
        log_action("SYSTEM", "REX 3.0 initialization started")
        
        # Initialize core components
        self._init_core_components()
        
        # Initialize intelligence
        self._init_intelligence()
        
        # Initialize command handlers
        self._init_command_handlers()
        
        # State
        self.state = "SLEEP"
        self.running = True
        self.current_user = None
        self.user_role = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        log_action("SYSTEM", "REX 3.0 initialization complete")
    
    def _init_core_components(self):
        """Initialize core components"""
        try:
            self.speech = SpeechEngine(rate=self.config.speech_rate)
            self.listener = VoiceListener(
                model_path=self.config.vosk_model_path,
                sample_rate=self.config.sample_rate
            )
            # Connect speech check to listener
            self.listener.set_speaking_check(self.speech.is_speaking)
            
            self.auth = AuthenticationManager()
            self.intent_classifier = IntentClassifier()
            self.history = CommandHistory(max_size=self.config.command_history_size)
            
            print("✓ Core components initialized")
        except Exception as e:
            print(f"✗ Failed to initialize core: {e}")
            raise
    
    def _init_intelligence(self):
        """Initialize intelligence layer"""
        try:
            self.memory = ContextMemory()
            self.conversation = ConversationManager(self.memory)
            self.routines = RoutineManager()
            self.proactive = ProactiveAssistant(self.memory)
            
            print("✓ Intelligence layer initialized")
        except Exception as e:
            print(f"✗ Failed to initialize intelligence: {e}")
            raise
    
    def _init_command_handlers(self):
        """Initialize command handlers"""
        try:
            self.system_controller = SystemController()
            self.advanced_features = AdvancedFeatures()
            self.command_handler = CommandHandler(
                speech=self.speech,
                memory=self.memory,
                history=self.history,
                system_controller=self.system_controller,
                advanced_features=self.advanced_features,
                routines=self.routines
            )
            
            print("✓ Command handlers initialized")
        except Exception as e:
            print(f"✗ Failed to initialize handlers: {e}")
            raise
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\n[!] Shutdown requested...")
        self.running = False
    
    def authenticate_user(self) -> bool:
        """Authenticate user"""
        print("\n" + "=" * 60)
        print("USER AUTHENTICATION")
        print("=" * 60)
        
        max_attempts = 3
        attempts = 0
        
        while attempts < max_attempts:
            username = input("Username: ").strip()
            password = input("Password: ").strip()
            
            success, role = self.auth.authenticate(username, password)
            
            if success:
                self.current_user = username
                self.user_role = role
                
                print(f"\n✓ Access Granted")
                print(f"User: {username}")
                print(f"Role: {role}")
                print("=" * 60)
                
                self.speech.speak(f"Welcome {username}")
                
                log_action("AUTH", f"User {username} logged in")
                
                self.memory.set_preference("user_name", username)
                self.memory.set_preference("user_role", role)
                
                return True
            else:
                attempts += 1
                remaining = max_attempts - attempts
                print(f"\n✗ Access Denied. {remaining} attempts remaining.\n")
        
        print("\n✗ Maximum attempts exceeded.")
        return False
    
    def run(self):
        """Main execution loop - SIMPLIFIED"""
        
        # Authenticate
        if not self.authenticate_user():
            return
        
        # Start audio
        try:
            self.listener.start_stream()
        except Exception as e:
            print(f"Failed to start audio: {e}")
            return
        
        # Initial message
        self.speech.speak("REX is in sleep mode. Say rex to wake me up.")
        
        # Main loop
        print("\n" + "=" * 60)
        print("REX 3.0 IS NOW LISTENING")
        print("Say 'rex' to wake up | Say 'shutdown rex' to exit")
        print("=" * 60 + "\n")
        
        while self.running:
            try:
                # Listen for input
                result = self.listener.listen()
                if not result:
                    continue
                
                command, confidence = result
                
                # Show what was heard
                print(f"\n🎤 You said: '{command}'")
                
                # Handle based on state
                if self.state == "SLEEP":
                    # Only respond to wake words
                    if "rex" in command.lower() or "wake" in command.lower():
                        self.state = "ACTIVE"
                        self.speech.speak("I am listening")
                        log_action("SYSTEM", "REX activated")
                    # Ignore everything else in sleep mode
                    continue
                
                elif self.state == "ACTIVE":
                    # Handle active commands
                    self._handle_active_command(command, confidence)
                
            except KeyboardInterrupt:
                print("\n[!] Interrupted by user")
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                log_action("ERROR", f"Main loop error: {e}")
                continue
        
        # Shutdown
        self.shutdown()
    
    def _handle_active_command(self, command: str, confidence: float):
        """Handle commands in active mode"""
        
        # Sleep command
        if "sleep" in command.lower() or "rest" in command.lower():
            self.state = "SLEEP"
            self.speech.speak("Going to sleep. Say rex to wake me.")
            log_action("SYSTEM", "REX deactivated")
            return
        
        # Exit command
        if "shutdown" in command.lower() and "rex" in command.lower():
            self.speech.speak("Are you sure? Say yes to confirm")
            
            result = self.listener.listen(timeout=5.0)
            if result and "yes" in result[0].lower():
                self.speech.speak(f"Goodbye {self.current_user}")
                self.running = False
            else:
                self.speech.speak("Cancelled")
            return
        
        # Classify intent
        intent, intent_confidence = self.intent_classifier.classify(command)
        
        # Execute command
        try:
            start_time = time.time()
            
            result = self.command_handler.handle_command(
                command=command,
                intent=intent,
                user=self.current_user,
                role=self.user_role,
                listen_func=self.listener.listen
            )
            
            duration = time.time() - start_time
            
            # Record in history
            self.history.add(CommandRecord(
                command=command,
                action_type=intent,
                result=result,
                timestamp=time.time(),
                undoable=result.get("undoable", False)
            ))
            
            # Update memory
            self.memory.update_short_term(
                command=command,
                action_type=intent,
                target=result.get("target")
            )
            
            # Check for exit
            if result.get("exit"):
                self.running = False
            
            print(f"✓ Command executed in {duration:.2f}s")
            log_action("COMMAND", f"{intent}: {command}")
            
        except Exception as e:
            print(f"[ERROR] Command failed: {e}")
            self.speech.speak("An error occurred")
            log_action("ERROR", f"Command execution failed: {e}")
    
    def shutdown(self):
        """Clean shutdown"""
        print("\n" + "=" * 60)
        print("SHUTTING DOWN REX 3.0")
        print("=" * 60)
        
        try:
            if self.memory:
                self.memory.save_long_term()
                print("✓ Memory saved")
            
            if self.routines:
                self.routines.save_routines()
                print("✓ Routines saved")
            
            if self.listener:
                self.listener.stop_stream()
                print("✓ Audio stopped")
            
            if self.speech:
                self.speech.shutdown()
                print("✓ Speech stopped")
            
            log_action("SYSTEM", "REX 3.0 shutdown complete")
            print("\n" + "=" * 60)
            print("SHUTDOWN COMPLETE")
            print("=" * 60)
            
        except Exception as e:
            print(f"Error during shutdown: {e}")


def main():
    """Entry point"""
    try:
        # Check Python version
        if sys.version_info < (3, 8):
            print("ERROR: Python 3.8+ required")
            sys.exit(1)
        
        # Create and run REX
        rex = REXAssistant()
        rex.run()
        
    except KeyboardInterrupt:
        print("\n\nShutdown by user")
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()