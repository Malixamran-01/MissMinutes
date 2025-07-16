# Quick Start Guide

Get your Discord Task Management Bot running in 5 minutes!

## Prerequisites
- Docker and Docker Compose installed
- Discord bot token
- Discord server (guild) ID

## Step 1: Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" → Enter name → Create
3. Go to "Bot" section → "Add Bot" → Copy the token
4. Go to "OAuth2" → "URL Generator"
5. Select scopes: `bot` and `applications.commands`
6. Select permissions: `Send Messages`, `Use Slash Commands`, `Read Message History`
7. Use generated URL to invite bot to your server

## Step 2: Get Server ID

1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click your server name → "Copy ID"

## Step 3: Deploy Bot

1. **Download and extract the bot files**
2. **Run the setup script:**
   ```bash
   ./setup.sh
   ```
3. **Configure the .env file when prompted:**
   ```env
   DISCORD_TOKEN=your_bot_token_here
   GUILD_ID=your_server_id_here
   TASKS_CHANNEL_ID=your_tasks_channel_id_here
   SUPERVISOR_USER_ID=your_user_id_here
   ```
4. **Press Enter to continue deployment**

## Step 4: Test the Bot

Try these commands in your Discord server:

```
/assign @username "Test Task" "This is a test task" deadline: 2025-07-06 16:00
/my-tasks
/update-task 1 in_progress "Working on it!"
```

## That's it! 🎉

Your bot is now running and will:
- Send reminders after 17 hours
- Notify about deadlines
- Send daily summaries to the supervisor
- Track task progress and user statistics

## Need Help?

- Check logs: `docker-compose logs -f discord-task-bot`
- Read full documentation: `README.md`
- Restart bot: `docker-compose restart discord-task-bot`

## Common Issues

**Bot not responding?**
- Check bot permissions in Discord server
- Verify bot token in .env file
- Ensure bot is online: `docker-compose ps`

**Commands not showing?**
- Wait a few minutes for Discord to sync commands
- Try restarting the bot: `docker-compose restart discord-task-bot`

