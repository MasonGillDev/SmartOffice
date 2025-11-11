"""
Model Caller Module
Handles communication with OpenAI API
"""

import os
from typing import Dict, Optional, List
from openai import OpenAI
import json

class ModelCaller:
    """Call OpenAI models with prepared prompts"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        """
        Initialize the ModelCaller
        
        Args:
            api_key: OpenAI API key (if not provided, will look for OPENAI_API_KEY env var)
            model: Model name to use (default: gpt-3.5-turbo)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        
        if not self.api_key:
            print("⚠️  Warning: No OpenAI API key found. Set OPENAI_API_KEY environment variable.")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)
            print(f"✅ ModelCaller initialized with model: {self.model}")
    
    def call_model(self, prompt_data: Dict) -> Dict:
        """
        Call OpenAI model with the prepared prompt
        
        Args:
            prompt_data: Dictionary containing the prompt (from PromptBuilder)
        
        Returns:
            Dictionary with model response and metadata
        """
        
        if not self.client:
            error_msg = "OpenAI client not initialized. Please provide API key."
            print(f"❌ {error_msg}")
            return {
                "error": error_msg,
                "success": False
            }
        
        try:
            print(f"🤖 Calling {self.model}...")
            
            # Extract messages from prompt data
            messages = prompt_data.get("messages", [])
            
            if not messages:
                # Fallback to simple format if messages not found
                user_input = prompt_data.get("user_input", "")
                messages = [{"role": "user", "content": user_input}]
            
            # Make API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            # Extract response
            assistant_message = response.choices[0].message.content
            
            # Build response object
            result = {
                "success": True,
                "response": assistant_message,
                "model": self.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "metadata": {
                    "model_id": response.id,
                    "created": response.created,
                    "finish_reason": response.choices[0].finish_reason
                }
            }
            
            print(f"✅ Model response received ({result['usage']['total_tokens']} tokens used)")
            return result
            
        except Exception as e:
            error_msg = f"Error calling model: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "error": error_msg,
                "success": False
            }
    
    def call_model_simple(self, user_message: str) -> str:
        """
        Simple interface for calling the model with just a text message
        
        Args:
            user_message: User's text input
            
        Returns:
            Model's text response or error message
        """
        prompt_data = {
            "messages": [
                {"role": "user", "content": user_message}
            ]
        }
        
        result = self.call_model(prompt_data)
        
        if result["success"]:
            return result["response"]
        else:
            return f"Error: {result.get('error', 'Unknown error')}"
    
    def set_model(self, model_name: str):
        """Change the model being used"""
        self.model = model_name
        print(f"✅ Model changed to: {model_name}")
    
    def get_available_models(self) -> List[str]:
        """Return list of commonly used OpenAI models"""
        return [
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "gpt-4",
            "gpt-4-turbo-preview",
            "gpt-4-32k"
        ]