"""Discord Bot - Main Entry Point"""
import os
import sys
import discord
from discord.ext import commands
import re
from dotenv import load_dotenv
from channel_guild_monitoring import init_channel_monitoring_db

# Ensure root emits this folder in module search path so cogs can import helpers.
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Load environment variables from .env file
load_dotenv()

TOKEN = os.getenv("TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optional for instant guild-level slash command registration
ALLOWED_GUILD_ID = 1485214892213538878  # Only server where bot is allowed to operate

# Import version management
from version import get_current_version, get_version_string

# Bot versioning follows semantic style: major.minor.patch
# - major: breaking or very major updates
# - minor: new features, command additions, or medium updates
# - patch: bug fixes and small improvements
# Reset lower values when the next higher value changes
BOT_VERSION_INFO = get_current_version()
BOT_VERSION = get_version_string()

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.owner_id = 1304326261241413664  # Set bot owner ID
        self.version = BOT_VERSION
        self.version_info = BOT_VERSION_INFO
        self.ID_RE = re.compile(r"\b(\d{6,20})\b")

    async def setup_hook(self):
        """Load all command cogs at startup"""
        # Initialize main bot database FIRST (warnings, banned players, etc.)
        try:
            from helpers import init_db
            print("🔄 Starting main bot database initialization...")
            init_db()
            print("✅ Main bot database initialized successfully")
            
            # Verify tables were created
            import sqlite3
            conn = sqlite3.connect("discord_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            print(f"📊 Database tables created: {', '.join(tables)}")
            
        except Exception as e:
            print(f"❌ Main bot database initialization failed: {e}")
            import traceback
            traceback.print_exc()
            # Try to continue anyway
        
        # Initialize SQLite database for channel monitoring
        try:
            from channel_guild_monitoring import init_channel_monitoring_db
            init_channel_monitoring_db()
            print("✅ SQLite database initialized for channel monitoring")
        except Exception as e:
            print(f"❌ Channel monitoring database initialization failed: {e}")
        
        # Initialize clan monitoring database
        try:
            from clan_monitoring import init_monitoring_db
            print("🔄 Starting clan monitoring database initialization...")
            init_monitoring_db()
            print("✅ Clan monitoring database initialized")
            
            # Verify clan monitoring tables were created
            import sqlite3
            import os
            from pathlib import Path
            clan_db_path = Path(__file__).parent / "clan_monitoring.db"
            if os.path.exists(clan_db_path):
                conn = sqlite3.connect(str(clan_db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                conn.close()
                print(f"📊 Clan monitoring tables created: {', '.join(tables)}")
            else:
                print("❌ Clan monitoring database file not created")
                
        except Exception as e:
            print(f"❌ Clan monitoring database initialization failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Load cogs from commands folder
        await self.load_cog('commands.commander_commands')
        await self.load_cog('commands.channel_commands')
        await self.load_cog('commands.cleanup_commands')
        await self.load_cog('commands.utility_commands')
        await self.load_cog('commands.reconcile_bot')
        await self.load_cog('commands.guild_monitoring')  # Free Fire Guild Monitoring
        await self.load_cog('commands.moderation_commands')  # Load after guild_monitoring
        await self.load_cog('cogs.token_management')  # Token management commands
        
        # Sync commands (guild-specific if configured, otherwise global)
        if GUILD_ID:
            guild_obj = discord.Object(id=int(GUILD_ID))
            await self.tree.sync(guild=guild_obj)
            print(f"✅ Synced {len(self.tree._get_all_commands())} commands to guild {GUILD_ID}")
        else:
            await self.tree.sync()
            print(f"✅ Synced {len(self.tree._get_all_commands())} commands globally")

        # Start background clan monitoring if configured
        # NOTE: Clan monitoring now handled by GuildMonitoringCog in commands/guild_monitoring.py
        # The new system includes banned player alerts and per-channel service configuration
        try:
            # setup_clan_monitoring(self)  # DISABLED - using new GuildMonitoringCog
            print("✅ Clan monitoring setup completed (using new GuildMonitoringCog)")
        except Exception as e:
            print(f"⚠️ Failed to start clan monitoring: {e}")

        # Print command list for debug
        all_names = [cmd.name for cmd in self.tree.walk_commands()]
        print("🧩 Registered slash commands:", ", ".join(sorted(all_names)))

    async def load_cog(self, cog_name):
        """Load a cog with error handling"""
        try:
            await self.load_extension(cog_name)
            print(f"✅ Loaded {cog_name}")
        except Exception as e:
            print(f"❌ Failed to load {cog_name}: {e}")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"✅ Bot is ready. Logged in as {bot.user}")
    print(f"🎮 Active in {len(bot.guilds)} server(s)")
    
    # Leave any servers that aren't the allowed guild
    for guild in bot.guilds:
        if guild.id != ALLOWED_GUILD_ID:
            print(f"⚠️  Leaving unauthorized server: {guild.name} (ID: {guild.id})")
            await guild.leave()

@bot.event
async def on_guild_join(guild):
    """Leave immediately if bot joins any server other than the allowed one"""
    if guild.id != ALLOWED_GUILD_ID:
        print(f"⚠️  Joined unauthorized server: {guild.name} (ID: {guild.id}) - Leaving immediately")
        await guild.leave()
    else:
        print(f"✅ Joined authorized server: {guild.name} (ID: {guild.id})")

@bot.event
async def on_error(event, *args, **kwargs):
    """Handle bot errors"""
    print(f"❌ Error in {event}: {args} {kwargs}")

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error):
    # Keep app command errors from crashing the bot and provide debug output.
    if isinstance(error, discord.NotFound):
        print("⚠️ App command failed: interaction not found (likely timed out).")
        return
    if isinstance(error, discord.HTTPException) and getattr(error, 'code', None) == 40060:
        print("⚠️ App command failed: interaction already acknowledged.")
        return
    print(f"❌ App command error: {error}")
    try:
        from helpers import safe_send
        await safe_send(interaction, "An error occurred while processing your command. Please try again later.", ephemeral=True)
    except Exception:
        pass


def main():
    """Start the bot"""
    if not TOKEN:
        print("❌ ERROR: TOKEN environment variable not set!")
        print("   Please set TOKEN in your .env file")
        return
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Bot crashed: {e}")

if __name__ == "__main__":
    main()
