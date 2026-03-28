"""Discord Bot - Main Entry Point"""
import discord
from discord import app_commands
from discord.ext import commands
import os
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TOKEN = os.getenv("TOKEN")

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.ID_RE = re.compile(r"\b(\d{6,20})\b")

    async def setup_hook(self):
        """Load all command cogs at startup"""
        # Load cogs from commands folder
        await self.load_cog('commands.member_commands')
        await self.load_cog('commands.commander_commands')
        await self.load_cog('commands.channel_commands')
        await self.load_cog('commands.moderation_commands')
        await self.load_cog('commands.cleanup_commands')
        await self.load_cog('commands.utility_commands')
        
        # Sync commands
        await self.tree.sync()
        print(f"✅ Synced {len(self.tree._get_all_commands())} commands")

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
    print(f"🎮 Active in {len(bot.guilds)} guild(s)")

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
