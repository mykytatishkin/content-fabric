SELECT 
    t.status,
    t.id AS task_id,
    t.account_id,
    t.error_message,
    yac.last_error,
    yc.name,
    yc.channel_id,
    yac.channel_name,
    yac.login_email
FROM tasks AS t
INNER JOIN youtube_channels AS yc ON t.account_id = yc.id
INNER JOIN youtube_account_credentials AS yac ON yc.name = yac.channel_name
WHERE t.status = 2 and t.id > 3000;