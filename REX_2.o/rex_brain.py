# ============================================
# FILE: rex_brain.py (NEW - Phase 1)
# REX 2.0 Intelligence Core
# ============================================

import json
import datetime
from pathlib import Path
from logger import log_action
from speech import speak

# ============================================
# ENHANCED CONTEXT MEMORY
# ============================================

class ContextMemory:
    """
    Advanced context tracking with long-term memory capabilities
    """
    
    def __init__(self):
        self.short_term = {
            "last_command": None,
            "last_app": None,
            "last_file": None,
            "last_folder": None,
            "conversation_history": [],
            "pending_action": None,
            "waiting_for": None
        }
        
        self.long_term_file = Path("memory/long_term.json")
        self.long_term = self._load_long_term()
    
    def _load_long_term(self):
        """Load long-term memory from disk"""
        if self.long_term_file.exists():
            try:
                with open(self.long_term_file, 'r') as f:
                    return json.load(f)
            except:
                return self._init_long_term()
        return self._init_long_term()
    
    def _init_long_term(self):
        """Initialize long-term memory structure"""
        return {
            "preferences": {
                "default_browser": "chrome",
                "default_editor": "notepad",
                "work_hours": {"start": 9, "end": 17},
                "verbosity": "normal"
            },
            "patterns": {
                "frequent_apps": {},
                "frequent_files": {},
                "daily_routines": []
            },
            "knowledge": {
                "contacts": {},
                "important_dates": {},
                "custom_facts": {}
            },
            "learning": {
                "corrections": {},
                "command_aliases": {}
            }
        }
    
    def save_long_term(self):
        """Persist long-term memory to disk"""
        self.long_term_file.parent.mkdir(exist_ok=True)
        with open(self.long_term_file, 'w') as f:
            json.dump(self.long_term, f, indent=2)
    
    def update_short_term(self, command, action_type=None, target=None):
        """Update short-term memory"""
        self.short_term["last_command"] = command
        
        if action_type == "open_app":
            self.short_term["last_app"] = target
            self._learn_pattern("app", target)
        elif action_type == "open_file":
            self.short_term["last_file"] = target
            self._learn_pattern("file", target)
        elif action_type == "open_folder":
            self.short_term["last_folder"] = target
        
        # Maintain conversation history (last 10 commands)
        self.short_term["conversation_history"].append({
            "command": command,
            "timestamp": datetime.datetime.now().isoformat(),
            "type": action_type
        })
        
        if len(self.short_term["conversation_history"]) > 10:
            self.short_term["conversation_history"].pop(0)
    
    def _learn_pattern(self, item_type, item_name):
        """Learn usage patterns"""
        key = f"frequent_{item_type}s"
        if item_name not in self.long_term["patterns"][key]:
            self.long_term["patterns"][key][item_name] = 0
        self.long_term["patterns"][key][item_name] += 1
        self.save_long_term()
    
    def resolve_reference(self, text):
        """
        Resolve contextual references like 'it', 'that', 'last one'
        """
        text_lower = text.lower()
        
        # Pronoun resolution
        if any(word in text_lower for word in ["it", "that", "this"]):
            if self.short_term["last_app"]:
                text = text.replace("it", self.short_term["last_app"])
                text = text.replace("that", self.short_term["last_app"])
                text = text.replace("this", self.short_term["last_app"])
        
        # Previous item references
        if "last" in text_lower or "previous" in text_lower:
            if "app" in text_lower and self.short_term["last_app"]:
                return f"open {self.short_term['last_app']}"
            elif "file" in text_lower and self.short_term["last_file"]:
                return f"open {self.short_term['last_file']}"
        
        return text
    
    def get_preference(self, key):
        """Get user preference"""
        return self.long_term["preferences"].get(key)
    
    def set_preference(self, key, value):
        """Set user preference"""
        self.long_term["preferences"][key] = value
        self.save_long_term()
    
    def remember_fact(self, category, key, value):
        """Store custom fact"""
        if category not in self.long_term["knowledge"]:
            self.long_term["knowledge"][category] = {}
        self.long_term["knowledge"][category][key] = value
        self.save_long_term()
    
    def recall_fact(self, category, key):
        """Retrieve custom fact"""
        return self.long_term["knowledge"].get(category, {}).get(key)

# ============================================
# MULTI-TURN CONVERSATION MANAGER
# ============================================

class ConversationManager:
    """
    Manages multi-turn conversations and pending actions
    """
    
    def __init__(self, memory: ContextMemory):
        self.memory = memory
        self.states = {
            "IDLE": self._handle_idle,
            "AWAITING_APP_CHOICE": self._handle_app_choice,
            "AWAITING_FILE_CHOICE": self._handle_file_choice,
            "AWAITING_CLARIFICATION": self._handle_clarification,
            "AWAITING_PARAMETER": self._handle_parameter
        }
        self.current_state = "IDLE"
        self.state_data = {}
    
    def set_state(self, state, data=None):
        """Change conversation state"""
        self.current_state = state
        self.state_data = data or {}
        self.memory.short_term["pending_action"] = state
        log_action("CONVERSATION", f"State changed to: {state}")
    
    def handle_input(self, command):
        """Process input based on current state"""
        handler = self.states.get(self.current_state, self._handle_idle)
        return handler(command)
    
    def _handle_idle(self, command):
        """Normal command processing"""
        return ("PROCESS_COMMAND", command)
    
    def _handle_app_choice(self, command):
        """Handle app selection from multiple choices"""
        choices = self.state_data.get("choices", [])
        
        # Try to match user input to choices
        for i, choice in enumerate(choices):
            if str(i+1) in command or choice.lower() in command.lower():
                self.set_state("IDLE")
                return ("OPEN_APP", choice)
        
        speak("I didn't understand. Please say the number or name")
        return ("WAIT", None)
    
    def _handle_file_choice(self, command):
        """Handle file selection from multiple choices"""
        choices = self.state_data.get("choices", [])
        
        for i, choice in enumerate(choices):
            if str(i+1) in command:
                self.set_state("IDLE")
                return ("OPEN_FILE", choice)
        
        speak("Please say the number of the file")
        return ("WAIT", None)
    
    def _handle_clarification(self, command):
        """Handle yes/no clarification"""
        if any(word in command.lower() for word in ["yes", "yeah", "sure", "correct"]):
            action = self.state_data.get("action")
            target = self.state_data.get("target")
            self.set_state("IDLE")
            return (action, target)
        else:
            speak("Okay, cancelled")
            self.set_state("IDLE")
            return ("CANCEL", None)
    
    def _handle_parameter(self, command):
        """Handle parameter collection"""
        param_type = self.state_data.get("param_type")
        action = self.state_data.get("action")
        
        # Store the parameter
        self.state_data["parameters"] = self.state_data.get("parameters", {})
        self.state_data["parameters"][param_type] = command
        
        # Check if we have all required parameters
        required = self.state_data.get("required_params", [])
        collected = list(self.state_data["parameters"].keys())
        
        if all(p in collected for p in required):
            self.set_state("IDLE")
            return (action, self.state_data["parameters"])
        else:
            # Ask for next parameter
            next_param = [p for p in required if p not in collected][0]
            speak(f"What is the {next_param}?")
            self.state_data["param_type"] = next_param
            return ("WAIT", None)

# ============================================
# ROUTINE AUTOMATION
# ============================================

class RoutineManager:
    """
    Manages automated routines and workflows
    """
    
    def __init__(self):
        self.routines_file = Path("memory/routines.json")
        self.routines = self._load_routines()
    
    def _load_routines(self):
        """Load saved routines"""
        if self.routines_file.exists():
            with open(self.routines_file, 'r') as f:
                return json.load(f)
        return self._init_default_routines()
    
    def _init_default_routines(self):
        """Create default routines"""
        return {
            "morning": {
                "name": "Morning Routine",
                "description": "Start your day productively",
                "actions": [
                    {"type": "open_app", "target": "chrome"},
                    {"type": "open_app", "target": "notepad"},
                    {"type": "speak", "text": "Good morning! Ready to start your day?"}
                ]
            },
            "work": {
                "name": "Work Mode",
                "description": "Focus on work",
                "actions": [
                    {"type": "open_app", "target": "vscode"},
                    {"type": "open_app", "target": "chrome"},
                    {"type": "speak", "text": "Work mode activated"}
                ]
            },
            "sleep": {
                "name": "Sleep Mode",
                "description": "Wind down for the night",
                "actions": [
                    {"type": "close_all_apps"},
                    {"type": "speak", "text": "Good night. Sleep well"}
                ]
            }
        }
    
    def save_routines(self):
        """Save routines to disk"""
        self.routines_file.parent.mkdir(exist_ok=True)
        with open(self.routines_file, 'w') as f:
            json.dump(self.routines, f, indent=2)
    
    def add_routine(self, name, actions, description=""):
        """Add new routine"""
        self.routines[name.lower()] = {
            "name": name,
            "description": description,
            "actions": actions
        }
        self.save_routines()
    
    def get_routine(self, name):
        """Get routine by name"""
        return self.routines.get(name.lower())
    
    def list_routines(self):
        """List all available routines"""
        return [
            f"{r['name']}: {r['description']}" 
            for r in self.routines.values()
        ]
    
    def execute_routine(self, name, executor_func):
        """Execute a routine"""
        routine = self.get_routine(name)
        if not routine:
            return False
        
        speak(f"Starting {routine['name']}")
        log_action("ROUTINE", f"Executing: {routine['name']}")
        
        for action in routine["actions"]:
            action_type = action["type"]
            
            if action_type == "open_app":
                executor_func("open_app", action["target"])
            elif action_type == "close_app":
                executor_func("close_app", action["target"])
            elif action_type == "speak":
                speak(action["text"])
            elif action_type == "close_all_apps":
                executor_func("close_all_apps", None)
            elif action_type == "wait":
                import time
                time.sleep(action.get("seconds", 1))
        
        speak(f"{routine['name']} complete")
        log_action("ROUTINE", f"Completed: {routine['name']}")
        return True

# ============================================
# PROACTIVE INTELLIGENCE
# ============================================

class ProactiveAssistant:
    """
    Provides proactive suggestions and monitoring
    """
    
    def __init__(self, memory: ContextMemory):
        self.memory = memory
        self.last_suggestion_time = None
        self.suggestion_cooldown = 300  # 5 minutes
    
    def check_battery(self):
        """Monitor battery level"""
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery and battery.percent < 20 and not battery.power_plugged:
                return f"Battery is low at {battery.percent}%. Should I enable power saving mode?"
        except:
            pass
        return None
    
    def check_time_based_suggestions(self):
        """Suggest actions based on time"""
        now = datetime.datetime.now()
        hour = now.hour
        
        # Morning routine
        if hour == 9 and self._can_suggest():
            return "Good morning! Would you like me to start your morning routine?"
        
        # Lunch break
        if hour == 12 and self._can_suggest():
            return "It's lunch time. Would you like me to lock your computer?"
        
        # End of day
        if hour == 17 and self._can_suggest():
            work_hours = self.memory.get_preference("work_hours")
            if work_hours and hour >= work_hours.get("end", 17):
                return "Your work day is ending. Should I close all work apps?"
        
        return None
    
    def check_usage_patterns(self):
        """Suggest based on learned patterns"""
        now = datetime.datetime.now()
        
        # Check if user usually opens certain apps at this time
        patterns = self.memory.long_term["patterns"]["frequent_apps"]
        if patterns:
            most_used = max(patterns.items(), key=lambda x: x[1])
            if most_used[1] > 5:  # Used more than 5 times
                return f"You usually open {most_used[0]} around this time. Should I open it?"
        
        return None
    
    def _can_suggest(self):
        """Check if enough time has passed since last suggestion"""
        if not self.last_suggestion_time:
            self.last_suggestion_time = datetime.datetime.now()
            return True
        
        elapsed = (datetime.datetime.now() - self.last_suggestion_time).seconds
        if elapsed > self.suggestion_cooldown:
            self.last_suggestion_time = datetime.datetime.now()
            return True
        
        return False
    
    def get_suggestion(self):
        """Get proactive suggestion if available"""
        # Check battery
        suggestion = self.check_battery()
        if suggestion:
            return suggestion
        
        # Check time-based
        suggestion = self.check_time_based_suggestions()
        if suggestion:
            return suggestion
        
        # Check patterns
        suggestion = self.check_usage_patterns()
        if suggestion:
            return suggestion
        
        return None

# ============================================
# INITIALIZE REX BRAIN
# ============================================

# Global instances
rex_memory = ContextMemory()
rex_conversation = ConversationManager(rex_memory)
rex_routines = RoutineManager()
rex_proactive = ProactiveAssistant(rex_memory)

def get_rex_brain():
    """Get REX brain components"""
    return {
        "memory": rex_memory,
        "conversation": rex_conversation,
        "routines": rex_routines,
        "proactive": rex_proactive
    }