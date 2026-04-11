"""Shared helper functions for the new guild monitoring bot."""
import os
import discord
from dotenv import load_dotenv

load_dotenv()

async def safe_send(interaction, message, ephemeral=False):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(message, ephemeral=ephemeral)
    except Exception:
        pass

async def log_action(interaction, action_type: str, details: str):
    print(f"[LOG] {action_type}: {details}")
    # Add more logging behavior here if needed.


def is_commander(interaction):
    if interaction.user.guild_permissions.administrator:
        return True
    for role in interaction.user.roles:
        if role.name.lower() == "commander":
            return True
    return False
