"""Tests for the Yii beforeValidate parity in /api/v1/streams/ POST.

When the request body omits ``service_name`` and/or ``workdir``, the API
must auto-derive them from ``name`` (matching legacy Yii behaviour):

    service_name = f"stream-{name}.service"
    workdir      = f"{settings.STREAMS_ROOT}/{name}"
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from main import app
    from app.api.deps import get_current_admin

    # FastAPI dependency_overrides bypass so endpoints accept any caller.
    app.dependency_overrides[get_current_admin] = lambda: {"id": 1, "status": 1}
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_admin, None)


def _mock_db_for_create(insert_id: int = 99,
                         derived_service: str = "stream-test_btn.service",
                         derived_workdir: str = "/srv/streams/test_btn"):
    """Build a get_connection mock that pretends INSERT + re-SELECT worked."""
    cur = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = cur
    cm.__exit__.return_value = False

    # First call: INSERT → lastrowid
    insert_result = MagicMock()
    insert_result.lastrowid = insert_id

    # Second call: SELECT → mappings().first() returns the row.
    select_result = MagicMock()
    select_result.mappings.return_value.first.return_value = {
        "id": insert_id,
        "name": "test_btn",
        "service_name": derived_service,
        "workdir": derived_workdir,
        "stream_key": "xxxx-yyyy-zzzz-wwww",
        "duration_sec": 42900,
        "rtmp_host": "a.rtmp.youtube.com",
        "rtmp_base": "rtmp://a.rtmp.youtube.com/live2/",
        "channel_id": None,
        "streaming_account_id": 1,
        "platform_broadcast_id": None,
        "platform_stream_id": None,
        "title": None,
        "description": None,
        "tags": None,
        "thumbnail_path": None,
        "enabled": 1,
    }

    cur.execute.side_effect = [insert_result, select_result]
    return cm, cur


def test_create_minimal_auto_derives_service_and_workdir(client, monkeypatch):
    """POST {name, stream_key, streaming_account_id} → service_name/workdir derived."""
    cm, cur = _mock_db_for_create()
    captured: dict = {}

    # Capture the bound INSERT params so we can assert what got persisted.
    orig_execute = cur.execute.side_effect

    def _spy(stmt, params=None, *a, **kw):
        if params and isinstance(params, dict) and "service_name" in params:
            captured.update(params)
        return next(_iter)
    _iter = iter(orig_execute)
    cur.execute.side_effect = _spy

    with patch("app.api.endpoints.streams.get_connection", return_value=cm), \
         patch("app.api.endpoints.streams.provisioner.provision_stream",
               return_value={"ok": True, "stream_id": 99,
                             "service": "stream-test_btn.service"}):
        r = client.post(
            "/api/v1/streams/",
            json={
                "name": "test_btn",
                "stream_key": "xxxx-yyyy-zzzz-wwww",
                "streaming_account_id": 1,
            },
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["stream"]["service_name"] == "stream-test_btn.service"
    assert body["stream"]["workdir"].endswith("/test_btn")
    # Verify INSERT was given the derived values, not None.
    assert captured["service_name"] == "stream-test_btn.service"
    assert captured["workdir"].endswith("/test_btn")


def test_create_explicit_service_and_workdir_preserved(client):
    """If caller supplies service_name/workdir, the API must NOT overwrite them."""
    cm, cur = _mock_db_for_create(
        derived_service="custom-stream.service",
        derived_workdir="/custom/path",
    )
    captured: dict = {}
    orig = cur.execute.side_effect

    def _spy(stmt, params=None, *a, **kw):
        if params and isinstance(params, dict) and "service_name" in params:
            captured.update(params)
        return next(_iter)
    _iter = iter(orig)
    cur.execute.side_effect = _spy

    with patch("app.api.endpoints.streams.get_connection", return_value=cm), \
         patch("app.api.endpoints.streams.provisioner.provision_stream",
               return_value={"ok": True}):
        r = client.post(
            "/api/v1/streams/",
            json={
                "name": "test_btn",
                "service_name": "custom-stream.service",
                "workdir": "/custom/path",
                "stream_key": "k",
            },
        )
    assert r.status_code == 201, r.text
    assert captured["service_name"] == "custom-stream.service"
    assert captured["workdir"] == "/custom/path"


def test_create_rejects_invalid_name(client):
    r = client.post(
        "/api/v1/streams/",
        json={"name": "bad name with spaces!", "stream_key": "k"},
    )
    assert r.status_code == 422
    assert "name" in r.json()["detail"].lower()


def test_create_rejects_empty_stream_key(client):
    r = client.post(
        "/api/v1/streams/",
        json={"name": "ok_name", "stream_key": ""},
    )
    assert r.status_code == 422
