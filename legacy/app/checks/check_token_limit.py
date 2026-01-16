#!/usr/bin/env python3
"""
Google OAuth Refresh Token Limit Checker

Diagnose if you're hitting Google's refresh token limits (50 per Client ID + User + Scopes).
This is one of the common causes of 'invalid_grant' errors.

USAGE:
    # Basic check
    python3 check_token_limit.py
    
    # Detailed info with solutions
    python3 check_token_limit.py --help

WHAT IT CHECKS:
    - Total number of YouTube channels in database
    - How many channels share the same Client ID
    - Token status for each channel (valid/expired)
    - How long since tokens were last updated
    - Warnings if approaching or exceeding limits

GOOGLE OAUTH LIMITS:
    - 50 refresh tokens per (Client ID + User + Scopes) combination
    - When 51st token is created, oldest one is auto-revoked
    - Revoked tokens return 'invalid_grant' error
    - Only CREATING new tokens counts (refreshing existing doesn't)

COMMON SCENARIOS:

    Scenario 1: Many channels with same Client ID
    Problem: 45+ channels using one Client ID
    Risk: High - close to limit
    Solution: Use different Client IDs for channel groups
    
    Scenario 2: Frequent re-authorization during development
    Problem: Testing OAuth flow creates many tokens
    Risk: Medium - old tokens get revoked
    Solution: Use separate dev/prod Client IDs
    
    Scenario 3: Multiple apps using same Client ID
    Problem: Other scripts also create tokens
    Risk: High - invisible token usage
    Solution: Track all apps, consolidate or separate

OUTPUT EXAMPLE:
    📊 Found 45 channel(s)
    📱 Unique OAuth Applications (Client IDs): 2
    
    App #1: 123456789-abc.apps.googleusercontent.com...
    Channels using this Client ID: 42
    
    ⚠️  WARNING: You have many channels with same Client ID!
       Each re-authorization creates a new refresh token
       Google limit: 50 tokens per Client ID + User + Scopes

SOLUTIONS:
    If you're hitting limits:
    1. Create separate OAuth applications in Google Cloud Console
    2. Group channels by Client ID (e.g., prod/test/dev)
    3. Update database with new Client IDs
    4. Re-authenticate affected channels
    5. Revoke old tokens at: https://myaccount.google.com/permissions

SEE ALSO:
    - Full guide: docs/youtube/05-TOKEN-REAUTH-GUIDE.md
    - Re-authenticate: python3 reauth_multiple_channels.py
    - Google OAuth docs: https://developers.google.com/identity/protocols/oauth2
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database.mysql_db import get_mysql_database
from core.utils.logger import get_logger

logger = get_logger("token_limit_checker")


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


def check_token_limits():
    """Check for potential token limit issues."""
    
    print("\n" + "=" * 70)
    print("🔍 GOOGLE OAUTH REFRESH TOKEN LIMIT CHECKER")
    print("=" * 70)
    
    mysql_config = load_mysql_config()
    db = get_mysql_database(config=mysql_config)
    channels = db.get_all_channels()
    
    if not channels:
        print("\n❌ No channels found in database")
        return
    
    print(f"\n📊 Found {len(channels)} channel(s)\n")
    
    # Group by client_id to check for potential limit issues
    # Get client_id from console credentials
    client_groups = {}
    
    for channel in channels:
        credentials = db.get_console_credentials_for_channel(channel.name)
        if credentials:
            client_id = credentials['client_id']
            if client_id not in client_groups:
                client_groups[client_id] = []
            client_groups[client_id].append(channel)
        else:
            # Channel without console - group separately
            if 'NO_CONSOLE' not in client_groups:
                client_groups['NO_CONSOLE'] = []
            client_groups['NO_CONSOLE'].append(channel)
    
    print(f"📱 Unique OAuth Applications (Client IDs): {len(client_groups)}\n")
    
    for i, (client_id, channels_list) in enumerate(client_groups.items(), 1):
        print(f"{'─' * 70}")
        if client_id == 'NO_CONSOLE':
            print(f"App #{i}: NO CONSOLE ASSIGNED")
            print(f"{'─' * 70}")
            print(f"Channels without console: {len(channels_list)}")
            print("⚠️  WARNING: These channels cannot publish without console assignment!")
        else:
            print(f"App #{i}: {client_id[:30]}...")
            print(f"{'─' * 70}")
            print(f"Channels using this Client ID: {len(channels_list)}")
        
        if len(channels_list) >= 40:
            print("⚠️  WARNING: You have many channels with same Client ID!")
            print("   Each re-authorization creates a new refresh token")
            print("   Google limit: 50 tokens per Client ID + User + Scopes")
        
        print(f"\nChannels:")
        for ch in channels_list:
            status = "✅" if ch.enabled else "❌"
            has_refresh = "🔑" if ch.refresh_token else "🔒"
            
            # Check token expiry
            token_age = "Unknown"
            if ch.updated_at:
                age = datetime.now() - ch.updated_at
                token_age = f"{age.days} days ago"
            
            # Check if expired
            is_expired = db.is_token_expired(ch.name)
            expiry_mark = "⚠️ EXPIRED" if is_expired else "✅ Valid"
            
            print(f"  {status} {ch.name}")
            print(f"     Refresh Token: {has_refresh}")
            print(f"     Token Status: {expiry_mark}")
            print(f"     Last Updated: {token_age}")
            
            # Check for invalid_grant indicators
            if ch.refresh_token and is_expired:
                print(f"     🚨 POTENTIAL ISSUE: Token expired but refresh_token exists")
                print(f"        This could indicate:")
                print(f"        - Refresh token limit exceeded")
                print(f"        - Refresh token manually revoked")
                print(f"        - 6 months of inactivity")
            print()
    
    print("=" * 70)
    print("\n💡 RECOMMENDATIONS:\n")
    
    total_channels = len(channels)
    
    if total_channels > 40:
        print("⚠️  You have MANY channels. Token limit issues are likely!")
        print("\n   Solutions:")
        print("   1. Use DIFFERENT Client IDs for different channels")
        print("   2. Group channels by purpose (prod, test, etc.)")
        print("   3. Delete unused channels to free up token slots")
        print("   4. Consider using Service Accounts (if applicable)")
    
    elif total_channels > 20:
        print("⚠️  You're approaching the safe limit")
        print("\n   Recommendations:")
        print("   1. Monitor token usage carefully")
        print("   2. Avoid frequent re-authorizations")
        print("   3. Use separate Client IDs for test vs production")
    
    else:
        print("✅ Your channel count is safe")
        print("\n   But remember:")
        print("   - Each re-authorization creates a NEW token")
        print("   - Testing OAuth flow repeatedly can hit the limit")
        print("   - If you have other apps/scripts using same Client ID, count those too")
    
    print("\n" + "=" * 70)
    print("\n📚 MORE INFO:\n")
    print("Google OAuth Token Limits:")
    print("• 50 refresh tokens per (Client ID + User + Scopes)")
    print("• Oldest token is auto-revoked when 51st is created")
    print("• Revoked tokens return 'invalid_grant' error")
    print("• Using refresh token does NOT count toward limit")
    print("• Only CREATING new tokens counts")
    
    print("\n🔗 Reference:")
    print("https://developers.google.com/identity/protocols/oauth2#expiration")
    print("\n" + "=" * 70 + "\n")


def show_solution():
    """Show solution for token limit issues."""
    print("\n" + "=" * 70)
    print("🔧 HOW TO FIX TOKEN LIMIT ISSUES")
    print("=" * 70)
    
    print("\n1️⃣  IDENTIFY THE PROBLEM:")
    print("   • Run this script to see how many channels share Client IDs")
    print("   • Check if you have > 40 channels with same Client ID")
    
    print("\n2️⃣  CREATE SEPARATE OAUTH APPLICATIONS:")
    print("   • Go to: https://console.cloud.google.com/apis/credentials")
    print("   • Create new OAuth 2.0 Client IDs for different channel groups")
    print("   • Example organization:")
    print("     - client_id_1: Production channels (audiokniga-one, etc.)")
    print("     - client_id_2: Test channels")
    print("     - client_id_3: Development channels")
    
    print("\n3️⃣  UPDATE CHANNEL CONFIGURATIONS:")
    print("   • Update database with new Client IDs")
    print("   • Re-authenticate channels with their new Client IDs")
    
    print("\n4️⃣  CLEAN UP OLD TOKENS:")
    print("   • Go to: https://myaccount.google.com/permissions")
    print("   • Revoke access for old/unused applications")
    print("   • This frees up token slots")
    
    print("\n5️⃣  PREVENT FUTURE ISSUES:")
    print("   • Don't re-authorize unnecessarily")
    print("   • Use token refresh instead of re-auth")
    print("   • Monitor token count with this script")
    print("   • Keep production and test separated")
    
    print("\n" + "=" * 70 + "\n")


def main():
    """Main function."""
    check_token_limits()
    
    if "--help" in sys.argv or "-h" in sys.argv:
        show_solution()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        logger.exception("Error checking token limits")
        sys.exit(1)

