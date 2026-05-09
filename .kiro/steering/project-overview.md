---
inclusion: always
---

# Content Fabric (CFF) — Обзор проекта

Last updated: 2026-05-09

## Что это

Content Fabric — внутренняя production-платформа для автоматизации полного цикла YouTube-контента. Управляет 39 каналами, 9 live-стримами, 7 DLE-источниками контента.

**Сервер:** 46.21.250.43 (ZOMRO), Ubuntu 22.04, Xeon E5-2430v2, 32GB RAM, Quadro P2000
**Домен:** `aiyoutube.pbnbots.com` → nginx (HTTPS) → uvicorn :8000
**Репо на сервере:** `/opt/content-fabric/`

---

## Hard rule — coexistence with tg-app

**tg-app — отдельное приложение на этом хосте. НЕ модифицировать его контейнеры (`tg-app-postgres`, `tg-app-redis`), процессы (`ngrok http 5173`, `Xvfb`, `Xtigervnc`), файлы. См. memory feedback_tg_app.md.**

CFF использует свой Redis на `localhost:6379` и MySQL — пересечений с tg-app быть не должно. Любые операции `docker stop`, `systemctl stop`, `pkill` фильтруют только по префиксу `cff-*` / `stream-*`.

---

## Текущий статус (май 2026)

Cutover завершён. Yii2 декомиссионирован. Весь pipeline крутится в CFF.

- Ветка по умолчанию: `main` (текущая рабочая — `feat/yii-integration`, ожидает мержа)
- Legacy Yii-код архивирован локально в `.legacy/yii/` (gitignored), на сервере /var/www удалён
- 7 DLE source-баз продолжают существовать как внешние MySQL — CFF читает их напрямую через `shared/ingestion/dle/`

### Что крутится в проде

- FastAPI: API + Web Portal + Admin Panel (`prod/main.py`)
- Scheduler → Redis → 9 RQ workers → YouTube
- Observability: Prometheus + Grafana + GlitchTip + Pushgateway, дашборды по сервисам и security
- Security hardening (май 2026): CSRF middleware, JWT secret 32B, CSP+HSTS, /metrics за nginx auth, admin-only API на streams/dle-sources/logs, auditd, rkhunter baseline
- 221 тест в `prod/tests/`, все проходят

### Workers (9 очередей RQ)

| systemd unit | queue | назначение |
|--------------|-------|-----------|
| cff-publishing-worker | `publishing` | YouTube upload |
| cff-notification-worker | `notifications` | Telegram/email |
| cff-voice-worker | `voice` | RVC/Silero voice change |
| cff-dle-ingestion-worker | `dle_ingestion` | парсинг 7 DLE-сайтов → создание задач |
| cff-dle-processor-worker | `dle_processing` | скачивание + voice + рендер видео |
| cff-shorts-worker | `shorts` | yt-dlp + Whisper + GPT highlights → ffmpeg |
| cff-sora-worker | `sora` | Sora AI scraping через zenrows |
| cff-stats-worker | `stats` | daily YouTube channel statistics |
| cff-stream-control-worker | `stream_control` | start/stop/restart 9× ffmpeg-стримов |

Live-стримы — отдельные systemd-сервисы `stream-*.service` (RTMP loop через ffmpeg), управляются через CFF.

---

## Архитектура

```
Browser/API Client
      ↓ HTTPS
Nginx :443 → uvicorn :8000 (FastAPI)
      ↓
  ┌──────────────────────────────────────────┐
  │  /api/v1/*  — REST API (Bearer or cookie)│
  │  /app/*     — User Portal (cookie SSR)   │
  │  /panel/*   — Admin Panel (cookie SSR)   │
  │  /metrics   — Prometheus (nginx-gated)   │
  │  /health    — JSON (full only for admin) │
  └──────────────────────────────────────────┘
      ↓
MySQL (content_fabric) + Redis :6379
      ↓
Scheduler (60s poll) + 9 RQ workers (см. таблицу выше)
      ↓
9× stream-*.service — ffmpeg RTMP loops (systemd)
```

Middleware order (см. `prod/main.py:197-200`):
`SlowAPI → SecurityHeaders → CSRF → TraceContext → CORS`.
Outer middleware sees innermost ContextVars only after Starlette unwinds, поэтому `trace_id` ставится и логгируется в одном `TraceContextMiddleware`.

---

## Структура кода

```
prod/
├── main.py                    — FastAPI app + middleware stack
├── app/
│   ├── api/endpoints/         — channels, tasks, templates, uploads,
│   │                            streams, dle_sources, logs, admin, auth
│   ├── views/                 — app_portal.py + panel.py (Jinja2 SSR)
│   ├── templates/             — *.html (см. portal-views.md)
│   ├── core/                  — config, auth (cookie), security (JWT, bcrypt)
│   └── schemas/               — Pydantic v2
├── shared/
│   ├── db/                    — connection, models, repositories, utils
│   ├── ingestion/dle/         — client, processor, xfields_parser, pipeline
│   ├── shorts/                — downloader, transcriber, highlight, cutter
│   ├── streams/               — systemd_manager, provisioner
│   ├── voice/                 — RVC, Silero, mixer, prosody
│   ├── youtube/               — client, upload, token_refresh, reauth/
│   ├── notifications/         — telegram, email, manager
│   ├── queue/                 — publisher, config, types
│   ├── sora/                  — scraper
│   ├── metrics.py             — Prometheus + push helpers + @instrument_job
│   ├── logging_context.py     — trace_id ContextVars
│   └── error_tracking.py      — Sentry/GlitchTip init
├── workers/                   — 9 rq worker entry points + _job_bootstrap.py
├── scheduler/                 — 60s polling loop
├── cli/                       — reauth, voice CLI tools
└── tests/                     — 221 pytest tests
```

---

## Ключевые конфиги

- `.env` в корне проекта — MySQL, Redis, JWT, Telegram, ENV
- `prod/.env/.env.db` — MySQL credentials
- `prod/.env/.env.api` — YouTube API keys
- `prod/.env/.env.dle` — DSN для 7 DLE баз (источники контента)
- `HTTPS_ENABLED=true` в проде — управляет `Secure` флагом cookie

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
| Pushgateway :9091 | Метрики short-lived RQ jobs |
| Prometheus / Grafana / GlitchTip | Observability |

---

## Команды

```bash
# Тесты
cd prod && python -m pytest tests/ -v --tb=short    # 221 tests

# Reauth канала
python -m cli.reauth --channel-id 9

# Сервисы
systemctl status cff-api cff-scheduler cff-publishing-worker
systemctl status 'cff-*-worker'

# Стримы
systemctl status 'stream-*.service'
```
