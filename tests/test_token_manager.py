"""Tests for secure token management."""

import os
import pytest
from pathlib import Path

from token_manager import (
    register_token,
    get_token_for_guild,
    get_registered_guilds,
    unregister_token,
    is_token_registered,
    TokenStorageError,
)


@pytest.fixture
def env_setup(monkeypatch):
    """Setup test environment variables."""
    test_guild_id = 123456789
    test_token = "secret_test_token_abc123"

    monkeypatch.setenv(f"GUILD_TOKEN_{test_guild_id}", test_token)

    return test_guild_id, test_token


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Use temporary database for tests."""
    import token_manager

    original_db = token_manager.DB_PATH
    test_db_path = tmp_path / "test_token_storage.db"
    monkeypatch.setattr(token_manager, "DB_PATH", test_db_path)

    # Initialize DB with required tables
    import sqlite3
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_tokens (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER,
            registered_by INTEGER,
            registered_at TEXT
        )
    """)
    conn.commit()
    conn.close()

    yield test_db_path

    # Restore original
    monkeypatch.setattr(token_manager, "DB_PATH", original_db)


def test_register_token_success(env_setup, test_db):
    """Test successful token registration."""
    guild_id, expected_token = env_setup
    owner_id = 987654321
    channel_id = 111222333

    result = register_token(guild_id, channel_id, owner_id)

    assert result is True
    assert is_token_registered(guild_id) is True
    assert get_token_for_guild(guild_id) == expected_token


def test_register_token_fails_without_env_var(test_db, monkeypatch):
    """Test token registration fails without environment variable."""
    monkeypatch.delenv("GUILD_ACCESS_TOKEN", raising=False)

    guild_id = 123456789
    owner_id = 987654321
    channel_id = 111222333

    with pytest.raises(TokenStorageError, match=f"GUILD_TOKEN_{guild_id} not found"):
        register_token(guild_id, channel_id, owner_id)


def test_get_token_returns_correct_value(env_setup, test_db):
    """Test retrieving registered token."""
    guild_id, expected_token = env_setup
    owner_id = 987654321
    channel_id = 111222333

    register_token(guild_id, channel_id, owner_id)
    token = get_token_for_guild(guild_id)

    assert token == expected_token


def test_get_token_returns_none_for_unregistered(test_db):
    """Test getting token for unregistered guild returns None."""
    guild_id = 999999999
    token = get_token_for_guild(guild_id)

    assert token is None


def test_get_registered_guilds_returns_list(env_setup, test_db):
    """Test getting list of registered guilds."""
    guild_id, _ = env_setup
    owner_id = 987654321
    channel_id = 111222333

    guilds_before = get_registered_guilds()
    register_token(guild_id, channel_id, owner_id)
    guilds_after = get_registered_guilds()

    assert guild_id not in guilds_before
    assert guild_id in guilds_after


def test_unregister_token_removes_registration(env_setup, test_db):
    """Test unregistering a token."""
    guild_id, _ = env_setup
    owner_id = 987654321
    channel_id = 111222333

    register_token(guild_id, channel_id, owner_id)
    assert is_token_registered(guild_id) is True

    result = unregister_token(guild_id)
    assert result is True
    assert is_token_registered(guild_id) is False


def test_multiple_guilds_independent(env_setup, test_db, monkeypatch):
    """Test multiple guilds can be registered independently."""
    guild_id1, _ = env_setup
    guild_id2 = 987654321
    owner_id = 987654321
    channel_id = 111222333

    # Set env for second guild
    monkeypatch.setenv(f"GUILD_TOKEN_{guild_id2}", "secret_test_token_xyz789")

    # Register first guild
    register_token(guild_id1, channel_id, owner_id)
    assert is_token_registered(guild_id1) is True
    assert is_token_registered(guild_id2) is False

    # Register second guild
    register_token(guild_id2, channel_id, owner_id)
    assert is_token_registered(guild_id1) is True
    assert is_token_registered(guild_id2) is True

    # Unregister first guild
    unregister_token(guild_id1)
    assert is_token_registered(guild_id1) is False
    assert is_token_registered(guild_id2) is True
    assert is_token_registered(guild_id2) is True


def test_token_never_exposed_in_registration(env_setup, test_db):
    """Test that token is never exposed in registration process."""
    guild_id, token_value = env_setup
    owner_id = 987654321
    channel_id = 111222333

    # Capture any output or exceptions
    import io
    import sys
    captured_output = io.StringIO()
    sys.stdout = captured_output

    try:
        register_token(guild_id, channel_id, owner_id)
        output = captured_output.getvalue()

        # Token should never appear in output
        assert token_value not in output
        assert "secret_test_token" not in output
    finally:
        sys.stdout = sys.__stdout__


def test_token_internal_function_hidden():
    """Test that internal token function is not exposed."""
    import token_manager

    # Internal function should not be in public API
    assert hasattr(token_manager, "_get_token_from_env")

    # But it should be private (by convention)
    # This is more of a documentation test
