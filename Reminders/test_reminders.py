#!/usr/bin/env python3
"""
Test script for the reminder system
Sets a quick timer and shows it working
"""

import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ToolKit.tools.set_reminder import SetReminderTool
from Reminders.reminder_daemon import ReminderDaemon
from Reminders.reminder_db import ReminderDB

def test_reminder_system():
    """Test the complete reminder system"""
    
    print("🧪 Testing Reminder System")
    print("=" * 50)
    
    # Initialize components
    tool = SetReminderTool()
    db = ReminderDB()
    
    # Set a timer for 15 seconds
    print("\n1️⃣ Setting a 15-second timer...")
    result = tool.execute("15 seconds", "Test timer")
    
    if result['success']:
        print(f"   ✅ {result['message']}")
        print(f"   ID: {result['reminder_id']}")
    else:
        print(f"   ❌ Failed: {result.get('error')}")
        return
    
    # Check pending reminders
    print("\n2️⃣ Checking pending reminders in database...")
    pending = db.get_all_pending()
    print(f"   Found {len(pending)} pending reminder(s)")
    for r in pending:
        print(f"   - {r['description']} at {r['trigger_time']}")
    
    # Start the daemon
    print("\n3️⃣ Starting reminder daemon (with 2-second check interval for testing)...")
    daemon = ReminderDaemon(check_interval=2)
    daemon.start()
    
    # Wait for the timer
    print("\n4️⃣ Waiting for timer to trigger...")
    print("   (You should hear TTS in about 15 seconds)")
    
    for i in range(20):
        time.sleep(1)
        remaining = 15 - i
        if remaining > 0:
            print(f"   {remaining} seconds remaining...", end='\r')
    
    print("\n   Timer should have triggered!")
    
    # Check if it was triggered
    time.sleep(3)  # Give daemon time to process
    pending_after = db.get_all_pending()
    print(f"\n5️⃣ Pending reminders after trigger: {len(pending_after)}")
    
    # Stop the daemon
    print("\n6️⃣ Stopping daemon...")
    daemon.stop()
    
    print("\n✅ Test complete!")
    print("\nNOTE: If you didn't hear TTS, make sure:")
    print("  1. Your Google TTS API key is set")
    print("  2. Your audio output is working")
    print("  3. The TTS queue manager is running")

if __name__ == '__main__':
    test_reminder_system()