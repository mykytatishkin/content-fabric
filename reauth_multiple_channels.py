#!/usr/bin/env python3
"""
Re-authenticate multiple YouTube channels at once.

This script helps fix expired or revoked OAuth refresh tokens by initiating
a fresh OAuth flow for one or more YouTube channels.

USAGE:
    # One channel
    python3 reauth_multiple_channels.py audiokniga-one
    
    # Multiple channels
    python3 reauth_multiple_channels.py channel-1 channel-2 channel-3
    
    # Auto-find and fix all channels with expired tokens
    python3 reauth_multiple_channels.py --expired

WHEN TO USE:
    - You see "invalid_grant: Token has been expired or revoked" error
    - Refresh token was manually revoked in Google Account settings
    - Token expired due to 6 months of inactivity
    - Need to re-authorize after changing OAuth scopes

WHAT IT DOES:
    1. Validates that channels exist in database
    2. For each channel:
       - Creates OAuth authorization URL
       - Opens browser for user authentication
       - Exchanges authorization code for tokens
       - Saves new access_token and refresh_token to database
    3. Shows summary of successful/failed re-authorizations

REQUIREMENTS:
    - MySQL/Docker must be running
    - Browser access for OAuth flow
    - Correct Client ID and Client Secret in database
    - Redirect URI configured: http://localhost:8080/callback

SEE ALSO:
    - Full documentation: docs/youtube/05-TOKEN-REAUTH-GUIDE.md
    - Token diagnostics: python3 check_token_limit.py
    - Status check: python run_youtube_manager.py check-tokens
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.auth.oauth_manager import OAuthManager
from core.database.mysql_db import get_mysql_database
from core.database import get_database_by_type
from core.utils.logger import get_logger

logger = get_logger("reauth_multiple")


def reauth_channel(oauth_manager, channel_name):
    """Re-authenticate a single channel."""
    print(f"\n{'=' * 70}")
    print(f"🔐 Re-authenticating: {channel_name}")
    print(f"{'=' * 70}")
    
    try:
        # Authorize the account
        result = oauth_manager.authorize_account(
            platform="youtube",
            account_name=channel_name,
            auto_open_browser=True
        )
        
        if result.get('success'):
            print(f"✅ SUCCESS! '{channel_name}' re-authenticated")
            print(f"   Access Token: {result['access_token'][:20]}...")
            print(f"   Refresh Token: {result.get('refresh_token', 'N/A')[:20]}...")
            return True
        else:
            print(f"❌ FAILED: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        logger.exception(f"Failed to re-auth {channel_name}")
        return False


def main():
    """Re-authenticate multiple channels."""
    
    # Check if channel names provided
    if len(sys.argv) < 2:
        print("\n📋 Usage:")
        print("   python3 reauth_multiple_channels.py channel1 channel2 channel3")
        print("\nExample:")
        print("   python3 reauth_multiple_channels.py audiokniga-one audiokniga-two")
        print("\n💡 Or use --expired to re-auth all channels with expired tokens")
        return 1
    
    # Check for --expired flag
    if sys.argv[1] == "--expired":
        print("\n🔍 Finding channels with expired tokens...")
        db = get_mysql_database()
        channels = db.get_all_channels(enabled_only=True)
        
        channel_names = []
        for ch in channels:
            if db.is_token_expired(ch.name):
                channel_names.append(ch.name)
        
        if not channel_names:
            print("✅ No channels with expired tokens found!")
            return 0
        
        print(f"\n⚠️  Found {len(channel_names)} channel(s) with expired tokens:")
        for name in channel_names:
            print(f"   - {name}")
        
        response = input("\n❓ Re-authenticate these channels? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Cancelled")
            return 0
    else:
        # Get channel names from command line
        channel_names = sys.argv[1:]
    
    # Validate all channels exist first
    print(f"\n🔍 Validating {len(channel_names)} channel(s)...")
    db = get_database_by_type()
    
    valid_channels = []
    invalid_channels = []
    
    for name in channel_names:
        channel = db.get_channel(name)
        if channel:
            valid_channels.append(name)
            print(f"   ✅ {name}")
        else:
            invalid_channels.append(name)
            print(f"   ❌ {name} - NOT FOUND")
    
    if invalid_channels:
        print(f"\n❌ Error: {len(invalid_channels)} channel(s) not found in database:")
        for name in invalid_channels:
            print(f"   - {name}")
        print("\n📋 Available channels:")
        channels = db.get_all_channels()
        for ch in channels:
            print(f"   - {ch.name}")
        return 1
    
    # Start re-authentication process
    print(f"\n{'=' * 70}")
    print(f"🚀 Starting re-authentication for {len(valid_channels)} channel(s)")
    print(f"{'=' * 70}")
    print("\n⚠️  IMPORTANT:")
    print("   - Make sure you select the CORRECT Google account for each channel")
    print("   - Grant ALL requested permissions")
    print("   - You'll need to authenticate each channel separately")
    print("   - Press Ctrl+C to cancel at any time")
    
    input("\nPress Enter to continue...")
    
    # Initialize OAuth manager
    # Use config/config.yaml path (relative to project root)
    config_path = project_root / "config" / "config.yaml"
    oauth_manager = OAuthManager(config_path=str(config_path), use_database=True)
    
    # Track results
    results = {
        'success': [],
        'failed': []
    }
    
    # Re-authenticate each channel
    for i, channel_name in enumerate(valid_channels, 1):
        print(f"\n\n{'#' * 70}")
        print(f"Channel {i}/{len(valid_channels)}")
        print(f"{'#' * 70}")
        
        success = reauth_channel(oauth_manager, channel_name)
        
        if success:
            results['success'].append(channel_name)
        else:
            results['failed'].append(channel_name)
        
        # Wait between channels (except for the last one)
        if i < len(valid_channels):
            print(f"\n⏳ Waiting 5 seconds before next channel...")
            time.sleep(5)
    
    # Print summary
    print(f"\n\n{'=' * 70}")
    print("📊 RE-AUTHENTICATION SUMMARY")
    print(f"{'=' * 70}")
    print(f"\n✅ Successful: {len(results['success'])}/{len(valid_channels)}")
    for name in results['success']:
        print(f"   - {name}")
    
    if results['failed']:
        print(f"\n❌ Failed: {len(results['failed'])}/{len(valid_channels)}")
        for name in results['failed']:
            print(f"   - {name}")
        print(f"\n💡 To retry failed channels:")
        print(f"   python3 reauth_youtube_channel.py {' '.join(results['failed'])}")
    
    print(f"\n{'=' * 70}\n")
    
    return 0 if not results['failed'] else 1


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

