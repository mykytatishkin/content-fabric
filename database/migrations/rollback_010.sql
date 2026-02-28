-- Rollback 010: Drop schedule template tables

DROP TABLE IF EXISTS schedule_template_slots;
DROP TABLE IF EXISTS schedule_templates;

DELETE FROM platform_schema_migrations WHERE version = '010';
