"""
Task Worker for processing scheduled tasks from MySQL database.
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any
from pathlib import Path

from core.database.mysql_db import YouTubeMySQLDatabase, Task
from core.api_clients.youtube_client import YouTubeClient
from core.utils.logger import get_logger
from core.utils.notifications import NotificationManager
from core.utils.error_categorizer import ErrorCategorizer
from core.utils.telegram_broadcast import TelegramBroadcast
from core.voice import VoiceChanger
from core.auth.reauth.service import YouTubeReauthService, ServiceConfig
from core.auth.reauth.models import ReauthStatus
from scripts.youtube_reauth_service import save_reauth_tokens_to_db


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
        self.voice_changer: Optional[VoiceChanger] = None
        self.notification_manager = NotificationManager()
        self.telegram_broadcast = TelegramBroadcast()
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'retried': 0
        }
        
        # In-memory retry tracking (task_id -> retry_count)
        self.task_retries = {}
        
        # Track channels currently being re-authenticated to avoid duplicate reauths
        self.ongoing_reauths = set()
        
        # Track reauth threads for proper cleanup
        self.reauth_threads: Dict[str, threading.Thread] = {}
    
    def set_youtube_client(self, client: YouTubeClient):
        """Set YouTube API client."""
        self.youtube_client = client
    
    def set_voice_changer(self, changer: VoiceChanger):
        """Set voice changer instance."""
        self.voice_changer = changer
    
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
        
        # Wait for reauth threads to complete (with timeout)
        if self.reauth_threads:
            self.logger.info(f"Waiting for {len(self.reauth_threads)} reauth thread(s) to complete...")
            for channel_name, thread in self.reauth_threads.items():
                if thread.is_alive():
                    self.logger.info(f"Waiting for reauth thread for {channel_name} to complete...")
                    thread.join(timeout=30)  # Give reauth threads time to clean up
                    if thread.is_alive():
                        self.logger.warning(f"Reauth thread for {channel_name} did not complete within timeout")
        
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
                        
                        # Process each task with individual error handling
                        # This ensures one failed task doesn't stop the entire loop
                        try:
                            self._process_task(task)
                        except Exception as task_error:
                            self.logger.error(f"Error processing task #{task.id}: {str(task_error)}", exc_info=True)
                            # Continue to next task
                            continue
                
                # Sleep for the specified interval
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                # Allow graceful shutdown on Ctrl+C
                self.logger.warning("Worker loop interrupted by KeyboardInterrupt")
                self.running = False
                break
            except SystemExit:
                # Allow system exit to propagate
                raise
            except Exception as e:
                # Catch all other exceptions to prevent worker from crashing
                self.logger.error(f"Worker loop error: {str(e)}", exc_info=True)
                # Sleep before retrying to avoid tight error loop
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
            
            # Get channel information (not needed for voice_change tasks)
            channel = None
            if task.media_type != 'voice_change':
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
            elif task.media_type == 'voice_change':
                success = self._process_voice_change_task(task)
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
            # Get OAuth credentials from google_consoles table via console_name
            # Fallback to deprecated channel.client_id/client_secret
            credentials = self.db.get_console_credentials_for_channel(channel.name)
            
            if not credentials:
                self.logger.error(f"No OAuth credentials found for channel '{channel.name}'")
                return False
            
            client_id = credentials['client_id']
            client_secret = credentials['client_secret']
            
            # Initialize YouTube client if not already set
            if not self.youtube_client:
                self.youtube_client = YouTubeClient(
                    client_id=client_id,
                    client_secret=client_secret
                )
            else:
                # Update client credentials if channel uses different console
                # (though account_info will override this in post_video)
                self.youtube_client.client_id = channel.client_id
                self.youtube_client.client_secret = channel.client_secret
            
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
                'client_id': client_id,
                'client_secret': client_secret
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
                # Mark task as completed and save upload_id
                self.db.mark_task_completed(task.id, upload_id=result.post_id)
                # Видалити з retry tracking після успіху
                self.task_retries.pop(task.id, None)
                
                # Like the video after successful upload
                if result.post_id:
                    self.logger.info(f"Liking video {result.post_id}...")
                    like_success = self._like_video(result.post_id, account_info)
                    if like_success:
                        self.logger.info(f"✓ Successfully liked video {result.post_id}")
                    else:
                        self.logger.warning(f"⚠ Failed to like video {result.post_id}")
                
                # Post comment if specified
                if task.post_comment and result.post_id:
                    self.logger.info(f"Posting comment on video {result.post_id}...")
                    comment_success = self._post_comment(result.post_id, task.post_comment, account_info)
                    if comment_success:
                        self.logger.info(f"✓ Successfully posted comment on video {result.post_id}")
                    else:
                        self.logger.warning(f"⚠ Failed to post comment on video {result.post_id}")
                
                # Видалити файли після успішної публікації (якщо увімкнено)
                if self.auto_cleanup:
                    self._cleanup_files(task)
                else:
                    self.logger.info(f"Auto-cleanup disabled, files kept: {task.att_file_path}")
                
                return True
            else:
                error_msg = result.error_message or "Unknown error during upload"
                self.logger.error(f"Task #{task.id} failed: {error_msg}")
                
                # Check if this is a token revocation error and send notification
                error_category = ErrorCategorizer.categorize(error_msg)
                is_token_revoked = error_category == 'Auth' and ('invalid_grant' in error_msg.lower() or 
                                                                  'token revoked' in error_msg.lower() or 
                                                                  'token expired' in error_msg.lower() or
                                                                  're-authenticate' in error_msg.lower())
                
                if is_token_revoked:
                    # Send notification and trigger automatic re-authentication
                    self._handle_token_revocation(channel.name, error_msg)
                    
                    # Token revocation errors should NOT be retried - mark as failed immediately
                    self.db.mark_task_failed(task.id, error_msg)
                    self.logger.error(f"Task #{task.id} marked as failed due to token revocation. Re-authentication required for account {channel.name}.")
                    self.task_retries.pop(task.id, None)
                    return False
                
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
            
            # Check if this is a token revocation error and send notification
            error_category = ErrorCategorizer.categorize(error_msg)
            is_token_revoked = error_category == 'Auth' and ('invalid_grant' in error_msg.lower() or 
                                                              'token revoked' in error_msg.lower() or 
                                                              'token expired' in error_msg.lower() or
                                                              're-authenticate' in error_msg.lower())
            
            if is_token_revoked:
                account_name = channel.name if channel else "Unknown"
                # Send notification and trigger automatic re-authentication
                self._handle_token_revocation(account_name, error_msg)
                
                # Token revocation errors should NOT be retried - mark as failed immediately
                self.db.mark_task_failed(task.id, error_msg)
                self.logger.error(f"Task #{task.id} marked as failed due to token revocation. Re-authentication required for account {account_name}.")
                self.task_retries.pop(task.id, None)
                return False
            
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
    
    def _process_voice_change_task(self, task: Task) -> bool:
        """
        Process a voice change task.
        
        Args:
            task: Task object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Initialize voice changer if not already set
            if not self.voice_changer:
                self.voice_changer = VoiceChanger()
            
            # Get voice change parameters from add_info
            conversion_type = 'male_to_female'  # Default
            pitch_shift = None
            formant_shift = None
            
            if task.add_info:
                conversion_type = task.add_info.get('conversion_type', 'male_to_female')
                pitch_shift = task.add_info.get('pitch_shift')
                formant_shift = task.add_info.get('formant_shift')
            
            # Determine output file path
            input_path = Path(task.att_file_path)
            output_dir = input_path.parent / 'voice_converted'
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_filename = f"voice_converted_{input_path.name}"
            output_path = output_dir / output_filename
            
            self.logger.info(f"Converting voice: {conversion_type}")
            self.logger.info(f"Input: {input_path}")
            self.logger.info(f"Output: {output_path}")
            
            # Process the file
            result = self.voice_changer.process_file(
                input_file=str(input_path),
                output_file=str(output_path),
                conversion_type=conversion_type,
                pitch_shift=pitch_shift,
                formant_shift=formant_shift,
                preserve_quality=True
            )
            
            if result['success']:
                self.logger.info(f"Voice change task #{task.id} completed successfully")
                self.logger.info(f"Output file: {output_path}")
                
                # Update task with result info
                result_info = {
                    'output_file': str(output_path),
                    'conversion_type': conversion_type,
                    'pitch_shift': result.get('pitch_shift'),
                    'formant_shift': result.get('formant_shift'),
                    'duration': result.get('duration')
                }
                
                self.db.mark_task_completed(task.id)
                # Видалити з retry tracking після успіху
                self.task_retries.pop(task.id, None)
                
                # Optionally cleanup original file
                if self.auto_cleanup:
                    self.logger.info(f"Note: Original file kept for voice change tasks: {input_path}")
                
                return True
            else:
                error_msg = "Voice change processing failed"
                self.logger.error(f"Task #{task.id} failed: {error_msg}")
                
                # Check if we should retry
                current_retries = self.task_retries.get(task.id, 0)
                if current_retries < self.max_retries:
                    self.task_retries[task.id] = current_retries + 1
                    self.db.update_task_status(task.id, 0)  # Reset to pending
                    self.logger.info(f"Task #{task.id} will be retried (attempt {self.task_retries[task.id]}/{self.max_retries})")
                    self.stats['retried'] += 1
                else:
                    self.db.mark_task_failed(task.id, error_msg)
                    self.task_retries.pop(task.id, None)
                
                return False
                
        except Exception as e:
            error_msg = f"Voice change error: {str(e)}"
            self.logger.error(error_msg)
            
            # Check if we should retry
            current_retries = self.task_retries.get(task.id, 0)
            if current_retries < self.max_retries:
                self.task_retries[task.id] = current_retries + 1
                self.db.update_task_status(task.id, 0)  # Reset to pending
                self.logger.info(f"Task #{task.id} will be retried (attempt {self.task_retries[task.id]}/{self.max_retries})")
                self.stats['retried'] += 1
            else:
                self.db.mark_task_failed(task.id, error_msg)
                self.task_retries.pop(task.id, None)
            
            return False
    
    def _like_video(self, video_id: str, account_info: Dict[str, Any]) -> bool:
        """
        Like the uploaded video.
        
        Args:
            video_id: YouTube video ID
            account_info: Account information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.youtube_client:
                self.logger.warning("YouTube client not initialized, cannot like video")
                return False
            
            return self.youtube_client.like_video(video_id, account_info)
            
        except Exception as e:
            self.logger.error(f"Failed to like video {video_id}: {str(e)}")
            return False
    
    def _post_comment(self, video_id: str, comment_text: str, account_info: Dict[str, Any]) -> bool:
        """
        Post a comment on the uploaded video.
        
        Args:
            video_id: YouTube video ID
            comment_text: Text of the comment
            account_info: Account information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.youtube_client:
                self.logger.warning("YouTube client not initialized, cannot post comment")
                return False
            
            if not comment_text or not comment_text.strip():
                self.logger.info("No comment text provided, skipping comment posting")
                return False
            
            return self.youtube_client.post_comment(video_id, comment_text, account_info)
            
        except Exception as e:
            self.logger.error(f"Failed to post comment on video {video_id}: {str(e)}")
            return False
    
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
            # Get channel by ID (including console_id)
            query = """
                SELECT id, name, channel_id, console_name, client_id, client_secret,
                       access_token, refresh_token, token_expires_at,
                       console_id, enabled, created_at, updated_at
                FROM youtube_channels WHERE id = %s
            """
            self.db._ensure_connection()
            cursor = self.db.connection.cursor()
            cursor.execute(query, (channel_id,))
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                from core.database.mysql_db import YouTubeChannel
                channel = YouTubeChannel(
                    id=row[0],
                    name=row[1],
                    channel_id=row[2],
                    console_name=row[3],
                    client_id=row[4],
                    client_secret=row[5],
                    access_token=row[6],
                    refresh_token=row[7],
                    token_expires_at=row[8],
                    enabled=bool(row[9]),
                    created_at=row[10],
                    updated_at=row[11]
                )
                
                # If channel has a console, get credentials from console
                if channel.console_id:
                    console = self.db.get_console(channel.console_id)
                    if console and console.enabled:
                        # Override with console credentials
                        channel.client_id = console.client_id
                        channel.client_secret = console.client_secret
                        self.logger.debug(f"Using console '{console.name}' credentials for channel '{channel.name}'")
                
                return channel
            return None
        except Exception as e:
            self.logger.error(f"Error getting channel by ID: {str(e)}")
            return None
    
    def _handle_token_revocation(self, channel_name: str, error_message: str):
        """
        Handle token revocation by sending notification and starting re-authentication.
        
        Args:
            channel_name: Name of the channel that needs re-authentication
            error_message: Error message describing the token revocation
        """
        try:
            # Check if reauth is already in progress for this channel
            if channel_name in self.ongoing_reauths:
                self.logger.info(f"Re-authentication already in progress for channel {channel_name}, skipping duplicate request")
                return
            
            # Send notification about token revocation
            try:
                self.notification_manager.send_token_revocation_alert(
                    platform="YouTube",
                    account=channel_name,
                    error_message=error_message
                )
                self.logger.info(f"Sent token revocation alert for account {channel_name}")
            except Exception as e:
                self.logger.error(f"Failed to send token revocation notification: {e}")
            
            # Send Telegram message about starting re-authentication
            try:
                message = f"""🔐 **Автоматична переавторизація YouTube каналу**

**Канал:** {channel_name}
**Час:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ Токен було відкликано або він застарів.
🔄 Запускаю автоматичну переавторизацію...

Очікуйте повідомлення про результат."""
                
                # Ensure we have subscribers (add TELEGRAM_CHAT_ID if no subscribers)
                subscribers = self.telegram_broadcast.get_subscribers()
                if not subscribers:
                    telegram_chat_id = self.notification_manager.notification_config.telegram_chat_id
                    if telegram_chat_id:
                        try:
                            chat_id_int = int(telegram_chat_id)
                            self.telegram_broadcast.add_subscriber(chat_id_int)
                            self.logger.info(f"Added TELEGRAM_CHAT_ID {chat_id_int} as subscriber for reauth notifications")
                        except (ValueError, TypeError):
                            self.logger.error(f"Invalid TELEGRAM_CHAT_ID: {telegram_chat_id}")
                
                # Try to send via broadcast (to group)
                result = self.telegram_broadcast.broadcast_message(message)
                if result['success'] > 0:
                    self.logger.info(f"Sent reauth notification to Telegram group: {result['success']}/{result['total']} subscribers")
                else:
                    # Fallback to single chat if broadcast fails
                    self.notification_manager._send_telegram_message(message)
                    self.logger.info("Sent reauth notification via fallback method")
            except Exception as e:
                self.logger.error(f"Failed to send Telegram reauth notification: {e}")
            
            # Start re-authentication in background thread
            # NOTE: NOT using daemon=True to prevent memory corruption when process exits
            # Playwright needs proper cleanup, so we use regular thread
            # Wrap in try-except to prevent any exception from crashing the main loop
            try:
                reauth_thread = threading.Thread(
                    target=self._run_reauth_in_background,
                    args=(channel_name,),
                    daemon=False,  # Changed from True to prevent memory corruption
                    name=f"Reauth-{channel_name}"
                )
                self.reauth_threads[channel_name] = reauth_thread
                reauth_thread.start()
                self.logger.info(f"Started re-authentication thread for channel {channel_name}")
            except Exception as e:
                self.logger.error(f"Failed to start re-authentication thread for {channel_name}: {e}", exc_info=True)
                # Don't raise - allow main loop to continue
        except Exception as e:
            # Catch-all to ensure main loop never crashes due to reauth handling
            self.logger.error(f"Unexpected error in _handle_token_revocation for {channel_name}: {e}", exc_info=True)
    
    def _run_reauth_in_background(self, channel_name: str):
        """
        Run re-authentication for a channel in background thread.
        Uses the same mechanism as run_youtube_reauth.py
        
        Args:
            channel_name: Name of the channel to re-authenticate
        """
        self.ongoing_reauths.add(channel_name)
        reauth_service = None
        try:
            self.logger.info(f"Starting re-authentication for channel {channel_name}")
            
            # Create reauth service configuration (same as run_youtube_reauth.py)
            service_config = ServiceConfig()
            service_config.browser.headless = True  # Run in headless mode
            service_config.oauth_settings.redirect_port = 8080
            service_config.oauth_settings.timeout_seconds = 300
            
            # Initialize reauth service (same as run_youtube_reauth.py)
            reauth_service = YouTubeReauthService(
                db=self.db,
                service_config=service_config,
                use_broadcast=True
            )
            
            # Run re-authentication (same as run_youtube_reauth.py)
            # Wrap in try-except to ensure proper cleanup even on errors
            results = reauth_service.run_sync([channel_name])
            
            if results and len(results) > 0:
                result = results[0]
                if result.status == ReauthStatus.SUCCESS:
                    self.logger.info(f"✅ Successfully re-authenticated channel {channel_name}")
                    
                    # Save tokens to database using the same function as run_youtube_reauth.py
                    save_reauth_tokens_to_db(self.db, result)
                    
                    # Send success notification
                    try:
                        success_message = f"""✅ **Переавторизація успішна**

**Канал:** {channel_name}
**Час:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🎉 Канал успішно переавторизовано. Токени збережено в БД.
Тепер можна продовжувати публікацію."""
                        broadcast_result = self.telegram_broadcast.broadcast_message(success_message)
                        if broadcast_result['success'] == 0:
                            # Fallback to single chat
                            self.notification_manager._send_telegram_message(success_message)
                    except Exception as e:
                        self.logger.error(f"Failed to send success notification: {e}")
                else:
                    self.logger.error(f"❌ Re-authentication failed for channel {channel_name}: {result.error}")
                    
                    # Send failure notification
                    try:
                        error_msg = result.error or "Unknown error"
                        failure_message = f"""❌ **Помилка переавторизації**

**Канал:** {channel_name}
**Помилка:** {error_msg}
**Час:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ Не вдалося автоматично переавторизувати канал. Потрібна ручна переавторизація.
Запустіть: python3 run_youtube_reauth.py \"{channel_name}\" """
                        broadcast_result = self.telegram_broadcast.broadcast_message(failure_message)
                        if broadcast_result['success'] == 0:
                            # Fallback to single chat
                            self.notification_manager._send_telegram_message(failure_message)
                    except Exception as e:
                        self.logger.error(f"Failed to send failure notification: {e}")
            else:
                self.logger.error(f"❌ No results returned from re-authentication for channel {channel_name}")
                
        except KeyboardInterrupt:
            # Handle graceful shutdown
            self.logger.warning(f"Re-authentication interrupted for channel {channel_name}")
            raise  # Re-raise to allow proper shutdown
        except Exception as e:
            self.logger.error(f"Error during re-authentication for channel {channel_name}: {str(e)}", exc_info=True)
            
            # Send error notification
            try:
                error_message = f"""❌ **Помилка під час переавторизації**

**Канал:** {channel_name}
**Помилка:** {str(e)}
**Час:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ Виникла помилка під час автоматичної переавторизації. Потрібна ручна переавторизація.
Запустіть: python3 run_youtube_reauth.py \"{channel_name}\" """
                broadcast_result = self.telegram_broadcast.broadcast_message(error_message)
                if broadcast_result['success'] == 0:
                    # Fallback to single chat
                    self.notification_manager._send_telegram_message(error_message)
            except Exception as notif_e:
                self.logger.error(f"Failed to send error notification: {notif_e}")
        finally:
            # Ensure Playwright resources are cleaned up
            # The reauth_service should handle cleanup via context managers,
            # but we log here to track completion
            try:
                # Force garbage collection to help release Playwright resources
                import gc
                gc.collect()
            except Exception as gc_e:
                self.logger.warning(f"Error during cleanup: {gc_e}")
            
            # Remove from ongoing reauths set and thread tracking
            self.ongoing_reauths.discard(channel_name)
            self.reauth_threads.pop(channel_name, None)
            self.logger.info(f"Completed re-authentication process for channel {channel_name}")
    
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

