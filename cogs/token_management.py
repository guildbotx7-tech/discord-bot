"""Owner-only commands for managing clan monitoring tokens.

SECURITY: Only the bot owner can register/manage access tokens.
Tokens are NEVER logged, displayed, or exposed to Discord.
"""

import discord
from discord.ext import commands

from token_manager import (
    is_token_registered,
    register_token,
    unregister_token,
    TokenStorageError,
)


class TokenManagementCog(commands.Cog):
    """Owner-only commands for token management."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="register_token")
    @commands.is_owner()
    async def register_clan_token(self, ctx, channel: discord.TextChannel = None):
        """Register this guild's clan monitoring token.

        IMPORTANT:
        1. Set the environment variable GUILD_TOKEN_<GUILD_ID> first
        2. Only the bot owner can run this command
        3. The token is NEVER displayed or logged

        Args:
            channel: Optional notification channel (uses current if not specified)

        Usage:
            !register_token              # Use current channel for notifications
            !register_token #announcements  # Use specific channel

        Setup:
            1. In .env or system environment, add:
               GUILD_TOKEN_123456789=your_secret_token_here
            2. Run: !register_token
            3. Monitoring will start automatically
        """
        try:
            guild_id = ctx.guild.id
            owner_id = ctx.author.id
            notification_channel = channel or ctx.channel

            register_token(guild_id, notification_channel.id, owner_id)

            # Confirm without revealing token
            embed = discord.Embed(
                title="✅ Token Registered",
                description=f"Clan monitoring activated for **{ctx.guild.name}**\nNotifications: {notification_channel.mention}",
                color=discord.Color.green(),
            )
            embed.set_footer(text="⚠️ Token is secure. Never logging or displaying it.")
            await ctx.send(embed=embed, ephemeral=True)

            # Log to owner DM for record
            try:
                await ctx.author.send(
                    f"✅ Token registered for guild **{ctx.guild.name}** ({guild_id})\n"
                    f"Notification channel: {notification_channel.mention}"
                )
            except Exception:
                pass

        except TokenStorageError as e:
            error_embed = discord.Embed(
                title="❌ Token Registration Failed",
                description=str(e),
                color=discord.Color.red(),
            )
            error_embed.set_footer(text="Check bot owner instructions")
            await ctx.send(embed=error_embed, ephemeral=True)

        except Exception as e:
            await ctx.send(f"❌ Unexpected error: {e}", ephemeral=True)

    @commands.command(name="token_status")
    @commands.is_owner()
    async def show_token_status(self, ctx):
        """Check if this guild has a registered token.

        Usage:
            !token_status

        Note:
            The actual token is never displayed for security.
        """
        try:
            guild_id = ctx.guild.id

            if is_token_registered(guild_id):
                embed = discord.Embed(
                    title="✅ Token Registered",
                    description=f"**{ctx.guild.name}** has an active token for clan monitoring.",
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="❌ No Token",
                    description=f"**{ctx.guild.name}** does not have a registered token.\nUse `!register_token` to set one up.",
                    color=discord.Color.red(),
                )

            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            await ctx.send(f"❌ Error: {e}", ephemeral=True)

    @commands.command(name="unregister_token")
    @commands.is_owner()
    async def unregister_clan_token(self, ctx):
        """Unregister this guild's token and stop monitoring.

        WARNING: This will disable clan monitoring for this guild.

        Usage:
            !unregister_token

        Note:
            The .env variable should manually be removed or cleared.
        """
        try:
            guild_id = ctx.guild.id
            owner_id = ctx.author.id

            if not is_token_registered(guild_id):
                await ctx.send(
                    "No token registered for this guild.",
                    ephemeral=True,
                )
                return

            unregister_token(guild_id, owner_id)

            embed = discord.Embed(
                title="⏹️ Token Unregistered",
                description=f"Clan monitoring stopped for **{ctx.guild.name}**",
                color=discord.Color.orange(),
            )
            embed.set_footer(text="⚠️ Also manually remove/clear GUILD_TOKEN_ from .env")
            await ctx.send(embed=embed, ephemeral=True)

            # Notify owner
            try:
                await ctx.author.send(
                    f"⏹️ Token unregistered for guild **{ctx.guild.name}** ({guild_id})"
                )
            except Exception:
                pass

        except Exception as e:
            await ctx.send(f"❌ Error: {e}", ephemeral=True)

    @register_clan_token.error
    @show_token_status.error
    @unregister_clan_token.error
    async def token_commands_error(self, ctx, error):
        """Handle token command errors."""
        if isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                title="🔒 Access Denied",
                description="Only the bot owner can manage tokens.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, ephemeral=True)
        else:
            await ctx.send(f"❌ Error: {error}", ephemeral=True)


async def setup(bot):
    """Load the cog into the bot."""
    await bot.add_cog(TokenManagementCog(bot))
