#!/usr/bin/env python3
"""
Add Group to Broadcast - додати групу до розсилки
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.utils.telegram_broadcast import TelegramBroadcast

def main():
    print("🤖 Add Group to Daily Reports")
    print("="*40)
    
    broadcaster = TelegramBroadcast()
    
    # Show current subscribers
    subscribers = broadcaster.get_subscribers()
    print(f"📊 Current subscribers: {len(subscribers)}")
    
    if subscribers:
        for i, chat_id in enumerate(subscribers, 1):
            chat_type = "👤 User" if chat_id > 0 else "👥 Group"
            print(f"  {i}. {chat_id} ({chat_type})")
    
    print("\n📋 How to get Group ID:")
    print("1. Add bot to your group")
    print("2. Send any message in the group")
    print("3. Forward that message to @userinfobot")
    print("4. Copy the 'Chat ID' (negative number like -1001234567890)")
    
    try:
        group_id = input("\n🔢 Enter Group ID (negative number): ").strip()
        
        if not group_id:
            print("❌ No Group ID provided")
            return
        
        try:
            group_id_int = int(group_id)
        except ValueError:
            print("❌ Invalid format. Should be a number like -1001234567890")
            return
        
        # Add group to subscribers
        if broadcaster.add_subscriber(group_id_int):
            print(f"✅ Group {group_id_int} added successfully!")
            
            # Test message
            test_msg = "🎉 **Group Added!**\n\nThis group will now receive daily reports at 12:00 PM (Kyiv time)."
            result = broadcaster.broadcast_message(test_msg)
            
            if result['success'] > 0:
                print("✅ Test message sent successfully!")
            else:
                print(f"❌ Failed to send test message: {result}")
        else:
            print(f"ℹ️ Group {group_id_int} was already subscribed")
            
    except KeyboardInterrupt:
        print("\n🛑 Cancelled")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
