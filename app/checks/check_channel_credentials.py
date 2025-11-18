#!/usr/bin/env python3
"""
Check channel credentials in database.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.database import get_database_by_type


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


def check_channel(channel_name: str):
    """Check channel credentials in database."""
    mysql_config = load_mysql_config()
    db = get_database_by_type(config=mysql_config)
    
    print(f"\n{'='*60}")
    print(f"Checking channel: {channel_name}")
    print(f"{'='*60}\n")
    
    channel = db.get_channel(channel_name)
    
    if not channel:
        print(f"❌ Channel '{channel_name}' not found in database")
        return
    
    print(f"✅ Channel found:")
    print(f"   ID: {channel.id}")
    print(f"   Name: {channel.name}")
    print(f"   Channel ID: {channel.channel_id}")
    print(f"   Enabled: {channel.enabled}")
    print(f"   Created: {channel.created_at}")
    print(f"   Updated: {channel.updated_at}")
    print()
    
    # Check client credentials
    print("Client Credentials:")
    if channel.client_id:
        client_id_preview = channel.client_id[:20] + "..." if len(channel.client_id) > 20 else channel.client_id
        print(f"   ✅ client_id: {client_id_preview} (length: {len(channel.client_id)})")
    else:
        print(f"   ❌ client_id: MISSING or NULL")
    
    if channel.client_secret:
        client_secret_preview = channel.client_secret[:20] + "..." if len(channel.client_secret) > 20 else channel.client_secret
        print(f"   ✅ client_secret: {client_secret_preview} (length: {len(channel.client_secret)})")
    else:
        print(f"   ❌ client_secret: MISSING or NULL")
    
    print()
    
    # Check tokens
    print("Tokens:")
    if channel.access_token:
        print(f"   ✅ access_token: present (length: {len(channel.access_token)})")
    else:
        print(f"   ⚠️  access_token: not set")
    
    if channel.refresh_token:
        print(f"   ✅ refresh_token: present (length: {len(channel.refresh_token)})")
    else:
        print(f"   ⚠️  refresh_token: not set")
    
    if channel.token_expires_at:
        print(f"   ✅ token_expires_at: {channel.token_expires_at}")
    else:
        print(f"   ⚠️  token_expires_at: not set")
    
    print()
    
    # Check account credentials
    account_creds = db.get_account_credentials(channel_name, include_disabled=False)
    if account_creds:
        print("✅ Account credentials found:")
        print(f"   Login email: {account_creds.login_email}")
        print(f"   Profile path: {account_creds.profile_path or 'not set'}")
        print(f"   Enabled: {account_creds.enabled}")
    else:
        print("⚠️  Account credentials not found (this is OK if using manual OAuth)")
    
    print()


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python check_channel_credentials.py <channel_name> [channel_name2 ...]")
        print("\nExample:")
        print("  python check_channel_credentials.py Popadanciaudio")
        print("  python check_channel_credentials.py Popadanciaudio andrew_garle")
        sys.exit(1)
    
    channel_names = sys.argv[1:]
    
    for channel_name in channel_names:
        try:
            check_channel(channel_name)
        except Exception as e:
            print(f"❌ Error checking channel '{channel_name}': {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

