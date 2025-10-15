#!/usr/bin/env python3
"""
Telegram Broadcast System - для розсилки повідомлень всім користувачам бота.
"""

import os
import json
from pathlib import Path
from typing import List, Set
import requests
from dotenv import load_dotenv
from .logger import get_logger

load_dotenv()


class TelegramBroadcast:
    """Manages Telegram broadcast to multiple users."""
    
    def __init__(self):
        self.logger = get_logger("telegram_broadcast")
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.subscribers_file = Path("data/telegram_subscribers.json")
        self.subscribers: Set[int] = self._load_subscribers()
        
        # Створити директорію якщо не існує
        self.subscribers_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_subscribers(self) -> Set[int]:
        """Load subscribers from file."""
        if self.subscribers_file.exists():
            try:
                with open(self.subscribers_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('subscribers', []))
            except Exception as e:
                self.logger.error(f"Error loading subscribers: {e}")
                return set()
        return set()
    
    def _save_subscribers(self):
        """Save subscribers to file."""
        try:
            with open(self.subscribers_file, 'w') as f:
                json.dump({'subscribers': list(self.subscribers)}, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving subscribers: {e}")
    
    def add_subscriber(self, chat_id: int) -> bool:
        """Add new subscriber."""
        if chat_id not in self.subscribers:
            self.subscribers.add(chat_id)
            self._save_subscribers()
            self.logger.info(f"Added subscriber: {chat_id}")
            return True
        return False
    
    def remove_subscriber(self, chat_id: int) -> bool:
        """Remove subscriber."""
        if chat_id in self.subscribers:
            self.subscribers.remove(chat_id)
            self._save_subscribers()
            self.logger.info(f"Removed subscriber: {chat_id}")
            return True
        return False
    
    def get_subscribers(self) -> List[int]:
        """Get list of all subscribers."""
        return list(self.subscribers)
    
    def broadcast_message(self, message: str, parse_mode: str = 'Markdown') -> dict:
        """
        Broadcast message to all subscribers.
        
        Returns:
            Dictionary with success/failure counts
        """
        if not self.bot_token:
            self.logger.error("TELEGRAM_BOT_TOKEN not configured")
            return {'success': 0, 'failed': 0, 'total': 0}
        
        if not self.subscribers:
            self.logger.warning("No subscribers to send messages to")
            return {'success': 0, 'failed': 0, 'total': 0}
        
        success_count = 0
        failed_count = 0
        failed_users = []
        
        for chat_id in self.subscribers:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': parse_mode
                }
                
                response = requests.post(url, json=payload, timeout=10)
                
                if response.ok:
                    success_count += 1
                    self.logger.debug(f"Message sent to {chat_id}")
                else:
                    failed_count += 1
                    failed_users.append(chat_id)
                    self.logger.error(f"Failed to send to {chat_id}: {response.text}")
                    
            except Exception as e:
                failed_count += 1
                failed_users.append(chat_id)
                self.logger.error(f"Error sending to {chat_id}: {str(e)}")
        
        result = {
            'success': success_count,
            'failed': failed_count,
            'total': len(self.subscribers),
            'failed_users': failed_users
        }
        
        self.logger.info(f"Broadcast completed: {success_count}/{len(self.subscribers)} successful")
        return result
    
    def get_updates(self, offset: int = None) -> List[dict]:
        """Get updates from Telegram (for processing /start commands)."""
        if not self.bot_token:
            return []
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {}
            if offset:
                params['offset'] = offset
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.ok:
                data = response.json()
                return data.get('result', [])
            else:
                self.logger.error(f"Failed to get updates: {response.text}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting updates: {str(e)}")
            return []
    
    def process_start_commands(self):
        """Process all interactions and automatically add users to subscribers."""
        updates = self.get_updates()
        new_subscribers = 0
        
        for update in updates:
            if 'message' in update:
                message = update['message']
                chat_id = message['chat']['id']
                text = message.get('text', '')
                
                # Автоматично додаємо ВСІХ хто взаємодіяв з ботом
                # Не тільки /start, але будь-яке повідомлення
                if self.add_subscriber(chat_id):
                    new_subscribers += 1
                    # Відправити привітання тільки для нових користувачів
                    welcome_msg = "✅ Привіт! Ви автоматично отримуватимете щоденні звіти о 12:00.\n\nНічого більше робити не потрібно!"
                    self._send_message(chat_id, welcome_msg)
        
        if new_subscribers > 0:
            self.logger.info(f"Auto-added {new_subscribers} new users from interactions")
        
        return new_subscribers
    
    def auto_sync_users(self):
        """Автоматично синхронізувати всіх користувачів які писали боту."""
        self.process_start_commands()
        return len(self.subscribers)
    
    def _send_message(self, chat_id: int, message: str):
        """Send message to specific chat."""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            self.logger.error(f"Error sending message to {chat_id}: {str(e)}")


# Standalone function for easy import
def broadcast_daily_report(message: str) -> dict:
    """Broadcast daily report to all subscribers."""
    broadcaster = TelegramBroadcast()
    return broadcaster.broadcast_message(message)


if __name__ == "__main__":
    # Test
    broadcaster = TelegramBroadcast()
    print(f"Subscribers: {broadcaster.get_subscribers()}")
    
    # Process new /start commands
    new_subs = broadcaster.process_start_commands()
    print(f"New subscribers: {new_subs}")
    
    # Test broadcast
    if broadcaster.get_subscribers():
        result = broadcaster.broadcast_message("🧪 Test broadcast message")
        print(f"Broadcast result: {result}")

