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


def get_channel_guild_name(channel_id):
    """Get the guild name registered for a specific channel"""
    try:
        doc = find_document(CHANNEL_GUILDS, {"channel_id": channel_id})
        if doc:
            return doc.get("guild_name")
        return None
    except Exception as e:
        print(f"⚠️ Error getting channel guild name: {e}")
        return None


def get_channel_registered_by(channel_id):
    """Get the Discord user ID that registered the guild for a channel"""
    try:
        doc = find_document(CHANNEL_GUILDS, {"channel_id": channel_id})
        if doc:
            registered_by = doc.get("registered_by")
            return int(registered_by) if registered_by else None
        return None
    except Exception as e:
        print(f"⚠️ Error getting channel registered_by: {e}")
        return None


def get_channel_last_list(channel_id):
    """Get the last known member list for a channel"""
    try:
        snapshots = find_documents(CHANNEL_SNAPSHOTS, {"channel_id": channel_id})
        if snapshots:
            latest = sorted(snapshots, key=lambda x: x.get("snapshot_at", ""), reverse=True)[0]
            return set(latest.get("member_uids", []))
        return set()
    except Exception as e:
        print(f"⚠️ Error getting channel last list: {e}")
        return set()


def save_channel_snapshot(channel_id, guild_id, uids):
    """Save a snapshot of current guild members for a channel"""
    try:
        doc = {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "member_uids": list(uids),
            "snapshot_at": datetime.utcnow().isoformat()
        }
        insert_document(CHANNEL_SNAPSHOTS, doc)
        return True
    except Exception as e:
        print(f"⚠️ Error saving channel snapshot: {e}")
        return False


def log_channel_membership_change(channel_id, guild_id, uid, change_type, nickname=None):
    """Log a membership change for a channel"""
    try:
        doc = {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "uid": uid,
            "change_type": change_type,
            "nickname": nickname,
            "timestamp": datetime.utcnow().isoformat()
        }
        insert_document(CHANNEL_CHANGES, doc)
        return True
    except Exception as e:
        print(f"⚠️ Error logging channel change: {e}")
        return False


def cache_member_data(uid, data):
    """Cache member data for quick lookups"""
    try:
        doc = {
            "uid": uid,
            "data": data,
            "cached_at": datetime.utcnow().isoformat()
        }
        
        existing = find_document(MEMBER_CACHE, {"uid": uid})
        if existing:
            update_document(MEMBER_CACHE, {"uid": uid}, doc)
        else:
            insert_document(MEMBER_CACHE, doc)
        
        return True
    except Exception as e:
        print(f"⚠️ Error caching member data: {e}")
        return False


def monitor_channel_guild(channel_id):
    """Monitor guild membership changes for a specific channel with double-check verification"""
    try:
        from member_guild_api import fetch_member_guild, detect_list_changes
        import time

        guild_id = get_channel_guild_id(channel_id)
        access_token = get_channel_access_token(channel_id)

        if not guild_id or not access_token:
            return {"status": "error", "error": "No guild registered for this channel"}

        # First API call
        api_response_1 = fetch_member_guild(access_token, timeout=10)
        current_members_1 = api_response_1.get("members", [])

        if not current_members_1:
            return {"status": "error", "error": "Failed to fetch current member list or guild is empty (first call)"}

        # Wait a short time before second call
        time.sleep(2)

        # Second API call for verification
        api_response_2 = fetch_member_guild(access_token, timeout=10)
        current_members_2 = api_response_2.get("members", [])

        if not current_members_2:
            return {"status": "error", "error": "Failed to fetch current member list or guild is empty (second call)"}

        # Extract UIDs from both calls
        current_uids_1 = set(m.get("account_id") for m in current_members_1 if m.get("account_id"))
        current_uids_2 = set(m.get("account_id") for m in current_members_2 if m.get("account_id"))

        # Verify both calls return consistent data
        if current_uids_1 != current_uids_2:
            return {"status": "error", "error": "API inconsistency detected - member lists differ between calls"}

        # Use the second call's data for processing (most recent)
        current_members = current_members_2
        current_uids = current_uids_2

        # Cache member data and get UIDs
        for member in current_members:
            account_id = member.get("account_id")
            if account_id:
                cache_member_data(account_id, member)

        # Get previous snapshot
        previous_uids = get_channel_last_list(channel_id)

        # Detect changes
        changes = detect_list_changes(current_uids, previous_uids)
        changes["joined"] = list(changes["joined"])
        changes["left"] = list(changes["left"])

        # Log changes
        for uid in changes["joined"]:
            member_data = next((m for m in current_members if m.get("account_id") == uid), {})
            nickname = member_data.get("nickname")
            log_channel_membership_change(channel_id, guild_id, uid, "joined", nickname)

        for uid in changes["left"]:
            log_channel_membership_change(channel_id, guild_id, uid, "left")

        # Save new snapshot
        save_channel_snapshot(channel_id, guild_id, current_uids)

        return {
            "status": "success",
            "changes": changes,
            "member_count": len(current_members)
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_channel_recent_changes(channel_id, limit=50):
    """Get recent membership changes for a channel"""
    try:
        changes = find_documents(CHANNEL_CHANGES, {"channel_id": channel_id})
        # Sort by timestamp descending
        sorted_changes = sorted(
            changes, 
            key=lambda x: x.get("timestamp", ""), 
            reverse=True
        )[:limit]
        
        return [{
            "uid": change.get("uid"),
            "change_type": change.get("change_type"),
            "nickname": change.get("nickname"),
            "timestamp": change.get("timestamp")
        } for change in sorted_changes]
    except Exception as e:
        print(f"⚠️ Error getting channel recent changes: {e}")
        return []


def get_channel_members(channel_id):
    """Get current cached members for a channel"""
    try:
        # Get the latest snapshot for the channel
        snapshots = find_documents(CHANNEL_SNAPSHOTS, {"channel_id": channel_id})
        if not snapshots:
            return []
        
        latest_snapshot = sorted(snapshots, key=lambda x: x.get("snapshot_at", ""), reverse=True)[0]
        member_uids = latest_snapshot.get("member_uids", [])
        
        # Get member data from cache
        members = []
        for uid in member_uids:
            member_doc = find_document(MEMBER_CACHE, {"uid": uid})
            if member_doc and member_doc.get("data"):
                members.append(member_doc.get("data"))
        
        return members
    except Exception as e:
        print(f"⚠️ Error getting channel members: {e}")
        return []


def get_monitoring_interval():
    """Get the current monitoring interval in minutes"""
    try:
        interval = get_bot_setting("monitoring_interval")
        return int(interval) if interval else 2  # Default 2 minutes
    except Exception as e:
        print(f"⚠️ Error getting monitoring interval: {e}")
        return 2


def set_monitoring_interval(minutes):
    """Set the monitoring interval in minutes"""
    try:
        return set_bot_setting("monitoring_interval", str(minutes))
    except Exception as e:
        print(f"⚠️ Error setting monitoring interval: {e}")
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
