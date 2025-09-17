#!/usr/bin/env python3
"""
Social Media Auto-Poster - Main CLI Interface

A comprehensive tool for automatically posting content to Instagram, TikTok, and YouTube Shorts
with support for scheduling, content optimization, and multi-account management.
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
import json
import yaml

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.auto_poster import SocialMediaAutoPoster
from src.logger import get_logger


def setup_directories():
    """Create necessary directories."""
    directories = [
        'content/videos',
        'content/descriptions', 
        'content/thumbnails',
        'content/processed',
        'logs'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    print("✅ Created necessary directories")


def validate_config():
    """Validate configuration file."""
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        print(f"❌ Configuration file not found: {config_path}")
        print("Please copy config.yaml.example to config.yaml and configure it.")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Basic validation
        required_sections = ['platforms', 'accounts', 'schedule']
        for section in required_sections:
            if section not in config:
                print(f"❌ Missing required configuration section: {section}")
                return False
        
        print("✅ Configuration file is valid")
        return True
        
    except Exception as e:
        print(f"❌ Configuration file error: {str(e)}")
        return False


def cmd_post(args):
    """Handle immediate posting command."""
    try:
        auto_poster = SocialMediaAutoPoster()
        
        # Validate content file
        if not os.path.exists(args.content):
            print(f"❌ Content file not found: {args.content}")
            return 1
        
        # Parse platforms
        platforms = [p.strip() for p in args.platforms.split(',')]
        
        # Parse accounts if provided
        accounts = None
        if args.accounts:
            accounts = [a.strip() for a in args.accounts.split(',')]
        
        # Parse metadata if provided
        metadata = None
        if args.metadata:
            try:
                metadata = json.loads(args.metadata)
            except json.JSONDecodeError:
                print("❌ Invalid JSON in metadata")
                return 1
        
        print(f"🚀 Posting content to {', '.join(platforms)}...")
        
        result = auto_poster.post_immediately(
            content_path=args.content,
            platforms=platforms,
            caption=args.caption,
            accounts=accounts,
            metadata=metadata
        )
        
        print(f"✅ Posted successfully: {result['successful_posts']}")
        print(f"❌ Failed posts: {result['failed_posts']}")
        
        # Show detailed results
        for res in result['results']:
            status = "✅" if res['success'] else "❌"
            print(f"  {status} {res['platform']} ({res['account']}): {res.get('post_id', res.get('error', 'Unknown'))}")
        
        return 0 if result['failed_posts'] == 0 else 1
        
    except Exception as e:
        print(f"❌ Posting failed: {str(e)}")
        return 1


def cmd_schedule(args):
    """Handle scheduling command."""
    try:
        auto_poster = SocialMediaAutoPoster()
        
        # Validate content file
        if not os.path.exists(args.content):
            print(f"❌ Content file not found: {args.content}")
            return 1
        
        # Parse platforms
        platforms = [p.strip() for p in args.platforms.split(',')]
        
        # Parse accounts if provided
        accounts = None
        if args.accounts:
            accounts = [a.strip() for a in args.accounts.split(',')]
        
        # Parse scheduled time if provided
        scheduled_time = None
        if args.time:
            try:
                scheduled_time = datetime.fromisoformat(args.time)
            except ValueError:
                print("❌ Invalid time format. Use ISO format: YYYY-MM-DDTHH:MM:SS")
                return 1
        
        # Parse metadata if provided
        metadata = None
        if args.metadata:
            try:
                metadata = json.loads(args.metadata)
            except json.JSONDecodeError:
                print("❌ Invalid JSON in metadata")
                return 1
        
        print(f"📅 Scheduling content for {', '.join(platforms)}...")
        
        post_ids = auto_poster.schedule_post(
            content_path=args.content,
            platforms=platforms,
            caption=args.caption,
            scheduled_time=scheduled_time,
            accounts=accounts,
            metadata=metadata
        )
        
        print(f"✅ Scheduled {len(post_ids)} posts")
        for post_id in post_ids:
            print(f"  📝 {post_id}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Scheduling failed: {str(e)}")
        return 1


def cmd_list_scheduled(args):
    """Handle list scheduled posts command."""
    try:
        auto_poster = SocialMediaAutoPoster()
        
        posts = auto_poster.get_scheduled_posts(
            platform=args.platform,
            account=args.account
        )
        
        if not posts:
            print("📭 No scheduled posts found")
            return 0
        
        print(f"📋 Found {len(posts)} scheduled posts:")
        print()
        
        for post in posts:
            status_emoji = {
                'scheduled': '⏰',
                'posting': '🚀',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '🚫'
            }.get(post.status, '❓')
            
            print(f"{status_emoji} {post.id}")
            print(f"   Platform: {post.platform}")
            print(f"   Account: {post.account}")
            print(f"   Scheduled: {post.scheduled_time}")
            print(f"   Status: {post.status}")
            print(f"   Content: {post.content_path}")
            print()
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to list scheduled posts: {str(e)}")
        return 1


def cmd_cancel(args):
    """Handle cancel post command."""
    try:
        auto_poster = SocialMediaAutoPoster()
        
        if auto_poster.cancel_post(args.post_id):
            print(f"✅ Cancelled post: {args.post_id}")
            return 0
        else:
            print(f"❌ Post not found: {args.post_id}")
            return 1
        
    except Exception as e:
        print(f"❌ Failed to cancel post: {str(e)}")
        return 1


def cmd_start_scheduler(args):
    """Handle start scheduler command."""
    try:
        auto_poster = SocialMediaAutoPoster()
        auto_poster.start_scheduler()
        
        print("🚀 Scheduler started successfully")
        print("Press Ctrl+C to stop the scheduler")
        
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping scheduler...")
            auto_poster.stop_scheduler()
            print("✅ Scheduler stopped")
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to start scheduler: {str(e)}")
        return 1


def cmd_validate_accounts(args):
    """Handle validate accounts command."""
    try:
        auto_poster = SocialMediaAutoPoster()
        
        print("🔐 Validating accounts...")
        results = auto_poster.validate_accounts()
        
        for platform, accounts in results.items():
            print(f"\n📱 {platform.title()}:")
            for account in accounts:
                status = "✅ Valid" if account['valid'] else "❌ Invalid"
                print(f"  {status} {account['name']}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Account validation failed: {str(e)}")
        return 1


def cmd_test_notifications(args):
    """Handle test notifications command."""
    try:
        auto_poster = SocialMediaAutoPoster()
        
        print("📧 Testing notifications...")
        results = auto_poster.test_notifications()
        
        for channel, success in results.items():
            status = "✅ Success" if success else "❌ Failed"
            print(f"  {status} {channel.title()}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Notification test failed: {str(e)}")
        return 1


def cmd_status(args):
    """Handle status command."""
    try:
        auto_poster = SocialMediaAutoPoster()
        
        print("📊 System Status:")
        print()
        
        status = auto_poster.get_system_status()
        
        # API Clients
        print("🔌 API Clients:")
        for platform, connected in status['api_clients'].items():
            status_emoji = "✅" if connected else "❌"
            print(f"  {status_emoji} {platform.title()}")
        
        # Scheduler
        print(f"\n⏰ Scheduler: {'✅ Running' if status['scheduler_running'] else '❌ Stopped'}")
        
        # Notifications
        print("\n📧 Notifications:")
        notif_status = status['notification_status']
        print(f"  Telegram: {'✅ Enabled' if notif_status['telegram_enabled'] else '❌ Disabled'}")
        print(f"  Email: {'✅ Enabled' if notif_status['email_enabled'] else '❌ Disabled'}")
        
        # Scheduled Posts
        print(f"\n📋 Scheduled Posts: {status['scheduled_posts_count']}")
        
        # Configuration
        print(f"\n⚙️ Configuration: {'✅ Loaded' if status['config_loaded'] else '❌ Failed'}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Status check failed: {str(e)}")
        return 1


def cmd_stats(args):
    """Handle stats command."""
    try:
        auto_poster = SocialMediaAutoPoster()
        
        print("📈 Posting Statistics:")
        print()
        
        stats = auto_poster.get_posting_stats()
        
        print(f"Total Scheduled: {stats['total_scheduled']}")
        print(f"Completed: {stats['total_completed']}")
        print(f"Failed: {stats['total_failed']}")
        print(f"Cancelled: {stats['total_cancelled']}")
        
        if stats['total_scheduled'] > 0:
            success_rate = (stats['total_completed'] / stats['total_scheduled']) * 100
            print(f"Success Rate: {success_rate:.1f}%")
        
        # By platform
        if stats['by_platform']:
            print("\nBy Platform:")
            for platform, platform_stats in stats['by_platform'].items():
                print(f"  {platform.title()}: {platform_stats['completed']}/{platform_stats['scheduled']} ({platform_stats['failed']} failed)")
        
        return 0
        
    except Exception as e:
        print(f"❌ Stats retrieval failed: {str(e)}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Social Media Auto-Poster - Automate posting to Instagram, TikTok, and YouTube Shorts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Post immediately to all platforms
  python main.py post --content video.mp4 --caption "Check this out!" --platforms "instagram,tiktok,youtube"
  
  # Schedule a post for specific time
  python main.py schedule --content video.mp4 --caption "Coming soon!" --platforms "instagram,tiktok" --time "2024-01-15T18:00:00"
  
  # Start the scheduler daemon
  python main.py start-scheduler
  
  # List scheduled posts
  python main.py list-scheduled
  
  # Validate all accounts
  python main.py validate-accounts
  
  # Test notifications
  python main.py test-notifications
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Post command
    post_parser = subparsers.add_parser('post', help='Post content immediately')
    post_parser.add_argument('--content', required=True, help='Path to content file')
    post_parser.add_argument('--caption', required=True, help='Post caption')
    post_parser.add_argument('--platforms', required=True, help='Comma-separated platforms (instagram,tiktok,youtube)')
    post_parser.add_argument('--accounts', help='Comma-separated account names (optional)')
    post_parser.add_argument('--metadata', help='JSON metadata (optional)')
    
    # Schedule command
    schedule_parser = subparsers.add_parser('schedule', help='Schedule content for posting')
    schedule_parser.add_argument('--content', required=True, help='Path to content file')
    schedule_parser.add_argument('--caption', required=True, help='Post caption')
    schedule_parser.add_argument('--platforms', required=True, help='Comma-separated platforms (instagram,tiktok,youtube)')
    schedule_parser.add_argument('--time', help='Specific time (ISO format: YYYY-MM-DDTHH:MM:SS)')
    schedule_parser.add_argument('--accounts', help='Comma-separated account names (optional)')
    schedule_parser.add_argument('--metadata', help='JSON metadata (optional)')
    
    # List scheduled command
    list_parser = subparsers.add_parser('list-scheduled', help='List scheduled posts')
    list_parser.add_argument('--platform', help='Filter by platform')
    list_parser.add_argument('--account', help='Filter by account')
    
    # Cancel command
    cancel_parser = subparsers.add_parser('cancel', help='Cancel a scheduled post')
    cancel_parser.add_argument('--post-id', required=True, help='Post ID to cancel')
    
    # Start scheduler command
    subparsers.add_parser('start-scheduler', help='Start the posting scheduler daemon')
    
    # Validate accounts command
    subparsers.add_parser('validate-accounts', help='Validate all configured accounts')
    
    # Test notifications command
    subparsers.add_parser('test-notifications', help='Test notification channels')
    
    # Status command
    subparsers.add_parser('status', help='Show system status')
    
    # Stats command
    subparsers.add_parser('stats', help='Show posting statistics')
    
    # Setup command
    subparsers.add_parser('setup', help='Setup directories and validate configuration')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Handle setup command
    if args.command == 'setup':
        print("🔧 Setting up Social Media Auto-Poster...")
        setup_directories()
        if validate_config():
            print("✅ Setup completed successfully!")
            return 0
        else:
            print("❌ Setup failed. Please check your configuration.")
            return 1
    
    # Validate configuration for other commands
    if not validate_config():
        return 1
    
    # Route to appropriate command handler
    command_handlers = {
        'post': cmd_post,
        'schedule': cmd_schedule,
        'list-scheduled': cmd_list_scheduled,
        'cancel': cmd_cancel,
        'start-scheduler': cmd_start_scheduler,
        'validate-accounts': cmd_validate_accounts,
        'test-notifications': cmd_test_notifications,
        'status': cmd_status,
        'stats': cmd_stats
    }
    
    handler = command_handlers.get(args.command)
    if handler:
        return handler(args)
    else:
        print(f"❌ Unknown command: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())


