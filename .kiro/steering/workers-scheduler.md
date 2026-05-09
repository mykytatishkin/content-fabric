---
inclusion: fileMatch
fileMatchPattern: ['prod/workers/**/*.py', 'prod/scheduler/**/*.py', 'prod/shared/queue/**/*.py', 'prod/shared/youtube/**/*.py']
---

# Workers & Scheduler

Last updated: 2026-05-09

## Task Lifecycle

```
Task Created (status=0 PENDING, scheduled_at set)
      ↓
Scheduler polls DB every 60s (prod/scheduler/jobs.py)
      ↓
Mark as PROCESSING (status=3)
      ↓
Enqueue to Redis (publishing queue via rq)
      ↓
Publishing Worker picks up (workers/publishing_worker.py)
      ↓
Upload to YouTube (shared/youtube/upload.py → client.py)
      ↓  success                    ↓  failure
COMPLETED (status=1)           Retry once, then FAILED (status=2)
- save upload_id               - save error_message
- set thumbnail                - send Telegram notification
- auto-like                    - if token error: suggest reauth
- post comment
```

DLE pipeline runs upstream of this: ingestion worker creates the PENDING tasks the scheduler then sees.

---

## Queue system (RQ) — 9 queues

Defined in `prod/shared/queue/config.py:17-26`:

| Queue | Worker (systemd unit) | Module | Payload type |
|-------|----------------------|--------|--------------|
| `publishing` | cff-publishing-worker | `workers/publishing_worker.py` | `VideoUploadPayload` |
| `notifications` | cff-notification-worker | `workers/notification_worker.py` | notification dict |
| `voice` | cff-voice-worker | `workers/voice_worker.py` | `VoicePayload` |
| `dle_ingestion` | cff-dle-ingestion-worker | `workers/dle_ingestion_worker.py` | `DleIngestionPayload` |
| `dle_processing` | cff-dle-processor-worker | `workers/dle_processor_worker.py` | `DleProcessingPayload` |
| `shorts` | cff-shorts-worker | `workers/shorts_worker.py` | `ShortsPayload` |
| `sora` | cff-sora-worker | (planned/wired) | sora payload |
| `stats` | cff-stats-worker | `workers/stats_worker.py` | `StatsPayload` |
| `stream_control` | cff-stream-control-worker | `workers/stream_worker.py` | `StreamControlPayload` |

All payload dataclasses live in `prod/shared/queue/types.py`. Constants `QUEUE_*` in `config.py` are the canonical names — never hard-code queue strings.

Default RQ timeouts: `publishing` 30min, `notifications` 2min, others per-job. See `shared/queue/publisher.py` `enqueue_*` helpers.

```python
from shared.queue.publisher import enqueue_video_upload
from shared.queue.types import VideoUploadPayload

enqueue_video_upload(VideoUploadPayload(
    task_id=t["id"],
    channel_id=t["channel_id"],
    source_file_path=t["source_file_path"],
    title=t["title"],
    ...
))
```

---

## @instrument_job + Pushgateway

Short-lived RQ jobs would die before Prometheus could scrape them, so each worker uses `@instrument_job(<job_name>)` from `shared.metrics`:

```python
from shared.metrics import instrument_job

@instrument_job("publishing")
def process_upload_job(payload: VideoUploadPayload) -> dict[str, Any]:
    bootstrap_job(payload, "cff-publishing")
    return process_upload(payload)
```

The decorator:
1. Creates a per-job `CollectorRegistry`.
2. Records duration in a `cff_job_duration_seconds` Histogram.
3. Pushes the registry to Pushgateway (`PUSHGATEWAY_URL`, default `http://127.0.0.1:9091`) on completion — keyed by `{job=cff-<name>, instance=<host>}`.
4. After the job, calls `push_worker_global_metrics(worker_name)` (`shared/metrics.py:214-`) which pushes the **process-wide REGISTRY** (log_events_total counters from `MetricsLogHandler`, plus `python_*` runtime metrics). This is what makes `rate(log_events_total)` queries work for short-lived workers.

Both pushes group by worker name so each worker overwrites its own slot — Prometheus sees real progress instead of stale snapshots.

Used in: `publishing_worker`, `notification_worker`, `voice_worker`, `dle_ingestion_worker`, `dle_processor_worker`, `shorts_worker`, `stats_worker`, `stream_worker`.

---

## trace_id propagation

Every job and every HTTP request carries a `trace_id` ContextVar (`shared/logging_context.py`). Logs and metrics auto-attach it.

**HTTP entry:** `TraceContextMiddleware` (`prod/main.py:139-183`) reads `X-Trace-Id` header (or generates new one), sets the ContextVar, echoes back in response header. Both setting trace_id AND logging happen in the SAME middleware because Starlette wraps each middleware in its own asyncio Task scope — outer middleware can't see ContextVars set by an inner one.

**Worker entry:** every job handler calls `bootstrap_job(payload, worker_name)` from `prod/workers/_job_bootstrap.py`. It pulls `trace_id` from `payload.trace_id` (or generates new) and binds it to logging context. Result: a task created by HTTP request → ingestion job → publishing job all share the same trace_id, and `/api/v1/logs/trace/{trace_id}` returns the full cross-service trail.

**Cross-service propagation gotcha:** when one job enqueues another (DLE ingestion → DLE processor → publishing), the parent's trace_id must be passed in the new payload. See commit `2a610cb` for the fix in `_create_cff_task`.

---

## YouTube upload pipeline (shared/youtube/upload.py)

1. `channel_repo.get_channel_by_id()` → get tokens
2. `console_repo.get_console_by_id()` → get client_id/secret
3. `yt.create_service()` → auto-refreshes token (token_refresh.py)
4. `yt.upload_video()` → resumable upload with retry
5. Post-upload: like, comment, thumbnail
6. On failure: detect token errors → Telegram notification

---

## Reauth module (shared/youtube/reauth/)

Playwright-based automated Google OAuth login:
- `service.py` — orchestration: loads credentials from DB → Playwright → captures token
- `playwright_client.py` — 3200+ lines of browser automation
- `oauth_flow.py` — HTTP callback server on port 8080, token exchange
- `models.py` — `AutomationCredential`, `ReauthResult`, `BrowserConfig`

CLI: `python -m cli.reauth --channel-id 9 --all-failed --all`

---

## Centralized logging
All workers use `setup_logging(service_name)`:
```python
from shared.logging_config import setup_logging
setup_logging(service_name="cff-publishing")
```

`MetricsLogHandler` (registered by `setup_logging`) increments `log_events_total{level=...}` Counter on every log line — picked up by `push_worker_global_metrics` after each job.
