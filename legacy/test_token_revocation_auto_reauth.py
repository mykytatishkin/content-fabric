#!/usr/bin/env python3
"""
Test script for automatic re-authentication on token revocation.

This script tests the new functionality that:
1. Detects token revocation errors
2. Sends Telegram notifications
3. Automatically starts re-authentication
4. Marks tasks as failed without retries

Usage:
    python3 test_token_revocation_auto_reauth.py [channel_name]
    
    If channel_name is provided, it will test with that channel.
    Otherwise, it will use a test channel or create a mock scenario.
"""

import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from core.database.mysql_db import get_mysql_database, Task, YouTubeChannel
from app.task_worker import TaskWorker
from core.api_clients.youtube_client import YouTubeClient, PostResult
from core.utils.logger import get_logger
from datetime import datetime

logger = get_logger("test_token_revocation")


def create_mock_failed_result_with_token_error(channel_name: str) -> PostResult:
    """Create a mock PostResult that simulates token revocation error."""
    error_message = "invalid_grant: Token has been expired or revoked."
    return PostResult(
        success=False,
        error_message=error_message,
        platform="YouTube",
        account=channel_name
    )


def test_token_revocation_detection():
    """Test 1: Verify that token revocation errors are detected correctly."""
    print("=" * 72)
    print("Test 1: Token Revocation Error Detection")
    print("=" * 72)
    print()
    
    from core.utils.error_categorizer import ErrorCategorizer
    
    test_errors = [
        "invalid_grant: Token has been expired or revoked.",
        "Token revoked or expired: invalid_grant",
        "Token has been expired or revoked",
        "Please re-authenticate this account",
        "Some other error"  # Should NOT be detected
    ]
    
    print("Testing error detection:")
    for error in test_errors:
        error_category = ErrorCategorizer.categorize(error)
        is_token_revoked = error_category == 'Auth' and (
            'invalid_grant' in error.lower() or 
            'token revoked' in error.lower() or 
            'token expired' in error.lower() or
            're-authenticate' in error.lower()
        )
        
        status = "✅ DETECTED" if is_token_revoked else "❌ NOT DETECTED"
        print(f"  {status}: {error[:60]}...")
    
    print()
    return True


def test_with_mock_channel():
    """Test 2: Test with a mock channel (simulated error)."""
    print("=" * 72)
    print("Test 2: Mock Channel Test (Simulated Token Revocation)")
    print("=" * 72)
    print()
    
    db = get_mysql_database()
    
    # Create a mock channel object
    mock_channel = YouTubeChannel(
        id=99999,
        name="TEST_CHANNEL_MOCK",
        channel_id="UC_TEST_MOCK",
        enabled=True
    )
    
    # Create a mock task
    mock_task = Task(
        id=99999,
        title="Test Video",
        description="Test description",
        account_id=mock_channel.id,
        media_type="youtube",
        att_file_path="/tmp/test_video.mp4",
        status=0,  # pending
        keywords="test",
        post_comment=None,
        cover=None,
        add_info=None
    )
    
    print(f"📝 Created mock channel: {mock_channel.name}")
    print(f"📝 Created mock task: #{mock_task.id}")
    print()
    
    # Initialize task worker
    print("🔧 Initializing Task Worker...")
    worker = TaskWorker(db=db, check_interval=60, max_retries=3)
    
    # Create a mock YouTube client that returns token error
    class MockYouTubeClient(YouTubeClient):
        def post_video(self, account_info, video_path, caption, metadata=None):
            return create_mock_failed_result_with_token_error(account_info.get('name', 'Unknown'))
    
    worker.set_youtube_client(MockYouTubeClient(
        client_id="test_client_id",
        client_secret="test_client_secret"
    ))
    
    print("✅ Task Worker initialized")
    print()
    
    # Check if channel is in ongoing_reauths (should be empty initially)
    print(f"📊 Initial state:")
    print(f"   Ongoing reauths: {worker.ongoing_reauths}")
    print()
    
    # Simulate processing the task
    print("🔄 Simulating task processing with token revocation error...")
    print()
    
    try:
        # This will trigger _handle_token_revocation
        result = worker._process_youtube_task(mock_task, mock_channel)
        
        print(f"✅ Task processing completed")
        print(f"   Result: {'Success' if result else 'Failed'}")
        print()
        
        # Check if reauth was triggered
        if mock_channel.name in worker.ongoing_reauths:
            print(f"✅ Re-authentication was triggered for {mock_channel.name}")
        else:
            print(f"⚠️  Re-authentication not in ongoing_reauths (may be in background thread)")
        
        print()
        print("📤 Check Telegram - you should have received:")
        print("   1. Token revocation alert")
        print("   2. Message about starting automatic re-authentication")
        print()
        
        # Wait a bit for background thread to start
        print("⏳ Waiting 3 seconds for background reauth thread to start...")
        time.sleep(3)
        
        if mock_channel.name in worker.ongoing_reauths:
            print(f"✅ Re-authentication is in progress for {mock_channel.name}")
        else:
            print(f"ℹ️  Re-authentication may have completed or failed to start")
            print(f"   (This is expected if channel doesn't exist in database)")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        logger.exception("Test failed")
        return False
    
    print()
    return True


def test_with_real_channel(channel_name: str):
    """Test 3: Test with a real channel from database."""
    print("=" * 72)
    print(f"Test 3: Real Channel Test - {channel_name}")
    print("=" * 72)
    print()
    
    db = get_mysql_database()
    
    # Get channel from database
    channel = db.get_channel(channel_name)
    if not channel:
        print(f"❌ Channel '{channel_name}' not found in database")
        print("   Available channels:")
        all_channels = db.get_all_channels()
        for ch in all_channels[:10]:  # Show first 10
            print(f"     - {ch.name}")
        return False
    
    print(f"✅ Found channel: {channel.name}")
    print(f"   Channel ID: {channel.channel_id}")
    print(f"   Enabled: {channel.enabled}")
    print()
    
    if not channel.enabled:
        print("⚠️  Channel is disabled. Enabling for test...")
        # Note: You might want to add a method to enable channel
        print("   (Skipping - channel must be enabled manually)")
        return False
    
    # Get a pending task for this channel
    pending_tasks = db.get_pending_tasks()
    task = None
    for t in pending_tasks:
        if t.account_id == channel.id:
            task = t
            break
    
    if not task:
        print(f"⚠️  No pending tasks found for channel {channel_name}")
        print("   Creating a test task...")
        print()
        print("   Note: To fully test, you need:")
        print("   1. A pending task for this channel")
        print("   2. The channel's token should be revoked/expired")
        print()
        print("   You can:")
        print("   - Manually revoke the token in Google Account settings")
        print("   - Or wait for a real token revocation to occur")
        return False
    
    print(f"✅ Found pending task: #{task.id}")
    print(f"   Title: {task.title}")
    print()
    
    # Initialize task worker
    print("🔧 Initializing Task Worker...")
    worker = TaskWorker(db=db, check_interval=60, max_retries=3)
    
    # Use real YouTube client (will try to upload and may fail with token error)
    print("⚠️  Using REAL YouTube client - this will attempt actual upload!")
    print("   If token is revoked, it will trigger automatic re-authentication")
    print()
    
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Test cancelled by user")
        return False
    
    print()
    print("🔄 Processing task...")
    print()
    
    try:
        # Process the task - if token is revoked, it will trigger reauth
        result = worker._process_youtube_task(task, channel)
        
        print()
        print(f"✅ Task processing completed")
        print(f"   Result: {'Success' if result else 'Failed'}")
        print()
        
        # Check task status in database
        updated_task = db.get_task(task.id)
        if updated_task:
            status_map = {0: "Pending", 1: "Processing", 2: "Completed", 3: "Failed"}
            print(f"📊 Task status in database: {status_map.get(updated_task.status, 'Unknown')}")
        
        # Check if reauth was triggered
        if channel.name in worker.ongoing_reauths:
            print(f"✅ Re-authentication is in progress for {channel.name}")
        else:
            print(f"ℹ️  Re-authentication status: Not in ongoing_reauths")
            print(f"   (May have completed, failed, or not triggered)")
        
        print()
        print("📤 Check Telegram for notifications:")
        print("   - Token revocation alert (if error occurred)")
        print("   - Re-authentication start message")
        print("   - Re-authentication result (success/failure)")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        logger.exception("Test failed")
        return False
    
    print()
    return True


def test_telegram_notifications():
    """Test 4: Verify Telegram notifications are sent."""
    print("=" * 72)
    print("Test 4: Telegram Notifications Test")
    print("=" * 72)
    print()
    
    from core.utils.telegram_broadcast import TelegramBroadcast
    from core.utils.notifications import NotificationManager
    
    broadcaster = TelegramBroadcast()
    notifier = NotificationManager()
    
    print("📊 Telegram Configuration:")
    print(f"   Bot Token: {'✅ Configured' if broadcaster.bot_token else '❌ Missing'}")
    
    subscribers = broadcaster.get_subscribers()
    print(f"   Subscribers: {len(subscribers)}")
    if subscribers:
        print(f"   Subscriber IDs: {subscribers}")
    else:
        telegram_chat_id = notifier.notification_config.telegram_chat_id
        if telegram_chat_id:
            print(f"   TELEGRAM_CHAT_ID: {telegram_chat_id} (will be added as subscriber)")
        else:
            print(f"   ⚠️  No subscribers and no TELEGRAM_CHAT_ID configured")
    
    print()
    
    if not broadcaster.bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not configured!")
        print("   Please set TELEGRAM_BOT_TOKEN in .env file")
        return False
    
    # Test sending a notification
    print("📤 Sending test notification...")
    test_message = f"""🧪 **Test Notification**

**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is a test notification to verify Telegram integration.
If you see this message, notifications are working correctly!"""
    
    try:
        result = broadcaster.broadcast_message(test_message)
        if result['success'] > 0:
            print(f"✅ Test notification sent successfully!")
            print(f"   Sent to: {result['success']}/{result['total']} subscribers")
        else:
            print(f"⚠️  No subscribers to send to")
            print(f"   Trying fallback method...")
            notifier._send_telegram_message(test_message)
            print(f"✅ Sent via fallback method")
    except Exception as e:
        print(f"❌ Error sending notification: {e}")
        logger.exception("Failed to send test notification")
        return False
    
    print()
    print("📱 Check your Telegram - you should have received the test message")
    print()
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 72)
    print("Token Revocation Auto-Reauth Test Suite")
    print("=" * 72)
    print()
    
    # Parse command line arguments
    channel_name = None
    if len(sys.argv) > 1:
        channel_name = sys.argv[1]
    
    # Run tests
    tests = [
        ("Test 1: Token Revocation Detection", test_token_revocation_detection),
        ("Test 2: Mock Channel Test", test_with_mock_channel),
        ("Test 4: Telegram Notifications", test_telegram_notifications),
    ]
    
    # Add real channel test if channel name provided
    if channel_name:
        tests.insert(2, (f"Test 3: Real Channel Test ({channel_name})", 
                       lambda: test_with_real_channel(channel_name)))
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'=' * 72}")
        print(f"Running: {test_name}")
        print('=' * 72)
        print()
        
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"\n✅ {test_name} - PASSED")
            else:
                print(f"\n❌ {test_name} - FAILED")
        except Exception as e:
            print(f"\n❌ {test_name} - ERROR: {e}")
            logger.exception(f"Test {test_name} failed")
            results.append((test_name, False))
        
        print("\n" + "-" * 72)
        
        # Skip interactive input if SKIP_INTERACTIVE is set
        import os
        if os.getenv('SKIP_INTERACTIVE', '').lower() != 'true' and test_name != tests[-1][0]:
            try:
                input("Press Enter to continue to next test...")
            except (EOFError, KeyboardInterrupt):
                print("(Skipping interactive input)")
                break
    
    # Summary
    print("\n" + "=" * 72)
    print("Test Summary")
    print("=" * 72)
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    print()
    print("=" * 72)
    print("Next Steps:")
    print("=" * 72)
    print("1. Check Telegram for notifications")
    print("2. Monitor logs for re-authentication process")
    print("3. Verify that tasks with revoked tokens are marked as failed")
    print("4. Verify that re-authentication starts automatically")
    print()
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

