#!/usr/bin/env python3
"""
Update old failed tasks that don't have error_message.
This will set error_message to "Unknown error" for failed tasks without error messages,
so they appear in daily reports.
"""

import sys
import os
import yaml
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.database.mysql_db import YouTubeMySQLDatabase
from mysql.connector import Error


def load_mysql_config():
    """Load MySQL configuration from yaml file."""
    config_path = os.path.join(project_root, 'config', 'mysql_config.yaml')
    
    if not os.path.exists(config_path):
        print(f"⚠️  MySQL config not found at {config_path}")
        print("Using environment variables or defaults")
        return None
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        print(f"✅ Loaded MySQL config from {config_path}")
        return config
    except Exception as e:
        print(f"⚠️  Failed to load MySQL config: {e}")
        return None

def main():
    """Update old failed tasks."""
    print("=" * 60)
    print("Updating Old Failed Tasks")
    print("=" * 60)
    print()
    
    try:
        # Load MySQL configuration
        mysql_config = load_mysql_config()
        db = YouTubeMySQLDatabase(config=mysql_config)
        
        # Find failed tasks without error_message
        query = """
            SELECT id, account_id, status, error_message
            FROM tasks 
            WHERE status = 2 AND (error_message IS NULL OR error_message = '')
            ORDER BY id
        """
        
        results = db._execute_query(query, fetch=True)
        
        if not results:
            print("✅ No failed tasks without error_message found")
            db.close()
            return 0
        
        print(f"Found {len(results)} failed task(s) without error_message:\n")
        
        for row in results:
            task_id, account_id, _, _ = row
            print(f"  Task #{task_id} (Account #{account_id})")
        
        print()
        response = input("Update these tasks with 'Unknown error'? (yes/no): ")
        
        if response.lower() != 'yes':
            print("❌ Cancelled")
            db.close()
            return 1
        
        # Update tasks
        update_query = """
            UPDATE tasks 
            SET error_message = 'Unknown error (task failed before error tracking was added)'
            WHERE status = 2 AND (error_message IS NULL OR error_message = '')
        """
        
        db._execute_query(update_query)
        
        print(f"\n✅ Updated {len(results)} task(s)")
        print("\nThese tasks will now appear in daily reports with error type 'Unknown'")
        
        db.close()
        return 0
        
    except Error as e:
        print(f"❌ Database error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

