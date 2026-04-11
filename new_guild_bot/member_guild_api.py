"""Helper module for tracking Free Fire guild membership and Discord user mappings."""

import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "http://controle.thug4ff.xyz/memberClan"


class MemberGuildAPIError(Exception):
    """Raised when the memberGuild API request fails."""


def fetch_member_guild(access_token, timeout=10):
    """Fetch current guild member list from the memberGuild API."""
    if not access_token:
        raise MemberGuildAPIError("Access token is required")

    query = urlencode({"access_token": access_token})
    url = f"{BASE_URL}?{query}"
    request = Request(url, method="GET")
    request.add_header("Accept", "application/json")

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            try:
                data = json.loads(raw.decode("utf-8"))

                if "members" in data and isinstance(data["members"], list) and data.get("uid"):
                    last_member = data["members"][-1] if data["members"] else None
                    if isinstance(last_member, dict) and last_member.get("account_id") == data.get("uid"):
                        data["members"] = data["members"][:-1]

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
    if not isinstance(response, dict):
        raise MemberGuildAPIError("API response is not a JSON object")

    members = response.get("members", [])
    if not isinstance(members, list):
        raise MemberGuildAPIError("Members field is not a list")

    return {member.get("account_id") for member in members if member.get("account_id")}


def detect_list_changes(current_uids, previous_uids):
    return {
        "joined": current_uids - previous_uids,
        "left": previous_uids - current_uids,
    }


def get_member_by_uid(response, uid):
    if not isinstance(response, dict):
        return None

    members = response.get("members", [])
    for member in members:
        if member.get("account_id") == uid:
            return member
    return None
