#!/usr/bin/env python3
"""
Run Daily Report - Send Telegram report for yesterday's tasks.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.utils.daily_report import DailyReportManager
from core.utils.logger import get_logger


def main():
    """Main function to run daily report."""
    logger = get_logger("run_daily_report")
    
    print("=" * 60)
    print("Daily Report System - Telegram Notifications")
    print("=" * 60)
    print()
    
    try:
        report_manager = DailyReportManager()
        
        # Check command line arguments
        if len(sys.argv) > 1 and sys.argv[1] == 'test':
            print("🧪 Running in TEST mode - sending test report...")
            success = report_manager.send_test_report()
        else:
            print("📊 Generating daily report for yesterday...")
            success = report_manager.generate_and_send_daily_report()
        
        print()
        if success:
            print("✅ Daily report sent successfully!")
            logger.info("Daily report completed successfully")
            return 0
        else:
            print("❌ Failed to send daily report")
            logger.error("Daily report failed")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        logger.error(f"Fatal error in daily report: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

