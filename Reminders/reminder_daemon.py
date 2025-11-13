#!/usr/bin/env python3
"""
Reminder Daemon Service
Monitors the database and triggers reminders through TTS queue
"""

import time
import sys
import os
import logging
import signal
from datetime import datetime
import threading

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Reminders.reminder_db import ReminderDB
from MainHub.tts_queue import TTSQueueManager
from TextToSpeech.google_tts import GoogleTTS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ReminderDaemon')

class ReminderDaemon:
    """Daemon service that monitors and triggers reminders"""
    
    def __init__(self, check_interval: int = 10):
        """
        Initialize the daemon
        
        Args:
            check_interval: How often to check for reminders (seconds)
        """
        self.db = ReminderDB()
        self.check_interval = check_interval
        self.is_running = False
        self.thread = None
        
        # Initialize TTS queue (shared with main server)
        tts = GoogleTTS()
        self.tts_queue = TTSQueueManager(tts)
        
        # Start the TTS queue if not already running
        if not self.tts_queue.is_running:
            self.tts_queue.start()
            logger.info("Started TTS queue from daemon")
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
    
    def start(self):
        """Start the daemon"""
        if self.is_running:
            logger.warning("Daemon already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info(f"Reminder daemon started (checking every {self.check_interval}s)")
    
    def stop(self):
        """Stop the daemon"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Reminder daemon stopped")
    
    def _run_loop(self):
        """Main daemon loop"""
        logger.info("Daemon loop started")
        
        while self.is_running:
            try:
                # Check for pending reminders
                self._check_reminders()
                
                # Clean up old reminders once per day
                if datetime.now().hour == 3 and datetime.now().minute == 0:
                    count = self.db.cleanup_old_reminders(days_to_keep=7)
                    if count > 0:
                        logger.info(f"Cleaned up {count} old reminders")
                
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}")
            
            # Sleep for the check interval
            time.sleep(self.check_interval)
    
    def _check_reminders(self):
        """Check and trigger any pending reminders"""
        current_time = datetime.now()
        
        # Get all reminders that should trigger
        pending = self.db.get_pending_reminders(current_time)
        
        for reminder in pending:
            try:
                logger.info(f"Triggering reminder: {reminder['id']} - {reminder['description']}")
                
                # Generate TTS message based on type
                tts_message = self._generate_tts_message(reminder)
                
                # Add to TTS queue with metadata
                self.tts_queue.add_to_queue(
                    text=tts_message,
                    metadata={
                        'source': 'reminder',
                        'reminder_id': reminder['id'],
                        'type': reminder['type'],
                        'priority': reminder.get('priority', 'normal')
                    }
                )
                
                # Mark as triggered in database
                self.db.mark_triggered(reminder['id'])
                
                logger.info(f"Successfully queued reminder {reminder['id']} for TTS")
                
            except Exception as e:
                logger.error(f"Failed to trigger reminder {reminder['id']}: {e}")
    
    def _generate_tts_message(self, reminder: dict) -> str:
        """
        Generate the TTS message for a reminder
        
        Args:
            reminder: Reminder dictionary from database
            
        Returns:
            The message to speak
        """
        reminder_type = reminder.get('type', 'reminder')
        description = reminder.get('description', '')
        
        if reminder_type == 'timer':
            # For timers, keep it simple
            if 'timer' in description.lower():
                # If description already says "timer", just use it
                return f"Your {description} is done"
            else:
                return f"Timer: {description}"
        else:
            # For reminders, be more descriptive
            current_time = datetime.now()
            
            # Check if it's overdue
            trigger_time = datetime.fromisoformat(reminder['trigger_time'])
            
            if (current_time - trigger_time).total_seconds() > 60:
                # Overdue by more than a minute
                return f"Reminder (overdue): {description}"
            else:
                return f"Reminder: {description}"
    
    def run_forever(self):
        """Run the daemon in the foreground (for standalone mode)"""
        self.start()
        
        try:
            # Keep the main thread alive
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()

def main():
    """Main entry point for standalone daemon"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Reminder Daemon Service')
    parser.add_argument(
        '--interval', 
        type=int, 
        default=10,
        help='Check interval in seconds (default: 10)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run in test mode with verbose output'
    )
    
    args = parser.parse_args()
    
    if args.test:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("Running in test mode")
    
    # Create and run daemon
    daemon = ReminderDaemon(check_interval=args.interval)
    
    logger.info("Starting Reminder Daemon...")
    logger.info(f"Check interval: {args.interval} seconds")
    logger.info("Press Ctrl+C to stop")
    
    daemon.run_forever()

if __name__ == '__main__':
    main()