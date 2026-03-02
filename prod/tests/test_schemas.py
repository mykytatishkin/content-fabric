"""Tests for Pydantic schemas — validation rules."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskBatchCreate


class TestLoginRequest:
    def test_valid(self):
        r = LoginRequest(email="a@b.com", password="pass")
        assert r.email == "a@b.com"
        assert r.totp_code is None

    def test_with_totp(self):
        r = LoginRequest(email="a@b.com", password="pass", totp_code="123456")
        assert r.totp_code == "123456"


class TestRegisterRequest:
    def test_valid(self):
        r = RegisterRequest(username="user", email="a@b.com", password="password123")
        assert r.display_name is None

    def test_with_display_name(self):
        r = RegisterRequest(username="user", email="a@b.com", password="password123", display_name="User")
        assert r.display_name == "User"

    def test_short_password_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(username="user", email="a@b.com", password="short")


class TestTokenResponse:
    def test_defaults(self):
        t = TokenResponse(access_token="tok")
        assert t.token_type == "bearer"
        assert t.requires_2fa is False


class TestTaskCreate:
    def test_valid(self):
        t = TaskCreate(
            channel_id=1,
            source_file_path="uploads/videos/video.mp4",
            title="My Video",
            scheduled_at=datetime(2026, 3, 1, 12, 0),
        )
        assert t.media_type == "video"

    def test_path_traversal_rejected(self):
        with pytest.raises(ValidationError, match="Path traversal"):
            TaskCreate(
                channel_id=1,
                source_file_path="uploads/../etc/passwd",
                title="Bad",
                scheduled_at=datetime(2026, 3, 1),
            )

    def test_absolute_path_rejected(self):
        with pytest.raises(ValidationError, match="Absolute paths"):
            TaskCreate(
                channel_id=1,
                source_file_path="/etc/passwd",
                title="Bad",
                scheduled_at=datetime(2026, 3, 1),
            )

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            TaskCreate(
                channel_id=1,
                source_file_path="uploads/v.mp4",
                title="",
                scheduled_at=datetime(2026, 3, 1),
            )

    def test_path_too_long_rejected(self):
        with pytest.raises(ValidationError):
            TaskCreate(
                channel_id=1,
                source_file_path="a" * 1002,
                title="X",
                scheduled_at=datetime(2026, 3, 1),
            )

    def test_thumbnail_traversal_rejected(self):
        with pytest.raises(ValidationError, match="Path traversal"):
            TaskCreate(
                channel_id=1,
                source_file_path="uploads/v.mp4",
                title="X",
                scheduled_at=datetime(2026, 3, 1),
                thumbnail_path="uploads/../../etc/shadow",
            )


class TestTaskUpdate:
    def test_all_none(self):
        t = TaskUpdate()
        assert t.status is None
        assert t.scheduled_at is None

    def test_partial(self):
        t = TaskUpdate(status=1)
        assert t.status == 1


class TestTaskBatchCreate:
    def test_multiple_tasks(self):
        b = TaskBatchCreate(tasks=[
            TaskCreate(channel_id=1, source_file_path="uploads/a.mp4", title="A", scheduled_at=datetime(2026, 3, 1)),
            TaskCreate(channel_id=2, source_file_path="uploads/b.mp4", title="B", scheduled_at=datetime(2026, 3, 2)),
        ])
        assert len(b.tasks) == 2
