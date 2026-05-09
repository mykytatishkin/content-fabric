"""Unit tests for shared.streams.lifecycle — broadcast lifecycle orchestration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.streams import lifecycle


@pytest.fixture
def stream():
    return {
        "id": 7,
        "name": "knigi-online",
        "service_name": "stream-knigi-online.service",
        "stream_key": "abcd-efgh-ijkl",
        "streaming_account_id": 42,
        "platform_broadcast_id": "",
        "title": "Live Stream",
    }


class TestPrepareBroadcast:
    def test_returns_noop_when_no_streaming_account(self):
        result = lifecycle.prepare_broadcast({"id": 1, "service_name": "x"})
        assert result == {"ok": True, "broadcast_id": None, "stream_id": None, "error": None}

    def test_calls_prepare_broadcast_for_start_with_built_service(self, stream):
        with patch("shared.youtube.streaming_accounts.build_service_for_streaming_account") as mock_build, \
             patch("shared.youtube.broadcasts.prepare_broadcast_for_start") as mock_prep:
            mock_build.return_value = (MagicMock(), MagicMock())
            mock_prep.return_value = {"broadcast_id": "BCAST_ID", "stream_id": "STREAM_ID"}
            result = lifecycle.prepare_broadcast(stream)
        assert result["ok"] is True
        assert result["broadcast_id"] == "BCAST_ID"
        assert result["stream_id"] == "STREAM_ID"
        mock_build.assert_called_once_with(42)

    def test_swallows_exceptions(self, stream):
        with patch("shared.youtube.streaming_accounts.build_service_for_streaming_account",
                   side_effect=RuntimeError("boom")):
            result = lifecycle.prepare_broadcast(stream)
        assert result["ok"] is False
        assert "boom" in result["error"]


class TestGoLive:
    def test_calls_transition_with_live(self, stream):
        with patch("shared.youtube.streaming_accounts.build_service_for_streaming_account") as mock_build, \
             patch("shared.youtube.broadcasts.transition_broadcast") as mock_trans:
            mock_build.return_value = (MagicMock(), MagicMock())
            res = lifecycle.go_live(stream, "BCAST_ID")
        assert res == {"ok": True, "error": None}
        mock_trans.assert_called_once()
        # 3rd positional arg to transition_broadcast is the target status
        args, _ = mock_trans.call_args
        assert args[1] == "BCAST_ID"
        assert args[2] == "live"


class TestCompleteBroadcast:
    def test_skips_when_no_broadcast_id(self):
        s = {"id": 1, "streaming_account_id": 1, "platform_broadcast_id": ""}
        assert lifecycle.complete_broadcast(s)["ok"] is True
        assert lifecycle.complete_broadcast(s)["broadcast_id"] is None

    def test_calls_transition_complete(self, stream):
        stream["platform_broadcast_id"] = "OLD_BCAST"
        with patch("shared.youtube.streaming_accounts.build_service_for_streaming_account") as mock_build, \
             patch("shared.youtube.broadcasts.transition_broadcast") as mock_trans:
            mock_build.return_value = (MagicMock(), MagicMock())
            res = lifecycle.complete_broadcast(stream)
        assert res["ok"] is True
        assert res["broadcast_id"] == "OLD_BCAST"
        args, _ = mock_trans.call_args
        assert args[1] == "OLD_BCAST"
        assert args[2] == "complete"


class TestReconcile:
    def test_noop_when_already_running_with_broadcast(self, stream):
        stream["platform_broadcast_id"] = "BCAST"
        with patch("shared.streams.systemd_manager.status",
                   return_value={"active_state": "active", "sub_state": "running"}):
            res = lifecycle.reconcile(stream)
        assert res["action"] == "noop"
        assert res["ok"] is True

    def test_starts_when_unit_failed(self, stream):
        with patch("shared.streams.systemd_manager.status",
                   return_value={"active_state": "failed", "sub_state": "auto-restart"}), \
             patch("shared.streams.systemd_manager.reset_failed", return_value=(0, "")), \
             patch("shared.streams.systemd_manager.stop", return_value=(0, "")), \
             patch.object(lifecycle, "start_stream",
                          return_value={"ok": True, "code": 0, "output": "started",
                                        "youtube_broadcast_id": "B1",
                                        "youtube_prep_error": None,
                                        "youtube_live_error": None}):
            res = lifecycle.reconcile(stream)
        assert res["action"] == "started"
        assert res["broadcast_id"] == "B1"
        assert res["ok"] is True

    def test_starts_when_inactive(self, stream):
        with patch("shared.streams.systemd_manager.status",
                   return_value={"active_state": "inactive", "sub_state": "dead"}), \
             patch("shared.streams.systemd_manager.reset_failed", return_value=(0, "")), \
             patch("shared.streams.systemd_manager.stop", return_value=(0, "")), \
             patch.object(lifecycle, "start_stream",
                          return_value={"ok": True, "code": 0, "output": "",
                                        "youtube_broadcast_id": None,
                                        "youtube_prep_error": None,
                                        "youtube_live_error": None}):
            res = lifecycle.reconcile(stream)
        assert res["action"] == "started"
