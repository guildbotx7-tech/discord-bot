import pytest

from member_clan_api import (
    create_discord_uid_mapping,
    detect_roster_changes,
    get_member_by_uid,
    get_roster_uids,
    record_membership_change,
)

SAMPLE_API_RESPONSE = {
    "clan_id": 63582136,
    "members": [
        {"account_id": 497528944, "like": 12176, "nickname": "1nOnlyAimzen"},
        {"account_id": 502945876, "like": 15287, "nickname": "NO\u3164MORE\u1d33\u1d3c\u1d30"},
        {"account_id": 15105112634, "like": 20, "nickname": "GuildBot#09"},
    ],
    "nickname": "GuildBot",
    "platform": "Google",
    "region": "IND",
    "uid": 15105112634,
}


def test_get_roster_uids_returns_set_of_account_ids():
    """Extract UIDs from current roster."""
    uids = get_roster_uids(SAMPLE_API_RESPONSE)

    assert isinstance(uids, set)
    assert 497528944 in uids
    assert 502945876 in uids
    assert 15105112634 in uids
    assert len(uids) == 3


def test_detect_roster_changes_identifies_joins_and_leaves():
    """Detect who joined and who left the clan."""
    current = {497528944, 502945876, 15105112634, 999999999}  # 999999999 is new
    previous = {497528944, 502945876, 888888888}  # 888888888 left

    changes = detect_roster_changes(current, previous)

    assert changes["joined"] == {15105112634, 999999999}
    assert changes["left"] == {888888888}


def test_get_member_by_uid_retrieves_full_member_data():
    """Get complete member object by UID."""
    member = get_member_by_uid(SAMPLE_API_RESPONSE, 497528944)

    assert member is not None
    assert member["nickname"] == "1nOnlyAimzen"
    assert member["like"] == 12176


def test_get_member_by_uid_returns_none_if_not_found():
    """Return None for non-existent UID."""
    member = get_member_by_uid(SAMPLE_API_RESPONSE, 999999999)
    assert member is None


def test_create_discord_uid_mapping_records_link():
    """Create a Discord-to-Free Fire UID mapping."""
    mapping = create_discord_uid_mapping(123456789, 497528944)

    assert mapping["discord_id"] == 123456789
    assert mapping["ff_uid"] == 497528944
    assert "linked_at" in mapping


def test_record_membership_change_logs_event():
    """Record when a member joins or leaves."""
    join_event = record_membership_change(497528944, "joined", clan_id=63582136)

    assert join_event["ff_uid"] == 497528944
    assert join_event["change_type"] == "joined"
    assert join_event["clan_id"] == 63582136
    assert "timestamp" in join_event

