# ============================================
# FILE: core/intent.py - FINAL FIXED VERSION
# REX 4.0 - Much Better Intent Classification
# ============================================

from typing import Tuple, Dict, List


class IntentClassifier:
    """Better intent classification - ACTUALLY RECOGNIZES COMMANDS"""
    
    def __init__(self):
        self.intents = {
            # Greetings - VERY SIMPLE
            "greeting": {
                "keywords": ["hello", "hi", "hey", "greetings", "good morning", "good evening"],
                "exact_match": True
            },
            
            # Time/Date - EXACT PHRASES
            "time_query": {
                "keywords": ["time", "what time", "tell time", "clock"],
                "exact_match": False
            },
            
            "date_query": {
                "keywords": ["date", "today", "what date", "calendar"],
                "exact_match": False
            },
            
            # Open apps - LOOSE MATCHING
            "open_app": {
                "keywords": ["open", "start", "launch", "run"],
                "exact_match": False
            },
            
            # Close apps
            "close_app": {
                "keywords": ["close", "quit", "exit", "kill"],
                "exact_match": False
            },
            
            # Logs
            "show_logs": {
                "keywords": ["show logs", "list logs", "view logs"],
                "exact_match": True
            },
            
            # Help
            "help": {
                "keywords": ["help", "commands", "what can you do"],
                "exact_match": False
            },
            
            # Shutdown
            "shutdown": {
                "keywords": ["shutdown rex", "exit", "quit rex", "close rex"],
                "exact_match": False
            }
        }
    
    def classify(self, command: str) -> Tuple[str, float]:
        """
        Classify intent - SIMPLE AND EFFECTIVE
        
        Returns: (intent_name, confidence)
        """
        command = command.lower().strip()
        
        # Empty command
        if not command:
            return "unknown", 0.0
        
        # Direct keyword matching
        best_intent = "unknown"
        best_score = 0.0
        
        for intent_name, config in self.intents.items():
            keywords = config["keywords"]
            exact = config.get("exact_match", False)
            
            for keyword in keywords:
                score = 0.0
                
                if exact:
                    # Exact match required
                    if command == keyword:
                        score = 1.0
                else:
                    # Keyword in command
                    if keyword in command:
                        # Bonus if at start
                        if command.startswith(keyword):
                            score = 0.95
                        else:
                            score = 0.85
                
                if score > best_score:
                    best_score = score
                    best_intent = intent_name
        
        # If no match, check if it's an open command with app name
        if best_intent == "unknown":
            if any(word in command for word in ["open", "start", "launch"]):
                return "open_app", 0.8
        
        return best_intent, best_score
    
    def list_all_intents(self) -> List[str]:
        """List all available intents"""
        return list(self.intents.keys())