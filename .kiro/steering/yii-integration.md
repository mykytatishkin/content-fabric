---
inclusion: always
---

# Yii2 → CFF Integration (historical record)

Last updated: 2026-05-09

## Status: COMPLETE

Yii2 → CFF миграция завершена. Yii2 на сервере остановлен и удалён из `/var/www/fastuser/data/www/aiyoutube.pbnbots.com/`. Crontab Yii снят. Никакого PHP-кода в проде не осталось.

Legacy Yii-код архивирован локально в `.legacy/yii/` (см. `.gitignore`) — только для справки/раскопок. Не редактировать, не деплоить.

7 внешних DLE source-баз (отдельные MySQL-серверы) **продолжают существовать** — это контент-доноры, не имеют отношения к Yii. CFF читает их напрямую через `prod/shared/ingestion/dle/`.

Этот файл оставлен как карта соответствий: «что делал Yii → где это в CFF сейчас». Если нужен код — смотрите ссылки на `prod/...`, не на `.legacy/yii/`.

---

## Что делал Yii2 → что делает CFF

| Yii2 (PHP, удалён) | CFF (Python, актуально) |
|--------------------|------------------------|
| `php yii unique_audio/upload_to_youtube` | queue `dle_ingestion` + `publishing` |
| `php yii audiokniga_one_com/upload_to_youtube` | queue `dle_ingestion` |
| `php yii bazaknig_net/upload_to_youtube` | queue `dle_ingestion` |
| `php yii shorts_from_video/shorts_from_donors` | queue `shorts` |
| `php yii youtube_stats/stat` | queue `stats` |
| `php yii stream/start\|stop\|restart` | queue `stream_control` |
| Crontab (5 задач) | Scheduler (`prod/scheduler/`) + 9 RQ workers |
| Web UI стримов (frontend Yii) | `/panel/streams` + `/api/v1/streams/*` |
| Web UI DLE sources (frontend Yii) | `/panel/dle-sources` + `/api/v1/dle-sources/*` |

---

## DLE Ingestion Pipeline (актуально)

7 внешних MySQL-серверов → CFF tasks → publishing worker → YouTube.

```
DleClient (prod/shared/ingestion/dle/client.py)
  → fetch_recent_posts() из dle_post + dle_post_extras
  → xfields_parser.py нормализует (author/avtor, cover/wallpaper, performer/chtec)
  → DleIngestionPipeline.run() (prod/shared/ingestion/dle/pipeline.py)
  → enqueue → cff-dle-ingestion-worker (queue 'dle_ingestion')
  → создаёт CFF tasks (status=PENDING)
  → scheduler потом enqueue'ит в 'publishing'
```

`slug_to_host(slug)` в `pipeline.py` — конвертит slug DLE-источника в host для построения `dle_post_url`. Без тестов — кандидат на покрытие (см. testing.md).

### DSN конфиг (prod/app/core/config.py → dle_settings)

Источники читаются из `prod/.env/.env.dle`. Семь записей: `DLE_DSN_KNIGI_AUDIO_BIZ`, `DLE_DSN_AUDIOKNIGA_ONE_COM`, `DLE_DSN_CLUB_BOOKS_RU`, `DLE_DSN_BOOKS_ONLINE_INFO`, `DLE_DSN_SLUSHAT_KNIGI_COM`, `DLE_DSN_KNIGI_ONLINE_CLUB`, `DLE_DSN_BAZAKNIG_NET`.

### XFields нормализация

| Поле | Стандарт | Исключения |
|------|---------|-----------|
| author | `author` | slushat_knigi_com → `avtor` |
| performer | `performer` | slushat_knigi_com → `chtec` |
| cover | `cover` | books_online_info → `wallpaper` |
| playerlist | `1` | audiokniga_one_com → `txt` |

`xfields_parser.py` нормализует всё это перед созданием task.

### Маппинг DLE источник → YouTube канал

| DLE источник | channel_id |
|-------------|-----------|
| knigi_audio_biz | 3, 6 |
| audiokniga_one_com | 5 |
| club_books_ru | 21 |
| books_online_info | 23 |
| slushat_knigi_com | 25 |
| bazaknig_net | 26, 27, 29, 30, 32, 47, 48 |

---

## Live Streams (9 каналов) — управление через CFF

Каждый стрим = ffmpeg RTMP loop как отдельный systemd unit:

```
stream-audiokniga-one.service
stream-bazaknig_net.service
stream-chitaemvslux.service
stream-haha-smiley-funny.service
stream-knigaza30sekund.service
stream-knigiaudiobiz.service
stream-knizhnyeannotacii.service
stream-Readbooks-online.service
stream-RelaxingHolidayLive.service
```

`knigiaudiobiz` использует кастомный `my_runner.sh` (видео + фоновая музыка + звуки + мурлыканье). Остальные — стандартный `yt_stream_runner.sh`.

Управление:
```python
from shared.streams.systemd_manager import SystemdManager
mgr = SystemdManager()
mgr.start("stream-knigaza30sekund")
mgr.status("stream-knigaza30sekund")
```

Или через API: `POST /api/v1/streams/{start,stop,restart}` (admin-only).

**Дубли** `stream-stream-*.service.service` от старого `mass_create_streams.sh` на сервере должны быть подчищены. Если встречаются — игнорировать, они не активны.

---

## Shorts Pipeline (queue `shorts`)

```
ShortsPayload (donor_video_url, channel_id, limit)
  → download_video() — yt-dlp
  → transcribe_with_timestamps() — OpenAI Whisper
  → find_highlights() — GPT-4 (5 best 10-30s segments)
  → cut_segment() — ffmpeg → vertical 1080x1920
  → pick_best_thumbnail() — GPT Vision
  → create_task() — CFF task ready for publishing
```

Worker: `cff-shorts-worker` (`prod/workers/shorts_worker.py`).

---

## Admin Panel маршруты (post-cutover)

| Path | Описание |
|------|---------|
| `/panel/streams` | Мониторинг и управление 9 стримами |
| `/panel/dle-sources` | Статус 7 DLE источников, ручной триггер |
| `/panel/stats` | Глобальная статистика (использует `snapshot_date` из `channel_daily_statistics`) |
| `/panel/logs` | journalctl-вьюер по всем `cff-*` сервисам |

---

## Общая БД — кто пишет что

После cutover все таблицы пишет только CFF.

| Таблица (новое имя) | Заменила Yii-таблицу |
|--------------------|---------------------|
| `platform_oauth_credentials` | `youtube_account` |
| `platform_channels` | `youtube_channels` |
| `live_stream_configurations` | `stream` |
| `content_upload_queue_tasks` | `tasks` |
| `channel_daily_statistics` | `youtube_channel_daily` |

См. database.md для полного списка таблиц.

---

## Rollback (на всякий)

Откат к Yii больше **не поддерживается**: PHP-код удалён, crontab снят, БД-схема ушла вперёд. Если что-то сломается — чинить в CFF, не пытаться вернуть Yii.

Архивная копия Yii-кода: `.legacy/yii/` локально + git tag перед merge'ом feat/yii-integration (если был выставлен).
