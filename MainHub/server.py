from flask import Flask, request, jsonify
import logging
import sys
import os

# Add parent directory to path to import ModelCaller modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ModelCaller.prompt_builder import PromptBuilder
from ModelCaller.call_model import ModelCaller
from TextToSpeech.google_tts import GoogleTTS

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize PromptBuilder, ModelCaller, and TTS
prompt_builder = PromptBuilder()
model_caller = ModelCaller()  # Will use OPENAI_API_KEY env var
tts = GoogleTTS()  # Will use GOOGLE_API_KEY env var

# Simple in-memory conversation storage
conversation_history = []
conversation_mode = False

@app.route('/health', methods=['GET'])
def healthcheck():
    """Health check endpoint to verify server is running"""
    return jsonify({"status": "healthy", "message": "Server is running"}), 200

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
            
            # Check if AI wants to end conversation
            end_conversation = False
            if "end_conversation_mode" in ai_response:
                end_conversation = True
                # Remove the end_conversation_mode marker from the spoken response
                ai_response_clean = ai_response.replace("end_conversation_mode", "").strip()
            else:
                ai_response_clean = ai_response
            
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
            
            # Step 4: Send to Text-to-Speech
            print("🔊 Converting response to speech...")
            tts_success = tts.speak(ai_response_clean)
            
            if not tts_success:
                print("⚠️  TTS failed, but text response is available")
            
            # Handle conversation ending
            if end_conversation:
                conversation_mode = False
                conversation_history = []
                print("🔚 Ending conversation mode - returning to wake word mode")
            
            return jsonify({
                "status": "success",
                "user_prompt": user_prompt,
                "ai_response": ai_response_clean,
                "conversation_mode": conversation_mode,  # Key flag for recorder
                "action": "continue_listening" if conversation_mode else "end_conversation",
                "usage": model_response.get("usage", {}),
                "model": model_response.get("model", "unknown"),
                "tts_played": tts_success
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