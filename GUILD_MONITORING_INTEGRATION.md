# Free Fire Guild Monitoring - Integrated

This integration adds Free Fire guild monitoring capabilities to your existing Discord bot. Each channel can monitor a different Free Fire guild.

## Features Added

- **Channel-based Guild Monitoring**: Each Discord channel can monitor one Free Fire guild
- **Automatic Notifications**: Get notified when players join/leave guilds
- **Member Management**: View current guild members
- **Change History**: Track membership changes over time
- **Ban System**: Log banned players (local tracking)
- **Global Bans**: Ban players across all monitored guilds

## Setup

### 1. Environment Variables

Add to your `.env` file:
```bash
GUILD_ACCESS_TOKEN=your_free_fire_api_token_here
```

### 2. Bot Integration

The guild monitoring is automatically loaded when you start your bot. No additional setup required.

## Commands Added

### Commander-Only Commands

- `/register_guild <guild_id>` - Register a Free Fire guild for monitoring in the current channel
- `/ban_player <uid> [reason]` - Ban a player from the guild (logs the action)
- `/global_ban <uid> [reason]` - Ban a player across all monitored guilds

### Public Commands

- `/guild_status` - Check if the current channel has a registered guild
- `/guild_members` - View current members of the monitored guild with guild ID, name, and member count
- `/guild_changes [limit] [csv_export]` - View all current guild members with detailed data (default: 20 per page, max: 50, optional CSV export)

## How It Works

### Channel = Guild
- Each Discord channel represents one Free Fire guild
- Register a guild ID for each channel you want to monitor
- The bot will check each registered channel every 10 minutes

### Notifications
- When players join/leave, the bot sends notifications to that channel
- Notifications include player names and UIDs
- Limited to 5 players per notification to avoid spam

### Data Storage
- Uses SQLite database (`guild_monitor_bot.db`)
- Stores membership snapshots, change history, and member cache
- Separate tables for each channel's data

## Usage Examples

### Setting Up Monitoring

1. **Register a Guild**:
   ```
   /register_guild guild_id: 12345678901234567890
   ```
   This registers the Free Fire guild for monitoring in the current channel.

2. **Check Status**:
   ```
   /guild_status
   ```
   Shows if monitoring is active for this channel.

### Viewing Data

1. **See Current Members**:
   ```
   /guild_members
   ```
   Lists all current guild members with their UIDs.

2. **View Recent Changes**:
   ```
   /guild_changes limit: 30
   ```
   Shows the last 30 join/leave events.

### Managing Players

1. **Ban a Player**:
   ```
   /ban_player uid: 1234567890 reason: Cheating
   ```
   Logs the ban action (doesn't actually ban via API).

2. **Global Ban**:
   ```
   /global_ban uid: 1234567890 reason: Toxic behavior
   ```
   Bans the player across all monitored guilds.

## Database Schema

### channel_guilds
- `channel_id` - Discord channel ID
- `guild_id` - Free Fire guild ID
- `registered_by` - Discord user who registered it
- `registered_at` - Registration timestamp

### channel_snapshots
- `channel_id` - Discord channel ID
- `guild_id` - Free Fire guild ID
- `member_uids` - JSON array of current member UIDs
- `snapshot_at` - When the snapshot was taken

### channel_changes
- `channel_id` - Discord channel ID
- `guild_id` - Free Fire guild ID
- `uid` - Player UID
- `change_type` - "joined" or "left"
- `nickname` - Player nickname
- `timestamp` - When the change occurred

### member_cache
- `uid` - Player UID
- `data` - JSON member data from API
- `cached_at` - Cache timestamp

## Security Notes

- Only Commanders can register guilds and ban players
- API tokens are stored as environment variables only
- Player data is cached locally for performance
- All actions are logged via your existing logging system

## Troubleshooting

### No Notifications
- Check that the channel has a registered guild with `/guild_status`
- Verify `GUILD_ACCESS_TOKEN` is set in `.env`
- Ensure the bot has permission to send messages in the channel

### API Errors
- Verify the guild ID is correct
- Check that the API token is valid
- Look at bot logs for detailed error messages

### Commands Not Working
- Ensure you're using slash commands (they start with `/`)
- Check that you have Commander permissions for restricted commands
- Verify the bot is online and responsive

## Integration Benefits

- **Seamless**: Works with your existing bot and permission system
- **Flexible**: One channel = one guild, unlimited channels
- **Automatic**: Background monitoring with notifications
- **Historical**: Track changes over time
- **Management**: Built-in ban tracking and member viewing

The integration is now complete and ready to use!