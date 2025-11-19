"""
YouTube API client with database integration for managing multiple channels.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from core.api_clients.base_client import BaseAPIClient, PostResult, RateLimitInfo
from core.database.mysql_db import get_mysql_database, YouTubeChannel


class YouTubeDBClient(BaseAPIClient):
    """YouTube API client with database integration for multiple channels."""
    
    # YouTube API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/youtube.upload',
        'https://www.googleapis.com/auth/youtube'
    ]
    
    def __init__(self, credentials_file: str = "credentials.json"):
        super().__init__("YouTube", "https://www.googleapis.com/youtube/v3")
        self.credentials_file = credentials_file
        self.db = get_mysql_database()
        self.youtube_service = None
        self._current_channel = None
    
    def set_channel(self, channel_name: str) -> bool:
        """Set the current channel for operations."""
        channel = self.db.get_channel(channel_name)
        if not channel:
            self.logger.error(f"Channel '{channel_name}' not found in database")
            return False
        
        if not channel.enabled:
            self.logger.error(f"Channel '{channel_name}' is disabled")
            return False
        
        self._current_channel = channel
        return self._authenticate_for_channel()
    
    def _authenticate_for_channel(self) -> bool:
        """Authenticate for the current channel."""
        if not self._current_channel:
            return False
        
        try:
            creds = None
            
            # Try to get credentials from database
            if (self._current_channel.access_token and 
                self._current_channel.refresh_token and
                not self.db.is_token_expired(self._current_channel.name)):
                
                creds = Credentials(
                    token=self._current_channel.access_token,
                    refresh_token=self._current_channel.refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self._current_channel.client_id,
                    client_secret=self._current_channel.client_secret,
                    scopes=self.SCOPES
                )
            
            # If no valid credentials, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        # Update database with new token
                        expires_at = datetime.now() + timedelta(seconds=creds.expiry - time.time())
                        self.db.update_channel_tokens(
                            self._current_channel.name,
                            creds.token,
                            creds.refresh_token,
                            expires_at
                        )
                        self.logger.info(f"Refreshed token for channel '{self._current_channel.name}'")
                    except Exception as e:
                        self.logger.error(f"Failed to refresh token: {e}")
                        creds = None
                
                if not creds:
                    # Start OAuth flow
                    if not os.path.exists(self.credentials_file):
                        self.logger.error(f"Credentials file '{self.credentials_file}' not found")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    
                    # Save tokens to database
                    expires_at = datetime.now() + timedelta(seconds=creds.expiry - time.time())
                    self.db.update_channel_tokens(
                        self._current_channel.name,
                        creds.token,
                        creds.refresh_token,
                        expires_at
                    )
                    self.logger.info(f"Authenticated channel '{self._current_channel.name}'")
            
            # Build YouTube service
            self.youtube_service = build('youtube', 'v3', credentials=creds)
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication failed for channel '{self._current_channel.name}': {e}")
            return False
    
    def get_available_channels(self) -> List[str]:
        """Get list of available channel names."""
        channels = self.db.get_all_channels(enabled_only=True)
        return [channel.name for channel in channels]
    
    def post_to_channel(self, channel_name: str, video_path: str, 
                       title: str, description: str = "", 
                       tags: List[str] = None, privacy: str = "public") -> PostResult:
        """Post video to specific channel."""
        if not self.set_channel(channel_name):
            return PostResult(
                success=False,
                error=f"Failed to authenticate channel '{channel_name}'"
            )
        
        return self.post(video_path, title, description, tags, privacy)
    
    def post_to_multiple_channels(self, channel_names: List[str], video_path: str,
                                 title: str, description: str = "",
                                 tags: List[str] = None, privacy: str = "public") -> Dict[str, PostResult]:
        """Post video to multiple channels."""
        results = {}
        
        for channel_name in channel_names:
            self.logger.info(f"Posting to channel: {channel_name}")
            result = self.post_to_channel(channel_name, video_path, title, description, tags, privacy)
            results[channel_name] = result
            
            if result.success:
                self.logger.info(f"✅ Successfully posted to {channel_name}")
            else:
                self.logger.error(f"❌ Failed to post to {channel_name}: {result.error}")
            
            # Add delay between posts to avoid rate limiting
            time.sleep(2)
        
        return results
    
    def post(self, video_path: str, title: str, description: str = "",
             tags: List[str] = None, privacy: str = "public") -> PostResult:
        """Post video to current channel."""
        if not self._current_channel:
            return PostResult(
                success=False,
                error="No channel selected. Use set_channel() first."
            )
        
        if not self.youtube_service:
            return PostResult(
                success=False,
                error="YouTube service not initialized. Authentication failed."
            )
        
        try:
            # Prepare video metadata
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags or [],
                    'categoryId': '22'  # People & Blogs category
                },
                'status': {
                    'privacyStatus': privacy,
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # Upload video
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/*'
            )
            
            # Execute upload
            insert_request = self.youtube_service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            # Execute the request
            response = self._execute_upload(insert_request)
            
            if response:
                video_id = response['id']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                return PostResult(
                    success=True,
                    post_id=video_id,
                    url=video_url,
                    platform="YouTube",
                    channel=self._current_channel.name
                )
            else:
                return PostResult(
                    success=False,
                    error="Upload failed - no response received"
                )
                
        except Exception as e:
            self.logger.error(f"YouTube upload error: {e}")
            return PostResult(
                success=False,
                error=str(e)
            )
    
    def _execute_upload(self, insert_request):
        """Execute the upload request with retry logic."""
        response = None
        error = None
        retry = 0
        max_retries = 3
        
        while response is None:
            try:
                status, response = insert_request.next_chunk()
                if response is not None:
                    if 'id' in response:
                        return response
                    else:
                        raise Exception(f"Upload failed: {response}")
            except Exception as e:
                error = e
                retry += 1
                if retry > max_retries:
                    raise e
                time.sleep(2 ** retry)  # Exponential backoff
        
        return response
    
    def get_channel_info(self, channel_name: str = None) -> Optional[Dict[str, Any]]:
        """Get channel information."""
        if channel_name and not self.set_channel(channel_name):
            return None
        
        if not self._current_channel or not self.youtube_service:
            return None
        
        try:
            # Get channel details
            request = self.youtube_service.channels().list(
                part='snippet,statistics',
                mine=True
            )
            response = request.execute()
            
            if response['items']:
                channel = response['items'][0]
                return {
                    'id': channel['id'],
                    'title': channel['snippet']['title'],
                    'description': channel['snippet']['description'],
                    'subscriber_count': channel['statistics'].get('subscriberCount', '0'),
                    'video_count': channel['statistics'].get('videoCount', '0'),
                    'view_count': channel['statistics'].get('viewCount', '0')
                }
        except Exception as e:
            self.logger.error(f"Failed to get channel info: {e}")
        
        return None
    
    def check_quota_usage(self) -> Dict[str, Any]:
        """Check API quota usage (approximate)."""
        # YouTube API doesn't provide real-time quota info
        # This is a placeholder for future implementation
        return {
            'daily_quota': 10000,
            'used_quota': 'Unknown',
            'remaining_quota': 'Unknown'
        }
    
    def get_rate_limit_info(self) -> RateLimitInfo:
        """Get rate limit information."""
        return RateLimitInfo(
            limit=100,  # YouTube API limit per 100 seconds
            remaining=100,
            reset_time=datetime.now() + timedelta(seconds=100)
        )
    
    # Abstract method implementations
    def validate_account(self, account_info: Dict[str, Any]) -> bool:
        """Validate account credentials and permissions."""
        channel_name = account_info.get('name')
        if not channel_name:
            return False
        
        return self.set_channel(channel_name)
    
    def post_video(self, account_info: Dict[str, Any], video_path: str, 
                  caption: str, metadata: Optional[Dict[str, Any]] = None) -> PostResult:
        """Post a video to the platform."""
        channel_name = account_info.get('name')
        if not channel_name:
            return PostResult(
                success=False,
                error_message="Channel name not provided"
            )
        
        # Extract title and description from caption
        lines = caption.split('\n')
        title = lines[0] if lines else caption
        description = '\n'.join(lines[1:]) if len(lines) > 1 else ""
        
        # Extract tags from metadata
        tags = metadata.get('tags', []) if metadata else []
        
        return self.post_to_channel(channel_name, video_path, title, description, tags)
    
    def get_account_info(self, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """Get account information."""
        channel_name = account_info.get('name')
        if not channel_name:
            return {}
        
        return self.get_channel_info(channel_name) or {}
