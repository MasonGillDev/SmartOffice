"""
Modular Server
Simplified server that delegates to orchestrator
"""

from flask import Flask, request, jsonify
import logging
import sys
import os
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import core components
from ModelCaller.prompt_builder import PromptBuilder
from ModelCaller.call_model import ModelCaller
from TextToSpeech.google_tts import GoogleTTS
from ToolKit.tool_manager import ToolManager

# Import modular components
from MainHub.tts_queue import TTSQueueManager
from MainHub.orchestrator import RequestOrchestrator
from MainHub.conversation_manager import ConversationManager
from MainHub.tool_executor import ToolExecutor
from MainHub.response_generator import ResponseGenerator
from MainHub.tts_manager import TTSManager

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize base components
logger.info("Initializing base components...")
tool_manager = ToolManager()
prompt_builder = PromptBuilder(tool_manager=tool_manager)
model_caller = ModelCaller()
tts_engine = GoogleTTS()

# Initialize TTS Queue
logger.info("Initializing TTS queue...")
tts_queue = TTSQueueManager(tts_engine)
tts_queue.start()

# Initialize modular components
logger.info("Initializing modular components...")
conversation_mgr = ConversationManager()
tool_executor = ToolExecutor(tool_manager, model_caller, prompt_builder)
response_gen = ResponseGenerator(model_caller, prompt_builder)
tts_mgr = TTSManager(tts_queue)

# Initialize orchestrator with all modules
logger.info("Initializing request orchestrator...")
orchestrator = RequestOrchestrator(
    conversation_manager=conversation_mgr,
    tool_executor=tool_executor,
    response_generator=response_gen,
    tts_manager=tts_mgr
)

logger.info("✅ All components initialized")

# =======================
# ROUTES
# =======================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "Modular server is running",
        "modules": orchestrator.get_status()
    }), 200

@app.route('/query', methods=['POST'])
def query():
    """
    Main query endpoint - simplified interface
    Accepts: {"prompt": "user text"}
    Returns: Standard response with AI answer and TTS task ID
    """
    try:
        data = request.json
        user_prompt = data.get('prompt', '').strip()
        
        if not user_prompt:
            return jsonify({"error": "No prompt provided"}), 400
        
        logger.info(f"Query received: {user_prompt[:50]}...")
        
        # Process through orchestrator
        result = orchestrator.process_request(user_prompt)
        
        # Check for conversation ending
        if conversation_mgr.should_end_conversation(result.get('ai_response', '')):
            conversation_mgr.end_conversation()
            result['conversation_active'] = False
            result['action'] = 'end_conversation'
        else:
            result['action'] = 'continue_listening' if conversation_mgr.is_active() else 'wait'
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "user_prompt": user_prompt
        }), 500

@app.route('/tts_check/<task_id>', methods=['GET'])
def tts_check(task_id):
    """Check TTS task status"""
    state = tts_queue.get_task_state(task_id)
    
    return jsonify({
        "task_id": task_id,
        "state": state or 'unknown',
        "queue_size": tts_queue.get_queue_size(),
        "is_speaking": tts_queue.is_speaking()
    }), 200

@app.route('/tts_wait/<task_id>', methods=['GET'])
def tts_wait(task_id):
    """Long-poll wait for TTS completion"""
    logger.info(f"Long poll for TTS task: {task_id}")
    
    while True:
        state = tts_queue.get_task_state(task_id)
        
        if state in ['complete', 'failed', 'error', 'cancelled']:
            return jsonify({
                "tts_complete": True,
                "task_id": task_id,
                "state": state
            }), 200
        
        if state is None:
            return jsonify({
                "tts_complete": True,
                "task_id": task_id,
                "warning": "task not found"
            }), 200
        
        time.sleep(0.1)

@app.route('/tts_announce', methods=['POST'])
def tts_announce():
    """
    Direct TTS announcement endpoint
    Used by reminder daemon and other services
    """
    try:
        data = request.json
        message = data.get('message', '')
        source = data.get('source', 'system')
        metadata = data.get('metadata', {})
        
        if not message:
            return jsonify({"error": "No message provided"}), 400
        
        # Add to TTS queue
        task_id = tts_queue.add_to_queue(
            text=message,
            metadata={**metadata, 'source': source}
        )
        
        return jsonify({
            "status": "success",
            "task_id": task_id,
            "message": "Announcement queued"
        }), 200
        
    except Exception as e:
        logger.error(f"Error queueing announcement: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/conversation/end', methods=['POST'])
def end_conversation():
    """Explicitly end conversation mode"""
    conversation_mgr.end_conversation()
    
    return jsonify({
        "status": "success",
        "message": "Conversation ended"
    }), 200

@app.route('/status', methods=['GET'])
def status():
    """Get system status"""
    return jsonify(orchestrator.get_status()), 200

# For backward compatibility - redirect old endpoint
@app.route('/build_prompt', methods=['POST'])
def build_prompt_legacy():
    """Legacy endpoint - redirects to /query"""
    logger.info("Legacy /build_prompt called, redirecting to /query")
    return query()

if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("Starting Modular SmartOffice Server")
    logger.info("Endpoints:")
    logger.info("  - POST /query - Main query endpoint")
    logger.info("  - GET  /health - Health check")
    logger.info("  - GET  /status - System status")
    logger.info("  - POST /tts_announce - Direct TTS")
    logger.info("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)