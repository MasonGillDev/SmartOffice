from flask import Flask, request, jsonify
import logging
import sys
import os
from datetime import datetime
import uuid
import threading
import time

# Add parent directory to path to import ModelCaller modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ModelCaller.prompt_builder import PromptBuilder
from ModelCaller.call_model import ModelCaller
from TextToSpeech.google_tts import GoogleTTS
from ToolKit.tool_manager import ToolManager

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize ToolManager first, then PromptBuilder with tool_manager
tool_manager = ToolManager()  # Initialize the tool manager
prompt_builder = PromptBuilder(tool_manager=tool_manager)  # Pass tool_manager to prompt builder
model_caller = ModelCaller()  # Will use OPENAI_API_KEY env var
tts = GoogleTTS()  # Will use GOOGLE_API_KEY env var

# Simple in-memory conversation storage
conversation_history = []
conversation_mode = False

# Track TTS playback states for each request
tts_states = {}  # {task_id: 'playing' | 'complete'}
tts_states_lock = threading.Lock()

@app.route('/health', methods=['GET'])
def healthcheck():
    """Health check endpoint to verify server is running"""
    return jsonify({"status": "healthy", "message": "Server is running"}), 200

@app.route('/wait_for_tts/<task_id>', methods=['GET'])
def wait_for_tts(task_id):
    """
    Long polling endpoint - waits until TTS playback completes
    Blocks until TTS is done or timeout (30 seconds)
    """
    timeout = 30  # Maximum wait time
    poll_interval = 0.1  # How often to check status
    start_time = time.time()
    
    print(f"📡 Long poll request for TTS task: {task_id}")
    
    while time.time() - start_time < timeout:
        with tts_states_lock:
            state = tts_states.get(task_id)
        
        if state == 'complete':
            print(f"✅ TTS complete for task {task_id}, returning to recorder")
            # Clean up the state
            with tts_states_lock:
                del tts_states[task_id]
            return jsonify({"tts_complete": True, "task_id": task_id}), 200
        
        time.sleep(poll_interval)
    
    # Timeout reached
    print(f"⏱️ Long poll timeout for task {task_id}")
    return jsonify({"tts_complete": False, "timeout": True, "task_id": task_id}), 200

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
            
            if tool_result:
                print(f"🔧 Executed tool: {tool_result}")
                
                # Check tool type for different handling
                if tool_result.get('tool_type') == 'retrieval' and tool_result.get('success'):
                    # For retrieval tools, feed data back to LLM
                    print(f"📊 Retrieval tool - feeding data back to LLM")
                    
                    # Build a follow-up prompt with the retrieved data
                    retrieval_context = f"Tool '{tool_result['tool']}' retrieved the following data:\n{tool_result['result']}\n\nNow answer the user's original question based on this data."
                    
                    # Add to conversation as system message
                    follow_up_messages = conversation_history.copy() if conversation_history else []
                    follow_up_messages.append({"role": "user", "content": user_prompt})
                    follow_up_messages.append({"role": "assistant", "content": ai_response})
                    follow_up_messages.append({"role": "system", "content": retrieval_context})
                    
                    # Build follow-up prompt
                    follow_up_prompt = {
                        "messages": [
                            {"role": "system", "content": prompt_builder.conversation_system_prompt}
                        ] + follow_up_messages,
                        "timestamp": datetime.now().isoformat(),
                        "metadata": {"mode": "retrieval_followup"}
                    }
                    
                    # Get final response from LLM with the data
                    print("🤖 Getting final response with retrieved data...")
                    follow_up_response = model_caller.call_model(follow_up_prompt)
                    
                    if follow_up_response.get("success"):
                        final_ai_response = follow_up_response.get("response", "I found the information but couldn't process it.")
                    else:
                        final_ai_response = "I retrieved the data but had trouble processing it."
                
                elif tool_result.get('tool_type') == 'action':
                    # For action tools, just confirm the action
                    if tool_result.get('success'):
                        tool_message = f" The note has been saved."
                    else:
                        tool_message = f" There was an error with the tool: {tool_result.get('error')}"
            
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
            
            # Generate a task ID for tracking TTS playback
            task_id = str(uuid.uuid4())
            
            # Step 4: Send to Text-to-Speech (in background thread)
            print("🔊 Starting TTS playback...")
            
            def play_tts_with_tracking():
                with tts_states_lock:
                    tts_states[task_id] = 'playing'
                
                # Synthesize and play
                tts_success = tts.speak(ai_response_clean)
                
                # Mark as complete
                with tts_states_lock:
                    tts_states[task_id] = 'complete'
                    
                if not tts_success:
                    print("⚠️  TTS failed")
                else:
                    print(f"✅ TTS complete for task {task_id}")
            
            # Start TTS in background thread
            tts_thread = threading.Thread(target=play_tts_with_tracking)
            tts_thread.start()
            
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