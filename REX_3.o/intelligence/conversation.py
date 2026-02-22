# ============================================
# FILE: intelligence/conversation.py
# REX 3.0 - Multi-turn Conversation Manager
# ============================================

from typing import Tuple, Dict, Any, Optional, Callable
from enum import Enum


class ConversationState(Enum):
    """Conversation states"""
    IDLE = "IDLE"
    AWAITING_APP_CHOICE = "AWAITING_APP_CHOICE"
    AWAITING_FILE_CHOICE = "AWAITING_FILE_CHOICE"
    AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"
    AWAITING_PARAMETER = "AWAITING_PARAMETER"
    AWAITING_DATE = "AWAITING_DATE"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"


class ConversationManager:
    """Manages multi-turn conversations and pending actions"""
    
    def __init__(self, memory):
        """
        Initialize conversation manager
        
        Args:
            memory: ContextMemory instance for state persistence
        """
        self.memory = memory
        self.current_state = ConversationState.IDLE
        self.state_data = {}
        self.conversation_stack = []
    
    def set_state(self, state: ConversationState, data: Optional[Dict] = None):
        """
        Change conversation state
        
        Args:
            state: New conversation state
            data: State-specific data
        """
        # Save previous state on stack
        if self.current_state != ConversationState.IDLE:
            self.conversation_stack.append({
                "state": self.current_state,
                "data": self.state_data
            })
        
        self.current_state = state
        self.state_data = data or {}
        
        # Update memory
        self.memory.short_term["pending_action"] = state.value
    
    def handle_input(self, command: str) -> Tuple[str, Any]:
        """
        Process input based on current state
        
        Args:
            command: User input
            
        Returns:
            Tuple of (action, data)
            Actions: WAIT, CANCEL, PROCESS_COMMAND, OPEN_APP, OPEN_FILE, etc.
        """
        # Route to appropriate handler
        if self.current_state == ConversationState.IDLE:
            return self._handle_idle(command)
        elif self.current_state == ConversationState.AWAITING_APP_CHOICE:
            return self._handle_app_choice(command)
        elif self.current_state == ConversationState.AWAITING_FILE_CHOICE:
            return self._handle_file_choice(command)
        elif self.current_state == ConversationState.AWAITING_CLARIFICATION:
            return self._handle_clarification(command)
        elif self.current_state == ConversationState.AWAITING_PARAMETER:
            return self._handle_parameter(command)
        elif self.current_state == ConversationState.AWAITING_DATE:
            return self._handle_date(command)
        elif self.current_state == ConversationState.AWAITING_CONFIRMATION:
            return self._handle_confirmation(command)
        
        return ("PROCESS_COMMAND", command)
    
    def _handle_idle(self, command: str) -> Tuple[str, str]:
        """Normal command processing"""
        return ("PROCESS_COMMAND", command)
    
    def _handle_app_choice(self, command: str) -> Tuple[str, Optional[str]]:
        """
        Handle app selection from multiple choices
        
        Expected state_data:
            - choices: List of app names/paths
            - prompt: Original prompt
        """
        choices = self.state_data.get("choices", [])
        
        if not choices:
            self.reset_state()
            return ("CANCEL", None)
        
        # Check for cancel
        if any(word in command.lower() for word in ["cancel", "nevermind", "no"]):
            self.reset_state()
            return ("CANCEL", None)
        
        # Try to match user input to choices
        command_lower = command.lower()
        
        # Check for number selection
        for i, choice in enumerate(choices, 1):
            if str(i) in command or f"number {i}" in command_lower:
                self.reset_state()
                return ("OPEN_APP", choice)
        
        # Check for name match
        for choice in choices:
            if choice.lower() in command_lower:
                self.reset_state()
                return ("OPEN_APP", choice)
        
        # Didn't understand
        return ("WAIT", None)
    
    def _handle_file_choice(self, command: str) -> Tuple[str, Optional[str]]:
        """
        Handle file selection from multiple choices
        
        Expected state_data:
            - choices: List of file paths
            - prompt: Original prompt
        """
        choices = self.state_data.get("choices", [])
        
        if not choices:
            self.reset_state()
            return ("CANCEL", None)
        
        # Check for cancel
        if any(word in command.lower() for word in ["cancel", "nevermind", "no"]):
            self.reset_state()
            return ("CANCEL", None)
        
        # Try to match number
        for i, choice in enumerate(choices, 1):
            if str(i) in command:
                self.reset_state()
                return ("OPEN_FILE", choice)
        
        return ("WAIT", None)
    
    def _handle_clarification(self, command: str) -> Tuple[str, Any]:
        """
        Handle yes/no clarification
        
        Expected state_data:
            - action: Action to perform if yes
            - target: Target of action
            - question: Question asked
        """
        command_lower = command.lower()
        
        # Check for yes
        if any(word in command_lower for word in ["yes", "yeah", "sure", "correct", "ok"]):
            action = self.state_data.get("action")
            target = self.state_data.get("target")
            self.reset_state()
            return (action, target)
        
        # Check for no
        if any(word in command_lower for word in ["no", "nope", "cancel"]):
            self.reset_state()
            return ("CANCEL", None)
        
        # Didn't understand - ask again
        return ("WAIT", None)
    
    def _handle_parameter(self, command: str) -> Tuple[str, Any]:
        """
        Handle parameter collection
        
        Expected state_data:
            - param_type: Current parameter being collected
            - required_params: List of all required parameters
            - parameters: Dict of collected parameters
            - action: Final action to perform
        """
        param_type = self.state_data.get("param_type")
        
        # Store the parameter
        if "parameters" not in self.state_data:
            self.state_data["parameters"] = {}
        
        self.state_data["parameters"][param_type] = command
        
        # Check if we have all required parameters
        required = self.state_data.get("required_params", [])
        collected = list(self.state_data["parameters"].keys())
        
        missing = [p for p in required if p not in collected]
        
        if not missing:
            # All parameters collected
            action = self.state_data.get("action")
            parameters = self.state_data["parameters"]
            self.reset_state()
            return (action, parameters)
        else:
            # Ask for next parameter
            next_param = missing[0]
            self.state_data["param_type"] = next_param
            return ("WAIT", f"What is the {next_param}?")
    
    def _handle_date(self, command: str) -> Tuple[str, str]:
        """
        Handle date input
        
        Expected state_data:
            - action: Action to perform with date
            - context: Additional context
        """
        from datetime import datetime, timedelta
        
        command_lower = command.lower()
        
        # Parse common date references
        if "today" in command_lower:
            date_str = datetime.now().strftime("%Y-%m-%d")
        elif "yesterday" in command_lower:
            date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        elif "tomorrow" in command_lower:
            date_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            # Try to parse as date
            date_str = command.replace(" ", "-")
        
        action = self.state_data.get("action", "PROCESS_DATE")
        self.reset_state()
        return (action, date_str)
    
    def _handle_confirmation(self, command: str) -> Tuple[str, bool]:
        """
        Handle confirmation requests
        
        Expected state_data:
            - action: Action to confirm
            - details: Details of action
        """
        command_lower = command.lower()
        
        # Check for yes
        if any(word in command_lower for word in ["yes", "yeah", "confirm", "sure", "ok"]):
            action = self.state_data.get("action")
            details = self.state_data.get("details")
            self.reset_state()
            return (action, details)
        
        # Check for no
        self.reset_state()
        return ("CANCEL", None)
    
    def reset_state(self):
        """Reset to idle state"""
        self.current_state = ConversationState.IDLE
        self.state_data = {}
        self.memory.short_term["pending_action"] = None
    
    def go_back(self) -> bool:
        """
        Go back to previous conversation state
        
        Returns:
            True if successful, False if no previous state
        """
        if not self.conversation_stack:
            return False
        
        previous = self.conversation_stack.pop()
        self.current_state = previous["state"]
        self.state_data = previous["data"]
        
        return True
    
    def is_active(self) -> bool:
        """Check if conversation is in progress"""
        return self.current_state != ConversationState.IDLE
    
    def get_prompt(self) -> Optional[str]:
        """Get current prompt for user"""
        return self.state_data.get("prompt")
    
    def set_app_selection(self, choices: list, prompt: str):
        """
        Set up app selection state
        
        Args:
            choices: List of app choices
            prompt: Prompt to show user
        """
        self.set_state(ConversationState.AWAITING_APP_CHOICE, {
            "choices": choices,
            "prompt": prompt
        })
    
    def set_file_selection(self, choices: list, prompt: str):
        """
        Set up file selection state
        
        Args:
            choices: List of file choices
            prompt: Prompt to show user
        """
        self.set_state(ConversationState.AWAITING_FILE_CHOICE, {
            "choices": choices,
            "prompt": prompt
        })
    
    def set_clarification(self, question: str, action: str, target: Any):
        """
        Set up clarification state
        
        Args:
            question: Question to ask
            action: Action to perform if confirmed
            target: Target of action
        """
        self.set_state(ConversationState.AWAITING_CLARIFICATION, {
            "question": question,
            "action": action,
            "target": target
        })
    
    def set_parameter_collection(self, required_params: list, action: str):
        """
        Set up parameter collection state
        
        Args:
            required_params: List of parameter names to collect
            action: Action to perform when all collected
        """
        self.set_state(ConversationState.AWAITING_PARAMETER, {
            "required_params": required_params,
            "param_type": required_params[0] if required_params else None,
            "action": action,
            "parameters": {}
        })
    
    def set_date_input(self, action: str, context: Optional[Dict] = None):
        """
        Set up date input state
        
        Args:
            action: Action to perform with date
            context: Additional context
        """
        self.set_state(ConversationState.AWAITING_DATE, {
            "action": action,
            "context": context or {}
        })
    
    def set_confirmation(self, action: str, details: Any, question: str):
        """
        Set up confirmation state
        
        Args:
            action: Action to confirm
            details: Details of action
            question: Question to ask
        """
        self.set_state(ConversationState.AWAITING_CONFIRMATION, {
            "action": action,
            "details": details,
            "question": question
        })