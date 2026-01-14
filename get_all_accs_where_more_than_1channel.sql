SELECT channel_name, login_email
FROM youtube_account_credentials
WHERE login_email IN (
    SELECT login_email
    FROM youtube_account_credentials
    GROUP BY login_email
    HAVING COUNT(*) > 1
);