from flask import Flask, request, jsonify
import logging
import sys
import os
from datetime import datetime
import time

# Add parent directory to path to import ModelCaller modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ModelCaller.prompt_builder import PromptBuilder
from ModelCaller.call_model import ModelCaller
from TextToSpeech.google_tts import GoogleTTS
from ToolKit.tool_manager import ToolManager
from MainHub.tts_queue import TTSQueueManager

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize ToolManager first, then PromptBuilder with tool_manager
tool_manager = ToolManager()  # Initialize the tool manager
prompt_builder = PromptBuilder(tool_manager=tool_manager)  # Pass tool_manager to prompt builder
model_caller = ModelCaller()  # Will use OPENAI_API_KEY env var
tts = GoogleTTS()  # Will use GOOGLE_API_KEY env var

# Initialize TTS Queue Manager
tts_queue = TTSQueueManager(tts)
tts_queue.start()  # Start the queue processing thread

# Simple in-memory conversation storage
conversation_history = []
conversation_mode = False

# TTS states are now managed by the queue manager

@app.route('/health', methods=['GET'])
def healthcheck():
    """Health check endpoint to verify server is running"""
    return jsonify({"status": "healthy", "message": "Server is running"}), 200

@app.route('/end_conversation', methods=['POST'])
def end_conversation():
    """Endpoint to notify server that conversation mode has ended"""
    global conversation_mode, conversation_history
    
    conversation_mode = False
    conversation_history = []
    
    print("📡 Received conversation end notification - clearing history")
    return jsonify({"status": "success", "message": "Conversation mode ended"}), 200

@app.route('/wait_for_tts/<task_id>', methods=['GET'])
def wait_for_tts(task_id):
    """
    Long polling endpoint - waits indefinitely until TTS playback completes
    No timeout - will wait as long as needed for TTS to finish
    """
    poll_interval = 0.1  # How often to check status
    
    print(f"📡 Long poll request for TTS task: {task_id} (no timeout)")
    
    # Wait indefinitely until TTS completes
    while True:
        # Check task state in queue
        state = tts_queue.get_task_state(task_id)
        
        if state in ['complete', 'failed', 'error']:
            print(f"✅ TTS {state} for task {task_id}, returning to recorder")
            return jsonify({"tts_complete": True, "task_id": task_id, "state": state}), 200
        
        # Check if task_id exists (in case of error)
        if state is None:
            print(f"⚠️ Task {task_id} not found - may have completed already")
            return jsonify({"tts_complete": True, "task_id": task_id, "warning": "task not found"}), 200
        
        time.sleep(poll_interval)

@app.route('/build_prompt', methods=['POST'])
def build_prompt():
    """Endpoint to receive prompt from voice recorder"""
    global conversation_mode, conversation_history
    
    try:
        data = request.get_json()
        
        if not data or 'prompt' not in data:
            return jsonify({"error": "Missing 'prompt' field in request"}), 400
        
        user_prompt = data['prompt']
        
        # Print the received prompt to terminal
        print(f"\n{'='*50}")
        print(f"Received prompt: {user_prompt}")
        print(f"Conversation mode: {conversation_mode}")
        print(f"{'='*50}\n")
        
        # Check if we're starting a new conversation
        if not conversation_mode:
            conversation_mode = True
            conversation_history = []
            print("🎤 Starting conversation mode")
        
        # Step 1: Build the prompt using PromptBuilder
        print("📝 Building prompt...")
        # Use conversation prompt builder if in conversation mode
        built_prompt = prompt_builder.build_conversation_prompt(user_prompt, conversation_history)
        
        # Debug: Print the system prompt being sent
        print("📋 System prompt preview (first 1500 chars):")
        if built_prompt and 'messages' in built_prompt and len(built_prompt['messages']) > 0:
            system_msg = built_prompt['messages'][0].get('content', '')[:1500]
            print(system_msg + "..." if len(system_msg) == 1500 else system_msg)
        
        # Step 2: Send to ModelCaller
        print("🤖 Calling AI model...")
        model_response = model_caller.call_model(built_prompt)
        
        # Step 3: Process response
        if model_response.get("success"):
            ai_response = model_response.get("response", "No response from model")
            
            # Check for tool calls in the response
            tool_result = tool_manager.parse_and_execute_from_response(ai_response)
            tool_message = ""
            final_ai_response = ai_response
            
            # Tool execution loop - allow multiple tool calls until we get a complete answer
            max_tool_iterations = 5
            tool_iteration = 0
            tool_results = []
            accumulated_data = []  # Store all retrieved data
            
            # Build message history for the conversation
            tool_messages = conversation_history.copy() if conversation_history else []
            tool_messages.append({"role": "user", "content": user_prompt})
            
            while tool_result and tool_iteration < max_tool_iterations:
                tool_iteration += 1
                print(f"🔧 [Iteration {tool_iteration}] Executed tool: {tool_result.get('tool')}")
                tool_results.append(tool_result)
                
                # Check tool type for different handling
                if tool_result.get('tool_type') == 'retrieval':
                    # For retrieval tools, feed data back to LLM
                    print(f"📊 [Iteration {tool_iteration}] Processing retrieval tool result...")
                    
                    if tool_result.get('success'):
                        # Store the retrieved data
                        tool_data = tool_result.get('result', {})
                        accumulated_data.append({
                            'tool': tool_result.get('tool'),
                            'data': tool_data
                        })
                        
                        # Build context with the new data
                        retrieval_context = f"Tool '{tool_result['tool']}' retrieved:\n{tool_data}\n\n"
                        retrieval_context += "CRITICAL RULES:\n"
                        retrieval_context += "1. If you have ALL info: Give ULTRA-CONCISE answer (1-2 sentences MAX, will be spoken aloud)\n"
                        retrieval_context += "2. If you need MORE info: Output ONLY JSON tool call\n\n"
                        retrieval_context += "VOICE RESPONSE EXAMPLES:\n"
                        retrieval_context += "❌ 'The temperature is 72°F with humidity at 65%' → TOO LONG\n"
                        retrieval_context += "✅ 'It's 72 degrees' → PERFECT\n\n"
                        retrieval_context += "For tools: OUTPUT JSON ONLY!\n"
                        retrieval_context += 'Example: {"tool": "tool_name", "parameters": {...}}'
                    else:
                        # Handle failed tool call
                        retrieval_context = f"Tool '{tool_result.get('tool')}' failed: {tool_result.get('error', 'Unknown error')}\n"
                        retrieval_context += "MUST try a different tool. OUTPUT ONLY JSON:\n"
                        retrieval_context += 'Example: {"tool": "different_tool", "parameters": {...}}\n'
                        retrieval_context += "NO EXPLANATORY TEXT! JUST THE JSON!"
                    
                    # Add the assistant's tool call and the result to the message history
                    tool_messages.append({"role": "assistant", "content": ai_response})
                    tool_messages.append({"role": "system", "content": retrieval_context})
                    
                    # Build follow-up prompt
                    follow_up_prompt = {
                        "messages": [
                            {"role": "system", "content": prompt_builder.conversation_system_prompt}
                        ] + tool_messages,
                        "timestamp": datetime.now().isoformat(),
                        "metadata": {"mode": "tool_chain", "iteration": tool_iteration}
                    }
                    
                    # Get next response from LLM
                    print(f"🤖 [Iteration {tool_iteration}] Getting LLM response...")
                    follow_up_response = model_caller.call_model(follow_up_prompt)
                    
                    if follow_up_response.get("success"):
                        ai_response = follow_up_response.get("response", "")
                        final_ai_response = ai_response
                        
                        # Check if LLM wants to call another tool
                        next_tool = tool_manager.parse_and_execute_from_response(ai_response)
                        
                        if next_tool:
                            print(f"🔄 [Iteration {tool_iteration}] LLM calling next tool: {next_tool.get('tool')}")
                            tool_result = next_tool
                            continue
                        else:
                            # No more tools, we have our final answer
                            print(f"✅ Final answer obtained after {tool_iteration} tool call(s)")
                            tool_result = None
                            break
                    else:
                        final_ai_response = "I had trouble processing the information."
                        break
                
                elif tool_result.get('tool_type') == 'action':
                    # For action tools, often we can just use the tool's message directly
                    print(f"⚡ [Iteration {tool_iteration}] Processing action tool result...")
                    
                    # Special handling for set_reminder - just use its message
                    if tool_result.get('tool') == 'set_reminder' and tool_result.get('success'):
                        # Use the concise message from the tool itself
                        tool_response = tool_result.get('result', {})
                        if isinstance(tool_response, dict):
                            final_ai_response = tool_response.get('message', 'Timer set')
                        else:
                            final_ai_response = str(tool_response)
                        tool_result = None
                        break
                    
                    # For other action tools, check if more actions needed
                    if tool_result.get('success'):
                        action_feedback = f"Action '{tool_result['tool']}' completed successfully."
                        if tool_result.get('result'):
                            action_feedback += f" Result: {tool_result.get('result')}"
                    else:
                        action_feedback = f"Action '{tool_result['tool']}' failed: {tool_result.get('error', 'Unknown error')}"
                    
                    # Add feedback to messages
                    tool_messages.append({"role": "assistant", "content": ai_response})
                    action_prompt = action_feedback + "\n\n"
                    action_prompt += "CRITICAL: Provide ULTRA-CONCISE response (max 1-2 sentences for voice output)\n"
                    action_prompt += "If MORE actions needed: Output ONLY JSON tool call\n"
                    action_prompt += "If task COMPLETE: Give brief confirmation only\n"
                    tool_messages.append({"role": "system", "content": action_prompt})
                    
                    # Check if more actions are needed
                    follow_up_prompt = {
                        "messages": [
                            {"role": "system", "content": prompt_builder.conversation_system_prompt}
                        ] + tool_messages,
                        "timestamp": datetime.now().isoformat(),
                        "metadata": {"mode": "action_chain", "iteration": tool_iteration}
                    }
                    
                    follow_up_response = model_caller.call_model(follow_up_prompt)
                    
                    if follow_up_response.get("success"):
                        ai_response = follow_up_response.get("response", "")
                        final_ai_response = ai_response
                        
                        # Check for another tool call
                        next_tool = tool_manager.parse_and_execute_from_response(ai_response)
                        
                        if next_tool:
                            print(f"🔄 [Iteration {tool_iteration}] LLM calling next tool: {next_tool.get('tool')}")
                            tool_result = next_tool
                            continue
                        else:
                            tool_result = None
                            break
                    else:
                        final_ai_response = ai_response
                        break
            
            # Check if we hit max iterations
            if tool_iteration >= max_tool_iterations:
                print(f"⚠️ Reached maximum tool iterations ({max_tool_iterations})")
                final_ai_response += f"\n\n[System: Maximum tool calls reached. Based on the data gathered:]"
                
                # Summarize what we collected
                if accumulated_data:
                    for item in accumulated_data:
                        final_ai_response += f"\n- {item['tool']}: Retrieved data successfully"
            
            # Check if AI wants to end conversation (use final response for retrieval tools)
            end_conversation = False
            if "end_conversation_mode" in final_ai_response:
                end_conversation = True
                # Remove the end_conversation_mode marker from the spoken response
                ai_response_clean = final_ai_response.replace("end_conversation_mode", "").strip()
            else:
                ai_response_clean = final_ai_response
            
            # Remove JSON tool calls from the spoken response
            import re
            ai_response_clean = re.sub(r'\{.*"tool".*\}', '', ai_response_clean, flags=re.DOTALL).strip()
            
            # Add tool message to response if tool was executed (for action tools)
            if tool_message:
                ai_response_clean += tool_message
            
            # Print AI response to terminal
            print(f"\n{'='*50}")
            print(f"AI Response: {ai_response_clean}")
            print(f"End conversation: {end_conversation}")
            print(f"Tokens used: {model_response.get('usage', {}).get('total_tokens', 'N/A')}")
            print(f"{'='*50}\n")
            
            # Update conversation history (before ending)
            if conversation_mode and not end_conversation:
                conversation_history.append({"role": "user", "content": user_prompt})
                conversation_history.append({"role": "assistant", "content": ai_response_clean})
                print(f"💾 Updated conversation history (now {len(conversation_history)} messages)")
            
            # Step 4: Add to TTS Queue
            print("🔊 Adding to TTS queue...")
            
            # Generate a task ID and add to queue
            task_id = tts_queue.add_to_queue(
                text=ai_response_clean,
                metadata={
                    'source': 'conversation',
                    'user_prompt': user_prompt[:50],  # First 50 chars for reference
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            print(f"✅ Added to TTS queue: task_id={task_id}, queue_size={tts_queue.get_queue_size()}")
            
            # Handle conversation ending
            if end_conversation:
                conversation_mode = False
                conversation_history = []
                print("🔚 Ending conversation mode - returning to wake word mode")
            
            return jsonify({
                "status": "success",
                "task_id": task_id,  # For tracking TTS completion
                "user_prompt": user_prompt,
                "ai_response": ai_response_clean,
                "conversation_mode": conversation_mode,  # Key flag for recorder
                "action": "continue_listening" if conversation_mode else "end_conversation",
                "usage": model_response.get("usage", {}),
                "model": model_response.get("model", "unknown"),
                "tts_started": True  # TTS is playing in background
            }), 200
        else:
            error_msg = model_response.get("error", "Unknown error occurred")
            logger.error(f"Model call failed: {error_msg}")
            
            return jsonify({
                "status": "error",
                "message": "Failed to get AI response",
                "error": error_msg,
                "user_prompt": user_prompt
            }), 500
        
    except Exception as e:
        logger.error(f"Error processing prompt: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting Flask server...")
    print("Healthcheck endpoint: http://localhost:5000/health")
    print("Build prompt endpoint: http://localhost:5000/build_prompt")
    app.run(host='0.0.0.0', port=5000, debug=True)