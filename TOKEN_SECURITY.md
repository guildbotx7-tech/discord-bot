"""Secure Token Management Guide

This document explains how to securely manage guild monitoring tokens with owner-only access.
"""

# ============================================================================
# SECURITY OVERVIEW
# ============================================================================
"""
✅ TOKEN SECURITY FEATURES:
1. Only bot owner can register/manage tokens
2. Tokens are NEVER logged, printed, or exposed
3. Tokens stored only in environment variables (not in code or database)
4. Database only stores registration metadata, not the actual token
5. Multi-guild support with separate tokens per guild
6. Owner receives notifications of token operations via DM
7. All sensitive operations are ephemeral (hidden from normal users)
"""

# ============================================================================
# SETUP INSTRUCTIONS
# ============================================================================
"""
STEP 1: Set Environment Variables
==================================

For each server/guild you want to monitor, set an environment variable:

In your .env file:
    GUILD_TOKEN_123456789=your_secret_api_token_here
    GUILD_TOKEN_987654321=another_secret_token_here

Where:
- 123456789 = Discord Server ID (right-click server → Copy Server ID)
- your_secret_api_token_here = Free Fire memberGuild API token

Example:
    GUILD_TOKEN_63582136=abc123def456xyz789token
    GUILD_TOKEN_12345678=zyx789abc123def456token


STEP 2: Start Bot and Load Cogs
================================

In your main bot file (e.g., reconcile_bot.py):

    from clan_monitor_task import setup_clan_monitoring
    import discord
    from discord.ext import commands

    bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())

    @bot.event
    async def setup_hook():
        # Load the cogs (including token management and clan monitoring)
        await bot.load_extension('cogs.token_management')
        await bot.load_extension('cogs.clan_monitoring_commands')
        
        # Initialize monitoring
        setup_clan_monitoring(bot)

    bot.run(YOUR_BOT_TOKEN)


STEP 3: Register Token (Owner Only)
====================================

In Discord, the bot owner runs:
    !register_token              # Use current channel for notifications
    !register_token #announcements  # Use #announcements for notifications

Response (ephemeral, only visible to owner):
    ✅ Token Registered
    Guild monitoring activated for **Server Name**
    Notifications: #channel-name

The bot will send a confirmation to the owner's DMs.
"""

# ============================================================================
# COMMANDS REFERENCE
# ============================================================================
"""
OWNER-ONLY TOKEN COMMANDS
==========================

1. !register_token [channel]
   - Register this server's token for monitoring
   - Optional: specify notification channel (default: current channel)
   - Requires environment variable GUILD_TOKEN_<GUILD_ID> to be set
   - Response: Ephemeral, only visible to owner

2. !token_status
   - Check if this server has a registered token
   - Response: Ephemeral, only visible to owner

3. !unregister_token
   - Stop monitoring and unregister the token
   - ⚠️ Also manually remove/clear environment variable

PUBLIC MONITORING COMMANDS (anyone can use)
=============================================

1. !clan_changes [limit]
   - Show recent clan membership changes
   - Default: last 20 changes, max 100
   - Shows: joins, leaves, timestamps, nicknames

2. !clan_joins [limit]
   - Show only recent joins
   - Default: last 10 joins, max 50

3. !clan_leaves [limit]
   - Show only recent leaves
   - Default: last 10 leaves, max 50

4. !clan_stats
   - Show clan statistics
   - Displays: total joins, total leaves, net change
"""

# ============================================================================
# SECURITY BEST PRACTICES
# ============================================================================
"""
DO ✅
----
✓ Store tokens in .env file or system environment variables
✓ Add .env to .gitignore to prevent accidental commits
✓ Only share token setup with bot owner
✓ Use!register_token once per guild
✓ Check !token_status to verify registration
✓ Review DM confirmations from bot


DON'T ❌
--------
✗ Never paste a token in Discord (even privately authenticated)
✗ Never share tokens via GitHub, messages, or documentation
✗ Never hardcode tokens in Python files
✗ Never expose tokens in bot logs/console
✗ Never give non-owner users access to !register_token
✗ Never share .env files


IF TOKEN IS COMPROMISED
------------------------
1. Immediately revoke the token in the API provider settings
2. Generate a new token
3. Update .env with new token
4. Run !unregister_token then !register_token


MULTI-GUILD SETUP
-----------------
To monitor multiple Discord guilds/clans:

.env file:
    GUILD_TOKEN_111111111=token_for_guild_1
    GUILD_TOKEN_222222222=token_for_guild_2
    GUILD_TOKEN_333333333=token_for_guild_3

Then in each guild:
    Owner runs: !register_token
    
The monitoring system will automatically handle all registered guilds.
"""

# ============================================================================
# TECHNICAL DETAILS
# ============================================================================
"""
HOW IT WORKS INTERNALLY
------------------------

1. Token Storage:
   - Tokens are ONLY stored in environment variables
   - Database only stores: guild_id, channel_id, registration_time, owner_id
   - Actual token values never touched by database

2. Token Retrieval:
   - Only internal monitoring system can retrieve tokens
   - Uses _get_token_from_env() [private function]
   - Not accessible to Discord commands

3. Command Security:
   - @commands.is_owner() decorator enforces ownership
   - Responses are ephemeral (hidden from other users)
   - Sensitive operations NOT logged to console

4. Monitoring Loop (every 10 minutes):
   - Gets registered guilds from database
   - Retrieves token from environment for each guild
   - Fetches current clan roster from API
   - Compares with previous roster
   - Logs changes to membership_changes table
   - Public commands read from this table only

DATABASE STRUCTURE (Token Storage)
-----------------------------------

Table: access_tokens
- guild_id (INTEGER, UNIQUE) - Discord Guild ID
- channel_id (INTEGER) - Notification channel ID
- registered_by (INTEGER) - Owner's user ID
- registered_at (TEXT) - ISO timestamp

Note: The actual token is NOT stored here.
Token is only in environment, never in database.

Table: membership_changes (readOnly from clan_monitoring.py)
- ff_uid - Free Fire UID
- change_type - "joined" or "left"
- nickname - Player's Free Fire nickname
- detected_at - ISO timestamp
"""

# ============================================================================
# TROUBLESHOOTING
# ============================================================================
"""
Problem: !register_token fails with "Token not found in environment"
Solution:
1. Check .env file: GUILD_TOKEN_<GUILD_ID>=<TOKEN> exists
2. Verify GUILD_ID matches your Discord guild ID (right-click guild)
3. Ensure .env is properly loaded (check with: python -c "import os; print(os.getenv('GUILD_TOKEN_<ID>'))")

Problem: Only owner can see command responses
Solution:
This is expected! Token commands are owner-only and ephemeral.

Problem: Token expired or API returns 401 Unauthorized
Solution:
1. Generate new token from API provider
2. Update .env
3. Run !unregister_token
4. Run !register_token (to re-register with new token)

Problem: Monitoring not running
Solution:
1. Check if bot is connected to Discord
2. Verify cli_monitor_task.py was loaded in setup_hook()
3. Check bot console for error messages
4. Ensure at least one guild has a registered token
"""

# ============================================================================
# COMPLETE INTEGRATION EXAMPLE
# ============================================================================
"""
# reconcile_bot.py

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load tokens from .env
load_dotenv()

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.event
async def setup_hook():
    '''Load cogs and initialize monitoring'''
    
    # Load all cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('_'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded {filename}')
            except Exception as e:
                print(f'Failed to load {filename}: {e}')
    
    # Initialize clan monitoring
    from clan_monitor_task import setup_clan_monitoring
    setup_clan_monitoring(bot)

# Run the bot
if __name__ == '__main__':
    token = os.getenv('TOKEN')
    if not token:
        raise ValueError('TOKEN environment variable not set in .env')
    bot.run(token)
"""

# .env structure
"""
# Bot token
TOKEN=your_discord_bot_token_here

# Guild tokens for clan monitoring
GUILD_TOKEN_63582136=your_free_fire_api_token_for_guild_1
GUILD_TOKEN_12345678=your_free_fire_api_token_for_guild_2

# SQLite Database - Local file storage
# Databases: discord_bot.db, clan_monitoring.db
"""
