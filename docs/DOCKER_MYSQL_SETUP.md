# 🐳 MySQL в Docker для разработки

## Быстрый старт на macOS

### 1. Запуск MySQL в Docker

```bash
# Запуск MySQL контейнера
docker-compose up -d mysql

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs mysql
```

### 2. Настройка окружения

```bash
# Скопировать конфигурацию для Docker
cp docker.env .env

# Или установить переменные окружения
export DB_TYPE=mysql
export MYSQL_HOST=localhost
export MYSQL_DATABASE=content_fabric
export MYSQL_USER=content_fabric_user
export MYSQL_PASSWORD=mysqlpassword
```

### 3. Установка зависимостей

```bash
pip install mysql-connector-python
```

### 4. Настройка базы данных

```bash
# Создание схемы (автоматически при запуске контейнера)
python setup_mysql.py --config mysql_config.yaml

# Или миграция данных
python migrate_to_mysql.py \
  --sqlite-path youtube_channels.db \
  --mysql-host localhost \
  --mysql-database content_fabric \
  --mysql-user content_fabric_user \
  --mysql-password mysqlpassword
```

### 5. Проверка работы

```bash
# Тест подключения
python setup_mysql.py --config mysql_config.yaml --test-only

# Просмотр каналов
python youtube_mysql_manager.py --config mysql_config.yaml list
```

## Управление Docker контейнерами

### Основные команды

```bash
# Запуск всех сервисов
docker-compose up -d

# Запуск только MySQL
docker-compose up -d mysql

# Остановка
docker-compose down

# Перезапуск
docker-compose restart mysql

# Просмотр логов
docker-compose logs -f mysql

# Подключение к MySQL в контейнере
docker-compose exec mysql mysql -u content_fabric_user -p content_fabric
```

### Резервное копирование

```bash
# Создание дампа
docker-compose exec mysql mysqldump -u content_fabric_user -p content_fabric > backup.sql

# Восстановление
docker-compose exec -T mysql mysql -u content_fabric_user -p content_fabric < backup.sql
```

## phpMyAdmin (опционально)

Если запустили phpMyAdmin:

```bash
# Запуск с phpMyAdmin
docker-compose up -d

# Доступ к phpMyAdmin
open http://localhost:8080
# Логин: content_fabric_user
# Пароль: mysqlpassword
```

## Остановка и очистка

```bash
# Остановка контейнеров
docker-compose down

# Удаление контейнеров и томов
docker-compose down -v

# Удаление образов
docker-compose down --rmi all
```

## Преимущества Docker подхода

✅ **Одинаковая среда** - MySQL работает одинаково на macOS и Linux  
✅ **Быстрая настройка** - один `docker-compose up -d`  
✅ **Изоляция** - не засоряет систему  
✅ **Портабельность** - легко перенести на другой сервер  
✅ **Версионирование** - фиксированная версия MySQL  

## Отладка

### Проблемы с подключением

```bash
# Проверка статуса контейнера
docker-compose ps

# Проверка логов
docker-compose logs mysql

# Проверка портов
netstat -an | grep 3306

# Тест подключения
telnet localhost 3306
```

### Сброс базы данных

```bash
# Остановка и удаление данных
docker-compose down -v

# Запуск с чистой базой
docker-compose up -d mysql
```
