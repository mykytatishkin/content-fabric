#!/usr/bin/env python3
"""
Check if refresh tokens were updated after re-authentication.
Shows which channels have refresh tokens and when they were last updated.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.database.mysql_db import get_mysql_database
from core.utils.logger import get_logger

logger = get_logger("check_reauth_results")


def main():
    """Check refresh token update status after re-authentication."""
    print("\n" + "=" * 80)
    print("Refresh Token Update Status (After Re-authentication)")
    print("=" * 80 + "\n")
    
    db = get_mysql_database()
    if not db:
        print("❌ Failed to connect to database")
        return 1
    
    channels = db.get_all_channels(enabled_only=False)
    
    if not channels:
        print("No channels found")
        return 0
    
    print(f"Checking {len(channels)} channel(s)...\n")
    
    now = datetime.now()
    recent_threshold = timedelta(hours=24)  # Consider "recent" if updated within 24 hours
    
    # Categories
    has_refresh_token = []
    no_refresh_token = []
    recently_updated = []
    old_tokens = []
    
    for channel in channels:
        has_refresh = bool(channel.refresh_token)
        has_access = bool(channel.access_token)
        
        if not has_refresh:
            no_refresh_token.append(channel)
            continue
        
        has_refresh_token.append(channel)
        
        # Check when token was last updated
        if channel.updated_at:
            time_since_update = now - channel.updated_at.replace(tzinfo=None) if channel.updated_at.tzinfo else now - channel.updated_at
            
            if time_since_update <= recent_threshold:
                recently_updated.append((channel, time_since_update))
            else:
                old_tokens.append((channel, time_since_update))
        else:
            old_tokens.append((channel, None))
    
    # Print summary
    print("📊 Refresh Token Update Summary:")
    print("-" * 80)
    print(f"✅ Channels with refresh tokens: {len(has_refresh_token)}")
    print(f"🔄 Recently updated (last 24h): {len(recently_updated)}")
    print(f"⏰ Old tokens (>24h): {len(old_tokens)}")
    print(f"🚫 No refresh token: {len(no_refresh_token)}")
    print()
    
    # Show recently updated channels
    if recently_updated:
        print("🔄 Recently Updated Channels (last 24 hours):")
        print("-" * 80)
        for channel, time_since in recently_updated:
            hours = int(time_since.total_seconds() // 3600)
            minutes = int((time_since.total_seconds() % 3600) // 60)
            
            token_preview = (
                channel.refresh_token[:10] + 
                "..." + 
                channel.refresh_token[-10:] if len(channel.refresh_token) > 20 
                else channel.refresh_token
            )
            
            print(f"   ✅ {channel.name}")
            print(f"      Refresh Token: {token_preview}")
            print(f"      Updated: {hours}h {minutes}m ago ({channel.updated_at})")
            print(f"      Enabled: {channel.enabled}")
            if channel.token_expires_at:
                expires_in = channel.token_expires_at - now.replace(tzinfo=channel.token_expires_at.tzinfo) if channel.token_expires_at.tzinfo else channel.token_expires_at - now
                if expires_in.total_seconds() > 0:
                    print(f"      Access Token expires in: {int(expires_in.total_seconds() // 3600)}h")
                else:
                    print(f"      ⚠️  Access Token expired")
            print()
    
    # Show channels with old tokens
    if old_tokens:
        print("⏰ Channels with Old Tokens (>24 hours):")
        print("-" * 80)
        for channel, time_since in old_tokens[:10]:  # Show first 10
            if time_since:
                days = time_since.days
                hours = int((time_since.total_seconds() % 86400) // 3600)
                time_str = f"{days}d {hours}h ago"
            else:
                time_str = "Unknown"
            
            token_preview = (
                channel.refresh_token[:10] + 
                "..." + 
                channel.refresh_token[-10:] if len(channel.refresh_token) > 20 
                else channel.refresh_token
            )
            
            print(f"   ⏰ {channel.name}")
            print(f"      Refresh Token: {token_preview}")
            print(f"      Last Updated: {time_str} ({channel.updated_at})")
            print(f"      Enabled: {channel.enabled}")
            print()
        
        if len(old_tokens) > 10:
            print(f"   ... and {len(old_tokens) - 10} more channels")
            print()
    
    # Show channels without refresh tokens
    if no_refresh_token:
        print("🚫 Channels WITHOUT Refresh Tokens:")
        print("-" * 80)
        for channel in no_refresh_token[:10]:  # Show first 10
            print(f"   ❌ {channel.name}")
            print(f"      Enabled: {channel.enabled}")
            print(f"      Access Token: {'Yes' if channel.access_token else 'No'}")
            print(f"      Last Updated: {channel.updated_at}")
            print()
        
        if len(no_refresh_token) > 10:
            print(f"   ... and {len(no_refresh_token) - 10} more channels")
            print()
    
    # Recommendations
    print("\n" + "=" * 80)
    print("💡 Recommendations:")
    print("=" * 80)
    
    if no_refresh_token:
        print(f"⚠️  {len(no_refresh_token)} channel(s) need re-authentication:")
        for ch in no_refresh_token[:5]:
            print(f"   - {ch.name}")
        if len(no_refresh_token) > 5:
            print(f"   ... and {len(no_refresh_token) - 5} more")
        print("\n   Run: python3 scripts/youtube_reauth_service.py <channel_name>")
        print()
    
    if old_tokens:
        print(f"💡 {len(old_tokens)} channel(s) have old tokens (may need refresh):")
        print("   Run: python3 app/checks/check_refresh_token_validity.py --all")
        print("   to verify if tokens are still valid")
        print()
    
    if recently_updated:
        print(f"✅ {len(recently_updated)} channel(s) were recently updated - tokens should be fresh!")
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
