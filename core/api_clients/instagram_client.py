"""
Instagram API client for posting Reels and managing content.
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
from core.api_clients.base_client import BaseAPIClient, PostResult, RateLimitInfo


class InstagramClient(BaseAPIClient):
    """Instagram API client using Instagram Graph API."""
    
    def __init__(self, app_id: str, app_secret: str):
        super().__init__("Instagram", "https://graph.facebook.com/v18.0")
        self.app_id = app_id
        self.app_secret = app_secret
        
        # Instagram-specific headers
        self.session.headers.update({
            'Authorization': f'Bearer {app_secret}',
        })
    
    def _update_rate_limit_info(self, response):
        """Update rate limit info from Instagram API headers."""
        # Instagram uses different header names
        remaining = response.headers.get('X-App-Usage-Call-Count')
        if remaining:
            # Instagram doesn't provide exact rate limit info in headers
            # We'll use a conservative approach
            self.rate_limit_info = RateLimitInfo(
                remaining=max(0, 200 - int(remaining)),  # Instagram allows ~200 calls per hour
                reset_time=datetime.now() + timedelta(hours=1),
                limit=200
            )
    
    def validate_account(self, account_info: Dict[str, Any]) -> bool:
        """Validate Instagram account credentials."""
        try:
            access_token = account_info.get('access_token')
            if not access_token:
                return False
            
            # Test the access token by getting user info
            response = self._make_request(
                'GET',
                f'/me',
                params={'access_token': access_token}
            )
            
            if response.ok:
                user_data = response.json()
                self.logger.info(f"Validated Instagram account: {user_data.get('name', 'Unknown')}")
                return True
            else:
                self.logger.error(f"Instagram account validation failed: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Instagram account validation error: {str(e)}")
            return False
    
    def get_account_info(self, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """Get Instagram account information."""
        try:
            access_token = account_info.get('access_token')
            response = self._make_request(
                'GET',
                f'/me',
                params={
                    'access_token': access_token,
                    'fields': 'id,name,username,account_type,media_count,followers_count,follows_count'
                }
            )
            
            if response.ok:
                return response.json()
            else:
                self.logger.error(f"Failed to get Instagram account info: {response.text}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error getting Instagram account info: {str(e)}")
            return {}
    
    def post_video(self, account_info: Dict[str, Any], video_path: str, 
                  caption: str, metadata: Optional[Dict[str, Any]] = None) -> PostResult:
        """Post a video to Instagram as a Reel."""
        try:
            access_token = account_info.get('access_token')
            account_name = account_info.get('name', 'Unknown')
            
            # Step 1: Create media container
            container_id = self._create_media_container(
                access_token, video_path, caption, metadata
            )
            
            if not container_id:
                return PostResult(
                    success=False,
                    error_message="Failed to create media container",
                    platform="Instagram",
                    account=account_name
                )
            
            # Step 2: Publish the media
            post_id = self._publish_media(access_token, container_id)
            
            if post_id:
                return PostResult(
                    success=True,
                    post_id=post_id,
                    posted_at=datetime.now(),
                    platform="Instagram",
                    account=account_name
                )
            else:
                return PostResult(
                    success=False,
                    error_message="Failed to publish media",
                    platform="Instagram",
                    account=account_name
                )
                
        except Exception as e:
            self.logger.error(f"Instagram post error: {str(e)}")
            return PostResult(
                success=False,
                error_message=str(e),
                platform="Instagram",
                account=account_info.get('name', 'Unknown')
            )
    
    def _create_media_container(self, access_token: str, video_path: str, 
                              caption: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Create a media container for the video."""
        try:
            # Upload video file
            video_url = self._upload_video(access_token, video_path)
            if not video_url:
                return None
            
            # Create container parameters
            container_params = {
                'access_token': access_token,
                'media_type': 'REELS',
                'video_url': video_url,
                'caption': caption,
            }
            
            # Add metadata if provided
            if metadata:
                if 'location' in metadata:
                    container_params['location_id'] = metadata['location']
                if 'thumb_offset' in metadata:
                    container_params['thumb_offset'] = metadata['thumb_offset']
            
            response = self._make_request(
                'POST',
                f'/{self._get_user_id(access_token)}/media',
                data=container_params
            )
            
            if response.ok:
                container_data = response.json()
                container_id = container_data.get('id')
                self.logger.info(f"Created Instagram media container: {container_id}")
                return container_id
            else:
                self.logger.error(f"Failed to create media container: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating media container: {str(e)}")
            return None
    
    def _upload_video(self, access_token: str, video_path: str) -> Optional[str]:
        """Upload video file to Instagram."""
        try:
            # For Instagram, we need to upload to a temporary location first
            # This is a simplified implementation - in production, you'd use Instagram's upload API
            
            # Read video file
            with open(video_path, 'rb') as video_file:
                video_data = video_file.read()
            
            # In a real implementation, you would:
            # 1. Upload to Instagram's upload endpoint
            # 2. Get a media URL back
            # 3. Use that URL in the container creation
            
            # For now, we'll simulate this process
            self.logger.info(f"Uploading video: {video_path}")
            
            # This is a placeholder - you need to implement actual Instagram upload
            # Instagram requires a multi-step upload process
            return f"https://example.com/uploaded_video_{int(time.time())}.mp4"
            
        except Exception as e:
            self.logger.error(f"Error uploading video: {str(e)}")
            return None
    
    def _publish_media(self, access_token: str, container_id: str) -> Optional[str]:
        """Publish the media container."""
        try:
            response = self._make_request(
                'POST',
                f'/{self._get_user_id(access_token)}/media_publish',
                data={
                    'access_token': access_token,
                    'creation_id': container_id
                }
            )
            
            if response.ok:
                publish_data = response.json()
                post_id = publish_data.get('id')
                self.logger.info(f"Published Instagram post: {post_id}")
                return post_id
            else:
                self.logger.error(f"Failed to publish media: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error publishing media: {str(e)}")
            return None
    
    def _get_user_id(self, access_token: str) -> Optional[str]:
        """Get the user ID from access token."""
        try:
            response = self._make_request(
                'GET',
                '/me',
                params={'access_token': access_token}
            )
            
            if response.ok:
                user_data = response.json()
                return user_data.get('id')
            else:
                self.logger.error(f"Failed to get user ID: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting user ID: {str(e)}")
            return None
    
    def test_connection(self) -> bool:
        """Test Instagram API connection."""
        try:
            # Test with a simple API call
            response = self._make_request('GET', f'/{self.app_id}')
            return response.ok
        except Exception as e:
            self.logger.error(f"Instagram connection test failed: {str(e)}")
            return False