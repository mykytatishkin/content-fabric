# Локальная разработка (dev-test-env)

Инструкция по настройке локальной базы данных для разработки.

## Что нужно установить

- Docker Desktop (скачать: https://www.docker.com/products/docker-desktop)
- Python 3.10 или новее
- SSH доступ к продакшн серверу (для копирования данных)

---

## Быстрый старт (4 шага)

### Шаг 1. Запустить Docker

Открыть терминал и выполнить:

```bash
cd content-fabric/docker
docker-compose up -d
```

После этого запустятся:
- **MySQL** - база данных на `localhost:3306`
- **phpMyAdmin** - веб-интерфейс на `http://localhost:8080`

Подождать 30 секунд пока MySQL загрузится.

### Шаг 2. Скопировать данные с продакшна

```bash
python scripts/migrate_prod_to_local.py
```

Скрипт автоматически:
1. Подключится к продакшн серверу по SSH
2. Сделает дамп базы данных
3. Загрузит дамп в локальный Docker MySQL
4. Проверит что все данные на месте

### Шаг 3. Настроить приложение

```bash
# Сохранить продакшн настройки (на всякий случай)
cp .env .env.prod.backup

# Использовать локальные настройки
cp .env.local .env
```

Или вручную отредактировать файл `.env`:
```
DB_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=content_fabric
MYSQL_USER=dev_user
MYSQL_PASSWORD=dev_pass
```

### Шаг 4. Запустить приложение

```bash
# Запустить воркер задач
python run_task_worker.py

# Или посмотреть статистику
python run_task_manager.py stats
```

---

## Данные для подключения

| Сервис | Адрес | Логин | Пароль |
|--------|-------|-------|--------|
| MySQL | localhost:3306 | dev_user | dev_pass |
| phpMyAdmin | http://localhost:8080 | dev_user | dev_pass |

---

## Команды Docker

```bash
# Запустить контейнеры
cd docker && docker-compose up -d

# Остановить контейнеры
docker-compose down

# Посмотреть логи MySQL
docker-compose logs -f mysql

# Проверить статус
docker-compose ps

# Полный сброс (удалить все данные и начать заново)
docker-compose down -v
docker-compose up -d
```

---

## Варианты миграции

```bash
# Полная миграция (скачать + загрузить)
python scripts/migrate_prod_to_local.py

# Только скачать дамп (без загрузки)
python scripts/migrate_prod_to_local.py --backup-only

# Только загрузить (из существующего дампа)
python scripts/migrate_prod_to_local.py --restore-only

# Только проверить данные
python scripts/migrate_prod_to_local.py --verify-only
```

---

## Переключение между окружениями

**Работать локально:**
```bash
cp .env.local .env
```

**Работать с продакшном:**
```bash
cp .env.prod.backup .env
```

---

## Решение проблем

### Docker не запускается

```bash
# Посмотреть что пошло не так
docker-compose logs mysql

# Сбросить и запустить заново
docker-compose down -v
docker-compose up -d
```

### Не могу подключиться к MySQL

```bash
# Проверить что контейнер работает
docker-compose ps

# Должен быть статус "healthy"
# Если нет - подождать 30 секунд

# Проверить подключение
docker exec dev-test-env-mysql mysql -u dev_user -pdev_pass -e "SELECT 1"
```

### Миграция не работает

```bash
# Проверить SSH подключение
ssh root@46.21.250.43 "echo OK"

# Если ошибка - проверить SSH ключи

# Проверить что дамп скачался
ls -la docker/init/production_dump.sql
```

---

## Структура файлов

```
content-fabric/
├── docker/
│   ├── docker-compose.yml       # Настройки Docker
│   ├── .env                     # Локальные пароли (не в git)
│   ├── .env.example             # Шаблон для .env
│   └── init/
│       └── production_dump.sql  # Дамп базы (не в git)
│
├── scripts/
│   └── migrate_prod_to_local.py # Скрипт миграции
│
├── .env                         # Активные настройки
├── .env.local                   # Шаблон для локальной работы
└── .env.prod.backup             # Бэкап продакшн настроек
```
