#!/usr/bin/env python3
"""
MongoDB Atlas Connection Diagnostic Tool

This script helps diagnose and fix MongoDB Atlas SSL/TLS connection issues.
Run this script to test your MongoDB connection and get specific fixes.
"""

import os
import sys
import ssl
import socket
import subprocess
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

def print_header(text):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f"🔍 {text}")
    print('='*60)

def check_python_version():
    """Check Python version compatibility"""
    print_header("Python Version Check")
    version = sys.version_info
    print(f"Python Version: {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 6):
        print("❌ Python 3.6+ required for MongoDB Atlas")
        return False

    print("✅ Python version compatible")
    return True

def check_ssl_version():
    """Check SSL/TLS version"""
    print_header("SSL/TLS Version Check")
    try:
        print(f"OpenSSL Version: {ssl.OPENSSL_VERSION}")

        # Test TLS versions
        context = ssl.create_default_context()
        if hasattr(ssl, 'TLSVersion'):
            print("✅ TLS 1.2/1.3 support available")
        else:
            print("⚠️ Limited TLS support - may cause issues")

        return True
    except Exception as e:
        print(f"❌ SSL check failed: {e}")
        return False

def check_network_connectivity():
    """Check basic network connectivity"""
    print_header("Network Connectivity Check")

    hosts = [
        "ac-hgckqvc-shard-00-00.pbdewtt.mongodb.net",
        "ac-hgckqvc-shard-00-01.pbdewtt.mongodb.net",
        "ac-hgckqvc-shard-00-02.pbdewtt.mongodb.net"
    ]

    success_count = 0
    for host in hosts:
        try:
            # Test DNS resolution
            ip = socket.gethostbyname(host)
            print(f"✅ {host} → {ip}")

            # Test basic connectivity (TCP handshake)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip, 27017))
            sock.close()

            if result == 0:
                print(f"   ✅ Port 27017 accessible")
                success_count += 1
            else:
                print(f"   ❌ Port 27017 blocked (firewall?)")

        except socket.gaierror:
            print(f"❌ {host} - DNS resolution failed")
        except Exception as e:
            print(f"❌ {host} - Connection failed: {e}")

    if success_count == len(hosts):
        print("✅ All MongoDB hosts reachable")
        return True
    else:
        print(f"⚠️ Only {success_count}/{len(hosts)} hosts reachable")
        return success_count > 0

def check_certificates():
    """Check SSL certificate configuration"""
    print_header("SSL Certificate Check")

    try:
        import certifi
        cert_file = certifi.where()

        if os.path.exists(cert_file):
            print(f"✅ Certifi certificates available: {cert_file}")
            return True
        else:
            print("❌ Certifi certificates not found")
            return False

    except ImportError:
        print("❌ certifi package not installed")
        print("   Install with: pip install certifi")
        return False

def test_mongodb_connection():
    """Test actual MongoDB connection"""
    print_header("MongoDB Connection Test")

    try:
        from mongodb import connect_mongodb
        result = connect_mongodb()
        return result
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def generate_fixes():
    """Generate specific fixes based on diagnostics"""
    print_header("RECOMMENDED FIXES")

    print("1. 🔐 Add IP to MongoDB Atlas Whitelist:")
    print("   - Go to: https://cloud.mongodb.com")
    print("   - Navigate: Network Access → Add IP Address")
    print("   - Add IP: 42.104.157.189")
    print("   - Or add: 0.0.0.0/0 (allows all IPs - less secure)")
    print()

    print("2. 🛡️ Check Windows Firewall:")
    print("   - Open Windows Defender Firewall")
    print("   - Allow outbound connections on port 27017")
    print("   - Or temporarily disable firewall for testing")
    print()

    print("3. 🌐 Disable VPN/Proxy:")
    print("   - Disconnect from VPN")
    print("   - Disable proxy settings in Windows")
    print("   - Test connection without VPN/proxy")
    print()

    print("4. 🔒 Update SSL Certificates:")
    print("   - Run: certlm.msc")
    print("   - Check Trusted Root Certification Authorities")
    print("   - Remove expired certificates if found")
    print()

    print("5. 🐍 Alternative: Use MongoDB Compass")
    print("   - Download from: https://www.mongodb.com/try/download/compass")
    print("   - Use connection string: mongodb+srv://admin:iamtheadmin@tonystark.pbdewtt.mongodb.net/?appName=tonystark")
    print("   - If Compass works, the issue is Python-specific")
    print()

    print("6. 💻 Try Different Network:")
    print("   - Test on different WiFi network")
    print("   - Use mobile hotspot")
    print("   - Test from different location")
    print()

def main():
    """Run all diagnostic checks"""
    print("🔧 MongoDB Atlas Connection Diagnostic Tool")
    print("This tool will help identify and fix SSL/TLS connection issues")
    print()

    # Run all checks
    checks = [
        ("Python Version", check_python_version),
        ("SSL/TLS Support", check_ssl_version),
        ("Network Connectivity", check_network_connectivity),
        ("SSL Certificates", check_certificates),
        ("MongoDB Connection", test_mongodb_connection),
    ]

    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"❌ {name} check failed: {e}")
            results[name] = False

    # Generate summary
    print_header("DIAGNOSTIC SUMMARY")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    print(f"Checks Passed: {passed}/{total}")

    if passed == total:
        print("✅ All checks passed - MongoDB should work!")
    else:
        print("⚠️ Some checks failed - see fixes below")

    # Show results
    for name, result in results.items():
        status = "✅" if result else "❌"
        print(f"   {status} {name}")

    # Generate fixes if needed
    if passed < total:
        generate_fixes()

    print_header("NEXT STEPS")
    print("1. Apply the recommended fixes above")
    print("2. Run this script again to verify fixes")
    print("3. If issues persist, try MongoDB Compass for comparison")
    print("4. Check MongoDB Atlas status: https://status.mongodb.com")

if __name__ == "__main__":
    main()