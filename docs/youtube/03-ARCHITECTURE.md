# 📺 YouTube Automation - Архитектура системы

Подробное описание архитектуры YouTube автоматизации в Content Fabric.

---

## 📋 Содержание

1. [Обзор системы](#обзор-системы)
2. [Компоненты](#компоненты)
3. [База данных](#база-данных)
4. [OAuth Flow](#oauth-flow)
5. [Task Worker Integration](#task-worker-integration)
6. [Data Flow](#data-flow)

---

## 🏗️ Обзор системы

Content Fabric использует многоуровневую архитектуру для управления YouTube каналами:

```
┌─────────────────────────────────────────────────────────┐
│                    User / CLI                           │
└─────────────────────┬───────────────────────────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
    ▼                 ▼                 ▼
┌────────┐   ┌──────────────┐   ┌──────────────┐
│Account │   │  Main App    │   │ Task Worker  │
│Manager │   │  (main.py)   │   │              │
└────┬───┘   └──────┬───────┘   └──────┬───────┘
     │              │                   │
     └──────────────┼───────────────────┘
                    │
         ┌──────────┼──────────┐
         │                     │
         ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│  Database       │   │  OAuth Manager  │
│  (SQLite/MySQL) │   │                 │
└────────┬────────┘   └────────┬────────┘
         │                     │
         └──────────┬──────────┘
                    │
         ┌──────────┼──────────┐
         │                     │
         ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│ YouTube API     │   │ Google OAuth    │
│ (Data API v3)   │   │ (OAuth 2.0)     │
└─────────────────┘   └─────────────────┘
```

---

## 🧩 Компоненты

### 1. CLI Утилиты

#### account_manager.py
**Расположение:** `scripts/account_manager.py`

**Назначение:** Управление каналами через командную строку

**Импорты (актуальные):**
```python
from core.utils.database_config_loader import DatabaseConfigLoader
from core.auth.oauth_manager import OAuthManager
from core.database import get_database_by_type
```

**Основные функции:**
- `handle_add_channel()` - Добавление канала
- `handle_authorize()` - OAuth авторизация
- `handle_db_command()` - Работа с базой
- `handle_migrate()` - Миграция из config.yaml

#### run_youtube_manager.py
**Расположение:** `run_youtube_manager.py`

**Назначение:** Управление каналами с явным указанием credentials

**Импорты:**
```python
from core.database.sqlite_db import get_database_by_type, YouTubeChannel
```

---

### 2. Database Layer

#### SQLite Database
**Расположение:** `core/database/sqlite_db.py`

**Класс:** `YouTubeDatabase`

**Основные методы:**
```python
class YouTubeDatabase:
    def add_channel(name, channel_id, client_id, client_secret, enabled=True)
    def get_channel(name) -> Optional[YouTubeChannel]
    def get_all_channels(enabled_only=False) -> List[YouTubeChannel]
    def update_channel_tokens(name, access_token, refresh_token, expires_at)
    def is_token_expired(name) -> bool
    def enable_channel(name) -> bool
    def disable_channel(name) -> bool
    def delete_channel(name) -> bool
```

**Расположение БД:** `data/databases/youtube_channels.db`

#### MySQL Database
**Расположение:** `core/database/mysql_db.py`

**Класс:** `YouTubeMySQLDatabase`

**Аналогичные методы, но с MySQL backend**

**Конфигурация:** `config/mysql_config.yaml`

---

### 3. OAuth Manager

**Расположение:** `core/auth/oauth_manager.py`

**Класс:** `OAuthManager`

**Назначение:** Автоматическое получение и обновление OAuth токенов

**Основные методы:**
```python
class OAuthManager:
    def __init__(config_path, use_database=True)
    
    def get_authorization_url(platform, account_name, custom_scopes=None)
    def authorize_account(platform, account_name, auto_open_browser=True)
    def _exchange_code_for_token(platform, account_name, code, state)
    
    # Platform-specific
    def _get_youtube_auth_url(account_name, custom_scopes=None)
    def _exchange_youtube_code(account_name, code)
```

**OAuth Scopes для YouTube:**
```python
scopes = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.force-ssl'
]
```

---

### 4. YouTube API Client

#### YouTubeDBClient
**Расположение:** `core/api_clients/youtube_db_client.py`

**Класс:** `YouTubeDBClient(BaseAPIClient)`

**Назначение:** Интеграция с YouTube API + Database

**Основные методы:**
```python
class YouTubeDBClient(BaseAPIClient):
    def get_available_channels() -> List[str]
    def set_channel(channel_name) -> bool
    def post_to_channel(channel_name, video_path, title, description)
    def post_to_multiple_channels(channel_names, video_path, title, description)
    
    # Internal
    def _authenticate_for_channel() -> bool
    def _build_youtube_service() -> googleapiclient.discovery.Resource
```

**Наследование от BaseAPIClient:**
- Rate limiting
- Retry logic
- Error handling
- Logging

#### YouTubeClient (legacy)
**Расположение:** `core/api_clients/youtube_client.py`

**Используется для обратной совместимости**

---

### 5. Configuration Loader

**Расположение:** `core/utils/database_config_loader.py`

**Класс:** `DatabaseConfigLoader`

**Назначение:** Загрузка конфигурации из базы данных

**Основные методы:**
```python
class DatabaseConfigLoader:
    def load_config() -> dict
    def add_youtube_channel(name, channel_id, client_id=None, client_secret=None)
    def remove_youtube_channel(name) -> bool
    def update_channel_tokens(name, access_token, refresh_token, expires_at)
```

**Особенности:**
- Автоматически подставляет credentials из `.env` если не указаны
- Совместим с существующим ConfigLoader
- Поддерживает SQLite и MySQL

---

## 🗄️ База данных

### Схема SQLite/MySQL

#### Таблица: youtube_channels

```sql
CREATE TABLE youtube_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,           -- Уникальное имя канала
    channel_id TEXT NOT NULL,            -- YouTube Channel ID (@username или UC...)
    client_id TEXT NOT NULL,             -- OAuth Client ID
    client_secret TEXT NOT NULL,         -- OAuth Client Secret
    access_token TEXT,                   -- Access Token (обновляется каждый час)
    refresh_token TEXT,                  -- Refresh Token (бессрочный)
    token_expires_at TEXT,               -- Время истечения access token
    enabled BOOLEAN DEFAULT 1,           -- Включен ли канал
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### Структура данных

**YouTubeChannel (dataclass):**
```python
@dataclass
class YouTubeChannel:
    id: int
    name: str                           # "Мой Канал"
    channel_id: str                     # "@mychannel" или "UC123..."
    client_id: str                      # "123-abc.apps.googleusercontent.com"
    client_secret: str                  # "GOCSPX-xyz..."
    access_token: Optional[str]         # "ya29.a0..."
    refresh_token: Optional[str]        # "1//0g..."
    token_expires_at: Optional[datetime] # 2025-10-17 12:00:00
    enabled: bool                       # True/False
    created_at: Optional[datetime]      # 2025-10-01 10:00:00
    updated_at: Optional[datetime]      # 2025-10-16 11:30:00
```

### Индексы

```sql
CREATE UNIQUE INDEX idx_channel_name ON youtube_channels(name);
CREATE INDEX idx_channel_enabled ON youtube_channels(enabled);
CREATE INDEX idx_token_expires ON youtube_channels(token_expires_at);
```

---

## 🔐 OAuth Flow

### 1. Первичная авторизация

```
┌─────────┐      ┌──────────────┐      ┌───────────┐      ┌─────────┐
│   CLI   │      │ OAuthManager │      │  Browser  │      │ Google  │
└────┬────┘      └──────┬───────┘      └─────┬─────┘      └────┬────┘
     │                  │                    │                  │
     │ authorize()      │                    │                  │
     │─────────────────>│                    │                  │
     │                  │                    │                  │
     │              [Start HTTP Server       │                  │
     │               on port 8080]           │                  │
     │                  │                    │                  │
     │                  │ Open Auth URL      │                  │
     │                  │───────────────────>│                  │
     │                  │                    │                  │
     │                  │                    │ Navigate         │
     │                  │                    │─────────────────>│
     │                  │                    │                  │
     │                  │                    │   [User Login]   │
     │                  │                    │   [Grant Access] │
     │                  │                    │                  │
     │                  │                    │<─────────────────│
     │                  │  Callback          │   code=...       │
     │                  │<───────────────────│                  │
     │                  │                    │                  │
     │              [Exchange code           │                  │
     │               for tokens]             │                  │
     │                  │                    │                  │
     │                  │ POST /token        │                  │
     │                  │───────────────────────────────────────>│
     │                  │                    │                  │
     │                  │<───────────────────────────────────────│
     │                  │  access_token      │   refresh_token  │
     │                  │                    │                  │
     │              [Save tokens to DB]      │                  │
     │                  │                    │                  │
     │<─────────────────│                    │                  │
     │   Success        │                    │                  │
```

### 2. Автоматическое обновление токена

```
┌──────────────┐      ┌──────────┐      ┌─────────┐
│YouTubeClient │      │ Database │      │ Google  │
└──────┬───────┘      └─────┬────┘      └────┬────┘
       │                    │                 │
       │ upload_video()     │                 │
       │                    │                 │
   [Check token expiry]     │                 │
       │                    │                 │
       │ is_token_expired() │                 │
       │───────────────────>│                 │
       │<───────────────────│                 │
       │    YES             │                 │
       │                    │                 │
       │ get refresh_token  │                 │
       │───────────────────>│                 │
       │<───────────────────│                 │
       │                    │                 │
       │ POST /token (refresh)                │
       │─────────────────────────────────────>│
       │                                      │
       │<─────────────────────────────────────│
       │    new access_token                  │
       │                    │                 │
       │ update_tokens()    │                 │
       │───────────────────>│                 │
       │                    │                 │
   [Continue with upload]   │                 │
```

---

## 🔄 Task Worker Integration

### Схема работы с Task Worker

```
┌─────────┐     ┌──────────┐     ┌────────────┐     ┌──────────────┐
│   CLI   │────>│ Task DB  │<────│ TaskWorker │────>│YouTubeClient │
└─────────┘     └──────────┘     └────────────┘     └──────────────┘
                      │                                      │
                      │                                      │
                      └──────────────────────────────────────┘
                           MySQL Tasks Table
```

### Task Structure

**Таблица: tasks**
```sql
CREATE TABLE tasks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    platform VARCHAR(50),                -- 'youtube'
    account_name VARCHAR(255),           -- 'Мой Канал'
    video_path TEXT,                     -- 'data/content/videos/video.mp4'
    title VARCHAR(255),                  -- 'Заголовок'
    description TEXT,                    -- 'Описание #shorts'
    scheduled_time DATETIME,             -- Время публикации
    status VARCHAR(50),                  -- 'pending', 'processing', 'completed', 'failed'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at DATETIME,
    error_message TEXT,
    upload_id VARCHAR(255)               -- ID опубликованного видео
);
```

### Task Flow

1. **Создание задачи:**
```python
# app/main.py
task_id = task_manager.create_task(
    platform='youtube',
    account_name='Мой Канал',
    video_path='video.mp4',
    title='Заголовок',
    description='Описание',
    scheduled_time=datetime.now()
)
```

2. **Обработка задачи:**
```python
# app/task_worker.py
class TaskWorker:
    def process_task(task):
        # 1. Получить канал из БД
        channel = db.get_channel(task.account_name)
        
        # 2. Создать YouTube клиент
        client = YouTubeDBClient()
        client.set_channel(task.account_name)
        
        # 3. Загрузить видео
        result = client.upload_video(
            video_path=task.video_path,
            title=task.title,
            description=task.description
        )
        
        # 4. Обновить статус
        task_manager.update_task(
            task_id=task.id,
            status='completed',
            upload_id=result['id']
        )
```

---

## 📊 Data Flow

### Полный цикл публикации видео

```
┌────────────────────────────────────────────────────────────┐
│ 1. User Input                                              │
│    python app/main.py post --content video.mp4 ...        │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│ 2. Task Creation                                           │
│    - Validate video file                                   │
│    - Create task in MySQL                                  │
│    - Set status = 'pending'                                │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│ 3. Task Worker Pickup                                      │
│    - Worker polls for pending tasks                        │
│    - Finds task with status = 'pending'                    │
│    - Updates status = 'processing'                         │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│ 4. Channel Authentication                                  │
│    - Get channel from database                             │
│    - Check token expiry                                    │
│    - Refresh token if needed                               │
│    - Build YouTube API service                             │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│ 5. Video Upload                                            │
│    - Read video file                                       │
│    - Detect if Shorts (9:16 aspect ratio)                  │
│    - Add #Shorts hashtag                                   │
│    - Upload via YouTube Data API v3                        │
│    - Resumable upload for large files                      │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│ 6. Task Completion                                         │
│    - Update task status = 'completed'                      │
│    - Save upload_id (YouTube video ID)                     │
│    - Log success                                           │
│    - Send notification (if configured)                     │
└────────────────────────────────────────────────────────────┘
```

---

## 🧪 Testing Architecture

### Unit Tests

**Расположение:** `tests/`

```python
# test_youtube_db_client.py
def test_add_channel()
def test_authenticate()
def test_upload_video()
def test_token_refresh()
```

### Integration Tests

```python
# test_integration.py
def test_full_flow():
    # 1. Add channel
    # 2. Authorize
    # 3. Upload video
    # 4. Verify upload
```

---

## 📁 Структура файлов

```
content-fabric/
├── app/
│   ├── main.py                      # Точка входа
│   ├── task_worker.py               # Обработчик задач
│   └── scheduler.py                 # Планировщик
│
├── core/
│   ├── api_clients/
│   │   ├── base_client.py           # Базовый API клиент
│   │   ├── youtube_client.py        # Legacy YouTube клиент
│   │   └── youtube_db_client.py     # YouTube + Database клиент
│   │
│   ├── auth/
│   │   ├── oauth_manager.py         # OAuth автоматизация
│   │   └── token_manager.py         # Управление токенами
│   │
│   ├── database/
│   │   ├── sqlite_db.py             # SQLite реализация
│   │   ├── mysql_db.py              # MySQL реализация
│   │   └── __init__.py              # get_database_by_type()
│   │
│   └── utils/
│       ├── database_config_loader.py # Загрузка конфигурации
│       └── config_loader.py          # Legacy config loader
│
├── scripts/
│   ├── account_manager.py           # CLI для управления
│   └── youtube_manager.py           # CLI для базы
│
├── config/
│   ├── config.yaml                  # Основная конфигурация
│   └── mysql_config.yaml            # MySQL настройки
│
├── data/
│   └── databases/
│       └── youtube_channels.db      # SQLite база
│
└── credentials.json                 # OAuth credentials
```

---

## 🔒 Security Architecture

### 1. Хранение токенов

**SQLite:**
- База данных: `data/databases/youtube_channels.db`
- Права доступа: `600` (только владелец)
- Токены хранятся в plaintext (локальная база)

**MySQL:**
- База данных: удалённый сервер
- Соединение: SSL/TLS
- Токены хранятся в plaintext (защита на уровне БД)

### 2. OAuth Credentials

**credentials.json:**
- Права доступа: `600`
- Не коммитится в git (.gitignore)
- Содержит только Client ID и Secret (не токены)

**.env:**
- Права доступа: `600`
- Не коммитится в git
- Содержит credentials для всех сервисов

### 3. API Rate Limiting

**BaseAPIClient:**
```python
class BaseAPIClient:
    def _check_rate_limit(self):
        # Проверка лимитов
        pass
    
    def _retry_with_backoff(self, func, max_retries=3):
        # Exponential backoff
        pass
```

**YouTube Quota:**
- Дневной лимит: 10,000 units
- Upload cost: ~1600 units
- ~6 uploads в день на проект

---

## 📈 Scalability

### Horizontal Scaling

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ TaskWorker 1 │     │ TaskWorker 2 │     │ TaskWorker 3 │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                     ┌──────┴──────┐
                     │   MySQL     │
                     │   (Tasks)   │
                     └─────────────┘
```

### Vertical Scaling

- Увеличение MySQL connection pool
- Больше task workers
- Параллельная обработка видео

---

## 🎯 Best Practices

### 1. Database Access
```python
# ✅ Используйте context manager
with sqlite3.connect(db_path) as conn:
    cursor.execute(...)

# ✅ Используйте prepared statements
cursor.execute("SELECT * FROM channels WHERE name = ?", (name,))
```

### 2. Error Handling
```python
# ✅ Специфичные исключения
try:
    result = youtube_client.upload_video(...)
except QuotaExceededError:
    # Обработка превышения квоты
except AuthenticationError:
    # Обработка проблем с авторизацией
```

### 3. Logging
```python
# ✅ Структурированные логи
logger.info(f"Uploading video to channel '{channel_name}'", extra={
    'channel_id': channel.channel_id,
    'video_size': os.path.getsize(video_path),
    'scheduled_time': scheduled_time
})
```

---

## 📞 Дополнительная информация

- [Setup Guide](01-SETUP.md) - Первичная настройка
- [CLI Guide](02-CLI-GUIDE.md) - Использование CLI
- [Troubleshooting](04-TROUBLESHOOTING.md) - Решение проблем

---

**Предыдущий:** [← CLI Guide](02-CLI-GUIDE.md)  
**Следующий:** [Troubleshooting →](04-TROUBLESHOOTING.md)

