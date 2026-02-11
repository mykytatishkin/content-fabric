#!/usr/bin/env python3
"""
Check if refresh tokens are valid by attempting to refresh them.
This script actually tests the refresh token by making an API call.
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

from core.auth.token_validator import test_refresh_token  # noqa: E402
from core.database.mysql_db import get_mysql_database
from core.utils.logger import get_logger

logger = get_logger("check_refresh_token_validity")


def main():
    """Check refresh token validity for all channels."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Check if refresh_token is valid for YouTube channels"
    )
    parser.add_argument(
        "channels",
        nargs="*",
        help="Channel name(s) to check (if not provided, checks all enabled channels)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all channels (including disabled)"
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("Refresh Token Validity Check")
    print("=" * 80 + "\n")
    
    db = get_mysql_database()
    if not db:
        print("❌ Failed to connect to database")
        return 1
    
    # Get channels
    if args.channels:
        channels = []
        for name in args.channels:
            channel = db.get_channel(name)
            if channel:
                channels.append(channel)
            else:
                print(f"❌ Channel '{name}' not found in database")
    else:
        channels = db.get_all_channels(enabled_only=not args.all)
    
    if not channels:
        print("No channels found to check.")
        return 0
    
    print(f"Checking {len(channels)} channel(s)...\n")
    
    valid_count = 0
    invalid_count = 0
    missing_count = 0
    no_credentials_count = 0
    
    results = []
    
    for channel in channels:
        print(f"📺 {channel.name}")
        print(f"   Channel ID: {channel.channel_id}")
        print(f"   Enabled: {channel.enabled}")
        
        if not channel.refresh_token:
            print(f"   ❌ No refresh_token")
            missing_count += 1
            results.append({
                'channel': channel.name,
                'valid': False,
                'status': 'missing',
                'error': 'No refresh_token'
            })
        else:
            # Test refresh_token validity
            is_valid, error_msg = test_refresh_token(channel, db)
            
            if is_valid:
                print(f"   ✅ Refresh Token: VALID")
                valid_count += 1
                results.append({
                    'channel': channel.name,
                    'valid': True,
                    'status': 'valid',
                    'error': None
                })
            else:
                print(f"   ❌ Refresh Token: INVALID")
                print(f"      Error: {error_msg}")
                invalid_count += 1
                if "No console credentials" in error_msg:
                    no_credentials_count += 1
                results.append({
                    'channel': channel.name,
                    'valid': False,
                    'status': 'invalid',
                    'error': error_msg
                })
        
        if channel.token_expires_at:
            now = datetime.now()
            if channel.token_expires_at.tzinfo:
                now = now.replace(tzinfo=channel.token_expires_at.tzinfo)
            elif now.tzinfo:
                channel.token_expires_at = channel.token_expires_at.replace(tzinfo=now.tzinfo)
            
            expires_in = (channel.token_expires_at - now).total_seconds() / 3600
            if expires_in > 0:
                print(f"   ⏰ Access Token expires in: {expires_in:.1f} hours")
            else:
                print(f"   ⚠️  Access Token expired: {abs(expires_in):.1f} hours ago")
        
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Valid refresh_tokens: {valid_count}")
    print(f"❌ Invalid refresh_tokens: {invalid_count}")
    print(f"⚠️  Missing refresh_tokens: {missing_count}")
    if no_credentials_count > 0:
        print(f"🔑 Missing console credentials: {no_credentials_count}")
    print(f"📊 Total checked: {len(channels)}")
    print()
    
    # List invalid channels
    if invalid_count > 0:
        print("❌ Channels with INVALID refresh_tokens (need re-authentication):")
        print("-" * 80)
        for result in results:
            if result['status'] == 'invalid':
                print(f"   - {result['channel']}: {result['error']}")
        print()
    
    # List missing channels
    if missing_count > 0:
        print("⚠️  Channels with MISSING refresh_tokens:")
        print("-" * 80)
        for result in results:
            if result['status'] == 'missing':
                print(f"   - {result['channel']}")
        print()
    
    if invalid_count > 0 or missing_count > 0:
        print("💡 To re-authenticate channels, run:")
        print("   python3 run_youtube_reauth.py <channel_name>")
        print("   or")
        print("   python3 run_youtube_reauth.py --all-expiring")
        print()
    
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
