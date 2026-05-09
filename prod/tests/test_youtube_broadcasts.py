"""Tests for shared.youtube.broadcasts — pure mocks, no real YouTube API."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_service(
    *,
    list_broadcasts_response=None,
    insert_broadcasts_response=None,
    list_streams_responses=None,
    list_streams_raise=None,
    bind_raise=None,
    transition_raise=None,
):
    """Build a chained MagicMock that mimics the googleapiclient Resource.

    Each .execute() returns the next item from the supplied list, or the
    given dict.  Configure raises by side_effect on .execute.
    """
    service = MagicMock(name="youtube_service")

    # liveBroadcasts().list().execute()
    lb_list = MagicMock()
    lb_list.execute.return_value = list_broadcasts_response or {"items": []}
    service.liveBroadcasts.return_value.list.return_value = lb_list

    # liveBroadcasts().insert().execute()
    lb_insert = MagicMock()
    lb_insert.execute.return_value = insert_broadcasts_response or {"id": "BNEW"}
    service.liveBroadcasts.return_value.insert.return_value = lb_insert

    # liveBroadcasts().update().execute()
    lb_update = MagicMock()
    lb_update.execute.return_value = {}
    service.liveBroadcasts.return_value.update.return_value = lb_update

    # liveBroadcasts().bind().execute()
    lb_bind = MagicMock()
    if bind_raise:
        lb_bind.execute.side_effect = bind_raise
    else:
        lb_bind.execute.return_value = {}
    service.liveBroadcasts.return_value.bind.return_value = lb_bind

    # liveBroadcasts().transition().execute()
    lb_trans = MagicMock()
    if transition_raise:
        lb_trans.execute.side_effect = transition_raise
    else:
        lb_trans.execute.return_value = {}
    service.liveBroadcasts.return_value.transition.return_value = lb_trans

    # liveStreams().list().execute() — paginated
    ls_list = MagicMock()
    if list_streams_raise:
        ls_list.execute.side_effect = list_streams_raise
    else:
        responses = list_streams_responses or [{"items": []}]
        ls_list.execute.side_effect = list(responses)
    service.liveStreams.return_value.list.return_value = ls_list

    # videos().update().execute()
    v_update = MagicMock()
    v_update.execute.return_value = {}
    service.videos.return_value.update.return_value = v_update

    return service


# ---------------------------------------------------------------------------
# parse_tags
# ---------------------------------------------------------------------------


def test_parse_tags_handles_mixed_separators_and_dedupes():
    from shared.youtube.broadcasts import parse_tags
    assert parse_tags("a, b; c\nd") == ["a", "b", "c", "d"]
    assert parse_tags(" foo,, bar ;  bar\nfoo ") == ["foo", "bar"]
    assert parse_tags("") == []
    assert parse_tags(None) == []
    assert parse_tags("only") == ["only"]


# ---------------------------------------------------------------------------
# find_live_stream_id_by_stream_key — paginated
# ---------------------------------------------------------------------------


def test_find_live_stream_id_paginates_until_match():
    from shared.youtube.broadcasts import find_live_stream_id_by_stream_key

    page1 = {
        "items": [
            {"id": "S1", "cdn": {"ingestionInfo": {"streamName": "key-a"}}},
            {"id": "S2", "cdn": {"ingestionInfo": {"streamName": "key-b"}}},
        ],
        "nextPageToken": "p2",
    }
    page2 = {
        "items": [
            {"id": "S3", "cdn": {"ingestionInfo": {"streamName": "want-this"}}},
        ],
    }
    service = _make_service(list_streams_responses=[page1, page2])
    result = find_live_stream_id_by_stream_key(service, "want-this")
    assert result == "S3"

    # Empty key short-circuits with no API call.
    service2 = _make_service(list_streams_responses=[{"items": []}])
    assert find_live_stream_id_by_stream_key(service2, "") is None
    service2.liveStreams.return_value.list.assert_not_called()


# ---------------------------------------------------------------------------
# transition_broadcast
# ---------------------------------------------------------------------------


def test_transition_broadcast_uses_correct_kwargs():
    from shared.youtube.broadcasts import transition_broadcast

    service = _make_service()
    transition_broadcast(service, "BID123", "live")

    service.liveBroadcasts.return_value.transition.assert_called_once_with(
        broadcastStatus="live",
        id="BID123",
        part="id,status",
    )


def test_transition_broadcast_rejects_invalid_status():
    from shared.youtube.broadcasts import transition_broadcast
    service = _make_service()
    with pytest.raises(ValueError):
        transition_broadcast(service, "BID", "bogus")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# update_broadcast_meta + bind_broadcast_to_stream — proper kwargs
# ---------------------------------------------------------------------------


def test_update_broadcast_meta_sends_snippet_with_scheduled_time():
    from shared.youtube.broadcasts import update_broadcast_meta

    # First .list() call (inside update_broadcast_meta) supplies an existing
    # scheduledStartTime, so it should be reused in the body.
    service = _make_service(
        list_broadcasts_response={
            "items": [{
                "id": "B1",
                "snippet": {"scheduledStartTime": "2030-01-01T00:00:00Z"},
                "status": {"lifeCycleStatus": "ready"},
            }],
        },
    )
    update_broadcast_meta(service, "B1", "Title", "Desc")

    update = service.liveBroadcasts.return_value.update
    update.assert_called_once()
    kwargs = update.call_args.kwargs
    assert kwargs["part"] == "snippet"
    body = kwargs["body"]
    assert body["id"] == "B1"
    assert body["snippet"]["title"] == "Title"
    assert body["snippet"]["description"] == "Desc"
    assert body["snippet"]["scheduledStartTime"] == "2030-01-01T00:00:00Z"


def test_bind_broadcast_to_stream_sends_correct_kwargs():
    from shared.youtube.broadcasts import bind_broadcast_to_stream

    service = _make_service()
    bind_broadcast_to_stream(service, "B1", "S1")
    service.liveBroadcasts.return_value.bind.assert_called_once_with(
        id="B1", streamId="S1", part="id,contentDetails",
    )


# ---------------------------------------------------------------------------
# ensure_broadcast_for_stream — both branches
# ---------------------------------------------------------------------------


def test_ensure_broadcast_reuses_existing_when_in_reusable_state():
    from shared.youtube.broadcasts import ensure_broadcast_for_stream

    service = _make_service(
        list_broadcasts_response={
            "items": [{
                "id": "B-EXIST",
                "snippet": {"scheduledStartTime": "2030-01-01T00:00:00Z"},
                "status": {"lifeCycleStatus": "ready"},
            }],
        },
    )
    stream = {
        "platform_broadcast_id": "B-EXIST",
        "name": "Stream",
        "title": "T",
        "description": "D",
    }
    bid = ensure_broadcast_for_stream(service, stream, fallback_title="T")
    assert bid == "B-EXIST"
    # Should NOT have inserted.
    service.liveBroadcasts.return_value.insert.assert_not_called()


def test_ensure_broadcast_creates_new_when_no_existing_id():
    from shared.youtube.broadcasts import ensure_broadcast_for_stream

    service = _make_service(insert_broadcasts_response={"id": "BNEW123"})
    stream = {
        "platform_broadcast_id": None,
        "name": "Stream X",
        "title": "Live X",
        "description": "Hello",
    }
    bid = ensure_broadcast_for_stream(service, stream, fallback_title="Live X")
    assert bid == "BNEW123"
    insert = service.liveBroadcasts.return_value.insert
    insert.assert_called_once()
    body = insert.call_args.kwargs["body"]
    assert body["snippet"]["title"] == "Live X"
    assert body["snippet"]["description"] == "Hello"
    assert body["status"]["privacyStatus"] == "public"


def test_ensure_broadcast_creates_new_when_existing_in_complete_state():
    """If existing broadcast is already 'complete' we must not reuse it."""
    from shared.youtube.broadcasts import ensure_broadcast_for_stream

    service = _make_service(
        list_broadcasts_response={
            "items": [{
                "id": "B-OLD",
                "snippet": {"scheduledStartTime": "2020-01-01T00:00:00Z"},
                "status": {"lifeCycleStatus": "complete"},
            }],
        },
        insert_broadcasts_response={"id": "B-NEW"},
    )
    stream = {
        "platform_broadcast_id": "B-OLD",
        "name": "S",
        "title": "T",
        "description": "",
    }
    bid = ensure_broadcast_for_stream(service, stream, fallback_title="T")
    assert bid == "B-NEW"
    service.liveBroadcasts.return_value.insert.assert_called_once()


# ---------------------------------------------------------------------------
# prepare_broadcast_for_start — both branches
# ---------------------------------------------------------------------------


def test_prepare_broadcast_for_start_reuses_existing_and_binds(monkeypatch):
    from shared.youtube import broadcasts as bm

    service = _make_service(
        list_broadcasts_response={
            "items": [{
                "id": "B-EXIST",
                "snippet": {"scheduledStartTime": "2030-01-01T00:00:00Z"},
                "status": {"lifeCycleStatus": "live"},
            }],
        },
        list_streams_responses=[{
            "items": [{
                "id": "S77", "cdn": {"ingestionInfo": {"streamName": "key-x"}},
            }],
        }],
    )
    stream = {
        "platform_broadcast_id": "B-EXIST",
        "stream_key": "key-x",
        "name": "Stream",
        "title": "T",
        "description": "D",
        "tags": "a,b",
        "thumbnail_path": None,
    }
    out = bm.prepare_broadcast_for_start(service, stream)
    assert out == {"broadcast_id": "B-EXIST", "stream_id": "S77"}
    service.liveBroadcasts.return_value.bind.assert_called_once_with(
        id="B-EXIST", streamId="S77", part="id,contentDetails",
    )


def test_prepare_broadcast_for_start_creates_when_no_existing(monkeypatch):
    from shared.youtube import broadcasts as bm

    service = _make_service(
        insert_broadcasts_response={"id": "B-FRESH"},
        list_streams_responses=[{"items": []}],
    )
    stream = {
        "platform_broadcast_id": None,
        "stream_key": "",  # no key → no bind attempt
        "name": "Stream Y",
        "title": "Y",
        "description": "",
        "tags": None,
        "thumbnail_path": None,
    }
    out = bm.prepare_broadcast_for_start(service, stream)
    assert out["broadcast_id"] == "B-FRESH"
    assert out["stream_id"] is None
    service.liveBroadcasts.return_value.insert.assert_called_once()
    # No bind because no stream_key.
    service.liveBroadcasts.return_value.bind.assert_not_called()


# ---------------------------------------------------------------------------
# error path: HttpError gets re-raised as RuntimeError with clear message
# ---------------------------------------------------------------------------


def test_transition_broadcast_reraises_httperror():
    from shared.youtube import broadcasts as bm

    # Inject a fake HttpError class into the module so the except-clause matches.
    class FakeHttpError(Exception):
        pass

    monkey = pytest.MonkeyPatch()
    monkey.setattr(bm, "HttpError", FakeHttpError)
    try:
        service = _make_service(
            transition_raise=FakeHttpError("403 Forbidden")
        )
        with pytest.raises(RuntimeError, match="transitionBroadcast"):
            bm.transition_broadcast(service, "B1", "live")
    finally:
        monkey.undo()


def test_find_live_stream_id_reraises_httperror():
    from shared.youtube import broadcasts as bm

    class FakeHttpError(Exception):
        pass

    monkey = pytest.MonkeyPatch()
    monkey.setattr(bm, "HttpError", FakeHttpError)
    try:
        service = _make_service(list_streams_raise=FakeHttpError("500"))
        with pytest.raises(RuntimeError, match="findLiveStreamIdByStreamKey"):
            bm.find_live_stream_id_by_stream_key(service, "any-key")
    finally:
        monkey.undo()
