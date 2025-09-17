"""
TikTok API client for posting videos and managing content.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .base_client import BaseAPIClient, PostResult, RateLimitInfo


class TikTokClient(BaseAPIClient):
    """TikTok API client using TikTok for Developers API."""
    
    def __init__(self, client_key: str, client_secret: str):
        super().__init__("TikTok", "https://open-api.tiktok.com")
        self.client_key = client_key
        self.client_secret = client_secret
        
        # TikTok-specific headers
        self.session.headers.update({
            'Content-Type': 'application/json',
        })
    
    def _update_rate_limit_info(self, response):
        """Update rate limit info from TikTok API headers."""
        # TikTok uses standard rate limit headers
        remaining = response.headers.get('X-RateLimit-Remaining')
        reset_time = response.headers.get('X-RateLimit-Reset')
        limit = response.headers.get('X-RateLimit-Limit')
        
        if remaining and reset_time and limit:
            try:
                self.rate_limit_info = RateLimitInfo(
                    remaining=int(remaining),
                    reset_time=datetime.fromtimestamp(int(reset_time)),
                    limit=int(limit)
                )
            except (ValueError, TypeError):
                pass
    
    def validate_account(self, account_info: Dict[str, Any]) -> bool:
        """Validate TikTok account credentials."""
        try:
            access_token = account_info.get('access_token')
            if not access_token:
                return False
            
            # Test the access token by getting user info
            response = self._make_request(
                'GET',
                '/user/info/',
                params={'access_token': access_token}
            )
            
            if response.ok:
                user_data = response.json()
                if user_data.get('data', {}).get('user'):
                    self.logger.info(f"Validated TikTok account: {user_data['data']['user'].get('display_name', 'Unknown')}")
                    return True
                else:
                    self.logger.error(f"TikTok account validation failed: Invalid response format")
                    return False
            else:
                self.logger.error(f"TikTok account validation failed: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"TikTok account validation error: {str(e)}")
            return False
    
    def get_account_info(self, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """Get TikTok account information."""
        try:
            access_token = account_info.get('access_token')
            response = self._make_request(
                'GET',
                '/user/info/',
                params={'access_token': access_token}
            )
            
            if response.ok:
                user_data = response.json()
                return user_data.get('data', {}).get('user', {})
            else:
                self.logger.error(f"Failed to get TikTok account info: {response.text}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error getting TikTok account info: {str(e)}")
            return {}
    
    def post_video(self, account_info: Dict[str, Any], video_path: str, 
                  caption: str, metadata: Optional[Dict[str, Any]] = None) -> PostResult:
        """Post a video to TikTok."""
        try:
            access_token = account_info.get('access_token')
            account_name = account_info.get('name', 'Unknown')
            
            # Step 1: Initialize video upload
            upload_url = self._initialize_upload(access_token, video_path)
            if not upload_url:
                return PostResult(
                    success=False,
                    error_message="Failed to initialize video upload",
                    platform="TikTok",
                    account=account_name
                )
            
            # Step 2: Upload video file
            video_id = self._upload_video_file(upload_url, video_path)
            if not video_id:
                return PostResult(
                    success=False,
                    error_message="Failed to upload video file",
                    platform="TikTok",
                    account=account_name
                )
            
            # Step 3: Publish the video
            post_id = self._publish_video(access_token, video_id, caption, metadata)
            
            if post_id:
                return PostResult(
                    success=True,
                    post_id=post_id,
                    posted_at=datetime.now(),
                    platform="TikTok",
                    account=account_name
                )
            else:
                return PostResult(
                    success=False,
                    error_message="Failed to publish video",
                    platform="TikTok",
                    account=account_name
                )
                
        except Exception as e:
            self.logger.error(f"TikTok post error: {str(e)}")
            return PostResult(
                success=False,
                error_message=str(e),
                platform="TikTok",
                account=account_info.get('name', 'Unknown')
            )
    
    def _initialize_upload(self, access_token: str, video_path: str) -> Optional[str]:
        """Initialize video upload and get upload URL."""
        try:
            # Get file size
            file_size = os.path.getsize(video_path)
            
            response = self._make_request(
                'POST',
                '/share/video/upload/',
                json={
                    'access_token': access_token,
                    'source_info': {
                        'source': 'FILE_UPLOAD',
                        'video_size': file_size,
                        'chunk_size': 10485760,  # 10MB chunks
                        'total_chunk_count': (file_size + 10485759) // 10485760
                    }
                }
            )
            
            if response.ok:
                upload_data = response.json()
                if upload_data.get('data', {}).get('upload_url'):
                    self.logger.info("Initialized TikTok video upload")
                    return upload_data['data']['upload_url']
                else:
                    self.logger.error(f"Invalid upload response: {upload_data}")
                    return None
            else:
                self.logger.error(f"Failed to initialize upload: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error initializing upload: {str(e)}")
            return None
    
    def _upload_video_file(self, upload_url: str, video_path: str) -> Optional[str]:
        """Upload video file to TikTok."""
        try:
            # Read video file in chunks
            chunk_size = 10485760  # 10MB
            video_id = None
            
            with open(video_path, 'rb') as video_file:
                chunk_number = 0
                while True:
                    chunk = video_file.read(chunk_size)
                    if not chunk:
                        break
                    
                    # Upload chunk
                    response = self.session.post(
                        upload_url,
                        files={'video': chunk},
                        params={'chunk_number': chunk_number}
                    )
                    
                    if response.ok:
                        chunk_data = response.json()
                        if chunk_number == 0:
                            video_id = chunk_data.get('data', {}).get('video_id')
                        self.logger.info(f"Uploaded chunk {chunk_number}")
                    else:
                        self.logger.error(f"Failed to upload chunk {chunk_number}: {response.text}")
                        return None
                    
                    chunk_number += 1
            
            self.logger.info(f"Successfully uploaded video: {video_id}")
            return video_id
            
        except Exception as e:
            self.logger.error(f"Error uploading video file: {str(e)}")
            return None
    
    def _publish_video(self, access_token: str, video_id: str, caption: str, 
                      metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Publish the uploaded video."""
        try:
            publish_data = {
                'access_token': access_token,
                'video_id': video_id,
                'post_info': {
                    'title': caption,
                    'description': caption,
                    'privacy_level': 'MUTUAL_FOLLOW_FRIEND',
                    'disable_duet': False,
                    'disable_comment': False,
                    'disable_stitch': False,
                    'video_cover_timestamp_ms': 1000
                }
            }
            
            # Add metadata if provided
            if metadata:
                if 'privacy_level' in metadata:
                    publish_data['post_info']['privacy_level'] = metadata['privacy_level']
                if 'disable_duet' in metadata:
                    publish_data['post_info']['disable_duet'] = metadata['disable_duet']
                if 'disable_comment' in metadata:
                    publish_data['post_info']['disable_comment'] = metadata['disable_comment']
                if 'disable_stitch' in metadata:
                    publish_data['post_info']['disable_stitch'] = metadata['disable_stitch']
            
            response = self._make_request(
                'POST',
                '/share/video/publish/',
                json=publish_data
            )
            
            if response.ok:
                publish_response = response.json()
                post_id = publish_response.get('data', {}).get('publish_id')
                self.logger.info(f"Published TikTok video: {post_id}")
                return post_id
            else:
                self.logger.error(f"Failed to publish video: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error publishing video: {str(e)}")
            return None
    
    def test_connection(self) -> bool:
        """Test TikTok API connection."""
        try:
            # Test with a simple API call
            response = self._make_request('GET', '/')
            return response.ok
        except Exception as e:
            self.logger.error(f"TikTok connection test failed: {str(e)}")
            return False

