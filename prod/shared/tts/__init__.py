"""Text-to-Speech modules for Content Fabric.

Subpackage layout:
    openai_tts.py      - OpenAI Audio Speech API (`gpt-4o-mini-tts` etc.)
    source_defaults.py - Per-DLE-source voice/instructions defaults

This is a *sibling* to `shared.voice` (Silero/RVC voice conversion); it does NOT
replace the existing voice subsystem. Choose between them based on need:
    - `shared.voice` — RU voice cloning of an existing audio file
    - `shared.tts`   — generate audio from raw text via OpenAI
"""

from shared.tts.openai_tts import (
    list_voices,
    map_language_to_voice,
    synthesize,
)
from shared.tts.source_defaults import (
    SOURCE_TTS_DEFAULTS,
    get_defaults_for_source,
)

__all__ = [
    "synthesize",
    "list_voices",
    "map_language_to_voice",
    "SOURCE_TTS_DEFAULTS",
    "get_defaults_for_source",
]
