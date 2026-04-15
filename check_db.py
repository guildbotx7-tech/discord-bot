import sqlite3
import os

db_path = 'discord_bot.db'
print('Database exists:', os.path.exists(db_path))

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
    tables = cursor.fetchall()
    print('Current tables:', [t[0] for t in tables])

    # Check for specific tables
    table_names = [t[0] for t in tables]
    missing_tables = []
    if 'banned_players' not in table_names:
        missing_tables.append('banned_players')
    if 'monitored_players' not in table_names:
        missing_tables.append('monitored_players')
    if 'channel_guilds' not in table_names:
        missing_tables.append('channel_guilds')

    if missing_tables:
        print('Missing tables:', missing_tables)
    else:
        print('All required tables exist')

    # Check channel_guilds columns
    if 'channel_guilds' in table_names:
        cursor.execute('PRAGMA table_info(channel_guilds)')
        columns = cursor.fetchall()
        column_names = [c[1] for c in columns]
        print('channel_guilds columns:', column_names)
        if 'player_monitoring_enabled' not in column_names:
            print('Missing column: player_monitoring_enabled')

    conn.close()
else:
    print('Database does not exist')