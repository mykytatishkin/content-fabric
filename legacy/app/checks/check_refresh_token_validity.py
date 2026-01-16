#!/usr/bin/env python3
"""
Script to check if refresh_token is valid for YouTube channels.
Tests refresh_token by attempting to refresh access_token.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load .env if present
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.database.mysql_db import get_mysql_database
from core.utils.logger import get_logger

LOGGER = get_logger("check_refresh_token_validity")


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


def test_refresh_token(channel, db) -> tuple[bool, str]:
    """
    Test if refresh_token is valid by attempting to refresh access_token.
    
    Args:
        channel: YouTubeChannel object
        db: YouTubeMySQLDatabase instance
    
    Returns:
        (is_valid, error_message)
    """
    if not channel.refresh_token:
        return False, "No refresh_token in database"
    
    # Get credentials from console
    credentials = db.get_console_credentials_for_channel(channel.name)
    if not credentials:
        return False, "No console credentials found. Channel must have console_name or console_id set."
    
    client_id = credentials['client_id']
    client_secret = credentials['client_secret']
    
    try:
        # Create credentials object with refresh_token
        creds = Credentials(
            token=None,  # We don't have a valid access_token, so set to None
            refresh_token=channel.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Try to refresh the token
        creds.refresh(Request())
        
        # If refresh succeeded, try to use the token to make an API call
        # This verifies the token actually works
        youtube_service = build('youtube', 'v3', credentials=creds)
        response = youtube_service.channels().list(part='snippet', mine=True).execute()
        
        if response.get('items'):
            return True, "Valid - successfully refreshed and tested with API"
        else:
            return False, "Refresh succeeded but API call returned no channels"
            
    except HttpError as e:
        error_str = str(e)
        if 'invalid_grant' in error_str.lower():
            return False, f"Invalid/revoked: {error_str[:100]}"
        else:
            return False, f"HTTP Error: {error_str[:100]}"
    except Exception as e:
        error_str = str(e)
        if 'invalid_grant' in error_str.lower():
            return False, f"Invalid/revoked: {error_str[:100]}"
        else:
            return False, f"Error: {error_str[:100]}"


def check_refresh_token_validity(channel_names: list[str] | None = None, enabled_only: bool = True) -> None:
    """Check refresh_token validity for specified channels or all channels."""
    mysql_config = load_mysql_config()
    db = get_mysql_database(config=mysql_config)
    
    print("=" * 80)
    print("Checking Refresh Token Validity for YouTube Channels")
    print("=" * 80)
    print()
    
    # Get channels
    if channel_names:
        channels = []
        for name in channel_names:
            channel = db.get_channel(name)
            if channel:
                channels.append(channel)
            else:
                print(f"❌ Channel '{name}' not found in database")
    else:
        channels = db.get_all_channels(enabled_only=enabled_only)
    
    if not channels:
        print("No channels found to check.")
        return
    
    print(f"Checking {len(channels)} channel(s)...\n")
    
    valid_count = 0
    invalid_count = 0
    missing_count = 0
    
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
    print(f"📊 Total checked: {len(channels)}")
    print()
    
    # List invalid channels
    if invalid_count > 0:
        print("❌ Channels with INVALID refresh_tokens (need re-authentication):")
        for result in results:
            if result['status'] == 'invalid':
                print(f"   - {result['channel']}: {result['error']}")
        print()
    
    # List missing channels
    if missing_count > 0:
        print("⚠️  Channels with MISSING refresh_tokens:")
        for result in results:
            if result['status'] == 'missing':
                print(f"   - {result['channel']}")
        print()
    
    if invalid_count > 0 or missing_count > 0:
        print("💡 To re-authenticate channels, run:")
        print("   python3 run_youtube_reauth.py <channel_name>")
        print("   or")
        print("   python3 run_youtube_reauth.py --all-expiring")


def main() -> int:
    """Main entry point."""
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
    
    try:
        check_refresh_token_validity(
            channel_names=args.channels if args.channels else None,
            enabled_only=not args.all
        )
        return 0
    except Exception as exc:
        LOGGER.exception("Error checking refresh token validity: %s", exc)
        print(f"\n❌ Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

