"""Helper module for tracking Free Fire clan membership and Discord user mappings.

Handles:
1. Fetching current clan roster from the memberClan API
2. Detecting roster changes (who joined/left)
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


class MemberClanAPIError(Exception):
    """Raised when the memberClan API request fails."""


def fetch_member_clan(access_token, timeout=30, retries=1):
    """Fetch current clan roster from the memberClan API.

    Args:
        access_token (str): API access token (supplied separately per guild).
        timeout (int): HTTP request timeout in seconds (default 30).
        retries (int): Number of retry attempts on timeout (default 1).

    Returns:
        dict: Parsed JSON response containing clan_id, members list, and metadata.

    Raises:
        MemberClanAPIError: If the request fails or response is invalid.
    """
    if not access_token:
        raise MemberClanAPIError("Access token is required")

    # Rate limit external API calls synchronously
    external_api_limiter.wait_for_slot_sync()

    query = urlencode({"access_token": access_token})
    url = f"{BASE_URL}?{query}"
    request = Request(url, method="GET")
    request.add_header("Accept", "application/json")

    last_exception = None
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                try:
                    return json.loads(raw.decode("utf-8"))
                except ValueError as exc:
                    raise MemberClanAPIError(f"Invalid JSON response: {exc}") from exc
        except HTTPError as exc:
            raise MemberClanAPIError(f"HTTP error {exc.code}: {exc.reason}") from exc
        except URLError as exc:
            if "getaddrinfo failed" in str(exc.reason):
                raise MemberClanAPIError(
                    f"Cannot reach the API server."
                    f"Check your internet connection or firewall settings. "
                    f"Error: {exc.reason}"
                ) from exc
            elif "timed out" in str(exc.reason).lower() or isinstance(exc.reason, TimeoutError):
                last_exception = exc
                if attempt < retries:
                    continue  # Retry on timeout
                else:
                    raise MemberClanAPIError(f"Request timed out after {timeout}s (retried {retries} times)") from exc
            else:
                raise MemberClanAPIError(f"API error: {exc.reason}") from exc
        except Exception as exc:
            raise MemberClanAPIError(f"Unexpected error: {exc}") from exc

    # If we get here, all retries failed with timeout
    if last_exception:
        raise MemberClanAPIError(f"Request timed out after {timeout}s (retried {retries} times)") from last_exception


def get_roster_uids(response):
    """Extract set of current UIDs (account_ids) from API response.

    Args:
        response (dict): API response containing members list.

    Returns:
        set: Set of UIDs (integers) currently in the clan.

    Raises:
        MemberClanAPIError: If response structure is invalid.
    """
    if not isinstance(response, dict):
        raise MemberClanAPIError("API response is not a JSON object")

    members = response.get("members", [])
    if not isinstance(members, list):
        raise MemberClanAPIError("Members field is not a list")

    return {member.get("account_id") for member in members if member.get("account_id")}


def detect_roster_changes(current_uids, previous_uids):
    """Detect who joined and left the clan.

    Args:
        current_uids (set): Current roster UIDs.
        previous_uids (set): Previous roster UIDs.

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


def record_membership_change(ff_uid, change_type, clan_id=None, timestamp=None):
    """Record a membership change event.

    Args:
        ff_uid (int): Free Fire UID.
        change_type (str): "joined" or "left".
        clan_id (int): Optional clan ID.
        timestamp (str): ISO timestamp (defaults to now).

    Returns:
        dict: Membership change record.
    """
    return {
        "ff_uid": int(ff_uid),
        "change_type": change_type,
        "clan_id": clan_id,
        "timestamp": timestamp or datetime.utcnow().isoformat(),
    }
