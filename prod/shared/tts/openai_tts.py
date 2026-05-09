"""OpenAI Text-to-Speech wrapper.

Replaces the legacy Yii `actionTts_openai($modelId, $text, $outputFile, $lang,
$gender, $voice, $instructions)` shell-out used across 8 DLE controllers
(audiokniga_one_com, books_online_info, bazaknig_net, club_books_ru,
knigi_online_club, slushat_knigi_com, unique_audio, sora).

Public API:
    synthesize(text, output_path, *, voice="nova", model="gpt-4o-mini-tts",
               language=None, instructions=None, response_format="mp3",
               speed=1.0) -> Path
    list_voices() -> list[str]
    map_language_to_voice(language_code, gender="female") -> str

Long inputs (>4096 chars) are split on sentence boundaries into chunks of
<=4000 chars, each chunk synthesised separately, then concatenated via
ffmpeg concat demuxer. This mirrors the legacy chunked behaviour used by
DLE controllers.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


# OpenAI Audio Speech API official voice list (as of 2025-11)
_VOICES = [
    "alloy", "ash", "ballad", "coral", "echo", "fable",
    "onyx", "nova", "sage", "shimmer", "verse",
]

# Mirrors the legacy PHP comment:
#   male: onyx, echo, fable
#   female: nova, shimmer, alloy
#   neutral: shimmer, alloy
_GENDER_VOICES = {
    "male":    {"ru": "onyx",    "uk": "onyx",    "en": "echo"},
    "female":  {"ru": "nova",    "uk": "nova",    "en": "shimmer"},
    "neutral": {"ru": "shimmer", "uk": "shimmer", "en": "alloy"},
}

_DEFAULT_VOICE = "nova"
_MAX_INPUT = 4096          # OpenAI hard limit per request
_CHUNK_SIZE = 4000         # safety margin
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?\n])\s+")


# ── Public ────────────────────────────────────────────────────────────────

def list_voices() -> list[str]:
    """Return available OpenAI TTS voice names."""
    return list(_VOICES)


def map_language_to_voice(language_code: str, gender: str = "female") -> str:
    """Pick a sensible default voice for (language, gender).

    Falls back to `nova` when the combination is unknown — matching the
    legacy PHP behaviour where most DLE controllers default to nova/female.
    """
    g = (gender or "female").lower()
    lc = (language_code or "ru").lower()[:2]
    return _GENDER_VOICES.get(g, _GENDER_VOICES["female"]).get(lc, _DEFAULT_VOICE)


def synthesize(
    text: str,
    output_path: Path | str,
    *,
    voice: str = "nova",
    model: str = "gpt-4o-mini-tts",
    language: str | None = None,
    instructions: str | None = None,
    response_format: str = "mp3",
    speed: float = 1.0,
) -> Path:
    """Synthesize `text` to `output_path` via OpenAI Audio Speech API.

    Raises:
        RuntimeError if OPENAI_API_KEY env is missing.
        RuntimeError on synthesis failure.
    """
    if not text or not text.strip():
        raise ValueError("text must be non-empty")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set; cannot call OpenAI TTS. "
            "Add it to prod/.env/.env.api or your shell env."
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Lazy import so test environments without `openai` can still load module
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "openai SDK is not installed; `pip install openai>=1.30`"
        ) from exc

    client = OpenAI(api_key=api_key)

    # Build augmented instructions (language hint if provided)
    eff_instructions = _build_instructions(instructions, language)

    if len(text) <= _MAX_INPUT:
        _synthesize_one(client, text, output_path, voice=voice, model=model,
                        instructions=eff_instructions,
                        response_format=response_format, speed=speed)
        return output_path

    # Long input → chunk + concat
    chunks = _chunk_text(text, max_len=_CHUNK_SIZE)
    logger.info("[TTS] Long input %d chars → %d chunks", len(text), len(chunks))

    with tempfile.TemporaryDirectory(prefix="tts_chunks_") as tmpdir:
        tmp = Path(tmpdir)
        part_paths: list[Path] = []
        for idx, chunk in enumerate(chunks):
            part = tmp / f"part_{idx:04d}.{response_format}"
            _synthesize_one(client, chunk, part, voice=voice, model=model,
                            instructions=eff_instructions,
                            response_format=response_format, speed=speed)
            part_paths.append(part)

        _concat_audio(part_paths, output_path, response_format)

    return output_path


# ── Internals ─────────────────────────────────────────────────────────────

def _build_instructions(instructions: str | None, language: str | None) -> str | None:
    if instructions:
        return instructions
    if language:
        # Lightweight language hint (matches legacy "tільки мовна інструкція" branch)
        return f"Speak naturally in language: {language}."
    return None


def _synthesize_one(
    client,
    text: str,
    output_path: Path,
    *,
    voice: str,
    model: str,
    instructions: str | None,
    response_format: str,
    speed: float,
) -> None:
    """One call to client.audio.speech.create + stream response to file."""
    kwargs: dict = {
        "model": model,
        "voice": voice,
        "input": text,
        "response_format": response_format,
        "speed": speed,
    }
    if instructions:
        kwargs["instructions"] = instructions

    try:
        response = client.audio.speech.create(**kwargs)
    except Exception as exc:
        raise RuntimeError(f"OpenAI TTS request failed: {exc}") from exc

    # Prefer streaming write helper, fall back to .content
    try:
        if hasattr(response, "stream_to_file"):
            response.stream_to_file(str(output_path))
            return
        if hasattr(response, "write_to_file"):
            response.write_to_file(str(output_path))
            return
    except Exception as exc:
        logger.warning("[TTS] stream_to_file failed: %s — falling back to .content", exc)

    content = getattr(response, "content", None)
    if content is None and hasattr(response, "read"):
        content = response.read()
    if content is None:
        raise RuntimeError("OpenAI TTS response has no extractable audio content")
    Path(output_path).write_bytes(content)


def _chunk_text(text: str, max_len: int = _CHUNK_SIZE) -> list[str]:
    """Split text into chunks no longer than max_len, breaking on sentence
    boundaries (`.`, `!`, `?`, `\\n`) where possible.

    - Returns `[text]` if it already fits.
    - Returns `[]` only for empty input.
    - Falls back to hard slicing if a single sentence exceeds max_len.
    """
    if not text:
        return []
    if len(text) <= max_len:
        return [text]

    sentences = _SENT_SPLIT_RE.split(text)
    chunks: list[str] = []
    current = ""

    for sent in sentences:
        if not sent:
            continue
        if len(sent) > max_len:
            # Flush current
            if current:
                chunks.append(current.strip())
                current = ""
            # Hard-split the oversized sentence
            for i in range(0, len(sent), max_len):
                chunks.append(sent[i:i + max_len].strip())
            continue

        candidate = (current + " " + sent).strip() if current else sent
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = sent

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c]


def _concat_audio(parts: list[Path], output_path: Path, fmt: str) -> None:
    """Concatenate audio files via ffmpeg concat demuxer."""
    if not parts:
        raise RuntimeError("No parts to concatenate")
    if len(parts) == 1:
        shutil.copyfile(parts[0], output_path)
        return

    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH; required for chunk concat")

    list_file = output_path.parent / f".{output_path.stem}_concat.txt"
    try:
        list_file.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in parts),
            encoding="utf-8",
        )
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode(errors="replace")[-1500:]
            raise RuntimeError(f"ffmpeg concat failed: {stderr}") from exc
    finally:
        try:
            list_file.unlink()
        except OSError:
            pass
