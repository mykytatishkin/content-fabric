#!/usr/bin/env python3
"""
Check the refresh token status in the database for all channels.
This helps diagnose which channels have refresh tokens available.
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
    """Check refresh token status for all channels."""
    print("\n" + "=" * 80)
    print("Refresh Token Status Check")
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
    valid_tokens = []
    no_token = []
    
    for channel in channels:
        has_refresh_token = bool(channel.refresh_token)
        
        if not has_refresh_token:
            no_token.append(channel)
            continue
        
        # Refresh tokens typically don't expire, so we just check if they exist
        valid_tokens.append(channel)
    
    # Print results
    print("📊 Refresh Token Status Summary:")
    print("-" * 80)
    print(f"✅ Valid refresh tokens: {len(valid_tokens)}")
    print(f"🚫 No refresh token: {len(no_token)}")
    print()
    
    if valid_tokens:
        print("✅ Channels with refresh tokens:")
        print("-" * 80)
        for ch in valid_tokens:
            print(f"   - {ch.name}")
            print(f"     Refresh Token: {'Yes' if ch.refresh_token else 'No'}")
            print(f"     Access Token: {'Yes' if ch.access_token else 'No'}")
            if ch.token_expires_at:
                time_until = ch.token_expires_at - now
                days = time_until.days
                hours = time_until.seconds // 3600
                if time_until.total_seconds() > 0:
                    print(f"     Access Token expires in: {days} day(s), {hours} hour(s)")
                else:
                    time_since = now - ch.token_expires_at
                    print(f"     Access Token expired: {time_since.days} day(s) ago")
                print(f"     Access Token Expires At: {ch.token_expires_at}")
            else:
                print("     Access Token Expires At: NULL")
            print(f"     Updated At: {ch.updated_at}")
            print()
    
    if no_token:
        print("🚫 Channels without refresh tokens:")
        print("-" * 80)
        for ch in no_token:
            print(f"   - {ch.name}")
            print("     Refresh Token: No")
            print(f"     Access Token: {'Yes' if ch.access_token else 'No'}")
            print()
    
    # Check refresh token status for each channel
    print("\n" + "=" * 80)
    print("Refresh Token Status Details:")
    print("=" * 80 + "\n")
    
    for channel in channels:
        has_refresh = bool(channel.refresh_token)
        has_access = bool(channel.access_token)
        
        if has_refresh:
            status = "✅ HAS REFRESH TOKEN"
        else:
            status = "❌ NO REFRESH TOKEN"
        
        access_info = "Has access token" if has_access else "No access token"
        expires_info = f"Access expires: {channel.token_expires_at}" if channel.token_expires_at else "No access expiry date"
        print(f"{status} - {channel.name} ({access_info}, {expires_info})")
    
    refresh_count = len([c for c in channels if c.refresh_token])
    print(f"\nTotal channels with refresh tokens: {refresh_count}/{len(channels)}")
    
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

