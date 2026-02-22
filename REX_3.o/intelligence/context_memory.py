# ============================================
# FILE: intelligence/context_memory.py
# REX 3.0 - Context Memory System
# ============================================

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class ContextMemory:
    """Advanced context tracking with long-term memory"""
    
    def __init__(self, memory_file: Path = Path("memory/long_term.json")):
        """
        Initialize context memory
        
        Args:
            memory_file: Path to long-term memory file
        """
        self.memory_file = memory_file
        
        # Short-term memory (current session)
        self.short_term = {
            "last_command": None,
            "last_app": None,
            "last_file": None,
            "last_folder": None,
            "conversation_history": [],
            "pending_action": None,
            "waiting_for": None,
            "context_stack": []
        }
        
        # Long-term memory (persistent)
        self.long_term = self._load_long_term()
    
    def _load_long_term(self) -> Dict:
        """Load long-term memory from disk"""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load memory: {e}")
        
        return self._init_long_term()
    
    def _init_long_term(self) -> Dict:
        """Initialize long-term memory structure"""
        return {
            "preferences": {
                "user_name": None,
                "user_role": None,
                "default_browser": "chrome",
                "default_editor": "notepad",
                "work_hours": {"start": 9, "end": 17},
                "verbosity": "normal"
            },
            "patterns": {
                "frequent_apps": {},
                "frequent_files": {},
                "frequent_folders": {},
                "daily_routines": [],
                "command_sequences": []
            },
            "knowledge": {
                "contacts": {},
                "important_dates": {},
                "custom_facts": {},
                "locations": {},
                "notes": []
            },
            "learning": {
                "corrections": {},
                "command_aliases": {},
                "context_links": {}
            },
            "statistics": {
                "total_commands": 0,
                "session_count": 0,
                "last_session": None,
                "most_used_commands": {}
            }
        }
    
    def save_long_term(self):
        """Persist long-term memory to disk"""
        try:
            self.memory_file.parent.mkdir(exist_ok=True)
            
            # Update statistics
            self.long_term["statistics"]["last_session"] = datetime.now().isoformat()
            
            with open(self.memory_file, 'w') as f:
                json.dump(self.long_term, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save memory: {e}")
    
    def update_short_term(self, command: str, action_type: Optional[str] = None, 
                         target: Optional[str] = None):
        """
        Update short-term memory
        
        Args:
            command: The executed command
            action_type: Type of action (open_app, open_file, etc.)
            target: Target of action (app name, file name, etc.)
        """
        self.short_term["last_command"] = command
        
        # Update specific contexts
        if action_type == "open_app":
            self.short_term["last_app"] = target
            self._learn_pattern("app", target)
        elif action_type == "open_file":
            self.short_term["last_file"] = target
            self._learn_pattern("file", target)
        elif action_type == "open_folder":
            self.short_term["last_folder"] = target
            self._learn_pattern("folder", target)
        
        # Maintain conversation history
        self.short_term["conversation_history"].append({
            "command": command,
            "timestamp": datetime.now().isoformat(),
            "type": action_type,
            "target": target
        })
        
        # Keep only last 10 commands
        if len(self.short_term["conversation_history"]) > 10:
            self.short_term["conversation_history"].pop(0)
        
        # Update statistics
        self.long_term["statistics"]["total_commands"] += 1
        
        # Track most used commands
        cmd_key = action_type or "general"
        most_used = self.long_term["statistics"]["most_used_commands"]
        most_used[cmd_key] = most_used.get(cmd_key, 0) + 1
    
    def _learn_pattern(self, item_type: str, item_name: str):
        """
        Learn usage patterns
        
        Args:
            item_type: Type of item (app, file, folder)
            item_name: Name of item
        """
        key = f"frequent_{item_type}s"
        
        if item_name:
            patterns = self.long_term["patterns"][key]
            patterns[item_name] = patterns.get(item_name, 0) + 1
    
    def resolve_reference(self, text: str) -> str:
        """
        Resolve contextual references like 'it', 'that', 'last one'
        
        Args:
            text: Command text with potential references
            
        Returns:
            Resolved command text
        """
        text_lower = text.lower()
        
        # Pronoun resolution
        if any(word in text_lower for word in ["it", "that", "this"]):
            if self.short_term["last_app"]:
                text = text.replace("it", self.short_term["last_app"])
                text = text.replace("that", self.short_term["last_app"])
                text = text.replace("this", self.short_term["last_app"])
            elif self.short_term["last_file"]:
                text = text.replace("it", self.short_term["last_file"])
                text = text.replace("that", self.short_term["last_file"])
                text = text.replace("this", self.short_term["last_file"])
        
        # Previous item references
        if "last" in text_lower or "previous" in text_lower:
            if "app" in text_lower and self.short_term["last_app"]:
                return f"open {self.short_term['last_app']}"
            elif "file" in text_lower and self.short_term["last_file"]:
                return f"open {self.short_term['last_file']}"
        
        # "Again" command
        if text_lower in ["again", "do it again", "repeat"]:
            if self.short_term["last_command"]:
                return self.short_term["last_command"]
        
        return text
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """
        Get user preference
        
        Args:
            key: Preference key
            default: Default value if not found
            
        Returns:
            Preference value
        """
        return self.long_term["preferences"].get(key, default)
    
    def set_preference(self, key: str, value: Any):
        """
        Set user preference
        
        Args:
            key: Preference key
            value: Preference value
        """
        self.long_term["preferences"][key] = value
        self.save_long_term()
    
    def remember_fact(self, category: str, key: str, value: Any):
        """
        Store custom fact in knowledge base
        
        Args:
            category: Category (contacts, dates, facts, etc.)
            key: Fact key
            value: Fact value
        """
        if category not in self.long_term["knowledge"]:
            self.long_term["knowledge"][category] = {}
        
        self.long_term["knowledge"][category][key] = value
        self.save_long_term()
    
    def recall_fact(self, category: str, key: str) -> Optional[Any]:
        """
        Retrieve custom fact
        
        Args:
            category: Category
            key: Fact key
            
        Returns:
            Fact value or None
        """
        return self.long_term["knowledge"].get(category, {}).get(key)
    
    def get_frequent_items(self, item_type: str, top_n: int = 5) -> List[tuple]:
        """
        Get most frequently used items
        
        Args:
            item_type: Type (app, file, folder)
            top_n: Number of items to return
            
        Returns:
            List of (item_name, count) tuples
        """
        key = f"frequent_{item_type}s"
        items = self.long_term["patterns"].get(key, {})
        
        # Sort by count descending
        sorted_items = sorted(items.items(), key=lambda x: x[1], reverse=True)
        
        return sorted_items[:top_n]
    
    def learn_alias(self, alias: str, command: str):
        """
        Learn command alias
        
        Args:
            alias: Alias phrase
            command: Actual command
        """
        self.long_term["learning"]["command_aliases"][alias.lower()] = command
        self.save_long_term()
    
    def get_alias(self, alias: str) -> Optional[str]:
        """
        Get command from alias
        
        Args:
            alias: Alias phrase
            
        Returns:
            Actual command or None
        """
        return self.long_term["learning"]["command_aliases"].get(alias.lower())
    
    def add_context_link(self, from_context: str, to_context: str):
        """
        Link related contexts
        
        Args:
            from_context: Source context
            to_context: Related context
        """
        links = self.long_term["learning"]["context_links"]
        
        if from_context not in links:
            links[from_context] = []
        
        if to_context not in links[from_context]:
            links[from_context].append(to_context)
    
    def get_context_links(self, context: str) -> List[str]:
        """
        Get contexts linked to given context
        
        Args:
            context: Context to look up
            
        Returns:
            List of linked contexts
        """
        return self.long_term["learning"]["context_links"].get(context, [])
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            "total_commands": self.long_term["statistics"]["total_commands"],
            "session_count": self.long_term["statistics"]["session_count"],
            "last_session": self.long_term["statistics"]["last_session"],
            "conversation_length": len(self.short_term["conversation_history"]),
            "learned_aliases": len(self.long_term["learning"]["command_aliases"]),
            "known_facts": sum(len(v) if isinstance(v, dict) else 0 
                             for v in self.long_term["knowledge"].values())
        }
    
    def clear_short_term(self):
        """Clear short-term memory"""
        self.short_term = {
            "last_command": None,
            "last_app": None,
            "last_file": None,
            "last_folder": None,
            "conversation_history": [],
            "pending_action": None,
            "waiting_for": None,
            "context_stack": []
        }
    
    def reset_long_term(self):
        """Reset long-term memory to defaults"""
        self.long_term = self._init_long_term()
        self.save_long_term()