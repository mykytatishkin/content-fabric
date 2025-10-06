"""
Content processing and optimization module for social media platforms.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, CompositeVideoClip, TextClip
import yaml

from .logger import get_logger


@dataclass
class ContentSpecs:
    """Content specifications for each platform."""
    platform: str
    aspect_ratio: Tuple[int, int]
    min_duration: float
    max_duration: float
    max_file_size: int  # in bytes
    supported_formats: List[str]
    recommended_resolution: Tuple[int, int]


class ContentProcessor:
    """Handles content processing and optimization for different platforms."""
    
    # Platform specifications
    PLATFORM_SPECS = {
        'instagram': ContentSpecs(
            platform='instagram',
            aspect_ratio=(9, 16),
            min_duration=15.0,
            max_duration=90.0,
            max_file_size=100 * 1024 * 1024,  # 100MB
            supported_formats=['mp4', 'mov'],
            recommended_resolution=(1080, 1920)
        ),
        'tiktok': ContentSpecs(
            platform='tiktok',
            aspect_ratio=(9, 16),
            min_duration=15.0,
            max_duration=180.0,
            max_file_size=500 * 1024 * 1024,  # 500MB
            supported_formats=['mp4', 'mov'],
            recommended_resolution=(1080, 1920)
        ),
        'youtube': ContentSpecs(
            platform='youtube',
            aspect_ratio=(9, 16),
            min_duration=15.0,
            max_duration=60.0,
            max_file_size=256 * 1024 * 1024,  # 256MB
            supported_formats=['mp4', 'mov'],
            recommended_resolution=(1080, 1920)
        )
    }
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.logger = get_logger("content_processor")
        
        # Create output directories
        self._create_directories()
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            self.logger.warning(f"Config file {config_path} not found, using defaults")
            return {}
    
    def _create_directories(self):
        """Create necessary directories for content processing."""
        folders = self.config.get('content', {}).get('folders', {})
        
        for folder_name, folder_path in folders.items():
            Path(folder_path).mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created directory: {folder_path}")
    
    def process_content(self, input_path: str, platforms: List[str], 
                       caption: str = "", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Process content for multiple platforms.
        
        Args:
            input_path: Path to the input video file
            platforms: List of platforms to process for
            caption: Caption text for the content
            metadata: Additional metadata for the content
            
        Returns:
            Dictionary mapping platform names to processed file paths
        """
        start_time = time.time()
        processed_files = {}
        
        try:
            # Validate input file
            if not self._validate_input_file(input_path):
                raise ValueError(f"Invalid input file: {input_path}")
            
            # Load video for analysis
            video = VideoFileClip(input_path)
            self.logger.info(f"Loaded video: {input_path} (Duration: {video.duration:.2f}s)")
            
            for platform in platforms:
                if platform not in self.PLATFORM_SPECS:
                    self.logger.warning(f"Unknown platform: {platform}")
                    continue
                
                try:
                    processed_path = self._process_for_platform(
                        video, platform, input_path, caption, metadata
                    )
                    processed_files[platform] = processed_path
                    
                except Exception as e:
                    self.logger.error(f"Failed to process for {platform}: {str(e)}")
                    continue
            
            video.close()
            
            processing_time = time.time() - start_time
            self.logger.info(f"Content processing completed in {processing_time:.2f}s")
            
            return processed_files
            
        except Exception as e:
            self.logger.error(f"Content processing failed: {str(e)}")
            raise
    
    def _validate_input_file(self, file_path: str) -> bool:
        """Validate input video file."""
        if not os.path.exists(file_path):
            self.logger.error(f"File does not exist: {file_path}")
            return False
        
        # Check file extension
        valid_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext not in valid_extensions:
            self.logger.error(f"Unsupported file format: {file_ext}")
            return False
        
        # Check file size (basic validation)
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            self.logger.error(f"File is empty: {file_path}")
            return False
        
        return True
    
    def _process_for_platform(self, video: VideoFileClip, platform: str, 
                            original_path: str, caption: str, 
                            metadata: Optional[Dict[str, Any]] = None) -> str:
        """Process video for a specific platform."""
        specs = self.PLATFORM_SPECS[platform]
        
        # Create output path
        output_dir = self.config.get('content', {}).get('folders', {}).get('processed', './content/processed')
        original_name = Path(original_path).stem
        output_path = os.path.join(output_dir, f"{original_name}_{platform}.mp4")
        
        # Process video
        processed_video = self._optimize_video(video, specs, caption, metadata)
        
        # Write processed video
        processed_video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            verbose=False,
            logger=None
        )
        
        processed_video.close()
        
        self.logger.info(f"Processed {platform} video: {output_path}")
        return output_path
    
    def _optimize_video(self, video: VideoFileClip, specs: ContentSpecs, 
                       caption: str, metadata: Optional[Dict[str, Any]] = None) -> VideoFileClip:
        """Optimize video for platform specifications."""
        
        # 1. Duration optimization
        optimized_video = self._optimize_duration(video, specs)
        
        # 2. Aspect ratio optimization
        optimized_video = self._optimize_aspect_ratio(optimized_video, specs)
        
        # 3. Resolution optimization
        optimized_video = self._optimize_resolution(optimized_video, specs)
        
        # 4. Add captions if specified
        if caption and self.config.get('content', {}).get('add_captions', False):
            optimized_video = self._add_captions(optimized_video, caption)
        
        # 5. Add watermark if specified
        if self.config.get('content', {}).get('add_watermark', False):
            optimized_video = self._add_watermark(optimized_video)
        
        return optimized_video
    
    def _optimize_duration(self, video: VideoFileClip, specs: ContentSpecs) -> VideoFileClip:
        """Optimize video duration for platform requirements."""
        duration = video.duration
        
        if duration < specs.min_duration:
            # If video is too short, loop it
            loops_needed = int(specs.min_duration / duration) + 1
            video_clips = [video] * loops_needed
            video = CompositeVideoClip(video_clips)
            video = video.subclip(0, specs.min_duration)
            self.logger.info(f"Extended video duration from {duration:.2f}s to {specs.min_duration:.2f}s")
            
        elif duration > specs.max_duration:
            # If video is too long, trim it
            video = video.subclip(0, specs.max_duration)
            self.logger.info(f"Trimmed video duration from {duration:.2f}s to {specs.max_duration:.2f}s")
        
        return video
    
    def _optimize_aspect_ratio(self, video: VideoFileClip, specs: ContentSpecs) -> VideoFileClip:
        """Optimize video aspect ratio for platform requirements."""
        current_width, current_height = video.size
        target_ratio = specs.aspect_ratio[0] / specs.aspect_ratio[1]
        current_ratio = current_width / current_height
        
        if abs(current_ratio - target_ratio) < 0.01:
            # Aspect ratio is already correct
            return video
        
        # Calculate new dimensions
        if current_ratio > target_ratio:
            # Video is too wide, crop sides
            new_width = int(current_height * target_ratio)
            x_offset = (current_width - new_width) // 2
            video = video.crop(x1=x_offset, x2=x_offset + new_width)
        else:
            # Video is too tall, crop top/bottom
            new_height = int(current_width / target_ratio)
            y_offset = (current_height - new_height) // 2
            video = video.crop(y1=y_offset, y2=y_offset + new_height)
        
        self.logger.info(f"Optimized aspect ratio to {specs.aspect_ratio[0]}:{specs.aspect_ratio[1]}")
        return video
    
    def _optimize_resolution(self, video: VideoFileClip, specs: ContentSpecs) -> VideoFileClip:
        """Optimize video resolution for platform requirements."""
        current_width, current_height = video.size
        target_width, target_height = specs.recommended_resolution
        
        if current_width == target_width and current_height == target_height:
            # Resolution is already correct
            return video
        
        # Resize video
        video = video.resize((target_width, target_height))
        self.logger.info(f"Optimized resolution to {target_width}x{target_height}")
        return video
    
    def _add_captions(self, video: VideoFileClip, caption: str) -> VideoFileClip:
        """Add captions to video."""
        try:
            # Create text clip
            text_clip = TextClip(
                caption,
                fontsize=50,
                color='white',
                font='Arial-Bold',
                stroke_color='black',
                stroke_width=2
            ).set_position(('center', 'bottom')).set_duration(video.duration)
            
            # Composite video with text
            final_video = CompositeVideoClip([video, text_clip])
            self.logger.info("Added captions to video")
            return final_video
            
        except Exception as e:
            self.logger.warning(f"Failed to add captions: {str(e)}")
            return video
    
    def _add_watermark(self, video: VideoFileClip) -> VideoFileClip:
        """Add watermark to video."""
        try:
            # Check if watermark image exists
            watermark_path = self.config.get('content', {}).get('watermark_path')
            if not watermark_path or not os.path.exists(watermark_path):
                self.logger.warning("Watermark image not found, skipping watermark")
                return video
            
            # Create watermark clip
            watermark = VideoFileClip(watermark_path).resize(height=100)
            watermark = watermark.set_position(('right', 'top')).set_duration(video.duration)
            
            # Composite video with watermark
            final_video = CompositeVideoClip([video, watermark])
            self.logger.info("Added watermark to video")
            return final_video
            
        except Exception as e:
            self.logger.warning(f"Failed to add watermark: {str(e)}")
            return video
    
    def generate_thumbnail(self, video_path: str, output_path: str, 
                          timestamp: float = 1.0) -> bool:
        """Generate thumbnail from video."""
        try:
            video = VideoFileClip(video_path)
            frame = video.get_frame(timestamp)
            
            # Convert frame to PIL Image
            from PIL import Image
            import numpy as np
            
            image = Image.fromarray(frame)
            image.save(output_path)
            
            video.close()
            self.logger.info(f"Generated thumbnail: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to generate thumbnail: {str(e)}")
            return False
    
    def validate_processed_content(self, file_path: str, platform: str) -> bool:
        """Validate processed content meets platform requirements."""
        try:
            if not os.path.exists(file_path):
                return False
            
            specs = self.PLATFORM_SPECS.get(platform)
            if not specs:
                return False
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > specs.max_file_size:
                self.logger.error(f"File too large for {platform}: {file_size} > {specs.max_file_size}")
                return False
            
            # Check video properties
            video = VideoFileClip(file_path)
            
            # Check duration
            if video.duration < specs.min_duration or video.duration > specs.max_duration:
                self.logger.error(f"Duration out of range for {platform}: {video.duration}")
                video.close()
                return False
            
            # Check aspect ratio
            width, height = video.size
            current_ratio = width / height
            target_ratio = specs.aspect_ratio[0] / specs.aspect_ratio[1]
            
            if abs(current_ratio - target_ratio) > 0.01:
                self.logger.error(f"Aspect ratio incorrect for {platform}: {current_ratio:.3f} != {target_ratio:.3f}")
                video.close()
                return False
            
            video.close()
            self.logger.info(f"Content validation passed for {platform}")
            return True
            
        except Exception as e:
            self.logger.error(f"Content validation failed: {str(e)}")
            return False

