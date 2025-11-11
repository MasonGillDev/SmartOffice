"""
Prompt Builder Module
Constructs prompts for AI assistant interactions
"""

from typing import Dict, List, Optional
from datetime import datetime

class PromptBuilder:
    """Build prompts for AI assistant"""
    
    def __init__(self):
        self.system_prompt = """You are a helpful AI assistant. You provide clear, accurate, and helpful responses to user queries. 
Be concise but thorough in your answers."""
    
    def build_prompt(self, user_message: str, context: Optional[Dict] = None) -> Dict:
        """
        Build a complete prompt for the AI model
        
        Args:
            user_message: The user's input/query
            context: Optional context information (previous messages, metadata, etc.)
        
        Returns:
            Dict containing the formatted prompt for the model
        """
        
        # Build message list for chat format
        messages = []
        
        # Add system prompt
        messages.append({
            "role": "system",
            "content": self.system_prompt
        })
        
        # Add context if provided (e.g., conversation history)
        if context and "history" in context:
            messages.extend(context["history"])
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Build complete prompt object
        prompt = {
            "messages": messages,
            "timestamp": datetime.now().isoformat(),
            "user_input": user_message,
            "metadata": {
                "prompt_version": "1.0",
                "builder": "PromptBuilder",
                "context_included": bool(context)
            }
        }
        
        # Log the prompt construction
        print(f"📝 Built prompt for: '{user_message[:50]}{'...' if len(user_message) > 50 else ''}'")
        
        return prompt
    
    def build_simple_prompt(self, user_message: str) -> str:
        """
        Build a simple text prompt (for models that don't use chat format)
        
        Args:
            user_message: The user's input
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""Assistant Instructions: {self.system_prompt}

User Query: {user_message}

Assistant Response:"""
        
        return prompt
    
    def set_system_prompt(self, system_prompt: str):
        """Update the system prompt"""
        self.system_prompt = system_prompt
        print(f"✅ System prompt updated")