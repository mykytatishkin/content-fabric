# Content Fabric prod — микросервис управления каналами

## Структура prod

```
prod/
├── app/
│   ├── api/endpoints/    # REST endpoints (channels, items)
│   ├── core/             # config, database
│   ├── repositories/     # channel_repository
│   ├── schemas/          # Pydantic-модели
│   ├── services/         # youtube_validator
│   └── templates/        # add_channel.html
├── main.py
├── requirements.txt
├── migrations/           # SQL-миграции
└── nginx-content-fabric.conf.example
```

Микросервис для управления YouTube-каналами: REST API и веб-форма добавления. Использует общую MySQL БД с legacy, подготовлен к multi-tenancy.

## Реализованный функционал

| Компонент       | Описание                                                        |
| --------------- | --------------------------------------------------------------- |
| Channels API    | REST API для CRUD YouTube-каналов                               |
| Web-форма       | `/api/v1/channels/form` — форма добавления канала               |
| Валидация       | YouTube Data API v3 (channel_id, @handle), Latin-only для имени |
| Дубликаты       | Проверка по name и channel_id                                   |
| Google Consoles | Dropdown из таблицы `google_consoles` (связь с legacy)          |
| Multi-tenancy   | `user_id` (nullable) — миграция в `migrations/`                 |

## API endpoints

| Метод | Путь                         | Описание           |
| ----- | ---------------------------- | ------------------ |
| GET   | `/`                          | Информация и ссылки|
| GET   | `/health`                    | Health check       |
| GET   | `/api/v1/channels/`          | Список каналов     |
| GET   | `/api/v1/channels/form`      | Форма добавления   |
| POST  | `/api/v1/channels/`          | Создать канал      |
| GET   | `/api/v1/channels/{id}`      | Канал по ID        |
| GET   | `/api/v1/channels/google-consoles` | Список консолей    |

## Конфигурация

### prod/.env/.env.db

```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=content_fabric
MYSQL_USER=user
MYSQL_PASSWORD=secret
```

### prod/.env/.env.api

```
YOUTUBE_API_KEY=AIza...
```

`YOUTUBE_API_KEY` — ключ **YouTube Data API v3** (из Google Cloud Console → APIs & Services → Credentials → Create API key). Это не OAuth client_id/client_secret.

### Важно

Файлы `.env` в `.gitignore`. На сервере их нужно создать вручную или скопировать через `scp`.

## Запуск локально

```bash
cd prod
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
# Создать prod/.env/.env.db и prod/.env/.env.api
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

После запуска: http://127.0.0.1:8000/

## Запуск на сервере

```bash
cd /path/to/content-fabric/prod
source venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000
```

Для фонового запуска — `nohup` или systemd (см. [legacy/docs/SERVER_DEPLOYMENT_CHECKLIST.md](legacy/docs/SERVER_DEPLOYMENT_CHECKLIST.md)).

Nginx должен проксировать на `127.0.0.1:8000`. Инструкции: [NGINX_SETUP.md](NGINX_SETUP.md).

## Миграция БД

Добавление `user_id` для multi-tenancy:

```bash
mysql -u user -p content_fabric < prod/migrations/add_user_id_to_youtube_channels.sql
```

## Полезные ссылки

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **Форма добавления канала**: `/api/v1/channels/form`
