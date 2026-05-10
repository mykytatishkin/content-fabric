"""Sora meme caption overlay — restores Yii ``SoraController::actionShorts``.

This was the iconic Yii feature: Sora-generated AI videos get processed
through GPT-4o-mini Vision (3 frames described) → GPT-4o-mini meme caption
generator → GPT-4o-mini JSON metadata → ffmpeg drawtext bottom-center
overlay. Result: a viral-ready short with funny meme caption.

The current CFF Sora worker just enqueues sora videos into the standard
Shorts pipeline (Whisper-based highlights) — losing the meme/funny nature.

This module is invoked by ``sora_worker`` when ``payload.metadata['mode'] ==
'meme'`` (else falls through to the existing standard Shorts path).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


_GPT_MODEL = "gpt-4o-mini"
_DEJAVU_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


@dataclass
class MemeMetadata:
    """Output of GPT JSON metadata generation."""
    title: str
    description: str
    hashtags: list[str]
    first_comment: str


def _ffprobe_duration(video_path: str) -> float:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", video_path],
            text=True
        ).strip()
        return float(out)
    except Exception as exc:
        logger.error("[SORA MEME] ffprobe failed: %s", exc)
        return 0.0


def _extract_frame_at(video_path: str, time_sec: float, output_jpg: str) -> bool:
    """Extract single frame at ``time_sec`` to JPG."""
    h = int(time_sec // 3600)
    m = int((time_sec % 3600) // 60)
    s = int(time_sec - h * 3600 - m * 60)
    timestamp = f"{h:02d}:{m:02d}:{s:02d}"

    cmd = ["ffmpeg", "-y", "-ss", timestamp, "-i", video_path,
           "-vframes", "1", "-q:v", "2", output_jpg]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return os.path.isfile(output_jpg)
    except subprocess.CalledProcessError as e:
        logger.error("[SORA MEME] frame extract failed: %s", e.stderr[-300:])
        return False


def _gpt_describe_frame(image_path: str, *, api_key: str) -> str:
    """GPT-4o-mini Vision: describe frame in 2-3 sentences (emotion, atmosphere, subtext).

    1:1 prompt from Yii ``SoraController::actionShorts``.
    """
    import base64
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    try:
        resp = client.chat.completions.create(
            model=_GPT_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": "Опиши коротко цей кадр у 2-3 реченнях. "
                             "Вкажи емоцію, атмосферу і можливий підтекст."},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        logger.error("[SORA MEME] vision call failed: %s", exc)
        return ""


def describe_frames(video_path: str, output_dir: str, *, api_key: str) -> list[dict[str, Any]]:
    """Extract 3 frames (20%/50%/80% timepoints) → GPT Vision descriptions.

    Returns: [{frame_path, time_sec, description}, ...]
    """
    duration = _ffprobe_duration(video_path)
    if duration <= 0:
        return []

    os.makedirs(output_dir, exist_ok=True)
    points = [duration * 0.2, duration * 0.5, duration * 0.8]

    results: list[dict[str, Any]] = []
    for i, time_sec in enumerate(points, start=1):
        frame = os.path.join(output_dir, f"frame_{i}.jpg")
        if not _extract_frame_at(video_path, time_sec, frame):
            continue
        desc = _gpt_describe_frame(frame, api_key=api_key)
        if desc:
            results.append({"frame_path": frame, "time_sec": time_sec, "description": desc})
            logger.info("[SORA MEME] frame %d (@%.1fs): %s", i, time_sec, desc[:120])
    return results


def generate_funny_caption(frame_descriptions: list[dict[str, Any]], *, api_key: str) -> str:
    """1:1 port of Yii ``generateFunnyCaption``.

    GPT-4o-mini, temperature=0.9, max_tokens=100. Returns 1-2 sentence
    ironic meme-style caption. Empty string on failure.
    """
    from openai import OpenAI

    if not frame_descriptions:
        return ""

    descriptions_block = "\n\n".join(
        f"{os.path.basename(f['frame_path'])}:\n{f['description']}"
        for f in frame_descriptions
    )

    prompt = f"""Ти — креативний сценарист для TikTok / YouTube Shorts.
На основі коротких описів трьох кадрів з відео створи 1 гумористичний опис \
(1-2 речення), у стилі мемів або короткої фрази або легкий гумор для підпису \
до відео.

Будь дотепним, але не грубим. Стиль — іронічний, легкий, ніби короткий мем у \
соцмережах.

Ось описи кадрів:
{descriptions_block}

Формат відповіді: тільки готовий короткий текст для опису (без пояснень і лапок)."""

    client = OpenAI(api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model=_GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=100,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.error("[SORA MEME] caption generation failed: %s", exc)
        return ""


def generate_meme_metadata(
    caption_text: str, *, api_key: str, max_attempts: int = 5,
) -> MemeMetadata | None:
    """1:1 port of Yii ``generateShortsMetaWithAI``.

    Returns structured metadata: title (≤70 chars), description (1-2 sent),
    hashtags (≤15), first_comment. Retries up to max_attempts on JSON
    parse failure (matching Yii's retry loop).
    """
    from openai import OpenAI

    prompt = f"""Ти — креативний сценарист YouTube Shorts, який створює короткі \
гумористичні тексти.

На основі цього тексту створи:
1. "title" — коротку, чіпляючу назву (до 70 символів, у стилі мемів);
2. "description" — 1–2 речення з легким гумором і розмовним тоном українською;
3. "hashtags" — до 15 штук, у форматі #shorts #гумор #меми ...;
4. "first_comment" — перший коментар від автора (жарт, запитання до глядачів, \
або дотепна реакція, щоб стимулювати коментарі).

Текст із відео:
---
{caption_text}
---

Відповідь поверни строго у JSON:
{{
  "title": "...",
  "description": "...",
  "hashtags": ["#...", "#...", "..."],
  "first_comment": "..."
}}"""

    client = OpenAI(api_key=api_key)

    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.chat.completions.create(
                model=_GPT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            reply = (resp.choices[0].message.content or "").strip()
            data = json.loads(reply)

            if "title" not in data:
                logger.warning("[SORA MEME] metadata missing 'title' (attempt %d)", attempt)
                if attempt < max_attempts:
                    time.sleep(3)
                    continue
                return None

            return MemeMetadata(
                title=str(data.get("title", ""))[:200],
                description=str(data.get("description", "")),
                hashtags=[str(h) for h in (data.get("hashtags") or []) if h],
                first_comment=str(data.get("first_comment", "")),
            )
        except json.JSONDecodeError as exc:
            logger.warning("[SORA MEME] JSON parse failed (attempt %d): %s", attempt, exc)
            if attempt < max_attempts:
                time.sleep(3)
        except Exception as exc:
            logger.error("[SORA MEME] metadata call failed (attempt %d): %s", attempt, exc)
            if attempt < max_attempts:
                time.sleep(3)

    return None


# Emoji ranges from Yii (preg_replace stripping)
_EMOJI_RANGES = [
    (0x1F300, 0x1FAFF),   # symbols & pictographs
    (0x2600,  0x26FF),    # miscellaneous symbols
    (0x2700,  0x27BF),    # dingbats
]


def strip_emojis(text: str) -> str:
    """Remove emoji code-point ranges. 1:1 port of Yii preg_replace block."""
    out_chars = []
    for ch in text:
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES):
            continue
        out_chars.append(ch)
    return "".join(out_chars).strip()


def _wrap_text(text: str, max_line_length: int = 40) -> str:
    """Wordwrap text at ``max_line_length`` with hard cuts. Mirrors PHP wordwrap."""
    import textwrap
    return "\n".join(textwrap.wrap(text, width=max_line_length, break_long_words=True) or [""])


def _escape_for_drawtext(text: str) -> str:
    """Escape for ffmpeg drawtext text= parameter.

    ffmpeg drawtext is finicky: ``'``, ``"``, ``:``, ``\\``, ``%`` need escaping.
    """
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace('"', '\\"')
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    return text


def overlay_meme_caption(
    video_path: str,
    output_path: str,
    caption: str,
    *,
    font_path: str = _DEJAVU_FONT,
    font_size: int = 32,
    max_line_length: int = 40,
    box_alpha: float = 0.5,
) -> bool:
    """ffmpeg drawtext overlay: bottom-center black-box meme caption.

    1:1 port of Yii ``SoraController::actionShorts`` ffmpeg drawtext block::

        drawtext=text='{wrapped}':fontcolor=white:fontsize=32:
                  fontfile={font}:line_spacing=8:
                  box=1:boxcolor=black@0.5:boxborderw=12:
                  x=(w-text_w)/2:y=h-text_h-50:
                  fix_bounds=true:text_shaping=1
    """
    if not os.path.isfile(video_path):
        logger.error("[SORA MEME] missing video: %s", video_path)
        return False

    cleaned = strip_emojis(caption)
    if not cleaned:
        logger.error("[SORA MEME] empty caption after emoji strip")
        return False

    wrapped = _wrap_text(cleaned, max_line_length)
    escaped = _escape_for_drawtext(wrapped)

    if not os.path.isfile(font_path):
        logger.warning("[SORA MEME] font not found: %s — using ffmpeg default", font_path)
        font_arg = ""
    else:
        font_arg = f":fontfile={font_path}"

    drawtext = (
        f"drawtext=text='{escaped}':"
        f"fontcolor=white:"
        f"fontsize={font_size}{font_arg}:"
        f"line_spacing=8:"
        f"box=1:boxcolor=black@{box_alpha}:boxborderw=12:"
        f"x=(w-text_w)/2:y=h-text_h-50:"
        f"fix_bounds=true:text_shaping=1"
    )

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", drawtext,
        "-c:a", "copy",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("[SORA MEME] drawtext ffmpeg failed (%d): %s",
                         result.returncode, result.stderr[-500:])
            return False
        return os.path.isfile(output_path)
    except Exception as exc:
        logger.exception("[SORA MEME] drawtext crashed: %s", exc)
        return False


def build_meme_short(
    video_path: str,
    output_path: str,
    work_dir: str,
    *,
    api_key: str | None = None,
) -> dict[str, Any] | None:
    """End-to-end: 3 frames → descriptions → caption → metadata → overlay.

    Returns:
        On success: dict with keys
            ``output_path``, ``caption``, ``title``, ``description``,
            ``hashtags``, ``first_comment``, ``hashtags_shuffled_str``.
        On failure: None (logs error).

    Mirrors Yii ``SoraController::actionShorts`` in full.
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("[SORA MEME] OPENAI_API_KEY not set")
        return None

    os.makedirs(work_dir, exist_ok=True)

    # Step 1: 3 frames + descriptions
    frames = describe_frames(video_path, work_dir, api_key=api_key)
    if not frames:
        logger.error("[SORA MEME] no frame descriptions generated")
        return None

    # Step 2: meme caption
    caption = generate_funny_caption(frames, api_key=api_key)
    if not caption:
        logger.error("[SORA MEME] caption generation returned empty")
        return None

    # Step 3: JSON metadata (title/description/hashtags/first_comment)
    metadata = generate_meme_metadata(caption, api_key=api_key)
    if not metadata:
        logger.error("[SORA MEME] metadata generation failed after retries")
        return None

    # Step 4: ffmpeg drawtext overlay
    if not overlay_meme_caption(video_path, output_path, caption):
        return None

    # Yii: shuffle hashtags, prepend 2 random to title, all into description
    import random as _random
    shuffled = list(metadata.hashtags)
    _random.shuffle(shuffled)
    title_with_tags = metadata.title + " " + " ".join(shuffled[:2])

    return {
        "output_path": output_path,
        "caption": caption,
        "title": title_with_tags[:255],
        "description": metadata.description + " " + " ".join(metadata.hashtags),
        "keywords": " ".join(metadata.hashtags),
        "first_comment": metadata.first_comment,
        "hashtags_shuffled": shuffled,
    }
