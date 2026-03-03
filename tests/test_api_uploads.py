"""Tests for file upload endpoints."""

import io
import os
import tempfile
from unittest.mock import patch

import pytest

from tests.conftest import TEST_USER


@pytest.fixture()
def upload_dir(tmp_path):
    """Provide a temp upload directory."""
    with patch("app.api.endpoints.uploads.UPLOAD_DIR", tmp_path):
        yield tmp_path


class TestVideoUpload:
    def test_unauthenticated(self, app_client):
        resp = app_client.post("/api/v1/uploads/video", files={"file": ("test.mp4", b"data", "video/mp4")})
        assert resp.status_code in (401, 403)

    def test_success(self, app_client, auth_headers, upload_dir):
        content = b"fake-video-content-" * 100
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("app.core.audit.log"):
            resp = app_client.post(
                "/api/v1/uploads/video",
                headers=auth_headers,
                files={"file": ("my_video.mp4", io.BytesIO(content), "video/mp4")},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "my_video.mp4"
        assert data["size_bytes"] == len(content)
        assert data["path"].endswith(".mp4")
        assert os.path.exists(data["path"])

    def test_bad_extension(self, app_client, auth_headers, upload_dir):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER):
            resp = app_client.post(
                "/api/v1/uploads/video",
                headers=auth_headers,
                files={"file": ("malware.exe", b"data", "application/octet-stream")},
            )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"]


class TestThumbnailUpload:
    def test_success(self, app_client, auth_headers, upload_dir):
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("app.core.audit.log"):
            resp = app_client.post(
                "/api/v1/uploads/thumbnail",
                headers=auth_headers,
                files={"file": ("thumb.png", io.BytesIO(content), "image/png")},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "thumb.png"
        assert os.path.exists(data["path"])

    def test_bad_extension(self, app_client, auth_headers, upload_dir):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER):
            resp = app_client.post(
                "/api/v1/uploads/thumbnail",
                headers=auth_headers,
                files={"file": ("doc.pdf", b"data", "application/pdf")},
            )
        assert resp.status_code == 400
