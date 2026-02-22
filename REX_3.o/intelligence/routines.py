# ============================================
# FILE: intelligence/routines.py
# REX 3.0 - Routine Automation Manager
# ============================================

import json
from pathlib import Path
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime


class RoutineManager:
    """Manages automated routines and workflows"""
    
    def __init__(self, routines_file: Path = Path("memory/routines.json")):
        """
        Initialize routine manager
        
        Args:
            routines_file: Path to routines configuration file
        """
        self.routines_file = routines_file
        self.routines = self._load_routines()
    
    def _load_routines(self) -> Dict:
        """Load saved routines"""
        if self.routines_file.exists():
            try:
                with open(self.routines_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load routines: {e}")
        
        return self._init_default_routines()
    
    def _init_default_routines(self) -> Dict:
        """Create default routines"""
        return {
            "morning": {
                "name": "Morning Routine",
                "description": "Start your productive day",
                "enabled": True,
                "actions": [
                    {
                        "type": "speak",
                        "text": "Good morning! Starting your day.",
                        "priority": 1
                    },
                    {
                        "type": "open_app",
                        "target": "chrome",
                        "priority": 2
                    },
                    {
                        "type": "open_app",
                        "target": "notepad",
                        "priority": 3
                    },
                    {
                        "type": "speak",
                        "text": "Morning routine complete. Have a great day!",
                        "priority": 4
                    }
                ],
                "schedule": {
                    "time": "09:00",
                    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
                }
            },
            
            "work": {
                "name": "Work Mode",
                "description": "Set up work environment",
                "enabled": True,
                "actions": [
                    {
                        "type": "speak",
                        "text": "Activating work mode",
                        "priority": 1
                    },
                    {
                        "type": "open_app",
                        "target": "vscode",
                        "priority": 2
                    },
                    {
                        "type": "open_app",
                        "target": "chrome",
                        "priority": 3
                    },
                    {
                        "type": "speak",
                        "text": "Work mode ready. Let's be productive!",
                        "priority": 4
                    }
                ]
            },
            
            "sleep": {
                "name": "Sleep Mode",
                "description": "Wind down for the night",
                "enabled": True,
                "actions": [
                    {
                        "type": "speak",
                        "text": "Preparing sleep mode",
                        "priority": 1
                    },
                    {
                        "type": "close_all_apps",
                        "priority": 2
                    },
                    {
                        "type": "speak",
                        "text": "Good night. Sleep well!",
                        "priority": 3
                    }
                ],
                "schedule": {
                    "time": "22:00",
                    "days": ["all"]
                }
            },
            
            "focus": {
                "name": "Focus Mode",
                "description": "Deep work session",
                "enabled": True,
                "actions": [
                    {
                        "type": "speak",
                        "text": "Entering focus mode. Minimizing distractions.",
                        "priority": 1
                    },
                    {
                        "type": "close_app",
                        "target": "chrome",
                        "priority": 2
                    },
                    {
                        "type": "open_app",
                        "target": "notepad",
                        "priority": 3
                    }
                ]
            },
            
            "break": {
                "name": "Break Time",
                "description": "Take a short break",
                "enabled": True,
                "actions": [
                    {
                        "type": "speak",
                        "text": "Time for a break. Stand up and stretch!",
                        "priority": 1
                    },
                    {
                        "type": "wait",
                        "seconds": 2,
                        "priority": 2
                    },
                    {
                        "type": "speak",
                        "text": "Remember to hydrate and rest your eyes.",
                        "priority": 3
                    }
                ]
            }
        }
    
    def save_routines(self):
        """Save routines to disk"""
        try:
            self.routines_file.parent.mkdir(exist_ok=True)
            
            with open(self.routines_file, 'w') as f:
                json.dump(self.routines, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save routines: {e}")
    
    def add_routine(self, name: str, actions: List[Dict], 
                   description: str = "", schedule: Optional[Dict] = None):
        """
        Add new routine
        
        Args:
            name: Routine name (lowercase, used as key)
            actions: List of action dictionaries
            description: Routine description
            schedule: Optional schedule configuration
        """
        self.routines[name.lower()] = {
            "name": name.title(),
            "description": description,
            "enabled": True,
            "actions": actions,
            "schedule": schedule or {},
            "created_at": datetime.now().isoformat()
        }
        self.save_routines()
    
    def get_routine(self, name: str) -> Optional[Dict]:
        """
        Get routine by name
        
        Args:
            name: Routine name
            
        Returns:
            Routine dictionary or None
        """
        return self.routines.get(name.lower())
    
    def list_routines(self) -> List[str]:
        """
        List all available routines
        
        Returns:
            List of routine descriptions
        """
        return [
            f"{r['name']}: {r['description']}"
            for r in self.routines.values()
            if r.get("enabled", True)
        ]
    
    def execute_routine(self, name: str, executor_func: Callable) -> bool:
        """
        Execute a routine
        
        Args:
            name: Routine name
            executor_func: Function to execute actions
                          Signature: func(action_type, target) -> bool
            
        Returns:
            True if successful, False otherwise
        """
        routine = self.get_routine(name)
        
        if not routine:
            print(f"Routine '{name}' not found")
            return False
        
        if not routine.get("enabled", True):
            print(f"Routine '{name}' is disabled")
            return False
        
        print(f"Executing routine: {routine['name']}")
        
        # Sort actions by priority
        actions = sorted(routine["actions"], key=lambda x: x.get("priority", 999))
        
        success_count = 0
        total_count = len(actions)
        
        for action in actions:
            action_type = action["type"]
            
            try:
                if action_type == "speak":
                    executor_func("speak", action["text"])
                    success_count += 1
                
                elif action_type == "open_app":
                    result = executor_func("open_app", action["target"])
                    if result:
                        success_count += 1
                
                elif action_type == "close_app":
                    result = executor_func("close_app", action["target"])
                    if result:
                        success_count += 1
                
                elif action_type == "close_all_apps":
                    executor_func("close_all_apps", None)
                    success_count += 1
                
                elif action_type == "wait":
                    import time
                    time.sleep(action.get("seconds", 1))
                    success_count += 1
                
                elif action_type == "custom":
                    # Allow custom actions
                    executor_func(action.get("custom_type"), action.get("data"))
                    success_count += 1
                
                else:
                    print(f"Unknown action type: {action_type}")
            
            except Exception as e:
                print(f"Error executing action {action_type}: {e}")
        
        print(f"Routine complete: {success_count}/{total_count} actions successful")
        return success_count > 0
    
    def enable_routine(self, name: str):
        """Enable a routine"""
        routine = self.get_routine(name)
        if routine:
            routine["enabled"] = True
            self.save_routines()
    
    def disable_routine(self, name: str):
        """Disable a routine"""
        routine = self.get_routine(name)
        if routine:
            routine["enabled"] = False
            self.save_routines()
    
    def delete_routine(self, name: str) -> bool:
        """
        Delete a routine
        
        Args:
            name: Routine name
            
        Returns:
            True if deleted, False if not found
        """
        if name.lower() in self.routines:
            del self.routines[name.lower()]
            self.save_routines()
            return True
        return False
    
    def get_scheduled_routines(self, current_time: str, current_day: str) -> List[str]:
        """
        Get routines scheduled for current time/day
        
        Args:
            current_time: Time in HH:MM format
            current_day: Day name (lowercase)
            
        Returns:
            List of routine names
        """
        scheduled = []
        
        for name, routine in self.routines.items():
            if not routine.get("enabled", True):
                continue
            
            schedule = routine.get("schedule", {})
            if not schedule:
                continue
            
            # Check time
            scheduled_time = schedule.get("time")
            if scheduled_time and scheduled_time == current_time:
                # Check day
                days = schedule.get("days", [])
                if "all" in days or current_day in days:
                    scheduled.append(name)
        
        return scheduled
    
    def modify_routine(self, name: str, **kwargs):
        """
        Modify routine properties
        
        Args:
            name: Routine name
            **kwargs: Properties to modify
        """
        routine = self.get_routine(name)
        if not routine:
            print(f"Routine '{name}' not found")
            return
        
        for key, value in kwargs.items():
            if key in routine:
                routine[key] = value
        
        self.save_routines()
    
    def add_action_to_routine(self, routine_name: str, action: Dict):
        """
        Add action to existing routine
        
        Args:
            routine_name: Name of routine
            action: Action dictionary to add
        """
        routine = self.get_routine(routine_name)
        if not routine:
            print(f"Routine '{routine_name}' not found")
            return
        
        routine["actions"].append(action)
        self.save_routines()
    
    def remove_action_from_routine(self, routine_name: str, action_index: int):
        """
        Remove action from routine
        
        Args:
            routine_name: Name of routine
            action_index: Index of action to remove
        """
        routine = self.get_routine(routine_name)
        if not routine:
            print(f"Routine '{routine_name}' not found")
            return
        
        if 0 <= action_index < len(routine["actions"]):
            routine["actions"].pop(action_index)
            self.save_routines()
    
    def get_routine_stats(self) -> Dict[str, Any]:
        """Get routine statistics"""
        return {
            "total_routines": len(self.routines),
            "enabled_routines": sum(1 for r in self.routines.values() if r.get("enabled", True)),
            "scheduled_routines": sum(1 for r in self.routines.values() if r.get("schedule")),
            "total_actions": sum(len(r["actions"]) for r in self.routines.values())
        }