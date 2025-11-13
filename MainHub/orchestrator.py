"""
Request Orchestrator
Central coordinator for all request processing modules
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class RequestOrchestrator:
    """
    Orchestrates the flow of user requests through various processing modules.
    This is the single entry point for all user queries.
    """
    
    def __init__(self, 
                 conversation_manager=None,
                 tool_executor=None, 
                 response_generator=None,
                 tts_manager=None):
        """
        Initialize the orchestrator with processing modules
        
        Args:
            conversation_manager: Handles conversation state and history
            tool_executor: Handles tool parsing and execution
            response_generator: Generates AI responses
            tts_manager: Manages text-to-speech queue
        """
        self.conversation = conversation_manager
        self.tools = tool_executor
        self.response_gen = response_generator
        self.tts = tts_manager
        
        logger.info("RequestOrchestrator initialized")
    
    def process_request(self, user_prompt: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main entry point for processing user requests
        
        Args:
            user_prompt: The user's text input
            metadata: Optional metadata about the request
            
        Returns:
            Response dictionary with results from all modules
        """
        logger.info(f"Processing request: {user_prompt[:50]}...")
        
        request_id = datetime.now().timestamp()
        
        try:
            # Step 1: Check conversation context
            context = self.conversation.get_context() if self.conversation else {}
            
            # Step 2: Generate initial AI response
            ai_response = self.response_gen.generate(
                user_prompt=user_prompt,
                context=context
            )
            
            # Step 3: Process any tool calls
            final_response = self.tools.process_tools(
                ai_response=ai_response,
                user_prompt=user_prompt,
                context=context
            )
            
            # Step 4: Update conversation history
            if self.conversation:
                self.conversation.add_exchange(user_prompt, final_response)
            
            # Step 5: Queue for TTS
            task_id = None
            if self.tts:
                task_id = self.tts.queue_speech(final_response)
            
            # Step 6: Build response
            return {
                "status": "success",
                "request_id": request_id,
                "user_prompt": user_prompt,
                "ai_response": final_response,
                "task_id": task_id,
                "conversation_active": self.conversation.is_active() if self.conversation else False,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "modules_used": self._get_active_modules()
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return {
                "status": "error",
                "request_id": request_id,
                "error": str(e),
                "user_prompt": user_prompt
            }
    
    def _get_active_modules(self) -> list:
        """Get list of active processing modules"""
        modules = []
        if self.conversation: modules.append("conversation")
        if self.tools: modules.append("tools")
        if self.response_gen: modules.append("response_generator")
        if self.tts: modules.append("tts")
        return modules
    
    def get_status(self) -> Dict:
        """Get status of all modules"""
        return {
            "orchestrator": "active",
            "modules": {
                "conversation": self.conversation.get_status() if self.conversation else "not configured",
                "tools": self.tools.get_status() if self.tools else "not configured",
                "response_generator": self.response_gen.get_status() if self.response_gen else "not configured",
                "tts": self.tts.get_status() if self.tts else "not configured"
            }
        }