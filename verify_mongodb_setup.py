#!/usr/bin/env python3
"""
MongoDB Atlas Setup Verification Script

This script helps you verify your MongoDB Atlas setup and provides
step-by-step instructions to fix connection issues.
"""

import os
import json
from dotenv import load_dotenv

def check_env_file():
    """Check if .env file exists and has MongoDB credentials"""
    print("🔍 Checking .env file...")

    if not os.path.exists('.env'):
        print("❌ .env file not found")
        return False

    load_dotenv()

    uri = os.getenv('MONGODB_URI')
    db_name = os.getenv('MONGO_DB_NAME')

    if not uri:
        print("❌ MONGODB_URI not found in .env")
        return False

    if not db_name:
        print("⚠️ MONGO_DB_NAME not set, using default 'discord_bot'")

    print("✅ .env file configured")
    print(f"   Database: {db_name or 'discord_bot'}")
    print(f"   URI: {uri[:50]}...")

    return True

def show_atlas_setup_steps():
    """Show step-by-step MongoDB Atlas setup instructions"""
    print("\n" + "="*60)
    print("🚀 MONGODB ATLAS SETUP GUIDE")
    print("="*60)

    print("\n1. 📱 ACCESS MONGODB ATLAS:")
    print("   • Go to: https://cloud.mongodb.com")
    print("   • Login with your account")

    print("\n2. 🌐 ADD IP TO WHITELIST:")
    print("   • Click 'Network Access' in left sidebar")
    print("   • Click 'Add IP Address' button")
    print("   • Add this IP: 42.104.157.189")
    print("   • Description: 'Discord Bot Server'")
    print("   • Click 'Confirm'")

    print("\n3. ⏳ WAIT FOR ACTIVATION:")
    print("   • IP whitelist takes 1-2 minutes to activate")
    print("   • Status will show 'ACTIVE' when ready")

    print("\n4. 🧪 TEST CONNECTION:")
    print("   • Run: python fix_mongodb_ssl.py")
    print("   • Should show: '✅ MongoDB connection successful!'")

    print("\n5. 🤖 START YOUR BOT:")
    print("   • Run: python reconcile_bot.py")
    print("   • Bot should connect to MongoDB successfully")

def show_troubleshooting():
    """Show additional troubleshooting steps"""
    print("\n" + "="*60)
    print("🔧 ADVANCED TROUBLESHOOTING")
    print("="*60)

    print("\n🔍 CHECK ATLAS CLUSTER STATUS:")
    print("   • Visit: https://status.mongodb.com")
    print("   • Ensure no ongoing incidents")

    print("\n🌐 TRY DIFFERENT IP SETTINGS:")
    print("   • Temporarily add: 0.0.0.0/0 (allows all IPs)")
    print("   • Remember to remove this for security!")

    print("\n🖥️ USE MONGODB COMPASS:")
    print("   • Download: https://www.mongodb.com/try/download/compass")
    print("   • Connection string: mongodb+srv://admin:iamtheadmin@tonystark.pbdewtt.mongodb.net/?appName=tonystark")
    print("   • If Compass works, issue is Python-specific")

    print("\n🔄 CHECK YOUR IP AGAIN:")
    print("   • Your IP may change if using dynamic IP")
    print("   • Run: python -c \"import requests; print(requests.get('https://api.ipify.org').text)\"")

def main():
    """Main verification function"""
    print("🔧 MongoDB Atlas Setup Verification")
    print("This script helps you fix MongoDB connection issues")

    # Check environment
    if not check_env_file():
        print("\n❌ Environment not configured properly")
        print("   Create a .env file with your MongoDB Atlas credentials")
        return

    # Show setup steps
    show_atlas_setup_steps()

    # Show troubleshooting
    show_troubleshooting()

    print("\n" + "="*60)
    print("📞 SUPPORT")
    print("="*60)
    print("If you continue having issues:")
    print("• Check MongoDB Atlas documentation")
    print("• Contact MongoDB Atlas support")
    print("• Verify your cluster is not paused")
    print("• Ensure your Atlas account has proper permissions")

if __name__ == "__main__":
    main()