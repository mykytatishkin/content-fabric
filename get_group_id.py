#!/usr/bin/env python3
"""
Get Group ID from bot interactions
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.utils.telegram_broadcast import TelegramBroadcast

def main():
    print("🔍 Get Group ID from Bot Interactions")
    print("="*50)
    
    broadcaster = TelegramBroadcast()
    
    print("📋 Steps:")
    print("1. Add your bot to the group")
    print("2. Send any message to the bot in the group")
    print("3. Run this script to see the group ID")
    print()
    
    # Get updates to see recent interactions
    updates = broadcaster.get_updates()
    
    if not updates:
        print("❌ No recent interactions found")
        print("👉 Make sure someone sent a message to the bot in the group")
        return
    
    print("📊 Recent interactions:")
    for i, update in enumerate(updates, 1):
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            chat_type = message['chat']['type']
            text = message.get('text', '')
            
            chat_type_emoji = "👤" if chat_id > 0 else "👥"
            print(f"  {i}. {chat_id} ({chat_type_emoji} {chat_type}) - '{text[:50]}...'")
    
    print("\n💡 Look for negative numbers - those are group IDs")
    print("💡 Copy the group ID and use it with add_group.py")

if __name__ == "__main__":
    main()
