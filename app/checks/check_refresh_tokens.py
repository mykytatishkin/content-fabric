#!/usr/bin/env python3
"""
Script to check refresh_token values for YouTube channels.
Useful for verifying that reauthorization updated the tokens.
"""

from __future__ import annotations

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from core.database.mysql_db import get_mysql_database
from core.utils.logger import get_logger

LOGGER = get_logger("check_refresh_tokens")


def load_mysql_config() -> dict:
    """Load MySQL configuration from environment variables."""
    return {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'database': os.getenv('MYSQL_DATABASE', 'content_fabric'),
        'user': os.getenv('MYSQL_USER', 'content_fabric_user'),
        'password': os.getenv('MYSQL_PASSWORD', ''),
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci',
        'autocommit': True
    }


def check_refresh_tokens(channel_names: list[str]) -> None:
    """Check and display refresh_token information for specified channels."""
    mysql_config = load_mysql_config()
    db = get_mysql_database(config=mysql_config)
    
    print("=" * 72)
    print("Checking Refresh Tokens for YouTube Channels")
    print("=" * 72)
    print()
    
    for channel_name in channel_names:
        channel = db.get_channel(channel_name)
        
        if not channel:
            print(f"❌ Channel '{channel_name}' not found in database")
            continue
        
        print(f"📺 Channel: {channel_name}")
        print(f"   Channel ID: {channel.channel_id}")
        print(f"   Enabled: {channel.enabled}")
        
        if channel.refresh_token:
            # Show first and last 10 characters of token for verification
            token_preview = (
                channel.refresh_token[:10] + 
                "..." + 
                channel.refresh_token[-10:] if len(channel.refresh_token) > 20 
                else channel.refresh_token
            )
            print(f"   ✅ Refresh Token: {token_preview}")
            print(f"   Token Length: {len(channel.refresh_token)} characters")
        else:
            print(f"   ❌ No refresh_token found")
        
        if channel.access_token:
            token_preview = (
                channel.access_token[:10] + 
                "..." + 
                channel.access_token[-10:] if len(channel.access_token) > 20 
                else channel.access_token
            )
            print(f"   ✅ Access Token: {token_preview}")
        else:
            print(f"   ❌ No access_token found")
        
        if channel.token_expires_at:
            print(f"   Token Expires At: {channel.token_expires_at}")
        else:
            print(f"   ⚠️  No expiration date set")
        
        print(f"   Updated At: {channel.updated_at}")
        print()


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 check_refresh_tokens.py <channel1> [channel2] [channel3] ...")
        print("\nExample:")
        print('  python3 check_refresh_tokens.py "Andrew Garle" "Ютуб5.0" "Ютуб 6.0"')
        return 1
    
    channel_names = sys.argv[1:]
    
    try:
        check_refresh_tokens(channel_names)
        return 0
    except Exception as exc:
        LOGGER.exception("Error checking refresh tokens: %s", exc)
        print(f"\n❌ Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

