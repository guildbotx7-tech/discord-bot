"""Secure token management for guild monitoring.

Only the bot owner can manage and register access tokens.
Tokens are NEVER logged, displayed, or exposed in any way.
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "discord_bot.db"


class TokenStorageError(Exception):
    """Raised when token storage operations fail."""


def init_token_db():
    """Initialize token storage tables (handled by guild_monitoring.py)."""
    # Tables are now created by guild_monitoring.init_monitoring_db()
    pass


def _get_token_from_env():
    """Retrieve token from environment variable (internal only).

    Never call this function from user-facing code.
    Uses GUILD_ACCESS_TOKEN environment variable.
    """
    return os.getenv('GUILD_ACCESS_TOKEN')


def register_token(guild_id, channel_id, owner_id):
    """Register the guild monitoring token for this server (single-server bot).

    The token itself should be in GUILD_ACCESS_TOKEN environment variable.
    This just records the registration.

    Args:
        guild_id (int): Discord guild ID.
        channel_id (int): Discord channel ID (for notification channel).
        owner_id (int): Discord user ID of the owner.

    Returns:
        bool: True if registered successfully.

    Raises:
        TokenStorageError: If token not found in environment.
    """
    # Verify token exists in environment
    token = _get_token_from_env()
    if not token:
        raise TokenStorageError(
            "GUILD_ACCESS_TOKEN not found in environment. "
            "Set GUILD_ACCESS_TOKEN=your_token_here in .env file"
        )

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO access_tokens
               (guild_id, channel_id, registered_by, registered_at)
               VALUES (?, ?, ?, ?)""",
            (guild_id, channel_id, owner_id, datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        raise TokenStorageError(f"Failed to register token: {e}") from e


def get_token_for_guild(guild_id):
    """Get the registered token for a guild.

    Args:
        guild_id (int): Discord guild ID.

    Returns:
        str or None: The access token if registered, None otherwise.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT guild_id FROM access_tokens WHERE guild_id = ?",
            (guild_id,)
        )
        result = cursor.fetchone()
        conn.close()

        if result:
            # Return the token from environment
            return _get_token_from_env()
        return None
    except Exception:
        return None


def is_token_registered(guild_id):
    """Check if a token is registered for the guild.

    Args:
        guild_id (int): Discord guild ID.

    Returns:
        bool: True if token is registered.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT guild_id FROM access_tokens WHERE guild_id = ?",
            (guild_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception:
        return False


def unregister_token(guild_id):
    """Remove token registration for a guild.

    Args:
        guild_id (int): Discord guild ID.

    Returns:
        bool: True if successfully unregistered.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM access_tokens WHERE guild_id = ?",
            (guild_id,)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_registered_guilds():
    """Get list of guilds with registered tokens.

    Returns:
        list: List of guild IDs with registered tokens.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT guild_id FROM access_tokens")
        results = cursor.fetchall()
        conn.close()
        return [row[0] for row in results]
    except Exception:
        return []