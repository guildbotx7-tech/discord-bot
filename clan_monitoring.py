"""Background task for monitoring Free Fire clan membership changes every 10 minutes.

Continuously fetches the clan roster and detects/logs join/leave events.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from helpers import get_ist_now, get_ist_timestamp

from member_clan_api import (
    detect_roster_changes,
    fetch_member_clan,
    get_roster_uids,
    record_membership_change,
    MemberClanAPIError,
)

# Database for tracking roster state and changes
DB_PATH = Path(__file__).parent / "clan_monitoring.db"


def init_monitoring_db():
    """Initialize the monitoring database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Store last known roster per guild/clan
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roster_snapshots (
            clan_id INTEGER PRIMARY KEY,
            uids TEXT,
            last_checked TEXT
        )
    """)

    # Log all membership changes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS membership_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clan_id INTEGER,
            ff_uid INTEGER,
            change_type TEXT,
            nickname TEXT,
            detected_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_last_roster(clan_id):
    """Retrieve the last known roster UIDs for a clan.

    Args:
        clan_id (int): The Free Fire clan ID.

    Returns:
        set: UIDs from last snapshot, or empty set if none exists.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT uids FROM roster_snapshots WHERE clan_id=?", (clan_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            return set(json.loads(row[0]))
        return set()
    except Exception as e:
        print(f"Error retrieving last roster for clan {clan_id}: {e}")
        return set()


def save_roster_snapshot(clan_id, uids):
    """Save the current roster UIDs as a snapshot.

    Args:
        clan_id (int): The Free Fire clan ID.
        uids (set): Current roster UIDs.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "REPLACE INTO roster_snapshots (clan_id, uids, last_checked) VALUES (?, ?, ?)",
            (clan_id, json.dumps(list(uids)), get_ist_timestamp()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving roster snapshot: {e}")


def log_membership_change(clan_id, ff_uid, change_type, nickname=None):
    """Log a membership change event.

    Args:
        clan_id (int): The Free Fire clan ID.
        ff_uid (int): The Free Fire UID.
        change_type (str): "joined" or "left".
        nickname (str): Optional player nickname.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO membership_changes 
               (clan_id, ff_uid, change_type, nickname, detected_at)
               VALUES (?, ?, ?, ?, ?)""",
            (clan_id, ff_uid, change_type, nickname, get_ist_timestamp()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging membership change: {e}")


def check_roster_changes(api_response, clan_id):
    """Check for roster changes and log events.

    Args:
        api_response (dict): Response from the memberClan API.
        clan_id (int): The Free Fire clan ID.

    Returns:
        dict: {"joined": list, "left": list} with member nicknames.
    """
    try:
        current_uids = get_roster_uids(api_response)
        previous_uids = get_last_roster(clan_id)

        changes = detect_roster_changes(current_uids, previous_uids)

        # Log joins
        for uid in changes["joined"]:
            member = next(
                (m for m in api_response.get("members", []) if m.get("account_id") == uid),
                None,
            )
            nickname = member.get("nickname") if member else None
            log_membership_change(clan_id, uid, "joined", nickname)
            print(f"  ✅ JOINED: {nickname or 'Unknown'} (UID: {uid})")

        # Log leaves
        for uid in changes["left"]:
            log_membership_change(clan_id, uid, "left")
            print(f"  ❌ LEFT: UID {uid}")

        # Save current state for next check
        save_roster_snapshot(clan_id, current_uids)

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
        print(f"Error checking roster changes: {e}")
        return {"joined": [], "left": []}


def monitor_clan_roster(access_token, clan_id):
    """Execute a single roster check cycle.

    Args:
        access_token (str): API access token.
        clan_id (int): Free Fire clan ID.

    Returns:
        dict: Result containing joined/left members, or error info.
    """
    try:
        print(f"\n[{get_ist_now().strftime('%Y-%m-%d %H:%M:%S IST')}] Checking clan {clan_id}...")
        api_response = fetch_member_clan(access_token)
        changes = check_roster_changes(api_response, clan_id)
        return {"status": "success", "changes": changes}
    except MemberClanAPIError as e:
        print(f"  ❌ API Error: {e}")
        return {"status": "error", "error": str(e)}
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return {"status": "error", "error": str(e)}


def get_recent_changes(clan_id, limit=20):
    """Retrieve recent membership changes for a clan.

    Args:
        clan_id (int): The Free Fire clan ID.
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
               WHERE clan_id=?
               ORDER BY detected_at DESC
               LIMIT ?""",
            (clan_id, limit),
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
