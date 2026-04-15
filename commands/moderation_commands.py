"""User Moderation & Discipline Commands"""
import discord
from discord import app_commands
from discord.ext import commands
import io
from datetime import datetime, timezone, timedelta
from helpers import (
    log_action,
    get_member_name_by_uid,
    update_glory,
    is_head_commander,
    add_banned_player,
    remove_banned_player,
    get_banned_players,
    get_banned_player,
)
from member_clan_api import fetch_player_info

# IST timezone constant
IST = timezone(timedelta(hours=5, minutes=30))

class GloryCheckModal(discord.ui.Modal, title="Check Glory Levels"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    glory_data = discord.ui.TextInput(
        label="UID and Glory",
        placeholder="Enter glory checks in format: UID,Glory (one per line)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        text = self.glory_data.value
        warnings_needed = []
        invalid_lines = []
        no_warning_needed = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split(",", 1)
            if len(parts) != 2:
                invalid_lines.append(line)
                continue

            uid_str, glory_str = parts
            uid_str = uid_str.strip()
            glory_str = glory_str.strip()

            if not uid_str or not glory_str:
                invalid_lines.append(line)
                continue

            try:
                uid = int(uid_str)
                glory = int(glory_str)
            except ValueError:
                invalid_lines.append(line)
                continue

            if glory >= 7000:
                no_warning_needed.append((uid, glory))
                continue

            # Get player name from guild data
            player_name = get_member_name_by_uid(interaction.channel_id, str(uid))
            if not player_name:
                invalid_lines.append(f"{uid},{glory} (not found in guild data)")
                continue

            warnings_needed.append((uid, glory, player_name))

        # Build response message
        msg = "**Glory Check Results**\n\n"
        if warnings_needed:
            msg += f"⚠️ **Glory warnings ({len(warnings_needed)}):\n**"
            for uid, glory, player_name in warnings_needed:
                msg += f"• {player_name} (UID: {uid}): Glory {glory}\n"
        
        if no_warning_needed:
            msg += f"\n✅ **Players with sufficient glory ({len(no_warning_needed)})** (glory >= 7000)\n"
        
        if invalid_lines:
            msg += f"\n❌ **Invalid entries ({len(invalid_lines)}):\n**"
            for line in invalid_lines[:10]:  # Limit to first 10 to avoid message too long
                msg += f"• {line}\n"
            if len(invalid_lines) > 10:
                msg += f"... and {len(invalid_lines) - 10} more\n"

        await interaction.response.send_message(msg)
        
        # Log action
        if warnings_needed:
            await log_action(interaction, "Glory Check", f"Checked glory for {len(warnings_needed)} players needing warnings")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("An error occurred while processing glory checks.", ephemeral=True)
        print(f"Glory check modal error: {error}")


class GloryUpdateModal(discord.ui.Modal, title="Update Glory Data"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    glory_data = discord.ui.TextInput(
        label="UID and Glory",
        placeholder="Enter glory updates in format: UID,Glory (one per line)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        text = self.glory_data.value
        updated = []
        invalid_lines = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split(",", 1)
            if len(parts) != 2:
                invalid_lines.append(line)
                continue

            uid_str, glory_str = parts
            uid_str = uid_str.strip()
            glory_str = glory_str.strip()

            if not uid_str or not glory_str:
                invalid_lines.append(line)
                continue

            try:
                uid = int(uid_str)
                glory = int(glory_str)
            except ValueError:
                invalid_lines.append(line)
                continue

            timestamp = datetime.now(IST).isoformat()
            success = update_glory(interaction.channel_id, uid, glory, str(interaction.user.id), timestamp)
            if success:
                updated.append((uid, glory))
            else:
                invalid_lines.append(f"{uid},{glory} (update failed)")

        # Build response message
        msg = "**Glory Data Updated**\n\n"
        if updated:
            msg += f"✅ **Updated {len(updated)} glory records:**\n"
            for uid, glory in updated[:20]:  # Limit display
                msg += f"• UID {uid}: Glory {glory}\n"
            if len(updated) > 20:
                msg += f"... and {len(updated) - 20} more\n"
        
        if invalid_lines:
            msg += f"\n❌ **Skipped {len(invalid_lines)} invalid line(s)**\n"

        await interaction.response.send_message(msg)
        
        # Log action
        if updated:
            await log_action(interaction, "Glory Updated", f"Updated glory data for {len(updated)} players")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("An error occurred while updating glory data.", ephemeral=True)
        print(f"Glory update modal error: {error}")


class ModerationCommands(commands.Cog):
    """Commands for user moderation and discipline"""
    
    def __init__(self, bot):
        self.bot = bot

    def _is_owner(self, interaction: discord.Interaction):
        owner_id = self.bot.owner_id
        if owner_id is None:
            return False
        return interaction.user.id == owner_id

    # TEMPORARILY DEACTIVATED
    # @app_commands.command(name="glorycheck", description="Check glory levels for multiple players")
    async def glorycheck(self, interaction: discord.Interaction):
        """Check glory levels for multiple players using a modal."""
        await interaction.response.send_modal(GloryCheckModal(self))

    # TEMPORARILY DEACTIVATED
    # @app_commands.command(name="gloryupdate", description="Update glory data for multiple players")
    async def gloryupdate(self, interaction: discord.Interaction):
        """Update glory data for multiple players using a modal."""
        await interaction.response.send_modal(GloryUpdateModal(self))

    @app_commands.command(name="banplayer", description="Ban a player from your channel and monitor partnered guild join events")
    @app_commands.describe(uid="Free Fire UID of the player to ban", reason="Reason for the ban")
    async def banplayer(self, interaction: discord.Interaction, uid: int, reason: str):
        """Ban a player for the current channel."""
        await interaction.response.defer()
        
        if not self._is_owner(interaction) and not is_head_commander(interaction):
            await interaction.followup.send("❌ Only the bot owner or Head Commanders can ban players.", ephemeral=True)
            return

        nickname = None
        try:
            player_info = fetch_player_info(uid)
            if player_info and "basicInfo" in player_info:
                nickname = player_info["basicInfo"].get("nickname")
        except Exception:
            nickname = None

        if not add_banned_player(interaction.channel_id, uid, nickname or "Unknown", reason, str(interaction.user)):
            await interaction.followup.send("❌ Failed to ban the player. Please try again.", ephemeral=True)
            return

        await interaction.followup.send(
            f"✅ Player {nickname or f'UID:{uid}'} has been banned for this channel. I will alert this channel if they join a partnered guild.",
            ephemeral=False
        )
        await log_action(interaction, "Player Banned", f"Banned UID {uid} ({nickname or 'Unknown'}) in channel {interaction.channel_id} - {reason}")

    @app_commands.command(name="unbanplayer", description="Remove a player from the ban list for this channel")
    @app_commands.describe(uid="Free Fire UID of the player to unban")
    async def unbanplayer(self, interaction: discord.Interaction, uid: int):
        """Remove a player from the banned list."""
        if not self._is_owner(interaction) and not is_head_commander(interaction):
            await interaction.response.send_message("❌ Only the bot owner or Head Commanders can unban players.", ephemeral=True)
            return

        if remove_banned_player(uid, interaction.channel_id):
            await interaction.response.send_message(f"✅ Player UID {uid} removed from the ban list for this channel.", ephemeral=False)
            await log_action(interaction, "Player Unbanned", f"Unbanned UID {uid} in channel {interaction.channel_id}")
        else:
            await interaction.response.send_message("❌ Failed to unban the player. Please try again.", ephemeral=True)

    @app_commands.command(name="listbanned", description="List currently banned players for this channel")
    async def listbanned(self, interaction: discord.Interaction):
        """List banned players for this channel."""
        if not self._is_owner(interaction) and not is_head_commander(interaction):
            await interaction.response.send_message("❌ Only the bot owner or Head Commanders can view banned players.", ephemeral=True)
            return

        bans = get_banned_players(interaction.channel_id)
        if not bans:
            await interaction.response.send_message("📋 No players are currently banned for this channel.", ephemeral=True)
            return

        msg_lines = ["**🚫 Banned Players for this Channel**"]
        for ban in bans[:20]:
            msg_lines.append(f"• {ban['nickname'] or 'Unknown'} (UID: {ban['uid']}) — Reason: {ban['reason']} — Banned by: {ban['banned_by']}")
        if len(bans) > 20:
            msg_lines.append(f"...and {len(bans) - 20} more banned players")

        await interaction.response.send_message("\n".join(msg_lines), ephemeral=True)





    @app_commands.command(name="banstatus", description="Show ban status for a player in this channel")
    @app_commands.describe(uid="Free Fire UID of the player")
    async def banstatus(self, interaction: discord.Interaction, uid: int):
        """Show whether a player is banned for this channel and alert state."""
        if not self._is_owner(interaction) and not is_head_commander(interaction):
            await interaction.response.send_message("❌ Only the bot owner or Head Commanders can view ban status.", ephemeral=True)
            return

        ban = get_banned_player(uid, interaction.channel_id)
        if not ban:
            await interaction.response.send_message(f"✅ UID {uid} is not banned for this channel.", ephemeral=True)
            return

        status = "Active" if ban["active"] else "Inactive"
        alert_status = "Sent" if ban["alert_sent"] else "Pending"
        msg = (
            f"**🚫 Ban Status for UID {uid}**\n"
            f"• Nickname: {ban['nickname'] or 'Unknown'}\n"
            f"• Reason: {ban['reason']}\n"
            f"• Banned by: {ban['banned_by']}\n"
            f"• Banned at: {ban['banned_at']}\n"
            f"• Active: {status}\n"
            f"• Partnered alert: {alert_status}\n"
        )

        if ban["alert_sent"]:
            msg += f"• Alert clan: {ban['alert_clan_name']} (ID: {ban['alert_clan_id']})\n"
            msg += f"• Alert sent at: {ban['alert_at']}\n"

        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot):
    """Load moderation commands"""
    await bot.add_cog(ModerationCommands(bot))
