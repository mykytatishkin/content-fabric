#!/usr/bin/env python3
"""
Check which channels are missing account credentials for automated reauth.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.database.mysql_db import get_mysql_database
from core.utils.logger import get_logger

LOGGER = get_logger("check_missing_credentials")


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


def check_missing_credentials(enabled_only: bool = True) -> None:
    """Check which channels are missing account credentials."""
    mysql_config = load_mysql_config()
    db = get_mysql_database(config=mysql_config)
    
    print("=" * 80)
    print("Checking Missing Account Credentials for YouTube Channels")
    print("=" * 80)
    print()
    
    # Get all channels
    channels = db.get_all_channels(enabled_only=enabled_only)
    
    if not channels:
        print("No channels found in database.")
        return
    
    print(f"Found {len(channels)} channel(s) in database\n")
    
    channels_with_creds = []
    channels_without_creds = []
    
    for channel in channels:
        creds = db.get_account_credentials(channel.name, include_disabled=True)
        if creds:
            channels_with_creds.append(channel.name)
        else:
            channels_without_creds.append(channel.name)
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Channels WITH credentials: {len(channels_with_creds)}")
    print(f"❌ Channels WITHOUT credentials: {len(channels_without_creds)}")
    print()
    
    if channels_with_creds:
        print("✅ Channels with credentials configured:")
        for name in sorted(channels_with_creds):
            creds = db.get_account_credentials(name, include_disabled=True)
            status = "enabled" if creds.enabled else "disabled"
            print(f"   - {name} ({status})")
        print()
    
    if channels_without_creds:
        print("❌ Channels MISSING credentials (need to be added):")
        for name in sorted(channels_without_creds):
            print(f"   - {name}")
        print()
        print("💡 To add credentials for these channels, use:")
        print("   python3 -c \"")
        print("   from core.database.mysql_db import get_mysql_database;")
        print("   db = get_mysql_database();")
        print("   db.upsert_account_credentials(")
        print("       channel_name='CHANNEL_NAME',")
        print("       login_email='email@gmail.com',")
        print("       login_password='password'")
        print("   )\"")
        print()
        print("   Or use the interactive script:")
        print("   python3 scripts/add_account_credentials.py")


def main() -> int:
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Check which channels are missing account credentials"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all channels (including disabled)"
    )
    
    args = parser.parse_args()
    
    try:
        check_missing_credentials(enabled_only=not args.all)
        return 0
    except Exception as exc:
        LOGGER.exception("Error checking missing credentials: %s", exc)
        print(f"\n❌ Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

