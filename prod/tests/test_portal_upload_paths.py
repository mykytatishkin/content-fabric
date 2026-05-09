"""Regression tests for /app/upload/* and /app/tasks/new path handling.

Covers fixes for:
- /app/upload/video and /app/upload/thumbnail must return ABSOLUTE
  server paths (not basenames); JS in app_task_new.html assigns the
  returned `path` straight into the `source_file_path` form field,
  and workers (shared/youtube/upload.py) call os.path.getsize on it.
- /app/tasks/new must accept paths under UPLOAD_DIR while still
  rejecting traversal and arbitrary absolute paths.
"""

import io
import os
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import TEST_USER, ADMIN_USER


@pytest.fixture()
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def portal_cookie():
    """Cookie that authenticates as TEST_USER on portal routes."""
    from app.core.security import create_access_token
    from app.core.auth import COOKIE_NAME
    token = create_access_token({"sub": TEST_USER["id"]})
    return {COOKIE_NAME: token}


def _csrf_headers():
    # The portal enforces a CSRF check on state-changing requests by
    # requiring the Origin or Referer header to match the request host.
    return {"Origin": "http://testserver", "Referer": "http://testserver/app/"}


class TestPortalUploadReturnsAbsolutePath:
    def test_video_upload_returns_absolute_path(self, app_client, portal_cookie, upload_dir):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER):
            resp = app_client.post(
                "/app/upload/video",
                cookies=portal_cookie,
                headers=_csrf_headers(),
                files={"file": ("test.mp4", io.BytesIO(b"fake-mp4-data" * 100), "video/mp4")},
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Bug regression: previously returned just dest.name (basename),
        # which broke worker access. Must be absolute.
        assert os.path.isabs(data["path"]), f"path must be absolute: {data['path']}"
        assert os.path.exists(data["path"])
        assert data["path"].startswith(str(upload_dir))
        assert data["filename"] == "test.mp4"
        assert data["size"] > 0

    def test_thumbnail_upload_returns_absolute_path(self, app_client, portal_cookie, upload_dir):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER):
            resp = app_client.post(
                "/app/upload/thumbnail",
                cookies=portal_cookie,
                headers=_csrf_headers(),
                files={"file": ("thumb.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 200), "image/jpeg")},
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert os.path.isabs(data["path"])
        assert os.path.exists(data["path"])
        assert data["path"].startswith(str(upload_dir))


class TestTaskNewPathValidation:
    """Verify that /app/tasks/new accepts upload-dir absolute paths and
    still rejects traversal / arbitrary absolute paths.

    We check status codes only; on rejection the handler redirects to
    /app/tasks/new with a flash; on accept it redirects to /app/tasks
    after creating the task. We don't need to assert on side-effects
    here — the routing target distinguishes the two paths.
    """

    def _post_task(self, app_client, portal_cookie, source_path, upload_root):
        # Mock channel ownership
        channel = {"id": 7, "uuid": "ch-uuid", "created_by": TEST_USER["id"]}
        with patch("shared.db.repositories.channel_repo.get_channel_by_id", return_value=channel), \
             patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.create_task", return_value=42), \
             patch.dict(os.environ, {"UPLOAD_DIR": str(upload_root)}):
            return app_client.post(
                "/app/tasks/new",
                cookies=portal_cookie,
                headers=_csrf_headers(),
                data={
                    "channel_id": "7",
                    "title": "test task",
                    "source_file_path": source_path,
                },
                follow_redirects=False,
            )

    def test_accepts_absolute_path_under_upload_dir(self, app_client, portal_cookie, upload_dir):
        # Create a real file under upload_dir so realpath resolution succeeds.
        f = upload_dir / "videos" / "abc.mp4"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")

        resp = self._post_task(app_client, portal_cookie, str(f), upload_dir)
        # Success path → redirect to /app/tasks
        assert resp.status_code == 302
        assert resp.headers["location"] == "/app/tasks"

    def test_rejects_path_traversal(self, app_client, portal_cookie, upload_dir):
        bad = f"{upload_dir}/videos/../../../etc/passwd"
        resp = self._post_task(app_client, portal_cookie, bad, upload_dir)
        # Rejection → redirect back to form
        assert resp.status_code == 302
        assert resp.headers["location"] == "/app/tasks/new"

    def test_rejects_absolute_path_outside_upload_dir(self, app_client, portal_cookie, upload_dir):
        resp = self._post_task(app_client, portal_cookie, "/etc/passwd", upload_dir)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/app/tasks/new"

    def test_accepts_relative_path(self, app_client, portal_cookie, upload_dir):
        # Relative paths historically allowed (workers may resolve them
        # relative to a known root) — must not be rejected by the
        # validator.
        resp = self._post_task(app_client, portal_cookie, "videos/file.mp4", upload_dir)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/app/tasks"
