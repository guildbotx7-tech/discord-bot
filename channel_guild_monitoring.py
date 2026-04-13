"""Channel-based guild monitoring functions for integration with main bot"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "discord_bot.db"


def init_channel_monitoring_db():
    """Initialize the channel-based monitoring database tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Channel-based guild registrations with access tokens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channel_guilds (
            channel_id INTEGER PRIMARY KEY,
            guild_id TEXT NOT NULL,
            access_token TEXT NOT NULL,  -- Per-guild access token
            registered_by INTEGER,
            registered_at TEXT
        )
    """)

    # Migration: Add access_token column if it doesn't exist
    try:
        cursor.execute("PRAGMA table_info(channel_guilds)")
        columns = [column[1] for column in cursor.fetchall()]
        if "access_token" not in columns:
            print("🔄 Migrating database: Adding access_token column to channel_guilds...")
            cursor.execute("ALTER TABLE channel_guilds ADD COLUMN access_token TEXT")
            conn.commit()
            print("✅ Migration complete: access_token column added")
    except Exception as e:
        print(f"⚠️ Migration warning: {e}")

    # Migration: Add guild_name column if it doesn't exist
    try:
        cursor.execute("PRAGMA table_info(channel_guilds)")
        columns = [column[1] for column in cursor.fetchall()]
        if "guild_name" not in columns:
            print("🔄 Migrating database: Adding guild_name column to channel_guilds...")
            cursor.execute("ALTER TABLE channel_guilds ADD COLUMN guild_name TEXT")
            conn.commit()
            print("✅ Migration complete: guild_name column added")
    except Exception as e:
        print(f"⚠️ Migration warning: {e}")

    # Guild snapshots (per channel)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channel_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            guild_id TEXT NOT NULL,
            member_uids TEXT NOT NULL,  -- JSON array of UIDs
            snapshot_at TEXT NOT NULL
        )
    """)

    # Membership changes (per channel)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channel_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            guild_id TEXT NOT NULL,
            uid TEXT NOT NULL,
            change_type TEXT NOT NULL,  -- 'joined' or 'left'
            nickname TEXT,
            timestamp TEXT NOT NULL
        )
    """)

    # Member cache for quick lookups
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS member_cache (
            uid TEXT PRIMARY KEY,
            data TEXT NOT NULL,  -- JSON member data
            cached_at TEXT NOT NULL
        )
    """)

    # Bot settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_channel_guild_id(channel_id):
    """Get the Free Fire guild ID for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT guild_id FROM channel_guilds WHERE channel_id = ?",
            (channel_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except:
        return None

def get_channel_guild_name(channel_id):
    """Get the guild name registered for a specific channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT guild_name FROM channel_guilds WHERE channel_id = ?",
            (channel_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except:
        return None


def get_channel_registered_by(channel_id):
    """Get the Discord user ID that registered the guild for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT registered_by FROM channel_guilds WHERE channel_id = ?",
            (channel_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return int(result[0]) if result and result[0] is not None else None
    except:
        return None


def register_channel_guild(channel_id, guild_id, access_token, registered_by, guild_name=None):
    """Register a guild for monitoring in a specific channel with its access token and name"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO channel_guilds (channel_id, guild_id, access_token, registered_by, registered_at, guild_name) VALUES (?, ?, ?, ?, ?, ?)",
            (channel_id, guild_id, access_token, registered_by, datetime.utcnow().isoformat(), guild_name)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error registering channel guild: {e}")
        return False


def unregister_channel_guild(channel_id):
    """Remove the guild registration for a specific channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM channel_guilds WHERE channel_id = ?",
            (channel_id,)
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted > 0
    except Exception as e:
        print(f"Error unregistering channel guild: {e}")
        return False


def get_channel_access_token(channel_id):
    """Get the access token for a channel's registered guild"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT access_token FROM channel_guilds WHERE channel_id = ?",
            (channel_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except:
        return None


def get_channel_last_list(channel_id):
    """Get the last known member list for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT member_uids FROM channel_snapshots WHERE channel_id = ? ORDER BY snapshot_at DESC LIMIT 1",
            (channel_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return set(json.loads(result[0])) if result else set()
    except:
        return set()


def save_channel_snapshot(channel_id, guild_id, uids):
    """Save a snapshot of current guild members for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO channel_snapshots (channel_id, guild_id, member_uids, snapshot_at) VALUES (?, ?, ?, ?)",
            (channel_id, guild_id, json.dumps(list(uids)), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving channel snapshot: {e}")


def log_channel_membership_change(channel_id, guild_id, uid, change_type, nickname=None):
    """Log a membership change for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO channel_changes (channel_id, guild_id, uid, change_type, nickname, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (channel_id, guild_id, uid, change_type, nickname, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging channel change: {e}")


def cache_member_data(uid, data):
    """Cache member data for quick lookups"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO member_cache (uid, data, cached_at) VALUES (?, ?, ?)",
            (uid, json.dumps(data), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error caching member: {e}")


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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, change_type, nickname, timestamp FROM channel_changes WHERE channel_id = ? ORDER BY timestamp DESC LIMIT ?",
            (channel_id, limit)
        )
        results = cursor.fetchall()
        conn.close()

        changes = []
        for row in results:
            changes.append({
                "uid": row[0],
                "change_type": row[1],
                "nickname": row[2],
                "timestamp": row[3]
            })

        return changes
    except Exception as e:
        print(f"Error getting channel changes: {e}")
        return []


def get_channel_members(channel_id):
    """Get current cached members for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT data FROM member_cache WHERE uid IN (SELECT json_each.value FROM channel_snapshots, json_each(channel_snapshots.member_uids) WHERE channel_snapshots.channel_id = ? ORDER BY channel_snapshots.snapshot_at DESC LIMIT 1)",
            (channel_id,)
        )
        results = cursor.fetchall()
        conn.close()

        members = []
        for row in results:
            members.append(json.loads(row[0]))

        return members
    except Exception as e:
        print(f"Error getting channel members: {e}")
        return []


def get_monitoring_interval():
    """Get the current monitoring interval in minutes"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM bot_settings WHERE key = 'monitoring_interval'"
        )
        result = cursor.fetchone()
        conn.close()
        return int(result[0]) if result else 2  # Default 2 minutes
    except:
        return 2


def set_monitoring_interval(minutes):
    """Set the monitoring interval in minutes"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO bot_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("monitoring_interval", str(minutes), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error setting monitoring interval: {e}")
        return False


# Initialize database on import
init_channel_monitoring_db()
