-- Migration 010: Create schedule template tables
-- Idempotent: safe to run multiple times

CREATE TABLE IF NOT EXISTS schedule_templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    created_by INT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES platform_projects(id),
    FOREIGN KEY (created_by) REFERENCES platform_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS schedule_template_slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    template_id INT NOT NULL,
    day_of_week TINYINT NOT NULL COMMENT '0=Monday, 6=Sunday',
    time_utc TIME NOT NULL,
    channel_id INT,
    media_type VARCHAR(20) NOT NULL DEFAULT 'video',
    enabled TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES schedule_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES platform_channels(id),
    INDEX idx_template_day (template_id, day_of_week)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Record migration
INSERT IGNORE INTO platform_schema_migrations (version, description, applied_at, execution_ms)
VALUES ('010', 'Create schedule template tables', NOW(), 0);
