"""MongoDB connection and utilities"""
import os
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "discord_bot")

# Global MongoDB client and database instances
_mongo_client = None
_mongo_db = None

def connect_mongodb():
    """Initialize MongoDB connection"""
    global _mongo_client, _mongo_db
    
    if not MONGODB_URI:
        print("⚠️ MONGODB_URI not found in environment variables. Skipping MongoDB connection.")
        return False
    
    try:
        _mongo_client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
        
        # Test the connection
        _mongo_client.admin.command('ping')
        _mongo_db = _mongo_client[MONGO_DB_NAME]
        
        print("✅ MongoDB Connection Successful")
        print(f"📦 Connected to database: {MONGO_DB_NAME}")
        return True
    except Exception as e:
        print(f"❌ MongoDB Connection Failed: {e}")
        return False

def get_database():
    """Get the MongoDB database instance"""
    global _mongo_db
    if _mongo_db is None:
        connect_mongodb()
    return _mongo_db

def close_mongodb():
    """Close MongoDB connection"""
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        print("✅ MongoDB connection closed")

def get_collection(collection_name):
    """Get a specific collection from the database"""
    db = get_database()
    if db is None:
        return None
    return db[collection_name]

# Helper functions for common operations

def insert_document(collection_name, document):
    """Insert a document into a collection"""
    collection = get_collection(collection_name)
    if collection:
        result = collection.insert_one(document)
        return result.inserted_id
    return None

def find_document(collection_name, query):
    """Find a single document in a collection"""
    collection = get_collection(collection_name)
    if collection:
        return collection.find_one(query)
    return None

def find_documents(collection_name, query=None):
    """Find multiple documents in a collection"""
    collection = get_collection(collection_name)
    if collection:
        if query is None:
            query = {}
        return list(collection.find(query))
    return []

def update_document(collection_name, query, update_data):
    """Update a document in a collection"""
    collection = get_collection(collection_name)
    if collection:
        result = collection.update_one(query, {"$set": update_data})
        return result.modified_count > 0
    return False

def delete_document(collection_name, query):
    """Delete a document from a collection"""
    collection = get_collection(collection_name)
    if collection:
        result = collection.delete_one(query)
        return result.deleted_count > 0
    return False

def clear_collection(collection_name):
    """Clear all documents from a collection"""
    collection = get_collection(collection_name)
    if collection:
        result = collection.delete_many({})
        return result.deleted_count
    return 0

def create_index(collection_name, field_name, unique=False):
    """Create an index on a collection"""
    collection = get_collection(collection_name)
    if collection:
        collection.create_index(field_name, unique=unique)
        return True
    return False
