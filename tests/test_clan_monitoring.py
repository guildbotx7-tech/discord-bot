"""Tests for clan monitoring background task."""

import json
import sqlite3
from pathlib import Path

import pytest

from clan_monitoring import (
    check_roster_changes,
    get_last_roster,
    get_recent_changes,
    init_monitoring_db,
    log_membership_change,
    save_roster_snapshot,
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


@pytest.fixture
def test_db(tmp_path):
    """Use a temporary database for tests."""
    import clan_monitoring

    original_db = clan_monitoring.DB_PATH
    test_db_path = tmp_path / "test_clan_monitoring.db"
    clan_monitoring.DB_PATH = test_db_path

    init_monitoring_db()

    yield test_db_path

    clan_monitoring.DB_PATH = original_db


def test_save_and_retrieve_roster_snapshot(test_db):
    """Save and retrieve a roster snapshot."""
    clan_id = 63582136
    uids = {497528944, 502945876, 15105112634}

    save_roster_snapshot(clan_id, uids)
    retrieved = get_last_roster(clan_id)

    assert retrieved == uids


def test_detect_roster_changes_with_state(test_db):
    """Detect changes between two roster checks."""
    clan_id = 63582136

    # First check - save initial state
    save_roster_snapshot(clan_id, {497528944, 502945876})

    # Second check - member joined, one left
    api_response_v2 = {
        "clan_id": clan_id,
        "members": [
            {"account_id": 497528944, "nickname": "1nOnlyAimzen"},
            {"account_id": 999999999, "nickname": "NewMember"},
        ],
    }

    changes = check_roster_changes(api_response_v2, clan_id)

    assert 999999999 in [c["uid"] for c in changes["joined"]]
    assert 502945876 in [c["uid"] for c in changes["left"]]


def test_log_and_retrieve_membership_changes(test_db):
    """Log membership changes and retrieve them."""
    clan_id = 63582136

    log_membership_change(clan_id, 497528944, "joined", "1nOnlyAimzen")
    log_membership_change(clan_id, 502945876, "left")

    recent = get_recent_changes(clan_id, limit=10)

    assert len(recent) == 2
    assert recent[0]["uid"] == 502945876
    assert recent[0]["change_type"] == "left"
    assert recent[1]["uid"] == 497528944
    assert recent[1]["nickname"] == "1nOnlyAimzen"


def test_initial_roster_snapshot(test_db):
    """First check should have empty previous roster."""
    clan_id = 63582136

    changes = check_roster_changes(SAMPLE_API_RESPONSE, clan_id)

    # First time = all are "new joins"
    assert len(changes["joined"]) == 3
    assert len(changes["left"]) == 0
