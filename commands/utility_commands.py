"""Utility Commands"""
import discord
from discord import app_commands
from discord.ext import commands
from helpers import is_commander

class UtilityCommands(commands.Cog):
    """General utility commands"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show available commands")
    async def help(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return

        commands = [
            "**📋 Member Commands** (`/members`)",
            "  • `/members setguild <text>` – Store guild list",
            "  • `/members setbound <text>` – Store bound list",
            "  • `/members notbind` – Guild members not bound",
            "  • `/members missing_player` – Bound members not in guild",
            "  • `/members showdata` – Preview lists",
            "  • `/members update <type> <id> <name>` – Update player name",
            "  • `/members clear` – Reset lists",
            "  • `/members count` – Show counts",
            "  • `/members export` – Export as CSV",
            "",
            "**👤 Commander Commands**",
            "  • `/addcommander <user>` – Promote user",
            "  • `/removecommander <user>` – Demote user",
            "  • `/listcommanders` – List all commanders",
            "",
            "**🔐 Channel Commands**",
            "  • `/lockchannel` – Lock channel",
            "  • `/unlockchannel` – Unlock channel",
            "",
            "**⚠️ Moderation Commands**",
            "  • `/warn <user> <reason>` – Warn user",
            "  • `/mute <user>` – Mute user",
            "  • `/unmute <user>` – Unmute user",
            "",
            "**🧹 Cleanup Commands**",
            "  • `/prune <amount>` – Delete messages",
            "  • `/pruneuser <user> <amount>` – Delete user messages",
        ]

        await interaction.response.send_message("**Available Commands:**\n" + "\n".join(commands))


async def setup(bot):
    """Load utility commands"""
    await bot.add_cog(UtilityCommands(bot))
