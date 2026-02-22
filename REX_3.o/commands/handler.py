# ============================================
# FILE: commands/handler.py - FINAL FIXED VERSION
# REX 4.0 - Fast & Reliable Command Handler
# ============================================

import os
import datetime
import subprocess
from typing import Dict, Any, Callable, Optional


class CommandHandler:
    """Fast, reliable command handler"""
    
    def __init__(self, speech, memory, history, system_controller, advanced_features, routines):
        self.speech = speech
        self.memory = memory
        self.history = history
        self.system_controller = system_controller
        self.advanced_features = advanced_features
        self.routines = routines
    
    def handle_command(self, command: str, intent: str, user: str, role: str, 
                      listen_func: Optional[Callable] = None) -> Dict[str, Any]:
        """Handle command execution - FAST & SIMPLE"""
        
        result = {
            "success": False,
            "message": "",
            "target": None,
            "undoable": False,
            "state_change": None,
            "exit": False
        }
        
        print(f"\n[DEBUG] Command: '{command}'")
        print(f"[DEBUG] Intent: '{intent}'")
        
        try:
            # Check permissions
            if not self._has_permission(role, command):
                self.speech.speak("You do not have permission for that action")
                result["message"] = "Permission denied"
                return result
            
            # FAST routing based on intent
            if intent == "greeting":
                self._handle_greeting(user)
                result["success"] = True
            
            elif intent == "time_query":
                self._handle_time()
                result["success"] = True
            
            elif intent == "date_query":
                self._handle_date()
                result["success"] = True
            
            elif intent == "open_app":
                result = self._handle_open_app_fast(command)
            
            elif intent == "close_app":
                result = self._handle_close_app_fast(command)
            
            elif intent == "show_logs":
                self._handle_show_logs()
                result["success"] = True
            
            elif intent == "help":
                self._handle_help()
                result["success"] = True
            
            elif intent == "shutdown":
                result["exit"] = True
                result["success"] = True
            
            else:
                # Try to execute anyway
                if "open" in command:
                    result = self._handle_open_app_fast(command)
                else:
                    self.speech.speak("I didn't understand that. Try saying: open chrome, what time is it, or help")
                    result["success"] = False
        
        except Exception as e:
            print(f"[ERROR] {e}")
            self.speech.speak("An error occurred")
            result["success"] = False
        
        return result
    
    def _has_permission(self, role: str, command: str) -> bool:
        """Quick permission check"""
        if role == "admin":
            return True
        
        restricted = ["close", "shutdown", "delete"]
        if role == "user":
            return not any(word in command.lower() for word in restricted)
        
        if role == "guest":
            allowed = ["hello", "time", "date", "help"]
            return any(word in command.lower() for word in allowed)
        
        return False
    
    def _handle_greeting(self, user: str):
        """Quick greeting"""
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"
        
        self.speech.speak(f"{greeting} {user}")
    
    def _handle_time(self):
        """Tell time"""
        now = datetime.datetime.now().strftime("%I:%M %p")
        self.speech.speak(f"The time is {now}")
    
    def _handle_date(self):
        """Tell date"""
        today = datetime.date.today().strftime("%B %d, %Y")
        self.speech.speak(f"Today is {today}")
    
    def _handle_open_app_fast(self, command: str) -> Dict:
        """FAST app opening - NO SEARCH DELAYS"""
        
        # Extract app name
        command_lower = command.lower()
        app_name = command_lower.replace("open", "").replace("start", "").replace("launch", "").strip()
        
        if not app_name:
            self.speech.speak("Which app?")
            return {"success": False}
        
        print(f"[OPEN] Attempting to open: {app_name}")
        
        # INSTANT open for common apps
        quick_apps = {
            "chrome": "chrome",
            "browser": "chrome",
            "notepad": "notepad",
            "calculator": "calc",
            "calc": "calc",
            "paint": "mspaint",
            "explorer": "explorer",
            "word": "winword",
            "excel": "excel",
            "powerpoint": "powerpnt",
            "outlook": "outlook"
        }
        
        # Try quick open
        if app_name in quick_apps:
            try:
                self.speech.speak(f"Opening {app_name}")
                subprocess.Popen(quick_apps[app_name], shell=True)
                print(f"[SUCCESS] Opened {app_name}")
                return {"success": True, "target": app_name}
            except Exception as e:
                print(f"[ERROR] Failed to open {app_name}: {e}")
        
        # Try direct Windows start
        try:
            self.speech.speak(f"Opening {app_name}")
            os.system(f"start {app_name}")
            print(f"[SUCCESS] Opened via start command")
            return {"success": True, "target": app_name}
        except:
            pass
        
        # Last resort - search (but faster)
        self.speech.speak(f"Searching for {app_name}")
        try:
            result = self.system_controller.search_and_open(app_name)
            if result["success"]:
                self.speech.speak(f"Opened {app_name}")
            else:
                self.speech.speak(f"Could not find {app_name}")
            return result
        except Exception as e:
            print(f"[ERROR] Search failed: {e}")
            self.speech.speak("Could not open that app")
            return {"success": False}
    
    def _handle_close_app_fast(self, command: str) -> Dict:
        """Quick app closing"""
        app_name = command.lower().replace("close", "").replace("quit", "").replace("exit", "").strip()
        
        if not app_name:
            self.speech.speak("Which app should I close?")
            return {"success": False}
        
        # Map to process names
        process_map = {
            "chrome": "chrome.exe",
            "browser": "chrome.exe",
            "notepad": "notepad.exe",
            "calculator": "Calculator.exe",
            "calc": "Calculator.exe",
            "paint": "mspaint.exe",
            "explorer": "explorer.exe"
        }
        
        process_name = process_map.get(app_name, f"{app_name}.exe")
        
        try:
            self.speech.speak(f"Closing {app_name}")
            subprocess.run(f"taskkill /f /im {process_name}", shell=True, capture_output=True)
            return {"success": True}
        except:
            self.speech.speak(f"Could not close {app_name}")
            return {"success": False}
    
    def _handle_show_logs(self):
        """Show logs"""
        from core.logger import get_logger
        logger = get_logger()
        log_files = logger.list_all_log_files()
        
        if log_files:
            self.speech.speak(f"Found {len(log_files)} log files")
            print("\n📋 Recent Logs:")
            for log in log_files[:3]:
                print(f"  • {log}")
        else:
            self.speech.speak("No logs found")
    
    def _handle_help(self):
        """Show help"""
        help_text = """
╔══════════════════════════════════════╗
║       REX 4.0 - COMMANDS             ║
╠══════════════════════════════════════╣
║                                      ║
║  Say clearly:                        ║
║                                      ║
║  "open chrome"                       ║
║  "open notepad"                      ║
║  "open calculator"                   ║
║                                      ║
║  "what time is it"                   ║
║  "what is the date"                  ║
║                                      ║
║  "hello"                             ║
║  "help"                              ║
║                                      ║
║  "sleep" - Put REX to sleep          ║
║  "shutdown rex" - Exit               ║
║                                      ║
╚══════════════════════════════════════╝
        """
        self.speech.speak("Here are the commands I understand")
        print(help_text)