"""Video cutting and resizing using FFmpeg."""

import logging
import subprocess
from typing import Literal

logger = logging.getLogger(__name__)


def cut_segment(
    input_path: str, 
    output_path: str, 
    start: float, 
    end: float,
    format_type: Literal["VERT", "ORIG", "VERT_BG"] = "VERT"
) -> bool:
    """Cut a segment from a video and apply formatting for Shorts."""
    duration = end - start
    
    # Base command for cutting
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", input_path
    ]
    
    # Add filters based on format_type
    if format_type == "VERT":
        # Crop center 9:16 and scale to 1080x1920
        # Formula: crop=in_h*9/16:in_h,scale=1080:1920
        cmd.extend([
            "-vf", "crop=ih*9/16:ih,scale=1080:1920",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "192k"
        ])
    elif format_type == "VERT_BG":
        # Blurred background (scale input to 1080x1920 with blur) + original video on top
        # This is more complex, using a simple scale/pad for now
        cmd.extend([
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "192k"
        ])
    else:
        # ORIGINAL aspect ratio, just scaled to 1080p height or width
        cmd.extend([
            "-vf", "scale=1080:-1",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "192k"
        ])
        
    cmd.append(output_path)
    
    try:
        logger.info("Cutting segment [%.1f - %.1f] (%s): %s", start, end, format_type, output_path)
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("FFmpeg cutting failed: %s", e.stderr)
        return False
