#!/usr/bin/env python3
"""
Script to check if google_consoles table exists and verify migration status.
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.database.mysql_db import get_mysql_database, YouTubeMySQLDatabase
from core.database.migrations.add_google_consoles_migration import table_exists, column_exists, load_mysql_config


def main():
    """Check migration status."""
    print("=" * 72)
    print("Checking Google Cloud Console migration status")
    print("=" * 72)
    print()
    
    try:
        # Load config explicitly
        mysql_config = load_mysql_config()
        if mysql_config:
            db = YouTubeMySQLDatabase(config=mysql_config)
        else:
            db = get_mysql_database()
        print("✅ Connected to MySQL database")
        print()
        
        # Check table
        table_exists_result = table_exists(db, "google_consoles")
        print(f"Table 'google_consoles' exists: {'✅ Yes' if table_exists_result else '❌ No'}")
        
        if table_exists_result:
            try:
                result = db._execute_query("SELECT COUNT(*) FROM google_consoles", fetch=True)
                if result:
                    count = result[0][0]
                    print(f"   Records in table: {count}")
                    
                    if count > 0:
                        consoles = db._execute_query("SELECT id, name, enabled FROM google_consoles", fetch=True)
                        print("   Consoles:")
                        for console in consoles:
                            status = "✅" if console[2] else "❌"
                            print(f"      {status} {console[1]} (ID: {console[0]})")
            except Exception as e:
                print(f"   ⚠️  Could not query table: {e}")
        
        print()
        
        # Check column
        column_exists_result = column_exists(db, "youtube_channels", "console_id")
        print(f"Column 'console_id' in 'youtube_channels' exists: {'✅ Yes' if column_exists_result else '❌ No'}")
        
        if column_exists_result:
            try:
                result = db._execute_query(
                    "SELECT COUNT(*) FROM youtube_channels WHERE console_id IS NOT NULL",
                    fetch=True
                )
                if result:
                    count = result[0][0]
                    total = db._execute_query("SELECT COUNT(*) FROM youtube_channels", fetch=True)[0][0]
                    print(f"   Channels with console assigned: {count} / {total}")
            except Exception as e:
                print(f"   ⚠️  Could not query column: {e}")
        
        print()
        print("=" * 72)
        
        if table_exists_result and column_exists_result:
            print("✅ Migration is complete!")
        else:
            print("❌ Migration is incomplete. Please run:")
            print("   python3 core/database/migrations/scripts/run_migration_google_consoles.py")
        
        print("=" * 72)
        print()
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

