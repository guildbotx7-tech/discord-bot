"""Utility Commands"""
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import shutil
from pathlib import Path
import zipfile
import io
from datetime import datetime
from helpers import is_commander, set_log_channel_async, get_log_channel_async, safe_send, log_action, get_ist_now
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
                "  • `/exportdb` – Export all databases (Owner only)",
                "  • `/importdb <backup_file>` – Import databases from backup (Owner only)",
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

    @app_commands.command(name="exportdb", description="Export SQLite databases (Owner only)")
    async def exportdb(self, interaction: discord.Interaction):
        """Owner-exclusive command to export all SQLite databases as a compressed ZIP"""
        # Check if user is the bot owner
        if interaction.user.id != self.bot.owner_id:
            await safe_send(interaction, "❌ Only the bot owner can export databases.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Get database file paths
            bot_dir = Path(__file__).parent.parent
            discord_db = bot_dir / "discord_bot.db"
            clan_db = bot_dir / "clan_monitoring.db"

            # Create a ZIP file in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add discord_bot.db if it exists
                if discord_db.exists():
                    zip_file.write(discord_db, arcname="discord_bot.db")

                # Add clan_monitoring.db if it exists
                if clan_db.exists():
                    zip_file.write(clan_db, arcname="clan_monitoring.db")

            zip_buffer.seek(0)

            # Create a filename with timestamp
            timestamp = get_ist_now().strftime("%Y%m%d_%H%M%S")
            filename = f"discord_bot_backup_{timestamp}.zip"

            # Send the ZIP file as attachment
            file = discord.File(zip_buffer, filename=filename)
            await interaction.followup.send(
                f"📦 Database backup exported successfully",
                file=file,
                ephemeral=True
            )

            await log_action(interaction, "Database Export", f"{interaction.user.mention} exported SQLite databases")

        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to export databases: {str(e)}",
                ephemeral=True
            )
            await log_action(interaction, "Database Export Failed", f"{interaction.user.mention} failed to export databases: {str(e)}")

    @app_commands.command(name="importdb", description="Import SQLite databases from backup (Owner only)")
    @app_commands.describe(backup_file="Upload the backup ZIP file exported from /exportdb")
    async def importdb(self, interaction: discord.Interaction, backup_file: discord.Attachment):
        """Owner-exclusive command to import SQLite databases from a backup ZIP"""
        # Check if user is the bot owner
        if interaction.user.id != self.bot.owner_id:
            await safe_send(interaction, "❌ Only the bot owner can import databases.", ephemeral=True)
            return

        # Check if the attachment is a ZIP file
        if not backup_file.filename.endswith('.zip'):
            await safe_send(interaction, "❌ Please upload a ZIP file (typically `discord_bot_backup_*.zip`).", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Get database file paths
            bot_dir = Path(__file__).parent.parent
            discord_db = bot_dir / "discord_bot.db"
            clan_db = bot_dir / "clan_monitoring.db"

            # Download the ZIP file
            zip_buffer = io.BytesIO()
            await backup_file.save(zip_buffer)
            zip_buffer.seek(0)

            # Create backup of current databases (with timestamp)
            timestamp = get_ist_now().strftime("%Y%m%d_%H%M%S")
            backup_dir = bot_dir / "backups"
            backup_dir.mkdir(exist_ok=True)

            if discord_db.exists():
                import shutil
                backup_discord = backup_dir / f"discord_bot_before_import_{timestamp}.db"
                shutil.copy2(discord_db, backup_discord)

            if clan_db.exists():
                import shutil
                backup_clan = backup_dir / f"clan_monitoring_before_import_{timestamp}.db"
                shutil.copy2(clan_db, backup_clan)

            # Extract and validate ZIP contents
            extracted_files = {}
            with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                # Check what files are in the ZIP
                namelist = zip_file.namelist()
                
                if 'discord_bot.db' in namelist:
                    extracted_files['discord_bot.db'] = zip_file.read('discord_bot.db')
                
                if 'clan_monitoring.db' in namelist:
                    extracted_files['clan_monitoring.db'] = zip_file.read('clan_monitoring.db')

            # Verify we got at least one database
            if not extracted_files:
                await interaction.followup.send(
                    "❌ ZIP file does not contain any recognized database files (discord_bot.db or clan_monitoring.db).",
                    ephemeral=True
                )
                return

            # Close any open connections to the databases
            try:
                conn = sqlite3.connect(str(discord_db))
                conn.close()
            except:
                pass

            try:
                conn = sqlite3.connect(str(clan_db))
                conn.close()
            except:
                pass

            # Replace databases with extracted files
            for filename, content in extracted_files.items():
                target_path = bot_dir / filename
                with open(target_path, 'wb') as f:
                    f.write(content)

            # Verify databases can be opened
            for filename in extracted_files.keys():
                target_path = bot_dir / filename
                try:
                    conn = sqlite3.connect(str(target_path))
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    conn.close()
                except Exception as e:
                    await interaction.followup.send(
                        f"❌ Imported {filename} is corrupt or invalid: {str(e)}",
                        ephemeral=True
                    )
                    return

            # Success message
            imported_list = ", ".join(extracted_files.keys())
            await interaction.followup.send(
                f"✅ Database import successful!\n\n**Imported files:**\n{imported_list}\n\n**Backup created:**\n(files stored in `backups/` directory)",
                ephemeral=True
            )

            await log_action(interaction, "Database Import", f"{interaction.user.mention} imported SQLite databases ({imported_list})")

        except zipfile.BadZipFile:
            await interaction.followup.send(
                "❌ The uploaded file is not a valid ZIP file.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to import databases: {str(e)}",
                ephemeral=True
            )
            await log_action(interaction, "Database Import Failed", f"{interaction.user.mention} failed to import databases: {str(e)}")


async def setup(bot):
    """Load utility commands"""
    await bot.add_cog(UtilityCommands(bot))
