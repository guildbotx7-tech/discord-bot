"""Commander Role Management Commands"""
import discord
from discord import app_commands
from discord.ext import commands

class CommanderCommands(commands.Cog):
    """Commands for managing the Commander role"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="addcommander", description="Grant Commander role to a user (Admins only)")
    async def addcommander(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can add Commanders.", ephemeral=True)
            return
        guild = interaction.guild
        role = discord.utils.get(guild.roles, name="Commander")
        if role is None:
            role = await guild.create_role(name="Commander", permissions=discord.Permissions.none())
        await member.add_roles(role)
        await interaction.response.send_message(f"✅ {member.display_name} has been promoted to Commander.")

    @app_commands.command(name="removecommander", description="Remove Commander role from a user (Admins only)")
    async def removecommander(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can remove Commanders.", ephemeral=True)
            return
        role = discord.utils.get(interaction.guild.roles, name="Commander")
        if role is None or role not in member.roles:
            await interaction.response.send_message(f"{member.display_name} is not a Commander.", ephemeral=True)
            return
        await member.remove_roles(role)
        await interaction.response.send_message(f"❌ {member.display_name} has been removed from Commander role.")

    @app_commands.command(name="listcommanders", description="List all users with the Commander role")
    async def listcommanders(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can list Commanders.", ephemeral=True)
            return
        role = discord.utils.get(interaction.guild.roles, name="Commander")
        if role is None or not role.members:
            await interaction.response.send_message("No users currently have the Commander role.")
            return
        members_list = "\n".join([m.display_name for m in role.members])
        await interaction.response.send_message(f"**Commanders:**\n{members_list}")


async def setup(bot):
    """Load commander commands"""
    await bot.add_cog(CommanderCommands(bot))
