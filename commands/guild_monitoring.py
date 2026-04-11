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
from datetime import datetime, timedelta
from helpers import log_action, is_commander
from member_guild_api import fetch_member_guild
from channel_guild_monitoring import (
    get_channel_guild_id, register_channel_guild, unregister_channel_guild, monitor_channel_guild,
    get_channel_recent_changes, get_channel_members, get_channel_access_token
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


def is_head_commander(interaction: discord.Interaction) -> bool:
    """Check if user has the Head Commander role"""
    if not isinstance(interaction.user, discord.Member):
        return False

    return any(role.name.lower() == "head commander" for role in interaction.user.roles)


class GuildMonitoringCog(commands.Cog):
    """Free Fire Guild Monitoring - One channel = one guild"""

    def __init__(self, bot):
        self.bot = bot
        self.monitoring_interval = 2  # Default 2 minutes
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
                joined_list.append(f"✅ {name}")

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
                left_list.append(f"❌ {name}")

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

        # Restrict to specific channel
        if interaction.channel.id != 1492394107799208077:
            await interaction.followup.send("❌ This command can only be used in the designated registration channel.", ephemeral=True)
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
            success = register_channel_guild(channel_id_int, guild_id, access_token, interaction.user.id)
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

    @app_commands.command(name="guild_members", description="View current guild members")
    async def guild_members(self, interaction: discord.Interaction):
        """Show current members of the monitored guild"""
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

            # Create CSV format
            csv_lines = ["Nickname,UID"]
            for member in members:
                uid = member.get("account_id") or member.get("uid", "Unknown")
                nickname = member.get("nickname", f"UID: {uid}")
                # Escape commas in nickname
                nickname = nickname.replace(",", ";")
                csv_lines.append(f"{nickname},{uid}")

            csv_content = "\n".join(csv_lines)

            # Send as code block for better formatting
            if len(csv_content) <= 1900:  # Leave some margin
                await interaction.followup.send(f"```\n{csv_content}\n```")
            else:
                # Truncate if too long
                truncated_csv = "\n".join(csv_lines[:50])  # First 50 members
                await interaction.followup.send(f"```\n{truncated_csv}\n```\n... and {len(members) - 50} more members")

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

            member_pages = math.ceil(len(member_lines) / 10) if member_lines else 0
            change_pages = math.ceil(len(change_lines) / 10) if change_lines else 0
            pages = []
            total_pages = 1 + member_pages + change_pages

            summary_embed = discord.Embed(
                title="📊 Guild Updates",
                description=f"Live guild summary for {interaction.channel.mention}",
                color=discord.Color.blurple(),
                timestamp=datetime.utcnow()
            )
            summary_embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            summary_embed.add_field(name="Total Members", value=str(len(members)), inline=True)
            summary_embed.add_field(name="Recent Changes", value=f"{len(changes)}\n✅ {joined_count} Joined\n❌ {left_count} Left", inline=False)

            if member_lines:
                summary_embed.add_field(
                    name="Top Members",
                    value="\n".join(member_lines[:5]) if len(member_lines) <= 5 else "\n".join(member_lines[:5]) + f"\n... and {len(member_lines) - 5} more members",
                    inline=False
                )

            if change_lines:
                summary_embed.add_field(
                    name="Top Changes",
                    value="\n".join(change_lines[:5]) if len(change_lines) <= 5 else "\n".join(change_lines[:5]) + f"\n... and {len(change_lines) - 5} more changes",
                    inline=False
                )
            else:
                summary_embed.add_field(name="Recent Activity", value="No recent changes recorded.", inline=False)

            if interaction.guild and interaction.guild.icon:
                summary_embed.set_thumbnail(url=interaction.guild.icon.url)

            summary_embed.set_footer(text=f"Page 1/{total_pages} • Use Previous/Next buttons to browse")
            pages.append(summary_embed)

            for page_index in range(member_pages):
                start = page_index * 10
                chunk = member_lines[start:start + 10]
                embed = discord.Embed(
                    title="📋 Guild Members",
                    description=f"Members {start + 1}-{start + len(chunk)} of {len(member_lines)}",
                    color=discord.Color.blurple(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(
                    name="Member List",
                    value="\n".join(chunk),
                    inline=False
                )
                embed.set_footer(text=f"Page {len(pages) + 1}/{total_pages}")
                pages.append(embed)

            for page_index in range(change_pages):
                start = page_index * 10
                chunk = change_lines[start:start + 10]
                embed = discord.Embed(
                    title="📌 Recent Changes",
                    description=f"Changes {start + 1}-{start + len(chunk)} of {len(change_lines)}",
                    color=discord.Color.blurple(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(
                    name="Recent Activity",
                    value="\n".join(chunk),
                    inline=False
                )
                embed.set_footer(text=f"Page {len(pages) + 1}/{total_pages}")
                pages.append(embed)

            view = GuildUpdatesView(pages)
            await interaction.followup.send(embed=pages[0], view=view)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to fetch guild updates: {e}", ephemeral=True)

    @app_commands.command(name="guild_changes", description="View recent membership changes")
    @app_commands.describe(limit="Number of changes to show (max 50)")
    async def guild_changes(self, interaction: discord.Interaction, limit: int = 20):
        """Show recent membership changes for this channel's guild"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        limit = min(limit, 50)  # Cap at 50

        changes = get_channel_recent_changes(interaction.channel.id, limit)

        if not changes:
            await interaction.followup.send("📭 No membership changes recorded yet.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📊 Recent Guild Changes",
            description=f"Latest membership activity for {interaction.channel.mention}",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )

        joined_count = sum(1 for c in changes if c["change_type"] == "joined")
        left_count = sum(1 for c in changes if c["change_type"] == "left")

        embed.add_field(name="✅ Joined", value=str(joined_count), inline=True)
        embed.add_field(name="❌ Left", value=str(left_count), inline=True)
        embed.add_field(name="📊 Total Changes", value=str(len(changes)), inline=True)

        change_list = []
        for change in changes[:10]:
            emoji = "✅" if change["change_type"] == "joined" else "❌"
            nickname = change["nickname"] or f"UID: {change['uid']}"
            timestamp = change["timestamp"].split("T")[0]
            change_list.append(f"{emoji} **{nickname}** — {timestamp}")

        if change_list:
            embed.add_field(
                name="Recent Activity",
                value="\n".join(change_list),
                inline=False
            )

        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        if len(changes) > 10:
            embed.set_footer(text=f"Showing 10 of {len(changes)} changes")

        await interaction.followup.send(embed=embed)

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