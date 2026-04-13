#!/usr/bin/env python3
"""Test IST timezone conversion"""

import reconcile_bot
import channel_guild_monitoring
import clan_monitoring
import guild_monitoring
from helpers import get_ist_now, get_ist_timestamp

print('✅ All modules import successfully with IST timezone')
print(f'Current IST Time: {get_ist_now().strftime("%Y-%m-%d %H:%M:%S")} IST')
print(f'Current IST Timestamp: {get_ist_timestamp()}')
