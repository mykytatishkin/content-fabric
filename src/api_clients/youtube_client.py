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
from .base_client import BaseAPIClient, PostResult, RateLimitInfo


class YouTubeClient(BaseAPIClient):
    """YouTube API client using YouTube Data API v3."""
    
    # YouTube API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/youtube.upload',
        'https://www.googleapis.com/auth/youtube'
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
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=self.SCOPES,
                expiry=expiry
            )
            
            # Check if token is expired and refresh if needed
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    try:
                        self.logger.info(f"Refreshing expired token for account {account_info.get('name', 'Unknown')}")
                        creds.refresh(Request())
                        
                        # Update the account_info with new token
                        account_info['access_token'] = creds.token
                        if creds.expiry:
                            account_info['token_expires_at'] = creds.expiry.isoformat()
                        
                        # Update database with new token
                        self._update_database_token(account_info, creds)
                        
                        self.logger.info(f"Token refreshed successfully for account {account_info.get('name', 'Unknown')}")
                    except Exception as e:
                        self.logger.error(f"Failed to refresh token for account {account_info.get('name', 'Unknown')}: {str(e)}")
                        return None
                else:
                    self.logger.error(f"No valid credentials for account {account_info.get('name', 'Unknown')}")
                    return None
            else:
                self.logger.info(f"Token is valid for account {account_info.get('name', 'Unknown')}")
                # Even if token is valid, update database with current token info
                # This ensures database stays in sync with actual token state
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
            from ..database import get_database
            
            db = get_database()
            account_name = account_info.get('name')
            
            if account_name and db:
                # Calculate expiry time if not provided
                expires_at = creds.expiry
                if not expires_at and creds.token:
                    # Default to 1 hour from now if no expiry provided
                    from datetime import datetime, timedelta
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
                return PostResult(
                    success=False,
                    error_message="Failed to create YouTube service with account token",
                    platform="YouTube",
                    account=account_info.get('name', 'Unknown')
                )
            
            account_name = account_info.get('name', 'Unknown')
            
            # Prepare video metadata
            video_metadata = {
                'snippet': {
                    'title': caption[:100],  # YouTube title limit
                    'description': caption,
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
                    video_metadata['snippet']['description'] = metadata['description']
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
                            raise Exception(f"Upload failed with response: {response}")
                except Exception as e:
                    if retry < max_retries:
                        retry += 1
                        self.logger.warning(f"Upload retry {retry}/{max_retries}: {str(e)}")
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

