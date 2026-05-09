"""Tests for the Shorts pipeline modules."""

import pytest
from unittest.mock import patch, MagicMock
from shared.shorts.downloader import download_video
from shared.shorts.transcriber import transcribe_audio
from shared.shorts.highlight import find_highlights
from shared.queue.types import ShortsPayload
from workers.shorts_worker import run_shorts_job

@patch("subprocess.run")
def test_download_video_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    res = download_video("https://youtube.com/watch?v=123", "/tmp/out.mp4")
    assert res is True
    mock_run.assert_called_once()
    assert "yt-dlp" in mock_run.call_args[0][0]

@patch("subprocess.run")
def test_download_video_failure(mock_run):
    import subprocess
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="error")
    res = download_video("https://youtube.com/watch?v=123", "/tmp/out.mp4")
    assert res is False

@patch("shared.shorts.transcriber.OpenAI")
def test_transcribe_audio(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.audio.transcriptions.create.return_value = "This is a transcript"
    
    # Mock settings to have an API key
    with patch("shared.shorts.transcriber.api_settings") as mock_settings:
        mock_settings.OPENAI_API_KEY = "test-key"
        with patch("builtins.open", MagicMock()):
            res = transcribe_audio("dummy.mp3")
            assert res == "This is a transcript"

@patch("shared.shorts.highlight.OpenAI")
def test_find_highlights(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    # Mock GPT response - json_object mode requires a dict
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = '{"highlights": [{"start": 10, "end": 30, "title": "Highlight 1"}]}'
    mock_client.chat.completions.create.return_value = mock_completion
    
    transcript = {"segments": [{"start": 0, "end": 100, "text": "Some text"}]}
    
    with patch("shared.shorts.highlight.api_settings") as mock_settings:
        mock_settings.OPENAI_API_KEY = "test-key"
        res = find_highlights(transcript)
        assert len(res) == 1
        assert res[0]["start"] == 10
        assert res[0]["title"] == "Highlight 1"


# ── Regression: shorts worker must not blow up on None donor URL ────


@patch("workers.shorts_worker.telegram")
@patch("workers.shorts_worker.download_video")
def test_shorts_job_skips_when_donor_url_missing(mock_download, mock_tg):
    """Reproduces prod failure: ShortsPayload(donor_video_url=None) used to
    surface as `expected str, bytes or os.PathLike object, not NoneType`
    inside subprocess. We now return a clean skipped result and notify."""
    payload = ShortsPayload(channel_id=28, donor_video_url=None, limit=5)

    res = run_shorts_job(payload)

    assert res == {
        "ok": False,
        "error": (
            "donor_video_url is missing for channel 28; configure a default "
            "donor URL on the channel or pass one in the payload"
        ),
        "skipped": True,
    }
    # No download attempted
    mock_download.assert_not_called()
    # Telegram alert fired
    mock_tg.send.assert_called_once()


@patch("workers.shorts_worker.telegram")
@patch("workers.shorts_worker.download_video")
def test_shorts_job_skips_on_blank_donor_url(mock_download, mock_tg):
    """Whitespace-only donor URLs are also rejected."""
    payload = ShortsPayload(channel_id=28, donor_video_url="   ", limit=5)

    res = run_shorts_job(payload)

    assert res["ok"] is False
    assert res["skipped"] is True
    mock_download.assert_not_called()
