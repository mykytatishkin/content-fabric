#!/usr/bin/env python3
"""
Daily Report Scheduler - Automatically sends Telegram reports at 12:00 daily.

This script runs continuously and triggers the daily report at the scheduled time.
"""

import schedule
import time
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.utils.daily_report import send_daily_report
from core.utils.logger import get_logger


def scheduled_daily_report():
    """Function called by scheduler to send daily report."""
    logger = get_logger("daily_report_scheduler")
    
    try:
        print(f"\n{'='*60}")
        print(f"Running Daily Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        success = send_daily_report()
        
        if success:
            logger.info("Scheduled daily report completed successfully")
            print("✅ Daily report sent successfully!\n")
        else:
            logger.error("Scheduled daily report failed")
            print("❌ Daily report failed!\n")
            
    except Exception as e:
        logger.error(f"Error in scheduled daily report: {str(e)}", exc_info=True)
        print(f"❌ Error: {str(e)}\n")


def main():
    """Main function to run the scheduler."""
    logger = get_logger("daily_report_scheduler")
    
    print("=" * 60)
    print("Daily Report Scheduler - Starting...")
    print("=" * 60)
    print()
    print("📅 Scheduled Time: 12:00 daily")
    print("📊 Report: Yesterday's task summary by platform")
    print("📱 Delivery: Telegram notifications")
    print()
    print("Press Ctrl+C to stop the scheduler")
    print("=" * 60)
    print()
    
    # Schedule the daily report at 12:00
    schedule.every().day.at("12:00").do(scheduled_daily_report)
    
    logger.info("Daily report scheduler started - will run at 12:00 daily")
    
    # Show next run time
    next_run = schedule.next_run()
    if next_run:
        print(f"⏰ Next report scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Scheduler stopped by user")
        logger.info("Daily report scheduler stopped")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Scheduler error: {str(e)}")
        logger.error(f"Fatal error in scheduler: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

