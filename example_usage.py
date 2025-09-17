#!/usr/bin/env python3
"""
Example usage of the Social Media Auto-Poster system.
This script demonstrates how to use the system programmatically.
"""

import sys
import os
from datetime import datetime, timedelta

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.auto_poster import SocialMediaAutoPoster


def example_immediate_posting():
    """Example of posting content immediately."""
    print("🚀 Example: Immediate Posting")
    print("=" * 50)
    
    # Initialize the auto-poster
    auto_poster = SocialMediaAutoPoster()
    
    # Post content immediately
    result = auto_poster.post_immediately(
        content_path="content/videos/example_video.mp4",
        platforms=["instagram", "tiktok", "youtube"],
        caption="Check out this amazing content! #shorts #viral #trending",
        accounts=["account1", "account2"],  # Optional: specify accounts
        metadata={
            "privacy_level": "public",
            "disable_comment": False,
            "disable_duet": False
        }
    )
    
    print(f"✅ Successful posts: {result['successful_posts']}")
    print(f"❌ Failed posts: {result['failed_posts']}")
    
    for res in result['results']:
        status = "✅" if res['success'] else "❌"
        print(f"{status} {res['platform']} ({res['account']}): {res.get('post_id', res.get('error'))}")


def example_scheduling():
    """Example of scheduling posts."""
    print("\n📅 Example: Scheduling Posts")
    print("=" * 50)
    
    auto_poster = SocialMediaAutoPoster()
    
    # Schedule for specific time
    specific_time = datetime.now() + timedelta(hours=2)
    post_ids = auto_poster.schedule_post(
        content_path="content/videos/example_video.mp4",
        platforms=["instagram", "tiktok"],
        caption="Scheduled post coming up! #scheduled #content",
        scheduled_time=specific_time,
        accounts=["account1"]
    )
    
    print(f"📝 Scheduled {len(post_ids)} posts:")
    for post_id in post_ids:
        print(f"  - {post_id}")
    
    # Schedule with random timing
    random_post_ids = auto_poster.schedule_post(
        content_path="content/videos/another_video.mp4",
        platforms=["youtube"],
        caption="Random timing post! #random #shorts"
    )
    
    print(f"🎲 Scheduled {len(random_post_ids)} posts with random timing")


def example_scheduler_management():
    """Example of managing the scheduler."""
    print("\n⏰ Example: Scheduler Management")
    print("=" * 50)
    
    auto_poster = SocialMediaAutoPoster()
    
    # Get scheduled posts
    scheduled_posts = auto_poster.get_scheduled_posts()
    print(f"📋 Total scheduled posts: {len(scheduled_posts)}")
    
    # Get posts for specific platform
    instagram_posts = auto_poster.get_scheduled_posts(platform="instagram")
    print(f"📱 Instagram posts: {len(instagram_posts)}")
    
    # Get posting statistics
    stats = auto_poster.get_posting_stats()
    print(f"📊 Statistics:")
    print(f"  - Total scheduled: {stats['total_scheduled']}")
    print(f"  - Completed: {stats['total_completed']}")
    print(f"  - Failed: {stats['total_failed']}")
    
    # Cancel a post (example)
    if scheduled_posts:
        post_to_cancel = scheduled_posts[0]
        if auto_poster.cancel_post(post_to_cancel.id):
            print(f"🚫 Cancelled post: {post_to_cancel.id}")


def example_account_validation():
    """Example of validating accounts."""
    print("\n🔐 Example: Account Validation")
    print("=" * 50)
    
    auto_poster = SocialMediaAutoPoster()
    
    # Validate all accounts
    validation_results = auto_poster.validate_accounts()
    
    for platform, accounts in validation_results.items():
        print(f"\n📱 {platform.title()}:")
        for account in accounts:
            status = "✅ Valid" if account['valid'] else "❌ Invalid"
            print(f"  {status} {account['name']}")


def example_notifications():
    """Example of testing notifications."""
    print("\n📧 Example: Notification Testing")
    print("=" * 50)
    
    auto_poster = SocialMediaAutoPoster()
    
    # Test notifications
    results = auto_poster.test_notifications()
    
    for channel, success in results.items():
        status = "✅ Success" if success else "❌ Failed"
        print(f"{status} {channel.title()} notifications")


def example_system_status():
    """Example of checking system status."""
    print("\n📊 Example: System Status")
    print("=" * 50)
    
    auto_poster = SocialMediaAutoPoster()
    
    # Get system status
    status = auto_poster.get_system_status()
    
    print("🔌 API Clients:")
    for platform, connected in status['api_clients'].items():
        status_emoji = "✅" if connected else "❌"
        print(f"  {status_emoji} {platform.title()}")
    
    print(f"\n⏰ Scheduler: {'✅ Running' if status['scheduler_running'] else '❌ Stopped'}")
    print(f"📋 Scheduled Posts: {status['scheduled_posts_count']}")
    print(f"⚙️ Configuration: {'✅ Loaded' if status['config_loaded'] else '❌ Failed'}")


def example_content_processing():
    """Example of content processing."""
    print("\n🎬 Example: Content Processing")
    print("=" * 50)
    
    from src.content_processor import ContentProcessor
    
    processor = ContentProcessor()
    
    # Process content for multiple platforms
    processed_files = processor.process_content(
        input_path="content/videos/example_video.mp4",
        platforms=["instagram", "tiktok", "youtube"],
        caption="Processed content example!",
        metadata={
            "add_captions": True,
            "add_watermark": False
        }
    )
    
    print("📁 Processed files:")
    for platform, file_path in processed_files.items():
        print(f"  {platform}: {file_path}")
        
        # Validate processed content
        is_valid = processor.validate_processed_content(file_path, platform)
        status = "✅ Valid" if is_valid else "❌ Invalid"
        print(f"    {status}")


def main():
    """Run all examples."""
    print("🎯 Social Media Auto-Poster - Usage Examples")
    print("=" * 60)
    
    try:
        # Run examples
        example_immediate_posting()
        example_scheduling()
        example_scheduler_management()
        example_account_validation()
        example_notifications()
        example_system_status()
        example_content_processing()
        
        print("\n✅ All examples completed successfully!")
        print("\n💡 To run the scheduler daemon:")
        print("   python main.py start-scheduler")
        
    except Exception as e:
        print(f"\n❌ Example failed: {str(e)}")
        print("Make sure you have:")
        print("1. Configured config.yaml")
        print("2. Set up API credentials in .env")
        print("3. Added sample content files")


if __name__ == '__main__':
    main()

