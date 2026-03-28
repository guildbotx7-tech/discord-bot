"""Shared helper functions and utilities"""
from pymongo import MongoClient
import re
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["discord_bot"]
guild_data = db["guild_data"]
audit_logs = db["audit_logs"]

# MongoDB helper functions
def get_channel_data(channel_id):
    """Retrieve guild and bound data for a channel"""
    result = guild_data.find_one({"channel_id": channel_id})
    if result:
        return result.get("guild", {}), result.get("bound", {})
    return {}, {}

def update_channel_data(channel_id, guild=None, bound=None):
    """Update guild and/or bound data for a channel"""
    data = {"channel_id": channel_id}
    if guild is not None:
        data["guild"] = guild
    if bound is not None:
        data["bound"] = bound
    guild_data.update_one(
        {"channel_id": channel_id},
        {"$set": data},
        upsert=True
    )

def clear_channel_data(channel_id):
    """Clear all data for a channel"""
    guild_data.update_one(
        {"channel_id": channel_id},
        {"$set": {"guild": {}, "bound": {}}},
        upsert=True
    )

# Permission helper functions
def is_commander(interaction):
    """Check if user is a commander or admin"""
    if interaction.user.guild_permissions.administrator:
        return True
    for role in interaction.user.roles:
        if role.name.lower() == "commander":
            return True
    return False

# Data processing
def parse_member_lines(text, ID_RE):
    """Parse member list from text input"""
    members = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = ID_RE.search(line)
        if m:
            id_ = m.group(1)
            name = line.replace(id_, "").replace(",", " ").strip(" -:|")
            members[id_] = name
    return members
