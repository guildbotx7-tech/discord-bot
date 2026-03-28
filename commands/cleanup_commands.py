"""Message Cleanup Commands"""
import discord
from discord import app_commands
from discord.ext import commands

class CleanupCommands(commands.Cog):
    """Commands for message management and cleanup"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="prune", description="Delete a number of recent messages")
    async def prune(self, interaction: discord.Interaction, amount: int):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to prune messages.", ephemeral=True)
            return
        if amount < 1 or amount > 100:
            await interaction.response.send_message("You can only delete between 1 and 100 messages.", ephemeral=True)
            return
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.response.send_message(f"🧹 Deleted {len(deleted)} messages.", ephemeral=True)

    @app_commands.command(name="pruneuser", description="Delete recent messages from a specific user")
    async def pruneuser(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to prune messages.", ephemeral=True)
            return
        if amount < 1 or amount > 100:
            await interaction.response.send_message("You can only delete between 1 and 100 messages.", ephemeral=True)
            return
        deleted = await interaction.channel.purge(limit=amount, check=lambda m: m.author == member)
        await interaction.response.send_message(f"🧹 Deleted {len(deleted)} messages from {member.display_name}.", ephemeral=True)


async def setup(bot):
    """Load cleanup commands"""
    await bot.add_cog(CleanupCommands(bot))
