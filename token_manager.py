"""Secure token management for server monitoring.

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
    """Initialize token storage tables (handled by server_monitoring.py)."""
    # Tables are now created by server_monitoring.init_monitoring_db()
    pass


def _get_token_from_env(guild_id):
    """Retrieve token from environment variable (internal only).

    Never call this function from user-facing code.
    Uses GUILD_TOKEN_<guild_id> environment variable.
    """
    return os.getenv(f'GUILD_TOKEN_{guild_id}')


def register_token(guild_id, channel_id, owner_id):
    """Register the server monitoring token for this server (single-server bot).

    The token itself should be in GUILD_TOKEN_<guild_id> environment variable.
    This just records the registration.

    Args:
        guild_id (int): Discord server ID.
        channel_id (int): Discord channel ID (for notification channel).
        owner_id (int): Discord user ID of the owner.

    Returns:
        bool: True if registered successfully.

    Raises:
        TokenStorageError: If token not found in environment.
    """
    # Verify token exists in environment
    token = _get_token_from_env(guild_id)
    if not token:
        raise TokenStorageError(
            f"GUILD_TOKEN_{guild_id} not found in environment. "
            "Set GUILD_TOKEN_<guild_id>=your_token_here in .env file"
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
            return _get_token_from_env(guild_id)
        return None
    except Exception:
        return None


def get_notification_channel_for_guild(guild_id):
    """Get the notification channel ID for a registered server.

    Args:
        guild_id (int): Discord server ID.

    Returns:
        int or None: The notification channel ID if registered.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT channel_id FROM access_tokens WHERE guild_id = ?",
            (guild_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return int(result[0]) if result and result[0] is not None else None
    except Exception:
        return None


def is_token_registered(guild_id):
    """Check if a token is registered for the server.

    Args:
        guild_id (int): Discord server ID.

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
    """Remove token registration for a server.

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
    """Get list of servers with registered tokens.

    Returns:
        list: List of server IDs with registered tokens.
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