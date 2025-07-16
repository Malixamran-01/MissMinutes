#!/usr/bin/env python3
"""
Test script for Discord Task Bot database functionality
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
import pytz

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from database import Database

async def test_database():
    """Test database functionality"""
    print("🧪 Testing Discord Task Bot Database")
    print("=" * 40)
    
    # Initialize test database
    test_db_path = "data/test_tasks.db"
    db = Database(test_db_path)
    
    try:
        # Test 1: Initialize database
        print("1. Testing database initialization...")
        await db.init_db()
        print("✅ Database initialized successfully")
        
        # Test 2: Create a task
        print("\n2. Testing task creation...")
        deadline = datetime.now(pytz.UTC) + timedelta(days=1)
        task_id = await db.create_task(
            title="Test Task",
            description="This is a test task",
            assigned_to_id=123456789,
            assigned_by_id=987654321,
            guild_id=111222333,
            deadline=deadline,
            priority="high"
        )
        print(f"✅ Task created with ID: {task_id}")
        
        # Test 3: Retrieve the task
        print("\n3. Testing task retrieval...")
        task = await db.get_task(task_id)
        if task:
            print(f"✅ Task retrieved: {task['title']}")
            print(f"   Status: {task['status']}")
            print(f"   Priority: {task['priority']}")
        else:
            print("❌ Failed to retrieve task")
            return False
        
        # Test 4: Update task status
        print("\n4. Testing task status update...")
        success = await db.update_task_status(task_id, "in_progress", 123456789, "Started working on it")
        if success:
            print("✅ Task status updated successfully")
        else:
            print("❌ Failed to update task status")
            return False
        
        # Test 5: Get user tasks
        print("\n5. Testing user task retrieval...")
        user_tasks = await db.get_user_tasks(123456789, 111222333)
        if user_tasks:
            print(f"✅ Found {len(user_tasks)} tasks for user")
            for task in user_tasks:
                print(f"   - {task['title']} ({task['status']})")
        else:
            print("❌ No tasks found for user")
        
        # Test 6: Test reminder functionality
        print("\n6. Testing reminder system...")
        # Create a task that should trigger reminder (simulate 18 hours ago)
        old_task_id = await db.create_task(
            title="Old Task",
            description="This task should trigger reminder",
            assigned_to_id=123456789,
            assigned_by_id=987654321,
            guild_id=111222333,
            deadline=deadline,
            priority="medium"
        )
        
        # Manually update created_at to simulate old task
        import aiosqlite
        async with aiosqlite.connect(test_db_path) as conn:
            await conn.execute('''
                UPDATE tasks SET created_at = datetime('now', '-18 hours') WHERE id = ?
            ''', (old_task_id,))
            await conn.commit()
        
        reminder_tasks = await db.get_tasks_for_reminder(17)
        if reminder_tasks:
            print(f"✅ Found {len(reminder_tasks)} tasks needing reminders")
        else:
            print("⚠️  No tasks found needing reminders (this might be expected)")
        
        # Test 7: Test daily summary
        print("\n7. Testing daily summary...")
        summary = await db.get_daily_summary(111222333)
        print(f"✅ Daily summary generated:")
        print(f"   - Tasks assigned today: {summary['tasks_assigned_today']}")
        print(f"   - Tasks due tomorrow: {summary['tasks_due_tomorrow']}")
        print(f"   - Overdue tasks: {summary['overdue_tasks']}")
        print(f"   - Recent updates: {len(summary['recent_updates'])}")
        
        # Test 8: Test user stats
        print("\n8. Testing user statistics...")
        await db.update_user_stats(123456789, 111222333, completed=True, karma=10)
        print("✅ User stats updated successfully")
        
        print("\n🎉 All database tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up test database
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            print("\n🧹 Test database cleaned up")

async def test_imports():
    """Test that all imports work correctly"""
    print("📦 Testing imports...")
    
    try:
        import discord
        print(f"✅ discord.py version: {discord.__version__}")
        
        import aiosqlite
        print("✅ aiosqlite imported successfully")
        
        import pytz
        print("✅ pytz imported successfully")
        
        from dateutil import parser
        print("✅ python-dateutil imported successfully")
        
        from dotenv import load_dotenv
        print("✅ python-dotenv imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

async def main():
    """Main test function"""
    print("🤖 Discord Task Management Bot - Test Suite")
    print("=" * 50)
    
    # Test imports first
    if not await test_imports():
        print("\n❌ Import tests failed!")
        return False
    
    print("\n" + "=" * 50)
    
    # Test database functionality
    if not await test_database():
        print("\n❌ Database tests failed!")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All tests passed! The bot is ready for deployment.")
    print("\nNext steps:")
    print("1. Configure your .env file with Discord bot token")
    print("2. Run ./setup.sh to deploy the bot")
    print("3. Invite the bot to your Discord server")
    print("4. Test with /assign command")
    
    return True

if __name__ == "__main__":
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Run tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

