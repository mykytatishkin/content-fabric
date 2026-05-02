"""Audio transcription using OpenAI Whisper API."""

import logging
from typing import Any

from openai import OpenAI
from app.core.config import api_settings

logger = logging.getLogger(__name__)


def transcribe_audio(file_path: str) -> str | None:
    """Transcribe audio file using OpenAI Whisper API."""
    if not api_settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set")
        return None

    client = OpenAI(api_key=api_settings.OPENAI_API_KEY)
    
    try:
        logger.info("Transcribing audio: %s", file_path)
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
        return transcript
    except Exception as e:
        logger.error("Transcription failed for %s: %s", file_path, e)
        return None


def transcribe_with_timestamps(file_path: str) -> dict[str, Any] | None:
    """Transcribe audio with segment timestamps (verbose_json)."""
    if not api_settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set")
        return None

    client = OpenAI(api_key=api_settings.OPENAI_API_KEY)
    
    try:
        logger.info("Transcribing audio with timestamps: %s", file_path)
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
        return response.model_dump()
    except Exception as e:
        logger.error("Transcription with timestamps failed for %s: %s", file_path, e)
        return None
