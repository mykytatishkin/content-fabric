"""Voice change processing — wraps the legacy VoiceChanger.

The heavy ML dependencies (torch, librosa, pyworld, etc.) live in the legacy
module.  This file provides a clean interface for the queue worker.

TODO (manual porting required):
    Voice ML module not yet ported to prod. See unported/core/voice/ for reference.
    1. Port unported/core/voice/voice_changer.py into prod/shared/voice/
    2. Install ML dependencies: torch, librosa, pyworld, soundfile, so-vits-svc
    3. Download voice models to prod server
    4. Set VOICE_MODELS_DIR env var pointing to models directory
    5. Test with: rq worker voice --url redis://localhost:6379
    6. The GPU (Quadro P2000) is available on prod server for inference
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Lazy-loaded to avoid importing heavy ML libs at module level
_voice_changer = None


def _get_changer():
    global _voice_changer
    if _voice_changer is None:
        from core.voice.voice_changer import VoiceChanger
        _voice_changer = VoiceChanger()
    return _voice_changer


def process_voice_change(
    source_file_path: str,
    output_file_path: str,
    voice_model: str | None = None,
    conversion_type: str = "male_to_female",
    method: str = "sovits",
    preserve_background: bool = False,
) -> dict[str, Any]:
    """Process a voice change task.

    Returns the result dict from VoiceChanger.process_file().
    """
    if not os.path.exists(source_file_path):
        raise FileNotFoundError(f"Source file not found: {source_file_path}")

    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    changer = _get_changer()
    result = changer.process_file(
        input_file=source_file_path,
        output_file=output_file_path,
        conversion_type=conversion_type,
        voice_model=voice_model,
        method=method,
        preserve_background=preserve_background,
    )

    logger.info(
        "Voice change complete: %s → %s (model=%s)",
        source_file_path, output_file_path, voice_model,
    )
    return result
