"""
YouTube API client for posting Shorts and managing content.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from core.api_clients.base_client import BaseAPIClient, PostResult, RateLimitInfo


class YouTubeClient(BaseAPIClient):
    """YouTube API client using YouTube Data API v3."""
    
    # YouTube API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/youtube.upload',
        'https://www.googleapis.com/auth/youtube',
        'https://www.googleapis.com/auth/youtube.force-ssl'  # Required for comments
    ]
    
    def __init__(self, client_id: str, client_secret: str, credentials_file: str = None):
        super().__init__("YouTube", "https://www.googleapis.com/youtube/v3")
        self.client_id = client_id
        self.client_secret = client_secret
        self.credentials_file = credentials_file
        self.youtube_service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with YouTube API."""
        try:
            creds = None
            token_file = 'youtube_token.json'
            
            # Load existing credentials
            if os.path.exists(token_file):
                creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
            
            # If there are no valid credentials, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if self.credentials_file and os.path.exists(self.credentials_file):
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self.credentials_file, self.SCOPES)
                        creds = flow.run_local_server(port=0)
                    else:
                        self.logger.error("No credentials file found for YouTube authentication")
                        return
                
                # Save credentials for next run
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
            
            # Build YouTube service
            self.youtube_service = build('youtube', 'v3', credentials=creds)
            self.logger.info("Successfully authenticated with YouTube API")
            
        except Exception as e:
            self.logger.error(f"YouTube authentication error: {str(e)}")
            self.youtube_service = None
    
    def _create_service_with_token(self, account_info: Dict[str, Any]):
        """Create YouTube service with account-specific token."""
        try:
            access_token = account_info.get('access_token')
            refresh_token = account_info.get('refresh_token')
            token_expires_at = account_info.get('token_expires_at')
            
            if not access_token:
                self.logger.error(f"No access token for account {account_info.get('name', 'Unknown')}")
                return None
            
            # Get client_id and client_secret from account_info (from console) or fallback to instance values
            client_id = account_info.get('client_id', self.client_id)
            client_secret = account_info.get('client_secret', self.client_secret)
            
            # Log which credentials are being used (for debugging console selection)
            account_name = account_info.get('name', 'Unknown')
            if account_info.get('client_id'):
                self.logger.info(f"Using client_id from account_info (console credentials) for account {account_name}")
            else:
                self.logger.warning(f"Using client_id from YouTubeClient instance (fallback) for account {account_name} - account_info.client_id not found!")
            
            # Parse expiry time if available
            expiry = None
            if token_expires_at:
                if isinstance(token_expires_at, str):
                    try:
                        expiry = datetime.fromisoformat(token_expires_at.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        pass
                elif isinstance(token_expires_at, datetime):
                    expiry = token_expires_at
            
            # Create credentials from account token
            creds = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=self.SCOPES,
                expiry=expiry
            )
            
            # Always try to refresh token if refresh_token is available
            # This ensures we have the freshest token and catches revoked tokens early
            if creds.refresh_token:
                try:
                    # Check if token needs refresh (expired or about to expire in 5 minutes)
                    needs_refresh = False
                    if creds.expired:
                        needs_refresh = True
                        self.logger.info(f"Token is expired for account {account_info.get('name', 'Unknown')}, refreshing...")
                    elif creds.expiry:
                        time_until_expiry = creds.expiry - datetime.utcnow()
                        if time_until_expiry < timedelta(minutes=5):
                            needs_refresh = True
                            self.logger.info(f"Token expires soon for account {account_info.get('name', 'Unknown')}, refreshing...")
                    else:
                        # No expiry info, refresh to be safe
                        needs_refresh = True
                        self.logger.info(f"No expiry info for account {account_info.get('name', 'Unknown')}, refreshing token...")
                    
                    if needs_refresh:
                        creds.refresh(Request())
                        
                        # Update the account_info with new token
                        account_info['access_token'] = creds.token
                        if creds.expiry:
                            account_info['token_expires_at'] = creds.expiry.isoformat()
                        
                        # Update database with new token
                        self._update_database_token(account_info, creds)
                        
                        self.logger.info(f"Token refreshed successfully for account {account_info.get('name', 'Unknown')}")
                    else:
                        self.logger.info(f"Token is valid for account {account_info.get('name', 'Unknown')}")
                        # Update database with current token info
                        self._update_database_token(account_info, creds)
                        
                except Exception as e:
                    error_str = str(e)
                    self.logger.error(f"Failed to refresh token for account {account_info.get('name', 'Unknown')}: {error_str}")
                    # If refresh fails, token might be revoked - user needs to re-authenticate
                    self.logger.error("Token may be revoked. Please re-authenticate this account.")
                    # Store error in account_info for later use
                    account_info['_token_error'] = error_str
                    return None
            elif not creds.valid:
                self.logger.error(f"No valid credentials and no refresh token for account {account_info.get('name', 'Unknown')}")
                return None
            else:
                self.logger.info(f"Token is valid for account {account_info.get('name', 'Unknown')}")
                self._update_database_token(account_info, creds)
            
            # Build YouTube service with account credentials
            youtube_service = build('youtube', 'v3', credentials=creds)
            return youtube_service
            
        except Exception as e:
            self.logger.error(f"Failed to create YouTube service for account {account_info.get('name', 'Unknown')}: {str(e)}")
            return None
    
    def _update_database_token(self, account_info: Dict[str, Any], creds):
        """Update database with refreshed token."""
        try:
            from core.database.mysql_db import get_mysql_database
            
            db = get_mysql_database()
            account_name = account_info.get('name')
            
            if account_name and db:
                # Calculate expiry time if not provided
                expires_at = creds.expiry
                if not expires_at and creds.token:
                    # Default to 1 hour from now if no expiry provided
                    expires_at = datetime.now() + timedelta(hours=1)
                
                db.update_channel_tokens(
                    name=account_name,
                    access_token=creds.token,
                    refresh_token=creds.refresh_token,
                    expires_at=expires_at
                )
                self.logger.info(f"Updated database token for account {account_name}")
        except Exception as e:
            self.logger.error(f"Failed to update database token: {str(e)}")
    
    def _update_rate_limit_info(self, response):
        """Update rate limit info from YouTube API headers."""
        # YouTube doesn't provide rate limit info in headers
        # We'll use a conservative approach based on quota limits
        if not hasattr(self, 'quota_used'):
            self.quota_used = 0
        
        # YouTube allows 10,000 quota units per day
        # Video upload costs 1,600 units
        self.quota_used += 1600
        remaining_quota = max(0, 10000 - self.quota_used)
        
        self.rate_limit_info = RateLimitInfo(
            remaining=remaining_quota // 1600,  # Approximate remaining uploads
            reset_time=datetime.now() + timedelta(days=1),
            limit=10000 // 1600
        )
    
    def validate_account(self, account_info: Dict[str, Any]) -> bool:
        """Validate YouTube account credentials."""
        try:
            if not self.youtube_service:
                return False
            
            # Test by getting channel information
            response = self.youtube_service.channels().list(
                part='snippet,statistics',
                mine=True
            ).execute()
            
            if response.get('items'):
                channel = response['items'][0]
                self.logger.info(f"Validated YouTube account: {channel['snippet']['title']}")
                return True
            else:
                self.logger.error("YouTube account validation failed: No channel found")
                return False
                
        except Exception as e:
            self.logger.error(f"YouTube account validation error: {str(e)}")
            return False
    
    def get_account_info(self, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """Get YouTube account information."""
        try:
            if not self.youtube_service:
                return {}
            
            response = self.youtube_service.channels().list(
                part='snippet,statistics,contentDetails',
                mine=True
            ).execute()
            
            if response.get('items'):
                channel = response['items'][0]
                return {
                    'id': channel['id'],
                    'title': channel['snippet']['title'],
                    'description': channel['snippet']['description'],
                    'subscriber_count': channel['statistics'].get('subscriberCount', '0'),
                    'video_count': channel['statistics'].get('videoCount', '0'),
                    'view_count': channel['statistics'].get('viewCount', '0')
                }
            else:
                self.logger.error("Failed to get YouTube account info: No channel found")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error getting YouTube account info: {str(e)}")
            return {}
    
    def post_video(self, account_info: Dict[str, Any], video_path: str, 
                  caption: str, metadata: Optional[Dict[str, Any]] = None) -> PostResult:
        """Post a video to YouTube as a Short."""
        try:
            # Create YouTube service with account-specific token
            youtube_service = self._create_service_with_token(account_info)
            if not youtube_service:
                # Check for token revocation error stored in account_info
                token_error = account_info.get('_token_error', '')
                if token_error and ('invalid_grant' in token_error or 'Token has been expired or revoked' in token_error):
                    error_message = f"Token revoked or expired: {token_error}. Please re-authenticate account {account_info.get('name', 'Unknown')}."
                else:
                    error_message = "Failed to create YouTube service with account token"
                
                return PostResult(
                    success=False,
                    error_message=error_message,
                    platform="YouTube",
                    account=account_info.get('name', 'Unknown')
                )
            
            account_name = account_info.get('name', 'Unknown')
            
            # Prepare video metadata
            video_metadata = {
                'snippet': {
                    'title': caption[:100],  # YouTube title limit
                    'description': self._sanitize_description(caption),  # YouTube description limit
                    'tags': self._extract_hashtags(caption),
                    'categoryId': '22'  # People & Blogs category
                },
                'status': {
                    'privacyStatus': 'public',
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # Add metadata if provided
            if metadata:
                if 'title' in metadata:
                    video_metadata['snippet']['title'] = metadata['title'][:100]
                if 'description' in metadata:
                    video_metadata['snippet']['description'] = self._sanitize_description(metadata['description'])
                if 'tags' in metadata:
                    video_metadata['snippet']['tags'] = metadata['tags']
                if 'privacy_status' in metadata:
                    video_metadata['status']['privacyStatus'] = metadata['privacy_status']
                if 'category_id' in metadata:
                    video_metadata['snippet']['categoryId'] = metadata['category_id']
            
            # Create media upload object
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/mp4'
            )
            
            # Upload video
            insert_request = youtube_service.videos().insert(
                part=','.join(video_metadata.keys()),
                body=video_metadata,
                media_body=media
            )
            
            # Execute upload with resumable upload
            response = self._resumable_upload(insert_request)
            
            if response:
                video_id = response['id']
                self.logger.info(f"Successfully uploaded YouTube Short: {video_id}")
                return PostResult(
                    success=True,
                    post_id=video_id,
                    posted_at=datetime.now(),
                    platform="YouTube",
                    account=account_name
                )
            else:
                return PostResult(
                    success=False,
                    error_message="Failed to upload video",
                    platform="YouTube",
                    account=account_name
                )
                
        except Exception as e:
            self.logger.error(f"YouTube post error: {str(e)}")
            return PostResult(
                success=False,
                error_message=str(e),
                platform="YouTube",
                account=account_info.get('name', 'Unknown')
            )
    
    def _resumable_upload(self, insert_request):
        """Handle resumable upload for large video files."""
        try:
            response = None
            retry = 0
            max_retries = 3
            
            while response is None:
                try:
                    _, response = insert_request.next_chunk()
                    if response is not None:
                        if 'id' in response:
                            return response
                        else:
                            raise Exception(f"Upload failed with response: {response}")
                except Exception as e:
                    error_str = str(e)
                    
                    # Check if it's an auth error
                    if 'invalid_grant' in error_str or 'Token has been expired or revoked' in error_str:
                        self.logger.error(f"Authentication error: {error_str}")
                        self.logger.error("The refresh token is invalid or revoked. Please re-authenticate the account:")
                        self.logger.error("1. Run: python scripts/account_manager.py")
                        self.logger.error("2. Remove the existing account")
                        self.logger.error("3. Add the account again with fresh OAuth credentials")
                        raise e  # Don't retry auth errors
                    
                    if retry < max_retries:
                        retry += 1
                        self.logger.warning(f"Upload retry {retry}/{max_retries}: {error_str}")
                        time.sleep(2 ** retry)  # Exponential backoff
                    else:
                        raise e
            
            return response
            
        except Exception as e:
            self.logger.error(f"Resumable upload error: {str(e)}")
            return None
    
    def _extract_hashtags(self, text: str) -> list:
        """Extract hashtags from text."""
        import re
        hashtags = re.findall(r'#\w+', text)
        return [tag[1:] for tag in hashtags]  # Remove # symbol
    
    def _sanitize_description(self, description: str) -> str:
        """
        Sanitize and validate video description for YouTube API.
        
        YouTube limits:
        - Max 5000 characters
        - Must not contain certain control characters
        
        Args:
            description: Raw description text
            
        Returns:
            Sanitized description that meets YouTube requirements
        """
        if not description:
            return ""
        
        # Convert to string if not already
        description = str(description)
        
        # Remove null bytes and other problematic characters
        description = description.replace('\x00', '')
        
        # Remove other control characters except newlines and tabs
        import re
        description = re.sub(r'[\x01-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', description)
        
        # Limit to 5000 characters (YouTube's limit)
        if len(description) > 5000:
            self.logger.warning(f"Description truncated from {len(description)} to 5000 characters")
            description = description[:5000]
            # Try to cut at last newline or space to avoid cutting words
            last_newline = description.rfind('\n')
            last_space = description.rfind(' ')
            if last_newline > 4900:
                description = description[:last_newline]
            elif last_space > 4900:
                description = description[:last_space]
        
        return description.strip()
    
    def like_video(self, video_id: str, account_info: Dict[str, Any]) -> bool:
        """
        Like a video on YouTube.
        
        Args:
            video_id: YouTube video ID
            account_info: Account information with access token
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create YouTube service with account-specific token
            youtube_service = self._create_service_with_token(account_info)
            if not youtube_service:
                self.logger.error("Failed to create YouTube service for liking video")
                return False
            
            # Insert a 'like' rating for the video
            youtube_service.videos().rate(
                id=video_id,
                rating='like'
            ).execute()
            
            self.logger.info(f"Successfully liked video: {video_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to like video {video_id}: {str(e)}")
            return False
    
    def post_comment(self, video_id: str, comment_text: str, account_info: Dict[str, Any]) -> bool:
        """
        Post a comment on a YouTube video.
        
        Args:
            video_id: YouTube video ID
            comment_text: Text of the comment to post
            account_info: Account information with access token
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not comment_text or not comment_text.strip():
                self.logger.warning("Comment text is empty, skipping comment posting")
                return False
            
            # Create YouTube service with account-specific token
            youtube_service = self._create_service_with_token(account_info)
            if not youtube_service:
                self.logger.error("Failed to create YouTube service for posting comment")
                return False
            
            # Prepare comment body
            comment_body = {
                'snippet': {
                    'videoId': video_id,
                    'topLevelComment': {
                        'snippet': {
                            'textOriginal': comment_text
                        }
                    }
                }
            }
            
            # Insert comment
            response = youtube_service.commentThreads().insert(
                part='snippet',
                body=comment_body
            ).execute()
            
            comment_id = response.get('id', 'Unknown')
            self.logger.info(f"Successfully posted comment on video {video_id}: Comment ID {comment_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to post comment on video {video_id}: {str(e)}")
            return False
    
    def test_connection(self) -> bool:
        """Test YouTube API connection."""
        try:
            if not self.youtube_service:
                return False
            
            # Test with a simple API call
            response = self.youtube_service.channels().list(
                part='snippet',
                mine=True
            ).execute()
            
            return bool(response.get('items'))
            
        except Exception as e:
            self.logger.error(f"YouTube connection test failed: {str(e)}")
            return False

