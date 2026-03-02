"""Tests for shared.logging_config — centralized logging setup."""

import logging
import os
from unittest.mock import patch

from shared.logging_config import setup_logging


class TestSetupLogging:
    def test_default_level_info(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEBUG", None)
            os.environ.pop("LOG_LEVEL", None)
            setup_logging("test-svc")
            root = logging.getLogger()
            assert root.level == logging.INFO

    def test_debug_mode(self):
        with patch.dict(os.environ, {"DEBUG": "1"}, clear=False):
            os.environ.pop("LOG_LEVEL", None)
            setup_logging("test-debug")
            root = logging.getLogger()
            assert root.level == logging.DEBUG

    def test_custom_log_level(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}, clear=False):
            setup_logging("test-warn")
            root = logging.getLogger()
            assert root.level == logging.WARNING

    def test_noisy_libraries_silenced(self):
        setup_logging("test-quiet")
        for name in ("urllib3", "sqlalchemy.engine", "googleapiclient"):
            assert logging.getLogger(name).level >= logging.WARNING

    def test_handler_added(self):
        setup_logging("test-handler")
        root = logging.getLogger()
        assert len(root.handlers) > 0


class TestHealthEndpoint:
    def test_health_returns_200(self, app_client):
        resp = app_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "checks" in data
        assert "details" in data
        assert "uptime_seconds" in data["details"]

    def test_health_has_api_check(self, app_client):
        resp = app_client.get("/health")
        data = resp.json()
        assert data["checks"]["api"] == "ok"
