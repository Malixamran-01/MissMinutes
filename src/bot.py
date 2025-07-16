import discord
from discord.ext import commands, tasks
import os
import asyncio
from datetime import datetime, timedelta
from dateutil import parser
import pytz
from dotenv import load_dotenv
import logging
from database import Database
# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot configuration
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID', 0))
TASKS_CHANNEL_ID = int(os.getenv('TASKS_CHANNEL_ID', 0))
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/tasks.db')
REMINDER_HOURS = int(os.getenv('REMINDER_HOURS', 17))
DAILY_SUMMARY_TIME = os.getenv('DAILY_SUMMARY_TIME', '21:00')
TIMEZONE = os.getenv('TIMEZONE', 'UTC')
SUPERVISOR_USER_ID = int(os.getenv('SUPERVISOR_USER_ID', 0))

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
db = Database(DATABASE_PATH)

async def get_tasks_channel():
    """Get the tasks channel for notifications"""
    if not TASKS_CHANNEL_ID:
        logger.warning("TASKS_CHANNEL_ID not configured")
        return None
    
    channel = bot.get_channel(TASKS_CHANNEL_ID)
    if not channel:
        logger.error(f"Tasks channel {TASKS_CHANNEL_ID} not found")
        return None
    
    return channel

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    
    # Initialize database
    await db.init_db()
    logger.info('Database initialized')
    
    # Start background tasks
    reminder_checker.start()
    deadline_checker.start()
    daily_summary.start()
    
    # Wait a bit to ensure slash commands are registered
    await asyncio.sleep(1)

    # Sync slash commands (guild-specific for fast updates, global otherwise)
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            # Optional: copy global to guild to force registration
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f'Synced {len(synced)} commands to guild {GUILD_ID}')
        else:
            synced = await bot.tree.sync()
            logger.info(f'Synced {len(synced)} commands globally')
    except Exception as e:
        logger.error(f'Failed to sync commands: {e}')

@bot.tree.command(name="assign", description="Assign a task to a team member")
async def assign_task(
    interaction: discord.Interaction,
    member: discord.Member,
    title: str,
    description: str,
    deadline: str,
    priority: str = "medium"
):
    """Assign a task to a team member"""
    try:
        # Parse deadline
        try:
            deadline_dt = parser.parse(deadline)
            # If no timezone info, assume it's in the configured timezone
            if deadline_dt.tzinfo is None:
                tz = pytz.timezone(TIMEZONE)
                deadline_dt = tz.localize(deadline_dt)
            
            # Convert to UTC for storage
            deadline_dt = deadline_dt.astimezone(pytz.UTC)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Invalid deadline format. Please use format like: `2025-07-06 16:00` or `July 6, 2025 4:00 PM`",
                ephemeral=True
            )
            return
        
        # Validate priority
        valid_priorities = ['low', 'medium', 'high', 'urgent']
        if priority.lower() not in valid_priorities:
            priority = 'medium'
        
        # Check if deadline is in the future
        if deadline_dt <= datetime.now(pytz.UTC):
            await interaction.response.send_message(
                "❌ Deadline must be in the future!",
                ephemeral=True
            )
            return
        
        # Create task in database
        task_id = await db.create_task(
            title=title,
            description=description,
            assigned_to_id=member.id,
            assigned_by_id=interaction.user.id,
            guild_id=interaction.guild.id,
            deadline=deadline_dt,
            priority=priority.lower()
        )
        
        # Create embed for task assignment
        embed = discord.Embed(
            title="✅ Task Assigned",
            description=f"**{title}**",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="Assigned to", value=member.mention, inline=True)
        embed.add_field(name="Assigned by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Priority", value=priority.capitalize(), inline=True)
        embed.add_field(name="Description", value=description, inline=False)
        embed.add_field(name="Deadline", value=f"<t:{int(deadline_dt.timestamp())}:F>", inline=False)
        embed.add_field(name="Task ID", value=f"`{task_id}`", inline=True)
        
        embed.set_footer(text=f"Use /update-task {task_id} to update status")
        
        await interaction.response.send_message(embed=embed)
        
        # Send notification to tasks channel
        tasks_channel = await get_tasks_channel()
        if tasks_channel:
            try:
                channel_embed = discord.Embed(
                    title="📋 New Task Assigned",
                    description=f"{member.mention} has been assigned a new task: **{title}**",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                channel_embed.add_field(name="Description", value=description, inline=False)
                channel_embed.add_field(name="Deadline", value=f"<t:{int(deadline_dt.timestamp())}:F>", inline=False)
                channel_embed.add_field(name="Priority", value=priority.capitalize(), inline=True)
                channel_embed.add_field(name="Assigned by", value=interaction.user.mention, inline=True)
                channel_embed.add_field(name="Task ID", value=f"`{task_id}`", inline=True)
                channel_embed.set_footer(text=f"Use /update-task {task_id} to update status")
                
                await tasks_channel.send(embed=channel_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send message to tasks channel {TASKS_CHANNEL_ID}")
        else:
            logger.warning("Tasks channel not available for notification")
        
        logger.info(f"Task {task_id} assigned to {member.display_name} by {interaction.user.display_name}")
        
    except Exception as e:
        logger.error(f"Error in assign_task: {e}")
        await interaction.response.send_message(
            "❌ An error occurred while assigning the task. Please try again.",
            ephemeral=True
        )

@bot.tree.command(name="update-task", description="Update the status of your task")
async def update_task(
    interaction: discord.Interaction,
    task_id: int,
    status: str,
    note: str = None
):
    """Update task status"""
    try:
        # Get task from database
        task = await db.get_task(task_id)
        if not task:
            await interaction.response.send_message(
                "❌ Task not found!",
                ephemeral=True
            )
            return
        
        # Check if user is assigned to this task or is the assigner
        if task['assigned_to_id'] != interaction.user.id and task['assigned_by_id'] != interaction.user.id:
            await interaction.response.send_message(
                "❌ You can only update tasks assigned to you or tasks you assigned!",
                ephemeral=True
            )
            return
        
        # Validate status
        valid_statuses = ['assigned', 'in_progress', 'stuck', 'completed', 'cancelled']
        if status.lower() not in valid_statuses:
            await interaction.response.send_message(
                f"❌ Invalid status. Valid options: {', '.join(valid_statuses)}",
                ephemeral=True
            )
            return
        
        # Update task status
        success = await db.update_task_status(task_id, status.lower(), interaction.user.id, note)
        if not success:
            await interaction.response.send_message(
                "❌ Failed to update task status!",
                ephemeral=True
            )
            return
        
        # Create status update embed
        status_colors = {
            'assigned': discord.Color.blue(),
            'in_progress': discord.Color.orange(),
            'stuck': discord.Color.red(),
            'completed': discord.Color.green(),
            'cancelled': discord.Color.dark_grey()
        }
        
        embed = discord.Embed(
            title="📝 Task Status Updated",
            description=f"**{task['title']}**",
            color=status_colors.get(status.lower(), discord.Color.blue()),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="Task ID", value=f"`{task_id}`", inline=True)
        embed.add_field(name="New Status", value=status.capitalize(), inline=True)
        embed.add_field(name="Updated by", value=interaction.user.mention, inline=True)
        
        if note:
            embed.add_field(name="Note", value=note, inline=False)
        
        await interaction.response.send_message(embed=embed)
        
        # Update user stats if completed
        if status.lower() == 'completed':
            await db.update_user_stats(task['assigned_to_id'], task['guild_id'], completed=True, karma=10)
        
        logger.info(f"Task {task_id} status updated to {status} by {interaction.user.display_name}")
        
    except Exception as e:
        logger.error(f"Error in update_task: {e}")
        await interaction.response.send_message(
            "❌ An error occurred while updating the task. Please try again.",
            ephemeral=True
        )

@bot.tree.command(name="my-tasks", description="View your assigned tasks")
async def my_tasks(interaction: discord.Interaction, status: str = None):
    """View user's tasks"""
    try:
        tasks = await db.get_user_tasks(interaction.user.id, interaction.guild.id, status)
        
        if not tasks:
            status_text = f" with status '{status}'" if status else ""
            await interaction.response.send_message(
                f"📋 You have no tasks{status_text}!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"📋 Your Tasks{f' ({status})' if status else ''}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        for task in tasks[:10]:  # Limit to 10 tasks to avoid embed limits
            deadline_ts = int(datetime.fromisoformat(task['deadline'].replace('Z', '+00:00')).timestamp())
            status_emoji = {
                'assigned': '🆕',
                'in_progress': '🔄',
                'stuck': '🚫',
                'completed': '✅',
                'cancelled': '❌'
            }.get(task['status'], '📋')
            
            embed.add_field(
                name=f"{status_emoji} {task['title']} (ID: {task['id']})",
                value=f"**Status:** {task['status'].replace('_', ' ').title()}\n"
                      f"**Deadline:** <t:{deadline_ts}:R>\n"
                      f"**Priority:** {task['priority'].capitalize()}",
                inline=False
            )
        
        if len(tasks) > 10:
            embed.set_footer(text=f"Showing 10 of {len(tasks)} tasks")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Error in my_tasks: {e}")
        await interaction.response.send_message(
            "❌ An error occurred while fetching your tasks. Please try again.",
            ephemeral=True
        )

@bot.tree.command(name="all-tasks", description="View all tasks assigned in the server")
async def all_tasks(interaction: discord.Interaction, status: str = None):
    """View all tasks for the current guild"""
    try:
        # Get tasks from DB
        tasks = await db.get_all_tasks(interaction.guild.id, status)
        
        if not tasks:
            await interaction.response.send_message(
                f"📋 No tasks found{f' with status {status}' if status else ''} in this server!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📚 All Tasks in {interaction.guild.name}{f' ({status})' if status else ''}",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )

        for task in tasks[:10]:  # Limit to first 10 for Discord embed field limit
            deadline_dt = datetime.fromisoformat(task['deadline'].replace('Z', '+00:00'))
            deadline_ts = int(deadline_dt.timestamp())
            now = datetime.utcnow().replace(tzinfo=pytz.UTC)

            # Time left or overdue
            if deadline_dt > now:
                time_left = f"<t:{deadline_ts}:R>"  # e.g., "in 2 hours"
            else:
                time_left = f"⏰ **Overdue** (<t:{deadline_ts}:R>)"

            # Get Discord user
            user = interaction.guild.get_member(task['assigned_to_id'])
            assignee = user.mention if user else f"<@{task['assigned_to_id']}>"

            status_emoji = {
                'assigned': '🆕',
                'in_progress': '🔄',
                'stuck': '🚫',
                'completed': '✅',
                'cancelled': '❌'
            }.get(task['status'], '📋')

            embed.add_field(
                name=f"{status_emoji} {task['title']} (ID: {task['id']})",
                value=(
                    f"**Assigned to:** {assignee}\n"
                    f"**Status:** {task['status'].replace('_', ' ').title()}\n"
                    f"**Deadline:** <t:{deadline_ts}:F> ({time_left})\n"
                    f"**Priority:** {task['priority'].capitalize()}"
                ),
                inline=False
            )

        if len(tasks) > 10:
            embed.set_footer(text=f"Showing 10 of {len(tasks)} tasks")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Error in all_tasks: {e}")
        await interaction.response.send_message(
            "❌ An error occurred while fetching all tasks.",
            ephemeral=True
        )

# Optional: You can define the command descriptions here
commands_info = {
    "/assign": "Assign a task to a team member.",
    "/deadline": "Set a deadline for a task.",
    "/reminder": "Set a reminder 17 hours before the deadline.",
    "/status": "Check the status of assigned tasks.",
    "/all-tasks": "Show all current tasks and assignees.",
    "/help": "Show this help message with all commands.",
}

# Slash help command
@bot.tree.command(name="help", description="List all available commands and their usage.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛠 Available Bot Commands",
        description="Here's a list of commands you can use:",
        color=discord.Color.green()
    )

    for cmd, desc in commands_info.items():
        embed.add_field(name=cmd, value=desc, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tasks.loop(minutes=30)
async def reminder_checker():
    """Check for tasks that need reminders"""
    try:
        tasks = await db.get_tasks_for_reminder(REMINDER_HOURS)
        tasks_channel = await get_tasks_channel()
        
        if not tasks_channel:
            logger.warning("Tasks channel not available for reminders")
            return
        
        for task in tasks:
            try:
                # Get user and send reminder to tasks channel
                user = bot.get_user(task['assigned_to_id'])
                if user:
                    embed = discord.Embed(
                        title="⏰ Task Reminder",
                        description=f"{user.mention}, it's been {REMINDER_HOURS} hours since you were assigned: **{task['title']}**",
                        color=discord.Color.orange(),
                        timestamp=datetime.now()
                    )
                    
                    deadline_ts = int(datetime.fromisoformat(task['deadline'].replace('Z', '+00:00')).timestamp())
                    embed.add_field(name="Deadline", value=f"<t:{deadline_ts}:R>", inline=True)
                    embed.add_field(name="Priority", value=task['priority'].capitalize(), inline=True)
                    embed.add_field(name="Task ID", value=f"`{task['id']}`", inline=True)
                    embed.add_field(name="Description", value=task['description'], inline=False)
                    embed.set_footer(text=f"Use /update-task {task['id']} to provide an update")
                    
                    await tasks_channel.send(embed=embed)
                    await db.mark_reminder_sent(task['id'])
                    logger.info(f"Reminder sent for task {task['id']} to tasks channel")
                
            except Exception as e:
                logger.error(f"Error sending reminder for task {task['id']}: {e}")
                
    except Exception as e:
        logger.error(f"Error in reminder_checker: {e}")

@tasks.loop(minutes=15)
async def deadline_checker():
    """Check for overdue tasks"""
    try:
        tasks = await db.get_overdue_tasks()
        tasks_channel = await get_tasks_channel()
        
        if not tasks_channel:
            logger.warning("Tasks channel not available for deadline notifications")
            return
        
        for task in tasks:
            try:
                # Get user and send deadline notification to tasks channel
                user = bot.get_user(task['assigned_to_id'])
                if user:
                    embed = discord.Embed(
                        title="🚨 Task Deadline Reached",
                        description=f"{user.mention}, the deadline for **{task['title']}** has passed!",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    
                    deadline_ts = int(datetime.fromisoformat(task['deadline'].replace('Z', '+00:00')).timestamp())
                    embed.add_field(name="Deadline was", value=f"<t:{deadline_ts}:R>", inline=True)
                    embed.add_field(name="Priority", value=task['priority'].capitalize(), inline=True)
                    embed.add_field(name="Task ID", value=f"`{task['id']}`", inline=True)
                    embed.add_field(name="Description", value=task['description'], inline=False)
                    embed.set_footer(text=f"Please update status: /update-task {task['id']} completed")
                    
                    await tasks_channel.send(embed=embed)
                    await db.mark_deadline_notified(task['id'])
                    
                    # Update user stats for overdue task
                    await db.update_user_stats(task['assigned_to_id'], task['guild_id'], overdue=True, karma=-5)
                    
                    logger.info(f"Deadline notification sent for task {task['id']} to tasks channel")
                
            except Exception as e:
                logger.error(f"Error sending deadline notification for task {task['id']}: {e}")
                
    except Exception as e:
        logger.error(f"Error in deadline_checker: {e}")

@tasks.loop(hours=24)
async def daily_summary():
    """Send daily summary to tasks channel"""
    try:
        # Check if it's the right time for daily summary
        now = datetime.now(pytz.timezone(TIMEZONE))
        summary_time = datetime.strptime(DAILY_SUMMARY_TIME, '%H:%M').time()
        
        if now.time().hour != summary_time.hour:
            return
        
        tasks_channel = await get_tasks_channel()
        if not tasks_channel:
            logger.warning("Tasks channel not available for daily summary")
            return
        
        # Get summary data for each guild the bot is in
        for guild in bot.guilds:
            summary = await db.get_daily_summary(guild.id)
            
            embed = discord.Embed(
                title=f"📊 Daily Summary - {guild.name}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📋 Tasks Assigned Today",
                value=str(summary['tasks_assigned_today']),
                inline=True
            )
            embed.add_field(
                name="⏰ Tasks Due Tomorrow",
                value=str(summary['tasks_due_tomorrow']),
                inline=True
            )
            embed.add_field(
                name="🚨 Overdue Tasks",
                value=str(summary['overdue_tasks']),
                inline=True
            )
            
            if summary['recent_updates']:
                updates_text = ""
                for update in summary['recent_updates'][:5]:
                    user = bot.get_user(update['assigned_to_id'])
                    user_name = user.mention if user else "Unknown User"
                    updates_text += f"• **{update['title']}** - {update['status']} ({user_name})\n"
                
                embed.add_field(
                    name="📝 Recent Updates",
                    value=updates_text or "No updates today",
                    inline=False
                )
            
            # Mention supervisor if configured
            if SUPERVISOR_USER_ID:
                supervisor = bot.get_user(SUPERVISOR_USER_ID)
                if supervisor:
                    embed.set_footer(text=f"Daily report for {supervisor.display_name}")
                    await tasks_channel.send(f"{supervisor.mention}", embed=embed)
                else:
                    await tasks_channel.send(embed=embed)
            else:
                await tasks_channel.send(embed=embed)
            
            logger.info(f"Daily summary sent to tasks channel for guild {guild.name}")
            
    except Exception as e:
        logger.error(f"Error in daily_summary: {e}")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    logger.error(f"Command error: {error}")

@bot.event
async def on_application_command_error(interaction, error):
    logger.error(f"Slash command error: {error}")
    if not interaction.response.is_done():
        await interaction.response.send_message(
            "❌ An error occurred while processing your command.",
            ephemeral=True
        )

if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs('data', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    if not TOKEN:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        exit(1)
    
    bot.run(TOKEN)

