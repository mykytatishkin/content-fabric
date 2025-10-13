# 📚 Content Fabric - Project Overview

> Комплексная система автоматической публикации контента с продвинутой обработкой голоса

**Последнее обновление**: 2025-10-13  
**Версия**: 2.0 (с Voice Processing)  
**Статус**: ✅ Production Ready

---

## 🎯 Что это?

**Content Fabric** - это Python-based платформа для:
1. 🎬 **Автоматической публикации** в социальные сети (YouTube Shorts, Instagram Reels, TikTok)
2. 🎙️ **Изменения голоса** в видео/аудио (RVC, Silero TTS, SoVITS)
3. 📋 **Управления задачами** через MySQL-based систему
4. 👥 **Работы с множественными аккаунтами** на каждой платформе

## ⚡ Quick Links

| Что нужно | Куда идти |
|-----------|-----------|
| 🚀 Быстрые команды | [quick-reference.md](quick-reference.md) |
| 📖 Контекст проекта | [context.md](context.md) |
| 🏗️ Архитектура | [architecture.md](architecture.md) |
| 📋 Правила разработки | [rules](rules) |
| 📁 Навигация | [INDEX.md](INDEX.md) |
| 📝 Описание проекта | [project_description.md](project_description.md) |
| 🔧 Правила работы | [work_rules.md](work_rules.md) |

## 🔥 Главные возможности

### 1. Voice Processing System 🎙️ (NEW!)
**Что**: Изменение голоса в аудио/видео с сохранением фоновой музыки

**Методы**:
- **Silero TTS**: Быстрый, качественный русский голос
- **RVC**: Высокое качество voice conversion
- **SoVITS**: Баланс качества и скорости

**Пресеты**:
- `male_to_female` - Мужской → Женский
- `female_to_male` - Женский → Мужской  
- `male_to_child` - Мужской → Детский
- `female_to_child` - Женский → Детский
- `elderly`, `robot`, `cartoon` и др.

**Ключевые фичи**:
- ✅ Параллельная обработка (2-4x ускорение)
- ✅ Сохранение фоновой музыки
- ✅ Правильное ударение (русский язык)
- ✅ Batch processing

**Пример**:
```bash
python run_voice_changer.py input.mp3 output.mp3 \
    --type male_to_female \
    --preserve-background \
    --parallel
```

### 2. Task Management System 📋 (NEW!)
**Что**: MySQL-based система управления задачами публикации

**Возможности**:
- ✅ Создание задач через CLI
- ✅ Планирование по расписанию
- ✅ Автоматические повторы
- ✅ Отслеживание статусов
- ✅ Background worker daemon

**Пример**:
```bash
# Создать задачу
python run_task_manager.py create \
    --account "Channel Name" \
    --video video.mp4 \
    --title "Title" \
    --schedule "2025-12-25 18:00:00"

# Запустить worker
python run_task_worker.py
```

### 3. Social Media Automation 🌐
**Что**: Автоматическая публикация на платформы

**Платформы**:
- YouTube Shorts (полная поддержка)
- Instagram Reels (в разработке)
- TikTok (в разработке)

**Возможности**:
- ✅ OAuth 2.0 авторизация
- ✅ Автоматическое обновление токенов
- ✅ Rate limiting и retry logic
- ✅ Множественные аккаунты
- ✅ Telegram/Email уведомления

### 4. Multi-Account Management 👥
**Что**: Управление неограниченным количеством аккаунтов

**Возможности**:
- ✅ SQLite для YouTube каналов
- ✅ MySQL для задач и загрузок
- ✅ CLI для управления
- ✅ Token management
- ✅ Auto-refresh tokens

## 🏗️ Архитектура

### Трехслойная архитектура

```
┌─────────────────────────────┐
│   Application Layer         │  ← app/ (main, auto_poster, scheduler)
├─────────────────────────────┤
│   Core Layer                │  ← core/ (api_clients, auth, database, utils)
├─────────────────────────────┤
│   Infrastructure Layer      │  ← scripts/ (CLI tools, managers)
└─────────────────────────────┘
```

### Ключевые компоненты

| Компонент | Путь | Назначение |
|-----------|------|------------|
| **VoiceChanger** | `core/utils/voice_changer.py` | Главная система изменения голоса |
| **ParallelVoiceProcessor** | `core/utils/parallel_voice_processor.py` | Параллельная обработка |
| **AudioBackgroundMixer** | `core/utils/audio_background_mixer.py` | Сохранение фона |
| **YouTubeMySQLDatabase** | `core/database/mysql_db.py` | Task management |
| **YouTubeClient** | `core/api_clients/youtube_client.py` | YouTube API |
| **OAuthManager** | `core/auth/oauth_manager.py` | OAuth flow |
| **TokenManager** | `core/auth/token_manager.py` | Token storage |
| **TaskWorker** | `app/task_worker.py` | Background processor |

## 📊 Текущий статус

### ✅ Полностью реализовано
- [x] Voice Changer (Silero, RVC, SoVITS)
- [x] Parallel Voice Processing (2-4x speedup)
- [x] Background Music Preservation
- [x] Task Management System (MySQL)
- [x] YouTube Integration (Data API v3)
- [x] Multi-account support
- [x] OAuth & Token Management
- [x] CLI Tools
- [x] Telegram/Email Notifications
- [x] Upload Tracking
- [x] Russian Stress Marking

### 🚧 В процессе
- [ ] Instagram Reels integration
- [ ] TikTok integration
- [ ] Web UI для task management
- [ ] REST API
- [ ] Advanced analytics

### 🎯 Ближайшие планы
- [ ] Batch processing UI
- [ ] Дополнительные RVC модели
- [ ] Content optimization pipeline
- [ ] A/B testing для контента

## 🚀 Quick Start

### Для разработчика
```bash
# 1. Прочитать
.cursor/README.md         # Начни здесь
.cursor/context.md        # Понять проект
.cursor/quick-reference.md # Команды и примеры

# 2. Запустить
python run_voice_changer.py --help
python run_task_manager.py --help
python run_youtube_manager.py --help
```

### Для AI ассистента
```bash
# Порядок чтения файлов:
1. .cursor/rules              # Правила разработки
2. .cursor/context.md         # Общий контекст
3. .cursor/architecture.md    # Техническая архитектура
4. .cursor/quick-reference.md # Примеры и паттерны
```

## 🔍 Навигация по документации

### По типу задачи

**Voice Processing**:
1. [rules](rules) → Voice Changer System
2. [quick-reference.md](quick-reference.md) → Voice Processing Examples
3. [architecture.md](architecture.md) → Voice Processing Pipeline

**Task Management**:
1. [rules](rules) → Task Management
2. [quick-reference.md](quick-reference.md) → Task Management Examples
3. [architecture.md](architecture.md) → Task Publishing Pipeline

**YouTube Integration**:
1. [rules](rules) → API Clients
2. [quick-reference.md](quick-reference.md) → YouTube Management
3. [architecture.md](architecture.md) → YouTube API Integration

**Database**:
1. [rules](rules) → Database Layer
2. [quick-reference.md](quick-reference.md) → Database Operations
3. [architecture.md](architecture.md) → Database Schema

### По уровню детализации

| Уровень | Файл | Когда читать |
|---------|------|--------------|
| 🔍 Quick Lookup | [quick-reference.md](quick-reference.md) | Нужна команда/пример |
| 📖 Overview | [context.md](context.md) | Понять что и как |
| 🏗️ Deep Dive | [architecture.md](architecture.md) | Детальное понимание |
| 📋 Guidelines | [rules](rules) | Как делать правильно |

## 📈 Performance Metrics

### Voice Processing
- **Sequential**: ~30s per minute of audio
- **Parallel (5min chunks)**: ~10-15s per minute
- **Speedup**: 2-4x depending on CPU cores

### API Quotas
- **YouTube**: 10,000 units/day (free tier)
  - Upload: 1,600 units (~6/day)
- **Instagram**: ~200 API calls/hour
- **TikTok**: ~100 posts/day

### Database
- **MySQL**: 1000+ tasks/second
- **SQLite**: 100+ channels
- **Worker**: 1 task per 5-10s

## 🛠️ Tech Stack

### Core
- Python 3.10+
- PyTorch, TorchAudio
- MySQL, SQLite

### Voice Processing
- Silero TTS
- RVC, SoVITS
- Whisper (transcription)
- audio-separator (MDX-Net)
- librosa, soundfile

### APIs & Integrations
- YouTube Data API v3
- Instagram Graph API
- TikTok Content API
- Telegram Bot API

## 📝 Code Examples

### Voice Processing
```python
from core.utils.voice_changer import VoiceChanger

changer = VoiceChanger(enable_parallel=True)
result = changer.process_file(
    'input.mp3', 'output.mp3',
    method='silero',
    voice_model='kseniya',
    preserve_background=True
)
changer.cleanup()
```

### Task Management
```python
from core.database.mysql_db import YouTubeMySQLDatabase

db = YouTubeMySQLDatabase()
task_id = db.create_task(
    account_name='Channel',
    video_path='video.mp4',
    title='Title',
    scheduled_time=datetime(2025, 12, 25, 18, 0)
)
```

### YouTube Upload
```python
from core.api_clients.youtube_client import YouTubeClient

client = YouTubeClient('Channel Name')
result = client.upload_video(
    video_path='video.mp4',
    title='Title',
    description='Description',
    keywords=['shorts', 'viral']
)
```

## 🔐 Security & Best Practices

### Security
- ✅ Все секреты в `.env`
- ✅ Токены в БД (TODO: encryption)
- ✅ Валидация всех входных данных
- ✅ Безопасное логирование (без секретов)

### Development
- ✅ Type hints везде
- ✅ Google-style docstrings
- ✅ PEP 8 compliance
- ✅ Comprehensive error handling
- ✅ Cleanup resources

### Testing
- ✅ Unit tests
- ✅ Integration tests
- ✅ Real file testing
- ✅ Performance profiling

## 📚 Documentation Structure

```
.cursor/
├── OVERVIEW.md          # ← YOU ARE HERE (главный обзор)
├── INDEX.md             # Навигация
├── README.md            # О .cursor директории
├── rules                # Правила разработки
├── context.md           # Контекст проекта
├── architecture.md      # Техническая архитектура
├── quick-reference.md   # Быстрый справочник
├── project_description.md # Описание проекта
└── work_rules.md        # Правила работы
```

## 🎯 Next Steps

### Для нового разработчика
1. Прочитать этот OVERVIEW (5 мин)
2. Изучить [context.md](context.md) (15 мин)
3. Просмотреть [quick-reference.md](quick-reference.md) (10 мин)
4. Запустить примеры (30 мин)
5. Изучить [rules](rules) (20 мин)

### Для AI ассистента
1. Загрузить [rules](rules)
2. Понять [context.md](context.md)
3. Изучить [architecture.md](architecture.md)
4. Использовать [quick-reference.md](quick-reference.md) как шаблоны

### Для добавления новой функции
1. Проверить [rules](rules) → соглашения
2. Посмотреть [architecture.md](architecture.md) → куда добавить
3. Использовать [quick-reference.md](quick-reference.md) → паттерны
4. Обновить [context.md](context.md) → текущее состояние

## 📞 Support & Resources

### Документация
- **Полная документация**: `docs/` директория
- **Voice Changer**: `docs/VOICE_CHANGER.md`
- **Parallel Processing**: `docs/parallel/`
- **Task Management**: `docs/guides/TASK_MANAGEMENT.md`
- **YouTube Setup**: `docs/guides/YOUTUBE_SETUP.md`

### Примеры
- `examples/voice_changer_example.py`
- `examples/russian_stress_example.py`
- `test_*.py` файлы

### Команды
```bash
# Voice
python run_voice_changer.py --help

# Tasks
python run_task_manager.py --help

# YouTube
python run_youtube_manager.py --help

# Database
python run_setup_database.py
```

---

**🎉 Ready to start? Начни с [quick-reference.md](quick-reference.md) для быстрых команд!**

**📖 Want to understand? Read [context.md](context.md) для полного понимания!**

**🏗️ Deep technical? Dive into [architecture.md](architecture.md)!**

---

**Version**: 2.0  
**Last Updated**: 2025-10-13  
**Branch**: speed-up-voice-change  
**Status**: ✅ Production Ready with Voice Processing

