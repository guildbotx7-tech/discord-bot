"""Discord bot commands for viewing Free Fire guild membership changes."""

import discord
from discord.ext import commands

from guild_monitoring import get_recent_changes


class GuildMonitoringCog(commands.Cog):
    """Commands for viewing Free Fire guild membership tracking."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="guild_changes", aliases=["gc", "guild_history"])
    @commands.has_permissions(administrator=True)
    async def show_guild_changes(self, ctx, limit: int = 20):
        """Display recent guild membership changes.

        Args:
            limit: Number of recent changes to show (default: 20, max: 100).

        Usage:
            !guild_changes          # Show last 20 changes
            !guild_changes 50       # Show last 50 changes
            !gc                     # Alias

        Shows who joined and who left the Free Fire guild.
        """
        try:
            limit = min(limit, 100)  # Cap at 100
            guild_id = ctx.guild.id

            changes = get_recent_changes(guild_id, limit)

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

    @commands.command(name="guild_joins")
    @commands.has_permissions(administrator=True)
    async def show_recent_joins(self, ctx, limit: int = 10):
        """Show who recently joined the guild.

        Usage:
            !guild_joins            # Show last 10 joins
            !guild_joins 20         # Show last 20 joins
        """
        try:
            limit = min(limit, 50)
            guild_id = ctx.guild.id
            all_changes = get_recent_changes(guild_id, 100)

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

    @commands.command(name="guild_leaves")
    @commands.has_permissions(administrator=True)
    async def show_recent_leaves(self, ctx, limit: int = 10):
        """Show who recently left the guild.

        Usage:
            !guild_leaves           # Show last 10 leaves
            !guild_leaves 20        # Show last 20 leaves
        """
        try:
            limit = min(limit, 50)
            guild_id = ctx.guild.id
            all_changes = get_recent_changes(guild_id, 100)

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

    @commands.command(name="guild_stats")
    @commands.has_permissions(administrator=True)
    async def show_guild_stats(self, ctx):
        """Display guild membership statistics.

        Shows total joins, leaves, and net change.

        Usage:
            !guild_stats
        """
        try:
            guild_id = ctx.guild.id
            all_changes = get_recent_changes(guild_id, 1000)

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


async def setup(bot):
    """Load the cog into the bot."""
    await bot.add_cog(GuildMonitoringCog(bot))