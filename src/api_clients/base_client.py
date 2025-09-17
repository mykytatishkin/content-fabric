"""
Base API client class with common functionality for all social media platforms.
"""

import requests
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from ..logger import get_logger


@dataclass
class PostResult:
    """Result of a post operation."""
    success: bool
    post_id: Optional[str] = None
    error_message: Optional[str] = None
    posted_at: Optional[datetime] = None
    platform: Optional[str] = None
    account: Optional[str] = None


@dataclass
class RateLimitInfo:
    """Information about API rate limits."""
    remaining: int
    reset_time: datetime
    limit: int


class BaseAPIClient(ABC):
    """Base class for all social media API clients."""
    
    def __init__(self, platform_name: str, base_url: str, timeout: int = 30):
        self.platform_name = platform_name
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.logger = get_logger(f"api.{platform_name}")
        self.rate_limit_info: Optional[RateLimitInfo] = None
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'SocialMediaAutoPoster/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an HTTP request with error handling and rate limiting."""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Check rate limits before making request
        if self.rate_limit_info and self.rate_limit_info.remaining <= 0:
            wait_time = (self.rate_limit_info.reset_time - datetime.now()).total_seconds()
            if wait_time > 0:
                self.logger.warning(f"Rate limit reached. Waiting {wait_time:.0f} seconds...")
                time.sleep(wait_time)
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )
            
            # Update rate limit info from response headers
            self._update_rate_limit_info(response)
            
            # Log API errors
            if not response.ok:
                self.logger.error(f"API Error: {method} {url} - {response.status_code}: {response.text}")
            
            return response
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {method} {url} - {str(e)}")
            raise
    
    def _update_rate_limit_info(self, response: requests.Response):
        """Update rate limit information from response headers."""
        # This is a generic implementation - subclasses should override for platform-specific headers
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
    
    def _handle_rate_limit(self, response: requests.Response) -> bool:
        """Handle rate limit responses."""
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                wait_time = int(retry_after)
                self.logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                return True
        return False
    
    def _retry_request(self, method: str, endpoint: str, max_retries: int = 3, **kwargs) -> requests.Response:
        """Make a request with retry logic."""
        for attempt in range(max_retries + 1):
            try:
                response = self._make_request(method, endpoint, **kwargs)
                
                # Handle rate limiting
                if self._handle_rate_limit(response):
                    continue
                
                # Return successful response
                if response.ok:
                    return response
                
                # Don't retry on client errors (4xx) except 429
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    return response
                
                # Retry on server errors (5xx) and rate limits
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    self.logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries + 1}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    return response
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Request exception (attempt {attempt + 1}/{max_retries + 1}): {str(e)}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
        
        return response
    
    @abstractmethod
    def validate_account(self, account_info: Dict[str, Any]) -> bool:
        """Validate account credentials and permissions."""
        pass
    
    @abstractmethod
    def post_video(self, account_info: Dict[str, Any], video_path: str, 
                  caption: str, metadata: Optional[Dict[str, Any]] = None) -> PostResult:
        """Post a video to the platform."""
        pass
    
    @abstractmethod
    def get_account_info(self, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """Get account information."""
        pass
    
    def test_connection(self) -> bool:
        """Test API connection."""
        try:
            # This is a generic test - subclasses should override
            response = self._make_request('GET', '/')
            return response.ok
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False
