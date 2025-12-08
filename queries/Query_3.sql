-- UPDATE для всех записей где client_id или client_secret пустые
UPDATE youtube_channels
SET
    client_id = '923063452206-78e3f9ea06pv5snaegs2a78i5na5o7hk.apps.googleusercontent.com',
    client_secret = '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',
    updated_at = CURRENT_TIMESTAMP
WHERE
    (client_id IS NULL OR client_id = '' OR TRIM(client_id) = '')
    OR (client_secret IS NULL OR client_secret = '' OR TRIM(client_secret) = '');
