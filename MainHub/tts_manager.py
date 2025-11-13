"""
TTS Manager Wrapper
Simplified interface to the TTS queue
"""

import logging
import re
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class TTSManager:
    """Manages TTS queue operations"""
    
    def __init__(self, tts_queue):
        """
        Initialize TTS manager
        
        Args:
            tts_queue: TTSQueueManager instance
        """
        self.queue = tts_queue
        logger.info("TTSManager initialized")
    
    def queue_speech(self, text: str, source: str = "conversation") -> Optional[str]:
        """
        Queue text for TTS playback
        
        Args:
            text: Text to speak
            source: Source of the text (conversation, reminder, etc.)
            
        Returns:
            Task ID for tracking
        """
        # Clean the text for TTS
        clean_text = self._clean_for_tts(text)
        
        # Add to queue
        task_id = self.queue.add_to_queue(
            text=clean_text,
            metadata={"source": source}
        )
        
        logger.debug(f"Queued TTS: {task_id} ({len(clean_text)} chars)")
        
        return task_id
    
    def _clean_for_tts(self, text: str) -> str:
        """
        Clean text for TTS output
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text suitable for speech
        """
        # Remove JSON tool calls
        text = re.sub(r'\{.*"tool".*\}', '', text, flags=re.DOTALL).strip()
        
        # Remove the end_conversation marker
        if "end_conversation_mode" in text:
            text = text.replace("end_conversation_mode", "").strip()
        
        return text
    
    def get_status(self) -> Dict:
        """Get current status"""
        return self.queue.get_status() if self.queue else {"active": False}