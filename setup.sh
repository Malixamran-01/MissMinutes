#!/bin/bash

# Discord Task Management Bot Setup Script
# This script helps you set up and deploy the Discord bot

set -e

echo "🤖 Discord Task Management Bot Setup"
echo "===================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Please edit the .env file with your Discord bot configuration:"
    echo "   - DISCORD_TOKEN: Your Discord bot token"
    echo "   - GUILD_ID: Your Discord server ID"
    echo "   - SUPERVISOR_USER_ID: Supervisor's Discord user ID (optional)"
    echo ""
    read -p "Press Enter after you've configured the .env file..."
else
    echo "✅ .env file already exists"
fi

# Validate required environment variables
echo "🔍 Validating configuration..."

if ! grep -q "DISCORD_TOKEN=.*[^[:space:]]" .env; then
    echo "❌ DISCORD_TOKEN is not set in .env file"
    exit 1
fi

if ! grep -q "GUILD_ID=.*[^[:space:]]" .env; then
    echo "❌ GUILD_ID is not set in .env file"
    exit 1
fi

if ! grep -q "TASKS_CHANNEL_ID=.*[^[:space:]]" .env; then
    echo "❌ TASKS_CHANNEL_ID is not set in .env file"
    exit 1
fi

echo "✅ Configuration validated"

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data logs
echo "✅ Directories created"

# Build and start the bot
echo "🏗️  Building Docker image..."
docker-compose build

echo "🚀 Starting the bot..."
docker-compose up -d

echo ""
echo "✅ Bot deployment completed!"
echo ""
echo "📊 Status:"
docker-compose ps

echo ""
echo "📋 Next steps:"
echo "1. Check bot logs: docker-compose logs -f discord-task-bot"
echo "2. Invite the bot to your Discord server using the OAuth2 URL"
echo "3. Test the bot with /assign command"
echo ""
echo "🔧 Management commands:"
echo "- View logs: docker-compose logs -f discord-task-bot"
echo "- Stop bot: docker-compose down"
echo "- Restart bot: docker-compose restart discord-task-bot"
echo "- Update bot: docker-compose down && docker-compose build && docker-compose up -d"
echo ""
echo "📚 For detailed documentation, see README.md"

