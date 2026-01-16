#!/usr/bin/env python3
"""
Test script for Telegram notifications in reauth system.
Tests that notifications are sent when authorization problems occur.
"""

from __future__ import annotations

import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from core.auth.reauth.models import ReauthResult, ReauthStatus
from core.auth.reauth.service import ServiceConfig, YouTubeReauthService
from core.database.mysql_db import get_mysql_database
from core.utils.logger import get_logger

LOGGER = get_logger("test_reauth_telegram")


def test_notification_with_fake_error():
    """Test notification with a fake error result."""
    print("=" * 72)
    print("Testing Telegram Notifications for Reauth Errors")
    print("=" * 72)
    print()
    
    db = get_mysql_database()
    service_config = ServiceConfig()
    service = YouTubeReauthService(db=db, service_config=service_config, use_broadcast=True)
    
    # Create a fake failed result
    test_result = ReauthResult(
        channel_name="TEST_CHANNEL",
        status=ReauthStatus.FAILED,
        error="Test error: Credentials not configured",
    )
    
    print(f"📝 Creating test error notification for channel: {test_result.channel_name}")
    print(f"   Status: {test_result.status.value}")
    print(f"   Error: {test_result.error}")
    print()
    
    # Send notification
    print("📤 Sending Telegram notification...")
    try:
        service._send_reauth_error_notification(test_result)
        print("✅ Notification sent successfully!")
        print()
        print("Проверьте Telegram - должно прийти сообщение об ошибке авторизации.")
    except Exception as e:
        print(f"❌ Error sending notification: {e}")
        LOGGER.exception("Failed to send test notification")
        return False
    
    return True


def test_notification_with_mfa_error():
    """Test notification with MFA challenge error."""
    print("=" * 72)
    print("Testing Telegram Notifications for MFA Challenge")
    print("=" * 72)
    print()
    
    db = get_mysql_database()
    service_config = ServiceConfig()
    service = YouTubeReauthService(db=db, service_config=service_config, use_broadcast=True)
    
    # Create a fake MFA challenge result
    test_result = ReauthResult(
        channel_name="TEST_CHANNEL_MFA",
        status=ReauthStatus.FAILED,
        error="Security challenge detected: Google запрашивает код подтверждения на телефон",
    )
    
    print(f"📝 Creating test MFA notification for channel: {test_result.channel_name}")
    print(f"   Status: {test_result.status.value}")
    print(f"   Error: {test_result.error}")
    print()
    
    # Send notification
    print("📤 Sending Telegram notification...")
    try:
        service._send_reauth_error_notification(test_result)
        print("✅ Notification sent successfully!")
        print()
        print("Проверьте Telegram - должно прийти сообщение о MFA challenge.")
    except Exception as e:
        print(f"❌ Error sending notification: {e}")
        LOGGER.exception("Failed to send test notification")
        return False
    
    return True


def test_with_real_channel_error():
    """Test with a real channel that doesn't exist (will cause error)."""
    print("=" * 72)
    print("Testing with Non-Existent Channel (Real Error)")
    print("=" * 72)
    print()
    
    db = get_mysql_database()
    service_config = ServiceConfig()
    service = YouTubeReauthService(db=db, service_config=service_config, use_broadcast=True)
    
    # Try to reauth a channel that doesn't exist
    fake_channel = "NON_EXISTENT_CHANNEL_12345"
    print(f"📝 Attempting reauth for non-existent channel: {fake_channel}")
    print("   This should trigger a credentials error and send notification.")
    print()
    
    try:
        results = service.run_sync([fake_channel])
        
        if results:
            result = results[0]
            print(f"✅ Reauth completed with status: {result.status.value}")
            if result.error:
                print(f"   Error: {result.error}")
            
            if result.status != ReauthStatus.SUCCESS:
                print()
                print("📤 Notification should have been sent to Telegram.")
                print("   Check your Telegram for the error message.")
        else:
            print("⚠️  No results returned")
            
    except Exception as e:
        print(f"❌ Error during reauth: {e}")
        LOGGER.exception("Failed to test reauth")
        return False
    
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 72)
    print("Telegram Notifications Test Suite for Reauth System")
    print("=" * 72)
    print()
    
    # Check Telegram configuration
    from core.utils.telegram_broadcast import TelegramBroadcast
    broadcaster = TelegramBroadcast()
    
    if not broadcaster.bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not configured!")
        print("   Please set TELEGRAM_BOT_TOKEN in .env file")
        return 1
    
    subscribers = broadcaster.get_subscribers()
    print(f"📊 Telegram Configuration:")
    print(f"   Bot Token: {'✅ Configured' if broadcaster.bot_token else '❌ Missing'}")
    print(f"   Subscribers: {len(subscribers)}")
    if subscribers:
        print(f"   Subscriber IDs: {subscribers}")
    print()
    
    # Run tests
    tests = [
        ("Test 1: Fake Error Notification", test_notification_with_fake_error),
        ("Test 2: MFA Challenge Notification", test_notification_with_mfa_error),
        ("Test 3: Real Channel Error", test_with_real_channel_error),
    ]
    
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
            LOGGER.exception(f"Test {test_name} failed")
            results.append((test_name, False))
        
        print("\n" + "-" * 72)
        # Skip interactive input in automated mode
        import os
        if os.getenv('SKIP_INTERACTIVE', '').lower() != 'true':
            try:
                input("Press Enter to continue to next test...")
            except EOFError:
                print("(Skipping interactive input)")
    
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
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

