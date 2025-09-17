"""
Posting scheduler with support for specific times and random timing.
"""

import random
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from pathlib import Path
import yaml
import pytz

from .logger import get_logger


@dataclass
class ScheduledPost:
    """Represents a scheduled post."""
    id: str
    platform: str
    account: str
    content_path: str
    caption: str
    scheduled_time: datetime
    metadata: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3
    status: str = 'scheduled'  # scheduled, posting, completed, failed, cancelled


class PostingScheduler:
    """Manages scheduled posts with support for specific and random timing."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.logger = get_logger("scheduler")
        self.scheduled_posts: Dict[str, ScheduledPost] = {}
        self.posting_callback: Optional[Callable] = None
        self.scheduler_thread: Optional[threading.Thread] = None
        self.running = False
        self.timezone = pytz.timezone(self.config.get('schedule', {}).get('timezone', 'UTC'))
        
        # Load existing scheduled posts
        self._load_scheduled_posts()
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            self.logger.warning(f"Config file {config_path} not found, using defaults")
            return {
                'schedule': {
                    'specific_times': ['09:00', '12:00', '15:00', '18:00', '21:00'],
                    'random_ranges': [
                        {'start': '08:00', 'end': '10:00'},
                        {'start': '11:00', 'end': '13:00'},
                        {'start': '14:00', 'end': '16:00'},
                        {'start': '17:00', 'end': '19:00'},
                        {'start': '20:00', 'end': '22:00'}
                    ],
                    'posting_days': [0, 1, 2, 3, 4, 5, 6],
                    'timezone': 'UTC'
                }
            }
    
    def _load_scheduled_posts(self):
        """Load scheduled posts from file."""
        posts_file = Path("scheduled_posts.json")
        if posts_file.exists():
            try:
                with open(posts_file, 'r') as f:
                    posts_data = yaml.safe_load(f)
                    for post_id, post_data in posts_data.items():
                        post_data['scheduled_time'] = datetime.fromisoformat(post_data['scheduled_time'])
                        self.scheduled_posts[post_id] = ScheduledPost(**post_data)
                self.logger.info(f"Loaded {len(self.scheduled_posts)} scheduled posts")
            except Exception as e:
                self.logger.error(f"Failed to load scheduled posts: {str(e)}")
    
    def _save_scheduled_posts(self):
        """Save scheduled posts to file."""
        try:
            posts_data = {}
            for post_id, post in self.scheduled_posts.items():
                post_dict = {
                    'id': post.id,
                    'platform': post.platform,
                    'account': post.account,
                    'content_path': post.content_path,
                    'caption': post.caption,
                    'scheduled_time': post.scheduled_time.isoformat(),
                    'metadata': post.metadata,
                    'retry_count': post.retry_count,
                    'max_retries': post.max_retries,
                    'status': post.status
                }
                posts_data[post_id] = post_dict
            
            with open("scheduled_posts.json", 'w') as f:
                yaml.dump(posts_data, f, default_flow_style=False)
                
        except Exception as e:
            self.logger.error(f"Failed to save scheduled posts: {str(e)}")
    
    def set_posting_callback(self, callback: Callable):
        """Set the callback function to execute when posts are due."""
        self.posting_callback = callback
    
    def schedule_post(self, platform: str, account: str, content_path: str, 
                     caption: str, scheduled_time: Optional[datetime] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Schedule a post for a specific time or generate a random time.
        
        Args:
            platform: Target platform (instagram, tiktok, youtube)
            account: Account name
            content_path: Path to content file
            caption: Post caption
            scheduled_time: Specific time to post (if None, will generate random time)
            metadata: Additional metadata
            
        Returns:
            Scheduled post ID
        """
        if scheduled_time is None:
            scheduled_time = self._generate_random_time()
        
        # Ensure scheduled time is in the future
        now = datetime.now(self.timezone)
        if scheduled_time <= now:
            scheduled_time = self._generate_random_time()
        
        post_id = f"{platform}_{account}_{int(scheduled_time.timestamp())}"
        
        scheduled_post = ScheduledPost(
            id=post_id,
            platform=platform,
            account=account,
            content_path=content_path,
            caption=caption,
            scheduled_time=scheduled_time,
            metadata=metadata
        )
        
        self.scheduled_posts[post_id] = scheduled_post
        self._save_scheduled_posts()
        
        self.logger.log_schedule_created(platform, account, content_path, scheduled_time)
        return post_id
    
    def _generate_random_time(self) -> datetime:
        """Generate a random posting time based on configuration."""
        schedule_config = self.config.get('schedule', {})
        
        # Get posting days
        posting_days = schedule_config.get('posting_days', [0, 1, 2, 3, 4, 5, 6])
        
        # Choose random day (within next 7 days)
        now = datetime.now(self.timezone)
        days_ahead = random.choice(posting_days)
        target_date = now + timedelta(days=days_ahead)
        
        # Choose random time range
        random_ranges = schedule_config.get('random_ranges', [])
        if not random_ranges:
            # Default time ranges if none specified
            random_ranges = [
                {'start': '09:00', 'end': '11:00'},
                {'start': '14:00', 'end': '16:00'},
                {'start': '19:00', 'end': '21:00'}
            ]
        
        time_range = random.choice(random_ranges)
        start_time = datetime.strptime(time_range['start'], '%H:%M').time()
        end_time = datetime.strptime(time_range['end'], '%H:%M').time()
        
        # Generate random time within range
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute
        random_minutes = random.randint(start_minutes, end_minutes)
        
        random_hour = random_minutes // 60
        random_minute = random_minutes % 60
        
        scheduled_time = target_date.replace(
            hour=random_hour,
            minute=random_minute,
            second=0,
            microsecond=0
        )
        
        return scheduled_time
    
    def schedule_multiple_posts(self, posts_data: List[Dict[str, Any]]) -> List[str]:
        """
        Schedule multiple posts at once.
        
        Args:
            posts_data: List of post data dictionaries
            
        Returns:
            List of scheduled post IDs
        """
        post_ids = []
        
        for post_data in posts_data:
            post_id = self.schedule_post(
                platform=post_data['platform'],
                account=post_data['account'],
                content_path=post_data['content_path'],
                caption=post_data['caption'],
                scheduled_time=post_data.get('scheduled_time'),
                metadata=post_data.get('metadata')
            )
            post_ids.append(post_id)
        
        return post_ids
    
    def get_scheduled_posts(self, platform: Optional[str] = None, 
                          account: Optional[str] = None,
                          status: Optional[str] = None) -> List[ScheduledPost]:
        """Get scheduled posts with optional filtering."""
        filtered_posts = []
        
        for post in self.scheduled_posts.values():
            if platform and post.platform != platform:
                continue
            if account and post.account != account:
                continue
            if status and post.status != status:
                continue
            
            filtered_posts.append(post)
        
        # Sort by scheduled time
        filtered_posts.sort(key=lambda x: x.scheduled_time)
        return filtered_posts
    
    def cancel_post(self, post_id: str) -> bool:
        """Cancel a scheduled post."""
        if post_id in self.scheduled_posts:
            self.scheduled_posts[post_id].status = 'cancelled'
            self._save_scheduled_posts()
            self.logger.info(f"Cancelled post: {post_id}")
            return True
        return False
    
    def reschedule_post(self, post_id: str, new_time: datetime) -> bool:
        """Reschedule a post to a new time."""
        if post_id in self.scheduled_posts:
            self.scheduled_posts[post_id].scheduled_time = new_time
            self.scheduled_posts[post_id].status = 'scheduled'
            self._save_scheduled_posts()
            self.logger.info(f"Rescheduled post {post_id} to {new_time}")
            return True
        return False
    
    def start_scheduler(self):
        """Start the posting scheduler."""
        if self.running:
            self.logger.warning("Scheduler is already running")
            return
        
        if not self.posting_callback:
            self.logger.error("No posting callback set. Cannot start scheduler.")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        self.logger.info("Posting scheduler started")
    
    def stop_scheduler(self):
        """Stop the posting scheduler."""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        self.logger.info("Posting scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                now = datetime.now(self.timezone)
                
                # Check for posts that are due
                due_posts = []
                for post in self.scheduled_posts.values():
                    if (post.status == 'scheduled' and 
                        post.scheduled_time <= now):
                        due_posts.append(post)
                
                # Process due posts
                for post in due_posts:
                    self._process_due_post(post)
                
                # Sleep for 1 minute before next check
                time.sleep(60)
                
            except Exception as e:
                self.logger.error(f"Scheduler loop error: {str(e)}")
                time.sleep(60)
    
    def _process_due_post(self, post: ScheduledPost):
        """Process a post that is due for posting."""
        try:
            post.status = 'posting'
            self._save_scheduled_posts()
            
            self.logger.info(f"Processing due post: {post.id}")
            
            # Call the posting callback
            if self.posting_callback:
                result = self.posting_callback(post)
                
                if result and result.get('success', False):
                    post.status = 'completed'
                    self.logger.log_post_success(
                        post.platform, post.account, 
                        result.get('post_id', ''), 
                        post.content_path, 
                        datetime.now()
                    )
                else:
                    post.status = 'failed'
                    self.logger.log_post_failure(
                        post.platform, post.account, 
                        post.content_path, 
                        result.get('error', 'Unknown error') if result else 'Callback failed'
                    )
                    
                    # Retry logic
                    if post.retry_count < post.max_retries:
                        post.retry_count += 1
                        post.status = 'scheduled'
                        # Reschedule for 1 hour later
                        post.scheduled_time = datetime.now(self.timezone) + timedelta(hours=1)
                        self.logger.info(f"Retrying post {post.id} in 1 hour (attempt {post.retry_count})")
            
            self._save_scheduled_posts()
            
        except Exception as e:
            self.logger.error(f"Error processing due post {post.id}: {str(e)}")
            post.status = 'failed'
            self._save_scheduled_posts()
    
    def get_next_posting_time(self, platform: str, account: str) -> Optional[datetime]:
        """Get the next scheduled posting time for a platform/account."""
        posts = self.get_scheduled_posts(platform=platform, account=account, status='scheduled')
        if posts:
            return posts[0].scheduled_time
        return None
    
    def get_posting_stats(self) -> Dict[str, Any]:
        """Get posting statistics."""
        stats = {
            'total_scheduled': 0,
            'total_completed': 0,
            'total_failed': 0,
            'total_cancelled': 0,
            'by_platform': {},
            'by_account': {}
        }
        
        for post in self.scheduled_posts.values():
            stats['total_scheduled'] += 1
            
            if post.status == 'completed':
                stats['total_completed'] += 1
            elif post.status == 'failed':
                stats['total_failed'] += 1
            elif post.status == 'cancelled':
                stats['total_cancelled'] += 1
            
            # By platform
            if post.platform not in stats['by_platform']:
                stats['by_platform'][post.platform] = {'scheduled': 0, 'completed': 0, 'failed': 0}
            stats['by_platform'][post.platform]['scheduled'] += 1
            if post.status == 'completed':
                stats['by_platform'][post.platform]['completed'] += 1
            elif post.status == 'failed':
                stats['by_platform'][post.platform]['failed'] += 1
            
            # By account
            if post.account not in stats['by_account']:
                stats['by_account'][post.account] = {'scheduled': 0, 'completed': 0, 'failed': 0}
            stats['by_account'][post.account]['scheduled'] += 1
            if post.status == 'completed':
                stats['by_account'][post.account]['completed'] += 1
            elif post.status == 'failed':
                stats['by_account'][post.account]['failed'] += 1
        
        return stats

