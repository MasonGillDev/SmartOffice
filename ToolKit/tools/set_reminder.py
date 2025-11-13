"""
Set Reminder Tool
Allows the AI to set timers and reminders with natural language
"""

import os
import sys
from typing import Dict, Any
from datetime import datetime, timedelta
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ToolKit.base_tool import BaseTool
from Reminders.reminder_db import ReminderDB

class SetReminderTool(BaseTool):
    """Tool for setting reminders and timers"""
    
    def __init__(self):
        super().__init__()
        self.db = ReminderDB()
    
    def get_name(self) -> str:
        return "set_reminder"
    
    def get_description(self) -> str:
        return "Set a timer or reminder. Examples: 'timer for 5 minutes', 'remind me at 3pm to call John', 'reminder tomorrow at 10am for meeting'"
    
    def get_tool_type(self):
        return "action"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "What to remind about (e.g., 'take medication', 'timer', 'meeting with John')"
                },
                "time_description": {
                    "type": "string",
                    "description": "When to trigger (e.g., '5 minutes', '2 hours', '3:30 PM', 'tomorrow at 2pm')"
                },
                "type": {
                    "type": "string",
                    "description": "Type: 'timer' for simple timers, 'reminder' for scheduled reminders (auto-detected if not specified)"
                }
            },
            "required": ["time_description"]
        }
    
    def parse_time(self, time_description: str, is_timer: bool = None) -> tuple:
        """
        Parse natural language time descriptions
        
        Returns:
            (datetime, is_timer_bool) - The trigger time and whether this is a timer
        """
        now = datetime.now()
        time_lower = time_description.lower().strip()
        
        # Auto-detect if it's a timer based on keywords
        if is_timer is None:
            timer_keywords = ['timer', 'minute', 'second', 'hour', 'in ']
            is_timer = any(kw in time_lower for kw in timer_keywords)
        
        # Remove "in" prefix if present
        if time_lower.startswith('in '):
            time_lower = time_lower[3:]
        
        # TIMER PATTERNS (relative times)
        timer_patterns = [
            # Seconds
            (r'^(\d+)\s*(?:second|seconds|sec|secs|s)$', 
             lambda m: now + timedelta(seconds=int(m.group(1)))),
            
            # Minutes
            (r'^(\d+)\s*(?:minute|minutes|min|mins|m)$', 
             lambda m: now + timedelta(minutes=int(m.group(1)))),
            
            # Hours
            (r'^(\d+)\s*(?:hour|hours|hr|hrs|h)$', 
             lambda m: now + timedelta(hours=int(m.group(1)))),
            
            # Combined (e.g., "1 hour 30 minutes")
            (r'^(\d+)\s*h(?:our|r)?\s*(\d+)\s*m(?:in|inute)?s?$',
             lambda m: now + timedelta(hours=int(m.group(1)), minutes=int(m.group(2)))),
        ]
        
        # Try timer patterns first
        for pattern, handler in timer_patterns:
            match = re.match(pattern, time_lower)
            if match:
                return handler(match), True
        
        # REMINDER PATTERNS (specific times)
        
        # Handle "tomorrow"
        if 'tomorrow' in time_lower:
            tomorrow = now + timedelta(days=1)
            time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', time_lower)
            
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                period = time_match.group(3)
                
                if period == 'pm' and hour < 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
                
                return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0), False
            else:
                # Tomorrow at 9 AM by default
                return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0), False
        
        # Handle "tonight" (today at 8 PM)
        if 'tonight' in time_lower:
            tonight = now.replace(hour=20, minute=0, second=0, microsecond=0)
            if tonight <= now:
                tonight += timedelta(days=1)
            return tonight, False
        
        # Handle specific times (3 PM, 15:30, 3:30pm)
        time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', time_lower)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            period = time_match.group(3)
            
            # Handle 12-hour format
            if period == 'pm' and hour < 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0
            
            target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If time has passed today, assume tomorrow
            if target_time <= now:
                target_time += timedelta(days=1)
            
            return target_time, False
        
        # Default fallback - 5 minutes from now as a timer
        return now + timedelta(minutes=5), True
    
    def execute(self, time_description: str, description: str = None, type: str = None, **kwargs) -> Dict[str, Any]:
        """Set a reminder or timer"""
        try:
            # Parse the time and auto-detect type
            trigger_time, is_timer = self.parse_time(time_description)
            
            # Determine type if not specified
            if type is None:
                type = 'timer' if is_timer else 'reminder'
            
            # Generate description if not provided
            if not description:
                if type == 'timer':
                    # For timer, describe the duration
                    delta = trigger_time - datetime.now()
                    if delta.total_seconds() < 60:
                        description = f"{int(delta.total_seconds())} second timer"
                    elif delta.total_seconds() < 3600:
                        description = f"{int(delta.total_seconds() / 60)} minute timer"
                    else:
                        description = f"{int(delta.total_seconds() / 3600)} hour timer"
                else:
                    description = "Reminder"
            
            # Create reminder object
            reminder_data = {
                'type': type,
                'description': description,
                'trigger_time': trigger_time.isoformat(),
                'created_time': datetime.now().isoformat(),
                'status': 'pending',
                'priority': 'normal',
                'source': 'voice',
                'metadata': {
                    'original_request': time_description
                }
            }
            
            # Add to database
            reminder_id = self.db.add_reminder(reminder_data)
            
            # Calculate human-readable time
            delta = trigger_time - datetime.now()
            if delta.total_seconds() < 60:
                human_duration = f"{int(delta.total_seconds())} seconds"
            elif delta.total_seconds() < 3600:
                minutes = int(delta.total_seconds() / 60)
                human_duration = f"{minutes} minute{'s' if minutes != 1 else ''}"
            elif delta.total_seconds() < 86400:
                hours = int(delta.total_seconds() / 3600)
                human_duration = f"{hours} hour{'s' if hours != 1 else ''}"
            else:
                days = int(delta.total_seconds() / 86400)
                human_duration = f"{days} day{'s' if days != 1 else ''}"
            
            # Format response based on type
            if type == 'timer':
                message = f"Timer set for {human_duration}"
            else:
                message = f"Reminder set for {human_duration} from now"
                if trigger_time.date() == datetime.now().date():
                    message += f" at {trigger_time.strftime('%I:%M %p')}"
                else:
                    message += f" ({trigger_time.strftime('%b %d at %I:%M %p')})"
            
            return {
                "success": True,
                "reminder_id": reminder_id,
                "type": type,
                "description": description,
                "trigger_time": trigger_time.strftime('%Y-%m-%d %H:%M:%S'),
                "human_time": human_duration,
                "message": message,
                "result": message
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }