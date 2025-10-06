#!/usr/bin/env python3
"""
Migration script from SQLite to MySQL for Content Fabric YouTube Database.
"""

import sqlite3
import mysql.connector
from mysql.connector import Error
import os
import sys
from datetime import datetime
from typing import List, Dict, Any
import argparse


class DatabaseMigrator:
    """Migrate data from SQLite to MySQL."""
    
    def __init__(self, sqlite_path: str, mysql_config: Dict[str, str]):
        self.sqlite_path = sqlite_path
        self.mysql_config = mysql_config
        self.mysql_connection = None
    
    def connect_mysql(self) -> bool:
        """Connect to MySQL database."""
        try:
            self.mysql_connection = mysql.connector.connect(**self.mysql_config)
            if self.mysql_connection.is_connected():
                print("✅ Connected to MySQL database")
                return True
        except Error as e:
            print(f"❌ Error connecting to MySQL: {e}")
            return False
    
    def disconnect_mysql(self):
        """Disconnect from MySQL database."""
        if self.mysql_connection and self.mysql_connection.is_connected():
            self.mysql_connection.close()
            print("✅ Disconnected from MySQL")
    
    def get_sqlite_data(self, table_name: str) -> List[Dict[str, Any]]:
        """Get data from SQLite table."""
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"❌ Error reading SQLite data: {e}")
            return []
    
    def _parse_datetime(self, datetime_str: str, field_name: str, row_name: str = None) -> datetime:
        """Parse datetime string with error handling."""
        if not datetime_str:
            return None
        
        try:
            return datetime.fromisoformat(datetime_str)
        except ValueError:
            print(f"⚠️ Invalid datetime format for {field_name} in {row_name or 'row'}: {datetime_str}")
            return datetime.now() if field_name in ['created_at', 'updated_at'] else None
    
    def _prepare_channel_data(self, row: Dict[str, Any]) -> tuple:
        """Prepare channel data for MySQL insertion."""
        return (
            row.get('id'),
            row.get('name'),
            row.get('channel_id'),
            row.get('client_id'),
            row.get('client_secret'),
            row.get('access_token'),
            row.get('refresh_token'),
            self._parse_datetime(row.get('token_expires_at'), 'token_expires_at', row.get('name')),
            bool(row.get('enabled', True)),
            self._parse_datetime(row.get('created_at'), 'created_at', row.get('name')),
            self._parse_datetime(row.get('updated_at'), 'updated_at', row.get('name'))
        )
    
    def migrate_youtube_channels(self) -> bool:
        """Migrate youtube_channels table."""
        print("📊 Migrating youtube_channels table...")
        
        # Get data from SQLite
        sqlite_data = self.get_sqlite_data('youtube_channels')
        if not sqlite_data:
            print("⚠️ No data found in SQLite youtube_channels table")
            return True
        
        print(f"📋 Found {len(sqlite_data)} channels to migrate")
        
        try:
            cursor = self.mysql_connection.cursor()
            
            # Clear existing data (optional - comment out if you want to keep existing data)
            cursor.execute("DELETE FROM youtube_channels")
            
            # Insert data
            insert_query = """
                INSERT INTO youtube_channels 
                (id, name, channel_id, client_id, client_secret, access_token, 
                 refresh_token, token_expires_at, enabled, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            for row in sqlite_data:
                values = self._prepare_channel_data(row)
                cursor.execute(insert_query, values)
            
            self.mysql_connection.commit()
            print(f"✅ Successfully migrated {len(sqlite_data)} channels")
            return True
            
        except Error as e:
            print(f"❌ Error migrating youtube_channels: {e}")
            self.mysql_connection.rollback()
            return False
    
    def _prepare_token_data(self, row: Dict[str, Any]) -> tuple:
        """Prepare token data for MySQL insertion."""
        return (
            row.get('id'),
            row.get('channel_name'),
            row.get('token_type'),
            row.get('token_value'),
            self._parse_datetime(row.get('expires_at'), 'expires_at', f"token {row.get('id')}"),
            self._parse_datetime(row.get('created_at'), 'created_at', f"token {row.get('id')}")
        )
    
    def migrate_youtube_tokens(self) -> bool:
        """Migrate youtube_tokens table."""
        print("📊 Migrating youtube_tokens table...")
        
        # Get data from SQLite
        sqlite_data = self.get_sqlite_data('youtube_tokens')
        if not sqlite_data:
            print("⚠️ No data found in SQLite youtube_tokens table")
            return True
        
        print(f"📋 Found {len(sqlite_data)} tokens to migrate")
        
        try:
            cursor = self.mysql_connection.cursor()
            
            # Clear existing data (optional - comment out if you want to keep existing data)
            cursor.execute("DELETE FROM youtube_tokens")
            
            # Insert data
            insert_query = """
                INSERT INTO youtube_tokens 
                (id, channel_name, token_type, token_value, expires_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            for row in sqlite_data:
                values = self._prepare_token_data(row)
                cursor.execute(insert_query, values)
            
            self.mysql_connection.commit()
            print(f"✅ Successfully migrated {len(sqlite_data)} tokens")
            return True
            
        except Error as e:
            print(f"❌ Error migrating youtube_tokens: {e}")
            self.mysql_connection.rollback()
            return False
    
    def verify_migration(self) -> bool:
        """Verify that migration was successful."""
        print("🔍 Verifying migration...")
        
        try:
            cursor = self.mysql_connection.cursor()
            
            # Check channels count
            cursor.execute("SELECT COUNT(*) FROM youtube_channels")
            mysql_channels_count = cursor.fetchone()[0]
            
            # Check tokens count
            cursor.execute("SELECT COUNT(*) FROM youtube_tokens")
            mysql_tokens_count = cursor.fetchone()[0]
            
            # Get SQLite counts
            sqlite_channels_count = len(self.get_sqlite_data('youtube_channels'))
            sqlite_tokens_count = len(self.get_sqlite_data('youtube_tokens'))
            
            print(f"📊 SQLite channels: {sqlite_channels_count}, MySQL channels: {mysql_channels_count}")
            print(f"📊 SQLite tokens: {sqlite_tokens_count}, MySQL tokens: {mysql_tokens_count}")
            
            if (mysql_channels_count == sqlite_channels_count and 
                mysql_tokens_count == sqlite_tokens_count):
                print("✅ Migration verification successful!")
                return True
            else:
                print("❌ Migration verification failed - counts don't match")
                return False
                
        except Error as e:
            print(f"❌ Error verifying migration: {e}")
            return False
    
    def run_migration(self) -> bool:
        """Run the complete migration process."""
        print("🚀 Starting migration from SQLite to MySQL...")
        
        if not self.connect_mysql():
            return False
        
        try:
            # Migrate tables
            if not self.migrate_youtube_channels():
                return False
            
            if not self.migrate_youtube_tokens():
                return False
            
            # Verify migration
            if not self.verify_migration():
                return False
            
            print("🎉 Migration completed successfully!")
            return True
            
        finally:
            self.disconnect_mysql()


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite to MySQL")
    parser.add_argument('--sqlite-path', default='youtube_channels.db', 
                       help='Path to SQLite database file')
    parser.add_argument('--mysql-host', default='localhost', 
                       help='MySQL host')
    parser.add_argument('--mysql-port', type=int, default=3306, 
                       help='MySQL port')
    parser.add_argument('--mysql-database', default='content_fabric', 
                       help='MySQL database name')
    parser.add_argument('--mysql-user', default='content_fabric_user', 
                       help='MySQL username')
    parser.add_argument('--mysql-password', 
                       help='MySQL password (will prompt if not provided)')
    
    args = parser.parse_args()
    
    # Get password if not provided
    if not args.mysql_password:
        import getpass
        args.mysql_password = getpass.getpass("MySQL password: ")
    
    # Check if SQLite file exists
    if not os.path.exists(args.sqlite_path):
        print(f"❌ SQLite file not found: {args.sqlite_path}")
        sys.exit(1)
    
    # MySQL configuration
    mysql_config = {
        'host': args.mysql_host,
        'port': args.mysql_port,
        'database': args.mysql_database,
        'user': args.mysql_user,
        'password': args.mysql_password,
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci'
    }
    
    # Run migration
    migrator = DatabaseMigrator(args.sqlite_path, mysql_config)
    success = migrator.run_migration()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
