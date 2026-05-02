"""DLE post processor: download assets, create images, assembled video."""

import logging
import os
import subprocess
import requests
from typing import Any
from datetime import datetime

from shared.shorts.cutter import cut_segment # Reuse ffmpeg logic if possible
from shared.voice.changer import process_voice_change

logger = logging.getLogger(__name__)


class DleProcessor:
    def __init__(self, work_dir: str = "/tmp/dle_processing"):
        self.work_dir = work_dir
        os.makedirs(self.work_dir, exist_ok=True)

    def process_task(self, task: dict[str, Any]) -> str | None:
        """Process a DLE task from raw post to final video file.
        
        Returns path to final video or None on failure.
        """
        legacy = task.get("legacy_add_info") or {}
        normalized = legacy.get("normalized") or {}
        source_slug = legacy.get("dle_source")
        dle_id = legacy.get("dle_post_id")
        
        logger.info("Processing DLE task %d (source: %s, ID: %d)", task["id"], source_slug, dle_id)
        
        # 1. Prepare directory
        task_dir = os.path.join(self.work_dir, f"task_{task['id']}")
        os.makedirs(task_dir, exist_ok=True)
        
        try:
            # 2. Download assets (cover, audio)
            # This logic depends on the source site.
            # For simplicity, we implement a generic one for now.
            cover_url = normalized.get("cover")
            if cover_url:
                cover_path = self._download_file(cover_url, os.path.join(task_dir, "cover.jpg"))
            else:
                cover_path = None
                
            # 3. Create YouTube Image
            image_path = os.path.join(task_dir, "youtube_image.jpg")
            if not self._create_youtube_image(image_path, cover_path, normalized.get("book_name"), normalized.get("author")):
                raise Exception("Failed to create YouTube image")
                
            # 4. Get Audio (either download MP3 or generate TTS from annotation)
            # Based on Yii2 controllers, some use TTS, some download.
            audio_path = os.path.join(task_dir, "source_audio.mp3")
            # TODO: Add logic to find and download MP3 or generate TTS
            # For now, let's assume we have a placeholder audio or use TTS if available
            
            # 5. Voice Change (if needed)
            processed_audio = os.path.join(task_dir, "processed_audio.mp3")
            process_voice_change(audio_path, processed_audio, preserve_background=True)
            
            # 6. Create Video
            output_video = os.path.join(task_dir, "final_video.mp4")
            if not self._assemble_video(image_path, processed_audio, output_video):
                raise Exception("Failed to assemble final video")
                
            return output_video
            
        except Exception as e:
            logger.error("DLE processing failed: %s", e)
            return None

    def _download_file(self, url: str, path: str) -> str | None:
        try:
            r = requests.get(url, stream=True, timeout=30)
            r.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return path
        except Exception as e:
            logger.warning("Failed to download %s: %s", url, e)
            return None

    def _create_youtube_image(self, output_path: str, cover_path: str | None, title: str, author: str) -> bool:
        """Generate a YouTube thumbnail/background image using ImageMagick or PIL."""
        # TODO: Implement actual image generation
        # For now, just copy cover if exists, or return True if successful
        return True

    def _assemble_video(self, image_path: str, audio_path: str, output_path: str) -> bool:
        """Assemble video from static image and audio track."""
        # Get audio duration
        cmd_dur = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
        try:
            duration = float(subprocess.check_output(cmd_dur).decode().strip())
        except:
            duration = 300.0 # Fallback
            
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264", "-t", str(duration),
            "-pix_fmt", "yuv420p", "-vf", "scale=1920:1080",
            "-c:a", "aac", "-shortest",
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Video assembly failed: %s", e.stderr)
            return False
