"""Discord bot task for continuous guild monitoring.

Run this as a background task in your Discord bot using discord.py.
"""

import asyncio
import discord
from discord.ext import tasks
from datetime import datetime

from clan_monitoring import monitor_clan_roster, get_flagged_clans
from channel_guild_monitoring import get_ban_monitoring_interval
from helpers import get_banned_players, mark_banned_player_alert_sent
from member_clan_api import get_player_clan_info, fetch_player_info
from token_manager import get_registered_guilds, get_notification_channel_for_guild, get_token_for_guild


async def alert_banned_players_in_partnered_clans(bot):
    """Check active banned players and alert if they join a partnered guild."""
    banned_players = get_banned_players()
    if not banned_players:
        return

    flagged_clans = get_flagged_clans()
    if not flagged_clans:
        return

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
            channel = bot.get_channel(int(channel_id_str))
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
                print(f"Sent banned player alert for UID {uid} to channel {channel.id}")
            except Exception as e:
                print(f"Failed to send banned player alert to channel {channel_id_str}: {e}")
        else:
            print(f"Could not resolve channel {channel_id_str} for banned UID {uid}")

        if sent_ok:
            mark_banned_player_alert_sent(uid, channel_id_str, clan_id, clan_name)
        else:
            print(f"Did not mark alert sent for banned UID {uid} since the message was not delivered")


class ConfigurableClanMonitor:
    """Configurable guild monitoring task that can change intervals dynamically."""
    
    def __init__(self, bot):
        self.bot = bot
        self.current_interval = get_ban_monitoring_interval()
        self.task = None
        self.create_task()
    
    def create_task(self):
        """Create the monitoring task with current interval."""
        if self.task:
            self.task.cancel()
        
        @tasks.loop(minutes=self.current_interval)
        async def monitor_all_clans():
            """Background task that runs to check all registered guilds."""
            print("\n" + "=" * 60)
            print("🔍 GUILD MONITORING CYCLE")
            print("=" * 60)

            registered_guilds = get_registered_guilds()
            await alert_banned_players_in_partnered_clans(self.bot)
            
            if not registered_guilds:
                print("No servers registered for monitoring.")
                print("=" * 60 + "\n")
                return

            for i, guild_id in enumerate(registered_guilds):
                access_token = get_token_for_guild(guild_id)
                
                if not access_token:
                    print(f"Server {guild_id}: Token not available")
                    continue

                result = monitor_clan_roster(access_token, guild_id)

                if result["status"] == "success":
                    changes = result["changes"]
                    current_members = result.get("members", [])
                    flagged_clans = get_flagged_clans()
                    is_flagged_guild = guild_id in flagged_clans

                    if changes["joined"] or changes["left"]:
                        channel_id = get_notification_channel_for_guild(guild_id)
                        channel = self.bot.get_channel(channel_id) if channel_id else None

                        title = "� Guild Monitoring Update"
                        description = (
                            f"Guild monitoring detected {len(changes['joined'])} joined and {len(changes['left'])} left."
                        )

                        embed = discord.Embed(
                            title=title,
                            description=description,
                            color=discord.Color.blue(),
                            timestamp=get_ist_now()
                        )
                        embed.add_field(name="Guild ID", value=str(guild_id), inline=True)
                        if changes["joined"]:
                            embed.add_field(name="Joined", value=str(len(changes["joined"])), inline=True)
                        if changes["left"]:
                            embed.add_field(name="Left", value=str(len(changes["left"])), inline=True)

                        if channel:
                            try:
                                await channel.send(embed=embed)
                                print(f"Server {guild_id}: Sent notification to channel {channel.name} ({channel.id})")
                            except Exception as e:
                                print(f"Server {guild_id}: Failed to send notification to channel {channel_id}: {e}")
                        else:
                            print(f"Server {guild_id}: No notification channel registered or accessible")

                        if guild := self.bot.get_guild(guild_id):
                            print(f"Guild: {guild.name} (ID: {guild_id})")
                        if changes["joined"]:
                            print(f"  ✅ Joined: {len(changes['joined'])} member(s)")
                        if changes["left"]:
                            print(f"  ❌ Left: {len(changes['left'])} member(s)")
                    else:
                        print(f"Server {guild_id}: No membership changes")
                else:
                    print(f"Server {guild_id}: Monitoring failed - {result.get('error', 'Unknown error')}")
            
            print("=" * 60 + "\n")
        
        self.task = monitor_all_clans
    
    def update_interval(self, new_interval):
        """Update the monitoring interval and restart the task."""
        self.current_interval = new_interval
        self.create_task()
        if not self.task.is_running():
            self.task.start()
    
    def start(self):
        """Start the monitoring task."""
        if self.task and not self.task.is_running():
            self.task.start()
    
    def stop(self):
        """Stop the monitoring task."""
        if self.task and self.task.is_running():
            self.task.cancel()


# Global instance
clan_monitor = None


@tasks.loop(minutes=10)
async def monitor_all_clans(bot):
    """Legacy function for backward compatibility."""
    global clan_monitor
    if clan_monitor:
        # This shouldn't be called if using the new system
        return
    
    # Fallback to old implementation
    print("\n" + "=" * 60)
    print("🔍 GUILD MONITORING CYCLE")
    print("=" * 60)

    registered_guilds = get_registered_guilds()
    await alert_banned_players_in_partnered_clans(bot)
    
    if not registered_guilds:
        print("No servers registered for monitoring.")
        print("=" * 60 + "\n")
        return

    for i, guild_id in enumerate(registered_guilds):
        access_token = get_token_for_guild(guild_id)
        
        if not access_token:
            print(f"Guild {guild_id}: Token not available")
            continue

        result = monitor_clan_roster(access_token, guild_id)

        if result["status"] == "success":
            changes = result["changes"]
            if changes["joined"] or changes["left"]:
                # Find the guild and send notifications (optional)
                guild = bot.get_guild(guild_id)
                if guild:
                    print(f"Guild: {guild.name} (ID: {guild_id})")
                    if changes["joined"]:
                        print(f"  ✅ Joined: {len(changes['joined'])} member(s)")
                    if changes["left"]:
                        print(f"  ❌ Left: {len(changes['left'])} member(s)")
            else:
                print(f"Guild {guild_id}: No membership changes")
        else:
            print(f"Guild {guild_id}: Monitoring failed - {result.get('error', 'Unknown error')}")
    
    print("=" * 60 + "\n")


@monitor_all_clans.before_loop
async def before_monitor_all_clans():
    """Wait for bot to be ready before starting monitoring."""
    await None  # This will be awaited by discord.py


def setup_clan_monitoring(bot):
    """Initialize guild monitoring on bot startup.

    Call this from your bot's setup_hook() or in a cog's __init__.

    Args:
        bot: Discord bot instance.

    Example:
        @bot.event
        async def setup_hook():
            setup_clan_monitoring(bot)
    """
    global clan_monitor
    clan_monitor = ConfigurableClanMonitor(bot)
    clan_monitor.start()
    print(f"✅ Guild monitoring task started (runs every {clan_monitor.current_interval} minutes)")


def stop_clan_monitoring():
    """Stop the monitoring task."""
    global clan_monitor
    if clan_monitor:
        clan_monitor.stop()
        print("⏹️ Guild monitoring task stopped")
