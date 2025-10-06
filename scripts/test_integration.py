#!/usr/bin/env python3
"""
Test script to verify MySQL integration works correctly.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add core directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'core'))

# Set MySQL as default database if not set
if not os.getenv('DB_TYPE'):
    os.environ['DB_TYPE'] = 'mysql'

def test_database_connection():
    """Test database connection."""
    print("🔍 Testing database connection...")
    
    try:
        from core.database.sqlite_db import get_database_by_type
        db = get_database_by_type()
        print("✅ Database connection successful")
        return db
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def test_database_operations(db):
    """Test basic database operations."""
    print("🔍 Testing database operations...")
    
    try:
        # Test getting all channels
        channels = db.get_all_channels()
        print(f"✅ Found {len(channels)} channels")
        
        # Test getting enabled channels
        enabled_channels = db.get_all_channels(enabled_only=True)
        print(f"✅ Found {len(enabled_channels)} enabled channels")
        
        # Test database stats
        stats = db.get_database_stats()
        print(f"✅ Database stats: {stats}")
        
        return True
    except Exception as e:
        print(f"❌ Database operations failed: {e}")
        return False

def test_youtube_client():
    """Test YouTube client with database."""
    print("🔍 Testing YouTube client...")
    
    try:
        from core.api_clients.youtube_db_client import YouTubeDBClient
        
        client = YouTubeDBClient()
        available_channels = client.get_available_channels()
        print(f"✅ YouTube client initialized, {len(available_channels)} channels available")
        
        return True
    except Exception as e:
        print(f"❌ YouTube client test failed: {e}")
        return False

def test_config_loader():
    """Test database config loader."""
    print("🔍 Testing database config loader...")
    
    try:
        from core.utils.database_config_loader import DatabaseConfigLoader
        
        loader = DatabaseConfigLoader()
        config = loader.load_config()
        
        youtube_accounts = config.get('accounts', {}).get('youtube', [])
        print(f"✅ Config loader working, {len(youtube_accounts)} YouTube accounts loaded")
        
        return True
    except Exception as e:
        print(f"❌ Config loader test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing MySQL Integration")
    print("=" * 50)
    
    # Test 1: Database connection
    db = test_database_connection()
    if not db:
        print("❌ Cannot proceed without database connection")
        return False
    
    # Test 2: Database operations
    if not test_database_operations(db):
        print("❌ Database operations failed")
        return False
    
    # Test 3: YouTube client
    if not test_youtube_client():
        print("❌ YouTube client test failed")
        return False
    
    # Test 4: Config loader
    if not test_config_loader():
        print("❌ Config loader test failed")
        return False
    
    print("=" * 50)
    print("🎉 All tests passed! MySQL integration is working correctly!")
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
