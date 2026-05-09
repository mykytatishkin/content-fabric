"""Unit tests for shared.tts.openai_tts and shared.tts.source_defaults.

NO real OpenAI calls are made — `openai.OpenAI` is mocked everywhere.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Provide a stub `openai` module so import works in CI without the SDK
if "openai" not in sys.modules:
    _stub = MagicMock()
    _stub.OpenAI = MagicMock()
    sys.modules["openai"] = _stub

from shared.tts import openai_tts  # noqa: E402
from shared.tts.openai_tts import (  # noqa: E402
    _chunk_text,
    list_voices,
    map_language_to_voice,
    synthesize,
)
from shared.tts.source_defaults import (  # noqa: E402
    SOURCE_TTS_DEFAULTS,
    get_defaults_for_source,
)


# ── Helpers ─────────────────────────────────────────────────────────────

class _FakeStreamResponse:
    """Mimics openai SDK response object."""

    def __init__(self, payload: bytes = b"FAKEMP3DATA"):
        self._payload = payload
        self.content = payload

    def stream_to_file(self, path: str) -> None:
        Path(path).write_bytes(self._payload)


def _make_client(payload: bytes = b"FAKEMP3DATA"):
    fake = _FakeStreamResponse(payload)
    client = MagicMock()
    client.audio.speech.create.return_value = fake
    return client, fake


# ── _chunk_text ─────────────────────────────────────────────────────────

def test_chunk_text_short_returns_single():
    assert _chunk_text("Hello world.") == ["Hello world."]


def test_chunk_text_empty():
    assert _chunk_text("") == []


def test_chunk_text_exactly_4000_chars_single_chunk():
    text = ("a" * 3998) + "."
    assert len(text) == 3999
    chunks = _chunk_text(text, max_len=4000)
    assert chunks == [text]


def test_chunk_text_splits_on_sentence_boundary():
    sent = "Это предложение средней длины. "
    text = sent * 200  # ~6200 chars
    chunks = _chunk_text(text, max_len=1000)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 1000
    rebuilt = " ".join(chunks).replace("  ", " ").strip()
    assert "предложение" in rebuilt


def test_chunk_text_oversized_single_sentence_hard_split():
    # No sentence terminators at all → hard slice
    text = "x" * 5000
    chunks = _chunk_text(text, max_len=1000)
    assert len(chunks) == 5
    assert all(len(c) <= 1000 for c in chunks)


# ── list_voices / map_language_to_voice ─────────────────────────────────

def test_list_voices_contains_expected():
    voices = list_voices()
    for v in ["alloy", "nova", "onyx", "fable", "shimmer"]:
        assert v in voices
    assert len(voices) == 11


def test_map_language_to_voice_ru_female():
    assert map_language_to_voice("ru", "female") == "nova"


def test_map_language_to_voice_unknown_falls_back():
    # unknown language code → still returns a real voice
    voice = map_language_to_voice("xx", "female")
    assert voice in list_voices()


# ── synthesize: missing api key ─────────────────────────────────────────

def test_synthesize_missing_api_key_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        synthesize("hello", tmp_path / "out.mp3")


# ── synthesize: short input ─────────────────────────────────────────────

def test_synthesize_short_input_forwards_kwargs(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client, fake = _make_client(b"OGG-PAYLOAD")

    with patch("openai.OpenAI", return_value=client):
        out = synthesize(
            "Привет, мир.",
            tmp_path / "out.mp3",
            voice="nova",
            model="gpt-4o-mini-tts",
            language="ru",
            instructions="Speak warmly",
            response_format="mp3",
            speed=1.0,
        )

    assert out == tmp_path / "out.mp3"
    assert out.exists()
    assert out.read_bytes() == b"OGG-PAYLOAD"

    # Verify SDK was called with our kwargs
    client.audio.speech.create.assert_called_once()
    kwargs = client.audio.speech.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini-tts"
    assert kwargs["voice"] == "nova"
    assert kwargs["input"] == "Привет, мир."
    assert kwargs["response_format"] == "mp3"
    assert kwargs["speed"] == 1.0
    # explicit instructions forwarded
    assert kwargs["instructions"] == "Speak warmly"


def test_synthesize_writes_response_bytes_via_content_fallback(tmp_path, monkeypatch):
    """If stream_to_file is missing, fall back to .content payload."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    fake = MagicMock(spec=["content"])
    fake.content = b"BYTES-ONLY"
    client = MagicMock()
    client.audio.speech.create.return_value = fake

    with patch("openai.OpenAI", return_value=client):
        out = synthesize("Hello.", tmp_path / "out.mp3", voice="nova")

    assert out.read_bytes() == b"BYTES-ONLY"


# ── synthesize: long input → chunk + concat ─────────────────────────────

def test_synthesize_long_input_triggers_chunk_concat(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client, _ = _make_client(b"PART")

    long_text = ("Это предложение для тестирования. " * 200)  # ~6800 chars
    assert len(long_text) > 4096

    concat_mock = MagicMock()

    with patch("openai.OpenAI", return_value=client), \
         patch.object(openai_tts, "_concat_audio", concat_mock):
        out = synthesize(long_text, tmp_path / "long.mp3", voice="nova")

    # multi-chunk → SDK called more than once
    assert client.audio.speech.create.call_count >= 2
    # concat invoked with the per-chunk paths
    concat_mock.assert_called_once()
    parts, out_arg, fmt = concat_mock.call_args.args
    assert isinstance(parts, list)
    assert len(parts) == client.audio.speech.create.call_count
    assert out_arg == out
    assert fmt == "mp3"


# ── source_defaults ─────────────────────────────────────────────────────

def test_get_defaults_for_known_source_audiokniga():
    d = get_defaults_for_source("audiokniga_one_com")
    assert d["voice"] == "nova"
    assert d["gender"] == "female"
    assert d["language"] == "ru"
    assert isinstance(d["instructions"], str) and d["instructions"]
    # Returned dict is a copy — mutating must not affect the registry
    d["voice"] = "MUTATED"
    assert SOURCE_TTS_DEFAULTS["audiokniga_one_com"]["voice"] == "nova"


def test_get_defaults_for_sora_is_male_fable():
    d = get_defaults_for_source("sora")
    assert d["voice"] == "fable"
    assert d["gender"] == "male"


def test_get_defaults_for_unknown_slug_generic_fallback():
    d = get_defaults_for_source("totally_unknown_source_zzz")
    assert d["voice"] == "nova"
    assert d["gender"] == "female"
    assert d["language"] == "ru"
    assert d["instructions"]


def test_all_8_legacy_yii_controllers_have_entries():
    expected = {
        "audiokniga_one_com", "bazaknig_net", "books_online_info",
        "club_books_ru", "knigi_online_club", "slushat_knigi_com",
        "unique_audio", "sora",
    }
    assert expected.issubset(set(SOURCE_TTS_DEFAULTS.keys()))
