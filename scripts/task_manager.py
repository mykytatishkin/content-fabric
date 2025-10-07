#!/usr/bin/env python3
"""
Task Manager CLI - Command line interface for managing scheduled posting tasks.
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database.mysql_db import YouTubeMySQLDatabase, Task
from core.utils.database_config_loader import DatabaseConfigLoader


class TaskManagerCLI:
    """CLI for managing tasks."""
    
    def __init__(self):
        """Initialize Task Manager CLI."""
        # Load database configuration
        config_path = Path("config/mysql_config.yaml")
        if config_path.exists():
            with open(config_path, 'r') as f:
                mysql_config = yaml.safe_load(f)
            self.db = YouTubeMySQLDatabase(mysql_config)
        else:
            print("⚠️  MySQL config not found, using environment variables")
            self.db = YouTubeMySQLDatabase()
    
    def create_task(self, args):
        """Create a new task."""
        try:
            # Parse account (can be name or ID)
            account_id = None
            if args.account.isdigit():
                account_id = int(args.account)
            else:
                # Get channel by name
                channel = self.db.get_channel(args.account)
                if channel:
                    account_id = channel.id
                else:
                    print(f"❌ Channel '{args.account}' not found")
                    return
            
            # Parse scheduled time
            if args.schedule:
                try:
                    date_post = datetime.fromisoformat(args.schedule)
                except ValueError:
                    print(f"❌ Invalid date format. Use ISO format: YYYY-MM-DD HH:MM:SS")
                    return
            else:
                date_post = datetime.now()
            
            # Parse additional info
            add_info = None
            if args.add_info:
                try:
                    add_info = json.loads(args.add_info)
                except json.JSONDecodeError:
                    print(f"❌ Invalid JSON in add_info")
                    return
            
            # Check if video file exists
            video_path = Path(args.video)
            if not video_path.exists():
                print(f"❌ Video file not found: {args.video}")
                return
            
            # Create task
            task_id = self.db.create_task(
                account_id=account_id,
                att_file_path=str(video_path.absolute()),
                title=args.title,
                date_post=date_post,
                media_type=args.media_type,
                cover=args.cover,
                description=args.description,
                keywords=args.keywords,
                post_comment=args.comment,
                add_info=add_info
            )
            
            if task_id:
                print(f"✅ Task created successfully!")
                print(f"   Task ID: {task_id}")
                print(f"   Account ID: {account_id}")
                print(f"   Title: {args.title}")
                print(f"   Scheduled for: {date_post}")
            else:
                print(f"❌ Failed to create task")
                
        except Exception as e:
            print(f"❌ Error creating task: {str(e)}")
    
    def list_tasks(self, args):
        """List tasks."""
        try:
            # Get tasks based on filters
            if args.status == 'all':
                tasks = self.db.get_all_tasks(limit=args.limit)
            else:
                status_map = {
                    'pending': 0,
                    'completed': 1,
                    'failed': 2,
                    'processing': 3
                }
                status = status_map.get(args.status)
                tasks = self.db.get_all_tasks(status=status, limit=args.limit)
            
            if not tasks:
                print("No tasks found")
                return
            
            # Print header
            print(f"\n{'ID':<6} {'Account':<15} {'Type':<10} {'Status':<12} {'Title':<40} {'Scheduled':<20}")
            print("-" * 120)
            
            # Print tasks
            for task in tasks:
                # Get channel name
                channel = self._get_channel_by_id(task.account_id)
                account_name = channel.name if channel else f"ID:{task.account_id}"
                
                # Get status text
                status_text = ['Pending', 'Completed', 'Failed', 'Processing'][task.status]
                
                # Truncate title if too long
                title = task.title[:37] + "..." if len(task.title) > 40 else task.title
                
                print(f"{task.id:<6} {account_name:<15} {task.media_type:<10} {status_text:<12} {title:<40} {task.date_post.strftime('%Y-%m-%d %H:%M'):<20}")
            
            print(f"\nTotal: {len(tasks)} task(s)")
            
        except Exception as e:
            print(f"❌ Error listing tasks: {str(e)}")
    
    def show_task(self, args):
        """Show detailed task information."""
        try:
            task = self.db.get_task(args.task_id)
            if not task:
                print(f"❌ Task #{args.task_id} not found")
                return
            
            # Get channel info
            channel = self._get_channel_by_id(task.account_id)
            account_name = channel.name if channel else f"ID:{task.account_id}"
            
            # Get status text
            status_text = ['Pending', 'Completed', 'Failed', 'Processing'][task.status]
            
            print(f"\n{'='*60}")
            print(f"Task #{task.id} Details")
            print(f"{'='*60}")
            print(f"Account:        {account_name} (ID: {task.account_id})")
            print(f"Media Type:     {task.media_type}")
            print(f"Status:         {status_text}")
            print(f"Title:          {task.title}")
            print(f"Description:    {task.description or 'N/A'}")
            print(f"Keywords:       {task.keywords or 'N/A'}")
            print(f"Video Path:     {task.att_file_path}")
            print(f"Cover:          {task.cover or 'N/A'}")
            print(f"Comment:        {task.post_comment or 'N/A'}")
            print(f"Additional:     {json.dumps(task.add_info) if task.add_info else 'N/A'}")
            print(f"Scheduled:      {task.date_post}")
            print(f"Created:        {task.date_add}")
            print(f"Completed:      {task.date_done or 'N/A'}")
            print(f"Retry Count:    {task.retry_count}")
            if task.error_message:
                print(f"Error:          {task.error_message}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Error showing task: {str(e)}")
    
    def delete_task(self, args):
        """Delete a task."""
        try:
            # Check if task exists
            task = self.db.get_task(args.task_id)
            if not task:
                print(f"❌ Task #{args.task_id} not found")
                return
            
            if not args.force:
                confirm = input(f"Are you sure you want to delete task #{args.task_id}? (y/N): ")
                if confirm.lower() != 'y':
                    print("Cancelled")
                    return
            
            if self.db.delete_task(args.task_id):
                print(f"✅ Task #{args.task_id} deleted successfully")
            else:
                print(f"❌ Failed to delete task #{args.task_id}")
                
        except Exception as e:
            print(f"❌ Error deleting task: {str(e)}")
    
    def stats(self, args):
        """Show task statistics."""
        try:
            stats = self.db.get_database_stats()
            
            print(f"\n{'='*60}")
            print(f"Task Statistics")
            print(f"{'='*60}")
            print(f"Total Tasks:     {stats.get('total_tasks', 0)}")
            print(f"Pending:         {stats.get('pending_tasks', 0)}")
            print(f"Completed:       {stats.get('completed_tasks', 0)}")
            print(f"Failed:          {stats.get('failed_tasks', 0)}")
            print(f"{'='*60}")
            print(f"Total Channels:  {stats.get('total_channels', 0)}")
            print(f"Enabled:         {stats.get('enabled_channels', 0)}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Error getting stats: {str(e)}")
    
    def _get_channel_by_id(self, channel_id: int):
        """Get channel by ID."""
        try:
            query = """
                SELECT id, name, channel_id, client_id, client_secret,
                       access_token, refresh_token, token_expires_at,
                       enabled, created_at, updated_at
                FROM youtube_channels WHERE id = %s
            """
            self.db._ensure_connection()
            cursor = self.db.connection.cursor()
            cursor.execute(query, (channel_id,))
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                from core.database.mysql_db import YouTubeChannel
                return YouTubeChannel(
                    id=row[0],
                    name=row[1],
                    channel_id=row[2],
                    client_id=row[3],
                    client_secret=row[4],
                    access_token=row[5],
                    refresh_token=row[6],
                    token_expires_at=row[7],
                    enabled=bool(row[8]),
                    created_at=row[9],
                    updated_at=row[10]
                )
            return None
        except:
            return None


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Task Manager - Manage scheduled posting tasks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a new task
  python scripts/task_manager.py create \\
    --account "MyChannel" \\
    --video "/path/to/video.mp4" \\
    --title "My Video Title" \\
    --description "Video description" \\
    --keywords "tag1,tag2,tag3" \\
    --schedule "2024-01-15 18:00:00"
  
  # List pending tasks
  python scripts/task_manager.py list --status pending
  
  # Show task details
  python scripts/task_manager.py show 123
  
  # Delete a task
  python scripts/task_manager.py delete 123
  
  # Show statistics
  python scripts/task_manager.py stats
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create task command
    create_parser = subparsers.add_parser('create', help='Create a new task')
    create_parser.add_argument('--account', '-a', required=True, help='Account name or ID')
    create_parser.add_argument('--video', '-v', required=True, help='Path to video file')
    create_parser.add_argument('--title', '-t', required=True, help='Video title')
    create_parser.add_argument('--description', '-d', help='Video description')
    create_parser.add_argument('--keywords', '-k', help='Keywords/hashtags (comma-separated)')
    create_parser.add_argument('--cover', '-c', help='Path to cover/thumbnail image')
    create_parser.add_argument('--comment', help='Comment to post after upload')
    create_parser.add_argument('--schedule', '-s', help='Scheduled time (YYYY-MM-DD HH:MM:SS)')
    create_parser.add_argument('--media-type', '-m', default='youtube', help='Media type (default: youtube)')
    create_parser.add_argument('--add-info', help='Additional info as JSON string')
    
    # List tasks command
    list_parser = subparsers.add_parser('list', help='List tasks')
    list_parser.add_argument('--status', choices=['all', 'pending', 'completed', 'failed', 'processing'], 
                           default='all', help='Filter by status')
    list_parser.add_argument('--limit', '-l', type=int, default=50, help='Limit number of results')
    
    # Show task command
    show_parser = subparsers.add_parser('show', help='Show task details')
    show_parser.add_argument('task_id', type=int, help='Task ID')
    
    # Delete task command
    delete_parser = subparsers.add_parser('delete', help='Delete a task')
    delete_parser.add_argument('task_id', type=int, help='Task ID')
    delete_parser.add_argument('--force', '-f', action='store_true', help='Skip confirmation')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show task statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize CLI
    cli = TaskManagerCLI()
    
    # Execute command
    if args.command == 'create':
        cli.create_task(args)
    elif args.command == 'list':
        cli.list_tasks(args)
    elif args.command == 'show':
        cli.show_task(args)
    elif args.command == 'delete':
        cli.delete_task(args)
    elif args.command == 'stats':
        cli.stats(args)


if __name__ == '__main__':
    main()

