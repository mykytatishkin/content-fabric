"""Tests for /api/v1/dle-sources/* endpoint validation.

Specifically focuses on the run-now endpoint guard for non-existent
channel_id (an FK violation that would otherwise propagate to the worker).
"""

from contextlib import contextmanager
from unittest.mock import patch, MagicMock


@contextmanager
def _admin_session(sources: dict[str, str]):
    """Patch admin auth + dle_settings.all_sources for an endpoint test."""
    from tests.conftest import ADMIN_USER
    fake_settings = MagicMock()
    fake_settings.all_sources.return_value = sources
    with patch("app.api.deps.user_repo.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.api.endpoints.dle_sources.dle_settings", fake_settings):
        yield


def test_run_now_404_for_unknown_slug(app_client, admin_headers):
    """Bad slug must return 404 (and never enqueue a job)."""
    with _admin_session({"real_slug_com": "mysql://x"}), \
         patch("app.api.endpoints.dle_sources.enqueue_dle_ingestion") as enq:
        resp = app_client.post(
            "/api/v1/dle-sources/bogus_slug/run-now",
            json={"channel_id": 1, "limit": 1, "media_type": "video"},
            headers=admin_headers,
        )
    assert resp.status_code == 404
    enq.assert_not_called()


def test_run_now_400_when_channel_missing(app_client, admin_headers):
    """Unknown channel_id must be rejected with 400 BEFORE enqueuing.

    Without this guard the job would crash inside the worker on the
    platform_channels FK constraint (silent failure observable only in logs).
    """
    with _admin_session({"knigi_audio_biz": "mysql://x"}), \
         patch("shared.db.repositories.channel_repo.get_channel_by_id", return_value=None) as gc, \
         patch("app.api.endpoints.dle_sources.enqueue_dle_ingestion") as enq:
        resp = app_client.post(
            "/api/v1/dle-sources/knigi_audio_biz/run-now",
            json={"channel_id": 99999, "limit": 1, "media_type": "video"},
            headers=admin_headers,
        )
    assert resp.status_code == 400
    assert "99999" in resp.json()["detail"]
    gc.assert_called_once_with(99999)
    enq.assert_not_called()


def test_run_now_400_for_invalid_media_type(app_client, admin_headers):
    with _admin_session({"knigi_audio_biz": "mysql://x"}), \
         patch("app.api.endpoints.dle_sources.enqueue_dle_ingestion") as enq:
        resp = app_client.post(
            "/api/v1/dle-sources/knigi_audio_biz/run-now",
            json={"channel_id": 1, "limit": 1, "media_type": "audio"},
            headers=admin_headers,
        )
    assert resp.status_code == 400
    enq.assert_not_called()


def test_run_now_happy_path(app_client, admin_headers):
    """When slug + channel_id + media_type are valid, the job is enqueued."""
    with _admin_session({"knigi_audio_biz": "mysql://x"}), \
         patch("shared.db.repositories.channel_repo.get_channel_by_id", return_value={"id": 5, "name": "ch"}), \
         patch("app.api.endpoints.dle_sources.enqueue_dle_ingestion", return_value="job-abc") as enq:
        resp = app_client.post(
            "/api/v1/dle-sources/knigi_audio_biz/run-now",
            json={"channel_id": 5, "limit": 1, "media_type": "video"},
            headers=admin_headers,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["job_id"] == "job-abc"
    enq.assert_called_once()


def test_slug_to_host_consistency():
    """slug_to_host must round-trip the slug → real domain for all 7 sources."""
    from shared.ingestion.dle.pipeline import slug_to_host
    expected = {
        "knigi_audio_biz": "knigi-audio.biz",
        "audiokniga_one_com": "audiokniga-one.com",
        "club_books_ru": "club-books.ru",
        "books_online_info": "books-online.info",
        "slushat_knigi_com": "slushat-knigi.com",
        "knigi_online_club": "knigi-online.club",
        "bazaknig_net": "bazaknig.net",
    }
    for slug, host in expected.items():
        assert slug_to_host(slug) == host, f"{slug} → {slug_to_host(slug)} (expected {host})"
