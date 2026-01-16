#!/usr/bin/env python3
"""
Simple Daily Report Loop - Запускається один раз і працює постійно.

Перевіряє кожну годину чи настав час для звіту (12:00 Київ).
Якщо так - відправляє звіт і чекає наступного дня.
"""

import time
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pytz
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.utils.daily_report import send_daily_report
from core.utils.logger import get_logger

# Київський час
KYIV_TZ = pytz.timezone('Europe/Kiev')
REPORT_HOUR = 12  # Час розсилки (12:00)

logger = get_logger("daily_report_loop")


def main():
    """Головний цикл."""
    print("="*60)
    print("Daily Report Loop - Starting...")
    print("="*60)
    print(f"📅 Report time: {REPORT_HOUR}:00 (Kyiv)")
    print(f"🔄 Check interval: every hour")
    print(f"📱 Delivery: Telegram broadcast")
    print()
    print("Press Ctrl+C to stop")
    print("="*60)
    print()
    
    last_report_date = None  # Дата останнього звіту
    
    while True:
        try:
            # Поточний час за Києвом
            now = datetime.now(KYIV_TZ)
            today = now.date()
            current_hour = now.hour
            
            print(f"⏰ Current time (Kyiv): {now.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Перевірка: чи настав час для звіту
            if current_hour >= REPORT_HOUR and last_report_date != today:
                print(f"\n{'='*60}")
                print(f"🚀 Time to send daily report!")
                print(f"{'='*60}\n")
                
                try:
                    success = send_daily_report()
                    
                    if success:
                        last_report_date = today
                        logger.info(f"Daily report sent successfully for {today}")
                        print(f"✅ Report sent successfully!")
                        print(f"📅 Next report: tomorrow at {REPORT_HOUR}:00\n")
                    else:
                        logger.error("Failed to send daily report")
                        print(f"❌ Failed to send report. Will retry in 1 hour.\n")
                        
                except Exception as e:
                    logger.error(f"Error sending report: {str(e)}", exc_info=True)
                    print(f"❌ Error: {str(e)}\n")
            
            elif last_report_date == today:
                print(f"✅ Report already sent today. Next: tomorrow at {REPORT_HOUR}:00")
            else:
                hours_until = REPORT_HOUR - current_hour
                print(f"⏳ Waiting... Report in {hours_until} hours (at {REPORT_HOUR}:00)")
            
            # Спати 1 годину
            print(f"😴 Sleeping for 1 hour...\n")
            time.sleep(3600)  # 3600 секунд = 1 година
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Stopped by user")
            logger.info("Daily report loop stopped by user")
            break
            
        except Exception as e:
            logger.error(f"Unexpected error in loop: {str(e)}", exc_info=True)
            print(f"\n❌ Unexpected error: {str(e)}")
            print("⏳ Retrying in 1 hour...\n")
            time.sleep(3600)


if __name__ == "__main__":
    main()

