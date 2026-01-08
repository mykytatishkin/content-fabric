# Локальная разработка (dev-test-env)

Полностью локальная среда для разработки. Не нужен доступ к продакшн серверу.

## Что нужно

- Docker Desktop (скачать: https://www.docker.com/products/docker-desktop)
- Python 3.10+
- Дамп базы данных (файл `production_dump.sql`)

---

## Быстрый старт (3 шага)

### Шаг 1. Запустить Docker

```bash
cd content-fabric/docker
docker-compose up -d
```

Запустятся:
- **MySQL** на `localhost:3306`
- **phpMyAdmin** на `http://localhost:8080`

Подождать 30 секунд пока MySQL загрузится.

### Шаг 2. Загрузить данные

Положить файл `production_dump.sql` в папку `docker/init/`, затем:

```bash
python scripts/migrate_prod_to_local.py --restore-only
```

Это загрузит дамп в локальную базу.

### Шаг 3. Настроить приложение

```bash
cp .env.local .env
```

Или вручную в `.env`:
```
DB_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=content_fabric
MYSQL_USER=dev_user
MYSQL_PASSWORD=dev_pass
```

---

## Готово! Запускаем

```bash
# Воркер задач
python run_task_worker.py

# Статистика
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
# Запустить
cd docker && docker-compose up -d

# Остановить
docker-compose down

# Логи MySQL
docker-compose logs -f mysql

# Статус
docker-compose ps

# Полный сброс (удалить все данные)
docker-compose down -v
docker-compose up -d
```

---

## Варианты загрузки данных

```bash
# Загрузить из существующего дампа
python scripts/migrate_prod_to_local.py --restore-only

# Проверить данные
python scripts/migrate_prod_to_local.py --verify-only
```

---

## Решение проблем

### Docker не запускается

```bash
docker-compose logs mysql
docker-compose down -v
docker-compose up -d
```

### Не могу подключиться к MySQL

```bash
# Проверить статус (должен быть "healthy")
docker-compose ps

# Тест подключения
docker exec dev-test-env-mysql mysql -u dev_user -pdev_pass -e "SELECT 1"
```

---

## Структура файлов

```
content-fabric/
├── docker/
│   ├── docker-compose.yml       # Docker настройки
│   ├── .env                     # Локальные пароли (не в git)
│   └── init/
│       └── production_dump.sql  # Дамп базы (не в git)
│
├── scripts/
│   └── migrate_prod_to_local.py # Скрипт загрузки данных
│
└── .env                         # Настройки приложения
```
