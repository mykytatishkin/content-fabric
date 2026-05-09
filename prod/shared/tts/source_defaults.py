"""Per-DLE-source TTS defaults recovered from the 8 legacy Yii controllers.

Source: `actionTts_openai(...)` call sites in:
    - Audiokniga_one_comController.php
    - Bazaknig_netController.php
    - Books_online_infoController.php
    - Club_books_ruController.php
    - Knigi_online_clubController.php
    - Slushat_knigi_comController.php
    - Unique_audioController.php
    - SoraController.php

For all DLE *audio-book* sources the call signature defaults to:
    language='ru', gender='female', voice='nova', style='fairytale',
    instructions=''  (empty → at runtime the PHP wrapper builds a language hint)

`SoraController` is the outlier — it uses a male voice ('fable') with the
'storytelling' style for its commented annotation flow.
"""

from __future__ import annotations

# Reusable instruction templates (translated from the PHP `style` block)
_INSTR_FAIRYTALE_RU = (
    "Озвучивай как тёплую сказку, с лёгким воодушевлением и доброй интонацией. "
    "Произноси чётко на русском языке, естественно расставляй паузы."
)
_INSTR_STORYTELLING_RU = (
    "Говори живо и выразительно, как увлечённый рассказчик у костра. "
    "Произноси чётко на русском языке."
)


SOURCE_TTS_DEFAULTS: dict[str, dict[str, str]] = {
    # 7 audiobook DLE sources — identical defaults
    "audiokniga_one_com": {
        "voice": "nova",
        "gender": "female",
        "language": "ru",
        "instructions": _INSTR_FAIRYTALE_RU,
    },
    "bazaknig_net": {
        "voice": "nova",
        "gender": "female",
        "language": "ru",
        "instructions": _INSTR_FAIRYTALE_RU,
    },
    "books_online_info": {
        "voice": "nova",
        "gender": "female",
        "language": "ru",
        "instructions": _INSTR_FAIRYTALE_RU,
    },
    "club_books_ru": {
        "voice": "nova",
        "gender": "female",
        "language": "ru",
        "instructions": _INSTR_FAIRYTALE_RU,
    },
    "knigi_online_club": {
        "voice": "nova",
        "gender": "female",
        "language": "ru",
        "instructions": _INSTR_FAIRYTALE_RU,
    },
    "slushat_knigi_com": {
        "voice": "nova",
        "gender": "female",
        "language": "ru",
        "instructions": _INSTR_FAIRYTALE_RU,
    },
    "unique_audio": {
        "voice": "nova",
        "gender": "female",
        "language": "ru",
        "instructions": _INSTR_FAIRYTALE_RU,
    },
    # Sora — narration controller, used the 'fable'/male/'storytelling'
    # variant in the (live) actionTts_openai call site.
    "sora": {
        "voice": "fable",
        "gender": "male",
        "language": "ru",
        "instructions": _INSTR_STORYTELLING_RU,
    },
}


_GENERIC_DEFAULT: dict[str, str] = {
    "voice": "nova",
    "gender": "female",
    "language": "ru",
    "instructions": _INSTR_FAIRYTALE_RU,
}


def get_defaults_for_source(slug: str) -> dict[str, str]:
    """Return TTS defaults dict for a DLE source slug.

    Falls back to a generic Russian-female default when the slug is unknown.
    Returned dict is always a fresh copy (safe to mutate by caller).
    """
    if slug in SOURCE_TTS_DEFAULTS:
        return dict(SOURCE_TTS_DEFAULTS[slug])
    return dict(_GENERIC_DEFAULT)
