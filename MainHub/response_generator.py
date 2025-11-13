"""
Response Generator
Handles AI response generation through the model
"""

import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ResponseGenerator:
    """Generates AI responses using the configured model"""
    
    def __init__(self, model_caller, prompt_builder):
        """
        Initialize the response generator
        
        Args:
            model_caller: ModelCaller instance
            prompt_builder: PromptBuilder instance
        """
        self.model_caller = model_caller
        self.prompt_builder = prompt_builder
        
        logger.info("ResponseGenerator initialized")
    
    def generate(self, user_prompt: str, context: Optional[Dict] = None) -> str:
        """
        Generate an AI response for the user prompt
        
        Args:
            user_prompt: The user's input text
            context: Optional conversation context
            
        Returns:
            The AI's response text
        """
        logger.debug(f"Generating response for: {user_prompt[:50]}...")
        
        # Build prompt with context
        messages = []
        
        # Add conversation history if available
        if context and context.get('history'):
            messages = context['history'].copy()
        
        # Build the complete prompt
        built_prompt = self.prompt_builder.build_conversation_prompt(
            user_prompt, 
            messages
        )
        
        # Call the model
        model_response = self.model_caller.call_model(built_prompt)
        
        if model_response.get("success"):
            response = model_response.get("response", "I couldn't generate a response.")
            logger.info(f"Generated response ({model_response.get('usage', {}).get('total_tokens', 0)} tokens)")
            return response
        else:
            error = model_response.get("error", "Unknown error")
            logger.error(f"Failed to generate response: {error}")
            raise Exception(f"Model error: {error}")
    
    def get_status(self) -> Dict:
        """Get current status"""
        return {
            "active": True,
            "model": self.model_caller.model if self.model_caller else "unknown"
        }