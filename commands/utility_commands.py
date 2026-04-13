"""Utility Commands"""
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from pathlib import Path
from helpers import is_commander, set_log_channel_async, get_log_channel_async, safe_send, log_action
from version import increment_version, get_version_string


class HelpView(discord.ui.View):
    def __init__(self, command_sections):
        super().__init__(timeout=300)
        self.command_sections = command_sections
        self.page = 0
        self.total_pages = len(command_sections)

        options = [
            discord.SelectOption(label=section_title, value=str(index))
            for index, (section_title, _) in enumerate(command_sections)
        ]
        self.section_select = discord.ui.Select(placeholder="Jump to section", options=options)
        self.section_select.callback = self.select_page
        self.add_item(self.section_select)

        self.update_buttons()

    def update_buttons(self):
        # Keep the section select at the top and refresh navigation buttons below it.
        existing_select = self.section_select
        self.clear_items()
        self.add_item(existing_select)

        if self.page > 0:
            prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.primary)
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
        if self.page < self.total_pages - 1:
            next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary)
            next_button.callback = self.next_page
            self.add_item(next_button)

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_buttons()
        await self.update_message(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_buttons()
        await self.update_message(interaction)

    async def select_page(self, interaction: discord.Interaction):
        if interaction.data and "values" in interaction.data and interaction.data["values"]:
            self.page = int(interaction.data["values"][0])
        self.update_buttons()
        await self.update_message(interaction)

    def get_page_content(self):
        section_title, commands = self.command_sections[self.page]
        content = f"**{section_title}**\n" + "\n".join(commands)
        return content

    async def update_message(self, interaction: discord.Interaction):
        content = self.get_page_content()
        embed = discord.Embed(
            title=f"📚 Help (Page {self.page + 1}/{self.total_pages})",
            description=content,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Use Previous/Next buttons or jump to a section")

        await interaction.response.edit_message(embed=embed, view=self)


class UtilityCommands(commands.Cog):
    """General utility commands"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setlogchannel", description="Set the log channel for bot actions (Commanders only)")
    async def setlogchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_commander(interaction) and interaction.user.id != self.bot.owner_id:
            await safe_send(interaction, "Only Commanders can set the log channel.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /setlogchannel without permission.")
            return
        await set_log_channel_async(interaction.guild_id, channel.id)
        await safe_send(interaction, f"✅ Log channel set to {channel.mention}", ephemeral=True)
        await log_action(interaction, "Log Channel Updated", f"{interaction.user.mention} set the log channel to {channel.mention}.")

    @app_commands.command(name="getlogchannel", description="Show the current log channel")
    async def getlogchannel(self, interaction: discord.Interaction):
        log_channel_id = await get_log_channel_async(interaction.guild_id)
        if not log_channel_id:
            await safe_send(interaction, "No log channel set yet. Use `/setlogchannel` to set one.", ephemeral=True)
            await log_action(interaction, "Get Log Channel", f"{interaction.user.mention} checked log channel: Not set.")
        else:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                await safe_send(interaction, f"📋 Current log channel: {log_channel.mention}", ephemeral=True)
                await log_action(interaction, "Get Log Channel", f"{interaction.user.mention} viewed log channel: {log_channel.mention}")
            else:
                await safe_send(interaction, "Log channel no longer exists. Use `/setlogchannel` to set a new one.", ephemeral=True)
                await log_action(interaction, "Get Log Channel", f"{interaction.user.mention} checked log channel: Channel no longer exists.")

    @app_commands.command(name="pingdb", description="Check SQLite database connection status")
    async def pingdb(self, interaction: discord.Interaction):
        """Utility: Ping SQLite database status"""
        try:
            db_path = Path(__file__).parent.parent / "discord_bot.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            await safe_send(interaction, "✅ SQLite database is connected", ephemeral=True)
            await log_action(interaction, "Database Ping", f"{interaction.user.mention} pinged SQLite database - Connected.")
        except Exception as e:
            await safe_send(interaction, f"❌ SQLite database connection failed: {str(e)}", ephemeral=True)
            await log_action(interaction, "Database Ping", f"{interaction.user.mention} pinged SQLite database - Connection failed: {str(e)}")

    @app_commands.command(name="version", description="Show the current bot version")
    async def version(self, interaction: discord.Interaction):
        version_value = getattr(self.bot, "version", "unknown")
        await safe_send(interaction, f"🤖 Bot version: `{version_value}`", ephemeral=False)

    @app_commands.command(name="increment_version", description="Increment bot version (Owner only)")
    @app_commands.describe(change_type="Type of change: major, minor, or patch")
    async def increment_version_cmd(self, interaction: discord.Interaction, change_type: str):
        # Check if user is the bot owner
        if interaction.user.id != self.bot.owner_id:
            await safe_send(interaction, "❌ Only the bot owner can update the bot version.", ephemeral=True)
            return

        change_type = change_type.lower()
        if change_type not in ['major', 'minor', 'patch']:
            await safe_send(interaction, "❌ Invalid change type. Use 'major', 'minor', or 'patch'.", ephemeral=True)
            return

        try:
            old_version = get_version_string()
            new_version_info = increment_version(change_type)
            new_version = get_version_string()

            # Update bot's version attribute
            self.bot.version = new_version
            self.bot.version_info = new_version_info

            await safe_send(interaction, f"✅ Version updated: `{old_version}` → `{new_version}`", ephemeral=False)
            await log_action(interaction, "Version Updated", f"Updated bot version from {old_version} to {new_version} ({change_type} change)")

        except Exception as e:
            await safe_send(interaction, f"❌ Failed to update version: {e}", ephemeral=True)

    @app_commands.command(name="help", description="Show available commands")
    async def help(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            return

        # Organize commands into sections for pagination
        command_sections = [
            ("📋 Member Commands", [
                "  • `/setguild <text>` – Store guild list",
                "  • `/setbound <text>` – Store bound list",
                "  • `/notbind` – Guild members not bound",
                "  • `/missing_player` – Bound members not in guild",
                "  • `/showdata` – Preview lists",
                "  • `/update <type> <id> <name>` – Update player name",
                "  • `/clear` – Reset lists",
                "  • `/count` – Show counts",
                "  • `/exportdiff` – Export guild-only members (CSV)"
            ]),
            ("⚔️ Guild Reconciliation Commands", [
                "  • `/currentmembers` – Show current guild members",
                "  • `/guildupdates` – Update guild and show changes",
                "  • `/clearguild` – Clear guild data (Head Commander only)",
                "  • `/editguild <text>` – Edit guild members (Head Commander only)",
                "  • `/guildhistory` – Show guild change history",
                "  • `/resethistory` – Clear history (Head Commander only)",
                "  • `/export <type> <format>` – Export guild data",
                "  • `/exportall` – Export all data as ZIP",
                "  • `/addheadcommander <user>` – Add Head Commander role",
                "  • `/removeheadcommander <user>` – Remove Head Commander role",
                "  • `/listheadcommanders` – List all Head Commanders"
            ]),
            ("👤 Commander Commands", [
                "  • `/addcommander <user>` – Promote user",
                "  • `/removecommander <user>` – Demote user",
                "  • `/listcommanders` – List all commanders"
            ]),
            ("🔐 Channel Commands", [
                "  • `/lockchannel` – Lock channel",
                "  • `/unlockchannel` – Unlock channel"
            ]),
            ("⚠️ Moderation Commands", [
                "  • `/warnuid` – Warn players by UID (modal)",
                "  • `/warnings <uid>` – View warnings for UID",
                "  • `/listwarnings` – List all warned members",
                "  • `/clearwarnings <uid>` – Clear warnings (Admin)",
                "  • `/check_glory` – Check glory levels below threshold",
                "  • `/view_glory` – View all glory levels",
                "  • `/glory_warn` – Auto-warn players below threshold",
                "  • `/set_glory_threshold <threshold>` – Set glory threshold",
                "  • `/update_glory` – Update glory data (modal)",
                "  • `/add_glory_exception <uid> <reason>` – Exempt player",
                "  • `/remove_glory_exception <uid>` – Remove exception",
                "  • `/list_glory_exceptions` – View exceptions",
                "  • `/mute <user>` – Mute user",
                "  • `/unmute <user>` – Unmute user"
            ]),
            ("🧹 Cleanup Commands", [
                "  • `/prune <amount>` – Delete messages",
                "  • `/pruneuser <user> <amount>` – Delete user messages"
            ]),
            ("📊 Logging Commands", [
                "  • `/setlogchannel <channel>` – Set log channel",
                "  • `/getlogchannel` – View log channel",
                "  • `/pingdb` – Check database connection",
                "  • `/version` – Show current bot version"
            ]),
            ("🔥 Guild Monitoring Commands", [
                "  • `/register_guild` – Register guild for monitoring",
                "  • `/remove_guild` – Remove guild registration",
                "  • `/guild_status` – Check monitoring status",
                "  • `/guild_updates` – View current members and recent changes",
                "  • `/guild_members` – View current guild members with guild info",
                "  • `/guild_changes` – View all current guild members with detailed data",
                "  • `/ban_player` – Ban player from guild",
                "  • `/global_ban` – Globally ban player",
                "  • `/set_monitoring_cycle` – Set monitoring interval"
            ])
        ]

        # Create paginated view
        view = HelpView(command_sections)
        embed = discord.Embed(
            title=f"📚 Help (Page 1/{view.total_pages})",
            description=view.get_page_content(),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Use Previous/Next buttons to navigate")

        try:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except discord.HTTPException as e:
            if getattr(e, 'code', None) == 40060:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                raise


async def setup(bot):
    """Load utility commands"""
    await bot.add_cog(UtilityCommands(bot))
