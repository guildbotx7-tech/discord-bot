"""Background task for monitoring Free Fire guild membership changes every 10 minutes.

Continuously fetches the guild roster and detects/logs join/leave events.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from helpers import get_ist_now, get_ist_timestamp

from member_clan_api import fetch_player_info
from member_guild_api import (
    detect_list_changes,
    fetch_member_guild,
    get_list_uids,
    MemberGuildAPIError,
)

# Database for tracking roster state and changes
DB_PATH = Path(__file__).parent / "clan_monitoring.db"


def init_monitoring_db():
    """Initialize the monitoring database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Store last known roster per guild/guild
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

    # Store partnered guild IDs for immediate alerts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flagged_clans (
            clan_id INTEGER PRIMARY KEY,
            flagged_at TEXT,
            reason TEXT
        )
    """)

    # Log partnered player movements
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flagged_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ff_uid INTEGER,
            nickname TEXT,
            from_clan_id INTEGER,
            to_clan_id INTEGER,
            detected_at TEXT,
            alert_sent BOOLEAN DEFAULT FALSE
        )
    """)

    # Store granted partnered guild permissions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS granted_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ff_uid INTEGER,
            channel_id INTEGER,
            granted_by INTEGER,
            remarks TEXT,
            granted_at TEXT,
            active BOOLEAN DEFAULT TRUE
        )
    """)

    # Store monitored players with time limits and channel/guild scope
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitored_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ff_uid INTEGER,
            channel_id INTEGER,
            nickname TEXT,
            monitoring_start TEXT,
            monitoring_end TEXT,
            reason TEXT,
            added_by INTEGER,
            added_at TEXT,
            active BOOLEAN DEFAULT TRUE,
            UNIQUE(ff_uid, channel_id)
        )
    """)

    # Migrate old monitored_players schema if the table exists without the new channel_id column
    cursor.execute("PRAGMA table_info(monitored_players)")
    columns = [column[1] for column in cursor.fetchall()]
    if "channel_id" not in columns:
        cursor.execute("ALTER TABLE monitored_players RENAME TO monitored_players_old")
        cursor.execute("""
            CREATE TABLE monitored_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ff_uid INTEGER,
                channel_id INTEGER,
                nickname TEXT,
                monitoring_start TEXT,
                monitoring_end TEXT,
                reason TEXT,
                added_by INTEGER,
                added_at TEXT,
                active BOOLEAN DEFAULT TRUE,
                UNIQUE(ff_uid, channel_id)
            )
        """)
        cursor.execute(
            """INSERT OR REPLACE INTO monitored_players 
               (ff_uid, channel_id, nickname, monitoring_start, monitoring_end, reason, added_by, added_at, active)
               SELECT ff_uid, NULL, nickname, monitoring_start, monitoring_end, reason, added_by, added_at, active FROM monitored_players_old"""
        )
        cursor.execute("DROP TABLE monitored_players_old")

    # Migration: Add ignore_until column if it doesn't exist
    try:
        cursor.execute("PRAGMA table_info(monitored_players)")
        columns = [column[1] for column in cursor.fetchall()]
        if "ignore_until" not in columns:
            print("🔄 Migrating database: Adding ignore_until column to monitored_players...")
            cursor.execute("ALTER TABLE monitored_players ADD COLUMN ignore_until TEXT")
            conn.commit()
            print("✅ Migration complete: ignore_until column added")
    except Exception as e:
        print(f"⚠️ Migration warning: {e}")

    # Log monitored player activities
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitored_player_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ff_uid INTEGER,
            activity_type TEXT,
            clan_id INTEGER,
            clan_name TEXT,
            details TEXT,
            detected_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_last_roster(clan_id):
    """Retrieve the last known roster UIDs for a guild.

    Args:
        clan_id (int): The Free Fire guild ID.

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
        clan_id (int): The Free Fire guild ID.
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


def add_flagged_clan(clan_id, reason="Partnered guild monitoring"):
    """Add a clan ID to the partnered list.

    Args:
        clan_id (int): The clan ID to flag.
        reason (str): Reason for flagging.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO flagged_clans (clan_id, flagged_at, reason) VALUES (?, ?, ?)",
            (clan_id, get_ist_timestamp(), reason),
        )
        conn.commit()
        conn.close()
        print(f"✅ Partnered guild {clan_id} for monitoring: {reason}")
    except Exception as e:
        print(f"Error adding flagged clan: {e}")


def get_flagged_clans():
    """Get all partnered guild IDs.

    Returns:
        set: Set of partnered guild IDs.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT clan_id FROM flagged_clans")
        rows = cursor.fetchall()
        conn.close()
        return {row[0] for row in rows}
    except Exception as e:
        print(f"Error retrieving flagged clans: {e}")
        return set()


def check_flagged_movement(ff_uid, from_clan_id, nickname=None):
    """Check if a player who left has joined a partnered guild.

    Args:
        ff_uid (int): The player's Free Fire UID.
        from_clan_id (int): The guild they left from.
        nickname (str): The player's nickname.

    Returns:
        dict or None: Partnered movement info if detected, None otherwise.
    """
    try:
        from member_clan_api import get_player_clan_info
        current_clan_info = get_player_clan_info(ff_uid)

        if not current_clan_info or not current_clan_info.get("clanId"):
            return None

        current_clan_id = int(current_clan_info["clanId"])
        flagged_clans = get_flagged_clans()

        if current_clan_id in flagged_clans:
            if has_permission(ff_uid):
                print(f"      ✅ Permission granted for UID {ff_uid} to join partnered guild {current_clan_id}; skipping partnered alert")
                return None

            # Player joined a partnered guild - log this movement
            movement = {
                "ff_uid": ff_uid,
                "nickname": nickname,
                "from_clan_id": from_clan_id,
                "to_clan_id": current_clan_id,
                "to_clan_name": current_clan_info.get("clanName"),
                "detected_at": get_ist_timestamp()
            }

            # Log the partnered movement
            log_flagged_movement(**movement)
            return movement

        return None
    except Exception as e:
        print(f"Error checking partnered movement for UID {ff_uid}: {e}")
        return None


def log_flagged_movement(ff_uid, nickname, from_clan_id, to_clan_id, to_clan_name, detected_at):
    """Log a partnered player movement.

    Args:
        ff_uid (int): Player UID.
        nickname (str): Player nickname.
        from_clan_id (int): Guild they left.
        to_clan_id (int): Partnered guild they joined.
        to_clan_name (str): Name of the partnered guild.
        detected_at (str): Timestamp.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO flagged_movements 
               (ff_uid, nickname, from_clan_id, to_clan_id, detected_at)
               VALUES (?, ?, ?, ?, ?)""",
            (ff_uid, nickname, from_clan_id, to_clan_id, detected_at),
        )
        conn.commit()
        conn.close()

        # Immediate alert
        alert_message = (
            f"🚨 **PARTNERED MOVEMENT DETECTED**\n"
            f"Player `{nickname or 'Unknown'}` (UID: `{ff_uid}`)\n"
            f"Left guild `{from_clan_id}` → Joined partnered guild `{to_clan_name}` (ID: `{to_clan_id}`)\n"
            f"Time: {detected_at}"
        )
        print(f"\n{alert_message}\n")

    except Exception as e:
        print(f"Error logging partnered movement: {e}")


def grant_permission(ff_uid, channel_id, granted_by, remarks=None):
    """Grant permission for a player to join a partnered guild."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(1) FROM granted_permissions WHERE ff_uid = ? AND channel_id = ? AND active = TRUE",
            (ff_uid, channel_id)
        )
        if cursor.fetchone()[0] > 0:
            conn.close()
            return False

        cursor.execute(
            "INSERT INTO granted_permissions (ff_uid, channel_id, granted_by, remarks, granted_at, active) VALUES (?, ?, ?, ?, ?, TRUE)",
            (ff_uid, channel_id, granted_by, remarks, get_ist_timestamp())
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error granting permission for UID {ff_uid}: {e}")
        return False


def has_permission(ff_uid, channel_id=None):
    """Check whether a player has active permission to join a partnered guild."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if channel_id is None:
            cursor.execute(
                "SELECT active FROM granted_permissions WHERE ff_uid = ? ORDER BY granted_at DESC LIMIT 1",
                (ff_uid,)
            )
        else:
            cursor.execute(
                "SELECT active FROM granted_permissions WHERE ff_uid = ? AND (channel_id = ? OR channel_id IS NULL) ORDER BY granted_at DESC LIMIT 1",
                (ff_uid, channel_id)
            )
        row = cursor.fetchone()
        conn.close()
        return bool(row[0]) if row else False
    except Exception as e:
        print(f"Error checking permission for UID {ff_uid}: {e}")
        return False


def add_monitored_player(ff_uid, nickname, duration_hours, added_by, channel_id=None):
    """Add a player to the monitoring list.

    Args:
        ff_uid (int): Free Fire UID to monitor.
        nickname (str): Player nickname.
        duration_hours (int or None): Hours to monitor (max 4380), or None for indefinite monitoring.
        added_by (int): Discord user ID who added the monitoring.
        channel_id (int): Discord channel ID tied to the monitored guild.

    Returns:
        bool: True if added successfully, False otherwise.
    """
    try:
        from datetime import datetime, timedelta
        start_time = get_ist_now()

        end_time = None
        duration_text = "indefinitely"
        if duration_hours is not None:
            duration_hours = min(duration_hours, 4380)
            end_time = start_time + timedelta(hours=duration_hours)
            duration_text = f"for {duration_hours} hours"

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO monitored_players 
               (ff_uid, channel_id, nickname, monitoring_start, monitoring_end, reason, added_by, added_at, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ff_uid, channel_id, nickname, get_ist_timestamp(), end_time.isoformat() if end_time else None, None, added_by, get_ist_timestamp(), True),
        )
        conn.commit()
        conn.close()

        print(f"👁️ Added player {nickname} (UID: {ff_uid}) to monitoring {duration_text}")
        return True
    except Exception as e:
        print(f"Error adding monitored player: {e}")
        return False


def remove_monitored_player(ff_uid, channel_id=None):
    """Remove a player from monitoring.

    Args:
        ff_uid (int): Free Fire UID to stop monitoring.
        channel_id (int): Discord channel ID to scope removal to a specific guild.

    Returns:
        bool: True if removed successfully, False otherwise.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if channel_id is not None:
            cursor.execute("UPDATE monitored_players SET active = FALSE WHERE ff_uid = ? AND channel_id = ?", (ff_uid, channel_id))
        else:
            cursor.execute("UPDATE monitored_players SET active = FALSE WHERE ff_uid = ?", (ff_uid,))
        conn.commit()
        conn.close()
        print(f"❌ Removed player UID {ff_uid} from monitoring")
        return True
    except Exception as e:
        print(f"Error removing monitored player: {e}")
        return False


def ignore_monitored_player(ff_uid, ignore_hours, channel_id=None):
    """Ignore monitoring for a player for a specified number of hours.

    Args:
        ff_uid (int): Free Fire UID to ignore monitoring for.
        ignore_hours (int): Hours to ignore monitoring (max 168 hours = 1 week).
        channel_id (int): Discord channel ID to scope the ignore to a specific guild.

    Returns:
        bool: True if ignored successfully, False otherwise.
    """
    try:
        from datetime import datetime, timedelta
        ignore_hours = min(ignore_hours, 168)  # Max 1 week
        ignore_until = get_ist_now() + timedelta(hours=ignore_hours)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if channel_id is not None:
            cursor.execute(
                "UPDATE monitored_players SET ignore_until = ? WHERE ff_uid = ? AND channel_id = ? AND active = TRUE",
                (ignore_until.isoformat(), ff_uid, channel_id)
            )
        else:
            cursor.execute(
                "UPDATE monitored_players SET ignore_until = ? WHERE ff_uid = ? AND active = TRUE",
                (ignore_until.isoformat(), ff_uid)
            )
        updated = cursor.rowcount
        conn.commit()
        conn.close()

        if updated > 0:
            print(f"🚫 Ignored monitoring for player UID {ff_uid} for {ignore_hours} hours")
            return True
        return False
    except Exception as e:
        print(f"Error ignoring monitored player: {e}")
        return False


def unignore_monitored_player(ff_uid, channel_id=None):
    """Stop ignoring monitoring for a player.

    Args:
        ff_uid (int): Free Fire UID to stop ignoring.
        channel_id (int): Discord channel ID to scope the unignore to a specific guild.

    Returns:
        bool: True if unignored successfully, False otherwise.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if channel_id is not None:
            cursor.execute(
                "UPDATE monitored_players SET ignore_until = NULL WHERE ff_uid = ? AND channel_id = ? AND active = TRUE",
                (ff_uid, channel_id)
            )
        else:
            cursor.execute(
                "UPDATE monitored_players SET ignore_until = NULL WHERE ff_uid = ? AND active = TRUE",
                (ff_uid,)
            )
        updated = cursor.rowcount
        conn.commit()
        conn.close()

        if updated > 0:
            print(f"✅ Stopped ignoring monitoring for player UID {ff_uid}")
            return True
        return False
    except Exception as e:
        print(f"Error unignoring monitored player: {e}")
        return False


def is_player_ignored(ff_uid, channel_id=None):
    """Check if a player is currently being ignored for monitoring.

    Args:
        ff_uid (int): Free Fire UID to check.
        channel_id (int): Discord channel ID to scope the check to a specific guild.

    Returns:
        bool: True if player is currently ignored, False otherwise.
    """
    try:
        from datetime import datetime
        now = get_ist_now()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if channel_id is not None:
            cursor.execute(
                "SELECT ignore_until FROM monitored_players WHERE ff_uid = ? AND channel_id = ? AND active = TRUE",
                (ff_uid, channel_id)
            )
        else:
            cursor.execute(
                "SELECT ignore_until FROM monitored_players WHERE ff_uid = ? AND active = TRUE",
                (ff_uid,)
            )
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            ignore_until = datetime.fromisoformat(row[0])
            return ignore_until > now
        return False
    except Exception as e:
        print(f"Error checking if player is ignored: {e}")
        return False


def get_monitored_players(channel_id=None):
    """Get all active monitored players.

    Args:
        channel_id (int): Discord channel ID to scope the result to a specific guild.

    Returns:
        list: List of monitored player records.
    """
    try:
        from datetime import datetime
        now = get_ist_now()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if channel_id is not None:
            cursor.execute(
                "SELECT ff_uid, nickname, monitoring_start, monitoring_end, added_by FROM monitored_players WHERE active = TRUE AND channel_id = ?",
                (channel_id,)
            )
        else:
            cursor.execute(
                "SELECT ff_uid, nickname, monitoring_start, monitoring_end, added_by FROM monitored_players WHERE active = TRUE"
            )
        rows = cursor.fetchall()
        conn.close()

        active_players = []
        for row in rows:
            ff_uid = row[0]
            # Skip players who are currently ignored
            if is_player_ignored(ff_uid, channel_id):
                continue

            end_time_str = row[3]
            if end_time_str is None:
                active_players.append({
                    "ff_uid": row[0],
                    "nickname": row[1],
                    "monitoring_start": row[2],
                    "monitoring_end": "Indefinite",
                    "added_by": row[4],
                })
                continue

            end_time = datetime.fromisoformat(end_time_str)
            if end_time > now:  # Still active
                active_players.append({
                    "ff_uid": row[0],
                    "nickname": row[1],
                    "monitoring_start": row[2],
                    "monitoring_end": end_time_str,
                    "added_by": row[4],
                })

        return active_players
    except Exception as e:
        print(f"Error retrieving monitored players: {e}")
        return []


def is_player_monitored(ff_uid, channel_id=None):
    """Check if a player is currently being monitored.

    Args:
        ff_uid (int): Free Fire UID to check.
        channel_id (int): Discord channel ID to scope the check to a specific guild.

    Returns:
        bool: True if player is actively monitored, False otherwise.
    """
    try:
        from datetime import datetime
        now = get_ist_now()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if channel_id is not None:
            cursor.execute(
                "SELECT monitoring_end FROM monitored_players WHERE ff_uid = ? AND channel_id = ? AND active = TRUE",
                (ff_uid, channel_id)
            )
        else:
            cursor.execute(
                "SELECT monitoring_end FROM monitored_players WHERE ff_uid = ? AND active = TRUE",
                (ff_uid,)
            )
        row = cursor.fetchone()
        conn.close()

        if row:
            if row[0] is None:
                return True
            end_time = datetime.fromisoformat(row[0])
            return end_time > now
        return False
    except Exception as e:
        print(f"Error checking if player is monitored: {e}")
        return False


def log_monitored_player_activity(ff_uid, activity_type, clan_id=None, clan_name=None, details=None):
    """Log activity for a monitored player.

    Args:
        ff_uid (int): Player UID.
        activity_type (str): Type of activity (joined_guild, left_guild, etc.).
        clan_id (int): Guild ID involved.
        clan_name (str): Guild name.
        details (str): Additional details.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO monitored_player_activity 
               (ff_uid, activity_type, clan_id, clan_name, details, detected_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ff_uid, activity_type, clan_id, clan_name, details, get_ist_timestamp()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging monitored player activity: {e}")


def check_monitored_player_activity(ff_uid, change_type, clan_id, nickname=None):
    """Check and log activity for monitored players.

    Args:
        ff_uid (int): Player UID.
        change_type (str): "joined" or "left".
        clan_id (int): Guild ID where change occurred.
        nickname (str): Player nickname.
    """
    if not is_player_monitored(ff_uid):
        return

    try:
        # Get clan name
        clan_name = None
        try:
            from member_clan_api import get_player_clan_info
            # For joined players, they're now in this guild
            # For left players, we need to get their current guild
            if change_type == "joined":
                clan_name = f"Guild {clan_id}"  # We don't have guild name here
            else:
                # For left players, check their current guild
                current_info = get_player_clan_info(ff_uid)
                if current_info:
                    clan_name = current_info.get("clanName", f"Guild {current_info.get('clanId', 'Unknown')}")
        except:
            clan_name = f"Guild {clan_id}"

        # Log the activity
        activity_type = f"{change_type}_guild"
        details = f"Player {nickname or 'Unknown'} {change_type} guild {clan_id}"
        log_monitored_player_activity(ff_uid, activity_type, clan_id, clan_name, details)

        # Send alert
        alert_msg = f"👁️ **MONITORED PLAYER ACTIVITY**\n"
        alert_msg += f"Player `{nickname or 'Unknown'}` (UID: `{ff_uid}`)\n"
        alert_msg += f"Action: {change_type.upper()} guild `{clan_name}` (ID: `{clan_id}`)\n"
        alert_msg += f"Time: {get_ist_timestamp()}"

        print(f"\n{alert_msg}\n")

    except Exception as e:
        print(f"Error checking monitored player activity: {e}")


def cleanup_expired_monitoring():
    """Clean up expired player monitoring entries."""
    try:
        from datetime import datetime
        now = get_ist_now()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE monitored_players SET active = FALSE WHERE monitoring_end IS NOT NULL AND monitoring_end < ?", (now.isoformat(),))
        expired_count = cursor.rowcount
        conn.commit()
        conn.close()

        if expired_count > 0:
            print(f"🧹 Cleaned up {expired_count} expired player monitoring entries")
    except Exception as e:
        print(f"Error cleaning up expired monitoring: {e}")


def log_membership_change(clan_id, ff_uid, change_type, nickname=None):
    """Log a membership change event.

    Args:
        clan_id (int): The Free Fire guild ID.
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
        api_response (dict): Response from the memberGuild API.
        clan_id (int): The Free Fire guild ID.

    Returns:
        dict: {"joined": list, "left": list} with member nicknames.
    """
    try:
        current_uids = get_list_uids(api_response)
        previous_uids = get_last_roster(clan_id)

        changes = detect_list_changes(current_uids, previous_uids)

        # Log joins
        for uid in changes["joined"]:
            member = next(
                (m for m in api_response.get("members", []) if m.get("account_id") == uid),
                None,
            )
            nickname = member.get("nickname") if member else None
            log_membership_change(clan_id, uid, "joined", nickname)
            print(f"  ✅ JOINED: {nickname or 'Unknown'} (UID: {uid})")

            # Check monitored player activity
            check_monitored_player_activity(uid, "joined", clan_id, nickname)

        # Log leaves
        left_members = []
        for uid in changes["left"]:
            # Try to get player info from the player info API
            nickname = None
            try:
                player_info = fetch_player_info(uid)
                if player_info and "basicInfo" in player_info and "nickname" in player_info["basicInfo"]:
                    nickname = player_info["basicInfo"]["nickname"]
            except MemberClanAPIError as e:
                print(f"  ⚠️ Could not fetch player info for UID {uid}: {e}")
            
            log_membership_change(clan_id, uid, "left", nickname)
            print(f"  ❌ LEFT: {nickname or 'Unknown'} (UID: {uid})")
            
            # Check for partnered movement (player joined a partnered clan)
            flagged_movement = check_flagged_movement(uid, clan_id, nickname)
            if flagged_movement:
                print(f"  🚨 PARTNERED: Player moved to partnered clan {flagged_movement['to_clan_name']}!")
            
            # Check monitored player activity
            check_monitored_player_activity(uid, "left", clan_id, nickname)
            
            left_members.append({"uid": uid, "nickname": nickname})

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
            "left": left_members,
        }
    except Exception as e:
        print(f"Error checking roster changes: {e}")
        return {"joined": [], "left": []}


def monitor_clan_roster(access_token, clan_id):
    """Execute a single roster check cycle.

    Args:
        access_token (str): API access token.
        clan_id (int): Free Fire guild ID.

    Returns:
        dict: Result containing joined/left members, or error info.
    """
    try:
        # Clean up expired monitoring entries
        cleanup_expired_monitoring()

        print(f"\n[{get_ist_now().strftime('%Y-%m-%d %H:%M:%S IST')}] Checking guild {clan_id}...")
        api_response = fetch_member_guild(access_token, timeout=45, retries=1)
        changes = check_roster_changes(api_response, clan_id)
        members = [
            {
                "uid": member.get("account_id"),
                "nickname": member.get("nickname"),
            }
            for member in api_response.get("members", [])
            if member.get("account_id")
        ]
        return {"status": "success", "changes": changes, "members": members}
    except MemberClanAPIError as e:
        print(f"  ❌ API Error: {e}")
        return {"status": "error", "error": str(e)}
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return {"status": "error", "error": str(e)}


def get_recent_changes(clan_id, limit=20):
    """Retrieve recent membership changes for a guild.

    Args:
        clan_id (int): The Free Fire guild ID.
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


def initialize_flagged_clans():
    """Initialize the partnered guilds list with the provided guild IDs."""
    flagged_clan_ids = [
        60740304, 61131109, 61639952, 60618087, 60993239, 62467926,
        63299215, 62009747, 63582136, 64108372, 65089147, 3009325153,
        61369463, 62439929, 3008075139, 3014128530
    ]

    for clan_id in flagged_clan_ids:
        add_flagged_clan(clan_id, "Partnered guild - immediate flagging required")


def get_flagged_movements(limit=50):
    """Get recent partnered player movements.

    Args:
        limit (int): Maximum number of records to return.

    Returns:
        list: Recent partnered movement records.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT ff_uid, nickname, from_clan_id, to_clan_id, detected_at
               FROM flagged_movements
               ORDER BY detected_at DESC
               LIMIT ?""",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "uid": row[0],
                "nickname": row[1],
                "from_clan_id": row[2],
                "to_clan_id": row[3],
                "timestamp": row[4],
            }
            for row in rows
        ]
    except Exception as e:
        print(f"Error retrieving partnered movements: {e}")
        return []


# Initialize DB on import
init_monitoring_db()

# Initialize flagged clans
initialize_flagged_clans()
