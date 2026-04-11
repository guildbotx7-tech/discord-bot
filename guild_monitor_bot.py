"""Free Fire Guild Monitoring Bot

Standalone Discord bot for monitoring Free Fire guild membership changes.
Runs independently from other bots.
"""

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    description="Free Fire Guild Monitoring Bot"
)

@bot.event
async def on_ready():
    """Called when bot is ready and connected."""
    print("🔥 Free Fire Guild Monitoring Bot Online!")
    print(f"Bot: {bot.user.name} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} server(s)")
    print("=" * 50)

@bot.event
async def setup_hook():
    """Initialize bot components."""
    print("Loading cogs...")

    # Load cogs
    cogs_to_load = [
        'cogs.guild_monitoring_commands',
        'cogs.token_management'
    ]

    for cog in cogs_to_load:
        try:
            await bot.load_extension(cog)
            print(f"✅ Loaded {cog}")
        except Exception as e:
            print(f"❌ Failed to load {cog}: {e}")

    # Initialize guild monitoring
    try:
        from guild_monitor_task import setup_guild_monitoring
        setup_guild_monitoring(bot)
        print("✅ Guild monitoring initialized")
    except Exception as e:
        print(f"❌ Failed to initialize monitoring: {e}")

    print("Bot setup complete!")

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❓ Command not found. Use `!help` for available commands.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("🔒 You don't have permission to use this command.")
    else:
        print(f"Command error: {error}")
        await ctx.send("❌ An error occurred while processing your command.")

def main():
    """Main entry point."""
    # Get bot token
    token = os.getenv('GUILD_MONITOR_BOT_TOKEN')

    if not token:
        print("❌ ERROR: GUILD_MONITOR_BOT_TOKEN not found in .env file")
        print("Please add GUILD_MONITOR_BOT_TOKEN=your_bot_token_here to .env")
        return

    print("Starting Free Fire Guild Monitoring Bot...")
    bot.run(token)

if __name__ == '__main__':
    main()