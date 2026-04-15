"""Integration guide for guild membership monitoring.

This file shows how to integrate the guild monitoring system into your Discord bot.
"""

# ============================================================================
# SETUP IN YOUR BOT'S MAIN FILE (e.g., reconcile_bot.py)
# ============================================================================

"""
From your bot initialization code, add these imports:

    from clan_monitor_task import setup_clan_monitoring, register_guild_token
    from member_guild_api import fetch_member_guild, get_roster_uids

And in your bot's setup_hook():

    @bot.event
    async def setup_hook():
        # Load your existing cogs
        await bot.load_extension('cogs.yourexistingcog')
        
        # Setup guild monitoring
        setup_clan_monitoring(bot)

Register guild tokens (BEFORE calling setup_clan_monitoring):

    # Option 1: From environment variables
    # Set these in your .env file:
    GUILD_TOKEN_123456789=your_api_token_here
    GUILD_TOKEN_987654321=another_api_token_here
    
    # Option 2: Manually register
    register_guild_token(123456789, "your_api_token_here")
    
    # Then call this:
    setup_clan_monitoring(bot)
"""

# ============================================================================
# DISCORD BOT COMMANDS
# ============================================================================

"""
After setting up the cog, you can use these commands in Discord:

1. View all recent changes:
   !clan_changes         # Shows last 20 changes
   !clan_changes 50      # Shows last 50 changes
   !cc                   # Shortcut

2. View only joins:
   !clan_joins           # Shows last 10 joins
   !clan_joins 20        # Shows last 20 joins

3. View only leaves:
   !clan_leaves          # Shows last 10 leaves
   !clan_leaves 30       # Shows last 30 leaves

4. View statistics:
   !clan_stats           # Shows summary: total joins, leaves, net change
"""

# ============================================================================
# HOW IT WORKS
# ============================================================================

"""
1. MONITORING RUNS EVERY 10 MINUTES:
   - Fetches current guild roster from the API
   - Compares with previous roster snapshot
   - Detects who joined and who left
   - Stores all changes in SQLite database

2. DATABASE TABLES:
   - roster_snapshots: Stores the current roster UIDs for each guild
   - membership_changes: Logs all join/leave events with timestamps

3. COMMANDS RETRIEVE HISTORY:
   !clan_changes  → Shows all recorded changes with timestamps
   !clan_joins    → Filters to show only joins
   !clan_leaves   → Filters to show only leaves
   !clan_stats    → Shows aggregate statistics
"""

# ============================================================================
# ENVIRONMENT VARIABLE SETUP (.env file)
# ============================================================================

"""
For each Discord server/guild you want to monitor, add:

    GUILD_TOKEN_<GUILD_ID>=<YOUR_API_TOKEN>

Example:
    GUILD_TOKEN_123456789=abc123def456xyz789
    GUILD_TOKEN_987654321=zyx789abc123def456

To find your Guild ID in Discord:
1. Enable Developer Mode (User Settings → Advanced → Developer Mode)
2. Right-click guild name → Copy Server ID

To get the API token:
1. Contact your Free Fire API provider
2. Token should have access to memberClan endpoint
"""

# ============================================================================
# FILES INVOLVED
# ============================================================================

"""
member_clan_api.py
  └─ Handles API communication
  └─ Detects roster changes
  └─ Provides core helper functions

clan_monitoring.py
  └─ Manages database (clan_monitoring.db)
  └─ Logs join/leave events
  └─ Provides change history retrieval

clan_monitor_task.py
  └─ Discord.py background task
  └─ Runs every 10 minutes
  └─ Processes all registered guilds

cogs/clan_monitoring_commands.py
  └─ Discord bot commands
  └─ !clan_changes, !clan_joins, !clan_leaves, !clan_stats
"""

# ============================================================================
# EXAMPLE COMPLETE BOT INTEGRATION
# ============================================================================

"""
# reconcile_bot.py (or similar)

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

from clan_monitor_task import setup_clan_monitoring, register_guild_token

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print('------')

    # Load all cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('_'):
            await bot.load_extension(f'cogs.{filename[:-3]}')

@bot.event
async def setup_hook():
    # Initialize clan monitoring
    setup_clan_monitoring(bot)

# Run the bot
bot.run(os.getenv('TOKEN'))
"""
