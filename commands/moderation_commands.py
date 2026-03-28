"""User Moderation & Discipline Commands"""
import discord
from discord import app_commands
from discord.ext import commands

class ModerationCommands(commands.Cog):
    """Commands for user moderation and discipline"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warn", description="Privately warn a user (Admins only)")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can warn users.", ephemeral=True)
            return
        try:
            await member.send(f"⚠️ You have been warned in {interaction.guild.name}.\nReason: {reason}")
            await interaction.response.send_message(f"{member.display_name} has been warned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Could not DM the user. They may have DMs disabled.", ephemeral=True)

    @app_commands.command(name="mute", description="Mute a user by assigning Muted role (Admins only)")
    async def mute(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can mute users.", ephemeral=True)
            return
        guild = interaction.guild
        role = discord.utils.get(guild.roles, name="Muted")
        if role is None:
            role = await guild.create_role(name="Muted")
            for channel in guild.channels:
                await channel.set_permissions(role, send_messages=False)
        await member.add_roles(role)
        await interaction.response.send_message(f"🔇 {member.display_name} has been muted.")

    @app_commands.command(name="unmute", description="Unmute a user by removing Muted role (Admins only)")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can unmute users.", ephemeral=True)
            return
        role = discord.utils.get(interaction.guild.roles, name="Muted")
        if role is None or role not in member.roles:
            await interaction.response.send_message(f"{member.display_name} is not muted.", ephemeral=True)
            return
        await member.remove_roles(role)
        await interaction.response.send_message(f"🔊 {member.display_name} has been unmuted.")


async def setup(bot):
    """Load moderation commands"""
    await bot.add_cog(ModerationCommands(bot))
