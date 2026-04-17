"""Free Fire Guild Monitoring Commands - Integrated into main bot"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import math
import io
from datetime import datetime, timedelta
from helpers import log_action, is_commander, get_ist_now, get_ist_timestamp, get_banned_players, mark_banned_player_alert_sent
from member_guild_api import fetch_member_guild
import clan_monitor_task
from clan_monitoring import (
    add_monitored_player,
    remove_monitored_player,
    get_monitored_players,
    is_player_monitored,
    ignore_monitored_player,
    unignore_monitored_player,
    is_player_ignored,
    get_flagged_clans,
    log_flagged_movement,
    grant_permission,
    has_permission,
)
from channel_guild_monitoring import (
    get_channel_guild_id, get_channel_guild_name, get_channel_registered_by,
    register_channel_guild, unregister_channel_guild, monitor_channel_guild,
    get_channel_recent_changes, get_channel_members, get_channel_access_token,
    get_monitoring_interval, set_monitoring_interval,
    get_ban_monitoring_interval, set_ban_monitoring_interval,
    get_ban_monitoring_interval, set_ban_monitoring_interval,
    get_ban_monitoring_interval, set_ban_monitoring_interval,
    get_channel_player_monitoring_interval, set_channel_player_monitoring_interval,
    get_channel_last_player_check, set_channel_last_player_check,
    get_channel_last_snapshot_time,
    get_player_monitoring_enabled, set_player_monitoring_enabled,
    get_rival_detection_enabled, set_rival_detection_enabled,
    get_auto_monitor_duration, set_auto_monitor_duration,
    get_auto_monitor_speed, set_auto_monitor_speed,
    get_auto_monitoring_enabled, set_auto_monitoring_enabled,
)


class GrantPermissionModal(discord.ui.Modal, title="Grant Partnered Guild Permission"):
    uid = discord.ui.TextInput(
        label="Free Fire UID",
        placeholder="Enter the player's Free Fire UID",
        required=True,
        max_length=20,
    )

    remarks = discord.ui.TextInput(
        label="Remarks (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=4000,
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        uid_value = self.uid.value.strip()
        remarks_value = self.remarks.value.strip() if self.remarks.value else None

        try:
            uid = int(uid_value)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid UID. Please enter a numeric Free Fire UID.",
                ephemeral=True,
            )
            return

        success = grant_permission(uid, interaction.channel.id, interaction.user.id, remarks_value)
        if success:
            stopped_monitoring = False
            if is_player_monitored(uid, interaction.channel.id):
                stopped_monitoring = remove_monitored_player(uid, interaction.channel.id)

            embed = discord.Embed(
                title="✅ Partnered Guild Permission Granted",
                description=f"Permission granted for UID `{uid}` to join a partnered guild.",
                color=discord.Color.green(),
            )
            if remarks_value:
                embed.add_field(name="Remarks", value=remarks_value, inline=False)
            if stopped_monitoring:
                embed.add_field(name="Monitoring", value="Player monitoring stopped because permission was granted.", inline=False)
            embed.add_field(name="Granted by", value=interaction.user.mention, inline=False)
            embed.add_field(name="Channel", value=interaction.channel.mention, inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await log_action(
                interaction,
                "Grant Permission",
                f"Permission granted for UID {uid} by {interaction.user.mention} in {interaction.channel.mention}. Remarks: {remarks_value or 'None'}",
            )
        else:
            await interaction.response.send_message(
                f"❌ Permission for UID `{uid}` is already active in this channel.",
                ephemeral=True,
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"GrantPermissionModal error: {error}")
        try:
            await interaction.response.send_message(
                "❌ Something went wrong while granting permission.",
                ephemeral=True,
            )
        except Exception:
            pass


class GuildUpdatesView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=300)
        self.pages = pages
        self.page = 0
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.page > 0:
            prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary)
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
        if self.page < len(self.pages) - 1:
            next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
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

    async def update_message(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)


class LogsView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=300)
        self.pages = pages
        self.page = 0
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.page > 0:
            prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary)
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
        if self.page < len(self.pages) - 1:
            next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
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

    async def update_message(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)


class ActivityLogFilterSelect(discord.ui.View):
    """Filter selection view for activity logs with checkboxes"""
    def __init__(self, members, guild_name, guild_id, changes):
        super().__init__(timeout=300)
        self.members = members
        self.guild_name = guild_name
        self.guild_id = guild_id
        self.changes = changes or []
        self.selected_filters = set()  # Track selected filter types
        
        # Create checkbox buttons for each filter
        self.add_filter_button("all", "All Logs", "📋")
        self.add_filter_button("joined", "Joined", "✅")
        self.add_filter_button("left", "Left", "❌")
        self.add_filter_button("today", "Today", "📅")
        
        # Add apply button
        apply_button = discord.ui.Button(label="Apply Filters", style=discord.ButtonStyle.success)
        apply_button.callback = self.apply_filters
        self.add_item(apply_button)
    
    def add_filter_button(self, filter_type, label, emoji):
        """Add a checkbox-style filter button"""
        button = discord.ui.Button(
            label=f"☐ {label}",
            style=discord.ButtonStyle.secondary,
            custom_id=f"filter_{filter_type}"
        )
        
        async def toggle_filter(interaction: discord.Interaction, ft=filter_type, btn=button):
            # Toggle filter selection
            if ft in self.selected_filters:
                self.selected_filters.discard(ft)
                btn.label = f"☐ {label}"
            else:
                # Handle "all" special case - can't combine with others
                if ft == "all":
                    self.selected_filters.clear()
                    self.selected_filters.add(ft)
                    # Update all buttons
                    self.update_button_states(label, emoji)
                elif "all" in self.selected_filters:
                    self.selected_filters.discard("all")
                    self.selected_filters.add(ft)
                    # Update all buttons
                    self.update_button_states(label, emoji)
                else:
                    self.selected_filters.add(ft)
                
                btn.label = f"☑️ {label}"
            
            await interaction.response.defer()
            # Update message with new button states
            await interaction.edit_original_response(view=self)
        
        button.callback = toggle_filter
        self.add_item(button)
    
    def update_button_states(self, current_label, current_emoji):
        """Update all button states to reflect selections"""
        filter_map = {
            "all": ("All Logs", "📋"),
            "joined": ("Joined", "✅"),
            "left": ("Left", "❌"),
            "today": ("Today", "📅"),
        }
        
        for item in self.children[:-1]:  # Exclude apply button
            if hasattr(item, 'custom_id') and item.custom_id.startswith('filter_'):
                filter_type = item.custom_id.replace('filter_', '')
                label, emoji = filter_map.get(filter_type, (filter_type, ""))
                
                if filter_type in self.selected_filters:
                    item.label = f"☑️ {label}"
                    item.style = discord.ButtonStyle.primary
                else:
                    item.label = f"☐ {label}"
                    item.style = discord.ButtonStyle.secondary
    
    async def apply_filters(self, interaction: discord.Interaction):
        """Apply selected filters and show logs"""
        if not self.selected_filters:
            await interaction.response.send_message(
                "❌ Please select at least one filter.",
                ephemeral=True
            )
            return
        
        # If "all" is selected, show all logs (both joined and left)
        if "all" in self.selected_filters:
            filter_types = ["joined", "left"]
        else:
            filter_types = list(self.selected_filters)
        
        await self.show_logs_filtered(interaction, filter_types)
    
    async def show_logs_filtered(self, interaction: discord.Interaction, filter_types: list):
        """Show filtered activity logs"""
        filtered_changes = self.changes
        
        # Apply type filters (joined/left)
        type_filtered = []
        for change in self.changes:
            if change["change_type"] in filter_types or not filter_types:
                type_filtered.append(change)
        
        # Apply today filter if selected
        if "today" in self.selected_filters:
            today_start = get_ist_now().replace(hour=0, minute=0, second=0, microsecond=0)
            filtered_changes = []
            for change in type_filtered:
                try:
                    # Parse timestamp (already in IST format from get_ist_timestamp)
                    change_time = datetime.fromisoformat(change["timestamp"])
                    if change_time >= today_start:
                        filtered_changes.append(change)
                except:
                    pass
        else:
            filtered_changes = type_filtered
        
        if not filtered_changes:
            filter_label = "No entries found for selected filters"
            embed = discord.Embed(
                title="📋 Guild Activity Logs",
                description=f"Recent activity for **{self.guild_name}**",
                color=discord.Color.blue(),
                timestamp=get_ist_now()
            )
            embed.add_field(name="Activity", value=filter_label, inline=False)
            await interaction.response.send_message(embed=embed)
            return

        # Split logs into chunks of 10 per page
        chunk_size = 10
        log_chunks = [filtered_changes[i:i + chunk_size] for i in range(0, len(filtered_changes), chunk_size)]
        pages = []
        
        # Build filter description
        filter_list = []
        if "all" in self.selected_filters:
            filter_list.append("All Activity")
        else:
            if "joined" in self.selected_filters:
                filter_list.append("Joined")
            if "left" in self.selected_filters:
                filter_list.append("Left")
        if "today" in self.selected_filters:
            filter_list.append("Today")
        
        filter_title = f"Filters: {', '.join(filter_list)}"

        for page_index, chunk in enumerate(log_chunks):
            embed = discord.Embed(
                title=f"📋 Guild Activity Logs",
                description=f"Activity for **{self.guild_name}** (Page {page_index + 1}/{len(log_chunks)})\n{filter_title}",
                color=discord.Color.blue(),
                timestamp=get_ist_now()
            )

            log_lines = []
            for change in chunk:
                emoji = "✅" if change["change_type"] == "joined" else "❌"
                nickname = change["nickname"] or f"UID: {change['uid']}"
                uid = change["uid"]
                timestamp = change["timestamp"]
                log_lines.append(f"{emoji} {nickname} ({uid})\n   {timestamp}")

            log_text = "\n".join(log_lines)
            embed.add_field(
                name=f"Activities {page_index * chunk_size + 1}-{page_index * chunk_size + len(chunk)}",
                value=f"```\n{log_text}\n```",
                inline=False
            )
            embed.set_footer(text=f"Showing {len(filtered_changes)} of {len(self.changes)} total logs")
            pages.append(embed)

        if len(pages) > 1:
            view = LogsView(pages)
            await interaction.response.send_message(embed=pages[0], view=view)
        else:
            await interaction.response.send_message(embed=pages[0])


class GuildMembersView(discord.ui.View):
    def __init__(self, members, guild_name, guild_id, changes=None):
        super().__init__(timeout=300)
        self.members = members
        self.guild_name = guild_name
        self.guild_id = guild_id
        self.changes = changes or []

        members_button = discord.ui.Button(label="Members", style=discord.ButtonStyle.primary)
        members_button.callback = self.show_members
        self.add_item(members_button)

        logs_button = discord.ui.Button(label="Filter Logs", style=discord.ButtonStyle.secondary)
        logs_button.callback = self.show_filter_modal
        self.add_item(logs_button)

    async def show_members(self, interaction: discord.Interaction):
        member_lines = []
        for i, member in enumerate(self.members):
            uid = member.get("account_id") or member.get("uid", "Unknown")
            nickname = member.get("nickname", f"UID: {uid}")
            member_lines.append(f"{i+1:2d}. {nickname} ({uid})")

        embed = discord.Embed(
            title="👥 Guild Member List",
            description=f"Full member list for **{self.guild_name}**",
            color=discord.Color.blue(),
            timestamp=get_ist_now()
        )

        # Split members into chunks to stay under Discord's 1024 character limit per field
        chunk_size = 28  # About 28 members per field
        member_chunks = [member_lines[i:i + chunk_size] for i in range(0, len(member_lines), chunk_size)]

        for idx, chunk in enumerate(member_chunks):
            field_value = "```\n" + "\n".join(chunk) + "\n```"

            # Ensure field value doesn't exceed 1024 characters
            if len(field_value) > 1024:
                # Truncate if still too long
                truncated_chunk = chunk[:15]  # Show fewer members
                field_value = "```\n" + "\n".join(truncated_chunk) + f"\n... and {len(chunk) - 15} more\n```"

            embed.add_field(
                name="Members",
                value=field_value,
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    async def show_filter_modal(self, interaction: discord.Interaction):
        """Open the filter selection menu"""
        filter_view = ActivityLogFilterSelect(self.members, self.guild_name, self.guild_id, self.changes)
        await interaction.response.send_message(
            "📋 **Select which activity logs to view:**",
            view=filter_view,
            ephemeral=True
        )


def is_head_commander(interaction: discord.Interaction) -> bool:
    """Check if user has the Head Commander role"""
    if not isinstance(interaction.user, discord.Member):
        return False

    return any(role.name.lower() == "head commander" for role in interaction.user.roles)


class GuildMonitoringCog(commands.Cog):
    """Free Fire Guild Monitoring - One channel = one guild"""

    def __init__(self, bot):
        self.bot = bot
        self.monitoring_interval = get_monitoring_interval()  # Global guild monitoring interval
        self.monitoring_task = None
        self.start_monitoring_task()

    def cog_unload(self):
        if self.monitoring_task:
            self.monitoring_task.cancel()

    def start_monitoring_task(self):
        """Start the monitoring task with current interval"""
        if self.monitoring_task:
            self.monitoring_task.cancel()

        async def monitoring_loop():
            """Monitor all registered channels"""
            print(f"\n🔥 GUILD MONITORING CYCLE (every {self.monitoring_interval} minutes)")

            # Check banned players in partnered guilds first (once per cycle)
            await self.check_banned_players_in_partnered_clans()

            # Check each text channel for registered guilds
            channels_checked = 0
            channels_skipped = 0
            total_channels = sum(1 for g in self.bot.guilds for c in g.text_channels if get_channel_guild_id(c.id))
            
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    if not get_channel_guild_id(channel.id):
                        continue

                    try:
                        # Check if guild_monitoring service is enabled for this channel
                        from helpers import get_channel_services
                        services = get_channel_services(channel.id)
                        if not services.get("guild_monitoring", True):  # Default to True if not set
                            channels_skipped += 1
                            continue

                        # Guild monitoring
                        result = await asyncio.to_thread(monitor_channel_guild, channel.id)

                        if result["status"] == "success":
                            changes = result["changes"]
                            if changes["joined"] or changes["left"]:
                                await self.send_change_notifications(channel, changes)
                        else:
                            print(f"❌ Channel {channel.name}: {result['error']}")

                        # Player monitoring (channel-specific intervals)
                        await self.check_player_monitoring(channel)

                    except Exception as e:
                        print(f"⚠️  Error monitoring channel {channel.name}: {e}")
                        # Continue with next channel even if this one fails
                        continue
                    
                    channels_checked += 1
                    # Add delay between channel checks to avoid rate limiting
                    if channels_checked < total_channels:
                        await asyncio.sleep(3)  # 3 second delay between API calls

            print(f"✅ Monitoring cycle complete ({channels_checked} checked, {channels_skipped} skipped)\n")

        self.monitoring_task = tasks.loop(minutes=self.monitoring_interval)(monitoring_loop)
        self.monitoring_task.before_loop(self.before_monitoring_task)
        self.monitoring_task.start()

    async def before_monitoring_task(self):
        await self.bot.wait_until_ready()

    def get_channel_guild_id(self, channel_id):
        """Get the Free Fire guild ID registered for a channel"""
        return get_channel_guild_id(channel_id)

    async def send_change_notifications(self, channel, changes):
        """Send notifications about membership changes"""
        embed = discord.Embed(
            title="👥 Guild Membership Changes",
            color=discord.Color.blue(),
            timestamp=get_ist_now()
        )

        if changes["joined"]:
            joined_items = list(changes["joined"])
            joined_list = []
            for uid in joined_items[:50]:  # Limit to 50 per message
                member_data = self.get_member_info(uid)
                display_name = self.format_member_display_name(uid, member_data)
                if display_name == f"UID: {uid}":
                    joined_list.append(f"✅ {display_name}")
                else:
                    joined_list.append(f"✅ {display_name} (UID: {uid})")

            embed.add_field(
                name=f"Joined ({len(joined_items)})",
                value="\n".join(joined_list),
                inline=False
            )

        if changes["left"]:
            left_items = list(changes["left"])
            left_list = []
            for uid in left_items[:5]:  # Limit to 5 per message
                member_data = self.get_member_info(uid)
                display_name = self.format_member_display_name(uid, member_data)
                if display_name == f"UID: {uid}":
                    left_list.append(f"❌ {display_name}")
                else:
                    left_list.append(f"❌ {display_name} (UID: {uid})")

            embed.add_field(
                name=f"Left ({len(left_items)})",
                value="\n".join(left_list),
                inline=False
            )

        if len(changes["joined"]) > 50 or len(changes["left"]) > 50:
            embed.set_footer(text="... and more changes")

        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send notification to {channel.name}: {e}")
        
        # Automatically monitor players who left the guild
        try:
            if changes["left"] and get_auto_monitoring_enabled(channel.id):
                auto_added = 0
                # Get the auto-monitoring duration for this channel (in days)
                duration_days = get_auto_monitor_duration(channel.id)
                duration_hours = duration_days * 24  # Convert days to hours
                
                for uid in changes["left"]:
                    # Check if already being monitored
                    if not is_player_monitored(uid, channel.id):
                        # Get player nickname for context
                        member_data = self.get_member_info(uid)
                        nickname = member_data.get("nickname") if member_data else None
                        
                        # Add to monitored list with the configured duration
                        add_monitored_player(uid, nickname or "Unknown", duration_hours, 0, channel.id)
                        auto_added += 1
                
                if auto_added > 0:
                    print(f"👁️ Auto-monitored {auto_added} player(s) who left {channel.name} for {duration_days} days")
                    # Send a follow-up about auto-monitoring
                    monitor_embed = discord.Embed(
                        title="👁️ Auto-Monitoring Activated",
                        description=f"{auto_added} player(s) who left the guild are now being monitored for **{duration_days} days** for guild movements.",
                        color=discord.Color.purple(),
                        timestamp=get_ist_now()
                    )
                    try:
                        await channel.send(embed=monitor_embed)
                    except Exception as e:
                        print(f"Failed to send auto-monitoring notification: {e}")
        except Exception as e:
            print(f"Error auto-monitoring players who left: {e}")

    def get_member_info(self, uid):
        """Get cached member info"""
        try:
            import sqlite3
            conn = sqlite3.connect("discord_bot.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data FROM member_cache WHERE uid = ? ORDER BY cached_at DESC LIMIT 1",
                (uid,)
            )
            result = cursor.fetchone()
            conn.close()
            return json.loads(result[0]) if result else None
        except:
            return None

    def format_member_display_name(self, uid, member_data):
        """Return a cleaned display name and avoid duplicate UID output."""
        if member_data:
            nickname = member_data.get("nickname")
            if nickname:
                normalized = nickname.strip()
                if normalized and normalized not in (f"UID:{uid}", f"UID: {uid}"):
                    return normalized
        return f"UID: {uid}"

    async def check_banned_players_in_partnered_clans(self):
        """Check active banned players and alert if they join a partnered guild."""
        try:
            from clan_monitoring import get_flagged_clans
            from member_clan_api import get_player_clan_info, fetch_player_info
            
            banned_players = get_banned_players()
            if not banned_players:
                return

            flagged_clans = get_flagged_clans()
            if not flagged_clans:
                return

            alerts_sent = 0
            for ban in banned_players:
                if ban.get("alert_sent"):
                    continue

                uid_str = str(ban.get("uid", ""))
                channel_id_str = str(ban.get("channel_id", ""))
                nickname = ban.get("nickname") or "Unknown"
                reason = ban.get("reason") or "No reason provided"
                banned_by = ban.get("banned_by") or "Unknown"

                try:
                    uid = int(uid_str)
                except (TypeError, ValueError):
                    print(f"Invalid banned UID: {uid_str}")
                    continue

                current_clan = await asyncio.to_thread(get_player_clan_info, uid)
                if not current_clan or not current_clan.get("clanId"):
                    continue

                try:
                    clan_id = int(current_clan["clanId"])
                except (TypeError, ValueError):
                    print(f"Invalid clan ID for UID {uid}: {current_clan.get('clanId')}")
                    continue

                if clan_id not in flagged_clans:
                    continue

                clan_name = current_clan.get("clanName") or f"Guild {clan_id}"
                if nickname in ("Unknown", "unknown", "", None):
                    try:
                        player_info = await asyncio.to_thread(fetch_player_info, uid)
                        if player_info and "basicInfo" in player_info:
                            api_name = player_info["basicInfo"].get("nickname")
                            if api_name:
                                nickname = api_name
                    except Exception as e:
                        print(f"Could not fetch nickname for UID {uid}: {e}")

                channel = None
                try:
                    channel = self.bot.get_channel(int(channel_id_str))
                except (TypeError, ValueError):
                    channel = None

                embed = discord.Embed(
                    title="🚨 BANNED PLAYER PARTNERED ALERT",
                    description="A banned player has joined a partnered guild.",
                    color=discord.Color.red(),
                    timestamp=get_ist_now()
                )
                embed.add_field(name="Player", value=f"{nickname} (UID: {uid})", inline=False)
                embed.add_field(name="Partnered Guild", value=f"{clan_name} (ID: {clan_id})", inline=False)
                embed.add_field(name="Ban Reason", value=reason, inline=False)
                embed.add_field(name="Banned By", value=banned_by, inline=False)
                embed.set_footer(text="This alert is sent to the channel where the player was banned.")

                sent_ok = False
                if channel:
                    try:
                        await channel.send(content="@here 🚨 **Banned player joined a partnered guild!**", embed=embed)
                        sent_ok = True
                        print(f"✅ Sent banned player alert for UID {uid} to channel {channel.id}")
                        alerts_sent += 1
                    except Exception as e:
                        print(f"❌ Failed to send banned player alert to channel {channel_id_str}: {e}")
                else:
                    print(f"❌ Could not resolve channel {channel_id_str} for banned UID {uid}")

                if sent_ok:
                    mark_banned_player_alert_sent(uid, channel_id_str, clan_id, clan_name)
                else:
                    print(f"Did not mark alert sent for banned UID {uid} since the message was not delivered")
            
            if alerts_sent > 0:
                print(f"🚨 Banned player monitoring: {alerts_sent} alert(s) sent\n")
                
        except Exception as e:
            print(f"Error in banned player monitoring: {e}")
            import traceback
            traceback.print_exc()

    async def check_player_monitoring(self, channel):
        """Check if player monitoring should run for this channel and execute if needed"""
        try:
            channel_id = channel.id
            
            # Check if player monitoring is enabled for this channel
            if not get_player_monitoring_enabled(channel_id):
                print(f"  ⏸️ Player monitoring disabled for {channel.name}")
                return
            
            player_interval = get_channel_player_monitoring_interval(channel_id)
            
            # Skip if no monitored players for this channel
            monitored_players = get_monitored_players(channel_id)
            if not monitored_players:
                return
            
            # Check if it's time to run player monitoring
            last_check = get_channel_last_player_check(channel_id)
            if last_check:
                from datetime import datetime, timedelta
                last_check_time = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                next_check_time = last_check_time + timedelta(minutes=player_interval)
                current_time = get_ist_now()
                
                print(f"  ⏱️ Player monitoring timing: Last={last_check_time.isoformat()}, Next={next_check_time.isoformat()}, Now={current_time.isoformat()}, Interval={player_interval}min")
                
                if current_time < next_check_time:
                    print(f"  ⏭️ Not time yet for player monitoring (need to wait {(next_check_time - current_time).total_seconds() / 60:.1f} more minutes)")
                    return  # Not time yet
            else:
                print(f"  📅 First player monitoring run for {channel.name}")
            
            print(f"👁️ Running player monitoring for channel {channel.name} (interval: {player_interval} minutes)")
            
            # Perform player monitoring - check each monitored player's current status
            await self.monitor_channel_players(channel)
            
            # Update last check time
            set_channel_last_player_check(channel_id)
            
        except Exception as e:
            print(f"Error checking player monitoring for channel {channel.name}: {e}")
            import traceback
            traceback.print_exc()

    async def send_alert_safe(self, channel, embed=None, message_text=None):
        """Send an alert to a channel with permission checking and fallback"""
        try:
            # Check if bot has permissions in this channel
            bot_member = channel.guild.me
            if not bot_member:
                print(f"      ⚠️ Bot is not a member of the guild")
                return False
            
            permissions = channel.permissions_for(bot_member)
            
            # Check required permissions
            if not permissions.view_channel:
                print(f"      ❌ Bot cannot view channel {channel.name} - Missing VIEW_CHANNEL permission")
                return False
            
            if not permissions.send_messages:
                print(f"      ❌ Bot cannot send messages in {channel.name} - Missing SEND_MESSAGES permission")
                return False
            
            # Try to send embed first
            if embed and permissions.embed_links:
                try:
                    await channel.send(embed=embed)
                    return True
                except discord.Forbidden:
                    print(f"      ⚠️ Embed permission denied, trying plain text fallback")
                except Exception as e:
                    print(f"      ⚠️ Failed to send embed: {e}")
            
            # Fallback to plain text message
            if message_text:
                try:
                    await channel.send(message_text)
                    return True
                except discord.Forbidden:
                    print(f"      ❌ Bot cannot send messages - Missing SEND_MESSAGES permission")
                    return False
                except Exception as e:
                    print(f"      ❌ Failed to send message: {e}")
                    return False
            
            return False
            
        except Exception as e:
            print(f"      ❌ Permission check error: {e}")
            return False

    async def monitor_channel_players(self, channel):
        """Monitor players for a specific channel"""
        try:
            channel_id = channel.id
            monitored_players = get_monitored_players(channel_id)
            
            if not monitored_players:
                print(f"  👁️ No monitored players for {channel.name}")
                return
            
            print(f"  👁️ Checking {len(monitored_players)} monitored player(s) in {channel.name}")
            
            from member_clan_api import get_player_clan_info
            flagged_clans = get_flagged_clans()
            
            print(f"  📋 Partnered guilds: {flagged_clans}")
            
            registered_guild_id = get_channel_guild_id(channel_id)
            try:
                registered_guild_id = int(registered_guild_id) if registered_guild_id is not None else None
            except (TypeError, ValueError):
                registered_guild_id = None

            print(f"  🏢 Registered guild ID: {registered_guild_id}")
            
            alerts_sent = 0
            for player in monitored_players:
                ff_uid = player['ff_uid']
                nickname = player['nickname']
                
                print(f"    👤 Checking player: {nickname} (UID: {ff_uid})")
                
# Get current guild info
                current_guild = await asyncio.to_thread(get_player_clan_info, ff_uid)

                if current_guild:
                    guild_id = current_guild.get('clanId')
                    guild_name = current_guild.get('clanName', f'Guild {guild_id}')

                    # Ensure guild_id is an integer for comparison
                    try:
                        guild_id = int(guild_id)
                    except (TypeError, ValueError):
                        print(f"    ⚠️ Invalid guild ID for {nickname}: {guild_id}")
                        continue

                    print(f"      Current Guild: {guild_name} (ID: {guild_id})")

                    # Check if this is different from the registered guild
                    if guild_id != registered_guild_id:
                        # Check if this is a partnered guild
                        is_rival_guild = guild_id in flagged_clans

                        print(f"      Different guild detected. Is partnered: {is_rival_guild}")

                        if is_rival_guild:
                            # Check if partnered detection is enabled for this channel
                            if not get_rival_detection_enabled(channel_id):
                                print(f"      ⏸️ Partnered detection disabled for {channel.name}, skipping alert")
                            else:
                                # Player is in a PARTNERED GUILD - send high-priority alert
                                embed = discord.Embed(
                                    title="🚨 PARTNERED GUILD ALERT - MONITORED PLAYER",
                                    description=f"Monitored player has joined a **PARTNERED GUILD**!",
                                    color=discord.Color.red(),
                                    timestamp=get_ist_now()
                                )
                                embed.add_field(name="Player", value=f"{nickname} (UID: {ff_uid})", inline=True)
                                embed.add_field(name="🚨 PARTNERED GUILD", value=f"{guild_name} (ID: {guild_id})", inline=True)
                                embed.add_field(name="Channel", value=channel.mention, inline=True)
                                embed.set_footer(text="⚠️ This player is now in a partnered guild!")
                                
                                # Fallback plain text
                                message_text = f"🚨 **PARTNERED GUILD ALERT - MONITORED PLAYER**\n👤 {nickname} (UID: {ff_uid})\n🏢 {guild_name} (ID: {guild_id})"
                                
                                # Log the partnered movement
                                log_flagged_movement(
                                    ff_uid=ff_uid,
                                    nickname=nickname,
                                    from_clan_id=registered_guild_id,
                                    to_clan_id=guild_id,
                                    to_clan_name=guild_name,
                                    detected_at=get_ist_timestamp()
                                )
                                
                                if await self.send_alert_safe(channel, embed, message_text):
                                    alerts_sent += 1
                                    print(f"      ✅ PARTNERED GUILD ALERT sent for {nickname}")
                                else:
                                    print(f"      ❌ Failed to send partnered guild alert")
                        else:
                            # Player is in a different guild but NOT a partnered guild - no alert needed
                            print(f"      ℹ️ Player in non-partnered guild, skipping alert")
                    else:
                        print(f"      Same as registered guild, no alert needed")
                else:
                    # Player not in any guild - no alert needed
                    print(f"    ℹ️ Player {nickname} is not in any guild, skipping alert")
            
            if alerts_sent > 0:
                print(f"  ✅ Sent {alerts_sent} player monitoring alerts to {channel.name}")
                
        except Exception as e:
            print(f"Error monitoring players for channel {channel.name}: {e}")
            import traceback
            traceback.print_exc()

    @app_commands.command(name="register_guild", description="Register a Free Fire guild for this channel (Commanders only)")
    @app_commands.describe(
        access_token="Access token for your guild's API",
        channel_id="Discord channel ID to register the guild in",
        guild_name="Name of your Free Fire guild"
    )
    async def register_guild(self, interaction: discord.Interaction, access_token: str, channel_id: str, guild_name: str):
        """Register a Free Fire guild for monitoring with access token, channel ID, and guild name"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            # Interaction expired, try to respond immediately instead
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_head_commander(interaction):
            await interaction.followup.send("❌ Only Head Commanders or higher roles can register guilds.", ephemeral=True)
            return

        # Validate channel ID
        try:
            channel_id_int = int(channel_id)
        except ValueError:
            await interaction.followup.send("❌ Invalid channel ID. Must be a number.", ephemeral=True)
            return

        # Get the channel from the guild
        try:
            channel = interaction.guild.get_channel(channel_id_int)
            if not channel:
                await interaction.followup.send(f"❌ Channel with ID `{channel_id}` not found in this server.", ephemeral=True)
                return
        except Exception as e:
            await interaction.followup.send(f"❌ Error accessing channel: {str(e)}", ephemeral=True)
            return

        # Reject duplicate registration for the same channel
        if get_channel_guild_id(channel_id_int):
            await interaction.followup.send(
                "❌ A guild is already registered to this channel. Remove the existing registration first or choose another channel.",
                ephemeral=True
            )
            return

        # Validate access token format (should be a long string)
        if len(access_token) < 50:
            await interaction.followup.send("❌ Invalid access token format. Token should be at least 50 characters.", ephemeral=True)
            return

        # Validate guild name
        if len(guild_name) < 2 or len(guild_name) > 100:
            await interaction.followup.send("❌ Guild name must be between 2 and 100 characters.", ephemeral=True)
            return

        # Test the access token and extract guild ID from API response
        try:
            api_response = fetch_member_guild(access_token, timeout=10)
            if "members" not in api_response or "clan_id" not in api_response:
                await interaction.followup.send("❌ Failed to verify guild access. Check your access token.", ephemeral=True)
                return
            
            guild_id = str(api_response["clan_id"])
            member_count = len(api_response.get("members", []))

        except Exception as e:
            await interaction.followup.send(f"❌ API test failed: {str(e)}", ephemeral=True)
            return

        # Register the guild for the specified channel with its access token
        try:
            success = register_channel_guild(channel_id_int, guild_id, access_token, interaction.user.id, guild_name)
            if not success:
                await interaction.followup.send("❌ Failed to register guild.", ephemeral=True)
                return

            embed = discord.Embed(
                title="✅ Guild Registered",
                description=f"Guild **{guild_name}** will be monitored in {channel.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            embed.add_field(name="Guild Name", value=guild_name, inline=True)
            embed.add_field(name="Current Members", value=str(member_count), inline=True)
            embed.add_field(name="Registered by", value=interaction.user.mention, inline=True)
            embed.set_footer(text="Guild monitoring will start in the next monitoring cycle (max 10 minutes)")

            await interaction.followup.send(embed=embed)

            # Log the action
            await log_action(
                interaction,
                "Guild Registered",
                f"Channel {channel.mention} registered to monitor guild {guild_id} ({guild_name})"
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Registration failed: {e}", ephemeral=True)

    @app_commands.command(name="remove_guild", description="Remove the registered guild for this channel or a specified channel (Commanders only)")
    @app_commands.describe(
        channel_id="Discord channel ID to unregister the guild from (defaults to current channel)"
    )
    async def remove_guild(self, interaction: discord.Interaction, channel_id: str = None):
        """Remove the registered guild for a channel"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_head_commander(interaction):
            await interaction.followup.send("❌ Only Head Commanders or higher roles can remove guild registrations.", ephemeral=True)
            return

        if channel_id:
            try:
                channel_id_int = int(channel_id)
            except ValueError:
                await interaction.followup.send("❌ Invalid channel ID. Must be a number.", ephemeral=True)
                return
        else:
            channel_id_int = interaction.channel.id

        try:
            channel = interaction.guild.get_channel(channel_id_int)
            if not channel:
                await interaction.followup.send(f"❌ Channel with ID `{channel_id_int}` not found in this server.", ephemeral=True)
                return
        except Exception as e:
            await interaction.followup.send(f"❌ Error accessing channel: {str(e)}", ephemeral=True)
            return

        if not get_channel_guild_id(channel_id_int):
            await interaction.followup.send("❌ No guild registered for this channel.", ephemeral=True)
            return

        if not unregister_channel_guild(channel_id_int):
            await interaction.followup.send("❌ Failed to remove guild registration.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🗑️ Guild Registration Removed",
            description=f"Guild monitoring has been removed for {channel.mention}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Removed by", value=interaction.user.mention, inline=True)

        await interaction.followup.send(embed=embed)
        await log_action(
            interaction,
            "Guild Registration Removed",
            f"Channel {channel.mention} unregistered from guild monitoring"
        )

    @app_commands.command(name="set_monitoring_speed", description="Set the global guild monitoring speed")
    @app_commands.describe(minutes="New global guild monitoring interval in minutes (1-600)")
    async def set_monitoring_speed(self, interaction: discord.Interaction, minutes: int):
        """Set the global guild monitoring speed."""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_head_commander(interaction):
            await interaction.followup.send("❌ Only Head Commanders can set monitoring speed.", ephemeral=True)
            return

        if minutes < 1 or minutes > 600:
            await interaction.followup.send("❌ Monitoring speed must be between 1 and 600 minutes.", ephemeral=True)
            return

        old_interval = self.monitoring_interval
        self.monitoring_interval = minutes

        if not set_monitoring_interval(minutes):
            await interaction.followup.send("❌ Failed to update global monitoring speed.", ephemeral=True)
            return

        self.start_monitoring_task()

        embed = discord.Embed(
            title="⚙️ Global Monitoring Speed Updated",
            description=f"Global guild monitoring interval changed from {old_interval} to {minutes} minutes.",
            color=discord.Color.blue()
        )
        embed.add_field(name="New Interval", value=f"{minutes} minutes", inline=True)

        await interaction.followup.send(embed=embed)
        await log_action(
            interaction,
            "Global Monitoring Speed Updated",
            f"Global guild monitoring interval changed from {old_interval} to {minutes} minutes"
        )

    @app_commands.command(name="set_ban_monitoring_speed", description="Set the ban monitoring speed for banned player alerts")
    @app_commands.describe(minutes="New ban monitoring interval in minutes (1-600)")
    async def set_ban_monitoring_speed(self, interaction: discord.Interaction, minutes: int):
        """Set how frequently banned players are checked for partnered guild joins."""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_head_commander(interaction):
            await interaction.followup.send("❌ Only Head Commanders can set ban monitoring speed.", ephemeral=True)
            return

        if minutes < 1 or minutes > 600:
            await interaction.followup.send("❌ Ban monitoring speed must be between 1 and 600 minutes.", ephemeral=True)
            return

        old_interval = get_ban_monitoring_interval()
        if not set_ban_monitoring_interval(minutes):
            await interaction.followup.send("❌ Failed to update ban monitoring speed.", ephemeral=True)
            return

        if getattr(clan_monitor_task, 'clan_monitor', None):
            try:
                clan_monitor_task.clan_monitor.update_interval(minutes)
            except Exception as e:
                print(f"Error updating ban monitoring interval runtime: {e}")

        embed = discord.Embed(
            title="⚙️ Ban Monitoring Speed Updated",
            description=f"Ban monitoring interval changed from {old_interval} to {minutes} minutes.",
            color=discord.Color.blue()
        )
        embed.add_field(name="New Interval", value=f"{minutes} minutes", inline=True)

        await interaction.followup.send(embed=embed)
        await log_action(
            interaction,
            "Ban Monitoring Speed Updated",
            f"Ban monitoring interval changed from {old_interval} to {minutes} minutes"
        )

    @app_commands.command(name="set_player_monitoring_speed", description="Set the player monitoring speed for this channel")
    @app_commands.describe(minutes="New player monitoring interval in minutes (1-600)")
    async def set_player_monitoring_speed(self, interaction: discord.Interaction, minutes: int):
        """Set the player monitoring speed for the current channel."""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_head_commander(interaction):
            await interaction.followup.send("❌ Only Head Commanders can set player monitoring speed.", ephemeral=True)
            return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild is registered for this channel. Register a guild first.", ephemeral=True)
            return

        if minutes < 1 or minutes > 600:
            await interaction.followup.send("❌ Player monitoring speed must be between 1 and 600 minutes.", ephemeral=True)
            return

        current_interval = get_channel_player_monitoring_interval(interaction.channel.id)
        if not set_channel_player_monitoring_interval(interaction.channel.id, minutes):
            await interaction.followup.send("❌ Failed to update player monitoring speed.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⚙️ Player Monitoring Speed Updated",
            description=f"Player monitoring interval for this channel changed from {current_interval} to {minutes} minutes.",
            color=discord.Color.blue()
        )
        embed.add_field(name="New Interval", value=f"{minutes} minutes", inline=True)
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)

        embed.add_field(name="Changed by", value=interaction.user.mention, inline=True)

        await interaction.followup.send(embed=embed)
        await log_action(
            interaction,
            "Player Monitoring Speed Updated",
            f"Channel {interaction.channel.mention} player monitoring interval updated from {current_interval} to {minutes} minutes"
        )

    @app_commands.command(name="set_auto_monitor_duration", description="Set auto-monitoring duration when players leave the guild")
    @app_commands.describe(days="Auto-monitoring duration in days (1-365, default: 30)")
    async def set_auto_monitor_duration(self, interaction: discord.Interaction, days: int = 30):
        """Set how long to automatically monitor players who leave the guild."""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_head_commander(interaction):
            await interaction.followup.send("❌ Only Head Commanders can set auto-monitoring duration.", ephemeral=True)
            return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild is registered for this channel. Register a guild first.", ephemeral=True)
            return

        if days < 1 or days > 365:
            await interaction.followup.send("❌ Auto-monitoring duration must be between 1 and 365 days.", ephemeral=True)
            return

        current_duration = get_auto_monitor_duration(interaction.channel.id)
        if not set_auto_monitor_duration(interaction.channel.id, days):
            await interaction.followup.send("❌ Failed to update auto-monitoring duration.", ephemeral=True)
            return

        # Convert to readable format
        if days == 1:
            duration_text = "1 day"
        elif days == 7:
            duration_text = "1 week"
        elif days == 30:
            duration_text = "1 month"
        else:
            duration_text = f"{days} days"

        embed = discord.Embed(
            title="⏱️ Auto-Monitoring Duration Updated",
            description=f"Auto-monitoring duration for players who leave the guild changed from {current_duration} to {days} days.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Previous Duration", value=f"{current_duration} days", inline=True)
        embed.add_field(name="New Duration", value=duration_text, inline=True)
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Changed by", value=interaction.user.mention, inline=True)
        embed.set_footer(text="Players leaving the guild will be monitored for this duration")

        await interaction.followup.send(embed=embed)
        await log_action(
            interaction,
            "Auto-Monitoring Duration Updated",
            f"Channel {interaction.channel.mention} auto-monitoring duration updated from {current_duration} to {days} days"
        )

    @app_commands.command(name="set_auto_monitor_speed", description="Set how fast to check monitored players who left the guild")
    @app_commands.describe(minutes="Check interval in minutes (1-600, default: 2)")
    async def set_auto_monitor_speed(self, interaction: discord.Interaction, minutes: int = 2):
        """Set the monitoring check speed for automatically monitored players."""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_head_commander(interaction):
            await interaction.followup.send("❌ Only Head Commanders can set auto-monitoring speed.", ephemeral=True)
            return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild is registered for this channel. Register a guild first.", ephemeral=True)
            return

        if minutes < 1 or minutes > 600:
            await interaction.followup.send("❌ Auto-monitoring speed must be between 1 and 600 minutes.", ephemeral=True)
            return

        current_speed = get_auto_monitor_speed(interaction.channel.id)
        if not set_auto_monitor_speed(interaction.channel.id, minutes):
            await interaction.followup.send("❌ Failed to update auto-monitoring speed.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⚙️ Auto-Monitoring Speed Updated",
            description=f"Auto-monitoring check interval changed from {current_speed} to {minutes} minutes.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Previous Speed", value=f"Every {current_speed} minutes", inline=True)
        embed.add_field(name="New Speed", value=f"Every {minutes} minutes", inline=True)
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Changed by", value=interaction.user.mention, inline=True)
        embed.set_footer(text="This applies to automatically monitored players who left the guild")

        await interaction.followup.send(embed=embed)
        await log_action(
            interaction,
            "Auto-Monitoring Speed Updated",
            f"Channel {interaction.channel.mention} auto-monitoring speed updated from {current_speed} to {minutes} minutes"
        )

    # DEPRECATED: Auto-monitoring toggle is now integrated into /viewservices command
    # Use /viewservices to toggle auto-monitoring service instead
    #
    # @app_commands.command(name="toggle_auto_monitoring", description="Toggle auto-monitoring service on/off")
    # async def toggle_auto_monitoring(self, interaction: discord.Interaction):
    #     """Toggle auto-monitoring service for this channel."""
    #     try:
    #         await interaction.response.defer()
    #     except (discord.errors.NotFound, discord.errors.HTTPException):
    #         try:
    #             await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
    #         except:
    #             return
    #
    #     if not is_head_commander(interaction):
    #         await interaction.followup.send("❌ Only Head Commanders can toggle auto-monitoring.", ephemeral=True)
    #         return
    #
    #     guild_id = self.get_channel_guild_id(interaction.channel.id)
    #     if not guild_id:
    #         await interaction.followup.send("❌ No guild is registered for this channel. Register a guild first.", ephemeral=True)
    #         return
    #
    #     current_status = get_auto_monitoring_enabled(interaction.channel.id)
    #     new_status = not current_status
    #
    #     if not set_auto_monitoring_enabled(interaction.channel.id, new_status):
    #         await interaction.followup.send("❌ Failed to toggle auto-monitoring service.", ephemeral=True)
    #         return
    #
    #     status_text = "✅ ENABLED" if new_status else "❌ DISABLED"
    #     
    #     embed = discord.Embed(
    #         title="🎛️ Auto-Monitoring Service Toggled",
    #         description=f"Auto-monitoring service is now {status_text}",
    #         color=discord.Color.green() if new_status else discord.Color.red()
    #     )
    #     embed.add_field(name="Service", value="Auto-Monitoring", inline=True)
    #     embed.add_field(name="Status", value=status_text, inline=True)
    #     embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
    #     embed.add_field(name="Toggled by", value=interaction.user.mention, inline=True)
    #     embed.set_footer(text="This service auto-monitors players who leave the guild" if new_status else "Players who leave the guild will not be auto-monitored")
    #
    #     await interaction.followup.send(embed=embed)
    #     await log_action(
    #         interaction,
    #         "Auto-Monitoring Service Toggled",
    #         f"Auto-monitoring service {status_text} for {interaction.channel.mention}"
    #     )

    @app_commands.command(name="monitor_player", description="Monitor a player by UID for a limited time")
    @app_commands.describe(
        uid="Free Fire UID of the player to monitor",
        duration_hours="Monitoring duration in hours (1-4380)"
    )
    async def monitor_player(self, interaction: discord.Interaction, uid: int, duration_hours: int):
        """Monitor a player with a time limit."""
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_commander(interaction):
            await interaction.followup.send("❌ Only Commanders or Administrators can monitor players.", ephemeral=True)
            return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild is registered for this channel. Register a guild first.", ephemeral=True)
            return

        if duration_hours < 1 or duration_hours > 4380:
            await interaction.followup.send("❌ Duration must be between 1 and 4380 hours.", ephemeral=True)
            return

        if is_player_monitored(uid, interaction.channel.id):
            await interaction.followup.send(f"❌ Player UID `{uid}` is already being monitored for this guild.", ephemeral=True)
            return

        nickname = None
        try:
            from member_clan_api import fetch_player_info
            player_info = fetch_player_info(uid)
            if player_info and "basicInfo" in player_info:
                nickname = player_info["basicInfo"].get("nickname")
        except:
            pass

        success = add_monitored_player(uid, nickname, duration_hours, interaction.user.id, interaction.channel.id)

        if success:
            embed = discord.Embed(
                title="👁️ Player Added to Monitoring",
                color=discord.Color.orange(),
            )
            embed.add_field(name="Player", value=f"{nickname or 'Unknown'} (UID: `{uid}`)", inline=False)
            embed.add_field(name="Duration", value=f"{duration_hours} hours", inline=True)
            embed.add_field(name="Added by", value=interaction.user.mention, inline=True)
            embed.set_footer(text="Player activity will be monitored and alerted")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to add player to monitoring.", ephemeral=True)

    @app_commands.command(name="grant_permission", description="Open a permission grant modal for adding a partnered-guild join UID")
    async def grant_permission(self, interaction: discord.Interaction):
        """Open a modal to grant permission for a player to join a partnered guild."""
        if not is_commander(interaction):
            await interaction.response.send_message("❌ Only Commanders or Administrators can grant partnered guild permission.", ephemeral=True)
            return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.response.send_message("❌ No guild is registered for this channel. Register a guild first.", ephemeral=True)
            return

        modal = GrantPermissionModal(self)
        await interaction.response.send_modal(modal)

    async def _remove_monitored_player(self, interaction: discord.Interaction, uid: int):
        """Helper method to remove a monitored player."""
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_commander(interaction):
            await interaction.followup.send("❌ Only Commanders or Administrators can stop player monitoring.", ephemeral=True)
            return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild is registered for this channel. Register a guild first.", ephemeral=True)
            return

        if not is_player_monitored(uid, interaction.channel.id):
            await interaction.followup.send(f"❌ Player UID `{uid}` is not currently being monitored for this guild.", ephemeral=True)
            return

        success = remove_monitored_player(uid, interaction.channel.id)
        if success:
            embed = discord.Embed(
                title="❌ Player Removed from Monitoring",
                description=f"Player UID `{uid}` is no longer being monitored.",
                color=discord.Color.greyple(),
            )
            embed.set_footer(text="Monitoring stopped")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to remove player from monitoring.", ephemeral=True)

    @app_commands.command(name="remove_monitored", description="Remove a monitored player by UID")
    @app_commands.describe(uid="Free Fire UID of the monitored player to remove")
    async def remove_monitored(self, interaction: discord.Interaction, uid: int):
        """Remove a monitored player by UID."""
        await self._remove_monitored_player(interaction, uid)

    @app_commands.command(name="auto_monitor_list", description="List players auto-monitored for leaving the guild")
    async def auto_monitor_list(self, interaction: discord.Interaction):
        """List all auto-monitored players (those who left the guild)."""
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_commander(interaction):
            await interaction.followup.send("❌ Only Commanders or Administrators can view auto-monitored players.", ephemeral=True)
            return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild is registered for this channel. Register a guild first.", ephemeral=True)
            return

        monitored_players = get_monitored_players(interaction.channel.id)
        
        # Filter only auto-monitored players (added_by = 0)
        auto_monitored = [p for p in monitored_players if p.get('added_by') == 0]
        
        embed = discord.Embed(
            title="👁️ Auto-Monitored Players (Left Guild)",
            description=f"Players automatically monitored after leaving guild {guild_id}",
            color=discord.Color.purple(),
        )

        if auto_monitored:
            auto_text = ""
            for player in auto_monitored:
                nickname = player["nickname"] or "Unknown"
                auto_text += (
                    f"**{nickname}** (UID: `{player['ff_uid']}`)"
                    f" • Monitoring: {player['monitoring_end'] if player['monitoring_end'] != 'Indefinite' else '∞'}"
                    f" • Added: {player['monitoring_start'][:10] if player['monitoring_start'] else 'Unknown'}\n"
                )
            if len(auto_text) > 2048:
                auto_text = auto_text[:2048] + "..."
            embed.add_field(name=f"🟣 Auto-Monitored: {len(auto_monitored)}", value=auto_text, inline=False)
        else:
            embed.add_field(name="No Players", value="No players are auto-monitored (no recent departures).", inline=False)

        embed.set_footer(text="Auto-monitored players are tracked after leaving the guild")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="list_monitored", description="List all currently monitored players")
    async def list_monitored(self, interaction: discord.Interaction):
        """List all active monitored players."""
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_commander(interaction):
            await interaction.followup.send("❌ Only Commanders or Administrators can view monitored players.", ephemeral=True)
            return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild is registered for this channel. Register a guild first.", ephemeral=True)
            return

        monitored_players = get_monitored_players(interaction.channel.id)
        
        # Separate active and ignored players
        active_players = []
        ignored_players = []
        
        for player in monitored_players:
            if is_player_ignored(player['ff_uid'], interaction.channel.id):
                ignored_players.append(player)
            else:
                active_players.append(player)
        
        embed = discord.Embed(
            title="👁️ Monitored Players",
            description=f"Active: {len(active_players)} | Ignored: {len(ignored_players)}",
            color=discord.Color.orange(),
        )

        # Show active players
        if active_players:
            active_text = ""
            for player in active_players:
                nickname = player["nickname"] or "Unknown"
                active_text += (
                    f"**{nickname}** (UID: `{player['ff_uid']}`)\n"
                    f"Ends: {player['monitoring_end']}\n\n"
                )
            if len(active_text) > 2000:
                active_text = active_text[:2000] + "..."
            embed.add_field(name="🟢 Active Monitoring", value=active_text, inline=False)
        
        # Show ignored players
        if ignored_players:
            ignored_text = ""
            for player in ignored_players:
                nickname = player["nickname"] or "Unknown"
                ignored_text += (
                    f"**{nickname}** (UID: `{player['ff_uid']}`)\n"
                    f"Ends: {player['monitoring_end']}\n\n"
                )
            if len(ignored_text) > 2000:
                ignored_text = ignored_text[:2000] + "..."
            embed.add_field(name="⏸️ Currently Ignored", value=ignored_text, inline=False)
        
        if not active_players and not ignored_players:
            embed.add_field(name="No Players", value="No players are currently being monitored.", inline=False)

        embed.set_footer(text="👁️ Active players are monitored | ⏸️ Ignored players are temporarily skipped")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="ignore_player", description="Temporarily ignore monitoring for a player (Commanders only)")
    @app_commands.describe(
        uid="Free Fire UID of the player to ignore",
        ignore_hours="Number of hours to ignore monitoring (1-168)"
    )
    async def ignore_player(self, interaction: discord.Interaction, uid: int, ignore_hours: int):
        """Temporarily ignore monitoring for a player."""
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_commander(interaction):
            await interaction.followup.send("❌ Only Commanders or Administrators can ignore player monitoring.", ephemeral=True)
            return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild is registered for this channel. Register a guild first.", ephemeral=True)
            return

        if ignore_hours < 1 or ignore_hours > 168:
            await interaction.followup.send("❌ Ignore duration must be between 1 and 168 hours.", ephemeral=True)
            return

        if not is_player_monitored(uid, interaction.channel.id):
            await interaction.followup.send(f"❌ Player UID `{uid}` is not currently being monitored for this guild.", ephemeral=True)
            return

        if is_player_ignored(uid, interaction.channel.id):
            await interaction.followup.send(f"❌ Player UID `{uid}` is already being ignored for monitoring.", ephemeral=True)
            return

        success = ignore_monitored_player(ignore_hours, uid, interaction.channel.id)

        if success:
            embed = discord.Embed(
                title="⏸️ Player Monitoring Ignored",
                color=discord.Color.yellow(),
            )
            embed.add_field(name="Player UID", value=f"`{uid}`", inline=True)
            embed.add_field(name="Ignore Duration", value=f"{ignore_hours} hours", inline=True)
            embed.add_field(name="Ignored by", value=interaction.user.mention, inline=True)
            embed.set_footer(text="Player monitoring will resume after the ignore period")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to ignore player monitoring.", ephemeral=True)

    @app_commands.command(name="unignore_player", description="Resume monitoring for an ignored player (Commanders only)")
    @app_commands.describe(uid="Free Fire UID of the player to resume monitoring")
    async def unignore_player(self, interaction: discord.Interaction, uid: int):
        """Resume monitoring for an ignored player."""
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        if not is_commander(interaction):
            await interaction.followup.send("❌ Only Commanders or Administrators can resume player monitoring.", ephemeral=True)
            return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild is registered for this channel. Register a guild first.", ephemeral=True)
            return

        if not is_player_monitored(uid, interaction.channel.id):
            await interaction.followup.send(f"❌ Player UID `{uid}` is not currently being monitored for this guild.", ephemeral=True)
            return

        if not is_player_ignored(uid, interaction.channel.id):
            await interaction.followup.send(f"❌ Player UID `{uid}` is not currently being ignored.", ephemeral=True)
            return

        success = unignore_monitored_player(uid, interaction.channel.id)

        if success:
            embed = discord.Embed(
                title="▶️ Player Monitoring Resumed",
                color=discord.Color.green(),
            )
            embed.add_field(name="Player UID", value=f"`{uid}`", inline=True)
            embed.add_field(name="Resumed by", value=interaction.user.mention, inline=True)
            embed.set_footer(text="Player monitoring has been resumed")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to resume player monitoring.", ephemeral=True)

    @app_commands.command(name="guild_status", description="Check all monitoring services and status for this channel")
    async def guild_status(self, interaction: discord.Interaction):
        """Check comprehensive monitoring status and active services for this channel"""
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        guild_id = self.get_channel_guild_id(interaction.channel.id)

        if not guild_id:
            embed = discord.Embed(
                title="📊 Guild Monitoring Status",
                description="No guild registered for this channel",
                color=discord.Color.greyple()
            )
            embed.add_field(
                name="Setup Required",
                value="Use `/register_guild` to start monitoring this channel",
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get comprehensive status information
        channel_id = interaction.channel.id
        global_interval = self.monitoring_interval
        player_interval = get_channel_player_monitoring_interval(channel_id)
        last_player_check = get_channel_last_player_check(channel_id)

        # Get monitored players data
        all_monitored = get_monitored_players(channel_id)
        active_monitored = []
        ignored_monitored = []

        for player in all_monitored:
            if is_player_ignored(player['ff_uid'], channel_id):
                ignored_monitored.append(player)
            else:
                active_monitored.append(player)

        # Get partnered guilds count
        flagged_clans = get_flagged_clans()
        flagged_count = len(flagged_clans)

        # Get guild name
        guild_name = get_channel_guild_name(channel_id) or f"Guild {guild_id}"

        # Create comprehensive status embed
        embed = discord.Embed(
            title="📊 Guild Monitoring Services Status",
            description=f"**{guild_name}** (ID: `{guild_id}`)",
            color=discord.Color.green(),
            timestamp=get_ist_now()
        )

        # Basic registration info
        embed.add_field(name="🏢 Channel", value=interaction.channel.mention, inline=True)
        embed.add_field(name="📋 Registration", value="✅ Active", inline=True)
        embed.add_field(name="👤 Registered By", value=f"<@{get_channel_registered_by(channel_id)}>", inline=True)

        # Get service enable/disable status
        player_monitoring_enabled = get_player_monitoring_enabled(channel_id)
        rival_detection_enabled = get_rival_detection_enabled(channel_id)
        auto_monitoring_enabled = get_auto_monitoring_enabled(channel_id)

        # Monitoring services status
        services_status = []
        services_status.append(f"🔄 **Guild Monitoring**: Active ({global_interval}min intervals)")
        services_status.append(f"👁️ **Player Monitoring**: Active ({player_interval}min intervals)")
        services_status.append(f"🚨 **Partnered Guild Detection**: Active ({flagged_count} partnered guilds)" if flagged_count > 0 else f"🚨 **Partnered Guild Detection**: Active (no partnered guilds)")
        auto_monitor_duration = get_auto_monitor_duration(channel_id)
        auto_monitor_speed = get_auto_monitor_speed(channel_id)
        if auto_monitoring_enabled:
            services_status.append(f"🤖 **Auto-Monitoring**: Enabled ({auto_monitor_speed}min speed, {auto_monitor_duration}d duration)")
        else:
            services_status.append(f"🤖 **Auto-Monitoring**: Disabled")

        embed.add_field(
            name="⚙️ Monitoring Services",
            value="\n".join(services_status),
            inline=False
        )

        # Player monitoring details
        if active_monitored or ignored_monitored:
            player_status = []
            if active_monitored:
                player_status.append(f"🟢 **Active Monitoring**: {len(active_monitored)} players")
            if ignored_monitored:
                player_status.append(f"⏸️ **Ignored Players**: {len(ignored_monitored)} players")

            embed.add_field(
                name="👥 Player Monitoring",
                value="\n".join(player_status),
                inline=True
            )

        # Last activity
        last_activity = []
        if last_player_check:
            from datetime import datetime
            last_check_time = datetime.fromisoformat(last_player_check.replace('Z', '+00:00'))
            time_diff = get_ist_now() - last_check_time
            hours_ago = time_diff.total_seconds() / 3600
            if hours_ago < 1:
                time_str = f"{time_diff.total_seconds() / 60:.1f} minutes ago"
            else:
                time_str = f"{hours_ago:.1f} hours ago"
            last_activity.append(f"👁️ Player Check: {time_str}")
        else:
            last_activity.append("👁️ Player Check: Never")

        embed.add_field(
            name="⏰ Last Activity",
            value="\n".join(last_activity),
            inline=True
        )

        # Quick actions
        embed.add_field(
            name="🛠️ Quick Actions",
            value="• `/list_monitored` - View monitored players\n• `/guild_updates` - Check recent changes\n• `/enable_player_monitoring` - Enable player monitoring\n• `/disable_rival_detection` - Disable partnered guild alerts",
            inline=False
        )

        embed.set_footer(text="Use /help for all available commands")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="guild_members", description="View current guild members with guild information")
    async def guild_members(self, interaction: discord.Interaction):
        """Show current members of the monitored guild with guild details"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild registered for this channel.", ephemeral=True)
            return

        guild_name = get_channel_guild_name(interaction.channel.id) or "Unknown Guild"
        registered_by_id = get_channel_registered_by(interaction.channel.id)
        registered_by = f"<@{registered_by_id}>" if registered_by_id else "Unknown"
        access_token = get_channel_access_token(interaction.channel.id)
        if not access_token:
            await interaction.followup.send("❌ Guild access not configured for this channel.", ephemeral=True)
            return

        try:
            api_response = fetch_member_guild(access_token, timeout=45, retries=1)
            members = api_response.get("members", [])

            if not members:
                await interaction.followup.send("❌ No members found in guild.", ephemeral=True)
                return

            changes = get_channel_recent_changes(interaction.channel.id, 200)  # Get more changes to filter
            
            # No time filtering - show all changes
            filtered_changes = changes

            embed = discord.Embed(
                title="👥 Guild Members",
                description=f"Guild details and update summary for **{guild_name}**",
                color=discord.Color.blue(),
                timestamp=get_ist_now()
            )

            embed.add_field(name="🆔 Guild ID", value=f"`{guild_id}`", inline=True)
            embed.add_field(name="🏷️ Guild Name", value=guild_name, inline=True)
            embed.add_field(name="🛠️ Registered By", value=registered_by, inline=True)
            embed.add_field(name=" Changes in Period", value=str(len(filtered_changes)), inline=True)

            # Add last 10 logs to main page
            recent_logs = filtered_changes[:10] if filtered_changes else []
            if recent_logs:
                log_lines = []
                for change in recent_logs:
                    emoji = "✅" if change["change_type"] == "joined" else "❌"
                    nickname = change["nickname"] or f"UID: {change['uid']}"
                    uid = change["uid"]
                    timestamp = change["timestamp"]
                    log_lines.append(f"{emoji} {nickname} ({uid})\n   {timestamp}")

                log_text = "\n".join(log_lines)
                embed.add_field(
                    name="Last 10 Activities",
                    value=f"```\n{log_text}\n```",
                    inline=False
                )

            if interaction.guild and interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)

            view = GuildMembersView(members, guild_name, guild_id, filtered_changes)
            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to fetch members: {e}", ephemeral=True)

    async def guild_updates(self, interaction: discord.Interaction, limit: int = 20):
        """Show combined guild members and recent membership changes"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        limit = max(1, min(limit, 50))
        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild registered for this channel.", ephemeral=True)
            return

        access_token = get_channel_access_token(interaction.channel.id)
        if not access_token:
            await interaction.followup.send("❌ Guild access not configured for this channel.", ephemeral=True)
            return

        try:
            api_response = fetch_member_guild(access_token, timeout=45, retries=1)
            members = api_response.get("members", [])

            if not members:
                await interaction.followup.send("❌ No members found in guild.", ephemeral=True)
                return

            guild_name = api_response.get("guild_name", "Unknown Guild")

            changes = get_channel_recent_changes(interaction.channel.id, limit)
            joined_count = sum(1 for c in changes if c["change_type"] == "joined")
            left_count = sum(1 for c in changes if c["change_type"] == "left")

            member_lines = []
            for member in members:
                uid = member.get("account_id") or member.get("uid", "Unknown")
                nickname = member.get("nickname", f"UID: {uid}")
                member_lines.append(f"{nickname} ({uid})")

            change_lines = []
            for change in changes:
                emoji = "✅" if change["change_type"] == "joined" else "❌"
                nickname = change["nickname"] or f"UID: {change['uid']}"
                timestamp = change["timestamp"].split("T")[0]
                change_lines.append(f"{emoji} {nickname} - {timestamp}")

            # Create single embed with all members instead of pagination
            embed = discord.Embed(
                title="👥 Guild Member List",
                description=f"Full member list for **{guild_name or 'Unknown Guild'}**",
                color=discord.Color.blue(),
                timestamp=get_ist_now()
            )

            # Add guild info
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            embed.add_field(name="Total Members", value=str(len(members)), inline=True)
            embed.add_field(name="Recent Changes", value=f"{len(changes)}\n✅ {joined_count} Joined\n❌ {left_count} Left", inline=True)

            # Create single field with all members
            member_text = "\n".join(f"{i+1}. {line}" for i, line in enumerate(member_lines))
            field_value = f"```\n{member_text}\n```"

            # Discord allows max 1024 characters per field, but we'll try to fit as many as possible
            if len(field_value) > 1024:
                # If too long, truncate gracefully
                lines = [f"{i+1}. {line}" for i, line in enumerate(member_lines)]
                while lines and len(f"```\n{chr(10).join(lines)}\n```") > 1024:
                    lines = lines[:-1]  # Remove last member until it fits
                field_value = f"```\n{chr(10).join(lines)}\n... and {len(member_lines) - len(lines)} more members\n```"

            embed.add_field(
                name="Members",
                value=field_value,
                inline=False
            )

            # Add recent changes if any
            if change_lines:
                change_text = "\n".join(change_lines[:10])  # Show first 10 changes
                if len(change_lines) > 10:
                    change_text += f"\n... and {len(change_lines) - 10} more changes"
                embed.add_field(
                    name="Recent Changes",
                    value=f"```\n{change_text}\n```",
                    inline=False
                )

            if interaction.guild and interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to fetch guild updates: {e}", ephemeral=True)

    @app_commands.command(name="guild_member_list", description="View all current guild members with detailed data")
    @app_commands.describe(limit="Number of members to show per page (max 50)", csv_export="Export as CSV file")
    async def guild_member_list(self, interaction: discord.Interaction, limit: int = 20, csv_export: bool = False):
        """Show all current guild members with detailed information including UID, name, and join dates"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            try:
                await interaction.response.send_message("⏱️ Processing took too long. Please try again.", ephemeral=True)
            except:
                return

        limit = min(limit, 50)  # Cap at 50 per page

        guild_id = self.get_channel_guild_id(interaction.channel.id)
        if not guild_id:
            await interaction.followup.send("❌ No guild registered for this channel.", ephemeral=True)
            return

        access_token = get_channel_access_token(interaction.channel.id)
        if not access_token:
            await interaction.followup.send("❌ Guild access not configured for this channel.", ephemeral=True)
            return

        try:
            # Fetch current members from API
            api_response = fetch_member_guild(access_token, timeout=45, retries=1)
            members = api_response.get("members", [])

            if not members:
                await interaction.followup.send("❌ No members found in guild.", ephemeral=True)
                return

            # Create member data (name and UID only)
            member_data = []
            for member in members:
                uid = member.get("account_id") or member.get("uid", "Unknown")
                nickname = member.get("nickname", f"UID: {uid}")

                member_data.append({
                    "nickname": nickname,
                    "uid": uid
                })

            # Sort by nickname
            member_data.sort(key=lambda x: x["nickname"])

            if csv_export:
                # Create CSV content and send as plain text
                csv_lines = ["Nickname,UID"]
                for member in member_data:
                    # Escape commas in nickname
                    nickname = member["nickname"].replace(",", ";")
                    csv_lines.append(f"{nickname},{member['uid']}")

                csv_content = "\n".join(csv_lines)
                await interaction.followup.send(f"📊 Guild Members (CSV Format) - {len(member_data)} members:\n```\n{csv_content}\n```")
                return

            # Create paginated embeds
            pages = []
            total_pages = math.ceil(len(member_data) / limit)

            for page_num in range(total_pages):
                start_idx = page_num * limit
                end_idx = min(start_idx + limit, len(member_data))
                page_members = member_data[start_idx:end_idx]

                embed = discord.Embed(
                    title="👥 Guild Members",
                    description=f"All current members of {interaction.channel.mention} (Page {page_num + 1}/{total_pages})",
                    color=discord.Color.green(),
                    timestamp=get_ist_now()
                )

                embed.add_field(name="📊 Total Members", value=str(len(member_data)), inline=True)
                embed.add_field(name="📄 Showing", value=f"{start_idx + 1}-{end_idx}", inline=True)
                embed.add_field(name="🆔 Guild ID", value=f"`{guild_id}`", inline=True)

                member_list = []
                for member in page_members:
                    member_list.append(f"**{member['nickname']}**\n🆔 `{member['uid']}`")

                if member_list:
                    embed.add_field(
                        name="Members",
                        value="\n\n".join(member_list),
                        inline=False
                    )

                if interaction.guild and interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)

                embed.set_footer(text=f"Page {page_num + 1}/{total_pages} • Use Previous/Next to navigate • Set csv_export=true for CSV download")
                pages.append(embed)

            if not pages:
                await interaction.followup.send("📭 No members found.", ephemeral=True)
                return

            # Send first page with navigation
            view = GuildUpdatesView(pages)
            await interaction.followup.send(embed=pages[0], view=view)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to fetch member data: {e}", ephemeral=True)

    @app_commands.command(name="debug_player_monitor", description="Debug player monitoring for a specific player (Admin only)")
    @app_commands.describe(uid="Free Fire UID to debug")
    async def debug_player_monitor(self, interaction: discord.Interaction, uid: int):
        """Debug player monitoring status"""
        try:
            await interaction.response.defer(ephemeral=True)
        except:
            return

        # Check permissions
        if not is_commander(interaction):
            await interaction.followup.send("❌ Only Commanders can use this command.", ephemeral=True)
            return

        from member_clan_api import get_player_clan_info
        
        channel_id = interaction.channel.id
        monitored = get_monitored_players(channel_id)
        flagged_clans = get_flagged_clans()
        
        # Check if player is in monitored list
        monitored_player = next((p for p in monitored if p['ff_uid'] == uid), None)
        
        embed = discord.Embed(
            title=f"🔍 Player Monitoring Debug: UID {uid}",
            color=discord.Color.blue()
        )
        
        # Check if monitored
        if monitored_player:
            embed.add_field(name="Monitoring Status", value="✅ YES - being monitored", inline=True)
            embed.add_field(name="Nickname", value=monitored_player['nickname'], inline=True)
        else:
            embed.add_field(name="Monitoring Status", value="❌ NO - not being monitored in this channel", inline=True)
        
        # Get current guild
        try:
            current_guild = await asyncio.to_thread(get_player_clan_info, uid)
            if current_guild:
                guild_id = int(current_guild.get('clanId', 'N/A'))
                guild_name = current_guild.get('clanName', f'Guild {guild_id}')
                embed.add_field(name="Current Guild", value=f"{guild_name} (ID: {guild_id})", inline=True)
                
                # Check if in a partnered guild
                is_rival = guild_id in flagged_clans
                embed.add_field(name="Is Partnered Guild?", value=f"{'🚨 YES' if is_rival else '❌ NO'}", inline=True)
                
                # Check if different from registered guild
                registered_guild_id = get_channel_guild_id(channel_id)
                is_different = guild_id != registered_guild_id
                embed.add_field(name="Different from Registered?", value=f"{'✅ YES' if is_different else '❌ NO'}", inline=True)
            else:
                embed.add_field(name="Current Guild", value="❌ Player not in any guild", inline=True)
        except Exception as e:
            embed.add_field(name="Current Guild", value=f"⚠️ Error fetching: {e}", inline=True)
        
        # Show partnered guilds
        embed.add_field(name="Partnered Guilds", value=f"Total: {len(flagged_clans)}\n{', '.join(str(c) for c in sorted(flagged_clans)[:5])}{'...' if len(flagged_clans) > 5 else ''}", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    """Load the guild monitoring cog"""
    # Database is initialized automatically when channel_guild_monitoring is imported
    await bot.add_cog(GuildMonitoringCog(bot))