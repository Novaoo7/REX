# ============================================
# FILE: intelligence/proactive.py
# REX 3.0 - Proactive Assistant
# ============================================

from typing import Optional
from datetime import datetime
import time


class ProactiveAssistant:
    """Provides proactive suggestions and monitoring"""
    
    def __init__(self, memory):
        self.memory = memory
        self.last_suggestion_time = None
        self.suggestion_cooldown = 300  # 5 minutes
    
    def get_suggestion(self) -> Optional[str]:
        """Get proactive suggestion if available"""
        # Check cooldown
        if not self._can_suggest():
            return None
        
        # Check time-based suggestions
        suggestion = self._check_time_based()
        if suggestion:
            return suggestion
        
        # Check pattern-based suggestions
        suggestion = self._check_patterns()
        if suggestion:
            return suggestion
        
        return None
    
    def _can_suggest(self) -> bool:
        """Check if enough time passed since last suggestion"""
        if not self.last_suggestion_time:
            self.last_suggestion_time = time.time()
            return True
        
        elapsed = time.time() - self.last_suggestion_time
        if elapsed > self.suggestion_cooldown:
            self.last_suggestion_time = time.time()
            return True
        
        return False
    
    def _check_time_based(self) -> Optional[str]:
        """Check for time-based suggestions"""
        now = datetime.now()
        hour = now.hour
        
        # Morning routine
        if hour == 9:
            return "Good morning! Would you like to start your morning routine?"
        
        # Lunch break
        if hour == 12:
            return "It's lunch time. Should I lock your computer?"
        
        # End of workday
        if hour == 17:
            work_hours = self.memory.get_preference("work_hours", {})
            end_hour = work_hours.get("end", 17)
            if hour >= end_hour:
                return "Your work day is ending. Should I close all work apps?"
        
        # Evening
        if hour == 22:
            return "It's getting late. Would you like to enable sleep mode?"
        
        return None
    
    def _check_patterns(self) -> Optional[str]:
        """Check usage patterns for suggestions"""
        frequent_apps = self.memory.get_frequent_items("app", top_n=3)
        
        if frequent_apps and frequent_apps[0][1] > 5:
            app_name = frequent_apps[0][0]
            return f"You frequently use {app_name}. Should I open it?"
        
        return None
