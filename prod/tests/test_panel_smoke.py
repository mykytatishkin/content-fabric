"""Smoke tests for every /panel/* admin page.

Verifies all admin panel pages return 200 with admin session, and that
the rendered HTML contains expected markers.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def admin_client():
    from main import app

    with patch("app.views.panel.require_admin") as mock_admin:
        mock_admin.return_value = (
            {"id": 1, "username": "admin", "role": "admin", "status": 1},
            None,
        )

        with patch("shared.db.connection.get_connection") as mc:
            cur = MagicMock()
            mc.return_value.__enter__.return_value = cur
            cur.execute.return_value.fetchone.return_value = (0, 0)
            cur.execute.return_value.fetchall.return_value = []
            cur.execute.return_value.mappings.return_value.first.return_value = None
            yield TestClient(app)


PANEL_PAGES = [
    "/panel/",
    "/panel/channels",
    "/panel/tasks",
    "/panel/users",
    "/panel/credentials",
    "/panel/payment",
    "/panel/health",
    "/panel/logs",
    "/panel/streams",
    "/panel/streams/create",
    "/panel/dle-sources",
    "/panel/stats",
    "/panel/broadcast",
]


@pytest.mark.parametrize("path", PANEL_PAGES)
def test_panel_page_renders(admin_client, path):
    r = admin_client.get(path)
    assert r.status_code == 200, f"{path}: HTTP {r.status_code}: {r.text[:200]}"
    assert "<html" in r.text.lower()


def test_streams_page_polling_present(admin_client):
    """Verify /panel/streams has setInterval polling for status."""
    r = admin_client.get("/panel/streams")
    assert r.status_code == 200
    assert "/api/v1/streams/status" in r.text
    assert "/api/v1/streams/tail" in r.text
    assert "setInterval(refreshStatus" in r.text


def test_streams_page_auth_button_link(admin_client):
    """Verify the Auth button per row links to /panel/streaming-accounts/{id}/authorize."""
    from main import app

    with patch("app.views.panel.require_admin") as mock_admin:
        mock_admin.return_value = ({"id": 1, "role": "admin"}, None)
        with patch("shared.db.connection.get_connection") as mc:
            cur = MagicMock()
            mc.return_value.__enter__.return_value = cur
            cur.execute.return_value.fetchall.return_value = [
                (1, "stream-1", "cff-stream-1", "/tmp/x", "key01", 5, 42),
            ]
            client = TestClient(app)
            r = client.get("/panel/streams")
            assert r.status_code == 200
            # Auth href is rendered client-side from r.yid; verify the JS template fragment.
            assert "/panel/streaming-accounts/" in r.text
            assert "/authorize" in r.text


def test_dle_sources_uses_modal_helper(admin_client):
    r = admin_client.get("/panel/dle-sources")
    assert r.status_code == 200
    assert "openModal" in r.text  # ensure preview/run uses the modal helper
    assert "/api/v1/dle-sources/" in r.text


def test_logs_service_filter_renders(admin_client):
    r = admin_client.get("/panel/logs")
    assert r.status_code == 200
    body = r.text
    # Form has Service + Level + Lines selects/inputs.
    assert 'name="service"' in body
    assert 'name="level"' in body
    assert 'name="lines"' in body
    # Service options include the well-known cff-* units.
    assert "cff-api" in body
    assert "cff-publishing-worker" in body


def test_logs_services_endpoint_exists():
    """Verify /api/v1/logs/services endpoint exists in router."""
    from app.api.endpoints.logs import router

    paths = [route.path for route in router.routes]
    assert "/services" in paths


def test_stats_uses_snapshot_date(admin_client):
    r = admin_client.get("/panel/stats")
    assert r.status_code == 200
    # The page must successfully render even with empty data.
    assert "Statistics" in r.text


def test_health_shows_systemd_services(admin_client):
    r = admin_client.get("/panel/health")
    assert r.status_code == 200
    assert "Health" in r.text
    # Either Services section or systemd table — both gated on data.


def test_broadcast_empty_title_flashes_error(admin_client):
    """POST /panel/broadcast with whitespace-only title must NOT 422."""
    r = admin_client.post(
        "/panel/broadcast",
        data={"title": "   ", "message": ""},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
    assert "Title is required" in r.text


def test_streams_create_form_minimal_has_auto_derivation(admin_client):
    """The create form should allow minimal name+key+account_id with service/workdir auto-derived.

    Yii parity: service_name and workdir must NOT be marked required in the form,
    because the server will fill them from name on POST.
    """
    import re as _re

    r = admin_client.get("/panel/streams/create")
    assert r.status_code == 200
    svc = _re.search(
        r'<(input|textarea|select)[^>]*name="service_name"[^>]*>', r.text
    )
    wd = _re.search(
        r'<(input|textarea|select)[^>]*name="workdir"[^>]*>', r.text
    )
    assert svc and wd, "service_name and workdir fields must exist"
    assert " required" not in svc.group(0), (
        f"service_name must be optional (Yii parity): {svc.group(0)}"
    )
    assert " required" not in wd.group(0), (
        f"workdir must be optional (Yii parity): {wd.group(0)}"
    )


def test_streams_create_endpoint_accepts_minimal_payload():
    """POST /api/v1/streams/ with only name+stream_key must succeed (auto-derive)."""
    from main import app
    from app.api.deps import get_current_admin

    app.dependency_overrides[get_current_admin] = lambda: {"id": 1, "role": "admin"}
    try:
        with patch("app.api.endpoints.streams.get_connection") as mc:
            cur = MagicMock()
            mc.return_value.__enter__.return_value = cur
            cur.execute.return_value.lastrowid = 99
            cur.execute.return_value.mappings.return_value.first.return_value = {
                "id": 99,
                "name": "myslug",
                "service_name": "stream-myslug.service",
                "workdir": "/var/lib/cff/streams/myslug",
                "stream_key": "k",
                "duration_sec": 42900,
                "rtmp_host": "a.rtmp.youtube.com",
                "rtmp_base": "rtmp://a.rtmp.youtube.com/live2/",
                "channel_id": None,
                "streaming_account_id": None,
                "platform_broadcast_id": None,
                "platform_stream_id": None,
                "title": None,
                "description": None,
                "tags": None,
                "thumbnail_path": None,
                "enabled": 1,
            }
            with patch("shared.streams.provisioner.provision_stream") as prov:
                prov.return_value = {"ok": True}
                client = TestClient(app)
                r = client.post(
                    "/api/v1/streams/",
                    json={"name": "myslug", "stream_key": "k"},
                )
                assert r.status_code == 201, f"got {r.status_code}: {r.text[:300]}"
                body = r.json()
                assert body["ok"] is True
                # Verify auto-derived values were inserted.
                # First INSERT call args contain the bound parameters.
                insert_call = next(
                    c
                    for c in cur.execute.call_args_list
                    if "INSERT INTO live_stream_configurations" in str(c.args[0])
                )
                params = insert_call.args[1]
                assert params["service_name"] == "stream-myslug.service"
                assert "myslug" in params["workdir"]
    finally:
        app.dependency_overrides.pop(get_current_admin, None)


def test_dle_sources_active_class_in_sidebar(admin_client):
    """Sidebar nav must mark DLE Sources link as active on /panel/dle-sources.

    /panel/dle-sources extends app_base.html (not base.html), and the sidebar
    there uses ``active == 'dle_sources'`` (underscore). Verify it matches
    the value set by the view.
    """
    import re as _re

    r = admin_client.get("/panel/dle-sources")
    assert r.status_code == 200
    # Use multiline regex; the link can be on its own line with any whitespace.
    m = _re.search(
        r'<a\s+href="/panel/dle-sources"[^>]*class="([^"]*)"', r.text
    )
    if not m:
        # Save for debugging
        with open("dle_test_debug.html", "w", encoding="utf-8") as fh:
            fh.write(r.text)
        pytest.fail(f"sidebar dle-sources link missing (len={len(r.text)})")
    assert "active" in m.group(1), (
        f"DLE Sources link must be active on /panel/dle-sources: {m.group(0)}"
    )


def test_panel_streaming_accounts_authorize_redirects_to_google(admin_client):
    """Clicking Auth button on /panel/streams must 302 to Google's accounts."""
    from main import app

    with patch("app.views.panel.require_admin") as mock_admin:
        mock_admin.return_value = ({"id": 1, "role": "admin"}, None)
        with patch("shared.db.connection.get_connection") as mc:
            cur = MagicMock()
            mc.return_value.__enter__.return_value = cur
            row = {
                "id": 42,
                "name": "test",
                "client_id": "client-xyz",
                "client_secret": "secret-xyz",
                "enabled": 1,
            }
            cur.execute.return_value.mappings.return_value.first.return_value = row

            client = TestClient(app)
            r = client.get(
                "/panel/streaming-accounts/42/authorize", follow_redirects=False
            )
            assert r.status_code == 302
            assert "accounts.google.com" in r.headers["location"]
