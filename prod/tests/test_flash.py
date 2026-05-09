"""Tests for the Yii-style flash message helpers + SessionMiddleware wiring.

Covers:
  1. SessionMiddleware is registered in main.py.
  2. flash() appends to request.session under "_flashes".
  3. get_flashes() returns and clears the queue.
  4. Multiple flashes preserved in order, with categories preserved.
  5. End-to-end: an endpoint calls flash() + redirects, and the next page
     served by the test client renders the flash via the Jinja global.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware


# ────────────────────────────────────────────────────────────────────
# Unit tests — flash() / get_flashes()
# ────────────────────────────────────────────────────────────────────


def _make_session_request(initial_session: dict | None = None) -> Request:
    """Hand-roll a Request with a session attribute (no middleware needed)."""
    req = MagicMock(spec=Request)
    req.session = {} if initial_session is None else initial_session
    return req


def test_flash_appends_to_session():
    from app.core.flash import flash

    req = _make_session_request()
    flash(req, "success", "Saved!")
    assert req.session["_flashes"] == [["success", "Saved!"]]


def test_get_flashes_returns_and_clears():
    from app.core.flash import flash, get_flashes

    req = _make_session_request()
    flash(req, "error", "Oops")
    out = get_flashes(req)
    assert out == [("error", "Oops")]
    # Second call → empty (cleared)
    assert get_flashes(req) == []
    assert "_flashes" not in req.session


def test_multiple_flashes_preserved_in_order():
    from app.core.flash import flash, get_flashes

    req = _make_session_request()
    flash(req, "info", "first")
    flash(req, "success", "second")
    flash(req, "error", "third")
    out = get_flashes(req)
    assert out == [
        ("info", "first"),
        ("success", "second"),
        ("error", "third"),
    ]


def test_categories_preserved_distinctly():
    from app.core.flash import flash, get_flashes

    req = _make_session_request()
    for cat in ("success", "error", "info", "warning", "danger"):
        flash(req, cat, f"msg-{cat}")
    out = get_flashes(req)
    assert [c for c, _ in out] == ["success", "error", "info", "warning", "danger"]
    assert all(m == f"msg-{c}" for c, m in out)


def test_flash_noop_when_session_missing():
    """When SessionMiddleware isn't installed, flash() must not raise."""
    from app.core.flash import flash, get_flashes

    req = MagicMock(spec=Request)
    type(req).session = property(
        lambda self: (_ for _ in ()).throw(AssertionError("no SessionMiddleware"))
    )
    # Must not raise
    flash(req, "info", "ignored")
    assert get_flashes(req) == []


# ────────────────────────────────────────────────────────────────────
# Integration — main.py wires SessionMiddleware
# ────────────────────────────────────────────────────────────────────


def test_session_middleware_registered_in_main():
    """main.py must register SessionMiddleware (otherwise flash silently no-ops)."""
    from main import app as fastapi_app

    middleware_classes = [m.cls for m in fastapi_app.user_middleware]
    assert SessionMiddleware in middleware_classes, (
        f"SessionMiddleware not registered. Found: {middleware_classes}"
    )


def test_main_jinja_globals_have_get_flashes():
    """The Jinja global must be wired so templates can call get_flashes(request)."""
    from main import app as fastapi_app  # noqa: F401  (side-effect: registers globals)
    from app.views.app_portal import templates as portal_templates
    from app.views.panel import templates as panel_templates

    assert "get_flashes" in portal_templates.env.globals
    assert "get_flashes" in panel_templates.env.globals
    assert callable(portal_templates.env.globals["get_flashes"])


# ────────────────────────────────────────────────────────────────────
# End-to-end — flash() in a handler is rendered on the next request
# ────────────────────────────────────────────────────────────────────


@pytest.fixture()
def flash_e2e_client(tmp_path):
    """Standalone FastAPI app exercising the full flash → redirect → render path.

    Uses the real flash module + SessionMiddleware + a tiny inline template
    so we don't need to mock the full main.py app.
    """
    from app.core.flash import flash as do_flash, get_flashes

    tpl_dir = tmp_path / "tpl"
    tpl_dir.mkdir()
    (tpl_dir / "page.html").write_text(
        "<!doctype html><html><body>"
        "{% for cat, msg in get_flashes(request) %}"
        "<div class=\"alert alert-{{ cat }}\">{{ msg }}</div>"
        "{% endfor %}"
        "<p>page</p></body></html>",
        encoding="utf-8",
    )

    templates = Jinja2Templates(directory=str(tpl_dir))
    templates.env.globals["get_flashes"] = get_flashes

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="e2e-test-secret", same_site="lax")

    @app.post("/do")
    def do(request: Request):
        do_flash(request, "success", "It worked!")
        return RedirectResponse("/page", status_code=303)

    @app.get("/page", response_class=HTMLResponse)
    def page(request: Request):
        return templates.TemplateResponse("page.html", {"request": request})

    return TestClient(app)


def test_flash_set_then_rendered_after_redirect(flash_e2e_client):
    # POST sets the flash and redirects.
    r = flash_e2e_client.post("/do", follow_redirects=False)
    assert r.status_code == 303
    assert urlparse(r.headers["location"]).path == "/page"

    # GET on the redirect target renders the flash.
    r2 = flash_e2e_client.get("/page")
    assert r2.status_code == 200
    assert 'class="alert alert-success"' in r2.text
    assert "It worked!" in r2.text

    # And the flash is consumed: a second GET should NOT re-render it.
    r3 = flash_e2e_client.get("/page")
    assert r3.status_code == 200
    assert "It worked!" not in r3.text


def test_flash_e2e_multiple_categories_in_order(flash_e2e_client):
    """Multiple flashes set across requests render in insertion order, then clear."""
    from app.core.flash import flash as do_flash

    # Manually drive several flashes then a single GET.
    # We piggyback on the same client/session; add an extra route inline by
    # patching the existing app to push three flashes in one POST.
    app = flash_e2e_client.app

    @app.post("/multi")
    def multi(request: Request):
        do_flash(request, "info", "one")
        do_flash(request, "warning", "two")
        do_flash(request, "error", "three")
        return RedirectResponse("/page", status_code=303)

    flash_e2e_client.post("/multi", follow_redirects=False)
    r = flash_e2e_client.get("/page")
    assert r.status_code == 200
    # All three rendered, in order.
    idx_one = r.text.find("one")
    idx_two = r.text.find("two")
    idx_three = r.text.find("three")
    assert 0 < idx_one < idx_two < idx_three
    assert "alert-info" in r.text
    assert "alert-warning" in r.text
    assert "alert-error" in r.text
