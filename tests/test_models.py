"""Tests for shared.db.models — enums and table definitions."""

from shared.db.models import TaskStatus, UserStatus, metadata


class TestTaskStatus:
    def test_values(self):
        assert TaskStatus.PENDING == 0
        assert TaskStatus.COMPLETED == 1
        assert TaskStatus.FAILED == 2
        assert TaskStatus.PROCESSING == 3
        assert TaskStatus.CANCELLED == 4

    def test_all_members(self):
        assert len(TaskStatus) == 5

    def test_name_lookup(self):
        assert TaskStatus(0).name == "PENDING"
        assert TaskStatus(2).name == "FAILED"


class TestUserStatus:
    def test_values(self):
        assert UserStatus.INACTIVE == 0
        assert UserStatus.ADMIN == 1
        assert UserStatus.ACTIVE == 10

    def test_all_members(self):
        assert len(UserStatus) == 3


class TestMetadata:
    def test_all_tables_defined(self):
        table_names = set(metadata.tables.keys())
        expected = {
            "platform_users",
            "platform_projects",
            "platform_project_members",
            "platform_oauth_credentials",
            "platform_channels",
            "platform_channel_tokens",
            "platform_channel_login_credentials",
            "content_upload_queue_tasks",
            "channel_daily_statistics",
            "channel_reauth_audit_logs",
            "live_streaming_accounts",
            "live_stream_configurations",
            "schedule_templates",
            "schedule_template_slots",
            "platform_schema_migrations",
        }
        assert expected.issubset(table_names)

    def test_tasks_table_has_status_column(self):
        from shared.db.models import content_upload_queue_tasks
        col_names = {c.name for c in content_upload_queue_tasks.columns}
        assert "status" in col_names
        assert "title" in col_names
        assert "scheduled_at" in col_names
