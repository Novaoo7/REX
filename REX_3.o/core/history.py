# ============================================
# FILE: core/history.py
# REX 3.0 - Command History & Undo System
# ============================================

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class CommandRecord:
    """Single command execution record"""
    command: str
    action_type: str
    result: Dict[str, Any]
    timestamp: float
    undoable: bool = False
    undo_action: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def get_timestamp_str(self) -> str:
        """Get formatted timestamp"""
        dt = datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


class CommandHistory:
    """Track command history with undo support"""
    
    def __init__(self, max_size: int = 50, history_file: Path = Path("memory/command_history.json")):
        """
        Initialize command history
        
        Args:
            max_size: Maximum number of commands to keep
            history_file: File to persist history
        """
        self.max_size = max_size
        self.history_file = history_file
        self.history: List[CommandRecord] = []
        self._load_history()
    
    def _load_history(self):
        """Load history from file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    
                for item in data:
                    self.history.append(CommandRecord(
                        command=item["command"],
                        action_type=item["action_type"],
                        result=item["result"],
                        timestamp=item["timestamp"],
                        undoable=item.get("undoable", False),
                        undo_action=item.get("undo_action")
                    ))
            except Exception as e:
                print(f"Warning: Failed to load history: {e}")
    
    def _save_history(self):
        """Save history to file"""
        try:
            self.history_file.parent.mkdir(exist_ok=True)
            
            data = [record.to_dict() for record in self.history]
            
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save history: {e}")
    
    def add(self, record: CommandRecord):
        """
        Add command to history
        
        Args:
            record: CommandRecord to add
        """
        self.history.append(record)
        
        # Maintain max size
        if len(self.history) > self.max_size:
            self.history.pop(0)
        
        self._save_history()
    
    def get_last(self, n: int = 1) -> List[CommandRecord]:
        """
        Get last n commands
        
        Args:
            n: Number of commands to retrieve
            
        Returns:
            List of CommandRecord objects
        """
        if n <= 0:
            return []
        
        return self.history[-n:] if n <= len(self.history) else self.history.copy()
    
    def get_all(self) -> List[CommandRecord]:
        """Get all commands in history"""
        return self.history.copy()
    
    def can_undo(self) -> bool:
        """Check if last command is undoable"""
        return len(self.history) > 0 and self.history[-1].undoable
    
    def undo_last(self) -> Optional[CommandRecord]:
        """
        Get last undoable command and remove from history
        
        Returns:
            CommandRecord if undoable, None otherwise
        """
        if self.can_undo():
            record = self.history.pop()
            self._save_history()
            return record
        return None
    
    def search(self, query: str) -> List[CommandRecord]:
        """
        Search command history
        
        Args:
            query: Search query
            
        Returns:
            List of matching CommandRecord objects
        """
        query_lower = query.lower()
        return [
            record for record in self.history
            if query_lower in record.command.lower()
        ]
    
    def filter_by_action(self, action_type: str) -> List[CommandRecord]:
        """
        Filter history by action type
        
        Args:
            action_type: Action type to filter by
            
        Returns:
            List of matching CommandRecord objects
        """
        return [
            record for record in self.history
            if record.action_type == action_type
        ]
    
    def filter_by_time(self, start_time: float, end_time: float) -> List[CommandRecord]:
        """
        Filter history by time range
        
        Args:
            start_time: Start timestamp
            end_time: End timestamp
            
        Returns:
            List of CommandRecord objects within time range
        """
        return [
            record for record in self.history
            if start_time <= record.timestamp <= end_time
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get history statistics
        
        Returns:
            Dictionary with statistics
        """
        if not self.history:
            return {
                "total_commands": 0,
                "undoable_commands": 0,
                "action_types": {},
                "oldest_command": None,
                "newest_command": None
            }
        
        action_types = {}
        undoable_count = 0
        
        for record in self.history:
            # Count action types
            action_types[record.action_type] = action_types.get(record.action_type, 0) + 1
            
            # Count undoable
            if record.undoable:
                undoable_count += 1
        
        return {
            "total_commands": len(self.history),
            "undoable_commands": undoable_count,
            "action_types": action_types,
            "oldest_command": self.history[0].get_timestamp_str(),
            "newest_command": self.history[-1].get_timestamp_str()
        }
    
    def clear(self):
        """Clear all history"""
        self.history = []
        self._save_history()
    
    def export_to_file(self, filepath: Path):
        """
        Export history to JSON file
        
        Args:
            filepath: Path to export file
        """
        try:
            data = [record.to_dict() for record in self.history]
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✓ History exported to {filepath}")
        except Exception as e:
            print(f"✗ Export failed: {e}")
    
    def import_from_file(self, filepath: Path):
        """
        Import history from JSON file
        
        Args:
            filepath: Path to import file
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            imported = 0
            for item in data:
                self.history.append(CommandRecord(
                    command=item["command"],
                    action_type=item["action_type"],
                    result=item["result"],
                    timestamp=item["timestamp"],
                    undoable=item.get("undoable", False),
                    undo_action=item.get("undo_action")
                ))
                imported += 1
            
            # Maintain max size
            if len(self.history) > self.max_size:
                self.history = self.history[-self.max_size:]
            
            self._save_history()
            print(f"✓ Imported {imported} commands")
        except Exception as e:
            print(f"✗ Import failed: {e}")
    
    def get_recent_summary(self, n: int = 5) -> str:
        """
        Get summary of recent commands
        
        Args:
            n: Number of recent commands
            
        Returns:
            Formatted string summary
        """
        recent = self.get_last(n)
        
        if not recent:
            return "No recent commands"
        
        lines = [f"Last {len(recent)} commands:"]
        for i, record in enumerate(reversed(recent), 1):
            lines.append(
                f"{i}. [{record.get_timestamp_str()}] "
                f"{record.action_type}: {record.command}"
            )
        
        return "\n".join(lines)