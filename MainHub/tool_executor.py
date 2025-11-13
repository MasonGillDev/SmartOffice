"""
Tool Executor
Handles all tool parsing, execution, and chaining logic
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ToolExecutor:
    """Executes tools and manages tool chaining"""
    
    def __init__(self, tool_manager, model_caller, prompt_builder, max_iterations: int = 5):
        """
        Initialize the tool executor
        
        Args:
            tool_manager: ToolKit tool manager instance
            model_caller: ModelCaller instance for LLM calls
            prompt_builder: PromptBuilder instance
            max_iterations: Maximum tool chain iterations
        """
        self.tool_manager = tool_manager
        self.model_caller = model_caller
        self.prompt_builder = prompt_builder
        self.max_iterations = max_iterations
        
        logger.info(f"ToolExecutor initialized (max iterations: {max_iterations})")
    
    def process_tools(self, ai_response: str, user_prompt: str, context: Dict) -> str:
        """
        Process any tool calls in the AI response
        
        Args:
            ai_response: Initial AI response that may contain tool calls
            user_prompt: Original user prompt
            context: Conversation context
            
        Returns:
            Final AI response after all tool processing
        """
        # Check for initial tool call
        tool_result = self.tool_manager.parse_and_execute_from_response(ai_response)
        
        if not tool_result:
            # No tools to execute
            return ai_response
        
        # Execute tool chain
        return self._execute_tool_chain(
            initial_tool_result=tool_result,
            initial_ai_response=ai_response,
            user_prompt=user_prompt,
            context=context
        )
    
    def _execute_tool_chain(self, initial_tool_result: Dict, initial_ai_response: str, 
                           user_prompt: str, context: Dict) -> str:
        """
        Execute a chain of tools until complete
        
        Returns:
            Final response text after all tools
        """
        tool_result = initial_tool_result
        ai_response = initial_ai_response
        final_response = ai_response
        
        iteration = 0
        tool_results = []
        messages = context.get('history', []).copy()
        messages.append({"role": "user", "content": user_prompt})
        
        while tool_result and iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Tool iteration {iteration}: {tool_result.get('tool')}")
            tool_results.append(tool_result)
            
            # Handle based on tool type
            if tool_result.get('tool_type') == 'retrieval':
                final_response = self._handle_retrieval_tool(
                    tool_result, ai_response, messages
                )
            elif tool_result.get('tool_type') == 'action':
                # Special handling for set_reminder
                if tool_result.get('tool') == 'set_reminder' and tool_result.get('success'):
                    result = tool_result.get('result', {})
                    if isinstance(result, dict):
                        return result.get('message', 'Timer set')
                    return str(result)
                
                final_response = self._handle_action_tool(
                    tool_result, ai_response, messages
                )
            
            # Check if we should continue
            if isinstance(final_response, tuple):
                final_response, tool_result = final_response
                ai_response = final_response
            else:
                break
        
        if iteration >= self.max_iterations:
            logger.warning(f"Reached maximum tool iterations ({self.max_iterations})")
            final_response += "\n[Maximum tool calls reached]"
        
        return final_response
    
    def _handle_retrieval_tool(self, tool_result: Dict, ai_response: str, 
                              messages: List[Dict]) -> tuple:
        """
        Handle retrieval-type tools that need data fed back to LLM
        
        Returns:
            (final_response, next_tool_result) or just final_response
        """
        if tool_result.get('success'):
            tool_data = tool_result.get('result', {})
            retrieval_context = f"Tool '{tool_result['tool']}' retrieved:\n{tool_data}\n\n"
            retrieval_context += "CRITICAL: You MUST either:\n"
            retrieval_context += "1. If you have ALL info: Give ULTRA-CONCISE answer (1-2 sentences MAX)\n"
            retrieval_context += "2. If you need MORE info: Output ONLY JSON tool call\n"
        else:
            retrieval_context = f"Tool '{tool_result.get('tool')}' failed: {tool_result.get('error')}\n"
            retrieval_context += "MUST try different tool. OUTPUT ONLY JSON!"
        
        messages.append({"role": "assistant", "content": ai_response})
        messages.append({"role": "system", "content": retrieval_context})
        
        # Get LLM response
        follow_up = self._call_model(messages, "tool_chain")
        
        if follow_up.get("success"):
            response = follow_up.get("response", "")
            
            # Check for another tool call
            next_tool = self.tool_manager.parse_and_execute_from_response(response)
            if next_tool:
                return (response, next_tool)
            
            return response
        
        return "I had trouble processing the information."
    
    def _handle_action_tool(self, tool_result: Dict, ai_response: str, 
                          messages: List[Dict]) -> tuple:
        """
        Handle action-type tools
        
        Returns:
            (final_response, next_tool_result) or just final_response
        """
        if tool_result.get('success'):
            feedback = f"Action '{tool_result['tool']}' completed."
        else:
            feedback = f"Action '{tool_result['tool']}' failed: {tool_result.get('error')}"
        
        messages.append({"role": "assistant", "content": ai_response})
        messages.append({"role": "system", "content": 
            feedback + "\nProvide ULTRA-CONCISE confirmation (1 sentence) or OUTPUT JSON for next tool."})
        
        # Get LLM response
        follow_up = self._call_model(messages, "action_chain")
        
        if follow_up.get("success"):
            response = follow_up.get("response", "")
            
            # Check for another tool call
            next_tool = self.tool_manager.parse_and_execute_from_response(response)
            if next_tool:
                return (response, next_tool)
            
            return response
        
        return feedback
    
    def _call_model(self, messages: List[Dict], mode: str) -> Dict:
        """Call the model with messages"""
        prompt = {
            "messages": [
                {"role": "system", "content": self.prompt_builder.conversation_system_prompt}
            ] + messages,
            "timestamp": datetime.now().isoformat(),
            "metadata": {"mode": mode}
        }
        
        return self.model_caller.call_model(prompt)
    
    def get_status(self) -> Dict:
        """Get current status"""
        return {
            "active": True,
            "max_iterations": self.max_iterations,
            "tools_available": len(self.tool_manager.tools)
        }