#!/usr/bin/env python3
"""
Test script to verify that error messages are saved correctly.
"""

import sys
import os
import yaml
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.database.mysql_db import YouTubeMySQLDatabase
from core.utils.error_categorizer import ErrorCategorizer

def load_mysql_config():
    """Load MySQL configuration from yaml file."""
    config_path = os.path.join(project_root, 'config', 'mysql_config.yaml')
    
    if not os.path.exists(config_path):
        return None
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception:
        return None

def main():
    """Test error message saving."""
    print("=" * 60)
    print("Testing Error Message Saving")
    print("=" * 60)
    print()
    
    try:
        mysql_config = load_mysql_config()
        db = YouTubeMySQLDatabase(config=mysql_config)
        
        # Get recent failed tasks (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        
        query = """
            SELECT id, account_id, status, error_message, date_post, date_done
            FROM tasks 
            WHERE status = 2 
            AND date_done >= %s
            ORDER BY date_done DESC
            LIMIT 20
        """
        
        results = db._execute_query(query, (week_ago,), fetch=True)
        
        if not results:
            print("ℹ️  No failed tasks found in the last 7 days")
            db.close()
            return 0
        
        print(f"Found {len(results)} failed task(s) in the last 7 days:\n")
        
        tasks_with_error = 0
        tasks_without_error = 0
        
        for row in results:
            task_id, account_id, status, error_message, date_post, date_done = row
            has_error = error_message is not None and error_message.strip() != ''
            
            if has_error:
                tasks_with_error += 1
                category = ErrorCategorizer.categorize(error_message)
                print(f"✅ Task #{task_id} (Account #{account_id}):")
                print(f"   Category: {category}")
                print(f"   Error: {error_message[:80]}...")
            else:
                tasks_without_error += 1
                print(f"❌ Task #{task_id} (Account #{account_id}):")
                print(f"   Error: NO ERROR MESSAGE")
            
            print(f"   Date: {date_done}")
            print()
        
        print("=" * 60)
        print("Summary:")
        print(f"  Tasks with error_message: {tasks_with_error}")
        print(f"  Tasks without error_message: {tasks_without_error}")
        print()
        
        if tasks_without_error > 0:
            print("⚠️  Some tasks don't have error_message!")
            print("   This might mean:")
            print("   1. Tasks were marked as failed before error tracking was added")
            print("   2. There's a bug in error saving")
            print("   3. Tasks were reset to pending during retry")
        
        db.close()
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

