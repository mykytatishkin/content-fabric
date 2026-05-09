"""Tests for the Sora pipeline (worker + scheduler tick + repo).

External calls (scraper.fetch_sora_feed, scraper.download_sora_video,
enqueue_shorts, sora_repo.*, telegram) are all mocked. No real HTTP.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.queue.types import SoraPayload

# Import the module so patches below can resolve attributes by dotted path
# (avoids "module 'workers' has no attribute 'sora_worker'" errors).
from workers import sora_worker  # noqa: F401


# ── Helpers ─────────────────────────────────────────────────────────


def _feed_item(post_id: str, video_url: str = "https://sora/v.mp4", views: int = 5000):
    return {
        "post": {
            "id": post_id,
            "attachments": [{"url": video_url}],
            "unique_view_count": views,
        }
    }


def _patch_worker():
    """Common patches for the worker. Returns a stack-aware ExitStack-like dict."""
    return {
        "fetch": patch("workers.sora_worker.scraper.fetch_sora_feed"),
        "download": patch("workers.sora_worker.scraper.download_sora_video", return_value=True),
        "used": patch("workers.sora_worker.sora_repo.get_used_post_ids", return_value=set()),
        "mark": patch("workers.sora_worker.sora_repo.mark_post_used"),
        "enqueue": patch("workers.sora_worker.enqueue_shorts", return_value="job-1"),
        "mkdir": patch("workers.sora_worker.os.makedirs"),
        "telegram": patch("workers.sora_worker.telegram.send"),
        "bootstrap": patch("workers.sora_worker.bootstrap_job", return_value="trace-x"),
    }


# ── Worker ──────────────────────────────────────────────────────────


def test_run_sora_job_empty_feed_no_enqueues():
    p = _patch_worker()
    with p["fetch"] as fetch, p["download"], p["used"], p["mark"] as mark, \
         p["enqueue"] as enq, p["mkdir"], p["telegram"], p["bootstrap"]:
        fetch.return_value = []

        from workers.sora_worker import run_sora_job
        result = run_sora_job(SoraPayload(channel_id=19, limit=3))

        assert result == {"ok": True, "fetched": 0, "new": 0, "queued": 0}
        enq.assert_not_called()
        mark.assert_not_called()


def test_run_sora_job_all_new_posts_enqueues_each_and_marks_used():
    p = _patch_worker()
    with p["fetch"] as fetch, p["download"] as dl, p["used"] as used, \
         p["mark"] as mark, p["enqueue"] as enq, p["mkdir"], p["telegram"], \
         p["bootstrap"]:
        fetch.return_value = [
            _feed_item("p1"), _feed_item("p2"), _feed_item("p3"),
        ]
        used.return_value = set()

        from workers.sora_worker import run_sora_job
        result = run_sora_job(SoraPayload(channel_id=19, limit=3))

        assert result["ok"] is True
        assert result["fetched"] == 3
        assert result["new"] == 3
        assert result["queued"] == 3
        assert enq.call_count == 3
        assert mark.call_count == 3
        # Verify channel_id propagated
        for call in enq.call_args_list:
            payload = call.args[0]
            assert payload.channel_id == 19
            assert payload.metadata.get("source") == "sora"
        # Each download was attempted
        assert dl.call_count == 3


def test_run_sora_job_skips_already_used_posts():
    p = _patch_worker()
    with p["fetch"] as fetch, p["download"] as dl, p["used"] as used, \
         p["mark"] as mark, p["enqueue"] as enq, p["mkdir"], p["telegram"], \
         p["bootstrap"]:
        fetch.return_value = [
            _feed_item("p1"),
            _feed_item("p2"),
            _feed_item("p3"),
        ]
        used.return_value = {"p1", "p3"}  # only p2 is new

        from workers.sora_worker import run_sora_job
        result = run_sora_job(SoraPayload(channel_id=19, limit=5))

        assert result["fetched"] == 3
        assert result["new"] == 1
        assert result["queued"] == 1
        assert enq.call_count == 1
        # The single mark must be for p2
        mark.assert_called_once_with("p2", channel_id=19)
        # Only one download triggered (for p2)
        assert dl.call_count == 1


def test_run_sora_job_respects_limit_and_min_views():
    p = _patch_worker()
    with p["fetch"] as fetch, p["download"], p["used"], p["mark"], \
         p["enqueue"] as enq, p["mkdir"], p["telegram"], p["bootstrap"]:
        fetch.return_value = [
            _feed_item("low", views=10),     # below min_views=1000 → skip
            _feed_item("p1", views=2000),
            _feed_item("p2", views=2000),
            _feed_item("p3", views=2000),    # over limit=2 → skip
        ]

        from workers.sora_worker import run_sora_job
        result = run_sora_job(SoraPayload(channel_id=19, limit=2, min_views=1000))

        assert result["queued"] == 2
        assert enq.call_count == 2


def test_run_sora_job_fetch_error_returns_ok_false():
    """If scraper.fetch_sora_feed raises, worker must return ok=False with error."""
    p = _patch_worker()
    with p["fetch"] as fetch, p["download"], p["used"], p["mark"] as mark, \
         p["enqueue"] as enq, p["mkdir"], p["telegram"] as tg, p["bootstrap"]:
        fetch.side_effect = RuntimeError("zenrows boom")

        from workers.sora_worker import run_sora_job
        result = run_sora_job(SoraPayload(channel_id=19, limit=3))

        assert result["ok"] is False
        assert "zenrows boom" in result["error"]
        assert result["fetched"] == 0
        assert result["new"] == 0
        assert result["queued"] == 0
        enq.assert_not_called()
        mark.assert_not_called()
        tg.assert_called_once()


def test_run_sora_job_download_failure_skips_enqueue():
    p = _patch_worker()
    with p["fetch"] as fetch, p["download"] as dl, p["used"], p["mark"] as mark, \
         p["enqueue"] as enq, p["mkdir"], p["telegram"], p["bootstrap"]:
        fetch.return_value = [_feed_item("p1")]
        dl.return_value = False  # download failed

        from workers.sora_worker import run_sora_job
        result = run_sora_job(SoraPayload(channel_id=19, limit=3))

        assert result["new"] == 1
        assert result["queued"] == 0
        enq.assert_not_called()
        mark.assert_not_called()


# ── Scheduler tick ──────────────────────────────────────────────────


def test_enqueue_sora_daily_calls_enqueue_sora_with_right_payload():
    with patch("scheduler.jobs.enqueue_sora") as mock_enq:
        from scheduler.jobs import enqueue_sora_daily, SORA_DAILY_CHANNELS

        n = enqueue_sora_daily()

        assert n == len(SORA_DAILY_CHANNELS)
        assert mock_enq.call_count == len(SORA_DAILY_CHANNELS)
        # The first configured channel should be 19 (per spec default)
        first_call_payload = mock_enq.call_args_list[0].args[0]
        assert isinstance(first_call_payload, SoraPayload)
        assert first_call_payload.channel_id == SORA_DAILY_CHANNELS[0][0]
        assert first_call_payload.limit == SORA_DAILY_CHANNELS[0][1]
        assert first_call_payload.media_type == SORA_DAILY_CHANNELS[0][2]


def test_sora_daily_is_in_yii_cron():
    """Scheduler tick must include sora_daily, otherwise it'll never fire."""
    from scheduler.jobs import _YII_CRON
    names = [row[0] for row in _YII_CRON]
    assert "sora_daily" in names


# ── DB repo idempotency ─────────────────────────────────────────────


def test_mark_post_used_uses_insert_ignore():
    """Idempotency: repeated calls must not raise (INSERT IGNORE in SQL)."""
    captured_sql: list[str] = []

    fake_conn = MagicMock()

    def _exec(stmt, params=None):
        # SQLAlchemy text() objects stringify to the SQL literal
        captured_sql.append(str(stmt))
        return MagicMock()
    fake_conn.execute.side_effect = _exec

    from contextlib import contextmanager

    @contextmanager
    def _fake_get_conn():
        yield fake_conn

    with patch("shared.db.repositories.sora_repo.get_connection", _fake_get_conn):
        from shared.db.repositories import sora_repo
        sora_repo.mark_post_used("p1", channel_id=19)
        sora_repo.mark_post_used("p1", channel_id=19)  # second call must not raise

    assert any("INSERT IGNORE" in sql.upper() or "INSERT  IGNORE" in sql.upper()
               for sql in captured_sql), captured_sql
    assert fake_conn.execute.call_count == 2
