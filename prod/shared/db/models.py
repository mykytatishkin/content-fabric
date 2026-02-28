"""SQLAlchemy Core table definitions for the new schema (13 tables)."""

from enum import IntEnum


class TaskStatus(IntEnum):
    PENDING = 0
    COMPLETED = 1
    FAILED = 2
    PROCESSING = 3
    CANCELLED = 4


class UserStatus(IntEnum):
    INACTIVE = 0
    ADMIN = 1
    ACTIVE = 10


from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    MetaData,
    SmallInteger,
    String,
    Table,
    Text,
    TIMESTAMP,
)
from sqlalchemy.dialects.mysql import TINYINT

metadata = MetaData()

# ── Identity & Access ──────────────────────────────────────────────

platform_users = Table(
    "platform_users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("uuid", String(36), nullable=False, unique=True),
    Column("username", String(255), nullable=False, unique=True),
    Column("email", String(255), nullable=False, unique=True),
    Column("password_hash", String(255)),
    Column("auth_key", String(32), nullable=False),
    Column("password_reset_token", String(255)),
    Column("totp_secret", String(64)),
    Column("totp_enabled", TINYINT(1), nullable=False, server_default="0"),
    Column("totp_backup_codes", JSON),
    Column("verification_token", String(255)),
    Column("display_name", String(255)),
    Column("avatar_url", Text),
    Column("status", SmallInteger, nullable=False, server_default="10"),
    Column("timezone", String(64), server_default="UTC"),
    Column("last_login_at", TIMESTAMP),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

platform_projects = Table(
    "platform_projects", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("uuid", String(36), nullable=False, unique=True),
    Column("owner_id", Integer, ForeignKey("platform_users.id"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("slug", String(100), nullable=False, unique=True),
    Column("description", Text),
    Column("subscription_plan", String(50), nullable=False, server_default="starter"),
    Column("subscription_expires_at", DateTime),
    Column("settings", JSON),
    Column("status", SmallInteger, nullable=False, server_default="10"),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

platform_project_members = Table(
    "platform_project_members", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", Integer, ForeignKey("platform_projects.id"), nullable=False),
    Column("user_id", Integer, ForeignKey("platform_users.id"), nullable=False),
    Column("role", String(50), nullable=False, server_default="viewer"),
    Column("invited_by", Integer, ForeignKey("platform_users.id")),
    Column("invited_at", TIMESTAMP),
    Column("accepted_at", TIMESTAMP),
    Column("status", String(20), nullable=False, server_default="active"),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

# ── Channels & OAuth ───────────────────────────────────────────────

platform_oauth_credentials = Table(
    "platform_oauth_credentials", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", Integer, ForeignKey("platform_projects.id"), nullable=False),
    Column("platform", String(50), nullable=False, server_default="google"),
    Column("name", String(255), nullable=False),
    Column("cloud_project_id", String(255)),
    Column("client_id", Text, nullable=False),
    Column("client_secret", Text, nullable=False),
    Column("redirect_uris", JSON),
    Column("credentials_file", String(500)),
    Column("description", Text),
    Column("enabled", TINYINT(1), nullable=False, server_default="1"),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

platform_channels = Table(
    "platform_channels", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", Integer, ForeignKey("platform_projects.id"), nullable=False),
    Column("console_id", Integer, ForeignKey("platform_oauth_credentials.id")),
    Column("platform", String(50), nullable=False, server_default="youtube"),
    Column("name", String(255), nullable=False),
    Column("platform_channel_id", String(255), nullable=False),
    Column("access_token", Text),
    Column("refresh_token", Text),
    Column("token_expires_at", DateTime),
    Column("enabled", TINYINT(1), nullable=False, server_default="1"),
    Column("processing_status", TINYINT(1), nullable=False, server_default="0"),
    Column("metadata_", JSON, key="metadata"),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

platform_channel_tokens = Table(
    "platform_channel_tokens", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("channel_id", Integer, ForeignKey("platform_channels.id"), nullable=False),
    Column("token_type", String(100), nullable=False),
    Column("token_value", Text, nullable=False),
    Column("expires_at", DateTime),
    Column("created_at", TIMESTAMP, nullable=False),
)

platform_channel_login_credentials = Table(
    "platform_channel_login_credentials", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("channel_id", Integer, ForeignKey("platform_channels.id"), nullable=False),
    Column("login_email", String(320), nullable=False),
    Column("login_password", Text, nullable=False),
    Column("totp_secret", String(64)),
    Column("backup_codes", JSON),
    Column("proxy_host", String(255)),
    Column("proxy_port", Integer),
    Column("proxy_username", String(255)),
    Column("proxy_password", String(255)),
    Column("profile_path", String(500)),
    Column("user_agent", String(500)),
    Column("last_success_at", DateTime),
    Column("last_attempt_at", DateTime),
    Column("last_error", Text),
    Column("enabled", TINYINT(1), nullable=False, server_default="1"),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

# ── Publishing ─────────────────────────────────────────────────────

content_upload_queue_tasks = Table(
    "content_upload_queue_tasks", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", Integer, ForeignKey("platform_projects.id"), nullable=False),
    Column("channel_id", Integer, ForeignKey("platform_channels.id"), nullable=False),
    Column("created_by", Integer, ForeignKey("platform_users.id")),
    Column("platform", String(50), nullable=False, server_default="youtube"),
    Column("media_type", String(20), nullable=False, server_default="video"),
    Column("status", TINYINT, nullable=False, server_default="0"),
    Column("source_file_path", String(500)),
    Column("thumbnail_path", String(500)),
    Column("title", String(500), nullable=False),
    Column("description", Text),
    Column("keywords", Text),
    Column("post_comment", Text),
    Column("metadata_", JSON, key="metadata"),
    Column("scheduled_at", DateTime, nullable=False),
    Column("started_at", DateTime),
    Column("completed_at", DateTime),
    Column("upload_id", String(255)),
    Column("upload_url", String(500)),
    Column("retry_count", Integer, nullable=False, server_default="0"),
    Column("max_retries", Integer, nullable=False, server_default="3"),
    Column("error_message", Text),
    Column("error_code", String(100)),
    Column("legacy_add_info", Text),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

# ── Analytics & Audit ──────────────────────────────────────────────

channel_daily_statistics = Table(
    "channel_daily_statistics", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("channel_id", Integer, ForeignKey("platform_channels.id"), nullable=False),
    Column("platform_channel_id", String(64), nullable=False),
    Column("snapshot_date", DateTime, nullable=False),
    Column("subscribers", BigInteger),
    Column("views", BigInteger),
    Column("videos", BigInteger),
    Column("likes", BigInteger),
    Column("comments", BigInteger),
    Column("metadata_", JSON, key="metadata"),
    Column("created_at", TIMESTAMP, nullable=False),
)

channel_reauth_audit_logs = Table(
    "channel_reauth_audit_logs", metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("channel_id", Integer, ForeignKey("platform_channels.id"), nullable=False),
    Column("initiated_at", DateTime, nullable=False),
    Column("completed_at", DateTime),
    Column("status", String(32), nullable=False),
    Column("trigger_reason", String(100)),
    Column("error_message", Text),
    Column("error_code", String(100)),
    Column("metadata_", JSON, key="metadata"),
    Column("created_at", TIMESTAMP, nullable=False),
)

# ── Streaming ──────────────────────────────────────────────────────

live_streaming_accounts = Table(
    "live_streaming_accounts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", Integer, ForeignKey("platform_projects.id"), nullable=False),
    Column("platform", String(50), nullable=False, server_default="youtube"),
    Column("name", String(255), nullable=False),
    Column("client_id", String(255), nullable=False),
    Column("client_secret", String(255), nullable=False),
    Column("access_token", Text, nullable=False),
    Column("refresh_token", Text, nullable=False),
    Column("token_expires_at", TIMESTAMP),
    Column("enabled", TINYINT(1), nullable=False, server_default="1"),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

live_stream_configurations = Table(
    "live_stream_configurations", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", Integer, ForeignKey("platform_projects.id"), nullable=False),
    Column("streaming_account_id", Integer, ForeignKey("live_streaming_accounts.id")),
    Column("channel_id", Integer, ForeignKey("platform_channels.id")),
    Column("name", String(120), nullable=False),
    Column("service_name", String(160), nullable=False),
    Column("workdir", String(255), nullable=False),
    Column("rtmp_host", String(255)),
    Column("rtmp_base", String(255)),
    Column("stream_key", String(255)),
    Column("duration_sec", Integer, nullable=False, server_default="42900"),
    Column("platform_broadcast_id", String(64)),
    Column("platform_video_id", String(64)),
    Column("platform_stream_id", String(64)),
    Column("platform_stream_key", String(128)),
    Column("title", String(255)),
    Column("description", Text),
    Column("tags", Text),
    Column("thumbnail_path", String(255)),
    Column("enabled", TINYINT(1), nullable=False, server_default="1"),
    Column("notes", Text),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

# ── Schedule Templates ────────────────────────────────────────────

schedule_templates = Table(
    "schedule_templates", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", Integer, ForeignKey("platform_projects.id"), nullable=False),
    Column("created_by", Integer, ForeignKey("platform_users.id")),
    Column("name", String(255), nullable=False),
    Column("description", Text),
    Column("timezone", String(64), nullable=False, server_default="UTC"),
    Column("is_active", TINYINT(1), nullable=False, server_default="1"),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

schedule_template_slots = Table(
    "schedule_template_slots", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("template_id", Integer, ForeignKey("schedule_templates.id"), nullable=False),
    Column("day_of_week", TINYINT, nullable=False),
    Column("time_utc", String(8), nullable=False),
    Column("channel_id", Integer, ForeignKey("platform_channels.id")),
    Column("media_type", String(20), nullable=False, server_default="video"),
    Column("enabled", TINYINT(1), nullable=False, server_default="1"),
    Column("created_at", TIMESTAMP, nullable=False),
)

# ── System ─────────────────────────────────────────────────────────

platform_schema_migrations = Table(
    "platform_schema_migrations", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("version", String(180), nullable=False, unique=True),
    Column("description", String(500)),
    Column("checksum", String(64)),
    Column("applied_at", TIMESTAMP, nullable=False),
    Column("execution_ms", Integer),
    Column("rolled_back", TINYINT(1), nullable=False, server_default="0"),
)
