import aiosqlite
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
import os

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    async def init_db(self):
        """Initialize the database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Tasks table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    assigned_to_id INTEGER NOT NULL,
                    assigned_by_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    deadline TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'assigned',
                    priority TEXT DEFAULT 'medium',
                    reminder_sent BOOLEAN DEFAULT FALSE,
                    deadline_notified BOOLEAN DEFAULT FALSE,
                    completed_at TIMESTAMP NULL
                )
            ''')
            
            # Task updates table for tracking progress
            await db.execute('''
                CREATE TABLE IF NOT EXISTS task_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks (id)
                )
            ''')
            
            # User stats table for tracking performance
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    tasks_completed INTEGER DEFAULT 0,
                    tasks_overdue INTEGER DEFAULT 0,
                    karma_points INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await db.commit()
    
    async def create_task(self, title: str, description: str, assigned_to_id: int, 
                         assigned_by_id: int, guild_id: int, deadline: datetime, 
                         priority: str = 'medium') -> int:
        """Create a new task and return its ID"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO tasks (title, description, assigned_to_id, assigned_by_id, 
                                 guild_id, deadline, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (title, description, assigned_to_id, assigned_by_id, guild_id, deadline, priority))
            
            task_id = cursor.lastrowid
            await db.commit()
            return task_id
    
    async def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get a task by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_user_tasks(self, user_id: int, guild_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all tasks for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cursor = await db.execute('''
                    SELECT * FROM tasks 
                    WHERE assigned_to_id = ? AND guild_id = ? AND status = ?
                    ORDER BY deadline ASC
                ''', (user_id, guild_id, status))
            else:
                cursor = await db.execute('''
                    SELECT * FROM tasks 
                    WHERE assigned_to_id = ? AND guild_id = ?
                    ORDER BY deadline ASC
                ''', (user_id, guild_id))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_task_status(self, task_id: int, status: str, user_id: int, note: str = None) -> bool:
        """Update task status and add update record"""
        async with aiosqlite.connect(self.db_path) as db:
            # Update task status
            cursor = await db.execute('''
                UPDATE tasks SET status = ?, completed_at = ?
                WHERE id = ?
            ''', (status, datetime.now() if status == 'completed' else None, task_id))
            
            if cursor.rowcount == 0:
                return False
            
            # Add update record
            await db.execute('''
                INSERT INTO task_updates (task_id, user_id, status, note)
                VALUES (?, ?, ?, ?)
            ''', (task_id, user_id, status, note))
            
            await db.commit()
            return True
    
    async def get_tasks_for_reminder(self, hours_ago: int) -> List[Dict[str, Any]]:
        """Get tasks that need reminders (assigned X hours ago, not reminded yet)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM tasks 
                WHERE reminder_sent = FALSE 
                AND status IN ('assigned', 'in_progress')
                AND datetime(created_at, '+{} hours') <= datetime('now')
            '''.format(hours_ago))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        """Get tasks that are past deadline and not notified"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM tasks 
                WHERE deadline_notified = FALSE 
                AND status NOT IN ('completed', 'cancelled')
                AND deadline <= datetime('now')
            ''')
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def mark_reminder_sent(self, task_id: int):
        """Mark that reminder has been sent for a task"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE tasks SET reminder_sent = TRUE WHERE id = ?
            ''', (task_id,))
            await db.commit()
    
    async def mark_deadline_notified(self, task_id: int):
        """Mark that deadline notification has been sent for a task"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE tasks SET deadline_notified = TRUE WHERE id = ?
            ''', (task_id,))
            await db.commit()
    
    async def get_daily_summary(self, guild_id: int) -> Dict[str, Any]:
        """Get daily summary data for supervisor"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Tasks assigned today
            cursor = await db.execute('''
                SELECT COUNT(*) as count FROM tasks 
                WHERE guild_id = ? AND date(created_at) = date('now')
            ''', (guild_id,))
            tasks_today = (await cursor.fetchone())['count']
            
            # Tasks due tomorrow
            cursor = await db.execute('''
                SELECT COUNT(*) as count FROM tasks 
                WHERE guild_id = ? AND date(deadline) = date('now', '+1 day')
                AND status NOT IN ('completed', 'cancelled')
            ''', (guild_id,))
            tasks_tomorrow = (await cursor.fetchone())['count']
            
            # Overdue tasks
            cursor = await db.execute('''
                SELECT COUNT(*) as count FROM tasks 
                WHERE guild_id = ? AND deadline < datetime('now')
                AND status NOT IN ('completed', 'cancelled')
            ''', (guild_id,))
            overdue_tasks = (await cursor.fetchone())['count']
            
            # Recent updates
            cursor = await db.execute('''
                SELECT t.title, tu.status, tu.note, tu.created_at, t.assigned_to_id
                FROM task_updates tu
                JOIN tasks t ON tu.task_id = t.id
                WHERE t.guild_id = ? AND date(tu.created_at) = date('now')
                ORDER BY tu.created_at DESC
                LIMIT 10
            ''', (guild_id,))
            recent_updates = [dict(row) for row in await cursor.fetchall()]
            
            return {
                'tasks_assigned_today': tasks_today,
                'tasks_due_tomorrow': tasks_tomorrow,
                'overdue_tasks': overdue_tasks,
                'recent_updates': recent_updates
            }
    
    async def update_user_stats(self, user_id: int, guild_id: int, completed: bool = False, overdue: bool = False, karma: int = 0):
        """Update user statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            # Insert or update user stats
            await db.execute('''
                INSERT OR REPLACE INTO user_stats 
                (user_id, guild_id, tasks_completed, tasks_overdue, karma_points, last_updated)
                VALUES (
                    ?, ?, 
                    COALESCE((SELECT tasks_completed FROM user_stats WHERE user_id = ?), 0) + ?,
                    COALESCE((SELECT tasks_overdue FROM user_stats WHERE user_id = ?), 0) + ?,
                    COALESCE((SELECT karma_points FROM user_stats WHERE user_id = ?), 0) + ?,
                    datetime('now')
                )
            ''', (user_id, guild_id, user_id, 1 if completed else 0, 
                  user_id, 1 if overdue else 0, user_id, karma))
            await db.commit()
    
    async def get_all_tasks(self, guild_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all tasks for a guild, optionally filtered by status"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cursor = await db.execute('''
                    SELECT * FROM tasks 
                    WHERE guild_id = ? AND status = ?
                    ORDER BY deadline ASC
                ''', (guild_id, status))
            else:
                cursor = await db.execute('''
                    SELECT * FROM tasks 
                    WHERE guild_id = ?
                    ORDER BY deadline ASC
                ''', (guild_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

