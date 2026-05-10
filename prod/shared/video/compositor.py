"""1920×1080 cover image compositor — 1:1 port of Yii ``create_youtube_image``.

Used by:
- DLE long-form upload (cover with book namebook + author + book cover overlay)
- News long-form (title + topic label, no cover overlay)
- Future: Sora pipeline thumbnails

Logic:
    1. Load PNG background, scale ×1.01, random offset crop to 1920×1080
    2. If overlay (book cover) — paste in top-left, ×2 size, offset (30, 30)
    3. Top label (e.g. "ФАНТАСТИКА", uppercase author) — fontSize 100,
       black 60/127 alpha bg-rect, brand colour text, centered.
    4. Body text (title) — split by word count:
       wordCount > 10 → 3 lines
       wordCount > 3  → 2 lines
       else           → 1 line
       Per-line dynamic font: try maxFontSize=150, decrement by 2 until fits.
       Bg-rect under each line (alpha 60/127), brand colour text.

Brand colours (per Yii sources):
- audiokniga, knigi-audio (Unique_audio): green neon (49, 232, 74)
- bazaknig, books-online, club-books, slushat, knigi-online: white
"""

from __future__ import annotations

import logging
import os
import random
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Standard 1920×1080 — never deviates per Yii
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080


@dataclass(frozen=True)
class BrandColour:
    """RGB colour for cover text. Default = white."""
    r: int = 255
    g: int = 255
    b: int = 255

    @property
    def rgb(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)


# Per-source brand colours (matches Yii exactly)
BRAND_GREEN = BrandColour(49, 232, 74)   # audiokniga, unique_audio (knigi-audio)
BRAND_WHITE = BrandColour(255, 255, 255) # all others


_FONT_BEBASNEUE = "/var/www/fastuser/data/www/aiyoutube.pbnbots.com/yii/console/controllers/bebasneuecyrillic.ttf"
_FONT_DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _resolve_font(brand_font: str | None) -> str:
    """Return existing font path. Caller can override via brand_font."""
    if brand_font and os.path.isfile(brand_font):
        return brand_font
    if os.path.isfile(_FONT_BEBASNEUE):
        return _FONT_BEBASNEUE
    if os.path.isfile(_FONT_DEJAVU):
        return _FONT_DEJAVU
    raise FileNotFoundError(
        f"No suitable font: tried {brand_font}, {_FONT_BEBASNEUE}, {_FONT_DEJAVU}"
    )


def _split_into_lines(text: str) -> list[str]:
    """Yii-style line splitter:
    - >10 words → 3 lines (third/third/third)
    - >3 words  → 2 lines (half/half)
    - else      → 1 line
    """
    words = text.strip().split()
    n = len(words)
    if n > 10:
        third = (n + 2) // 3  # ceil(n/3)
        return [
            " ".join(words[:third]),
            " ".join(words[third : third * 2]),
            " ".join(words[third * 2 :]),
        ]
    if n > 3:
        half = (n + 1) // 2
        return [" ".join(words[:half]), " ".join(words[half:])]
    return [text.strip() or " "]


def create_youtube_image(
    output_path: str,
    background_path: str,
    title: str,
    top_text: str = "",
    overlay_path: str | None = None,
    *,
    brand_colour: BrandColour = BRAND_GREEN,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    font_path: str | None = None,
    max_font_size: int = 150,
    min_font_size: int = 40,
    letter_spacing: int = 10,
    line_spacing: int = 40,
    quality: int = 100,
) -> bool:
    """Compose a 1920×1080 YouTube cover image.

    Args:
        output_path: destination .jpg
        background_path: PNG background to scale + crop
        title: main body text (will be split by word count)
        top_text: optional uppercase label rendered top-center (e.g. genre)
        overlay_path: optional book cover, pasted top-left ×2 size
        brand_colour: text colour (default green; pass BRAND_WHITE for others)
        ...

    Returns:
        True on success. False on failure (logged).
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error("[COMPOSITOR] PIL not available")
        return _fallback_black_jpeg(output_path, width, height)

    try:
        font = _resolve_font(font_path)
    except FileNotFoundError as e:
        logger.error("[COMPOSITOR] %s", e)
        return False

    if not os.path.isfile(background_path):
        logger.error("[COMPOSITOR] Background not found: %s", background_path)
        return False

    try:
        # 1. Background: scale ×1.01, random offset crop
        bg = Image.open(background_path).convert("RGBA")
        scale = 1.01
        sw, sh = int(bg.width * scale), int(bg.height * scale)
        bg = bg.resize((sw, sh), Image.LANCZOS)
        ox = random.randint(0, max(0, sw - width))
        oy = random.randint(0, max(0, sh - height))
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 255))
        canvas.paste(bg.crop((ox, oy, ox + width, oy + height)), (0, 0))

        draw = ImageDraw.Draw(canvas, "RGBA")
        colour = brand_colour.rgb + (255,)
        bg_rect = (0, 0, 0, 60 * 255 // 127)  # 60/127 alpha → 0..255

        # 2. Overlay (book cover) — top-left, ×2 size, offset (30, 30)
        overlay_shift_x = 0
        if overlay_path and os.path.isfile(overlay_path):
            try:
                overlay = Image.open(overlay_path).convert("RGBA")
                ow, oh = overlay.width * 2, overlay.height * 2
                overlay = overlay.resize((ow, oh), Image.LANCZOS)
                canvas.paste(overlay, (30, 30), overlay)
                overlay_shift_x = ow + 60
            except Exception as exc:
                logger.warning("[COMPOSITOR] overlay paste failed: %s", exc)

        # 3. Top text (uppercase label)
        if top_text:
            top_size = 100
            top_y = 150
            top_font = ImageFont.truetype(font, top_size)
            tbox = draw.textbbox((0, 0), top_text, font=top_font)
            tw, th = tbox[2] - tbox[0], tbox[3] - tbox[1]
            tx = overlay_shift_x + (width - overlay_shift_x - tw) // 2

            padding = 30
            draw.rectangle(
                (tx - padding, top_y - th - padding // 2,
                 tx + tw + padding, top_y + padding // 2),
                fill=bg_rect
            )
            draw.text((tx, top_y - th), top_text, fill=colour, font=top_font)

        # 4. Body text — multi-line, dynamic font size per line
        lines = _split_into_lines(title)
        zone_start = overlay_shift_x
        zone_width = width - overlay_shift_x - 60

        y_start = 620
        shift_text = 120 if len(lines) > 1 else 0

        for idx, line in enumerate(lines):
            font_size2 = max_font_size
            line_font: ImageFont.FreeTypeFont
            total_width = 0
            while font_size2 >= min_font_size:
                line_font = ImageFont.truetype(font, font_size2)
                # measure char-by-char with letter_spacing
                char_widths = []
                for ch in line:
                    cb = draw.textbbox((0, 0), ch, font=line_font)
                    char_widths.append(cb[2] - cb[0])
                total_width = sum(char_widths) + letter_spacing * (len(char_widths) - 1)
                if total_width <= zone_width:
                    break
                font_size2 -= 2

            line_font = ImageFont.truetype(font, font_size2)
            tx = zone_start + (zone_width - total_width) // 2
            ly = y_start - shift_text + idx * (font_size2 + line_spacing)

            # bg rect for this line
            line_bbox = draw.textbbox((0, 0), line, font=line_font)
            line_h = line_bbox[3] - line_bbox[1]
            padding = 30
            draw.rectangle(
                (tx - padding, ly - line_h - padding // 2,
                 tx + total_width + padding, ly + padding // 2),
                fill=bg_rect
            )

            # render char-by-char with letter_spacing
            cx = tx
            for ch in line:
                cb = draw.textbbox((0, 0), ch, font=line_font)
                cw = cb[2] - cb[0]
                draw.text((cx, ly - line_h), ch, fill=colour, font=line_font)
                cx += cw + letter_spacing

        canvas.convert("RGB").save(output_path, "JPEG", quality=quality)
        logger.info("[COMPOSITOR] Saved %s", output_path)
        return True

    except Exception as exc:
        logger.exception("[COMPOSITOR] Failed: %s", exc)
        return False


def _fallback_black_jpeg(output_path: str, width: int, height: int) -> bool:
    """Last-resort black canvas via ffmpeg (no PIL needed)."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             f"color=black:s={width}x{height}:d=1", "-vframes", "1", output_path],
            check=True, capture_output=True
        )
        return True
    except Exception as exc:
        logger.error("[COMPOSITOR] Black fallback failed: %s", exc)
        return False
