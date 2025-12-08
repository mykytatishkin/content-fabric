-- UPDATE для всех записей где client_id или client_secret пустые
UPDATE youtube_channels
SET
    console_id = 1,
    updated_at = CURRENT_TIMESTAMP
WHERE
    (console_id IS NULL OR console_id = '' OR TRIM(console_id) = '');
