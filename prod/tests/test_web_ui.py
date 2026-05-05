"""Web UI tests for the new integrated admin panels."""

import pytest
from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch, MagicMock

client = TestClient(app)

@pytest.fixture
def mock_admin_session():
    """Mock the admin session to bypass require_admin check in panel.py."""
    with patch("app.views.panel.require_admin") as mock:
        # Return a mock user and None for redirect
        mock.return_value = ({"id": 1, "username": "admin", "role": "admin"}, None)
        yield mock

def test_dashboard_page(mock_admin_session):
    # Mock DB calls within dashboard
    with patch("shared.db.connection.get_connection") as mock_conn:
        # Mock result for multiple queries
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_cursor
        
        # 1. Channel counts
        mock_cursor.execute.return_value.fetchone.return_value = (10, 5)
        # 2. User count
        # 3. Task stats, etc.
        mock_cursor.execute.return_value.fetchall.return_value = []
        
        response = client.get("/panel/")
        assert response.status_code == 200
        assert "Dashboard" in response.text

def test_streams_page(mock_admin_session):
    with patch("shared.db.connection.get_connection") as mock_conn:
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_cursor
        
        # Mock 2 streams: (id, name, service, workdir, key, channel_id, yid)
        mock_cursor.execute.return_value.fetchall.return_value = [
            (1, "stream-1", "cff-stream-1", "/tmp", "key12345678", 5, 101),
            (2, "stream-2", "cff-stream-2", "/tmp", "key45678901", 6, 102),
        ]
        
        # Mock systemctl status check
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="active")
            
            response = client.get("/panel/streams")
            assert response.status_code == 200
            assert "Live Streams" in response.text
            assert "stream-1" in response.text
            assert "Running" in response.text

def test_dle_sources_page(mock_admin_session):
    with patch("app.core.config.dle_settings") as mock_settings:
        mock_settings.all_sources.return_value = {
            "test_source": "mysql://user:pass@host/db"
        }
        
        response = client.get("/panel/dle-sources")
        assert response.status_code == 200
        assert "DLE Content Sources" in response.text
        assert "test_source" in response.text
        # Ensure password is masked
        assert "pass" not in response.text

def test_stats_page(mock_admin_session):
    with patch("shared.db.connection.get_connection") as mock_conn:
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_cursor
        
        mock_cursor.execute.return_value.fetchall.return_value = [
            ("2026-05-01", 1000, 50000, 100)
        ]
        
        response = client.get("/panel/stats")
        assert response.status_code == 200
        assert "2026-05-01" in response.text
