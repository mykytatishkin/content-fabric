#!/usr/bin/env python3
"""
Daily Telegram Report System for scheduled tasks.
Sends daily summary of yesterday's tasks grouped by platform and account.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
from dataclasses import dataclass

from core.database.mysql_db import YouTubeMySQLDatabase, Task
from core.utils.notifications import NotificationManager
from core.utils.telegram_broadcast import TelegramBroadcast
from core.utils.logger import get_logger


@dataclass
class AccountReport:
    """Report data for a single account."""
    account_id: int
    account_name: str
    channel_id: str  # @username or channel link
    task_ids: List[int]  # All task IDs for reference
    total_scheduled: int
    total_completed: int
    total_failed: int
    
    @property
    def error_count(self) -> int:
        """Number of failed tasks."""
        return self.total_failed
    
    @property
    def success_count(self) -> int:
        """Number of completed tasks."""
        return self.total_completed


@dataclass
class PlatformReport:
    """Report data for a platform."""
    platform: str
    accounts: List[AccountReport]
    
    @property
    def total_tasks(self) -> int:
        """Total tasks across all accounts."""
        return sum(acc.total_scheduled for acc in self.accounts)


class DailyReportManager:
    """Manages daily Telegram reports for tasks."""
    
    def __init__(self, db: Optional[YouTubeMySQLDatabase] = None, 
                 notification_manager: Optional[NotificationManager] = None,
                 use_broadcast: bool = True):
        """
        Initialize Daily Report Manager.
        
        Args:
            db: MySQL database instance
            notification_manager: Notification manager for Telegram
            use_broadcast: If True, use broadcast to all subscribers. If False, use single chat_id
        """
        self.db = db or YouTubeMySQLDatabase()
        self.notifier = notification_manager or NotificationManager(config_path="config/config.yaml")
        self.broadcaster = TelegramBroadcast() if use_broadcast else None
        self.use_broadcast = use_broadcast
        self.logger = get_logger("daily_report")
    
    def generate_and_send_daily_report(self, date: Optional[datetime] = None) -> bool:
        """
        Generate and send daily report for specified date (default: yesterday).
        
        Args:
            date: Date to generate report for (defaults to yesterday)
            
        Returns:
            True if reports were sent successfully, False otherwise
        """
        try:
            # Default to yesterday
            if date is None:
                date = datetime.now() - timedelta(days=1)
            
            # Get tasks for the specified date
            tasks = self._get_tasks_for_date(date)
            
            if not tasks:
                self.logger.info(f"No tasks found for {date.strftime('%Y-%m-%d')}")
                return True
            
            # Group tasks by platform
            platform_reports = self._group_tasks_by_platform(tasks)
            
            # Автоматично синхронізувати нових користувачів перед розсилкою
            if self.use_broadcast and self.broadcaster:
                new_users = self.broadcaster.process_start_commands()
                if new_users > 0:
                    self.logger.info(f"Auto-added {new_users} new users before broadcast")
            
            # Send separate report for each platform
            for platform_name, platform_report in platform_reports.items():
                message = self._format_platform_report(platform_report, date)
                self._send_telegram_message(message)
                self.logger.info(f"Sent daily report for platform: {platform_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error generating daily report: {str(e)}", exc_info=True)
            return False
    
    def _get_tasks_for_date(self, date: datetime) -> List[Task]:
        """
        Get all tasks for a specific date.
        
        Args:
            date: Date to get tasks for
            
        Returns:
            List of tasks for that date
        """
        try:
            # Get start and end of the day
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Query tasks for the date
            query = """
                SELECT id, account_id, media_type, status, date_add, att_file_path,
                       cover, title, description, keywords, post_comment, add_info,
                       date_post, date_done, upload_id
                FROM tasks 
                WHERE date_post >= %s AND date_post <= %s
                ORDER BY account_id, media_type
            """
            
            results = self.db._execute_query(query, (start_of_day, end_of_day), fetch=True)
            
            if not results:
                return []
            
            tasks = [self.db._row_to_task(row) for row in results]
            return tasks
            
        except Exception as e:
            self.logger.error(f"Error getting tasks for date {date}: {str(e)}")
            return []
    
    def _group_tasks_by_platform(self, tasks: List[Task]) -> Dict[str, PlatformReport]:
        """
        Group tasks by platform and account.
        
        Args:
            tasks: List of tasks
            
        Returns:
            Dictionary mapping platform name to PlatformReport
        """
        # Group by platform -> account_id
        platform_data = defaultdict(lambda: defaultdict(list))
        
        for task in tasks:
            platform_data[task.media_type][task.account_id].append(task)
        
        # Build platform reports
        platform_reports = {}
        
        for platform, accounts_data in platform_data.items():
            account_reports = []
            
            for account_id, account_tasks in accounts_data.items():
                # Get account details from database
                account_info = self._get_account_info(account_id)
                
                # Count task statuses
                completed = sum(1 for t in account_tasks if t.status == 1)
                failed = sum(1 for t in account_tasks if t.status == 2)
                total = len(account_tasks)
                
                # Get task IDs
                task_ids = [t.id for t in account_tasks]
                
                account_report = AccountReport(
                    account_id=account_id,
                    account_name=account_info.get('name', f'Unknown-{account_id}'),
                    channel_id=account_info.get('channel_id', f'ID-{account_id}'),
                    task_ids=task_ids,
                    total_scheduled=total,
                    total_completed=completed,
                    total_failed=failed
                )
                
                account_reports.append(account_report)
            
            # Sort accounts by ID for consistent ordering
            account_reports.sort(key=lambda x: x.account_id)
            
            platform_reports[platform] = PlatformReport(
                platform=platform,
                accounts=account_reports
            )
        
        return platform_reports
    
    def _get_account_info(self, account_id: int) -> Dict[str, str]:
        """
        Get account information from database.
        
        Args:
            account_id: Account ID
            
        Returns:
            Dictionary with account info (name, channel_id)
        """
        try:
            query = """
                SELECT name, channel_id
                FROM youtube_channels
                WHERE id = %s
            """
            results = self.db._execute_query(query, (account_id,), fetch=True)
            
            if results:
                return {
                    'name': results[0][0],
                    'channel_id': results[0][1]
                }
            
            return {'name': f'Unknown-{account_id}', 'channel_id': f'ID-{account_id}'}
            
        except Exception as e:
            self.logger.error(f"Error getting account info for ID {account_id}: {str(e)}")
            return {'name': f'Unknown-{account_id}', 'channel_id': f'ID-{account_id}'}
    
    def _format_platform_report(self, platform_report: PlatformReport, date: datetime) -> str:
        """
        Format platform report as Telegram message.
        
        Args:
            platform_report: Platform report data
            date: Date of the report
            
        Returns:
            Formatted message string
        """
        platform_name = platform_report.platform.upper()
        date_str = date.strftime('%Y-%m-%d')
        
        # Build message header
        message = f"📊 **Daily Report - {platform_name}**\n"
        message += f"📅 Date: {date_str}\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Add account reports
        for account in platform_report.accounts:
            # Format: (#5 @audiokniga-one - (0) 5/5)
            # Task IDs for reference (first task ID from the list)
            first_task_id = account.task_ids[0] if account.task_ids else 0
            
            # Format channel link based on platform
            channel_link = self._format_channel_link(account.channel_id, platform_report.platform)
            
            # Build account line
            line = f"#{first_task_id} {channel_link} - "
            line += f"({account.error_count}) "
            line += f"{account.success_count}/{account.total_scheduled}\n"
            
            message += line
        
        # Add summary
        total_scheduled = sum(acc.total_scheduled for acc in platform_report.accounts)
        total_completed = sum(acc.total_completed for acc in platform_report.accounts)
        total_failed = sum(acc.total_failed for acc in platform_report.accounts)
        
        message += "\n━━━━━━━━━━━━━━━━━━━━\n"
        message += "**Summary:**\n"
        message += f"✅ Completed: {total_completed}/{total_scheduled}\n"
        message += f"❌ Failed: {total_failed}\n"
        
        success_rate = (total_completed / total_scheduled * 100) if total_scheduled > 0 else 0
        message += f"📈 Success Rate: {success_rate:.1f}%\n"
        
        return message
    
    def _format_channel_link(self, channel_id: str, platform: str) -> str:
        """
        Format channel ID as clickable link based on platform.
        
        Args:
            channel_id: Channel ID or username
            platform: Platform name
            
        Returns:
            Formatted link string
        """
        # Ensure channel_id starts with @ if it doesn't
        if not channel_id.startswith('@'):
            display_id = f'@{channel_id}'
        else:
            display_id = channel_id
        
        # Create platform-specific links
        if platform.lower() == 'youtube':
            # YouTube link format
            if channel_id.startswith('@'):
                # Handle format
                link = f"[{display_id}](https://youtube.com/{channel_id})"
            else:
                # Assume it's a channel ID or handle without @
                link = f"[{display_id}](https://youtube.com/@{channel_id})"
        
        elif platform.lower() == 'instagram':
            # Instagram link format
            clean_id = channel_id.lstrip('@')
            link = f"[{display_id}](https://instagram.com/{clean_id})"
        
        elif platform.lower() == 'tiktok':
            # TikTok link format
            clean_id = channel_id.lstrip('@')
            link = f"[{display_id}](https://tiktok.com/@{clean_id})"
        
        elif platform.lower() == 'vk':
            # VK link format
            clean_id = channel_id.lstrip('@')
            link = f"[{display_id}](https://vk.com/{clean_id})"
        
        else:
            # Generic format for unknown platforms
            link = display_id
        
        return link
    
    def _send_telegram_message(self, message: str) -> bool:
        """
        Send message via Telegram (broadcast or single user).
        
        Args:
            message: Message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if self.use_broadcast and self.broadcaster:
                # Розсилка всім підписникам
                result = self.broadcaster.broadcast_message(message)
                success = result['success'] > 0
                if success:
                    self.logger.info(f"Broadcast sent to {result['success']}/{result['total']} subscribers")
                return success
            else:
                # Відправка одному користувачу (старий метод)
                self.notifier._send_telegram_message(message)
                return True
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {str(e)}")
            return False
    
    def send_test_report(self) -> bool:
        """
        Send a test report for today's tasks.
        
        Returns:
            True if test report sent successfully
        """
        try:
            self.logger.info("Sending test daily report...")
            return self.generate_and_send_daily_report(datetime.now() - timedelta(days=1))
        except Exception as e:
            self.logger.error(f"Error sending test report: {str(e)}")
            return False


# Standalone function for cron/scheduler integration
def send_daily_report():
    """Standalone function to send daily report (for use with cron/scheduler)."""
    logger = get_logger("daily_report_cron")
    try:
        report_manager = DailyReportManager()
        success = report_manager.generate_and_send_daily_report()
        
        if success:
            logger.info("Daily report sent successfully")
        else:
            logger.error("Failed to send daily report")
            
        return success
        
    except Exception as e:
        logger.error(f"Error in daily report cron job: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    # For testing
    import sys
    
    print("Testing Daily Report System...")
    
    report_manager = DailyReportManager()
    
    # Test with yesterday's data
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        print("\n🧪 Sending test report for yesterday...")
        success = report_manager.send_test_report()
    else:
        print("\n📊 Sending daily report for yesterday...")
        success = report_manager.generate_and_send_daily_report()
    
    if success:
        print("✅ Report sent successfully!")
    else:
        print("❌ Failed to send report")
        sys.exit(1)

