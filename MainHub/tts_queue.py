"""
TTS Queue Manager
Handles queuing and sequential playback of all TTS messages
"""

import threading
import queue
import time
import uuid
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class TTSQueueManager:
    """Manages a FIFO queue for TTS playback"""
    
    def __init__(self, tts_engine):
        """
        Initialize the TTS Queue Manager
        
        Args:
            tts_engine: The TTS engine instance to use for speaking
        """
        self.tts = tts_engine
        self.queue = queue.Queue()
        self.is_running = False
        self.current_task = None
        self.task_states = {}  # task_id -> state
        self.task_states_lock = threading.Lock()
        self.worker_thread = None
        
    def start(self):
        """Start the queue processing thread"""
        if not self.is_running:
            self.is_running = True
            self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()
            logger.info("TTS Queue Manager started")
    
    def stop(self):
        """Stop the queue processing thread"""
        self.is_running = False
        # Add a sentinel to wake up the thread
        self.queue.put(None)
        if self.worker_thread:
            self.worker_thread.join(timeout=2)
        logger.info("TTS Queue Manager stopped")
    
    def add_to_queue(self, text: str, task_id: Optional[str] = None, metadata: Optional[Dict] = None) -> str:
        """
        Add text to the TTS queue
        
        Args:
            text: The text to speak
            task_id: Optional task ID for tracking (will generate one if not provided)
            metadata: Optional metadata (source, priority, etc.)
            
        Returns:
            The task_id for tracking
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # Create queue item
        item = {
            'task_id': task_id,
            'text': text,
            'metadata': metadata or {},
            'queued_time': time.time()
        }
        
        # Update task state
        with self.task_states_lock:
            self.task_states[task_id] = 'queued'
        
        # Add to queue
        self.queue.put(item)
        
        logger.debug(f"Added to TTS queue: task_id={task_id}, length={len(text)}")
        
        return task_id
    
    def get_task_state(self, task_id: str) -> Optional[str]:
        """Get the current state of a task"""
        with self.task_states_lock:
            return self.task_states.get(task_id)
    
    def get_queue_size(self) -> int:
        """Get the current size of the queue"""
        return self.queue.qsize()
    
    def is_speaking(self) -> bool:
        """Check if TTS is currently speaking"""
        return self.current_task is not None
    
    def clear_queue(self):
        """Clear all pending items from the queue"""
        while not self.queue.empty():
            try:
                item = self.queue.get_nowait()
                if item:
                    with self.task_states_lock:
                        if item['task_id'] in self.task_states:
                            self.task_states[item['task_id']] = 'cancelled'
            except queue.Empty:
                break
        logger.info("TTS queue cleared")
    
    def _process_queue(self):
        """Main queue processing loop (runs in separate thread)"""
        logger.info("TTS queue processing started")
        
        while self.is_running:
            try:
                # Get next item from queue (blocks until available)
                item = self.queue.get(timeout=1)
                
                # Check for stop signal
                if item is None:
                    break
                
                task_id = item['task_id']
                text = item['text']
                metadata = item.get('metadata', {})
                
                # Update state to playing
                with self.task_states_lock:
                    self.task_states[task_id] = 'playing'
                    self.current_task = task_id
                
                logger.info(f"TTS playing: task_id={task_id}, source={metadata.get('source', 'unknown')}")
                
                # Speak the text
                try:
                    success = self.tts.speak(text)
                    
                    # Update state based on result
                    with self.task_states_lock:
                        if success:
                            self.task_states[task_id] = 'complete'
                            logger.info(f"TTS complete: task_id={task_id}")
                        else:
                            self.task_states[task_id] = 'failed'
                            logger.error(f"TTS failed: task_id={task_id}")
                        
                        self.current_task = None
                        
                except Exception as e:
                    logger.error(f"Error in TTS playback: {e}")
                    with self.task_states_lock:
                        self.task_states[task_id] = 'error'
                        self.current_task = None
                
                # Mark queue task as done
                self.queue.task_done()
                
            except queue.Empty:
                # No items in queue, continue waiting
                continue
            except Exception as e:
                logger.error(f"Error in queue processing: {e}")
                time.sleep(0.1)  # Brief pause on error
        
        logger.info("TTS queue processing stopped")
    
    def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> str:
        """
        Wait for a specific task to complete
        
        Args:
            task_id: The task ID to wait for
            timeout: Optional timeout in seconds
            
        Returns:
            The final state of the task
        """
        start_time = time.time()
        
        while True:
            state = self.get_task_state(task_id)
            
            if state in ['complete', 'failed', 'error', 'cancelled']:
                return state
            
            if timeout and (time.time() - start_time) > timeout:
                return 'timeout'
            
            time.sleep(0.1)
    
    def get_status(self) -> Dict:
        """Get current status of the queue manager"""
        with self.task_states_lock:
            return {
                'is_running': self.is_running,
                'queue_size': self.queue.qsize(),
                'is_speaking': self.current_task is not None,
                'current_task': self.current_task,
                'total_tasks_tracked': len(self.task_states)
            }