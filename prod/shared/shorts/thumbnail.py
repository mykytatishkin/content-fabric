"""Thumbnail selection using GPT Vision."""

import base64
import logging
import os
import subprocess
from typing import Any

from openai import OpenAI
from app.core.config import api_settings

logger = logging.getLogger(__name__)


def extract_frames(video_path: str, output_dir: str, count: int = 5) -> list[str]:
    """Extract N frames from a video for analysis."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Get duration first
    cmd_dur = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    try:
        duration = float(subprocess.check_output(cmd_dur).decode().strip())
    except:
        duration = 30.0
        
    interval = duration / (count + 1)
    frames = []
    
    for i in range(1, count + 1):
        ts = i * interval
        out_f = os.path.join(output_dir, f"frame_{i}.jpg")
        cmd = ["ffmpeg", "-y", "-ss", str(ts), "-i", video_path, "-vframes", "1", "-q:v", "2", out_f]
        subprocess.run(cmd, capture_output=True)
        if os.path.exists(out_f):
            frames.append(out_f)
            
    return frames


def pick_best_thumbnail(frame_paths: list[str]) -> str | None:
    """Use GPT-4 Vision to pick the most viral-looking frame."""
    if not api_settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set")
        return frame_paths[0] if frame_paths else None

    client = OpenAI(api_key=api_settings.OPENAI_API_KEY)
    
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Below are 5 frames from a video. Which one would make the best, most click-worthy thumbnail for a YouTube Short? Respond ONLY with the frame number (1-5)."}
            ]
        }
    ]
    
    for i, path in enumerate(frame_paths):
        with open(path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

    try:
        logger.info("Requesting GPT Vision thumbnail selection")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=10
        )
        
        answer = response.choices[0].message.content.strip()
        # Find a digit in the answer
        import re
        match = re.search(r'\d', answer)
        if match:
            idx = int(match.group()) - 1
            if 0 <= idx < len(frame_paths):
                return frame_paths[idx]
        
        return frame_paths[0]
    except Exception as e:
        logger.error("GPT Vision failed: %s", e)
        return frame_paths[0] if frame_paths else None
