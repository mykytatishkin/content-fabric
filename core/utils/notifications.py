"""
Notification system for success/failure alerts via Telegram and Email.
"""

import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
from datetime import datetime
import requests
import yaml
from dataclasses import dataclass
from dotenv import load_dotenv

from .logger import get_logger


@dataclass
class NotificationConfig:
    """Notification configuration."""
    telegram_enabled: bool = False
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    email_enabled: bool = False
    email_smtp_server: Optional[str] = None
    email_smtp_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_recipients: Optional[List[str]] = None
    send_success_notifications: bool = True
    send_failure_notifications: bool = True


class NotificationManager:
    """Manages notifications for posting success/failure."""
    
    def __init__(self, config_path: str = "config.yaml"):
        # Load environment variables from .env file
        load_dotenv()
        self.config = self._load_config(config_path)
        self.notification_config = self._parse_notification_config()
        self.logger = get_logger("notifications")
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            self.logger.warning(f"Config file {config_path} not found, using defaults")
            return {}
    
    def _parse_notification_config(self) -> NotificationConfig:
        """Parse notification configuration from config file and environment variables."""
        notification_section = self.config.get('notifications', {})
        
        # Telegram configuration - read credentials from environment variables
        telegram_config = notification_section.get('telegram', {})
        telegram_enabled = telegram_config.get('enabled', False)
        telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Email configuration - read credentials from environment variables
        email_config = notification_section.get('email', {})
        email_enabled = email_config.get('enabled', False)
        email_smtp_server = os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
        email_smtp_port = int(os.getenv('EMAIL_SMTP_PORT', '587'))
        email_username = os.getenv('EMAIL_USERNAME')
        email_password = os.getenv('EMAIL_PASSWORD')
        email_recipients = notification_section.get('recipients', []) or []
        
        return NotificationConfig(
            telegram_enabled=telegram_enabled,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            email_enabled=email_enabled,
            email_smtp_server=email_smtp_server,
            email_smtp_port=email_smtp_port,
            email_username=email_username,
            email_password=email_password,
            email_recipients=email_recipients,
            send_success_notifications=telegram_config.get('send_success', True) or email_config.get('send_success', True),
            send_failure_notifications=telegram_config.get('send_failure', True) or email_config.get('send_failure', True)
        )
    
    def send_success_notification(self, platform: str, account: str, post_id: str, 
                                 content_path: str, posted_at: datetime):
        """Send success notification."""
        if not self.notification_config.send_success_notifications:
            return
        
        message = self._format_success_message(platform, account, post_id, content_path, posted_at)
        self._send_notification(message, "✅ Post Success")
    
    def send_failure_notification(self, platform: str, account: str, content_path: str, 
                                 error_message: str, retry_count: int = 0):
        """Send failure notification."""
        if not self.notification_config.send_failure_notifications:
            return
        
        message = self._format_failure_message(platform, account, content_path, error_message, retry_count)
        self._send_notification(message, "❌ Post Failed")
    
    def send_batch_summary(self, summary_data: Dict[str, Any]):
        """Send batch posting summary."""
        message = self._format_batch_summary(summary_data)
        self._send_notification(message, "📊 Posting Summary")
    
    def send_system_alert(self, alert_type: str, message: str):
        """Send system alert notification."""
        formatted_message = f"🚨 **{alert_type}**\n\n{message}"
        self._send_notification(formatted_message, f"System Alert: {alert_type}")
    
    def _send_notification(self, message: str, subject: str):
        """Send notification via all configured channels."""
        # Send via Telegram
        if self.notification_config.telegram_enabled:
            self._send_telegram_message(message)
        
        # Send via Email
        if self.notification_config.email_enabled:
            self._send_email_message(message, subject)
    
    def _send_telegram_message(self, message: str):
        """Send message via Telegram."""
        try:
            if not self.notification_config.telegram_bot_token or not self.notification_config.telegram_chat_id:
                self.logger.warning("Telegram credentials not configured")
                return
            
            url = f"https://api.telegram.org/bot{self.notification_config.telegram_bot_token}/sendMessage"
            
            payload = {
                'chat_id': self.notification_config.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.ok:
                self.logger.info("Telegram notification sent successfully")
            else:
                self.logger.error(f"Failed to send Telegram notification: {response.text}")
                
        except Exception as e:
            self.logger.error(f"Error sending Telegram notification: {str(e)}")
    
    def _send_email_message(self, message: str, subject: str):
        """Send message via Email."""
        try:
            if not self.notification_config.email_username or not self.notification_config.email_password:
                self.logger.warning("Email credentials not configured")
                return
            
            if not self.notification_config.email_recipients:
                self.logger.warning("No email recipients configured")
                return
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.notification_config.email_username
            msg['To'] = ', '.join(self.notification_config.email_recipients)
            msg['Subject'] = f"Social Media Auto-Poster: {subject}"
            
            # Add body
            msg.attach(MIMEText(message, 'plain'))
            
            # Create secure connection and send email
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with smtplib.SMTP(self.notification_config.email_smtp_server, 
                            self.notification_config.email_smtp_port) as server:
                server.starttls(context=context)
                server.login(self.notification_config.email_username, 
                           self.notification_config.email_password)
                
                text = msg.as_string()
                server.sendmail(self.notification_config.email_username, 
                              self.notification_config.email_recipients, text)
            
            self.logger.info("Email notification sent successfully")
            
        except Exception as e:
            self.logger.error(f"Error sending email notification: {str(e)}")
    
    def _format_success_message(self, platform: str, account: str, post_id: str, 
                               content_path: str, posted_at: datetime) -> str:
        """Format success notification message."""
        timestamp = posted_at.strftime('%Y-%m-%d %H:%M:%S')
        content_name = content_path.split('/')[-1] if '/' in content_path else content_path
        
        message = f"""✅ **Post Successful**

**Platform:** {platform.title()}
**Account:** {account}
**Content:** {content_name}
**Post ID:** {post_id}
**Posted At:** {timestamp}

The content has been successfully posted to {platform.title()}."""
        
        return message
    
    def _format_failure_message(self, platform: str, account: str, content_path: str, 
                               error_message: str, retry_count: int = 0) -> str:
        """Format failure notification message."""
        content_name = content_path.split('/')[-1] if '/' in content_path else content_path
        retry_info = f" (Retry {retry_count})" if retry_count > 0 else ""
        
        message = f"""❌ **Post Failed{retry_info}**

**Platform:** {platform.title()}
**Account:** {account}
**Content:** {content_name}
**Error:** {error_message}
**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The post failed to upload to {platform.title()}. Please check the logs for more details."""
        
        return message
    
    def _format_batch_summary(self, summary_data: Dict[str, Any]) -> str:
        """Format batch posting summary message."""
        total_posts = summary_data.get('total_posts', 0)
        successful_posts = summary_data.get('successful_posts', 0)
        failed_posts = summary_data.get('failed_posts', 0)
        platforms = summary_data.get('platforms', [])
        
        success_rate = (successful_posts / total_posts * 100) if total_posts > 0 else 0
        
        message = f"""📊 **Posting Summary**

**Total Posts:** {total_posts}
**Successful:** {successful_posts}
**Failed:** {failed_posts}
**Success Rate:** {success_rate:.1f}%

**Platforms:** {', '.join(platforms)}

**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        return message
    
    def test_notifications(self) -> Dict[str, bool]:
        """Test notification channels."""
        test_message = "🧪 This is a test notification from Social Media Auto-Poster"
        test_subject = "Test Notification"
        
        results = {
            'telegram': False,
            'email': False
        }
        
        # Test Telegram
        if self.notification_config.telegram_enabled:
            try:
                self._send_telegram_message(test_message)
                results['telegram'] = True
                self.logger.info("Telegram notification test successful")
            except Exception as e:
                self.logger.error(f"Telegram notification test failed: {str(e)}")
        
        # Test Email
        if self.notification_config.email_enabled:
            try:
                self._send_email_message(test_message, test_subject)
                results['email'] = True
                self.logger.info("Email notification test successful")
            except Exception as e:
                self.logger.error(f"Email notification test failed: {str(e)}")
        
        return results
    
    def get_notification_status(self) -> Dict[str, Any]:
        """Get notification system status."""
        return {
            'telegram_enabled': self.notification_config.telegram_enabled,
            'telegram_configured': bool(self.notification_config.telegram_bot_token and 
                                      self.notification_config.telegram_chat_id),
            'email_enabled': self.notification_config.email_enabled,
            'email_configured': bool(self.notification_config.email_username and 
                                   self.notification_config.email_password and
                                   self.notification_config.email_recipients),
            'send_success': self.notification_config.send_success_notifications,
            'send_failure': self.notification_config.send_failure_notifications,
            'recipients_count': len(self.notification_config.email_recipients or [])
        }
