# Content Fabric — Observability

**Развёрнуто:** 2026-05-09 на `46.21.250.43`
**Стек:** Prometheus, Loki, Grafana, GlitchTip, node/process exporters
**Доступ:** только через SSH-туннель — ничего наружу не светим

---

## Зачем это и что оно делает

| Проблема | Решение |
|----------|---------|
| Не видно, на каком этапе одна задача упала: ingestion → voice → upload? | **trace_id** проходит через все воркеры. Один клик — весь путь задачи в Loki/Grafana. |
| Сейчас ничего не происходит — а как узнать, что всё в порядке? | **System Overview** дашборд: 11 ключевых метрик одной картинкой. |
| Очередь забилась, через 30 минут всё умрёт. | **Predictive alerts** — Grafana пингует за 15 минут до проблемы. |
| Что у нас за ошибки в `cff-publishing-worker` за час? | **AI-friendly logs API** + `/analyze` endpoint — JSON-сводка топ-ошибок. |
| Stack trace без контекста, не понятно какая задача упала | **GlitchTip** (Sentry) — ошибки сгруппированы, с trace_id и breadcrumbs. |

Все Telegram-уведомления, что были до этого, **продолжают работать** — `shared/notifications/telegram` не тронут.

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       CFF (FastAPI + 8 RQ workers)                       │
│   ┌──────────┐  ┌────────────┐  ┌───────────┐  ┌──────────────────┐    │
│   │ cff-api  │  │ scheduler  │  │ workers × │  │ DLE pipeline     │    │
│   │  :8000   │  │            │  │  8        │  │ ingest → process │    │
│   └────┬─────┘  └─────┬──────┘  └─────┬─────┘  └────────┬─────────┘    │
│        │              │                │                  │             │
│   trace_id propagation на каждой границе (logging_context.ContextVar)   │
└────────┼──────────────┼────────────────┼──────────────────┼─────────────┘
         │              │                │                  │
         ▼              ▼                ▼                  ▼
   /metrics      pushgateway        journald          sentry_sdk
   (FastAPI)     (rq jobs)        (stdout JSON)      (exceptions)
         │              │                │                  │
         ▼              ▼                ▼                  ▼
   ┌─────────────────────────┐  ┌──────────────┐  ┌────────────────┐
   │      Prometheus         │  │   Promtail   │  │   GlitchTip    │
   │   (30 d retention)      │  │   journal →  │  │  (selfhost     │
   │                         │  │      Loki    │  │   Sentry API)  │
   └────────┬────────────────┘  └──────┬───────┘  └────────┬───────┘
            │                          │                   │
            ▼                          ▼                   ▼
                       ┌──────────────────────────────────┐
                       │           Grafana :3001           │
                       │                                   │
                       │  Dashboards:                      │
                       │   • System Overview               │
                       │   • Task Pipeline                 │
                       │   • Trace Explorer                │
                       │   • Incidents Now                 │
                       │                                   │
                       │  Alerting (10 rules) → in-Grafana │
                       │  notifications + email (stub)     │
                       └──────────────────────────────────┘
```

---

## Что развёрнуто

### Контейнеры (`/opt/content-fabric/prod/deploy/observability/`)

| Container | Image | Bind | Назначение |
|-----------|-------|------|-----------|
| `cff-prometheus` | prom/prometheus:v2.55.1 | host net :9090 | TSDB метрик, 30 дней |
| `cff-pushgateway` | prom/pushgateway:v1.10.0 | 127.0.0.1:9091 | Метрики коротких rq job'ов |
| `cff-node-exporter` | prom/node-exporter:v1.8.2 | host net | CPU/RAM/диск/systemd |
| `cff-process-exporter` | ncabatoff/process-exporter:0.8.7 | 127.0.0.1:9256 | Per-process для cff-* и ffmpeg |
| `cff-loki` | grafana/loki:3.2.1 | 127.0.0.1:3100 | Хранилище логов, 30 дней |
| `cff-promtail` | grafana/promtail:3.2.1 | — | journalctl → Loki |
| `cff-grafana` | grafana/grafana:11.3.0 | 127.0.0.1:3001 | UI + Alerting |
| `cff-glitchtip-web` | glitchtip/glitchtip:v4.2.5 | 127.0.0.1:8001 | Sentry-совместимое API |
| `cff-glitchtip-worker` | glitchtip/glitchtip:v4.2.5 | — | Celery бэкграунд |
| `cff-glitchtip-postgres` | postgres:16-alpine | internal | DB GlitchTip |
| `cff-glitchtip-redis` | redis:7-alpine | internal | Cache GlitchTip |

### Изменения в CFF

| Где | Что |
|-----|-----|
| `shared/logging_context.py` | ContextVar для trace_id/task_id/worker, `TraceContextFilter` |
| `shared/logging_config.py` | JSON formatter с trace_id (`LOG_FORMAT=json`) |
| `shared/metrics.py` | 15+ Prometheus метрик, `@instrument_job` декоратор, `sample_all()` |
| `shared/error_tracking.py` | sentry_sdk init с FastAPI/SQLAlchemy/Redis/RQ интеграциями |
| `shared/queue/types.py` | `trace_id` поле в каждой Payload |
| `shared/queue/publisher.py` | Auto-fill trace_id из контекста на каждом enqueue |
| `workers/_job_bootstrap.py` | `bootstrap_job()` — единая точка для воркеров |
| `workers/*` (8 шт) | `@instrument_job` + `bootstrap_job()` в начале |
| `main.py` | `TraceContextMiddleware` (X-Trace-Id), `/metrics`, фоновый sample_all |
| `app/api/endpoints/logs.py` | AI-friendly Logs API — list, trace, tail, analyze, stats |
| `shared/ingestion/dle/pipeline.py` | trace_id в `legacy_add_info` + propagation |

---

## Как пользоваться

### Открыть Grafana

```bash
ssh -L 3001:127.0.0.1:3001 root@46.21.250.43
# затем в браузере: http://127.0.0.1:3001
```

**Креды:** `admin / -idmenpMzcVHdRITE8o1MoxXHNqRkLeI`
(хранятся в `/opt/content-fabric/prod/deploy/observability/.env`)

### Открыть GlitchTip (для настройки error tracking)

```bash
ssh -L 8001:127.0.0.1:8001 root@46.21.250.43
# затем: http://127.0.0.1:8001
```

Регистрация через UI первой кнопкой (open registration отключена — первый пользователь становится superuser).

### Посмотреть путь одной задачи (главная фича)

**Способ 1 — Grafana UI:**
1. Открыть дашборд **CFF → Trace Explorer**
2. Вставить `trace_id` (UUID, ~32 hex chars)
3. Получить полный timeline по всем воркерам, упорядоченный по времени

**Способ 2 — API (для AI-инструментов):**
```bash
curl -H "Authorization: Bearer <jwt>" \
  http://127.0.0.1:8000/api/v1/logs/trace/abc123def456...
# JSON с полями: events, count, per_service, by_level, first/last_seen
```

**Способ 3 — Loki напрямую:**
В Grafana → Explore → datasource Loki:
```
{unit=~"cff-.*"} |~ "abc123def456"
```

### Где взять trace_id

- **API:** в каждом ответе HTTP-заголовок `X-Trace-Id`
- **БД:** для DLE-задач — `JSON_EXTRACT(legacy_add_info, '$.trace_id')` в `content_upload_queue_tasks`
- **Логи:** в каждой строке (формат JSON или plain `[trace=xxx task=N]`)

### AI-friendly Logs API

Все endpoint'ы под `/api/v1/logs/*`, требуют JWT auth.

| Endpoint | Назначение |
|----------|-----------|
| `GET /services` | Список cff-* и stream-* юнитов |
| `GET /` | Фильтрованный list (service[], level, since, until, grep, trace_id, task_id) |
| `GET /trace/{trace_id}` | Все логи по одному trace_id, упорядочены, с per_service summary |
| `GET /tail/{service}?lines=N` | Последние N строк сервиса |
| `GET /analyze?since=1+hour+ago` | Сводка: top errors, anomalies, hot trace_ids, текстовый summary |
| `GET /stats?since=1+hour+ago` | Лёгкая версия — только counts по level/service |

Пример "что сейчас ломается":
```bash
curl -s "http://127.0.0.1:8000/api/v1/logs/analyze?since=15+min+ago" | jq .summary
# "Window: 15 min ago. Lines: 1247. Errors+critical: 8. Top errors: (3) ..."
```

### Дашборды (Grafana → Dashboards → CFF)

| Дашборд | Когда смотреть |
|---------|----------------|
| **System Overview** | Регулярная проверка — всё ли в норме |
| **Task Pipeline** | Анализ потока задач, успешность, latency |
| **Incidents Now** | Что-то горит — что именно? |
| **Trace Explorer** | Дебаг конкретной задачи |

---

## Алерты

### Конфигурация
Файл: `deploy/observability/grafana/provisioning/alerting/rules.yaml` (10 правил)

| Severity | Алерт | Условие |
|----------|-------|---------|
| critical | cff-api down | `up{job="cff-api"} == 0` для 2 мин |
| critical | Worker missing | Воркер cff-* без процессов 5 мин |
| critical | Error spike | >50 ошибок за 5 мин |
| warning | Queue growing | depth > 50 И растёт > 15 мин |
| warning | Failure rate >30% | за 15 мин окно |
| warning | OAuth token <24h | предсказание истечения |
| warning | Worker memory >80% | памяти от лимита |
| warning | Disk <20GB | свободного места |
| warning | Stream restart loop | >5 restart/час |
| info | DLE source flapping | up/down >4 раз/час |

### Куда приходят
- **По умолчанию** — в Grafana inbox (`Alerting → History`)
- На дашборды (annotation на графиках в момент срабатывания)
- На главной странице badge "X firing alerts"

### Email — заглушка
Email contact point **не создан** в provisioning, потому что Grafana не валидирует пустой адрес.

Когда дадите адрес и SMTP-креды:
1. Заполнить в `/opt/content-fabric/prod/deploy/observability/.env`:
   ```
   ALERT_EMAIL_TO=alerts@example.com
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=...
   SMTP_PASSWORD=...
   ```
2. В docker-compose.yml поменять `GF_SMTP_ENABLED=true`, передать SMTP вары в env
3. `docker compose --env-file .env up -d grafana`
4. В Grafana UI: `Alerting → Contact points → New` → type Email → routing rule в `policies.yaml`

### Telegram
**Не тронут** — продолжает работать через `shared/notifications/telegram` для критичных ошибок воркеров (DLE, voice, publishing). Альтернатива в Grafana — параллельный канал, не замена.

---

## Метрики (что собирается)

`shared/metrics.py` экспортирует:

| Метрика | Тип | Лейблы | Источник |
|---------|-----|--------|----------|
| `cff_tasks_created_total` | Counter | source, media_type, channel | DLE pipeline |
| `cff_tasks_completed_total` | Counter | channel | publishing_worker |
| `cff_tasks_failed_total` | Counter | channel, stage, error_kind | scheduler |
| `cff_task_stage_duration_seconds` | Histogram | stage | per stage |
| `cff_queue_depth` | Gauge | queue | sample_all() через 30с |
| `cff_dle_source_up` | Gauge | source | sample_all() — SELECT 1 timeout 5с |
| `cff_youtube_token_expires_in_seconds` | Gauge | channel | platform_channels.token_expires_at |
| `cff_youtube_upload_bytes` | Histogram | channel | publishing_worker |
| `cff_youtube_upload_duration_seconds` | Histogram | channel | publishing_worker |
| `cff_stream_active` | Gauge | stream, service | systemctl |
| `cff_stream_uptime_seconds` | Gauge | stream | /proc/uptime - ActiveEnterTimestampMonotonic |
| `cff_errors_total` | Counter | worker, error_kind | `@instrument_job` exception capture |
| `cff_worker_job_duration_seconds` | Histogram | worker, outcome | `@instrument_job` через pushgateway |
| `cff_worker_jobs_total` | Counter | worker, outcome | то же |

HTTP-метрики (FastAPI Instrumentator): `http_requests_total`, `http_request_duration_seconds` с labels `method`, `handler`, `status`.

---

## Операции

### Включить JSON логи (для лучшего парсинга в Loki)
```bash
# /opt/content-fabric/prod/.env/.env.api
LOG_FORMAT=json
# затем:
systemctl restart cff-api 'cff-*-worker'
```

### Подключить GlitchTip
1. `ssh -L 8001:127.0.0.1:8001 root@46.21.250.43`
2. Открыть `http://127.0.0.1:8001` → зарегистрироваться (первый user — superuser)
3. Создать проект `cff-prod`
4. Скопировать DSN из Settings → Client Keys
5. Добавить в `/opt/content-fabric/prod/.env/.env.api`:
   ```
   SENTRY_DSN=http://<key>@127.0.0.1:8001/<project_id>
   ```
6. `systemctl restart cff-api 'cff-*-worker'`

### Проверить статус стека
```bash
ssh root@46.21.250.43 'cd /opt/content-fabric/prod/deploy/observability && \
  docker compose --env-file .env ps --format "table {{.Name}}\t{{.Status}}"'
```

### Перезапустить отдельный сервис
```bash
ssh root@46.21.250.43 'docker restart cff-grafana'  # или cff-prometheus / cff-loki
```

### Полностью обновить стек (новые конфиги/dashboards)
```bash
ssh root@46.21.250.43 'cd /opt/content-fabric/prod && git pull && \
  cd deploy/observability && docker compose --env-file .env up -d'
```

---

## Безопасность

- ✅ Все порты на `127.0.0.1` (кроме node_exporter в host network — он на 9100, но за firewall сервера)
- ✅ Доступ только через SSH-туннель
- ✅ Grafana — admin password в `.env`, файл chmod 600
- ✅ GlitchTip — open registration отключен
- ✅ `.env` файлы в gitignore — не коммитятся в репо
- ⚠️ Если `LOG_FORMAT=json`, логи становятся длиннее — это нормально для Loki но journalctl читать сложнее

---

## Текущее состояние (2026-05-09 после деплоя)

```
Containers:    11/11 up
Targets:       5/5 up (cff-api, node, process, prometheus, pushgateway)
CFF services:  10/10 active
Logs API:      HTTP 200 (требует JWT)
/metrics:      HTTP 200
Grafana:       HTTP 200
Loki:          HTTP 200
GlitchTip:     HTTP 200
```

---

## Что не вошло (можно сделать позже)

- **Email контакт-поинт** — ждёт адрес и SMTP-кредов
- **Custom Loki retention для разных severity** — пока единый 30d
- **Alert на predicted disk full** через `predict_linear()` — сейчас только на текущем уровне
- **Recording rules** для тяжёлых дашбордов — `prometheus/rules/` пустая
- **Distributed tracing** через OpenTelemetry → Tempo — пока trace_id только через логи. Если понадобится визуализация спанов, добавим.
- **GlitchTip notifications в Slack/Discord** — пока только UI-просмотр ошибок

---

## Ссылки на код

| Файл | Что внутри |
|------|-----------|
| `prod/shared/logging_context.py` | ContextVar trace_id, set/get/ensure |
| `prod/shared/logging_config.py` | JSON+text formatters, TraceContextFilter |
| `prod/shared/metrics.py` | Prometheus метрики + `@instrument_job` + `sample_all()` |
| `prod/shared/error_tracking.py` | sentry_sdk init с auto-tags |
| `prod/workers/_job_bootstrap.py` | bootstrap_job() |
| `prod/app/api/endpoints/logs.py` | AI-friendly Logs API |
| `prod/main.py` (TraceContextMiddleware, /metrics startup) | FastAPI integration |
| `prod/deploy/observability/docker-compose.yml` | Стек |
| `prod/deploy/observability/grafana/dashboards/*.json` | 4 дашборда |
| `prod/deploy/observability/grafana/provisioning/alerting/rules.yaml` | 10 alert rules |
| `prod/deploy/observability/README.md` | Quick reference |
