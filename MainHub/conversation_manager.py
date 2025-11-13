"""
Conversation Manager
Handles conversation state, history, and context
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ConversationManager:
    """Manages conversation state and history"""
    
    def __init__(self, max_history: int = 20):
        """
        Initialize conversation manager
        
        Args:
            max_history: Maximum number of exchanges to keep in memory
        """
        self.history: List[Dict] = []
        self.is_conversation_mode = False
        self.max_history = max_history
        self.start_time = None
        
    def start_conversation(self):
        """Start a new conversation session"""
        self.is_conversation_mode = True
        self.start_time = datetime.now()
        logger.info("Conversation mode started")
        
    def end_conversation(self):
        """End the current conversation"""
        self.is_conversation_mode = False
        self.history = []
        self.start_time = None
        logger.info("Conversation mode ended")
        
    def add_exchange(self, user_prompt: str, ai_response: str):
        """
        Add a user-AI exchange to history
        
        Args:
            user_prompt: What the user said
            ai_response: What the AI responded
        """
        if not self.is_conversation_mode:
            self.start_conversation()
        
        self.history.append({"role": "user", "content": user_prompt})
        self.history.append({"role": "assistant", "content": ai_response})
        
        # Trim history if too long
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-(self.max_history * 2):]
        
        logger.debug(f"Added exchange, history now has {len(self.history)} messages")
        
    def get_context(self) -> Dict:
        """
        Get the current conversation context
        
        Returns:
            Dictionary with conversation history and metadata
        """
        return {
            "history": self.history.copy(),
            "is_active": self.is_conversation_mode,
            "message_count": len(self.history),
            "duration": (datetime.now() - self.start_time).seconds if self.start_time else 0
        }
    
    def should_end_conversation(self, ai_response: str) -> bool:
        """
        Check if the AI wants to end the conversation
        
        Args:
            ai_response: The AI's response text
            
        Returns:
            True if conversation should end
        """
        return "end_conversation_mode" in ai_response
    
    def is_active(self) -> bool:
        """Check if conversation mode is active"""
        return self.is_conversation_mode
    
    def get_status(self) -> Dict:
        """Get current status"""
        return {
            "active": self.is_conversation_mode,
            "history_length": len(self.history),
            "duration_seconds": (datetime.now() - self.start_time).seconds if self.start_time else 0
        }