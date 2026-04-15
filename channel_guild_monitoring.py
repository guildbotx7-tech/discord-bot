"""Channel-based guild monitoring functions for integration with main bot"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from helpers import get_ist_timestamp

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
            registered_at TEXT,
            guild_name TEXT,
            monitoring_interval INTEGER DEFAULT 2
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

    # Migration: Add last_player_check column if it doesn't exist
    try:
        cursor.execute("PRAGMA table_info(channel_guilds)")
        columns = [column[1] for column in cursor.fetchall()]
        if "last_player_check" not in columns:
            print("🔄 Migrating database: Adding last_player_check column to channel_guilds...")
            cursor.execute("ALTER TABLE channel_guilds ADD COLUMN last_player_check TEXT")
            conn.commit()
            print("✅ Migration complete: last_player_check column added")
    except Exception as e:
        print(f"⚠️ Migration warning: {e}")

    # Migration: Add monitoring_interval column if it doesn't exist
    try:
        cursor.execute("PRAGMA table_info(channel_guilds)")
        columns = [column[1] for column in cursor.fetchall()]
        if "monitoring_interval" not in columns:
            print("🔄 Migrating database: Adding monitoring_interval column to channel_guilds...")
            cursor.execute("ALTER TABLE channel_guilds ADD COLUMN monitoring_interval INTEGER DEFAULT 2")
            conn.commit()
            print("✅ Migration complete: monitoring_interval column added")
    except Exception as e:
        print(f"⚠️ Migration warning: {e}")

    # Migration: Add player_monitoring_enabled column if it doesn't exist
    try:
        cursor.execute("PRAGMA table_info(channel_guilds)")
        columns = [column[1] for column in cursor.fetchall()]
        if "player_monitoring_enabled" not in columns:
            print("🔄 Migrating database: Adding player_monitoring_enabled column to channel_guilds...")
            cursor.execute("ALTER TABLE channel_guilds ADD COLUMN player_monitoring_enabled INTEGER DEFAULT 1")
            conn.commit()
            print("✅ Migration complete: player_monitoring_enabled column added")
    except Exception as e:
        print(f"⚠️ Migration warning: {e}")

    # Migration: Add rival_detection_enabled column if it doesn't exist
    try:
        cursor.execute("PRAGMA table_info(channel_guilds)")
        columns = [column[1] for column in cursor.fetchall()]
        if "rival_detection_enabled" not in columns:
            print("🔄 Migrating database: Adding rival_detection_enabled column to channel_guilds...")
            cursor.execute("ALTER TABLE channel_guilds ADD COLUMN rival_detection_enabled INTEGER DEFAULT 1")
            conn.commit()
            print("✅ Migration complete: rival_detection_enabled column added")
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
            (channel_id, guild_id, access_token, registered_by, get_ist_timestamp(), guild_name)
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


def get_channel_last_snapshot_time(channel_id):
    """Get the last snapshot timestamp for a channel."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT snapshot_at FROM channel_snapshots WHERE channel_id = ? ORDER BY snapshot_at DESC LIMIT 1",
            (channel_id,)
        )
        result = cursor.fetchone()
        conn.close()
        if not result or not result[0]:
            return None
        from datetime import datetime
        return datetime.fromisoformat(result[0])
    except Exception as e:
        print(f"Error getting last snapshot time for channel {channel_id}: {e}")
        return None


def get_channel_player_monitoring_interval(channel_id):
    """Get the current per-channel player monitoring interval in minutes."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT monitoring_interval FROM channel_guilds WHERE channel_id = ?",
            (channel_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return int(result[0]) if result and result[0] is not None else 2
    except:
        return 2


def set_channel_player_monitoring_interval(channel_id, minutes):
    """Set the player monitoring interval for a specific channel."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE channel_guilds SET monitoring_interval = ? WHERE channel_id = ?",
            (minutes, channel_id)
        )
        updated = cursor.rowcount
        conn.commit()
        conn.close()
        return updated > 0
    except Exception as e:
        print(f"Error setting player monitoring interval for channel {channel_id}: {e}")
        return False


def get_channel_last_player_check(channel_id):
    """Get the last time player monitoring was run for a channel."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT last_player_check FROM channel_guilds WHERE channel_id = ?",
            (channel_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result and result[0] else None
    except Exception as e:
        print(f"Error getting last player check time for channel {channel_id}: {e}")
        return None


def set_channel_last_player_check(channel_id, timestamp=None):
    """Set the last time player monitoring was run for a channel."""
    if timestamp is None:
        from helpers import get_ist_timestamp
        timestamp = get_ist_timestamp()
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE channel_guilds SET last_player_check = ? WHERE channel_id = ?",
            (timestamp, channel_id)
        )
        updated = cursor.rowcount
        conn.commit()
        conn.close()
        return updated > 0
    except Exception as e:
        print(f"Error setting last player check time for channel {channel_id}: {e}")
        return False


def save_channel_snapshot(channel_id, guild_id, uids):
    """Save a snapshot of current guild members for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO channel_snapshots (channel_id, guild_id, member_uids, snapshot_at) VALUES (?, ?, ?, ?)",
            (channel_id, guild_id, json.dumps(list(uids)), get_ist_timestamp())
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
            (channel_id, guild_id, uid, change_type, nickname, get_ist_timestamp())
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
            (uid, json.dumps(data), get_ist_timestamp())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error caching member: {e}")


def get_cached_member_data(uid):
    """Get cached member data for a specific UID."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT data FROM member_cache WHERE uid = ? ORDER BY cached_at DESC LIMIT 1",
            (uid,)
        )
        result = cursor.fetchone()
        conn.close()
        return json.loads(result[0]) if result else None
    except Exception:
        return None


def monitor_channel_guild(channel_id, retry_count=0, max_retries=2):
    """Monitor guild membership changes for a specific channel with double-check verification and retry logic"""
    try:
        from member_guild_api import fetch_member_guild, detect_list_changes, MemberGuildAPIError
        import time

        guild_id = get_channel_guild_id(channel_id)
        access_token = get_channel_access_token(channel_id)

        if not guild_id or not access_token:
            return {"status": "error", "error": "No guild registered for this channel"}

        token_preview = f"{access_token[:10]}...{access_token[-5:]}" if len(access_token) > 15 else "***"
        
        try:
            # First API call
            api_response_1 = fetch_member_guild(access_token, timeout=45, retries=1)
            current_members_1 = api_response_1.get("members", [])

            if not current_members_1:
                return {"status": "error", "error": "Failed to fetch current member list or guild is empty (first call)"}

            # Wait a short time before second call
            time.sleep(2)

            # Second API call for verification
            api_response_2 = fetch_member_guild(access_token, timeout=45, retries=1)
            current_members_2 = api_response_2.get("members", [])

            if not current_members_2:
                return {"status": "error", "error": "Failed to fetch current member list or guild is empty (second call)"}

        except MemberGuildAPIError as api_err:
            error_msg = str(api_err)
            # Check if it's a HTTP 500 or other transient error
            if "HTTP error 500" in error_msg or "timed out" in error_msg.lower():
                if retry_count < max_retries:
                    print(f"⚠️  Channel {channel_id} (Guild {guild_id}): {error_msg} - Retrying ({retry_count + 1}/{max_retries})...")
                    time.sleep(5 * (retry_count + 1))  # Exponential backoff
                    return monitor_channel_guild(channel_id, retry_count + 1, max_retries)
                else:
                    print(f"❌ Channel {channel_id} (Guild {guild_id}): {error_msg} - Max retries exceeded")
                    return {"status": "error", "error": f"{error_msg} (after {max_retries} retries)"}
            else:
                print(f"❌ Channel {channel_id} (Guild {guild_id}): {error_msg}")
                return {"status": "error", "error": error_msg}

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
            member_data = get_cached_member_data(uid)
            nickname = member_data.get("nickname") if member_data else None
            if not nickname:
                try:
                    from member_clan_api import fetch_player_info
                    player_info = fetch_player_info(uid)
                    nickname = player_info.get("basicInfo", {}).get("nickname")
                except Exception:
                    nickname = None

            log_channel_membership_change(channel_id, guild_id, uid, "left", nickname)

        # Save new snapshot
        save_channel_snapshot(channel_id, guild_id, current_uids)

        return {
            "status": "success",
            "changes": changes,
            "member_count": len(current_members)
        }

    except Exception as e:
        print(f"❌ Channel {channel_id}: Unexpected error: {e}")
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
            ("monitoring_interval", str(minutes), get_ist_timestamp())
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error setting monitoring interval: {e}")
        return False


def get_ban_monitoring_interval():
    """Get the current ban monitoring interval in minutes"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM bot_settings WHERE key = 'ban_monitoring_interval'"
        )
        result = cursor.fetchone()
        conn.close()
        return int(result[0]) if result else 10  # Default 10 minutes
    except:
        return 10


def set_ban_monitoring_interval(minutes):
    """Set the ban monitoring interval in minutes"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO bot_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("ban_monitoring_interval", str(minutes), get_ist_timestamp())
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error setting ban monitoring interval: {e}")
        return False


def get_player_monitoring_enabled(channel_id):
    """Get whether player monitoring is enabled for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT player_monitoring_enabled FROM channel_guilds WHERE channel_id = ?",
            (channel_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return bool(result[0]) if result else True  # Default enabled
    except Exception as e:
        print(f"Error getting player monitoring status: {e}")
        return True


def set_player_monitoring_enabled(channel_id, enabled):
    """Enable or disable player monitoring for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE channel_guilds SET player_monitoring_enabled = ? WHERE channel_id = ?",
            (1 if enabled else 0, channel_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error setting player monitoring status: {e}")
        return False


def get_rival_detection_enabled(channel_id):
    """Get whether rival detection is enabled for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT rival_detection_enabled FROM channel_guilds WHERE channel_id = ?",
            (channel_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return bool(result[0]) if result else True  # Default enabled
    except Exception as e:
        print(f"Error getting rival detection status: {e}")
        return True


def set_rival_detection_enabled(channel_id, enabled):
    """Enable or disable rival detection for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE channel_guilds SET rival_detection_enabled = ? WHERE channel_id = ?",
            (1 if enabled else 0, channel_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error setting rival detection status: {e}")
        return False


# Initialize database on import
init_channel_monitoring_db()
