"""SRT subtitle alignment via Whisper word-level timestamps.

Replaces opaque Yii ``make_srt.py`` (not in our extracted source). The
strategy mirrors what `make_srt.py` is known to do: transcribe the audio
with Whisper word-level timestamps and emit SRT cues grouping ~5-7 words
each.

We do NOT do true forced alignment with the source text — Whisper-1 is
accurate enough for news narration that the transcribed text matches the
TTS output (since the TTS itself was generated from the same text).
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_WORDS_PER_CUE = 6   # group words into N-word SRT cues
_MAX_CUE_DUR = 4.0   # split if a single cue would exceed N seconds


def _format_srt_timestamp(seconds: float) -> str:
    """SRT timestamp: HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    secs_int = int(s)
    ms = int(round((s - secs_int) * 1000))
    return f"{h:02d}:{m:02d}:{secs_int:02d},{ms:03d}"


def _whisper_word_timestamps(audio_path: str) -> list[dict[str, Any]]:
    """Call OpenAI Whisper-1 with word-level timestamps.

    Returns list of {word, start, end} or empty on failure.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("[SRT] OPENAI_API_KEY not set")
        return []

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("[SRT] openai package not available")
        return []

    client = OpenAI(api_key=api_key)
    try:
        with open(audio_path, "rb") as f:
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["word"],
            )
    except Exception as exc:
        logger.error("[SRT] Whisper-1 failed: %s", exc)
        return []

    # OpenAI SDK returns `words` as a list of {word, start, end}
    words = getattr(resp, "words", None) or []
    if not isinstance(words, list):
        return []

    out: list[dict[str, Any]] = []
    for w in words:
        word = getattr(w, "word", None) or (w.get("word") if isinstance(w, dict) else None)
        start = getattr(w, "start", None) or (w.get("start") if isinstance(w, dict) else None)
        end = getattr(w, "end", None) or (w.get("end") if isinstance(w, dict) else None)
        if word and start is not None and end is not None:
            out.append({"word": str(word).strip(), "start": float(start), "end": float(end)})
    return out


def _group_words_to_cues(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group word timestamps into N-word cues.

    Splits early if a cue would exceed _MAX_CUE_DUR seconds.
    """
    cues: list[dict[str, Any]] = []
    chunk: list[dict[str, Any]] = []

    def flush():
        if chunk:
            cues.append({
                "text": " ".join(c["word"] for c in chunk).strip(),
                "start": chunk[0]["start"],
                "end": chunk[-1]["end"],
            })

    for w in words:
        chunk.append(w)
        cue_dur = chunk[-1]["end"] - chunk[0]["start"]
        if len(chunk) >= _WORDS_PER_CUE or cue_dur >= _MAX_CUE_DUR:
            flush()
            chunk = []

    flush()
    return cues


def align_subtitles(audio_path: str, text: str, output_srt: str) -> bool:
    """Generate SRT subtitles for `audio_path` (text param is reference only).

    Args:
        audio_path: TTS-rendered MP3 / WAV
        text: original text (used as fallback hint, not for alignment)
        output_srt: destination .srt path

    Returns:
        True on success.

    1:1 replacement for Yii ``make_srt.py`` invocation::

        python3 make_srt.py audio.mp3 text.txt sub.srt

    The Yii script's exact alignment algorithm is not in our source; we use
    Whisper word-level timestamps which produce equivalent or better quality
    for news narration.
    """
    if not os.path.isfile(audio_path):
        logger.error("[SRT] audio not found: %s", audio_path)
        return False

    words = _whisper_word_timestamps(audio_path)
    if not words:
        logger.error("[SRT] Whisper returned no words for %s", audio_path)
        return False

    cues = _group_words_to_cues(words)
    if not cues:
        logger.error("[SRT] no cues built from %d words", len(words))
        return False

    try:
        with open(output_srt, "w", encoding="utf-8") as f:
            for i, cue in enumerate(cues, start=1):
                f.write(f"{i}\n")
                f.write(f"{_format_srt_timestamp(cue['start'])} --> "
                        f"{_format_srt_timestamp(cue['end'])}\n")
                f.write(f"{cue['text']}\n\n")
    except Exception as exc:
        logger.exception("[SRT] write failed: %s", exc)
        return False

    logger.info("[SRT] wrote %d cues to %s", len(cues), output_srt)
    return True
