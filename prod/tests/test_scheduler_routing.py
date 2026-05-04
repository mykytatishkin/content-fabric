"""Tests for the scheduler distribution logic."""

import pytest
from unittest.mock import patch, MagicMock
from scheduler.jobs import enqueue_pending_tasks
from shared.db.models import TaskStatus

@patch("shared.db.repositories.task_repo.get_pending_tasks")
@patch("shared.db.repositories.task_repo.mark_task_processing")
@patch("shared.db.repositories.task_repo.update_task_status")
@patch("scheduler.jobs.enqueue_voice_change")
@patch("scheduler.jobs.enqueue_video_upload")
def test_enqueue_routing_logic(mock_upload, mock_voice, mock_update, mock_mark, mock_get_pending):
    # Case 1: DLE task (empty path + dle_source in legacy)
    dle_task = {
        "id": 1,
        "channel_id": 5,
        "source_file_path": "",
        "title": "DLE Title",
        "media_type": "video",
        "legacy_add_info": {"dle_source": "audiokniga"}
    }
    
    # Case 2: Regular task (has path)
    regular_task = {
        "id": 2,
        "channel_id": 6,
        "source_file_path": "path/to/video.mp4",
        "title": "Regular Title",
        "media_type": "video",
        "legacy_add_info": {}
    }
    
    mock_get_pending.return_value = [dle_task, regular_task]
    
    count = enqueue_pending_tasks()
    
    assert count == 2
    
    # Verify DLE task went to voice queue
    mock_voice.assert_called_once()
    dle_payload = mock_voice.call_args[0][0]
    assert dle_payload.task_id == 1
    assert dle_payload.metadata["is_dle"] is True
    
    # Verify regular task went to upload queue
    mock_upload.assert_called_once()
    reg_payload = mock_upload.call_args[0][0]
    assert reg_payload.task_id == 2
    assert reg_payload.source_file_path == "path/to/video.mp4"
    
    # Verify both marked as processing
    assert mock_mark.call_count == 2

@patch("shared.db.repositories.task_repo.get_pending_tasks")
@patch("shared.db.repositories.task_repo.update_task_status")
@patch("shared.queue.publisher.enqueue_video_upload")
def test_enqueue_error_handling(mock_upload, mock_update_status, mock_get_pending):
    # Mock failure during enqueuing
    mock_get_pending.return_value = [{"id": 10, "channel_id": 5, "source_file_path": "x.mp4"}]
    mock_upload.side_effect = Exception("Redis down")
    
    enqueue_pending_tasks()
    
    # Should reset status back to PENDING (0)
    mock_update_status.assert_called_with(10, TaskStatus.PENDING.value)
