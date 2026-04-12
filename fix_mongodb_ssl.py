#!/usr/bin/env python3
"""
MongoDB Atlas SSL Fix Script

This script applies various SSL/TLS fixes to resolve MongoDB Atlas connection issues.
Run this before starting your Discord bot.
"""

import os
import ssl
import sys
import subprocess

def apply_ssl_fixes():
    """Apply comprehensive SSL fixes for MongoDB Atlas"""

    print("🔧 Applying MongoDB Atlas SSL Fixes...")

    # Fix 1: Update SSL certificates
    try:
        import certifi
        cert_file = certifi.where()
        os.environ['SSL_CERT_FILE'] = cert_file
        os.environ['REQUESTS_CA_BUNDLE'] = cert_file
        print(f"✅ SSL certificates updated: {cert_file}")
    except ImportError:
        print("❌ certifi not installed. Install with: pip install certifi")
        return False

    # Fix 2: Configure SSL context
    try:
        # Create SSL context with MongoDB Atlas compatibility
        ssl_context = ssl.create_default_context(cafile=cert_file)
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED

        # Force TLS 1.2+ (required by MongoDB Atlas)
        if hasattr(ssl, 'TLSVersion'):
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.maximum_version = ssl.TLSVersion.TLSv1_3

        # Disable compression (can cause handshake issues)
        ssl_context.options |= ssl.OP_NO_COMPRESSION

        # Apply globally
        ssl._create_default_https_context = lambda: ssl_context
        print("✅ SSL context configured for MongoDB Atlas")
    except Exception as e:
        print(f"❌ SSL context configuration failed: {e}")
        return False

    # Fix 3: Update Windows certificate store (if possible)
    try:
        # Try to update Windows certificates
        result = subprocess.run(
            ['certutil', '-generateSSTFromWU', 'roots.sst'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("✅ Windows certificate store updated")
        else:
            print("⚠️ Windows certificate update skipped (may not be needed)")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("⚠️ Windows certificate update not available")

    print("🎉 SSL fixes applied successfully!")
    print("\n📋 NEXT STEPS:")
    print("1. Go to https://cloud.mongodb.com")
    print("2. Network Access → Add IP Address")
    print("3. Add your IP: 42.104.157.189")
    print("4. Or add: 0.0.0.0/0 (for testing)")
    print("5. Run your Discord bot: python reconcile_bot.py")

    return True

def test_connection():
    """Test MongoDB connection after fixes"""
    print("\n🧪 Testing MongoDB connection...")

    try:
        from mongodb import connect_mongodb
        result = connect_mongodb()
        if result:
            print("✅ MongoDB connection successful!")
            return True
        else:
            print("❌ MongoDB connection still failing")
            return False
    except Exception as e:
        print(f"❌ Connection test error: {e}")
        return False

if __name__ == "__main__":
    print("🔧 MongoDB Atlas SSL Fix Script")
    print("=" * 50)

    # Apply fixes
    if apply_ssl_fixes():
        # Test connection
        test_connection()
    else:
        print("❌ Failed to apply SSL fixes")
        sys.exit(1)