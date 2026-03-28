"""Guild & Bound Member List Commands"""
import discord
from discord import app_commands
from discord.ext import commands
import io, csv
from helpers import get_channel_data, update_channel_data, clear_channel_data, is_commander, parse_member_lines

class MemberCommands(commands.Cog):
    """Commands for managing guild and bound member lists"""
    
    def __init__(self, bot):
        self.bot = bot

    member_group = app_commands.Group(name="members", description="Guild & Bound member list commands")

    @member_group.command(name="setguild", description="Store guild member list")
    async def setguild(self, interaction: discord.Interaction, text: str):
        if not is_commander(interaction):
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return
        channel_id = interaction.channel_id
        guild_members = parse_member_lines(text, interaction.client.ID_RE)
        update_channel_data(channel_id, guild=guild_members)
        await interaction.response.send_message(f"Stored {len(guild_members)} guild members.")

    @member_group.command(name="setbound", description="Store bound member list")
    async def setbound(self, interaction: discord.Interaction, text: str):
        if not is_commander(interaction):
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return
        channel_id = interaction.channel_id
        bound_members = parse_member_lines(text, interaction.client.ID_RE)
        update_channel_data(channel_id, bound=bound_members)
        await interaction.response.send_message(f"Stored {len(bound_members)} bound members.")

    @member_group.command(name="notbind", description="Show guild members not yet bound")
    async def notbind(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return
        channel_id = interaction.channel_id
        guild, bound = get_channel_data(channel_id)
        if not guild or not bound:
            await interaction.response.send_message("Use /members setguild and /members setbound first.")
            return
        rows = [(guild[i], i) for i in guild if i not in bound]
        if not rows:
            await interaction.response.send_message("All guild members are bound.")
            return
        csv_text = "Display Name,ID\n" + "\n".join(f"{n},{i}" for n,i in rows)
        await interaction.response.send_message(f"**Guild members not bound:**\n```csv\n{csv_text}\n```")

    @member_group.command(name="missing_player", description="Show bound members not in guild")
    async def missing_player(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return
        channel_id = interaction.channel_id
        guild, bound = get_channel_data(channel_id)
        if not guild or not bound:
            await interaction.response.send_message("Use /members setguild and /members setbound first.")
            return
        rows = [(bound[i], i) for i in bound if i not in guild]
        if not rows:
            await interaction.response.send_message("All bound members are in the guild.")
            return
        csv_text = "Display Name,ID\n" + "\n".join(f"{n},{i}" for n,i in rows)
        await interaction.response.send_message(f"**Bound members not in guild:**\n```csv\n{csv_text}\n```")

    @member_group.command(name="showdata", description="Show stored guild and bound lists")
    async def showdata(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return
        channel_id = interaction.channel_id
        guild, bound = get_channel_data(channel_id)
        if not guild and not bound:
            await interaction.response.send_message("No data stored yet. Use /members setguild and /members setbound first.")
            return
        guild_text = "\n".join([f"{n},{i}" for i,n in guild.items()][:10]) or "No guild members stored."
        bound_text = "\n".join([f"{n},{i}" for i,n in bound.items()][:10]) or "No bound members stored."
        await interaction.response.send_message(
            f"**Guild list (first 10):**\n```csv\n{guild_text}\n```\n"
            f"**Bound list (first 10):**\n```csv\n{bound_text}\n```"
        )

    @member_group.command(name="update", description="Update a player's name in guild or bound list")
    async def update(self, interaction: discord.Interaction, list_type: str, player_id: str, new_name: str):
        if not is_commander(interaction):
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return
        channel_id = interaction.channel_id
        guild, bound = get_channel_data(channel_id)
        if not guild and not bound:
            await interaction.response.send_message("No data stored yet. Use /members setguild and /members setbound first.")
            return
        if list_type.lower() not in ["guild", "bound"]:
            await interaction.response.send_message("Invalid list type. Use 'guild' or 'bound'.", ephemeral=True)
            return
        target_list = guild if list_type.lower() == "guild" else bound
        if player_id not in target_list:
            await interaction.response.send_message(f"Player ID {player_id} not found in {list_type} list.", ephemeral=True)
            return
        target_list[player_id] = new_name
        if list_type.lower() == "guild":
            update_channel_data(channel_id, guild=guild)
        else:
            update_channel_data(channel_id, bound=bound)
        await interaction.response.send_message(f"Updated {list_type} list: ID {player_id} → {new_name}")

    @member_group.command(name="clear", description="Clear stored guild and bound lists")
    async def clear(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return
        channel_id = interaction.channel_id
        clear_channel_data(channel_id)
        await interaction.response.send_message("Cleared guild and bound lists for this channel.")

    @member_group.command(name="count", description="Show counts of guild and bound lists")
    async def count(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return
        channel_id = interaction.channel_id
        guild, bound = get_channel_data(channel_id)
        guild_count = len(guild)
        bound_count = len(bound)
        await interaction.response.send_message(f"Guild list: {guild_count} members\nBound list: {bound_count} members")

    @member_group.command(name="export", description="Export guild-only members as CSV")
    async def export(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return
        channel_id = interaction.channel_id
        guild, bound = get_channel_data(channel_id)
        rows = [(guild[i], i) for i in guild if i not in bound]
        if not rows:
            await interaction.response.send_message("No differences found.")
            return
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Display Name","ID"])
        for name,id_ in rows:
            writer.writerow([name,id_])
        file = discord.File(io.BytesIO(buf.getvalue().encode("utf-8")), filename="guild_only.csv")
        await interaction.response.send_message("Here's the CSV file:", file=file)


async def setup(bot):
    """Load member commands"""
    await bot.add_cog(MemberCommands(bot))
