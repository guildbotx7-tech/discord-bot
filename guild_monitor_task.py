"""Discord bot task for continuous guild monitoring.

Run this as a background task in your Discord bot using discord.py.
"""

from discord.ext import tasks

from guild_monitoring import monitor_guild_list


@tasks.loop(minutes=10)
async def monitor_all_guilds(bot):
    """Background task that runs every 10 minutes to check all registered guilds.

    Args:
        bot: Discord bot instance.
    """
    print("\n" + "=" * 60)
    print("🔥 GUILD MONITORING CYCLE")
    print("=" * 60)

    # For single-server bot, monitor the guild the bot is in
    if not bot.guilds:
        print("Bot is not in any servers.")
        print("=" * 60 + "\n")
        return

    # Get access token from environment
    import os
    access_token = os.getenv('GUILD_ACCESS_TOKEN')

    if not access_token:
        print("❌ GUILD_ACCESS_TOKEN not found in environment")
        print("=" * 60 + "\n")
        return

    for guild in bot.guilds:
        result = monitor_guild_list(access_token, guild.id)

        if result["status"] == "success":
            changes = result["changes"]
            if changes["joined"] or changes["left"]:
                print(f"Guild: {guild.name} (ID: {guild.id})")
                if changes["joined"]:
                    print(f"  ✅ Joined: {len(changes['joined'])} member(s)")
                if changes["left"]:
                    print(f"  ❌ Left: {len(changes['left'])} member(s)")
            else:
                print(f"Guild {guild.id}: No changes")
        else:
            print(f"Guild {guild.id}: {result['error']}")

    print("=" * 60 + "\n")


@monitor_all_guilds.before_loop
async def before_monitor_all_guilds():
    """Wait for bot to be ready before starting monitoring."""
    await None  # This will be awaited by discord.py


def setup_guild_monitoring(bot):
    """Initialize guild monitoring on bot startup.

    Call this from your bot's setup_hook() or in a cog's __init__.

    Args:
        bot: Discord bot instance.

    Example:
        @bot.event
        async def setup_hook():
            setup_guild_monitoring(bot)
    """
    monitor_all_guilds.start(bot)
    print("✅ Guild monitoring task started (runs every 10 minutes)")


def stop_guild_monitoring():
    """Stop the monitoring task."""
    if monitor_all_guilds.is_running():
        monitor_all_guilds.stop()
        print("⏹️ Guild monitoring task stopped")