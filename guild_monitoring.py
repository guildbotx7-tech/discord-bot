"""Background task for monitoring Free Fire guild membership changes every 10 minutes.

Continuously fetches the guild member list and detects/logs join/leave events.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from helpers import get_ist_timestamp

from member_guild_api import (
    detect_list_changes,
    fetch_member_guild,
    get_list_uids,
    record_membership_change,
    MemberGuildAPIError,
)

# Database for tracking list state and changes
DB_PATH = Path(__file__).parent / "discord_bot.db"


def init_monitoring_db():
    """Initialize the monitoring database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Store last known member list per guild
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS list_snapshots (
            guild_id INTEGER PRIMARY KEY,
            uids TEXT,
            last_checked TEXT
        )
    """)

    # Log all membership changes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS membership_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            ff_uid INTEGER,
            change_type TEXT,
            nickname TEXT,
            detected_at TEXT
        )
    """)

    # Store access tokens per guild/channel (for multi-guild support)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER UNIQUE,
            channel_id INTEGER,
            registered_by INTEGER,
            registered_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_last_list(guild_id):
    """Retrieve the last known member list UIDs for a guild.

    Args:
        guild_id (int): The Free Fire guild ID.

    Returns:
        set: UIDs from last snapshot, or empty set if none exists.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT uids FROM list_snapshots WHERE guild_id=?", (guild_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            return set(json.loads(row[0]))
        return set()
    except Exception as e:
        print(f"Error retrieving last list for guild {guild_id}: {e}")
        return set()


def save_list_snapshot(guild_id, uids):
    """Save the current member list UIDs as a snapshot.

    Args:
        guild_id (int): The Free Fire guild ID.
        uids (set): Current member list UIDs.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "REPLACE INTO list_snapshots (guild_id, uids, last_checked) VALUES (?, ?, ?)",
            (guild_id, json.dumps(list(uids)), get_ist_timestamp()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving list snapshot: {e}")


def log_membership_change(guild_id, ff_uid, change_type, nickname=None):
    """Log a membership change event.

    Args:
        guild_id (int): The Free Fire guild ID.
        ff_uid (int): The Free Fire UID.
        change_type (str): "joined" or "left".
        nickname (str): Optional player nickname.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO membership_changes
               (guild_id, ff_uid, change_type, nickname, detected_at)
               VALUES (?, ?, ?, ?, ?)""",
            (guild_id, ff_uid, change_type, nickname, get_ist_timestamp()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging membership change: {e}")


def check_list_changes(api_response, guild_id):
    """Check for member list changes and log events.

    Args:
        api_response (dict): Response from the memberGuild API.
        guild_id (int): The Free Fire guild ID.

    Returns:
        dict: {"joined": list, "left": list} with member nicknames.
    """
    try:
        current_uids = get_list_uids(api_response)
        previous_uids = get_last_list(guild_id)

        changes = detect_list_changes(current_uids, previous_uids)

        # Log joins
        for uid in changes["joined"]:
            member = next(
                (m for m in api_response.get("members", []) if m.get("account_id") == uid),
                None,
            )
            nickname = member.get("nickname") if member else None
            log_membership_change(guild_id, uid, "joined", nickname)
            print(f"  ✅ JOINED: {nickname or 'Unknown'} (UID: {uid})")

        # Log leaves
        for uid in changes["left"]:
            log_membership_change(guild_id, uid, "left")
            print(f"  ❌ LEFT: UID {uid}")

        # Save current state for next check
        save_list_snapshot(guild_id, current_uids)

        return {
            "joined": [
                {
                    "uid": uid,
                    "nickname": next(
                        (m.get("nickname") for m in api_response.get("members", []) if m.get("account_id") == uid),
                        None,
                    ),
                }
                for uid in changes["joined"]
            ],
            "left": [{"uid": uid} for uid in changes["left"]],
        }
    except Exception as e:
        print(f"Error checking list changes: {e}")
        return {"joined": [], "left": []}


def monitor_guild_list(access_token, guild_id):
    """Execute a single member list check cycle.

    Args:
        access_token (str): API access token.
        guild_id (int): Free Fire guild ID.

    Returns:
        dict: Result containing joined/left members, or error info.
    """
    try:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking guild {guild_id}...")
        api_response = fetch_member_guild(access_token)
        changes = check_list_changes(api_response, guild_id)
        return {"status": "success", "changes": changes}
    except MemberGuildAPIError as e:
        print(f"  ❌ API Error: {e}")
        return {"status": "error", "error": str(e)}
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return {"status": "error", "error": str(e)}


def get_recent_changes(guild_id, limit=20):
    """Retrieve recent membership changes for a guild.

    Args:
        guild_id (int): The Free Fire guild ID.
        limit (int): Max number of records to return.

    Returns:
        list: Recent change records.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT ff_uid, change_type, nickname, detected_at
               FROM membership_changes
               WHERE guild_id=?
               ORDER BY detected_at DESC
               LIMIT ?""",
            (guild_id, limit),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "uid": row[0],
                "change_type": row[1],
                "nickname": row[2],
                "timestamp": row[3],
            }
            for row in rows
        ]
    except Exception as e:
        print(f"Error retrieving recent changes: {e}")
        return []


# Initialize DB on import
init_monitoring_db()