---
inclusion: always
---

# Content Fabric (CFF) — Обзор проекта

## Что это

Content Fabric — внутренняя production-платформа для автоматизации полного цикла YouTube-контента. Управляет 39 каналами, 9 live-стримами, 7 DLE-источниками контента.

**Сервер:** 46.21.250.43 (ZOMRO), Ubuntu 22.04, Xeon E5-2430v2, 32GB RAM, Quadro P2000  
**Домен:** aiyoutube.pbnbots.com → nginx → uvicorn :8000  
**Репо:** `/opt/content-fabric/` на сервере

---

## Текущий статус (май 2026)

**Ветка:** `feat/yii-integration`  
**Этап:** Готово к weekend cutover — Yii2 полностью интегрирован в CFF, ждём переключения.

### Что уже работает в CFF
- FastAPI приложение (API + Web Portal + Admin Panel)
- Publishing pipeline: Scheduler → Redis → Worker → YouTube
- 39 каналов, OAuth токены, авто-рефреш
- 9 live-стримов через systemd + ffmpeg
- DLE ingestion worker (7 источников → CFF tasks)
- Shorts worker (yt-dlp → Whisper → GPT → ffmpeg → task)
- Stats worker (ежедневная статистика каналов)
- Stream control worker (start/stop/restart через systemd)
- Voice worker (RVC/Silero)
- 204 теста, все проходят

### Что ещё работает через Yii2 (legacy, будет отключено)
- Crontab: 5 задач (ночной upload, shorts, stats)
- PHP контроллеры для каждого DLE-сайта
- Shell-скрипты запуска

---

## Архитектура

```
Browser/API Client
      ↓
Nginx :80 → uvicorn :8000 (FastAPI)
      ↓
  ┌─────────────────────────────────┐
  │  /api/v1/*  — REST API (JWT)    │
  │  /app/*     — Web Portal (cookie)│
  │  /panel/*   — Admin Panel       │
  └─────────────────────────────────┘
      ↓
MySQL (content_fabric) + Redis
      ↓
Background Workers (systemd):
  cff-scheduler          — polls DB every 60s, enqueues tasks
  cff-publishing-worker  — YouTube upload via rq
  cff-notification-worker — Telegram/email
  cff-voice-worker       — RVC/Silero voice processing
  cff-dle-ingestion-worker — DLE → CFF tasks
  cff-shorts-worker      — yt-dlp → Whisper → GPT → shorts
  cff-stats-worker       — YouTube channel stats
  cff-stream-control-worker — systemd stream management
  9× stream-*.service    — ffmpeg RTMP loops
```

---

## Структура кода

```
prod/
├── main.py                    — FastAPI app entry point
├── app/
│   ├── api/endpoints/         — REST API handlers
│   ├── views/
│   │   ├── app_portal.py      — User portal (SSR, 1000+ lines)
│   │   └── panel.py           — Admin panel
│   ├── templates/             — Jinja2 HTML
│   ├── core/
│   │   ├── config.py          — Settings + dle_settings
│   │   ├── auth.py            — Cookie auth (require_user/require_admin)
│   │   ├── database.py        — DB init
│   │   └── security.py        — bcrypt, JWT
│   └── schemas/               — Pydantic v2 models
├── shared/
│   ├── db/
│   │   ├── connection.py      — get_connection() context manager
│   │   ├── models.py          — SQLAlchemy Core Table definitions
│   │   ├── repositories/      — task_repo, channel_repo, console_repo, etc.
│   │   └── utils.py           — serialize_json, build_update, etc.
│   ├── ingestion/dle/         — DLE pipeline (client, processor, xfields_parser)
│   ├── shorts/                — downloader, transcriber, highlight, cutter, thumbnail
│   ├── streams/               — systemd_manager, provisioner
│   ├── voice/                 — RVC, Silero, mixer, prosody
│   ├── youtube/               — client, upload, token_refresh, reauth/
│   ├── notifications/         — telegram, email, manager
│   ├── queue/                 — publisher, config, types
│   └── sora/                  — scraper
├── workers/                   — rq worker entry points
├── scheduler/                 — 60s polling loop
├── cli/                       — reauth, voice CLI tools
└── tests/                     — 204 pytest tests
```

---

## Ключевые конфиги

- `.env` в корне проекта — MySQL, Redis, JWT, Telegram
- `prod/.env/.env.db` — MySQL credentials
- `prod/.env/.env.api` — YouTube API keys
- `prod/.env/.env.dle` — DSN для 7 DLE баз (создать перед cutover!)
- `prod/.env/.env.api.new` / `.env.dle.new` — шаблоны новых env файлов

---

## Внешние зависимости

| Сервис | Назначение |
|--------|-----------|
| YouTube Data API v3 | Upload, metadata, stats |
| Google OAuth 2.0 | Channel authorization |
| OpenAI GPT-4 / Whisper | Shorts highlights, title generation |
| Telegram Bot API | Notifications |
| Gmail SMTP | Email notifications |
| 7× DLE MySQL серверов | Контент-источники (аудиокниги, книги) |
| Zenrows Proxy | Sora AI scraping |

---

## Команды

```bash
# Запуск тестов
cd prod && python -m pytest tests/ -v --tb=short

# Сравнение данных Yii ↔ CFF
python3 -m scripts.compare_yii_cff_data

# Reauth канала
python -m cli.reauth --channel-id 9

# Проверка сервисов
systemctl status cff-api cff-scheduler cff-publishing-worker
```
