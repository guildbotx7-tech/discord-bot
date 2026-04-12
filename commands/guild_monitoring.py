"""Free Fire Guild Monitoring Commands - Integrated into main bot"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import math
import io
from datetime import datetime, timedelta
from helpers import log_action, is_commander
from member_guild_api import fetch_member_guild
from channel_guild_monitoring import (
    get_channel_guild_id, get_channel_guild_name, get_channel_registered_by,
    register_channel_guild, unregister_channel_guild, monitor_channel_guild,
    get_channel_recent_changes, get_channel_members, get_channel_access_token,
    get_monitoring_interval, set_monitoring_interval
)


class GuildUpdatesView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=300)
        self.pages = pages
        self.page = 0
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.page > 0:
            prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary)
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
        if self.page < len(self.pages) - 1:
            next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_buttons()
        await self.update_message(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_buttons()
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)


class LogsView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=300)
        self.pages = pages
        self.page = 0
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.page > 0:
            prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary)
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
        if self.page < len(self.pages) - 1:
            next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_buttons()
        await self.update_message(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_buttons()
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)


class GuildMembersView(discord.ui.View):
    def __init__(self, members, guild_name, guild_id, changes=None):
        super().__init__(timeout=300)
        self.members = members
        self.guild_name = guild_name
        self.guild_id = guild_id
        self.changes = changes or []

        members_button = discord.ui.Button(label="Members", style=discord.ButtonStyle.primary)
        members_button.callback = self.show_members
        self.add_item(members_button)

        logs_button = discord.ui.Button(label="Logs", style=discord.ButtonStyle.secondary)
        logs_button.callback = self.show_logs
        self.add_item(logs_button)

    async def show_members(self, interaction: discord.Interaction):
        member_lines = []
        for i, member in enumerate(self.members):
            uid = member.get("account_id") or member.get("uid", "Unknown")
            nickname = member.get("nickname", f"UID: {uid}")
            member_lines.append(f"{i+1:2d}. {nickname} ({uid})")

        embed = discord.Embed(
            title="👥 Guild Member List",
            description=f"Full member list for **{self.guild_name}**",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        # Split members into chunks to stay under Discord's 1024 character limit per field
        chunk_size = 28  # About 28 members per field
        member_chunks = [member_lines[i:i + chunk_size] for i in range(0, len(member_lines), chunk_size)]

        for idx, chunk in enumerate(member_chunks):
            field_value = "```\n" + "\n".join(chunk) + "\n```"

            # Ensure field value doesn't exceed 1024 characters
            if len(field_value) > 1024:
                # Truncate if still too long
                truncated_chunk = chunk[:15]  # Show fewer members
                field_value = "```\n" + "\n".join(truncated_chunk) + f"\n... and {len(chunk) - 15} more\n```"

            embed.add_field(
                name="Members",
                value=field_value,
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    async def show_logs(self, interaction: discord.Interaction):
        """Show all join/leave logs with pagination if needed"""
        if not self.changes:
            embed = discord.Embed(
                title="📋 Guild Activity Logs",
                description=f"Recent activity for **{self.guild_name}**",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="Activity",
                value="No activity recorded.",
                inline=False
            )
            await interaction.response.send_message(embed=embed)
            return

        # Split logs into chunks of 10 per page
        chunk_size = 10
        log_chunks = [self.changes[i:i + chunk_size] for i in range(0, len(self.changes), chunk_size)]
        pages = []

        for page_index, chunk in enumerate(log_chunks):
            embed = discord.Embed(
                title="📋 Guild Activity Logs",
                description=f"Activity for **{self.guild_name}** (Page {page_index + 1}/{len(log_chunks)})",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            log_lines = []
            for change in chunk:
                emoji = "✅" if change["change_type"] == "joined" else "❌"
                nickname = change["nickname"] or f"UID: {change['uid']}"
                uid = change["uid"]
                timestamp = change["timestamp"]
                log_lines.append(f"{emoji} {nickname} ({uid})\n   {timestamp}")

            log_text = "\n".join(log_lines)
            embed.add_field(
                name=f"Activities {page_index * chunk_size + 1}-{page_index * chunk_size + len(chunk)}",
                value=f"```\n{log_text}\n```",
                inline=False
            )
            embed.set_footer(text=f"Total logs: {len(self.changes)}")
            pages.append(embed)

        if len(pages) > 1:
            view = LogsView(pages)
            await interaction.response.send_message(embed=pages[0], view=view)
        else:
            await interaction.response.send_message(embed=pages[0])


def is_head_commander(interaction: discord.Interaction) -> bool:
    """Check if user has the Head Commander role"""
    if not isinstance(interaction.user, discord.Member):
        return False

    return any(role.name.lower() == "head commander" for role in interaction.user.roles)


class GuildMonitoringCog(commands.Cog):
    """Free Fire Guild Monitoring - One channel = one guild"""

    def __init__(self, bot):
        self.bot = bot
        self.monitoring_interval = get_monitoring_interval()  # Load from database
        self.monitoring_task = None
        self.start_monitoring_task()

    def cog_unload(self):
        if self.monitoring_task:
            self.monitoring_task.cancel()

    def start_monitoring_task(self):
        """Start the monitoring task with current interval"""
        if self.monitoring_task:
            self.monitoring_task.cancel()

        async def monitoring_loop():
            """Monitor all registered channels"""
            print(f"\n🔥 GUILD MONITORING CYCLE (every {self.monitoring_interval} minutes)")

            # Check each text channel for registered guilds
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    # Check if this channel has a registered guild
                    if get_channel_guild_id(channel.id):
                        result = await asyncio.to_thread(monitor_channel_guild, channel.id)

                        if result["status"] == "success":
                            changes = result["changes"]
                            if changes["joined"] or changes["left"]:
                                await self.send_change_notifications(channel, changes)
                        else:
                            print(f"❌ Channel {channel.name}: {result['error']}")

            print("✅ Monitoring cycle complete\n")

        self.monitoring_task = tasks.loop(minutes=self.monitoring_interval)(monitoring_loop)
        self.monitoring_task.before_loop(self.before_monitoring_task)
        self.monitoring_task.start()

    async def before_monitoring_task(self):
        await self.bot.wait_until_ready()

    def get_channel_guild_id(self, channel_id):
        """Get the Free Fire guild ID registered for a channel"""
        return get_channel_guild_id(channel_id)

    async def send_change_notifications(self, channel, changes):
        """Send notifications about membership changes"""
        embed = discord.Embed(
            title="👥 Guild Membership Changes",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        if changes["joined"]:
            joined_items = list(changes["joined"])
            joined_list = []
            for uid in joined_items[:50]:  # Limit to 50 per message
                member_data = self.get_member_info(uid)
                name = member_data.get("nickname", f"UID: {uid}") if member_data else f"UID: {uid}"
                joined_list.append(f"✅ {name} (UID: {uid})")

            embed.add_field(
                name=f"Joined ({len(joined_items)})",
                value="\n".join(joined_list),
                inline=False
            )

        if changes["left"]:
            left_items = list(changes["left"])
            left_list = []
            for uid in left_items[:5]:  # Limit to 5 per message
                member_data = self.get_member_info(uid)
                name = member_data.get("nickname", f"UID: {uid}") if member_data else f"UID: {uid}"
                left_list.append(f"❌ {name} (UID: {uid})")

            embed.add_field(
                name=f"Left ({len(left_items)})",
                value="\n".join(left_list),
                inline=False
            )

        if len(changes["joined"]) > 50 or len(changes["left"]) > 50:
            embed.set_footer(text="... and more changes")

        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send notification to {channel.name}: {e}")

    def get_member_info(self, uid):
        """Get cached member info"""
        try:
            import sqlite3
            conn = sqlite3.connect("discord_bot.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data FROM member_cache WHERE uid = ? ORDER BY cached_at DESC LIMIT 1",
                (uid,)
            )
            result = cursor.fetchone()
            conn.close()
            return json.loads(result[0]) if result else None
        except:
            return None

    @app_commands.command(name="register_guild", description="Register a Free Fire guild for this channel (Commanders only)")
    @app_commands.describe(
        access_token="Access token for your guild's API",
        channel_id="Discord channel ID to register the guild in",
        guild_name="Name of your Free Fire guild"
    )
    async def register_guild(self, interaction: discord.Interaction, access_token: str, channel_id: str, guild_name: str):
        """Register a Free Fire guild for monitoring with access token, channel ID, and guild name"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            # Interaction expired, try to respond immediately instead
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_head_commander(interaction):
            await interaction.followup.send("❌ Only Head Commanders or higher roles can register guilds.", ephemeral=True)
            return

        # Validate channel ID
        try:
            channel_id_int = int(channel_id)
        except ValueError:
            await interaction.followup.send("❌ Invalid channel ID. Must be a number.", ephemeral=True)
            return

        # Get the channel from the guild
        try:
            channel = interaction.guild.get_channel(channel_id_int)
            if not channel:
                await interaction.followup.send(f"❌ Channel with ID `{channel_id}` not found in this server.", ephemeral=True)
                return
        except Exception as e:
            await interaction.followup.send(f"❌ Error accessing channel: {str(e)}", ephemeral=True)
            return

        # Reject duplicate registration for the same channel
        if get_channel_guild_id(channel_id_int):
            await interaction.followup.send(
                "❌ A guild is already registered to this channel. Remove the existing registration first or choose another channel.",
                ephemeral=True
            )
            return

        # Validate access token format (should be a long string)
        if len(access_token) < 50:
            await interaction.followup.send("❌ Invalid access token format. Token should be at least 50 characters.", ephemeral=True)
            return

        # Validate guild name
        if len(guild_name) < 2 or len(guild_name) > 100:
            await interaction.followup.send("❌ Guild name must be between 2 and 100 characters.", ephemeral=True)
            return

        # Test the access token and extract guild ID from API response
        try:
            api_response = fetch_member_guild(access_token, timeout=10)
            if "members" not in api_response or "clan_id" not in api_response:
                await interaction.followup.send("❌ Failed to verify guild access. Check your access token.", ephemeral=True)
                return
            
            guild_id = str(api_response["clan_id"])
            member_count = len(api_response.get("members", []))

        except Exception as e:
            await interaction.followup.send(f"❌ API test failed: {str(e)}", ephemeral=True)
            return

        # Register the guild for the specified channel with its access token
        try:
            success = register_channel_guild(channel_id_int, guild_id, access_token, interaction.user.id, guild_name)
            if not success:
                await interaction.followup.send("❌ Failed to register guild.", ephemeral=True)
                return

            embed = discord.Embed(
                title="✅ Guild Registered",
                description=f"Guild **{guild_name}** will be monitored in {channel.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            embed.add_field(name="Guild Name", value=guild_name, inline=True)
            embed.add_field(name="Current Members", value=str(member_count), inline=True)
            embed.add_field(name="Registered by", value=interaction.user.mention, inline=True)
            embed.set_footer(text="Guild monitoring will start in the next monitoring cycle (max 10 minutes)")

            await interaction.followup.send(embed=embed)

            # Log the action
            await log_action(
                interaction,
                "Guild Registered",
                f"Channel {channel.mention} registered to monitor guild {guild_id} ({guild_name})"
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Registration failed: {e}", ephemeral=True)

    @app_commands.command(name="remove_guild", description="Remove the registered guild for this channel or a specified channel (Commanders only)")
    @app_commands.describe(
        channel_id="Discord channel ID to unregister the guild from (defaults to current channel)"
    )
    async def remove_guild(self, interaction: discord.Interaction, channel_id: str = None):
        """Remove the registered guild for a channel"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_head_commander(interaction):
            await interaction.followup.send("❌ Only Head Commanders or higher roles can remove guild registrations.", ephemeral=True)
            return

        if channel_id:
            try:
                channel_id_int = int(channel_id)
            except ValueError:
                await interaction.followup.send("❌ Invalid channel ID. Must be a number.", ephemeral=True)
                return
        else:
            channel_id_int = interaction.channel.id

        try:
            channel = interaction.guild.get_channel(channel_id_int)
            if not channel:
                await interaction.followup.send(f"❌ Channel with ID `{channel_id_int}` not found in this server.", ephemeral=True)
                return
        except Exception as e:
            await interaction.followup.send(f"❌ Error accessing channel: {str(e)}", ephemeral=True)
            return

        if not get_channel_guild_id(channel_id_int):
            await interaction.followup.send("❌ No guild registered for this channel.", ephemeral=True)
            return

        if not unregister_channel_guild(channel_id_int):
            await interaction.followup.send("❌ Failed to remove guild registration.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🗑️ Guild Registration Removed",
            description=f"Guild monitoring has been removed for {channel.mention}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Removed by", value=interaction.user.mention, inline=True)

        await interaction.followup.send(embed=embed)
        await log_action(
            interaction,
            "Guild Registration Removed",
            f"Channel {channel.mention} unregistered from guild monitoring"
        )

    @app_commands.command(name="set_monitoring_cycle", description="Set the guild monitoring cycle interval (Head Commander only)")
    @app_commands.describe(minutes="New cycle interval in minutes (1-600)")
    async def set_monitoring_cycle(self, interaction: discord.Interaction, minutes: int):
        """Set the monitoring cycle interval"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_head_commander(interaction):
            await interaction.followup.send("❌ Only Head Commanders can set the monitoring cycle.", ephemeral=True)
            return

        # Restrict to specific channel
        if interaction.channel.id != 1492403871593791649:
            await interaction.followup.send("❌ This command can only be used in the designated monitoring channel.", ephemeral=True)
            return

        if minutes < 1 or minutes > 600:
            await interaction.followup.send("❌ Cycle interval must be between 1 and 600 minutes.", ephemeral=True)
            return

        old_interval = self.monitoring_interval
        self.monitoring_interval = minutes

        # Save to database
        set_monitoring_interval(minutes)

        # Restart the task with new interval
        self.start_monitoring_task()

        embed = discord.Embed(
            title="⚙️ Monitoring Cycle Updated",
            description=f"Guild monitoring cycle changed from {old_interval} to {minutes} minutes",
            color=discord.Color.blue()
        )
        embed.add_field(name="New Interval", value=f"{minutes} minutes", inline=True)
        embed.add_field(name="Changed by", value=interaction.user.mention, inline=True)

        await interaction.followup.send(embed=embed)
        await log_action(
            interaction,
            "Monitoring Cycle Updated",
            f"Changed monitoring interval from {old_interval} to {minutes} minutes"
        )

    @app_commands.command(name="guild_status", description="Check monitoring status for this channel")
    async def guild_status(self, interaction: discord.Interaction):
        """Check if this channel has a registered guild"""
        guild_id = self.get_channel_guild_id(interaction.channel.id)

        if guild_id:
            embed = discord.Embed(
                title="📊 Guild Monitoring Status",
                color=discord.Color.green()
            )
            embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            embed.add_field(name="Status", value="✅ Active", inline=True)
            embed.set_footer(text=f"Monitoring every {self.monitoring_interval} minutes")
        else:
            embed = discord.Embed(
                title="📊 Guild Monitoring Status",
                description="No guild registered for this channel",
                color=discord.Color.greyple()
            )
            embed.add_field(
                name="Setup",
                value="Use `/register_guild` to start monitoring",
                inline=False
            )

        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.errors.NotFound:
            # Interaction expired, unable to respond
            pass
        except Exception as e:
            print(f"Error sending guild status: {e}")

    @app_commands.command(name="guild_members", description="View current guild members with guild information")
    async def guild_members(self, interaction: discord.Interaction):
        """Show current members of the monitored guild with guild details"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild registered for this channel.", ephemeral=True)
            return

        guild_name = get_channel_guild_name(interaction.channel.id) or "Unknown Guild"
        registered_by_id = get_channel_registered_by(interaction.channel.id)
        registered_by = f"<@{registered_by_id}>" if registered_by_id else "Unknown"
        access_token = get_channel_access_token(interaction.channel.id)
        if not access_token:
            await interaction.followup.send("❌ Guild access not configured for this channel.", ephemeral=True)
            return

        try:
            api_response = fetch_member_guild(access_token, timeout=10)
            members = api_response.get("members", [])

            if not members:
                await interaction.followup.send("❌ No members found in guild.", ephemeral=True)
                return

            changes = get_channel_recent_changes(interaction.channel.id, 50)

            embed = discord.Embed(
                title="👥 Guild Members",
                description=f"Guild details and update summary for **{guild_name}**",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(name="🆔 Guild ID", value=f"`{guild_id}`", inline=True)
            embed.add_field(name="🏷️ Guild Name", value=guild_name, inline=True)
            embed.add_field(name="🛠️ Registered By", value=registered_by, inline=True)
            embed.add_field(name="👤 Current Members", value=str(len(members)), inline=True)
            embed.add_field(name="📌 Total Changes", value=str(len(changes)), inline=True)

            # Add last 10 logs to main page
            recent_logs = changes[:10] if changes else []
            if recent_logs:
                log_lines = []
                for change in recent_logs:
                    emoji = "✅" if change["change_type"] == "joined" else "❌"
                    nickname = change["nickname"] or f"UID: {change['uid']}"
                    uid = change["uid"]
                    timestamp = change["timestamp"]
                    log_lines.append(f"{emoji} {nickname} ({uid})\n   {timestamp}")

                log_text = "\n".join(log_lines)
                embed.add_field(
                    name="Last 10 Activities",
                    value=f"```\n{log_text}\n```",
                    inline=False
                )

            if interaction.guild and interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)

            view = GuildMembersView(members, guild_name, guild_id, changes)
            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to fetch members: {e}", ephemeral=True)

    @app_commands.command(name="guild_updates", description="View current guild members and recent guild changes")
    @app_commands.describe(limit="Number of changes to show (max 50)")
    async def guild_updates(self, interaction: discord.Interaction, limit: int = 20):
        """Show combined guild members and recent membership changes"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        limit = max(1, min(limit, 50))
        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild registered for this channel.", ephemeral=True)
            return

        access_token = get_channel_access_token(interaction.channel.id)
        if not access_token:
            await interaction.followup.send("❌ Guild access not configured for this channel.", ephemeral=True)
            return

        try:
            api_response = fetch_member_guild(access_token, timeout=10)
            members = api_response.get("members", [])

            if not members:
                await interaction.followup.send("❌ No members found in guild.", ephemeral=True)
                return

            changes = get_channel_recent_changes(interaction.channel.id, limit)
            joined_count = sum(1 for c in changes if c["change_type"] == "joined")
            left_count = sum(1 for c in changes if c["change_type"] == "left")

            member_lines = []
            for member in members:
                uid = member.get("account_id") or member.get("uid", "Unknown")
                nickname = member.get("nickname", f"UID: {uid}")
                member_lines.append(f"{nickname} ({uid})")

            change_lines = []
            for change in changes:
                emoji = "✅" if change["change_type"] == "joined" else "❌"
                nickname = change["nickname"] or f"UID: {change['uid']}"
                timestamp = change["timestamp"].split("T")[0]
                change_lines.append(f"{emoji} {nickname} - {timestamp}")

            # Create single embed with all members instead of pagination
            embed = discord.Embed(
                title="👥 Guild Member List",
                description=f"Full member list for **{guild_name or 'Unknown Guild'}**",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            # Add guild info
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            embed.add_field(name="Total Members", value=str(len(members)), inline=True)
            embed.add_field(name="Recent Changes", value=f"{len(changes)}\n✅ {joined_count} Joined\n❌ {left_count} Left", inline=True)

            # Create single field with all members
            member_text = "\n".join(f"{i+1}. {line}" for i, line in enumerate(member_lines))
            field_value = f"```\n{member_text}\n```"

            # Discord allows max 1024 characters per field, but we'll try to fit as many as possible
            if len(field_value) > 1024:
                # If too long, truncate gracefully
                lines = [f"{i+1}. {line}" for i, line in enumerate(member_lines)]
                newline = "\n"
                while lines and len(f"```\n{newline.join(lines)}\n```") > 1024:
                    lines = lines[:-1]  # Remove last member until it fits
                joined_lines = newline.join(lines)
                field_value = f"```\n{joined_lines}\n... and {len(member_lines) - len(lines)} more members\n```"

            embed.add_field(
                name="Members",
                value=field_value,
                inline=False
            )

            # Add recent changes if any
            if change_lines:
                change_text = "\n".join(change_lines[:10])  # Show first 10 changes
                if len(change_lines) > 10:
                    change_text += f"\n... and {len(change_lines) - 10} more changes"
                embed.add_field(
                    name="Recent Changes",
                    value=f"```\n{change_text}\n```",
                    inline=False
                )

            if interaction.guild and interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to fetch guild updates: {e}", ephemeral=True)

    @app_commands.command(name="guild_changes", description="View all current guild members with detailed data")
    @app_commands.describe(limit="Number of members to show per page (max 50)", csv_export="Export as CSV file")
    async def guild_changes(self, interaction: discord.Interaction, limit: int = 20, csv_export: bool = False):
        """Show all current guild members with detailed information including UID, name, and join dates"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        limit = min(limit, 50)  # Cap at 50 per page

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild registered for this channel.", ephemeral=True)
            return

        access_token = get_channel_access_token(interaction.channel.id)
        if not access_token:
            await interaction.followup.send("❌ Guild access not configured for this channel.", ephemeral=True)
            return

        try:
            # Fetch current members from API
            api_response = fetch_member_guild(access_token, timeout=10)
            members = api_response.get("members", [])

            if not members:
                await interaction.followup.send("❌ No members found in guild.", ephemeral=True)
                return

            # Get recent changes for join dates
            changes = get_channel_recent_changes(interaction.channel.id, 1000)  # Get more changes to find join dates

            # Create member data with join dates
            member_data = []
            for member in members:
                uid = member.get("account_id") or member.get("uid", "Unknown")
                nickname = member.get("nickname", f"UID: {uid}")

                # Find join date from changes
                join_date = None
                for change in changes:
                    if change["uid"] == uid and change["change_type"] == "joined":
                        join_date = change["timestamp"]
                        break

                member_data.append({
                    "nickname": nickname,
                    "uid": uid,
                    "join_date": join_date
                })

            # Sort by join date (newest first), then by name
            member_data.sort(key=lambda x: (x["join_date"] or "9999-99-99", x["nickname"]))

            if csv_export:
                # Create CSV content
                import io
                csv_lines = ["Nickname,UID,Join Date"]
                for member in member_data:
                    join_date = member["join_date"].split("T")[0] if member["join_date"] else "Unknown"
                    # Escape commas in nickname
                    nickname = member["nickname"].replace(",", ";")
                    csv_lines.append(f"{nickname},{member['uid']},{join_date}")

                csv_content = "\n".join(csv_lines)
                csv_file = discord.File(io.BytesIO(csv_content.encode("utf-8")), filename="guild_members.csv")
                await interaction.followup.send("📊 Guild members exported as CSV:", file=csv_file)
                return

            # Create paginated embeds
            pages = []
            total_pages = math.ceil(len(member_data) / limit)

            for page_num in range(total_pages):
                start_idx = page_num * limit
                end_idx = min(start_idx + limit, len(member_data))
                page_members = member_data[start_idx:end_idx]

                embed = discord.Embed(
                    title="👥 Guild Members",
                    description=f"All current members of {interaction.channel.mention} (Page {page_num + 1}/{total_pages})",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )

                embed.add_field(name="📊 Total Members", value=str(len(member_data)), inline=True)
                embed.add_field(name="📄 Showing", value=f"{start_idx + 1}-{end_idx}", inline=True)
                embed.add_field(name="🆔 Guild ID", value=f"`{guild_id}`", inline=True)

                member_list = []
                for member in page_members:
                    join_date = "Unknown"
                    if member["join_date"]:
                        try:
                            dt = datetime.fromisoformat(member["join_date"].replace('Z', '+00:00'))
                            join_date = dt.strftime("%Y-%m-%d")
                        except:
                            join_date = member["join_date"].split("T")[0]

                    member_list.append(f"**{member['nickname']}**\n🆔 `{member['uid']}` • 📅 {join_date}")

                if member_list:
                    embed.add_field(
                        name="Members",
                        value="\n\n".join(member_list),
                        inline=False
                    )

                if interaction.guild and interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)

                embed.set_footer(text=f"Page {page_num + 1}/{total_pages} • Use Previous/Next to navigate • Set csv_export=true for CSV download")
                pages.append(embed)

            if not pages:
                await interaction.followup.send("📭 No members found.", ephemeral=True)
                return

            # Send first page with navigation
            view = GuildUpdatesView(pages)
            await interaction.followup.send(embed=pages[0], view=view)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to fetch member data: {e}", ephemeral=True)

    @app_commands.command(name="ban_player", description="Ban a player from the guild (Commanders only)")
    @app_commands.describe(uid="Player UID to ban", reason="Reason for ban")
    async def ban_player(self, interaction: discord.Interaction, uid: str, reason: str = "No reason provided"):
        """Ban a player from the guild (logs the action)"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_commander(interaction):
            await interaction.followup.send("❌ Only Commanders can ban players.", ephemeral=True)
            return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild registered for this channel.", ephemeral=True)
            return

        # Log the ban action (we can't actually ban via API, so this is just logging)
        embed = discord.Embed(
            title="🚫 Player Banned",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Player UID", value=f"`{uid}`", inline=True)
        embed.add_field(name="Banned by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)

        await interaction.followup.send(embed=embed)

        # Log to action log
        await log_action(
            interaction,
            "Player Banned",
            f"Player {uid} banned from guild monitoring in {interaction.channel.mention}. Reason: {reason}"
        )

    @app_commands.command(name="global_ban", description="Globally ban a player across all monitored guilds (Commanders only)")
    @app_commands.describe(uid="Player UID to globally ban", reason="Reason for global ban")
    async def global_ban(self, interaction: discord.Interaction, uid: str, reason: str = "No reason provided"):
        """Globally ban a player from all monitored guilds"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_commander(interaction):
            await interaction.followup.send("❌ Only Commanders can globally ban players.", ephemeral=True)
            return

        # Find all channels with registered guilds
        banned_channels = []
        for channel in interaction.guild.text_channels:
            if self.get_channel_guild_id(channel.id):
                banned_channels.append(channel)

        if not banned_channels:
            await interaction.followup.send("❌ No guilds registered for global ban.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🚫 Global Player Ban",
            description=f"Player `{uid}` banned across all monitored guilds",
            color=discord.Color.dark_red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Banned by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(
            name="Affected Channels",
            value="\n".join([ch.mention for ch in banned_channels]),
            inline=False
        )

        await interaction.followup.send(embed=embed)

        # Log to action log
        await log_action(
            interaction,
            "Global Player Ban",
            f"Player {uid} globally banned across {len(banned_channels)} guilds. Reason: {reason}"
        )


async def setup(bot):
    """Load the guild monitoring cog"""
    # Database is initialized automatically when channel_guild_monitoring is imported
    await bot.add_cog(GuildMonitoringCog(bot))