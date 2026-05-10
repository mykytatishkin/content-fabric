"""Ken Burns slideshow + subtitle burn-in — 1:1 port of Yii ``NewsController``.

Used by News pipeline (RBC → 5 photos + audio → video).

Yii originals:
- ``makeYoutubeVideoFrom5Images($workDir)`` — long 1920×1080
- ``makeShortsFrom5Images($workDir)`` — vertical 1080×1920
- ``addSubtitlesToShorts($workDir)`` — burn-in ASS-style SRT

The Ken Burns ``zoompan=z='1+0.00012*on'`` produces ~3% zoom over
~5s per image (actual rate depends on FPS — at 25fps for 5s
image the zoom factor reaches 1+0.00012*125 ≈ 1.015).
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from typing import Iterable

logger = logging.getLogger(__name__)


def _ffprobe_duration(audio_path: str) -> float:
    """Read audio duration in seconds via ffprobe."""
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", audio_path],
            text=True
        ).strip()
        return float(out)
    except Exception as exc:
        logger.error("[SLIDESHOW] ffprobe failed: %s", exc)
        return 0.0


def _build_kenburns_filter(
    images: list[str],
    width: int,
    height: int,
    fps: int,
    per_image_sec: float,
    zoom_rate: float = 0.00012,
) -> str:
    """Build ffmpeg filter_complex for N images with Ken Burns zoom + concat.

    For each image i:
      [i:v]scale={W}:{H}:force_original_aspect_ratio=increase,
           crop={W}:{H},
           setsar=1,
           zoompan=z='1+{rate}*on':d={frames}:s={W}x{H}:fps={fps},
           trim=duration={per_image_sec},
           setpts=PTS-STARTPTS,
           format=yuv420p
      [v{i}];
    Then [v0][v1]...[vN-1]concat=n=N:v=1:a=0[v]
    """
    n = len(images)
    frames_per = int(round(per_image_sec * fps))
    parts = []
    concat_inputs = []
    for i in range(n):
        parts.append(
            f"[{i}:v]"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"setsar=1,"
            f"zoompan=z='1+{zoom_rate}*on':d={frames_per}:s={width}x{height}:fps={fps},"
            f"trim=duration={per_image_sec},"
            f"setpts=PTS-STARTPTS,"
            f"format=yuv420p"
            f"[v{i}]"
        )
        concat_inputs.append(f"[v{i}]")
    parts.append(f"{''.join(concat_inputs)}concat=n={n}:v=1:a=0[v]")
    return ";".join(parts)


def _make_slideshow(
    images: list[str],
    audio_path: str,
    output_path: str,
    *,
    width: int,
    height: int,
    fps: int = 25,
    audio_bitrate: str = "192k",
) -> bool:
    """Common implementation for long and shorts slideshow."""
    if not images:
        logger.error("[SLIDESHOW] no images provided")
        return False
    for img in images:
        if not os.path.isfile(img):
            logger.error("[SLIDESHOW] missing image: %s", img)
            return False
    if not os.path.isfile(audio_path):
        logger.error("[SLIDESHOW] missing audio: %s", audio_path)
        return False

    duration = _ffprobe_duration(audio_path)
    if duration <= 0:
        logger.error("[SLIDESHOW] invalid audio duration")
        return False

    per_image = duration / len(images)
    filter_complex = _build_kenburns_filter(images, width, height, fps, per_image)

    cmd = ["ffmpeg", "-y"]
    for img in images:
        cmd += ["-loop", "1", "-i", img]
    cmd += [
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", f"{len(images)}:a",
        "-c:v", "libx264", "-preset", "veryfast", "-r", str(fps),
        "-c:a", "aac", "-b:a", audio_bitrate,
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        logger.info("[SLIDESHOW] %s images %.1fs each → %s",
                    len(images), per_image, output_path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("[SLIDESHOW] ffmpeg failed (%d): %s",
                         result.returncode, result.stderr[-500:])
            return False
        return os.path.isfile(output_path)
    except Exception as exc:
        logger.exception("[SLIDESHOW] crashed: %s", exc)
        return False


def make_long_slideshow(images: list[str], audio_path: str, output_path: str,
                        fps: int = 25) -> bool:
    """Yii-equivalent ``makeYoutubeVideoFrom5Images`` — 1920×1080 long video.

    Used for News long-form upload (id_yt_acc=55) — 5 SerpAPI images +
    TTS narration → YouTube long video.
    """
    return _make_slideshow(images, audio_path, output_path,
                           width=1920, height=1080, fps=fps)


def make_shorts_slideshow(images: list[str], audio_path: str, output_path: str,
                          fps: int = 25) -> bool:
    """Yii-equivalent ``makeShortsFrom5Images`` — 1080×1920 vertical."""
    return _make_slideshow(images, audio_path, output_path,
                           width=1080, height=1920, fps=fps,
                           audio_bitrate="128k")


def burn_subtitles(
    input_video: str,
    subtitles_path: str,
    output_path: str,
    *,
    font_name: str = "Arial",
    font_size: int = 14,
    margin_v: int = 160,
    primary_colour: str = "&H00FFFFFF",
    outline_colour: str = "&H00000000",
    outline: int = 4,
    shadow: int = 2,
    alignment: int = 2,  # 2 = bottom-center
) -> bool:
    """Burn-in SRT/ASS subtitles via ffmpeg ``subtitles`` filter.

    1:1 port of Yii ``addSubtitlesToShorts``::

        $style = "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,
                  OutlineColour=&H00000000,BorderStyle=1,Outline=4,
                  Shadow=2,Alignment=2,MarginV=160";
    """
    if not os.path.isfile(input_video):
        logger.error("[BURN] missing input: %s", input_video)
        return False
    if not os.path.isfile(subtitles_path):
        logger.error("[BURN] missing subtitles: %s", subtitles_path)
        return False

    # ffmpeg subtitles filter quoting: escape single quotes
    subs_escaped = subtitles_path.replace("'", "\\'").replace(":", "\\:")
    style = (
        f"FontName={font_name},FontSize={font_size},"
        f"PrimaryColour={primary_colour},OutlineColour={outline_colour},"
        f"BorderStyle=1,Outline={outline},Shadow={shadow},"
        f"Alignment={alignment},MarginV={margin_v}"
    )
    vf = f"subtitles='{subs_escaped}':force_style='{style}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-vf", vf,
        "-c:a", "copy",
        output_path,
    ]
    try:
        logger.info("[BURN] %s + %s → %s", input_video, subtitles_path, output_path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("[BURN] ffmpeg failed (%d): %s",
                         result.returncode, result.stderr[-500:])
            return False
        return os.path.isfile(output_path)
    except Exception as exc:
        logger.exception("[BURN] crashed: %s", exc)
        return False
