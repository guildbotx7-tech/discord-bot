"""Discord bot task for continuous clan monitoring.

Run this as a background task in your Discord bot using discord.py.
"""

from discord.ext import tasks

from clan_monitoring import monitor_clan_roster
from token_manager import get_registered_guilds, get_token_for_guild


@tasks.loop(minutes=10)
async def monitor_all_clans(bot):
    """Background task that runs every 10 minutes to check all registered clans.

    Args:
        bot: Discord bot instance.
    """
    print("\n" + "=" * 60)
    print("🔍 CLAN MONITORING CYCLE")
    print("=" * 60)

    registered_guilds = get_registered_guilds()
    
    if not registered_guilds:
        print("No guilds registered for monitoring.")
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
                print(f"Guild {guild_id}: No changes")
        else:
            print(f"Guild {guild_id}: {result['error']}")

        # Add delay between guild checks to avoid rate limiting
        if i < len(registered_guilds) - 1:  # Don't delay after the last guild
            await asyncio.sleep(2)  # 2 second delay between API calls

    print("=" * 60 + "\n")


@monitor_all_clans.before_loop
async def before_monitor_all_clans():
    """Wait for bot to be ready before starting monitoring."""
    await None  # This will be awaited by discord.py


def setup_clan_monitoring(bot):
    """Initialize clan monitoring on bot startup.

    Call this from your bot's setup_hook() or in a cog's __init__.

    Args:
        bot: Discord bot instance.

    Example:
        @bot.event
        async def setup_hook():
            setup_clan_monitoring(bot)
    """
    monitor_all_clans.start(bot)
    print("✅ Clan monitoring task started (runs every 10 minutes)")


def stop_clan_monitoring():
    """Stop the monitoring task."""
    if monitor_all_clans.is_running():
        monitor_all_clans.stop()
        print("⏹️ Clan monitoring task stopped")
