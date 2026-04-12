#!/usr/bin/env python3
"""
Quick MongoDB Connection Test

Run this after adding your IP to MongoDB Atlas whitelist.
"""

from mongodb import connect_mongodb

def main():
    print("🧪 Testing MongoDB Atlas Connection...")
    print("Make sure you've added your IP (42.104.157.189) to MongoDB Atlas whitelist!")
    print()

    result = connect_mongodb()

    if result:
        print("\n🎉 SUCCESS! MongoDB is connected.")
        print("Your Discord bot should now work with full MongoDB support!")
        print("\nNext step: python reconcile_bot.py")
    else:
        print("\n❌ Still failing. Check:")
        print("• IP whitelist in MongoDB Atlas")
        print("• Wait 1-2 minutes after adding IP")
        print("• Try adding 0.0.0.0/0 temporarily")
        print("• Check MongoDB Atlas status: https://status.mongodb.com")

if __name__ == "__main__":
    main()