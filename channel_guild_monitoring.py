"""Channel-based guild monitoring functions using MongoDB"""

import json
from datetime import datetime
from mongodb import get_collection, insert_document, find_document, update_document, delete_document, find_documents

# MongoDB collection names
CHANNEL_GUILDS = "channel_guilds"
CHANNEL_SNAPSHOTS = "channel_snapshots"
CHANNEL_CHANGES = "channel_changes"
MEMBER_CACHE = "member_cache"
BOT_SETTINGS = "bot_settings"


def init_channel_monitoring_db():
    """Initialize MongoDB collections and indexes (replaces SQLite init)"""
    try:
        # Create indexes for fast lookups
        from mongodb import create_index
        
        create_index(CHANNEL_GUILDS, "channel_id", unique=True)
        create_index(CHANNEL_SNAPSHOTS, "channel_id")
        create_index(CHANNEL_SNAPSHOTS, "guild_id")
        create_index(CHANNEL_CHANGES, "channel_id")
        create_index(CHANNEL_CHANGES, "guild_id")
        create_index(MEMBER_CACHE, "uid", unique=True)
        create_index(BOT_SETTINGS, "key", unique=True)
        
        print("✅ MongoDB collections initialized")
        return True
    except Exception as e:
        print(f"⚠️ MongoDB initialization warning: {e}")
        return False


def get_channel_guild_id(channel_id):
    """Get the Free Fire guild ID for a channel"""
    try:
        doc = find_document(CHANNEL_GUILDS, {"channel_id": channel_id})
        if doc:
            return doc.get("guild_id")
        return None
    except Exception as e:
        print(f"⚠️ Error getting channel guild ID: {e}")
        return None


def get_channel_access_token(channel_id):
    """Get the access token for a channel's guild"""
    try:
        doc = find_document(CHANNEL_GUILDS, {"channel_id": channel_id})
        if doc:
            return doc.get("access_token")
        return None
    except Exception as e:
        print(f"⚠️ Error getting access token: {e}")
        return None


def register_channel_guild(channel_id, guild_id, access_token, registered_by, guild_name=None):
    """Register a guild for monitoring in a channel"""
    try:
        doc = {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "access_token": access_token,
            "registered_by": registered_by,
            "guild_name": guild_name,
            "registered_at": datetime.utcnow().isoformat()
        }
        
        # Update if exists, insert if not
        existing = find_document(CHANNEL_GUILDS, {"channel_id": channel_id})
        if existing:
            update_document(CHANNEL_GUILDS, {"channel_id": channel_id}, doc)
        else:
            insert_document(CHANNEL_GUILDS, doc)
        
        return True
    except Exception as e:
        print(f"⚠️ Error registering channel guild: {e}")
        return False


def unregister_channel_guild(channel_id):
    """Unregister a guild from a channel"""
    try:
        delete_document(CHANNEL_GUILDS, {"channel_id": channel_id})
        return True
    except Exception as e:
        print(f"⚠️ Error unregistering channel guild: {e}")
        return False


def get_channel_guild_info(channel_id):
    """Get full guild info for a channel"""
    try:
        return find_document(CHANNEL_GUILDS, {"channel_id": channel_id})
    except Exception as e:
        print(f"⚠️ Error getting channel guild info: {e}")
        return None


def save_snapshot(channel_id, guild_id, member_uids):
    """Save a snapshot of guild members"""
    try:
        doc = {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "member_uids": member_uids,
            "snapshot_at": datetime.utcnow().isoformat()
        }
        insert_document(CHANNEL_SNAPSHOTS, doc)
        return True
    except Exception as e:
        print(f"⚠️ Error saving snapshot: {e}")
        return False


def get_latest_snapshot(channel_id, guild_id):
    """Get the latest snapshot for a guild in a channel"""
    try:
        snapshots = find_documents(CHANNEL_SNAPSHOTS, 
                                   {"channel_id": channel_id, "guild_id": guild_id})
        if snapshots:
            return snapshots[-1]  # Last one is latest
        return None
    except Exception as e:
        print(f"⚠️ Error getting latest snapshot: {e}")
        return None


def record_membership_change(channel_id, guild_id, uid, change_type, nickname=None):
    """Record a membership change (joined/left)"""
    try:
        doc = {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "uid": uid,
            "change_type": change_type,  # 'joined' or 'left'
            "nickname": nickname,
            "timestamp": datetime.utcnow().isoformat()
        }
        insert_document(CHANNEL_CHANGES, doc)
        return True
    except Exception as e:
        print(f"⚠️ Error recording membership change: {e}")
        return False


def get_membership_changes(channel_id, guild_id, limit=50):
    """Get recent membership changes for a guild"""
    try:
        changes = find_documents(CHANNEL_CHANGES, 
                                {"channel_id": channel_id, "guild_id": guild_id})
        # Return most recent first
        return sorted(changes, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
    except Exception as e:
        print(f"⚠️ Error getting membership changes: {e}")
        return []


def cache_member(uid, member_data):
    """Cache member data for quick lookups"""
    try:
        doc = {
            "uid": uid,
            "data": member_data,
            "cached_at": datetime.utcnow().isoformat()
        }
        
        existing = find_document(MEMBER_CACHE, {"uid": uid})
        if existing:
            update_document(MEMBER_CACHE, {"uid": uid}, doc)
        else:
            insert_document(MEMBER_CACHE, doc)
        
        return True
    except Exception as e:
        print(f"⚠️ Error caching member: {e}")
        return False


def get_cached_member(uid):
    """Get cached member data"""
    try:
        doc = find_document(MEMBER_CACHE, {"uid": uid})
        if doc:
            return doc.get("data")
        return None
    except Exception as e:
        print(f"⚠️ Error getting cached member: {e}")
        return None


def clear_member_cache():
    """Clear all cached member data"""
    try:
        from mongodb import clear_collection
        clear_collection(MEMBER_CACHE)
        return True
    except Exception as e:
        print(f"⚠️ Error clearing member cache: {e}")
        return False


def set_bot_setting(key, value):
    """Store a bot setting"""
    try:
        doc = {
            "key": key,
            "value": value,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        existing = find_document(BOT_SETTINGS, {"key": key})
        if existing:
            update_document(BOT_SETTINGS, {"key": key}, doc)
        else:
            insert_document(BOT_SETTINGS, doc)
        
        return True
    except Exception as e:
        print(f"⚠️ Error setting bot setting: {e}")
        return False


def get_bot_setting(key, default=None):
    """Get a bot setting"""
    try:
        doc = find_document(BOT_SETTINGS, {"key": key})
        if doc:
            return doc.get("value")
        return default
    except Exception as e:
        print(f"⚠️ Error getting bot setting: {e}")
        return default


def get_all_registered_channels():
    """Get all channels with registered guilds"""
    try:
        return find_documents(CHANNEL_GUILDS, {})
    except Exception as e:
        print(f"⚠️ Error getting registered channels: {e}")
        return []
