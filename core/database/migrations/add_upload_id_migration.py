#!/usr/bin/env python3
"""
Migration script to add upload_id column to tasks table.
This script adds the upload_id field to existing tasks table for storing video IDs after upload.
"""

import sys
import os
import yaml

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.database.mysql_db import YouTubeMySQLDatabase
from mysql.connector import Error


def load_mysql_config():
    """Load MySQL configuration from yaml file."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        'config',
        'mysql_config.yaml'
    )
    
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


def add_upload_id_column(db: YouTubeMySQLDatabase) -> bool:
    """Add upload_id column to tasks table if it doesn't exist."""
    
    try:
        # Check if column already exists
        check_query = """
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'tasks' 
            AND COLUMN_NAME = 'upload_id'
        """
        
        result = db._execute_query(check_query, fetch=True)
        
        if result and result[0][0] > 0:
            print("✅ Column 'upload_id' already exists in tasks table")
            return True
        
        # Add the column
        alter_query = """
            ALTER TABLE tasks 
            ADD COLUMN upload_id VARCHAR(255) COMMENT 'Video ID from platform after upload'
        """
        
        db._execute_query(alter_query)
        print("✅ Successfully added 'upload_id' column to tasks table")
        
        # Add index for better query performance
        index_query = """
            CREATE INDEX idx_upload_id ON tasks(upload_id)
        """
        
        try:
            db._execute_query(index_query)
            print("✅ Successfully added index on 'upload_id' column")
        except Error as e:
            if "Duplicate key name" in str(e):
                print("ℹ️  Index on 'upload_id' already exists")
            else:
                raise e
        
        return True
        
    except Error as e:
        print(f"❌ Error during migration: {e}")
        return False


def main():
    """Run migration."""
    print("=" * 60)
    print("Migration: Add upload_id column to tasks table")
    print("=" * 60)
    print()
    
    # Load MySQL configuration
    mysql_config = load_mysql_config()
    
    # Initialize database connection
    try:
        db = YouTubeMySQLDatabase(config=mysql_config)
        print()
        
        # Run migration
        if add_upload_id_column(db):
            print()
            print("=" * 60)
            print("✅ Migration completed successfully!")
            print("=" * 60)
            print()
            print("The 'upload_id' field will now be populated automatically")
            print("when tasks are completed by the task worker.")
            print()
        else:
            print()
            print("=" * 60)
            print("❌ Migration failed!")
            print("=" * 60)
            print()
            sys.exit(1)
        
        db.close()
        
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        print()
        print("Please ensure:")
        print("  1. MySQL server is running")
        print("  2. Database credentials are correct in config/mysql_config.yaml")
        print("  3. Database 'content_fabric' exists")
        sys.exit(1)


if __name__ == "__main__":
    main()

