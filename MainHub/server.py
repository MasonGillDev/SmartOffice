from flask import Flask, request, jsonify
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        
        prompt = data['prompt']
        
        # Print the received prompt to terminal
        print(f"\n{'='*50}")
        print(f"Received prompt: {prompt}")
        print(f"{'='*50}\n")
        
        # Log the prompt
        logger.info(f"Received prompt: {prompt}")
        
        return jsonify({
            "status": "success",
            "message": "Prompt received",
            "prompt": prompt
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing prompt: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting Flask server...")
    print("Healthcheck endpoint: http://localhost:5000/health")
    print("Build prompt endpoint: http://localhost:5000/build_prompt")
    app.run(host='0.0.0.0', port=5000, debug=True)