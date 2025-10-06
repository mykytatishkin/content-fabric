# MySQL Migration Guide

## Обзор миграции

Этот гайд поможет вам мигрировать с SQLite на MySQL для проекта Content Fabric.

## Предварительные требования

1. **MySQL Server** установлен и запущен
2. **Python 3.8+** с установленными зависимостями
3. **Резервная копия** текущей SQLite базы данных

## Пошаговая миграция

### Шаг 1: Установка MySQL

Следуйте инструкциям в [MYSQL_SETUP_GUIDE.md](MYSQL_SETUP_GUIDE.md) для установки и настройки MySQL.

### Шаг 2: Установка зависимостей

```bash
# Установка MySQL драйвера
pip install mysql-connector-python

# Или обновить все зависимости
pip install -r requirements.txt
```

### Шаг 3: Настройка конфигурации MySQL

1. **Скопируйте конфигурационный файл:**
   ```bash
   cp mysql_config.yaml mysql_config_local.yaml
   ```

2. **Отредактируйте `mysql_config_local.yaml`:**
   ```yaml
   mysql:
     host: localhost
     port: 3306
     database: content_fabric
     user: content_fabric_user
     password: your_secure_password_here
     charset: utf8mb4
     collation: utf8mb4_unicode_ci
   ```

3. **Или установите переменные окружения:**
   ```bash
   export DB_TYPE=mysql
   export MYSQL_HOST=localhost
   export MYSQL_PORT=3306
   export MYSQL_DATABASE=content_fabric
   export MYSQL_USER=content_fabric_user
   export MYSQL_PASSWORD=your_secure_password_here
   ```

### Шаг 4: Создание MySQL базы данных

```bash
# Автоматическая настройка
python setup_mysql.py --config mysql_config_local.yaml

# Или только создание базы данных
python setup_mysql.py --config mysql_config_local.yaml --setup-only
```

### Шаг 5: Миграция данных

```bash
# Миграция из SQLite в MySQL
python migrate_to_mysql.py \
  --sqlite-path youtube_channels.db \
  --mysql-host localhost \
  --mysql-database content_fabric \
  --mysql-user content_fabric_user \
  --mysql-password your_password
```

### Шаг 6: Проверка миграции

```bash
# Проверка подключения
python setup_mysql.py --config mysql_config_local.yaml --test-only

# Просмотр каналов в MySQL
python youtube_mysql_manager.py --config mysql_config_local.yaml list

# Статистика базы данных
python youtube_mysql_manager.py --config mysql_config_local.yaml stats
```

## Использование MySQL в приложении

### Переключение на MySQL

1. **Установите переменную окружения:**
   ```bash
   export DB_TYPE=mysql
   ```

2. **Или обновите код для использования MySQL:**
   ```python
   from src.database import get_database_by_type
   
   # Использование MySQL
   db = get_database_by_type('mysql', mysql_config)
   
   # Или через переменную окружения
   db = get_database_by_type()  # Использует DB_TYPE из env
   ```

### Обновление существующего кода

Замените импорты в ваших файлах:

```python
# Старый код
from src.database import get_database
db = get_database()

# Новый код
from src.database import get_database_by_type
db = get_database_by_type('mysql', config)
```

## Управление каналами через MySQL

### Основные команды

```bash
# Просмотр всех каналов
python youtube_mysql_manager.py list

# Добавление канала
python youtube_mysql_manager.py add "My Channel" \
  --channel-id "UC123456789" \
  --client-id "your_client_id" \
  --client-secret "your_client_secret"

# Просмотр информации о канале
python youtube_mysql_manager.py show "My Channel"

# Включение/отключение канала
python youtube_mysql_manager.py enable "My Channel"
python youtube_mysql_manager.py disable "My Channel"

# Проверка токенов
python youtube_mysql_manager.py check-tokens

# Статистика базы данных
python youtube_mysql_manager.py stats
```

### Экспорт/Импорт конфигурации

```bash
# Экспорт в файл
python youtube_mysql_manager.py export --output channels_backup.json

# Импорт из файла
python youtube_mysql_manager.py import channels_backup.json
```

## Мониторинг и обслуживание

### Полезные SQL запросы

```sql
-- Просмотр всех каналов
SELECT name, channel_id, enabled, created_at FROM youtube_channels;

-- Каналы с истекшими токенами
SELECT name, token_expires_at FROM youtube_channels 
WHERE enabled = 1 AND (token_expires_at IS NULL OR token_expires_at < NOW());

-- Статистика по каналам
SELECT 
    COUNT(*) as total_channels,
    SUM(enabled) as enabled_channels,
    COUNT(*) - SUM(enabled) as disabled_channels
FROM youtube_channels;
```

### Резервное копирование

```bash
# Создание дампа базы данных
mysqldump -u content_fabric_user -p content_fabric > content_fabric_backup.sql

# Восстановление из дампа
mysql -u content_fabric_user -p content_fabric < content_fabric_backup.sql
```

## Устранение неполадок

### Проблемы с подключением

1. **Проверьте статус MySQL:**
   ```bash
   sudo systemctl status mysql
   ```

2. **Проверьте конфигурацию:**
   ```bash
   python setup_mysql.py --test-only
   ```

3. **Проверьте логи MySQL:**
   ```bash
   sudo tail -f /var/log/mysql/error.log
   ```

### Проблемы с миграцией

1. **Проверьте SQLite файл:**
   ```bash
   sqlite3 youtube_channels.db ".tables"
   ```

2. **Проверьте права доступа:**
   ```bash
   ls -la youtube_channels.db
   ```

3. **Запустите миграцию с подробным выводом:**
   ```bash
   python migrate_to_mysql.py --sqlite-path youtube_channels.db --mysql-password your_password
   ```

## Откат к SQLite

Если нужно вернуться к SQLite:

1. **Установите переменную окружения:**
   ```bash
   export DB_TYPE=sqlite
   # или удалите переменную DB_TYPE
   ```

2. **Или явно укажите тип базы данных в коде:**
   ```python
   db = get_database_by_type('sqlite')
   ```

## Производительность

### Рекомендации по оптимизации MySQL

1. **Настройте InnoDB:**
   ```ini
   [mysqld]
   innodb_buffer_pool_size = 256M
   innodb_log_file_size = 64M
   innodb_flush_log_at_trx_commit = 2
   ```

2. **Создайте индексы:**
   ```sql
   CREATE INDEX idx_channels_enabled ON youtube_channels(enabled);
   CREATE INDEX idx_tokens_expires ON youtube_tokens(expires_at);
   ```

3. **Регулярно оптимизируйте таблицы:**
   ```sql
   OPTIMIZE TABLE youtube_channels;
   OPTIMIZE TABLE youtube_tokens;
   ```

## Безопасность

### Рекомендации по безопасности

1. **Используйте сильные пароли**
2. **Ограничьте доступ по IP адресам**
3. **Используйте SSL соединения**
4. **Регулярно обновляйте MySQL**
5. **Делайте резервные копии**

### Настройка SSL

```sql
-- Проверка SSL статуса
SHOW VARIABLES LIKE 'have_ssl';

-- Принудительное использование SSL
ALTER USER 'content_fabric_user'@'%' REQUIRE SSL;
```

## Поддержка

При возникновении проблем:

1. Проверьте логи приложения
2. Проверьте логи MySQL
3. Убедитесь в правильности конфигурации
4. Проверьте сетевые подключения
5. Обратитесь к документации MySQL
