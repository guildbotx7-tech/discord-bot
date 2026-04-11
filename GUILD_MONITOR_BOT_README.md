# Free Fire Guild Monitoring Bot

A standalone Discord bot that monitors Free Fire guild membership changes and notifies your Discord server about joins and leaves.

## Features

- 🔍 **Real-time Monitoring**: Checks guild membership every 10 minutes
- 📊 **Change Tracking**: Logs all joins and leaves with timestamps
- 🔔 **Discord Notifications**: Sends alerts to your configured channel
- 🔒 **Secure Token Management**: Owner-only token management with environment variables
- 📈 **Statistics**: View membership statistics and recent changes
- 👥 **Admin Commands**: Administrator-only access to monitoring data

## Setup Instructions

### 1. Environment Setup

The bot requires two environment variables:

```bash
# Create or update your .env file
GUILD_MONITOR_BOT_TOKEN=your_discord_bot_token_here
GUILD_ACCESS_TOKEN=6a55070c747ba28f36e7e7e3697ccc91407f0b1a56aeb41678568b0eec65082162d7cdf2de74f500f93b8afaf0cd81e5ae88de052f07d9f823935ab291a7bbbc59106abc6a19b7297910700c2f0c7571
```

### 2. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the bot token and add it to your `.env` file as `GUILD_MONITOR_BOT_TOKEN`
5. Enable these intents:
   - Message Content Intent
6. Invite the bot to your server with these permissions:
   - Send Messages
   - Use Slash Commands
   - Embed Links
   - Read Message History

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Bot

```bash
python guild_monitor_bot.py
```

## Bot Commands

### Owner-Only Commands (Bot Owner Only)

- `!register_token [channel]`: Register the guild monitoring token
  - `channel`: Optional notification channel (uses current if not specified)
- `!token_status`: Check if token is configured
- `!test_monitoring`: Test the monitoring system

### Admin Commands (Server Administrators)

- `!guild_changes [limit]`: Show recent membership changes
  - `limit`: Number of changes to show (default: 20, max: 100)
- `!guild_joins [limit]`: Show recent joins
- `!guild_leaves [limit]`: Show recent leaves
- `!guild_stats`: Show membership statistics

### Aliases

- `!gc` → `!guild_changes`
- `!guild_history` → `!guild_changes`

## Usage Examples

### Initial Setup (Bot Owner)

1. **Register Token**:
   ```
   !register_token #guild-announcements
   ```
   This will:
   - Verify the API token works
   - Start monitoring automatically
   - Set notifications to the specified channel

2. **Test Monitoring**:
   ```
   !test_monitoring
   ```
   Performs a one-time check to ensure everything works.

### Viewing Changes (Administrators)

1. **Recent Changes**:
   ```
   !guild_changes 50
   ```
   Shows the last 50 membership changes.

2. **Recent Joins**:
   ```
   !guild_joins 20
   ```
   Shows the last 20 people who joined.

3. **Statistics**:
   ```
   !guild_stats
   ```
   Shows total joins, leaves, and net change.

## Security Features

- **Token Security**: API tokens are never displayed or logged
- **Owner-Only Access**: Only the bot owner can manage tokens
- **Environment Variables**: Sensitive data stored securely
- **Permission Checks**: Commands require appropriate permissions

## Database

The bot uses a SQLite database (`guild_monitor_bot.db`) to store:
- Membership change history
- Guild configuration
- Monitoring metadata

## Monitoring Details

- **Frequency**: Every 10 minutes
- **API Endpoint**: `http://controle.thug4ff.xyz/memberClan`
- **Data Tracked**: Player UIDs, nicknames, join/leave events
- **Notifications**: Automatic alerts for membership changes

## Troubleshooting

### Bot Won't Start
- Check that `GUILD_MONITOR_BOT_TOKEN` is set in `.env`
- Verify the bot token is correct
- Ensure all dependencies are installed

### Token Registration Fails
- Verify `GUILD_ACCESS_TOKEN` is set correctly
- Check that the API token is valid
- Ensure you have bot owner permissions

### No Notifications
- Confirm the token is registered with `!token_status`
- Check that the bot has permission to send messages in the channel
- Verify the monitoring task is running (check bot logs)

### Commands Not Working
- Ensure you have the required permissions (admin for most commands)
- Check that the bot is online and responsive
- Use `!help` to see available commands

## File Structure

```
discord-bot/
├── guild_monitor_bot.py          # Main bot file
├── guild_monitor_task.py         # Background monitoring task
├── guild_monitoring.py           # Core monitoring logic
├── member_guild_api.py           # Free Fire API interface
├── token_manager.py              # Token management utilities
├── cogs/
│   ├── guild_monitoring_commands.py  # Discord commands
│   └── token_management.py           # Token management commands
├── tests/                         # Test files
├── .env                           # Environment variables
└── requirements.txt               # Python dependencies
```

## Support

If you encounter issues:
1. Check the bot logs for error messages
2. Verify your environment variables are set correctly
3. Test individual components with the provided test files
4. Ensure your Discord bot has the correct permissions

## License

This project is provided as-is for educational and personal use.