"""MongoDB connection and utilities"""
import os
import ssl
from pathlib import Path
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env in the repository root or current working directory
dotenv_path = find_dotenv(filename='.env', raise_error_if_not_found=False)
if not dotenv_path:
    dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path)

# certifi is optional but recommended for updated CA certificates
try:
    import certifi
except ImportError:
    certifi = None

MONGODB_URI = os.getenv("MONGODB_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "discord_bot")

# Global MongoDB client and database instances
_mongo_client = None
_mongo_db = None
_mongo_connection_attempted = False
_mongo_collection_warning_printed = False

def connect_mongodb():
    """Initialize MongoDB connection with proper SSL/TLS configuration"""
    global _mongo_client, _mongo_db, _mongo_connection_attempted
    _mongo_connection_attempted = True
    
    if not MONGODB_URI:
        print("⚠️ MONGODB_URI not found in environment variables. Skipping MongoDB connection.")
        return False
    
    try:
        # Comprehensive SSL configuration for MongoDB Atlas
        print("🔍 Attempting MongoDB connection with comprehensive SSL settings...")

        if certifi:
            # Set SSL certificate environment variables when certifi is available
            os.environ['SSL_CERT_FILE'] = certifi.where()
            os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        else:
            print("⚠️ certifi not installed: falling back to system CA certificates")
            ssl_context = ssl.create_default_context()

        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED

        # Force TLS 1.2+ for MongoDB Atlas compatibility
        if hasattr(ssl, 'TLSVersion'):
            try:
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
                ssl_context.maximum_version = ssl.TLSVersion.TLSv1_3
            except AttributeError:
                ssl_context.protocol = ssl.PROTOCOL_TLSv1_2

        ssl_context.options |= ssl.OP_NO_COMPRESSION
        ssl._create_default_https_context = lambda: ssl_context

        _mongo_client = MongoClient(
            MONGODB_URI,
            server_api=ServerApi('1'),
            connectTimeoutMS=15000,
            serverSelectionTimeoutMS=15000,
            socketTimeoutMS=30000,
            maxPoolSize=5,
            minPoolSize=1,
            maxIdleTimeMS=30000,
            retryWrites=True,
            retryReads=True,
            tls=True,
            tlsAllowInvalidCertificates=False,
            tlsAllowInvalidHostnames=False
        )
        
        # Test the connection with timeout
        _mongo_client.admin.command('ping')
        _mongo_db = _mongo_client[MONGO_DB_NAME]
        
        print("✅ MongoDB Connection Successful")
        print(f"📦 Connected to database: {MONGO_DB_NAME}")
        print(f"🔒 SSL/TLS: Configured with certifi certificates")
        return True
    except Exception as e:
        print(f"❌ MongoDB Connection Failed: {e}")
        print("\n🔧 TROUBLESHOOTING STEPS:")
        print("1. Check MongoDB Atlas IP Whitelist:")
        print("   - Go to MongoDB Atlas dashboard")
        print("   - Network Access → Add IP Address")
        print("   - Add your current IP or '0.0.0.0/0' for testing")
        print()
        print("2. Check Firewall/Antivirus:")
        print("   - Ensure outbound connections to port 27017 are allowed")
        print("   - Disable VPN/proxy temporarily for testing")
        print()
        print("3. Update Windows SSL Certificates:")
        print("   - Run: certlm.msc → Trusted Root Certification Authorities")
        print("   - Check for expired certificates")
        print()
        print("4. Test Network Connectivity:")
        print("   - Try: telnet ac-hgckqvc-shard-00-00.pbdewtt.mongodb.net 27017")
        print()
        print("5. Alternative: Use MongoDB Compass or Studio 3T to test connection")
        if not certifi:
            print("\n⚠️ Optional package 'certifi' is missing. Install it with: pip install certifi")
        return False

def get_database():
    """Get the MongoDB database instance"""
    global _mongo_db, _mongo_connection_attempted
    if _mongo_db is None and not _mongo_connection_attempted:
        connect_mongodb()
    return _mongo_db

def get_collection(collection_name):
    """Get a MongoDB collection"""
    global _mongo_collection_warning_printed
    db = get_database()
    if db is None:
        if not _mongo_collection_warning_printed:
            print("⚠️ MongoDB is not connected. Collection access will be skipped until connection is available.")
            _mongo_collection_warning_printed = True
        return None
    return db[collection_name]

def insert_document(collection_name, document):
    """Insert a document into a collection"""
    try:
        collection = get_collection(collection_name)
        if collection is None:
            return None
        result = collection.insert_one(document)
        return result.inserted_id
    except Exception as e:
        print(f"Error inserting document: {e}")
        return None

def find_document(collection_name, query):
    """Find a single document"""
    try:
        collection = get_collection(collection_name)
        if collection is None:
            return None
        return collection.find_one(query)
    except Exception as e:
        print(f"Error finding document: {e}")
        return None

def find_documents(collection_name, query=None, limit=100):
    """Find multiple documents"""
    try:
        collection = get_collection(collection_name)
        if collection is None:
            return []
        if query is None:
            query = {}
        return list(collection.find(query).limit(limit))
    except Exception as e:
        print(f"Error finding documents: {e}")
        return []

def update_document(collection_name, query, update_data):
    """Update a document"""
    try:
        collection = get_collection(collection_name)
        if collection is None:
            return 0
        result = collection.update_one(query, {"$set": update_data})
        return result.modified_count
    except Exception as e:
        print(f"Error updating document: {e}")
        return 0

def delete_document(collection_name, query):
    """Delete a document"""
    try:
        collection = get_collection(collection_name)
        if collection is None:
            return 0
        result = collection.delete_one(query)
        return result.deleted_count
    except Exception as e:
        print(f"Error deleting document: {e}")
        return 0

def create_index(collection_name, field, unique=False):
    """Create an index on a collection"""
    try:
        collection = get_collection(collection_name)
        if collection is None:
            return False
        collection.create_index(field, unique=unique)
        return True
    except Exception as e:
        print(f"Error creating index: {e}")
        return False

def close_mongodb():
    """Close MongoDB connection"""
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()