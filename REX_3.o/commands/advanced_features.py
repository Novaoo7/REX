# ============================================
# FILE: commands/advanced_features.py
# REX 3.0 - Advanced Features
# ============================================

import os
from typing import Dict


class AdvancedFeatures:
    """Advanced features like web search, email, etc."""
    
    def __init__(self):
        self.enabled = True
    
    def web_search(self, query: str) -> Dict:
        """Perform web search"""
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        os.system(f'start {search_url}')
        return {"success": True, "message": f"Searched for {query}"}
    
    def get_weather(self, location: str = "current") -> Dict:
        """Get weather information"""
        weather_url = f"https://www.google.com/search?q=weather+{location.replace(' ', '+')}"
        os.system(f'start {weather_url}')
        return {"success": True, "message": f"Weather for {location}"}
    
    def open_website(self, url: str) -> Dict:
        """Open website"""
        if not url.startswith("http"):
            url = f"https://{url}"
        os.system(f'start {url}')
        return {"success": True, "message": f"Opened {url}"}