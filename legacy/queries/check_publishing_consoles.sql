-- SQL запрос для проверки, какие Google консоли используются для публикаций
-- Запустите этот запрос в MySQL, чтобы увидеть текущую конфигурацию

-- 1. Показать все Google консоли
SELECT 
    id,
    name,
    enabled,
    description,
    LEFT(client_id, 30) as client_id_preview,
    created_at,
    updated_at
FROM google_consoles
ORDER BY enabled DESC, name;

-- 2. Показать каналы и их назначенные консоли
SELECT 
    c.id as channel_id,
    c.name as channel_name,
    c.channel_id as youtube_channel_id,
    c.enabled as channel_enabled,
    c.console_name,
    g.name as console_name_from_table,
    g.enabled as console_enabled,
    CASE 
        WHEN c.console_name IS NOT NULL AND g.id IS NOT NULL THEN 'Использует консоль'
        WHEN c.client_id IS NOT NULL AND c.client_secret IS NOT NULL THEN 'Использует fallback (credentials канала)'
        ELSE 'Нет credentials'
    END as publishing_method
FROM youtube_channels c
LEFT JOIN google_consoles g ON c.console_name = g.name
ORDER BY c.enabled DESC, c.name;

-- 3. Сводка по использованию консолей
SELECT 
    COALESCE(g.name, 'Fallback (credentials канала)') as console_name,
    COUNT(*) as channel_count,
    SUM(CASE WHEN c.enabled = 1 THEN 1 ELSE 0 END) as enabled_channels
FROM youtube_channels c
LEFT JOIN google_consoles g ON c.console_name = g.name
GROUP BY g.name
ORDER BY channel_count DESC;

-- 4. Детальная информация о том, какая консоль используется для каждого канала
SELECT 
    c.name as channel_name,
    c.enabled as channel_enabled,
    CASE 
        WHEN c.console_name IS NOT NULL THEN 
            CONCAT('Консоль: ', c.console_name, 
                   CASE WHEN g.enabled = 1 THEN ' (включена)' ELSE ' (отключена!)' END)
        WHEN c.client_id IS NOT NULL THEN 
            'Fallback: credentials из канала'
        ELSE 
            'ОШИБКА: Нет credentials!'
    END as publishing_console_info,
    CASE 
        WHEN c.console_name IS NOT NULL AND g.id IS NOT NULL AND g.enabled = 1 THEN '✅ OK'
        WHEN c.console_name IS NOT NULL AND g.id IS NULL THEN '❌ Консоль не найдена'
        WHEN c.console_name IS NOT NULL AND g.enabled = 0 THEN '⚠️ Консоль отключена'
        WHEN c.client_id IS NOT NULL THEN '⚠️ Fallback'
        ELSE '❌ Нет credentials'
    END as status
FROM youtube_channels c
LEFT JOIN google_consoles g ON c.console_name = g.name
ORDER BY c.enabled DESC, c.name;


