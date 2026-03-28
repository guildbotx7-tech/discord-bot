"""Channel Control Commands"""
import discord
from discord import app_commands
from discord.ext import commands

class ChannelCommands(commands.Cog):
    """Commands for managing channel permissions"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="lockchannel", description="Lock the current channel (Admins only)")
    async def lockchannel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can lock channels.", ephemeral=True)
            return
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔒 Channel locked.")

    @app_commands.command(name="unlockchannel", description="Unlock the current channel (Admins only)")
    async def unlockchannel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can unlock channels.", ephemeral=True)
            return
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = True
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔓 Channel unlocked.")


async def setup(bot):
    """Load channel commands"""
    await bot.add_cog(ChannelCommands(bot))
