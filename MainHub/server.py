from flask import Flask, request, jsonify
import logging
import sys
import os

# Add parent directory to path to import ModelCaller modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ModelCaller.prompt_builder import PromptBuilder
from ModelCaller.call_model import ModelCaller

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize PromptBuilder and ModelCaller
prompt_builder = PromptBuilder()
model_caller = ModelCaller()  # Will use OPENAI_API_KEY env var

@app.route('/health', methods=['GET'])
def healthcheck():
    """Health check endpoint to verify server is running"""
    return jsonify({"status": "healthy", "message": "Server is running"}), 200

@app.route('/build_prompt', methods=['POST'])
def build_prompt():
    """Endpoint to receive prompt from voice recorder"""
    try:
        data = request.get_json()
        
        if not data or 'prompt' not in data:
            return jsonify({"error": "Missing 'prompt' field in request"}), 400
        
        user_prompt = data['prompt']
        
        # Print the received prompt to terminal
        print(f"\n{'='*50}")
        print(f"Received prompt: {user_prompt}")
        print(f"{'='*50}\n")
        
        # Step 1: Build the prompt using PromptBuilder
        print("📝 Building prompt...")
        built_prompt = prompt_builder.build_prompt(user_prompt)
        
        # Step 2: Send to ModelCaller
        print("🤖 Calling AI model...")
        model_response = model_caller.call_model(built_prompt)
        
        # Step 3: Process response
        if model_response.get("success"):
            ai_response = model_response.get("response", "No response from model")
            
            # Print AI response to terminal
            print(f"\n{'='*50}")
            print(f"AI Response: {ai_response}")
            print(f"Tokens used: {model_response.get('usage', {}).get('total_tokens', 'N/A')}")
            print(f"{'='*50}\n")
            
            return jsonify({
                "status": "success",
                "user_prompt": user_prompt,
                "ai_response": ai_response,
                "usage": model_response.get("usage", {}),
                "model": model_response.get("model", "unknown")
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