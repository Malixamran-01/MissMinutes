#!/usr/bin/env python3
"""
Deployment verification script for Discord Task Bot
Checks if all files are present and configuration is valid
"""

import os
import sys
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists and report status"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ Missing {description}: {filepath}")
        return False

def check_directory_exists(dirpath, description):
    """Check if a directory exists and report status"""
    if os.path.exists(dirpath) and os.path.isdir(dirpath):
        print(f"✅ {description}: {dirpath}")
        return True
    else:
        print(f"❌ Missing {description}: {dirpath}")
        return False

def verify_env_file():
    """Verify .env file configuration"""
    env_path = ".env"
    if not os.path.exists(env_path):
        print(f"⚠️  .env file not found. Copy .env.example to .env and configure it.")
        return False
    
    print(f"✅ .env file exists")
    
    # Check for required variables
    required_vars = ['DISCORD_TOKEN', 'GUILD_ID']
    missing_vars = []
    
    try:
        with open(env_path, 'r') as f:
            content = f.read()
            for var in required_vars:
                if f"{var}=" not in content or f"{var}=your_" in content:
                    missing_vars.append(var)
        
        if missing_vars:
            print(f"⚠️  Please configure these variables in .env: {', '.join(missing_vars)}")
            return False
        else:
            print("✅ Required environment variables are configured")
            return True
            
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return False

def main():
    """Main verification function"""
    print("🔍 Discord Task Management Bot - Deployment Verification")
    print("=" * 60)
    
    all_good = True
    
    # Check core files
    print("\n📁 Checking core files...")
    core_files = [
        ("src/bot.py", "Main bot script"),
        ("src/database.py", "Database module"),
        ("requirements.txt", "Python dependencies"),
        ("Dockerfile", "Docker configuration"),
        ("docker-compose.yml", "Docker Compose configuration"),
        ("setup.sh", "Setup script"),
        (".env.example", "Environment template")
    ]
    
    for filepath, description in core_files:
        if not check_file_exists(filepath, description):
            all_good = False
    
    # Check directories
    print("\n📂 Checking directories...")
    directories = [
        ("src", "Source code directory"),
        ("data", "Database directory"),
        ("logs", "Logs directory")
    ]
    
    for dirpath, description in directories:
        if not check_directory_exists(dirpath, description):
            all_good = False
    
    # Check documentation
    print("\n📚 Checking documentation...")
    doc_files = [
        ("README.md", "Main documentation"),
        ("QUICKSTART.md", "Quick start guide")
    ]
    
    for filepath, description in doc_files:
        if not check_file_exists(filepath, description):
            all_good = False
    
    # Check environment configuration
    print("\n⚙️  Checking environment configuration...")
    env_ok = verify_env_file()
    if not env_ok:
        all_good = False
    
    # Check script permissions
    print("\n🔐 Checking script permissions...")
    scripts = ["setup.sh", "test_database.py", "verify_deployment.py"]
    for script in scripts:
        if os.path.exists(script):
            if os.access(script, os.X_OK):
                print(f"✅ {script} is executable")
            else:
                print(f"⚠️  {script} is not executable (run: chmod +x {script})")
        else:
            print(f"❌ {script} not found")
            all_good = False
    
    # Final status
    print("\n" + "=" * 60)
    if all_good:
        print("🎉 Deployment verification passed!")
        print("\nYour Discord Task Management Bot is ready for deployment!")
        print("\nNext steps:")
        print("1. Configure .env file with your Discord bot token and server ID")
        print("2. Run: ./setup.sh")
        print("3. Invite bot to your Discord server")
        print("4. Test with /assign command")
        print("\nFor detailed instructions, see README.md or QUICKSTART.md")
    else:
        print("❌ Deployment verification failed!")
        print("\nPlease fix the issues above before deploying.")
    
    return all_good

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

