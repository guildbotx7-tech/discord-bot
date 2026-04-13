"""Background task for monitoring Free Fire clan membership changes using MongoDB.

Continuously fetches the clan roster and detects/logs join/leave events.
"""

import json
from datetime import datetime
from mongodb import get_collection, insert_document, find_document, update_document, find_documents

# MongoDB collections
ROSTER_SNAPSHOTS = "clan_roster_snapshots"
MEMBERSHIP_CHANGES = "clan_membership_changes"


def init_monitoring_db():
    """Initialize MongoDB collections (replaces SQLite init)."""
    try:
        from mongodb import create_index
        create_index(ROSTER_SNAPSHOTS, "clan_id", unique=True)
        create_index(MEMBERSHIP_CHANGES, "clan_id")
        create_index(MEMBERSHIP_CHANGES, "detected_at")
        print("✅ Clan monitoring MongoDB collections initialized")
    except Exception as e:
        print(f"⚠️ Clan monitoring initialization warning: {e}")


def get_last_roster(clan_id):
    """Retrieve the last known roster UIDs for a clan.

    Args:
        clan_id (int): The Free Fire clan ID.

    Returns:
        set: UIDs from last snapshot, or empty set if none exists.
    """
    try:
        doc = find_document(ROSTER_SNAPSHOTS, {"clan_id": clan_id})
        if doc and doc.get("uids"):
            return set(doc["uids"])
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
        doc = {
            "clan_id": clan_id,
            "uids": list(uids),
            "last_checked": datetime.utcnow().isoformat()
        }
        
        existing = find_document(ROSTER_SNAPSHOTS, {"clan_id": clan_id})
        if existing:
            update_document(ROSTER_SNAPSHOTS, {"clan_id": clan_id}, doc)
        else:
            insert_document(ROSTER_SNAPSHOTS, doc)
    except Exception as e:
        print(f"Error saving roster snapshot: {e}")


def log_membership_change(clan_id, ff_uid, change_type, nickname=None):
    """Log a membership change event.

    Args:
        clan_id (int): The Free Fire clan ID.
        ff_uid (int): The Free Fire UID.
        change_type (str): "joined" or "left".
        nickname (str, optional): Player name. Defaults to None.
    """
    try:
        doc = {
            "clan_id": clan_id,
            "ff_uid": ff_uid,
            "change_type": change_type,
            "nickname": nickname,
            "detected_at": datetime.utcnow().isoformat()
        }
        insert_document(MEMBERSHIP_CHANGES, doc)
    except Exception as e:
        print(f"Error logging membership change: {e}")


def get_recent_changes(clan_id, limit=50):
    """Get recent membership changes for a clan.

    Args:
        clan_id (int): The Free Fire clan ID.
        limit (int): Maximum results to return. Defaults to 50.

    Returns:
        list: Membership change records.
    """
    try:
        changes = find_documents(MEMBERSHIP_CHANGES, {"clan_id": clan_id})
        # Sort by detected_at descending and limit
        sorted_changes = sorted(
            changes, 
            key=lambda x: x.get("detected_at", ""), 
            reverse=True
        )[:limit]
        return sorted_changes
    except Exception as e:
        print(f"Error retrieving membership changes: {e}")
        return []


def record_membership_change(clan_id, ff_uid, change_type, nickname=None):
    """Record a membership change (wrapper for log_membership_change)."""
    log_membership_change(clan_id, ff_uid, change_type, nickname)


def check_roster_changes(api_response, clan_id):
    """Check for roster changes and update database.

    Args:
        api_response (dict): API response from memberClan API.
        clan_id (int): Free Fire clan ID.

    Returns:
        dict: {"joined": list, "left": list} with member info.
    """
    try:
        from member_clan_api import get_roster_uids, detect_roster_changes, get_member_by_uid
        
        current_uids = get_roster_uids(api_response)
        previous_uids = get_last_roster(clan_id)
        
        changes = detect_roster_changes(current_uids, previous_uids)
        
        # Log changes
        for uid in changes["joined"]:
            member_data = get_member_by_uid(api_response, uid)
            nickname = member_data.get("nickname") if member_data else None
            log_membership_change(clan_id, uid, "joined", nickname)
            
        for uid in changes["left"]:
            log_membership_change(clan_id, uid, "left")
        
        # Save current roster
        save_roster_snapshot(clan_id, current_uids)
        
        # Convert sets to lists for return
        return {
            "joined": list(changes["joined"]),
            "left": list(changes["left"])
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
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking clan {clan_id}...")
        from member_clan_api import fetch_member_clan
        api_response = fetch_member_clan(access_token)
        changes = check_roster_changes(api_response, clan_id)
        return {"status": "success", "changes": changes}
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {"status": "error", "error": str(e)}


# Initialize DB on import
init_monitoring_db()
