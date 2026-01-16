#!/usr/bin/env python3
"""
Check token expiry status for all YouTube channels.
Shows when tokens expire and which ones are expiring soon.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.database.mysql_db import get_mysql_database
from core.utils.logger import get_logger

LOGGER = get_logger("check_token_expiry")


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


def format_time_until_expiry(expires_at: datetime, now: datetime) -> str:
    """Format time until expiry in a human-readable way."""
    delta = expires_at - now
    
    if delta.total_seconds() < 0:
        # Already expired
        abs_delta = abs(delta)
        if abs_delta.days > 0:
            return f"⚠️  Expired {abs_delta.days} day(s) ago"
        hours = abs_delta.total_seconds() / 3600
        if hours >= 1:
            return f"⚠️  Expired {int(hours)} hour(s) ago"
        minutes = abs_delta.total_seconds() / 60
        return f"⚠️  Expired {int(minutes)} minute(s) ago"
    
    # Not expired yet
    if delta.days > 0:
        return f"✅ {delta.days} day(s) remaining"
    hours = delta.total_seconds() / 3600
    if hours >= 1:
        return f"✅ {int(hours)} hour(s) remaining"
    minutes = delta.total_seconds() / 60
    return f"✅ {int(minutes)} minute(s) remaining"


def check_token_expiry(days_ahead: int = 3, enabled_only: bool = True) -> None:
    """Check token expiry status for all channels."""
    mysql_config = load_mysql_config()
    db = get_mysql_database(config=mysql_config)
    
    print("=" * 80)
    print("Token Expiry Status for YouTube Channels")
    print("=" * 80)
    print()
    
    # Get all channels
    channels = db.get_all_channels(enabled_only=enabled_only)
    
    if not channels:
        print("No channels found in database.")
        return
    
    print(f"Checking {len(channels)} channel(s)...\n")
    
    now = datetime.now()
    threshold = now + timedelta(days=days_ahead)
    
    expired_channels = []
    expiring_soon_channels = []
    valid_channels = []
    no_expiry_info = []
    
    # Sort channels by expiry date
    channels_with_expiry = []
    channels_without_expiry = []
    
    for channel in channels:
        if not channel.token_expires_at:
            channels_without_expiry.append(channel)
            continue
        
        # Normalize timezone
        expires_at = channel.token_expires_at
        if expires_at.tzinfo and now.tzinfo is None:
            now_tz = now.replace(tzinfo=expires_at.tzinfo)
        elif expires_at.tzinfo is None and now.tzinfo:
            expires_at = expires_at.replace(tzinfo=now.tzinfo)
            now_tz = now
        else:
            now_tz = now
        
        channels_with_expiry.append((channel, expires_at))
    
    # Sort by expiry date (expired first, then expiring soon)
    channels_with_expiry.sort(key=lambda x: x[1])
    
    # Display channels
    print("📺 Channels with expiry information:")
    print("-" * 80)
    
    for channel, expires_at in channels_with_expiry:
        # Normalize timezone for comparison
        if expires_at.tzinfo and now.tzinfo is None:
            now_tz = now.replace(tzinfo=expires_at.tzinfo)
        elif expires_at.tzinfo is None and now.tzinfo:
            expires_at_tz = expires_at.replace(tzinfo=now.tzinfo)
            now_tz = now
        else:
            now_tz = now
            expires_at_tz = expires_at
        
        delta = expires_at_tz - now_tz
        
        status_icon = "❌" if delta.total_seconds() < 0 else "⏰" if expires_at_tz <= threshold else "✅"
        time_str = format_time_until_expiry(expires_at_tz, now_tz)
        
        print(f"{status_icon} {channel.name}")
        print(f"   Expires: {expires_at_tz.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Status: {time_str}")
        
        if delta.total_seconds() < 0:
            expired_channels.append(channel.name)
        elif expires_at_tz <= threshold:
            expiring_soon_channels.append(channel.name)
        else:
            valid_channels.append(channel.name)
        
        print()
    
    # Display channels without expiry info
    if channels_without_expiry:
        print("⚠️  Channels without expiry information:")
        print("-" * 80)
        for channel in channels_without_expiry:
            print(f"   {channel.name}")
            no_expiry_info.append(channel.name)
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"❌ Expired tokens: {len(expired_channels)}")
    print(f"⏰ Expiring within {days_ahead} days: {len(expiring_soon_channels)}")
    print(f"✅ Valid tokens (>{days_ahead} days): {len(valid_channels)}")
    print(f"⚠️  No expiry info: {len(no_expiry_info)}")
    print(f"📊 Total: {len(channels)}")
    print()
    
    # List expired channels
    if expired_channels:
        print("❌ EXPIRED tokens (need immediate re-authentication):")
        for name in sorted(expired_channels):
            print(f"   - {name}")
        print()
    
    # List expiring soon channels
    if expiring_soon_channels:
        print(f"⏰ Expiring within {days_ahead} days (should re-authenticate soon):")
        for name in sorted(expiring_soon_channels):
            print(f"   - {name}")
        print()
    
    # Show expiring channels count
    expiring_total = len(expired_channels) + len(expiring_soon_channels)
    if expiring_total > 0:
        print(f"💡 Total channels needing re-auth: {expiring_total}")
        print(f"   Run: python3 run_youtube_reauth.py --all-expiring --redirect-port 9090")
        print()


def main() -> int:
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Check token expiry status for YouTube channels"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="Number of days ahead to consider as 'expiring soon' (default: 3)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all channels (including disabled)"
    )
    
    args = parser.parse_args()
    
    try:
        check_token_expiry(days_ahead=args.days, enabled_only=not args.all)
        return 0
    except Exception as exc:
        LOGGER.exception("Error checking token expiry: %s", exc)
        print(f"\n❌ Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

