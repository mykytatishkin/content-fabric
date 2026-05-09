# Content Fabric — Production

Адресат: оператор / новый инженер. Сервер `46.21.250.43`, Ubuntu 22.04, kernel 5.15. Все команды запускаются под `root`.

---

## 1. Overview

Content Fabric (CFF) — сервис полного цикла управления YouTube-контентом: ingestion с DLE-источников, голосовая обработка (TTS / voice-change), сборка видео, заливка на YouTube, статистика, нарезка shorts, управление 9 непрерывными live-стримами. Прод развёрнут на одном хосте, FastAPI + 9 RQ-воркеров + scheduler, всё под systemd, наружу торчит только nginx (80/443) → `127.0.0.1:8000`.

Yii (`aiyoutube.pbnbots.com`) полностью **выведен из эксплуатации** (legacy, removed) — таблицы дропнуты миграцией `005_drop_yii_tables.sql`, код и cron-расписание перенесены в `prod/`.

---

## 2. Architecture

```
                          Internet
                              │
                              ▼
              ┌─────────────────────────────────┐
              │  nginx :80 (default_server) /   │
              │  :443 (aiyoutube.pbnbots.com)   │
              │  → proxy_pass 127.0.0.1:8000    │
              └────────────────┬────────────────┘
                               │
          ┌────────────────────▼─────────────────────┐
          │  cff-api  uvicorn FastAPI :8000          │
          │  middleware: SecurityHeaders, CSRF,      │
          │              TraceContext, SlowAPI,      │
          │              CORS                         │
          └─┬─────────────┬──────────────┬───────────┘
            │             │              │
       ┌────▼───┐    ┌────▼────┐    ┌────▼─────┐
       │ MySQL  │    │ Redis   │    │ scheduler│
       │ :3306  │    │ :6379   │    │ (60s loop│
       │ (local)│    │ (local) │    │  + Yii   │
       └────────┘    └────┬────┘    │  cron)   │
                          │         └──────────┘
                          ▼
       ┌──────────────────────────────────────────┐
       │  RQ workers (9):                          │
       │   publishing, voice, notification,        │
       │   dle-ingestion, dle-processor,           │
       │   shorts, stats, stream-control           │
       └──────────────────────────────────────────┘

       9× stream-*.service — отдельный пул systemd-юнитов
                              для непрерывных YouTube-трансляций
                              (управляется cff-stream-control-worker)

       Observability stack (docker-compose, 127.0.0.1):
         prometheus :9090, pushgateway :9091, loki :3100,
         grafana :3001, glitchtip :8001, node/process-exporter
```

Стек: Python 3.10, FastAPI, Pydantic v2, SQLAlchemy Core (без ORM), RQ + Redis, MySQL 8.x, nginx, systemd.

---

## 3. Services (systemd)

10 systemd-юнитов CFF, все определены в `prod/deploy/systemd/cff-*.service`. Установка — `prod/deploy/install-services.sh`. Все запускаются от `User=root`, `WorkingDirectory=/opt/content-fabric/prod`, читают `EnvironmentFile=/opt/content-fabric/.env`.

| Unit | Что делает | Очередь / триггер | Лог |
|------|-----------|-------------------|-----|
| `cff-api` | FastAPI/uvicorn на `127.0.0.1:8000` | HTTP | `/var/log/cff-api.log` + journal |
| `cff-scheduler` | Polling БД каждые 60с + cron-эмулятор Yii | таймер | `/var/log/cff-scheduler.log` + journal |
| `cff-publishing-worker` | Заливка видео на YouTube (resumable upload, лайк, коммент, миниатюра) | `publishing` | `/var/log/cff-publishing-worker.log` |
| `cff-voice-worker` | Voice-change / TTS обработка | `voice` | `/var/log/cff-voice-worker.log` |
| `cff-notification-worker` | Telegram / email уведомления | `notifications` | `/var/log/cff-notification-worker.log` |
| `cff-dle-ingestion-worker` | Парсинг постов с DLE-источников → создание задач | `dle_ingestion` | journal |
| `cff-dle-processor-worker` | Скачивание + voice + сборка видео для DLE | `dle_processing` | `/var/log/cff-dle-processor-worker.log` |
| `cff-shorts-worker` | Whisper-транскрипция + GPT-highlight + нарезка shorts | `shorts` | journal |
| `cff-stats-worker` | Сбор YouTube-статистики каналов и видео | `stats` | journal |
| `cff-stream-control-worker` | start/stop/restart 9 `stream-*.service` юнитов | `stream_control` | journal |

`StandardOutput=append:/var/log/cff-*.log` пишут в файл. `StandardOutput=journal` (ingestion, shorts, stats, stream-control) — только в journald (читается через `journalctl -u <unit>`).

Логи также собираются promtail'ом в Loki — см. секцию 6.

### Stream pool (9 units)

Параллельно живут 9 системных юнитов для непрерывного вещания:

```
stream-audiokniga-one.service       stream-knigaza30sekund.service
stream-bazaknig_net.service         stream-knigiaudiobiz.service
stream-chitaemvslux.service         stream-knizhnyeannotacii.service
stream-haha-smiley-funny.service    stream-Readbooks-online.service
stream-RelaxingHolidayLive.service
```

Управляются `cff-stream-control-worker` через `systemctl <action> <unit>` (см. `prod/workers/stream_worker.py:39-40`). Источник имён — таблица `live_stream_configurations`.

### Scheduler — что делает

`prod/scheduler/run.py` — главный цикл. Каждые 60 секунд:

1. `enqueue_pending_tasks()` — забирает из БД задачи со `status=0` и `scheduled_at <= NOW()`, маркирует как processing, кладёт в `publishing` или `voice` очередь (`scheduler/jobs.py:26-92`).
2. `run_periodic_yii_jobs()` — cron-эмулятор для DLE-расписания (бывший `shel_youtube*.sh`): видео-ingestion @02:00, shorts @14:15/16:15/21:15, slushat @17:15/20:15, shorts-from-video @13:20 (`scheduler/jobs.py:395-428`).
3. Раз в сутки — `validate_channel_tokens()` (refresh OAuth) и `collect_channel_stats()` + `collect_video_stats()` (YouTube Data API v3).

---

## 4. Endpoints

Корневой роутер монтируется так (`prod/main.py:269-271`):

```
/api/v1/*   — REST API (router из app/api/routes.py)
/panel/*    — старая внутренняя админка (Jinja templates)
/app/*      — портал для пользователей (Jinja templates)
```

### Public

| Path | Описание |
|------|----------|
| `GET /` | `{"message": "Content Fabric API", "status": "running"}` |
| `GET /health` | Базовый статус (mysql, redis, disk, queue depth). Для админа с cookie — полный JSON с latency, диском, памятью, uptime (`main.py:315-403`). |
| `GET /metrics` | Prometheus exposition. **Заблокирован nginx'ом** для всех IP кроме `127.0.0.1` (`deploy/nginx/content-fabric.conf:49-52`, `aiyoutube.pbnbots.com.conf:19-22`). Скрейп идёт локально. |
| `GET /favicon.ico`, `GET /robots.txt`, `/static/*` | Статика. |
| `GET /docs`, `GET /redoc`, `GET /openapi.json` | **Только в `ENV=development`** (`main.py:186-194`). В проде — 404. |

### `/api/v1/*` (роутеры подключаются в `app/api/routes.py`)

| Префикс | Tag | Auth |
|---------|-----|------|
| `/auth` | auth | `POST /login`, `POST /register` — public; `GET /me` — JWT |
| `/channels` | channels | mix |
| `/tasks` | tasks | JWT required |
| `/templates` | templates | JWT |
| `/admin` | admin | JWT + admin role |
| `/uploads` | uploads | JWT |
| `/streams` | streams | JWT (admin) |
| `/dle-sources` | dle-sources | JWT |
| `/logs` | logs | JWT — AI-friendly logs API (см. `OBSERVABILITY.md`) |

### Browser routes

`/panel/*` — старая админка (Jinja). `/app/*` — пользовательский портал. Оба используют cookie `cff_token` (а не Bearer).

---

## 5. Authentication & Security

### JWT

- Алгоритм `HS256`, секрет из `JWT_SECRET_KEY` (32-байтовый hex, ротирован 2026-05-09).
- Токен живёт 24 часа (`JWT_EXPIRE_MINUTES=1440`, `app/core/security.py:20`).
- Запуск падает, если `JWT_SECRET_KEY` не задан (`app/core/security.py:13-18`).
- Два способа отдать токен:
  - Cookie `cff_token` — для браузерных страниц `/app/*`, `/panel/*` (`app/core/auth.py:16`).
  - `Authorization: Bearer <jwt>` — для API/CLI/cron-клиентов.

### CSRF

`CSRFMiddleware` (`main.py:61-136`):
- Проверяет `Origin` (или `Referer` если Origin отсутствует) для **state-changing методов** (POST/PUT/DELETE/PATCH).
- **Skip** если: метод safe (GET/HEAD/OPTIONS), есть `Authorization: Bearer …`, нет cookie `cff_token`.
- Если `Origin`/`Referer` не совпадают с `Host` — 403 + лог в `cff.csrf`.
- Если оба заголовка отсутствуют для small-changing запроса — 403.

### Security headers (`SecurityHeadersMiddleware`, `main.py:30-58`)

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload   (2 года)
Content-Security-Policy:
  default-src 'self'; style-src 'self' 'unsafe-inline';
  script-src 'self' 'unsafe-inline'; img-src 'self' data: blob:;
  connect-src 'self'; object-src 'none'; base-uri 'self';
  form-action 'self'; frame-ancestors 'none';
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

`unsafe-eval` **снято** (нет runtime eval). `unsafe-inline` оставлен для inline `<style>`/`<script>` в Jinja-шаблонах. `frame-ancestors 'none'` перекрывает `X-Frame-Options` для современных браузеров.

### Rate limiting

`slowapi` через `Limiter(default_limits=["120/minute"])`, ключ — `get_remote_address` (`main.py:27`). При превышении — 429.

### Port lockdown (iptables)

Снаружи открыты только **22 / 80 / 443**. Mail (25/465/587/993/995), MySQL (3306), Postgres (5432), Redis (6379), FastPanel (8888), Zabbix (10050/10051) — DROP с не-localhost. Зафиксировано коммитом `049f140`.

### auditd

52 правила в `/etc/audit/rules.d/cff-security.rules` (источник — `prod/deploy/auditd/cff-security.rules`). Ватчат:
- Identity / sudoers / PAM / SSH config / SSH keys (`/root/.ssh/`).
- Cron (`/etc/cron*`, `/var/spool/cron/`) — после Redis-RCE инцидента в мае.
- Systemd unit-файлы, iptables, nginx config.
- CFF code: `main.py`, `app/core/security.py`, `app/api/deps.py`.
- Secrets: чтения и записи `/opt/content-fabric/.env`.
- Syscalls: `init_module/finit_module/delete_module` (rootkit), `adjtimex/settimeofday`, `mount`.

Логи → `/var/log/audit/audit.log` → promtail → Loki → дашборд `cff-security`. Лимит 500MB (`50MB × 10`, `auditd.conf`). Подробности и threat-model: `prod/deploy/auditd/README.md`.

---

## 6. Observability

Self-hosted, всё на `127.0.0.1`, доступ только через SSH-туннель. Контейнеры в `/opt/content-fabric/prod/deploy/observability/` (docker-compose).

| Компонент | Порт | Назначение |
|-----------|------|-----------|
| Prometheus | 9090 | TSDB, retention 30 дней |
| Pushgateway | 9091 | Метрики коротких RQ-job'ов |
| node-exporter | 9100 | CPU/RAM/диск (host net) |
| process-exporter | 9256 | Per-process для cff-* и ffmpeg |
| Loki | 3100 | Хранилище логов, 30 дней |
| Promtail | — | journalctl + `/var/log/cff-*.log` + `/var/log/audit/audit.log` + `/var/log/nginx/*` → Loki |
| Grafana | 3001 | UI + Alerting (10 правил) |
| GlitchTip | 8001 | Sentry-совместимый error tracking |

Дашборды: `cff-now`, `cff-system`, `cff-pipeline`, `cff-incidents`, `cff-trace`, `cff-security`.

Trace propagation: `X-Trace-Id` приходит/генерится в `TraceContextMiddleware` (`main.py:139-183`), кладётся в ContextVar, проходит через все воркеры через `bootstrap_job()` (`workers/_job_bootstrap.py`) и попадает в каждую строку лога. Для DLE-задач trace_id хранится также в `legacy_add_info` в БД.

Полный гид: [OBSERVABILITY.md](OBSERVABILITY.md). Auditd-секция: [prod/deploy/auditd/README.md](../prod/deploy/auditd/README.md).

---

## 7. Deployment

### Стандартный workflow

```bash
ssh root@46.21.250.43
cd /opt/content-fabric
git pull origin main

# Если поменялись deps:
cd prod && ./venv/bin/pip install -r requirements.txt && cd ..

# Перезапуск всего CFF:
systemctl restart 'cff-*.service'

# Или по одному:
systemctl restart cff-api
systemctl restart cff-publishing-worker
systemctl restart cff-scheduler
```

> **Старый `nohup uvicorn …` workflow удалён** (legacy, removed). Не использовать.

### Первая установка / переустановка systemd-юнитов

```bash
cd /opt/content-fabric/prod/deploy
bash install-services.sh
# скрипт копирует cff-*.service → /etc/systemd/system/, делает daemon-reload и enable
systemctl start cff-api cff-scheduler cff-publishing-worker \
                cff-notification-worker cff-voice-worker \
                cff-dle-ingestion-worker cff-dle-processor-worker \
                cff-shorts-worker cff-stats-worker \
                cff-stream-control-worker
```

### Конфиг

```
/opt/content-fabric/.env              # главный — JWT_SECRET_KEY, REDIS_URL, MYSQL_*, TELEGRAM_*, SENTRY_DSN
/opt/content-fabric/prod/.env         # опциональный override (EnvironmentFile=- в unit'ах)
/opt/content-fabric/prod/.env/.env.api  # YOUTUBE_API_KEY и т.п.
/opt/content-fabric/prod/.env/.env.db   # MySQL креды
```

### Logrotate

`prod/deploy/logrotate-cff` ставится в `/etc/logrotate.d/cff`:
- `/var/log/cff-*.log` — daily, 14 дней, gzip + copytruncate.
- `/var/log/cff-audit.log` — weekly, 52 недели.

### Nginx

Два конфига в `prod/deploy/nginx/`:
- `content-fabric.conf` — слушает `46.21.250.43:80` (default_server).
- `aiyoutube.pbnbots.com.conf` — `46.21.250.43:443` SSL (cert FastPanel) + 80→443 redirect, `client_max_body_size 10G`.

Оба прокидывают на `127.0.0.1:8000` и блокируют `/metrics` для всех IP кроме `127.0.0.1`.

---

## 8. Operations

### Статус и логи

```bash
# Статус всех CFF
systemctl status 'cff-*.service' --no-pager

# Live-лог конкретного сервиса
journalctl -u cff-api -f
journalctl -u cff-publishing-worker -f --since "10 min ago"

# Файловый лог (для тех юнитов, что пишут в файл)
tail -f /var/log/cff-api.log
tail -f /var/log/cff-dle-processor-worker.log

# Все CFF-логи разом
journalctl -u 'cff-*' -f
```

### Глубины очередей

```bash
redis-cli LLEN rq:queue:publishing
redis-cli LLEN rq:queue:voice
redis-cli LLEN rq:queue:dle_ingestion
redis-cli LLEN rq:queue:dle_processing
redis-cli LLEN rq:queue:shorts
redis-cli LLEN rq:queue:stats
redis-cli LLEN rq:queue:notifications
redis-cli LLEN rq:queue:failed
```

### Health checks

```bash
curl -s http://127.0.0.1:8000/health | jq .
# полный JSON только если cookie cff_token принадлежит админу

curl -s http://127.0.0.1:8000/api/v1/channels/   # 200 = API живой
```

### Stream pool

```bash
systemctl status 'stream-*.service' --no-pager
systemctl restart stream-bazaknig_net.service
# или через worker — поставить job в stream_control queue
```

### Тесты

```bash
cd /opt/content-fabric/prod
./venv/bin/python -m pytest tests/ -q
# 221 тест, все зелёные на Linux-сервере
```

### Troubleshooting pointers

| Симптом | Куда смотреть |
|---------|--------------|
| API не отвечает | `journalctl -u cff-api`, `curl 127.0.0.1:8000/health` |
| Задачи висят `status=0` | `cff-scheduler` логи + `redis-cli LLEN rq:queue:publishing` |
| Upload падает | `cff-publishing-worker` лог + `OAuth refresh` события + `cff_youtube_token_expires_in_seconds` метрика |
| 39% failure rate | Чаще всего OAuth-токены — `python -m cli.reauth --all-failed` |
| Высокая память voice-воркера | Лимит `MemoryMax=4G` в unit-файле, ML-модели не выгружаются между job'ами |
| auditd флудит | См. "Gotchas" в `prod/deploy/auditd/README.md` (особенно `data/streams/`) |
| Stream restart loop | Алерт `cff-stream-restart-loop` в Grafana, см. `journalctl -u stream-*` |

---

## 9. Database

MySQL 8.x, база `content_fabric`. Подключение через SQLAlchemy Core (без ORM) — `prod/shared/db/connection.py`. Модели — `prod/shared/db/models.py` (~17 таблиц).

### Ключевые таблицы

```
platform_users                      platform_oauth_credentials
platform_projects                   platform_channels
platform_project_members            platform_channel_tokens
platform_channel_login_credentials  content_upload_queue_tasks
channel_daily_statistics            channel_reauth_audit_logs
live_streaming_accounts             live_stream_configurations
schedule_templates                  schedule_template_slots
notifications                       platform_schema_migrations
```

### Repositories (`prod/shared/db/repositories/`)

`audit_repo`, `channel_repo`, `console_repo`, `credential_repo`, `notification_repo`, `stats_repo`, `task_repo`, `template_repo`, `user_repo`. Каждый — тонкая обёртка над SQLAlchemy Core.

### Миграции

`database/DDL/migrations/` — SQL-файлы:
- `001_create_schema.sql` — базовая схема.
- `002_migrate_data.sql` — перенос данных с Yii.
- `003_cleanup_legacy.sql`
- `004_yii_decommission.sql`, `005_drop_yii_tables.sql` — снос Yii.

Применение — вручную (`mysql content_fabric < 00X_*.sql`). Tracker — таблица `platform_schema_migrations`.

Schema-индекс: [database/DDL/SCHEMA_INDEX.md](../database/DDL/SCHEMA_INDEX.md).

---

## 10. Things to know

- **MSK timezone.** Сервер в `Europe/Moscow`. Yii-cron-эмулятор (`scheduler/jobs.py:395-404`) использует local time — расписание DLE привязано к МСК.
- **IntEnum + SQL.** Для `TaskStatus` / `UserStatus` всегда передавать `.value`, а не сам IntEnum. Иначе SQLAlchemy + MySQL Connector могут не привести к int. См. `scheduler/jobs.py:88` (`TaskStatus.PENDING.value`).
- **`metadata_` workaround.** В `models.py` колонки `metadata` объявлены как `Column("metadata_", JSON, key="metadata")` чтобы избежать конфликта с `MetaData` SQLAlchemy.
- **Yii — legacy, removed.** Старый `aiyoutube.pbnbots.com/yii/` физически удалён, таблицы дропнуты, домен сейчас обслуживает только новый FastAPI через nginx-проксю. Если в `auditd` срабатывает `cff-yii-legacy` — кто-то восстановил старый код, это инцидент.
- **`tg-app/` — это ОТДЕЛЬНОЕ приложение.** Telegram-бот @mykytatishkin, физически в `/opt/tg-app/` (или где он его сейчас держит), к CFF/прод-стеку отношения не имеет. **Не трогать.** Сейчас он offline после `prod/tg-app/` cleanup'а — восстановление на @mykytatishkin.
- **`/metrics` не наружу.** nginx режет всё кроме `127.0.0.1`. Prometheus скрейпает локально. Если нужен доступ снаружи — SSH-туннель на 9090, не открывать порт.
- **Docs (`/docs`, `/redoc`, `/openapi.json`) выключены в проде.** Включаются только если `ENV=development` (`main.py:191-193`).
- **`unported/` директория удалена.** Никогда не существовала в текущем layout, не искать.
- **`User=root` в systemd.** Все юниты бегут от root — наследие Yii. План понизить до `cff:cff` есть, но не приоритет (auditd ловит всё, что нужно).
- **`prod/Dockerfile` и `docker-compose.yml`** в корне `prod/` — alternative deployment, в проде **не используется**. Прод = systemd + venv. Docker используется только для observability-стека (`prod/deploy/observability/docker-compose.yml`).
- **`failed` queue в Redis.** Если `redis-cli LLEN rq:queue:failed > 0` — задачи упали и не реквеуятся автоматически. Разбирать через `rq info` или вручную.
- **Log rotation = copytruncate.** Воркеры держат FD на лог-файл, поэтому `copytruncate` (а не `create`). После ротации FD остаётся валидным.
