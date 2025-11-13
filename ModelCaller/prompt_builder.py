"""
Prompt Builder Module
Constructs prompts for AI assistant interactions
"""

from typing import Dict, List, Optional
from datetime import datetime

class PromptBuilder:
    """Build prompts for AI assistant"""
    
    def __init__(self, tool_manager=None):
        self.tool_manager = tool_manager
        self.system_prompt = """You are a helpful AI assistant. You provide clear, accurate, and helpful responses to user queries. 
Be concise but thorough in your answers."""
        
        # Base conversation prompt
        self.base_conversation_prompt = """You are a voice AI assistant. Your responses will be READ ALOUD.

🎯 CRITICAL VOICE RESPONSE RULES:
1. EXTREMELY CONCISE - Maximum 1-2 sentences for answers
2. NO LISTS - Just give the most important info
3. NO FORMATTING - No bullets, asterisks, or special characters
4. BARE MINIMUM - Only essential information
5. NATURAL SPEECH - Use spoken language, not written

EXAMPLES:
❌ BAD: "The current temperature in New York is 72 degrees Fahrenheit with partly cloudy skies, humidity at 65%, and winds from the northwest at 10 mph."
✅ GOOD: "It's 72 degrees and partly cloudy in New York."

❌ BAD: "I've successfully saved your note about the meeting at 3pm to the system."
✅ GOOD: "Note saved."

❌ BAD: "Here are the processes running on port 3000: node process with PID 1234..."  
✅ GOOD: "Port 3000 has a node process, PID 1234."

If user says "more", "details", "expand", "tell me more" → THEN provide full information.
Otherwise → MINIMUM words possible!

"""
        
        # This will be built dynamically with tools
        self._update_conversation_prompt()
    
    def _update_conversation_prompt(self):
        """Update conversation prompt with available tools"""
        # Add today's date to the prompt
        today = datetime.now().strftime("%A, %B %d, %Y")
        date_context = f"Today's date is: {today}\n\n"
        
        self.conversation_system_prompt = date_context + self.base_conversation_prompt
        
        # Add tools if tool_manager is available
        if self.tool_manager:
            self.conversation_system_prompt += self.tool_manager.get_tools_for_prompt()
            self.conversation_system_prompt += "\n\nREMEMBER: Always use tools for system queries, even in conversation context.\n\n"
        
        # Add conversation ending instructions
        self.conversation_system_prompt += """IMPORTANT: When the user indicates they want to end the conversation (saying things like "goodbye", "that's all", "thank you that's it", "I'm done", "goodnight", or similar), 
you MUST respond with "end_conversation_mode" as the VERY LAST LINE of your response. First give a polite farewell, then add "end_conversation_mode" on a new line.

Example:
User: "That will be all, thank you"
Assistant: "You're welcome! Have a great day!
end_conversation_mode"
"""
    
    def set_tool_manager(self, tool_manager):
        """Set or update the tool manager"""
        self.tool_manager = tool_manager
        self._update_conversation_prompt()
    
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
    
    def build_conversation_prompt(self, user_message: str, conversation_history: Optional[List[Dict]] = None) -> Dict:
        """
        Build a prompt for conversation mode with history
        
        Args:
            user_message: Current user input
            conversation_history: List of previous messages in the conversation
            
        Returns:
            Dict containing the formatted prompt for the model
        """
        
        # Build message list for chat format
        messages = []
        
        # Use conversation-specific system prompt
        messages.append({
            "role": "system",
            "content": self.conversation_system_prompt
        })
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
        
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
                "mode": "conversation",
                "history_length": len(conversation_history) if conversation_history else 0
            }
        }
        
        print(f"💬 Built conversation prompt with {len(messages)-2} history messages")
        
        return prompt
    
    def set_system_prompt(self, system_prompt: str):
        """Update the system prompt"""
        self.system_prompt = system_prompt
        print(f"✅ System prompt updated")