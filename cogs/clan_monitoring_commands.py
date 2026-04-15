"""Discord bot commands for viewing guild membership changes."""

import discord
from discord.ext import commands

from clan_monitoring import (
    get_recent_changes,
    get_flagged_movements,
    add_monitored_player,
    remove_monitored_player,
    get_monitored_players,
    is_player_monitored
)
from channel_guild_monitoring import get_channel_guild_id


class ClanMonitoringCog(commands.Cog):
    """Commands for viewing Free Fire guild membership tracking."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="guild_changes", aliases=["cc", "clan_history", "clan_changes"])
    @commands.has_permissions(administrator=True)
    async def show_clan_changes(self, ctx, limit: int = 20):
        """Display recent guild membership changes.

        Args:
            limit: Number of recent changes to show (default: 20, max: 100).

        Usage:
            !guild_changes          # Show last 20 changes
            !guild_changes 50       # Show last 50 changes
            !cc                    # Alias
        """
        try:
            limit = min(limit, 100)  # Cap at 100
            clan_id = ctx.guild.id

            changes = get_recent_changes(clan_id, limit)

            if not changes:
                embed = discord.Embed(
                    title="📊 Guild Membership Changes",
                    description="No membership changes recorded yet.",
                    color=discord.Color.greyple(),
                )
                await ctx.send(embed=embed)
                return

            # Build embed with changes
            embed = discord.Embed(
                title="📊 Guild Membership Changes",
                description=f"Showing last {len(changes)} changes",
                color=discord.Color.blue(),
            )

            joined_count = sum(1 for c in changes if c["change_type"] == "joined")
            left_count = sum(1 for c in changes if c["change_type"] == "left")

            embed.add_field(name="✅ Joined", value=str(joined_count), inline=True)
            embed.add_field(name="❌ Left", value=str(left_count), inline=True)
            embed.add_field(name="⏱️ Total", value=str(len(changes)), inline=True)

            # Add recent changes (limit to 10 fields due to embed limits)
            changes_display = changes[:10]
            for change in changes_display:
                emoji = "✅" if change["change_type"] == "joined" else "❌"
                nickname = change["nickname"] or f"UID: {change['uid']}"
                timestamp = change["timestamp"].split("T")[0]  # Date only

                field_value = f"{nickname}\nUID: {change['uid']}\n{timestamp}"
                embed.add_field(
                    name=f"{emoji} {change['change_type'].upper()}",
                    value=field_value,
                    inline=False,
                )

            if len(changes) > 10:
                embed.set_footer(text=f"... and {len(changes) - 10} more changes")

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error retrieving guild changes: {e}")

    @commands.command(name="guild_joins", aliases=["clan_joins"])
    @commands.has_permissions(administrator=True)
    async def show_recent_joins(self, ctx, limit: int = 10):
        """Show who recently joined the guild.

        Usage:
            !guild_joins            # Show last 10 joins
            !guild_joins 20         # Show last 20 joins
        """
        try:
            limit = min(limit, 50)
            clan_id = ctx.guild.id
            all_changes = get_recent_changes(clan_id, 100)

            joins = [c for c in all_changes if c["change_type"] == "joined"][:limit]

            if not joins:
                await ctx.send("📭 No recent joins logged.")
                return

            embed = discord.Embed(
                title="✅ Recent Guild Joins",
                description=f"{len(joins)} member(s) joined recently",
                color=discord.Color.green(),
            )

            for join in joins:
                nickname = join["nickname"] or f"UID: {join['uid']}"
                timestamp = join["timestamp"].split("T")[0]
                embed.add_field(
                    name=nickname,
                    value=f"UID: {join['uid']}\nJoined: {timestamp}",
                    inline=False,
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @commands.command(name="guild_leaves", aliases=["clan_leaves"])
    @commands.has_permissions(administrator=True)
    async def show_recent_leaves(self, ctx, limit: int = 10):
        """Show who recently left the guild.

        Usage:
            !guild_leaves           # Show last 10 leaves
            !guild_leaves 20        # Show last 20 leaves
        """
        try:
            limit = min(limit, 50)
            clan_id = ctx.guild.id
            all_changes = get_recent_changes(clan_id, 100)

            leaves = [c for c in all_changes if c["change_type"] == "left"][:limit]

            if not leaves:
                await ctx.send("📭 No recent leaves logged.")
                return

            embed = discord.Embed(
                title="❌ Recent Guild Leaves",
                description=f"{len(leaves)} member(s) left recently",
                color=discord.Color.red(),
            )

            for leave in leaves:
                nickname = leave["nickname"] or f"UID: {leave['uid']}"
                timestamp = leave["timestamp"].split("T")[0]
                embed.add_field(
                    name=nickname or "Unknown",
                    value=f"UID: {leave['uid']}\nLeft: {timestamp}",
                    inline=False,
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @commands.command(name="guild_stats", aliases=["clan_stats"])
    @commands.has_permissions(administrator=True)
    async def show_clan_stats(self, ctx):
        """Display guild membership statistics.

        Shows total joins, leaves, and net change.

        Usage:
            !guild_stats
        """
        try:
            clan_id = ctx.guild.id
            all_changes = get_recent_changes(clan_id, 1000)

            joined_count = sum(1 for c in all_changes if c["change_type"] == "joined")
            left_count = sum(1 for c in all_changes if c["change_type"] == "left")
            net_change = joined_count - left_count

            embed = discord.Embed(
                title="📈 Guild Membership Statistics",
                color=discord.Color.gold(),
            )

            embed.add_field(name="✅ Total Joins", value=str(joined_count), inline=True)
            embed.add_field(name="❌ Total Leaves", value=str(left_count), inline=True)
            net_emoji = "📈" if net_change > 0 else "📉" if net_change < 0 else "➡️"
            embed.add_field(name=f"{net_emoji} Net Change", value=str(net_change), inline=True)

            if all_changes:
                latest = all_changes[0]
                embed.set_footer(text=f"Last event: {latest['timestamp']}")

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @commands.command(name="flagged_movements", aliases=["fm", "rival_moves", "partnered_moves", "partnered_movements"])
    @commands.has_permissions(administrator=True)
    async def show_flagged_movements(self, ctx, limit: int = 20):
        """Display recent partnered player movements to partnered guilds.

        Args:
            limit: Number of recent partnered movements to show (default: 20, max: 50).

        Usage:
            !flagged_movements     # Show last 20 partnered movements
            !flagged_movements 10  # Show last 10 partnered movements
            !fm                    # Alias
        """
        try:
            limit = min(limit, 50)  # Cap at 50

            movements = get_flagged_movements(limit)

            if not movements:
                embed = discord.Embed(
                    title="🚨 Partnered Player Movements",
                    description="No partnered movements detected yet.",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed)
                return

            # Build embed with partnered movements
            embed = discord.Embed(
                title="🚨 Partnered Player Movements",
                description=f"Players who moved to partnered guilds\nShowing last {len(movements)} movements",
                color=discord.Color.red(),
            )

            movement_text = ""
            for movement in movements:
                nickname = movement["nickname"] or "Unknown"
                movement_text += (
                    f"**{nickname}** (UID: `{movement['uid']}`)\n"
                    f"From: `{movement['from_clan_id']}` → To: `{movement['to_clan_id']}`\n"
                    f"Time: {movement['timestamp']}\n\n"
                )

            if len(movement_text) > 4000:  # Discord embed limit
                movement_text = movement_text[:4000] + "..."

            embed.add_field(name="Recent Movements", value=movement_text or "None", inline=False)

            embed.set_footer(text="🚨 These players moved to partnered guilds!")

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @commands.command(name="monitor_player", aliases=["mp", "watch_player"])
    @commands.has_permissions(administrator=True)
    async def monitor_player(self, ctx, uid: str, duration_hours: int):
        """Add a specific player to monitoring.

        Args:
            uid: Free Fire UID to monitor.
            duration_hours: Hours to monitor (max 4380).

        Usage:
            !monitor_player 1281687888 24
            !mp 1281687888 48
        """
        try:
            # Validate UID
            try:
                ff_uid = int(uid)
            except ValueError:
                await ctx.send("❌ Invalid UID. Must be a number.")
                return

            # Validate duration
            if duration_hours is None or duration_hours < 1 or duration_hours > 4380:
                await ctx.send("❌ Duration must be between 1 and 4380 hours.")
                return

            guild_id = get_channel_guild_id(ctx.channel.id)
            if not guild_id:
                await ctx.send("❌ No guild is registered for this channel. Register a guild first.")
                return

            # Check if already monitored for this channel
            if is_player_monitored(ff_uid, ctx.channel.id):
                await ctx.send(f"❌ Player UID `{ff_uid}` is already being monitored for this guild.")
                return

            # Try to get player nickname
            nickname = None
            try:
                from member_clan_api import fetch_player_info
                player_info = fetch_player_info(ff_uid)
                if player_info and "basicInfo" in player_info:
                    nickname = player_info["basicInfo"].get("nickname")
            except:
                pass

            # Add to monitoring
            success = add_monitored_player(ff_uid, nickname, duration_hours, ctx.author.id, ctx.channel.id)

            if success:
                embed = discord.Embed(
                    title="👁️ Player Added to Monitoring",
                    color=discord.Color.orange(),
                )
                embed.add_field(name="Player", value=f"{nickname or 'Unknown'} (UID: `{ff_uid}`)", inline=False)

                duration_label = "Indefinite" if duration_hours is None else f"{duration_hours} hours"
                embed.add_field(name="Duration", value=duration_label, inline=True)
                embed.add_field(name="Added by", value=ctx.author.mention, inline=True)
                embed.set_footer(text="Player activity will be monitored and alerted")

                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Failed to add player to monitoring.")

        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @commands.command(name="stop_monitoring", aliases=["sm", "unwatch_player"])
    @commands.has_permissions(administrator=True)
    async def stop_monitoring(self, ctx, uid: str):
        """Remove a player from monitoring.

        Args:
            uid: Free Fire UID to stop monitoring.

        Usage:
            !stop_monitoring 1281687888
            !sm 1281687888
        """
        try:
            # Validate UID
            try:
                ff_uid = int(uid)
            except ValueError:
                await ctx.send("❌ Invalid UID. Must be a number.")
                return

            guild_id = get_channel_guild_id(ctx.channel.id)
            if not guild_id:
                await ctx.send("❌ No guild is registered for this channel. Register a guild first.")
                return

            # Check if monitored for this channel
            if not is_player_monitored(ff_uid, ctx.channel.id):
                await ctx.send(f"❌ Player UID `{ff_uid}` is not currently being monitored for this guild.")
                return

            # Remove from monitoring
            success = remove_monitored_player(ff_uid, ctx.channel.id)

            if success:
                embed = discord.Embed(
                    title="❌ Player Removed from Monitoring",
                    description=f"Player UID `{ff_uid}` is no longer being monitored.",
                    color=discord.Color.greyple(),
                )
                embed.set_footer(text="Monitoring stopped")
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Failed to remove player from monitoring.")

        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @commands.command(name="list_monitored", aliases=["lm", "monitored_players"])
    @commands.has_permissions(administrator=True)
    async def list_monitored(self, ctx):
        """List all currently monitored players.

        Usage:
            !list_monitored
            !lm
        """
        try:
            guild_id = get_channel_guild_id(ctx.channel.id)
            if not guild_id:
                await ctx.send("❌ No guild is registered for this channel. Register a guild first.")
                return

            monitored_players = get_monitored_players(ctx.channel.id)

            if not monitored_players:
                embed = discord.Embed(
                    title="👁️ Monitored Players",
                    description="No players are currently being monitored.",
                    color=discord.Color.greyple(),
                )
                await ctx.send(embed=embed)
                return

            # Build embed with monitored players
            embed = discord.Embed(
                title="👁️ Monitored Players",
                description=f"Currently monitoring {len(monitored_players)} players",
                color=discord.Color.orange(),
            )

            player_text = ""
            for player in monitored_players:
                nickname = player["nickname"] or "Unknown"
                player_text += (
                    f"**{nickname}** (UID: `{player['ff_uid']}`)\n"
                    f"Ends: {player['monitoring_end'][:19]}\n\n"
                )

            if len(player_text) > 4000:  # Discord embed limit
                player_text = player_text[:4000] + "..."

            embed.add_field(name="Active Monitoring", value=player_text or "None", inline=False)
            embed.set_footer(text="👁️ These players are being actively monitored for guild activity")

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {e}")


async def setup(bot):
    """Load the cog into the bot."""
    await bot.add_cog(ClanMonitoringCog(bot))
