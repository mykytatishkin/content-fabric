"""Integration test for DleIngestionPipeline (Mocked DB)."""

import pytest
from unittest.mock import MagicMock, patch
from shared.ingestion.dle.pipeline import DleIngestionPipeline

@patch("shared.ingestion.dle.pipeline.DleClient")
@patch("shared.ingestion.dle.pipeline.get_task_by_dle_id")
@patch("shared.ingestion.dle.pipeline.create_task")
def test_dle_pipeline_run(mock_create, mock_get_by_id, mock_client_class):
    # Mock settings
    with patch("shared.ingestion.dle.pipeline.dle_settings") as mock_settings:
        mock_settings.all_sources.return_value = {"test_source": "mysql://dsn"}
        
        # Mock Client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.fetch_recent_posts.return_value = [
            {"id": 1, "title": "Post 1", "alt_name": "post-1", "normalized": {}},
            {"id": 2, "title": "Post 2", "alt_name": "post-2", "normalized": {}},
        ]
        
        # Mock duplicate check: post 1 exists, post 2 is new
        mock_get_by_id.side_effect = lambda slug, post_id: {"id": 101} if post_id == 1 else None
        
        # Mock task creation
        mock_create.return_value = 202
        
        pipeline = DleIngestionPipeline("test_source")
        count = pipeline.run(channel_id=5, limit=2)
        
        assert count == 1  # Only post 2 should be created
        mock_create.assert_called_once()
        args, kwargs = mock_create.call_args
        assert kwargs["title"] == "Post 2"
        assert kwargs["channel_id"] == 5
