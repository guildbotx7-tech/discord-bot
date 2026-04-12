"""Helper module for tracking Free Fire guild membership and Discord user mappings.

Handles:
1. Fetching current guild member list from the memberGuild API
2. Detecting member list changes (who joined/left)
3. Mapping Discord users to Free Fire UIDs
"""

import json
import asyncio
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rate_limiter import external_api_limiter

BASE_URL = "http://controle.thug4ff.xyz/memberClan"


class MemberGuildAPIError(Exception):
    """Raised when the memberGuild API request fails."""


def fetch_member_guild(access_token, timeout=10):
    """Fetch current guild member list from the memberGuild API.

    Args:
        access_token (str): API access token (supplied separately per guild).
        timeout (int): HTTP request timeout in seconds.

    Returns:
        dict: Parsed JSON response containing guild_id, members list, and metadata.
              Members list is filtered to exclude bot/user entries.

    Raises:
        MemberGuildAPIError: If the request fails or response is invalid.
    """
    if not access_token:
        raise MemberGuildAPIError("Access token is required")

    # Rate limit external API calls
    asyncio.run(external_api_limiter.wait_for_slot())

    query = urlencode({"access_token": access_token})
    url = f"{BASE_URL}?{query}"
    request = Request(url, method="GET")
    request.add_header("Accept", "application/json")

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            try:
                data = json.loads(raw.decode("utf-8"))

                if "members" in data:
                    members = data["members"]
                    if isinstance(members, str):
                        try:
                            members = json.loads(members)
                        except Exception:
                            members = []
                    elif isinstance(members, dict):
                        members = [members]

                    if not isinstance(members, list):
                        members = []

                    data["members"] = members

                return data

            except ValueError as exc:
                raise MemberGuildAPIError(f"Invalid JSON response: {exc}") from exc
    except HTTPError as exc:
        raise MemberGuildAPIError(f"HTTP error {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        if "getaddrinfo failed" in str(exc.reason):
            raise MemberGuildAPIError(
                f"Cannot reach the API server (controle.thug4ff.xyz). "
                f"Check your internet connection or firewall settings. "
                f"Error: {exc.reason}"
            ) from exc
        else:
            raise MemberGuildAPIError(f"API error: {exc.reason}") from exc
    except Exception as exc:
        raise MemberGuildAPIError(f"Unexpected error: {exc}") from exc


def get_list_uids(response):
    """Extract set of current UIDs (account_ids) from API response.

    Args:
        response (dict): API response containing members list.

    Returns:
        set: Set of UIDs (integers) currently in the guild.

    Raises:
        MemberGuildAPIError: If response structure is invalid.
    """
    if not isinstance(response, dict):
        raise MemberGuildAPIError("API response is not a JSON object")

    members = response.get("members", [])
    if not isinstance(members, list):
        raise MemberGuildAPIError("Members field is not a list")

    return {member.get("account_id") for member in members if member.get("account_id")}


def detect_list_changes(current_uids, previous_uids):
    """Detect who joined and left the guild.

    Args:
        current_uids (set): Current member list UIDs.
        previous_uids (set): Previous member list UIDs.

    Returns:
        dict: {"joined": set, "left": set} with UID changes.
    """
    return {
        "joined": current_uids - previous_uids,
        "left": previous_uids - current_uids,
    }


def get_member_by_uid(response, uid):
    """Retrieve full member data by UID from response.

    Args:
        response (dict): API response.
        uid (int): Member's UID (account_id).

    Returns:
        dict or None: Member object if found, None otherwise.
    """
    if not isinstance(response, dict):
        return None

    members = response.get("members", [])
    for member in members:
        if member.get("account_id") == uid:
            return member
    return None


def create_discord_uid_mapping(discord_id, ff_uid):
    """Create a mapping record linking Discord user to Free Fire UID.

    Args:
        discord_id (int): Discord user ID.
        ff_uid (int): Free Fire UID (account_id).

    Returns:
        dict: Mapping record with timestamps.
    """
    return {
        "discord_id": int(discord_id),
        "ff_uid": int(ff_uid),
        "linked_at": datetime.utcnow().isoformat(),
    }


def record_membership_change(ff_uid, change_type, guild_id=None, timestamp=None):
    """Record a membership change event.

    Args:
        ff_uid (int): Free Fire UID.
        change_type (str): "joined" or "left".
        guild_id (int): Optional guild ID.
        timestamp (str): ISO timestamp (defaults to now).

    Returns:
        dict: Membership change record.
    """
    return {
        "ff_uid": int(ff_uid),
        "change_type": change_type,
        "guild_id": guild_id,
        "timestamp": timestamp or datetime.utcnow().isoformat(),
    }