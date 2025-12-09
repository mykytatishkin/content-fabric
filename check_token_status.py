#!/usr/bin/env python3
"""
Check the actual token status in the database for all channels.
This helps diagnose why tokens are marked as expired.
"""

import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.database.mysql_db import get_mysql_database
from core.utils.logger import get_logger

logger = get_logger("check_token_status")


def main():
    """Check token status for all channels."""
    print("\n" + "=" * 80)
    print("Token Status Check")
    print("=" * 80 + "\n")
    
    db = get_mysql_database()
    if not db:
        print("❌ Failed to connect to database")
        return 1
    
    channels = db.get_all_channels(enabled_only=True)
    
    if not channels:
        print("No channels found")
        return 0
    
    print(f"Checking {len(channels)} channel(s)...\n")
    
    now = datetime.now()
    
    # Categories
    expired_by_date = []
    expired_by_null = []
    valid_tokens = []
    no_token = []
    
    for channel in channels:
        has_access_token = bool(channel.access_token)
        has_refresh_token = bool(channel.refresh_token)
        expires_at = channel.token_expires_at
        
        if not has_access_token:
            no_token.append(channel)
            continue
        
        if expires_at is None:
            expired_by_null.append(channel)
        elif now >= expires_at:
            expired_by_date.append(channel)
        else:
            valid_tokens.append(channel)
    
    # Print results
    print("📊 Token Status Summary:")
    print("-" * 80)
    print(f"✅ Valid tokens: {len(valid_tokens)}")
    print(f"❌ Expired (by date): {len(expired_by_date)}")
    print(f"⚠️  Expired (no expiry date): {len(expired_by_null)}")
    print(f"🚫 No access token: {len(no_token)}")
    print()
    
    if expired_by_null:
        print("⚠️  Channels with tokens but NO expiry date (marked as expired):")
        print("-" * 80)
        for ch in expired_by_null:
            print(f"   - {ch.name}")
            print(f"     Access Token: {'Yes' if ch.access_token else 'No'}")
            print(f"     Refresh Token: {'Yes' if ch.refresh_token else 'No'}")
            print(f"     Expires At: NULL")
            print(f"     Updated At: {ch.updated_at}")
            print()
    
    if expired_by_date:
        print("❌ Channels with tokens expired by date:")
        print("-" * 80)
        for ch in expired_by_date:
            time_since = now - ch.token_expires_at
            print(f"   - {ch.name}")
            print(f"     Expired: {time_since.days} day(s) ago")
            print(f"     Expires At: {ch.token_expires_at}")
            print()
    
    if valid_tokens:
        print("✅ Channels with valid tokens:")
        print("-" * 80)
        for ch in valid_tokens:
            time_until = ch.token_expires_at - now
            days = time_until.days
            hours = time_until.seconds // 3600
            print(f"   - {ch.name}")
            print(f"     Expires in: {days} day(s), {hours} hour(s)")
            print(f"     Expires At: {ch.token_expires_at}")
            print()
    
    if no_token:
        print("🚫 Channels without access tokens:")
        print("-" * 80)
        for ch in no_token:
            print(f"   - {ch.name}")
            print()
    
    # Check what is_token_expired returns
    print("\n" + "=" * 80)
    print("is_token_expired() Results:")
    print("=" * 80 + "\n")
    
    expired_count = 0
    for channel in channels:
        is_expired = db.is_token_expired(channel.name)
        if is_expired:
            expired_count += 1
            status = "❌ EXPIRED"
        else:
            status = "✅ VALID"
        
        expires_info = f"Expires: {channel.token_expires_at}" if channel.token_expires_at else "No expiry date"
        print(f"{status} - {channel.name} ({expires_info})")
    
    print(f"\nTotal marked as expired by is_token_expired(): {expired_count}/{len(channels)}")
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        logger.exception("Unexpected error")
        sys.exit(1)

