"""
Task Worker for processing scheduled tasks from MySQL database.
"""

import time
import threading
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from pathlib import Path

from core.database.mysql_db import YouTubeMySQLDatabase, Task
from core.api_clients.youtube_client import YouTubeClient
from core.utils.logger import get_logger


class TaskWorker:
    """Worker that processes scheduled tasks from database."""
    
    def __init__(self, db: YouTubeMySQLDatabase, check_interval: int = 60, max_retries: int = 3, auto_cleanup: bool = True):
        """
        Initialize Task Worker.
        
        Args:
            db: MySQL database instance
            check_interval: Interval in seconds to check for new tasks (default: 60)
            max_retries: Maximum number of retries for failed tasks (default: 3)
            auto_cleanup: Automatically delete files after successful upload (default: True)
        """
        self.db = db
        self.check_interval = check_interval
        self.max_retries = max_retries
        self.auto_cleanup = auto_cleanup
        self.logger = get_logger("task_worker")
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.youtube_client: Optional[YouTubeClient] = None
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'retried': 0
        }
        
        # In-memory retry tracking (task_id -> retry_count)
        self.task_retries = {}
    
    def set_youtube_client(self, client: YouTubeClient):
        """Set YouTube API client."""
        self.youtube_client = client
    
    def start(self):
        """Start the task worker."""
        if self.running:
            self.logger.warning("Task worker is already running")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        self.logger.info(f"Task worker started (checking every {self.check_interval}s)")
    
    def stop(self):
        """Stop the task worker."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        self.logger.info("Task worker stopped")
    
    def _worker_loop(self):
        """Main worker loop."""
        while self.running:
            try:
                # Get pending tasks from database
                pending_tasks = self.db.get_pending_tasks()
                
                if pending_tasks:
                    self.logger.info(f"Found {len(pending_tasks)} pending task(s)")
                    
                    for task in pending_tasks:
                        if not self.running:
                            break
                        
                        self._process_task(task)
                
                # Sleep for the specified interval
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Worker loop error: {str(e)}")
                time.sleep(self.check_interval)
    
    def _process_task(self, task: Task):
        """
        Process a single task.
        
        Args:
            task: Task object to process
        """
        try:
            self.logger.info(f"Processing task #{task.id}: {task.title}")
            
            # Mark task as processing
            self.db.mark_task_processing(task.id)
            
            # Get channel information
            channel = self._get_channel_by_id(task.account_id)
            if not channel:
                error_msg = f"Channel with ID {task.account_id} not found"
                self.logger.error(error_msg)
                self.db.mark_task_failed(task.id, error_msg)
                self.stats['failed'] += 1
                return
            
            # Check if channel is enabled
            if not channel.enabled:
                error_msg = f"Channel {channel.name} is disabled"
                self.logger.error(error_msg)
                self.db.mark_task_failed(task.id, error_msg)
                self.stats['failed'] += 1
                return
            
            # Check if video file exists
            video_path = Path(task.att_file_path)
            if not video_path.exists():
                error_msg = f"Video file not found: {task.att_file_path}"
                self.logger.error(error_msg)
                self.db.mark_task_failed(task.id, error_msg)
                self.stats['failed'] += 1
                return
            
            # Process based on media type
            if task.media_type == 'youtube':
                success = self._process_youtube_task(task, channel)
            else:
                error_msg = f"Unsupported media type: {task.media_type}"
                self.logger.error(error_msg)
                self.db.mark_task_failed(task.id, error_msg)
                self.stats['failed'] += 1
                return
            
            # Update statistics
            self.stats['total_processed'] += 1
            if success:
                self.stats['successful'] += 1
            else:
                self.stats['failed'] += 1
            
        except Exception as e:
            error_msg = f"Error processing task #{task.id}: {str(e)}"
            self.logger.error(error_msg)
            self.db.mark_task_failed(task.id, error_msg)
            self.stats['failed'] += 1
    
    def _process_youtube_task(self, task: Task, channel) -> bool:
        """
        Process a YouTube upload task.
        
        Args:
            task: Task object
            channel: YouTubeChannel object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Initialize YouTube client if not already set
            if not self.youtube_client:
                self.youtube_client = YouTubeClient(
                    client_id=channel.client_id,
                    client_secret=channel.client_secret
                )
            
            # Prepare video metadata
            video_metadata = {
                'title': task.title,
                'description': task.description or '',
                'tags': task.keywords.split(',') if task.keywords else [],
                'categoryId': '22',  # Default to People & Blogs
                'privacyStatus': 'public'  # Default to public
            }
            
            # Add additional info from add_info JSON
            if task.add_info:
                if 'privacy' in task.add_info:
                    video_metadata['privacyStatus'] = task.add_info['privacy']
                if 'category' in task.add_info:
                    video_metadata['categoryId'] = str(task.add_info['category'])
            
            # Prepare account info
            account_info = {
                'name': channel.name,
                'channel_id': channel.channel_id,
                'access_token': channel.access_token,
                'refresh_token': channel.refresh_token,
                'client_id': channel.client_id,
                'client_secret': channel.client_secret
            }
            
            self.logger.info(f"Uploading video to YouTube channel: {channel.name}")
            
            # Upload video
            result = self.youtube_client.post_video(
                account_info=account_info,
                video_path=task.att_file_path,
                caption=task.description or '',
                metadata={
                    'title': task.title,
                    'description': task.description,
                    'tags': video_metadata['tags'],
                    'category': video_metadata['categoryId'],
                    'privacy': video_metadata['privacyStatus'],
                    'thumbnail': task.cover
                }
            )
            
            if result.success:
                self.logger.info(f"Task #{task.id} completed successfully. Video ID: {result.post_id}")
                self.db.mark_task_completed(task.id)
                # Видалити з retry tracking після успіху
                self.task_retries.pop(task.id, None)
                
                # Post comment if specified
                if task.post_comment and result.post_id:
                    self._post_comment(result.post_id, task.post_comment, account_info)
                
                # Видалити файли після успішної публікації (якщо увімкнено)
                if self.auto_cleanup:
                    self._cleanup_files(task)
                else:
                    self.logger.info(f"Auto-cleanup disabled, files kept: {task.att_file_path}")
                
                return True
            else:
                error_msg = result.error_message or "Unknown error during upload"
                self.logger.error(f"Task #{task.id} failed: {error_msg}")
                
                # Check if we should retry (відстежуємо в пам'яті)
                current_retries = self.task_retries.get(task.id, 0)
                if current_retries < self.max_retries:
                    self.task_retries[task.id] = current_retries + 1
                    self.db.update_task_status(task.id, 0)  # Reset to pending
                    self.logger.info(f"Task #{task.id} will be retried (attempt {self.task_retries[task.id]}/{self.max_retries})")
                    self.stats['retried'] += 1
                else:
                    self.db.mark_task_failed(task.id, error_msg)
                    self.logger.error(f"Task #{task.id} exceeded max retries")
                    # Видалити з tracking після максимальних спроб
                    self.task_retries.pop(task.id, None)
                
                return False
                
        except Exception as e:
            error_msg = f"YouTube upload error: {str(e)}"
            self.logger.error(error_msg)
            
            # Check if we should retry (відстежуємо в пам'яті)
            current_retries = self.task_retries.get(task.id, 0)
            if current_retries < self.max_retries:
                self.task_retries[task.id] = current_retries + 1
                self.db.update_task_status(task.id, 0)  # Reset to pending
                self.logger.info(f"Task #{task.id} will be retried (attempt {self.task_retries[task.id]}/{self.max_retries})")
                self.stats['retried'] += 1
            else:
                self.db.mark_task_failed(task.id, error_msg)
                # Видалити з tracking після максимальних спроб
                self.task_retries.pop(task.id, None)
            
            return False
    
    def _post_comment(self, video_id: str, comment_text: str, account_info: Dict[str, Any]):
        """Post a comment on the uploaded video."""
        try:
            # This would require YouTube API comment posting
            # For now, just log it
            self.logger.info(f"Would post comment on video {video_id}: {comment_text}")
            # TODO: Implement actual comment posting via YouTube API
        except Exception as e:
            self.logger.error(f"Failed to post comment: {str(e)}")
    
    def _cleanup_files(self, task: Task):
        """Delete video and cover files after successful upload."""
        import os
        
        deleted_files = []
        failed_files = []
        
        # Delete video file
        if task.att_file_path:
            try:
                if os.path.exists(task.att_file_path):
                    file_size = os.path.getsize(task.att_file_path)
                    os.remove(task.att_file_path)
                    deleted_files.append(f"Video: {task.att_file_path} ({file_size / (1024*1024):.2f} MB)")
                    self.logger.info(f"🗑️  Deleted video file: {task.att_file_path}")
                else:
                    self.logger.warning(f"Video file not found: {task.att_file_path}")
            except Exception as e:
                failed_files.append(f"Video: {task.att_file_path} - {str(e)}")
                self.logger.error(f"Failed to delete video file: {task.att_file_path} - {str(e)}")
        
        # Delete cover file
        if task.cover:
            try:
                if os.path.exists(task.cover):
                    file_size = os.path.getsize(task.cover)
                    os.remove(task.cover)
                    deleted_files.append(f"Cover: {task.cover} ({file_size / 1024:.2f} KB)")
                    self.logger.info(f"🗑️  Deleted cover file: {task.cover}")
                else:
                    self.logger.warning(f"Cover file not found: {task.cover}")
            except Exception as e:
                failed_files.append(f"Cover: {task.cover} - {str(e)}")
                self.logger.error(f"Failed to delete cover file: {task.cover} - {str(e)}")
        
        # Summary log
        if deleted_files:
            self.logger.info(f"✅ Cleanup complete for task #{task.id}. Deleted: {', '.join(deleted_files)}")
        if failed_files:
            self.logger.warning(f"⚠️  Some files could not be deleted: {', '.join(failed_files)}")
    
    def _get_channel_by_id(self, channel_id: int):
        """Get channel from database by ID."""
        try:
            # Get channel by ID
            query = """
                SELECT id, name, channel_id, client_id, client_secret,
                       access_token, refresh_token, token_expires_at,
                       enabled, created_at, updated_at
                FROM youtube_channels WHERE id = %s
            """
            self.db._ensure_connection()
            cursor = self.db.connection.cursor()
            cursor.execute(query, (channel_id,))
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                from core.database.mysql_db import YouTubeChannel
                return YouTubeChannel(
                    id=row[0],
                    name=row[1],
                    channel_id=row[2],
                    client_id=row[3],
                    client_secret=row[4],
                    access_token=row[5],
                    refresh_token=row[6],
                    token_expires_at=row[7],
                    enabled=bool(row[8]),
                    created_at=row[9],
                    updated_at=row[10]
                )
            return None
        except Exception as e:
            self.logger.error(f"Error getting channel by ID: {str(e)}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            'running': self.running,
            'check_interval': self.check_interval,
            'max_retries': self.max_retries,
            'auto_cleanup': self.auto_cleanup,
            'statistics': self.stats.copy()
        }
    
    def process_single_task(self, task_id: int) -> bool:
        """
        Process a single task immediately (for manual execution).
        
        Args:
            task_id: ID of the task to process
            
        Returns:
            True if successful, False otherwise
        """
        try:
            task = self.db.get_task(task_id)
            if not task:
                self.logger.error(f"Task #{task_id} not found")
                return False
            
            if task.status != 0:  # Not pending
                self.logger.warning(f"Task #{task_id} is not pending (status: {task.status})")
                return False
            
            self._process_task(task)
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing single task: {str(e)}")
            return False

