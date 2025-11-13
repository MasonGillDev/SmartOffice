"""
Reminder Database Manager
Handles SQLite storage for reminders and timers
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import threading
from pathlib import Path

class ReminderDB:
    """SQLite database manager for reminders and timers"""
    
    def __init__(self, db_path: str = None):
        """
        Initialize the database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            # Default to a file in the Reminders directory
            reminders_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(reminders_dir, 'reminders.db')
        
        self.db_path = db_path
        self.lock = threading.Lock()  # Thread safety for concurrent access
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create reminders table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,  -- 'timer' or 'reminder'
                    description TEXT NOT NULL,
                    trigger_time TEXT NOT NULL,  -- ISO format timestamp
                    created_time TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',  -- pending, triggered, cancelled, failed
                    priority TEXT DEFAULT 'normal',  -- low, normal, high
                    metadata TEXT,  -- JSON string for extra data
                    repeat_pattern TEXT,  -- null, daily, weekly, monthly
                    source TEXT DEFAULT 'voice'  -- voice, calendar, manual
                )
            ''')
            
            # Create index on trigger_time for fast queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_trigger_time 
                ON reminders(trigger_time, status)
            ''')
            
            conn.commit()
    
    def add_reminder(self, reminder_data: Dict) -> str:
        """
        Add a new reminder to the database
        
        Args:
            reminder_data: Dictionary with reminder details
            
        Returns:
            The reminder ID
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Generate unique ID if not provided
                reminder_id = reminder_data.get('id', f"{datetime.now().timestamp()}_{os.urandom(4).hex()}")
                
                cursor.execute('''
                    INSERT INTO reminders (
                        id, type, description, trigger_time, created_time,
                        status, priority, metadata, repeat_pattern, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    reminder_id,
                    reminder_data.get('type', 'reminder'),
                    reminder_data['description'],
                    reminder_data['trigger_time'],
                    reminder_data.get('created_time', datetime.now().isoformat()),
                    reminder_data.get('status', 'pending'),
                    reminder_data.get('priority', 'normal'),
                    json.dumps(reminder_data.get('metadata', {})),
                    reminder_data.get('repeat_pattern'),
                    reminder_data.get('source', 'voice')
                ))
                
                conn.commit()
                return reminder_id
    
    def get_pending_reminders(self, current_time: datetime = None) -> List[Dict]:
        """
        Get all reminders that should trigger now or earlier
        
        Args:
            current_time: Time to check against (defaults to now)
            
        Returns:
            List of reminder dictionaries
        """
        if current_time is None:
            current_time = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM reminders
                WHERE status = 'pending'
                AND trigger_time <= ?
                ORDER BY trigger_time ASC
            ''', (current_time.isoformat(),))
            
            columns = [col[0] for col in cursor.description]
            reminders = []
            
            for row in cursor.fetchall():
                reminder = dict(zip(columns, row))
                # Parse metadata JSON
                if reminder['metadata']:
                    reminder['metadata'] = json.loads(reminder['metadata'])
                reminders.append(reminder)
            
            return reminders
    
    def mark_triggered(self, reminder_id: str) -> bool:
        """
        Mark a reminder as triggered
        
        Args:
            reminder_id: ID of the reminder to update
            
        Returns:
            True if successful
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE reminders
                    SET status = 'triggered'
                    WHERE id = ?
                ''', (reminder_id,))
                
                conn.commit()
                return cursor.rowcount > 0
    
    def cancel_reminder(self, reminder_id: str) -> bool:
        """
        Cancel a pending reminder
        
        Args:
            reminder_id: ID of the reminder to cancel
            
        Returns:
            True if successful
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE reminders
                    SET status = 'cancelled'
                    WHERE id = ? AND status = 'pending'
                ''', (reminder_id,))
                
                conn.commit()
                return cursor.rowcount > 0
    
    def get_all_pending(self) -> List[Dict]:
        """Get all pending reminders (for display/management)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM reminders
                WHERE status = 'pending'
                ORDER BY trigger_time ASC
            ''')
            
            columns = [col[0] for col in cursor.description]
            reminders = []
            
            for row in cursor.fetchall():
                reminder = dict(zip(columns, row))
                if reminder['metadata']:
                    reminder['metadata'] = json.loads(reminder['metadata'])
                reminders.append(reminder)
            
            return reminders
    
    def cleanup_old_reminders(self, days_to_keep: int = 7):
        """
        Remove triggered/cancelled reminders older than specified days
        
        Args:
            days_to_keep: Number of days to keep old reminders
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cutoff_date = datetime.now().timestamp() - (days_to_keep * 86400)
                cutoff_iso = datetime.fromtimestamp(cutoff_date).isoformat()
                
                cursor.execute('''
                    DELETE FROM reminders
                    WHERE status IN ('triggered', 'cancelled')
                    AND created_time < ?
                ''', (cutoff_iso,))
                
                conn.commit()
                return cursor.rowcount