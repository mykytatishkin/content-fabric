"""News text cleaning — 1:1 port of Yii ``cleanNewsText`` + ``makeTextFileFromNews``.

Both Yii functions strip HTML, remove "boilerplate" patterns ("Читайте також:",
"Фото:", URLs, etc), and collapse whitespace. ``makeTextFileFromNews`` is
slightly more aggressive (more patterns, raises on empty result).
"""

from __future__ import annotations

import re

# Patterns aggressive cleaner removes — direct port of Yii regex list
_REMOVE_PATTERNS_AGGRESSIVE = [
    re.compile(r"Читайте також:.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"Об этом сообщает.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"Про це повідомляє.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"Фото:.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"Источник:.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"Джерело:.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"https?://\S+", re.IGNORECASE),
]

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_ENT_RE = re.compile(r"&[a-z#0-9]+;", re.IGNORECASE)
_LIST_MARKER_RE = re.compile(r"^\s*[-–•]\s*", re.MULTILINE)
_WS_RE = re.compile(r"\s+", re.UNICODE)
_PARENS_RE = re.compile(r"\([^)]*\)", re.UNICODE)


def clean_for_tts(text: str) -> str:
    """Light-touch cleaner from ``NewsController::cleanNewsText``.

    Used for TTS input where a more permissive output is desired (we want to
    keep most of the prose intact, just remove boilerplate and noise).
    """
    if not text:
        return ""

    # Decode HTML entities + strip tags
    text = _HTML_TAG_RE.sub("", text)
    text = _HTML_ENT_RE.sub(" ", text)

    # Remove specific patterns
    text = re.sub(r"Читайте также:.*(\n|$)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Фото:.*(\n|$)", "", text, flags=re.IGNORECASE)

    # Strip parens (often contain "(t.me/...)" boilerplate)
    text = _PARENS_RE.sub("", text)

    # Strip list markers
    text = _LIST_MARKER_RE.sub("", text)

    # Collapse whitespace except double newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)

    return text.strip()


def prepare_text_file(title: str, content: str, out_path: str) -> str:
    """Aggressive cleaner from ``NewsController::makeTextFileFromNews``.

    Combines title + content, strips HTML, removes 6 boilerplate patterns,
    removes URLs, collapses whitespace. Writes to ``out_path``.

    Raises:
        ValueError if cleaned text is empty.
    """
    text = (title or "") + ". " + (content or "")
    text = _HTML_TAG_RE.sub("", text)
    text = _HTML_ENT_RE.sub(" ", text)

    for pat in _REMOVE_PATTERNS_AGGRESSIVE:
        text = pat.sub(" ", text)

    text = _WS_RE.sub(" ", text).strip()

    if not text:
        raise ValueError("Empty text after cleaning")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    return out_path
