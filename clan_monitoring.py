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
