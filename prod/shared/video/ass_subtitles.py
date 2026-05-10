"""Per-word ASS subtitle generator — 1:1 port of Yii actionShorts ASS block.

The Yii implementation lived inside every DLE controller's ``actionShorts``:
TTS audio is generated, normalised to 48 kHz stereo @ volume 1.4, then
the annotation text is split by whitespace, durations are distributed
evenly with a 2.0s reservation for the last word, and the resulting ASS
block is rendered with Lena.ttf @ 140px centered (Alignment=5) on a
1080×1920 canvas.

Why ASS (not SRT): each word lands at exact ms-precise timestamps with
its own ``Dialogue:`` line. SRT cannot do per-word styling reliably across
ffmpeg ``subtitles`` filter; ASS handles it cleanly with one event per word.

Usage:
    >>> ass = generate_per_word_ass(
    ...     text="Привіт світ як справи",
    ...     audio_duration_sec=4.5,
    ...     font_family="Lena",
    ...     font_size=140,
    ... )
    >>> Path("text.ass").write_text(ass)
"""

from __future__ import annotations

import re

# Defaults match Yii actionShorts:
#   Alignment=5 → centered on screen (not bottom)
#   Outline=4   → 4px black outline
#   Shadow=0    → no shadow (offset 0)
#   PrimaryColour &H00FFFFFF (white)
#   OutlineColour &H00000000 (black)
#   BackColour &H64000000 (semi-transparent black background)
_MIN_WORD_DURATION_SEC = 0.22  # below this, the player may not render
_LAST_WORD_RESERVE_SEC = 2.0   # tail buffer for the closing word


def sec2ass(t: float) -> str:
    """Convert seconds → ASS timestamp ``H:MM:SS.cc``.

    1:1 port of Yii ``MyFunction::sec2ass``::

        $h = floor($t / 3600);
        $m = floor(($t % 3600) / 60);
        $s = fmod($t, 60);
        return sprintf('%01d:%02d:%05.2f', $h, $m, $s);

    >>> sec2ass(0)
    '0:00:00.00'
    >>> sec2ass(12.34)
    '0:00:12.34'
    >>> sec2ass(3661.5)
    '1:01:01.50'
    """
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:01d}:{m:02d}:{s:05.2f}"


def _split_words(text: str) -> list[str]:
    """Split text on whitespace, drop empties — same as PHP ``preg_split('/\\s+/')``."""
    return [w for w in re.split(r"\s+", text.strip()) if w]


def generate_per_word_ass(
    text: str,
    audio_duration_sec: float,
    *,
    font_family: str = "Lena",
    font_size: int = 140,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    alignment: int = 5,  # 5 = centered on screen, 2 = bottom-center
    outline: int = 4,
    shadow: int = 0,
    margin_v: int = 120,
) -> str:
    """Generate ASS subtitle file content with per-word ``Dialogue:`` events.

    1:1 port of the ASS generation block in Yii ``actionShorts`` (DLE
    controllers). Each word gets evenly-distributed timing, last word
    receives the audio tail starting at ``audio_duration_sec - 2.0s``
    (or shorter if audio is short).

    Args:
        text: annotation text (one quote / one phrase).
        audio_duration_sec: total TTS audio length in seconds.
        font_family: must be installed system-wide (use ``fc-scan`` to verify).
        font_size: in pixels at PlayRes resolution.
        play_res_x/y: ASS canvas (must match output video resolution).
        alignment: 1-9, 5=center, 2=bottom-center.
        outline/shadow: text effects in pixels.
        margin_v: vertical margin from bottom (only used for alignment=2).

    Returns:
        Full ASS file content (header + V4+ Styles + Events + Dialogue lines).
        Caller writes to disk and references via ffmpeg ``-vf "ass=path"``.
    """
    words = _split_words(text)
    n = len(words)

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "Collisions: Normal\n"
        f"PlayResX: {play_res_x}\n"
        f"PlayResY: {play_res_y}\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_family},{font_size},&H00FFFFFF,&H000000FF,"
        f"&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},"
        f"{alignment},60,60,{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )

    if n == 0:
        return header

    if n == 1:
        return (
            header
            + f"Dialogue: 0,0:00:00.00,{sec2ass(audio_duration_sec)},Default,,0,0,0,,{words[0]}\n"
        )

    # Compute timing — same logic as Yii.
    # If audio is too short, shrink the last-word reserve so words still fit.
    last_reserve = _LAST_WORD_RESERVE_SEC
    if audio_duration_sec < (n * _MIN_WORD_DURATION_SEC) + last_reserve:
        last_reserve = max(_MIN_WORD_DURATION_SEC, audio_duration_sec - n * _MIN_WORD_DURATION_SEC)
        if last_reserve < _MIN_WORD_DURATION_SEC:
            last_reserve = _MIN_WORD_DURATION_SEC

    usable_time = max(0.0, audio_duration_sec - last_reserve)
    per_word = max(_MIN_WORD_DURATION_SEC, usable_time / max(1, n - 1))

    lines: list[str] = []
    t = 0.0
    for i in range(n - 1):
        start = t
        end = t + per_word
        if end - start < _MIN_WORD_DURATION_SEC:
            end = start + _MIN_WORD_DURATION_SEC
        if end > usable_time:
            end = usable_time
        if end <= start:
            end = start + _MIN_WORD_DURATION_SEC * 1.001
        lines.append(
            f"Dialogue: 0,{sec2ass(start)},{sec2ass(end)},Default,,0,0,0,,{words[i]}"
        )
        t = end

    # Last word — claims the audio tail
    start_last = t
    end_last = audio_duration_sec
    if end_last - start_last < last_reserve:
        start_last = max(0.0, end_last - last_reserve)
        if start_last <= t:
            start_last = t
    if end_last <= start_last:
        end_last = start_last + _MIN_WORD_DURATION_SEC
    lines.append(
        f"Dialogue: 0,{sec2ass(start_last)},{sec2ass(end_last)},Default,,0,0,0,,{words[-1]}"
    )

    return header + "\n".join(lines) + "\n"
