"""Free Fire Guild Monitoring Commands for the new bot."""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
from datetime import datetime
from helpers import log_action, is_commander
from member_guild_api import fetch_member_guild
from channel_guild_monitoring import (
    get_channel_guild_id, register_channel_guild, monitor_channel_guild,
    get_channel_recent_changes, get_channel_members, get_channel_access_token
)


class GuildMonitoringCog(commands.Cog):
    """Free Fire Guild Monitoring - One channel = one guild"""

    def __init__(self, bot):
        self.bot = bot
        self.monitoring_task.start()

    def cog_unload(self):
        self.monitoring_task.cancel()

    @tasks.loop(minutes=2)
    async def monitoring_task(self):
        """Monitor all registered channels every 2 minutes"""
        print("\n🔥 GUILD MONITORING CYCLE")

        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if get_channel_guild_id(channel.id):
                    result = monitor_channel_guild(channel.id)
                    if result["status"] == "success":
                        changes = result["changes"]
                        if changes["joined"] or changes["left"]:
                            await self.send_change_notifications(channel, changes)
                    else:
                        print(f"❌ Channel {channel.name}: {result['error']}")

        print("✅ Monitoring cycle complete\n")

    @monitoring_task.before_loop
    async def before_monitoring_task(self):
        await self.bot.wait_until_ready()

    def get_channel_guild_id(self, channel_id):
        return get_channel_guild_id(channel_id)

    async def send_change_notifications(self, channel, changes):
        embed = discord.Embed(
            title="👥 Guild Membership Changes",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        if changes["joined"]:
            joined_items = list(changes["joined"])
            joined_list = []
            for uid in joined_items[:5]:
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
            for uid in left_items[:5]:
                member_data = self.get_member_info(uid)
                name = member_data.get("nickname", f"UID: {uid}") if member_data else f"UID: {uid}"
                left_list.append(f"❌ {name}")

            embed.add_field(
                name=f"Left ({len(left_items)})",
                value="\n".join(left_list),
                inline=False
            )

        if len(changes["joined"]) > 5 or len(changes["left"]) > 5:
            embed.set_footer(text="... and more changes")

        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send notification to {channel.name}: {e}")

    def get_member_info(self, uid):
        try:
            import sqlite3
            conn = sqlite3.connect("guild_monitor_bot.db")
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
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_commander(interaction):
            await interaction.followup.send("❌ Only Commanders can register guilds.", ephemeral=True)
            return

        try:
            channel_id_int = int(channel_id)
        except ValueError:
            await interaction.followup.send("❌ Invalid channel ID. Must be a number.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(channel_id_int)
        if not channel:
            await interaction.followup.send(f"❌ Channel with ID `{channel_id}` not found in this server.", ephemeral=True)
            return

        if len(access_token) < 50:
            await interaction.followup.send("❌ Invalid access token format. Token should be at least 50 characters.", ephemeral=True)
            return

        if len(guild_name) < 2 or len(guild_name) > 100:
            await interaction.followup.send("❌ Guild name must be between 2 and 100 characters.", ephemeral=True)
            return

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

            await log_action(
                interaction,
                "Guild Registered",
                f"Channel {channel.mention} registered to monitor guild {guild_id} ({guild_name})"
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Registration failed: {e}", ephemeral=True)

    @app_commands.command(name="guild_status", description="Check monitoring status for this channel")
    async def guild_status(self, interaction: discord.Interaction):
        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if guild_id:
            embed = discord.Embed(
                title="📊 Guild Monitoring Status",
                color=discord.Color.green()
            )
            embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            embed.add_field(name="Status", value="✅ Active", inline=True)
            embed.set_footer(text="Monitoring every 2 minutes")
        else:
            embed = discord.Embed(
                title="📊 Guild Monitoring Status",
                description="No guild registered for this channel",
                color=discord.Color.greyple()
            )
            embed.add_field(name="Setup", value="Use `/register_guild` to start monitoring", inline=False)

        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.errors.NotFound:
            pass
        except Exception as e:
            print(f"Error sending guild status: {e}")

    @app_commands.command(name="guild_members", description="View current guild members")
    async def guild_members(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
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
            members = get_channel_members(interaction.channel.id)
            if not members:
                api_response = fetch_member_guild(access_token, timeout=10)
                members = api_response.get("members", [])

            if not members:
                await interaction.followup.send("❌ No members found in guild.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"👥 Guild Members ({len(members)})",
                color=discord.Color.blue()
            )

            member_lines = []
            for member in members:
                uid = member.get("account_id") or member.get("uid", "Unknown")
                nickname = member.get("nickname", f"UID: {uid}")
                member_lines.append(f"{nickname}    `{uid}`")

            description = "\n".join(member_lines)
            if len(description) <= 4096:
                embed.description = description
            else:
                truncated_lines = []
                current_length = 0
                for line in member_lines:
                    if current_length + len(line) + 1 > 4096:
                        break
                    truncated_lines.append(line)
                    current_length += len(line) + 1
                embed.description = "\n".join(truncated_lines)
                embed.set_footer(text=f"... and {len(members) - len(truncated_lines)} more members")

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to fetch members: {e}", ephemeral=True)

    @app_commands.command(name="guild_changes", description="View recent membership changes")
    @app_commands.describe(limit="Number of changes to show (max 50)")
    async def guild_changes(self, interaction: discord.Interaction, limit: int = 20):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        limit = min(limit, 50)
        changes = get_channel_recent_changes(interaction.channel.id, limit)
        if not changes:
            await interaction.followup.send("📭 No membership changes recorded yet.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📊 Recent Changes ({len(changes)})",
            color=discord.Color.blue()
        )
        joined_count = sum(1 for c in changes if c["change_type"] == "joined")
        left_count = sum(1 for c in changes if c["change_type"] == "left")
        embed.add_field(name="✅ Joined", value=str(joined_count), inline=True)
        embed.add_field(name="❌ Left", value=str(left_count), inline=True)
        embed.add_field(name="📊 Total", value=str(len(changes)), inline=True)

        change_list = []
        for change in changes[:10]:
            emoji = "✅" if change["change_type"] == "joined" else "❌"
            nickname = change["nickname"] or f"UID: {change['uid']}"
            timestamp = change["timestamp"].split("T")[0]
            change_list.append(f"{emoji} {nickname} - {timestamp}")

        if change_list:
            embed.add_field(name="Recent Activity", value="\n".join(change_list), inline=False)
        if len(changes) > 10:
            embed.set_footer(text=f"... and {len(changes) - 10} more changes")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ban_player", description="Ban a player from the guild (Commanders only)")
    @app_commands.describe(uid="Player UID to ban", reason="Reason for ban")
    async def ban_player(self, interaction: discord.Interaction, uid: str, reason: str = "No reason provided"):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
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
        await log_action(
            interaction,
            "Player Banned",
            f"Player {uid} banned from guild monitoring in {interaction.channel.mention}. Reason: {reason}"
        )

    @app_commands.command(name="global_ban", description="Globally ban a player across all monitored guilds (Commanders only)")
    @app_commands.describe(uid="Player UID to globally ban", reason="Reason for global ban")
    async def global_ban(self, interaction: discord.Interaction, uid: str, reason: str = "No reason provided"):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_commander(interaction):
            await interaction.followup.send("❌ Only Commanders can globally ban players.", ephemeral=True)
            return

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
        embed.add_field(name="Affected Channels", value="\n".join([ch.mention for ch in banned_channels]), inline=False)

        await interaction.followup.send(embed=embed)
        await log_action(
            interaction,
            "Global Player Ban",
            f"Player {uid} globally banned across {len(banned_channels)} guilds. Reason: {reason}"
        )


async def setup(bot):
    await bot.add_cog(GuildMonitoringCog(bot))
