---
inclusion: always
---

# Yii2 → CFF Интеграция

## Контекст

Yii2 (PHP) — legacy-приложение на том же сервере (`/var/www/fastuser/data/www/aiyoutube.pbnbots.com/`). Работало параллельно с CFF через общую БД `content_fabric`. Вся его логика перенесена в CFF на ветке `feat/yii-integration`. Ждём weekend cutover для финального переключения.

---

## Что делал Yii2 → что делает CFF сейчас

| Yii2 (PHP) | CFF (Python) | Статус |
|-----------|-------------|--------|
| `php yii unique_audio/upload_to_youtube` | `cff-dle-ingestion-worker` + `cff-publishing-worker` | ✅ Готово |
| `php yii audiokniga_one_com/upload_to_youtube` | `cff-dle-ingestion-worker` | ✅ Готово |
| `php yii bazaknig_net/upload_to_youtube` | `cff-dle-ingestion-worker` | ✅ Готово |
| `php yii shorts_from_video/shorts_from_donors` | `cff-shorts-worker` | ✅ Готово |
| `php yii youtube_stats/stat` | `cff-stats-worker` | ✅ Готово |
| `php yii stream/start\|stop\|restart` | `cff-stream-control-worker` | ✅ Готово |
| Crontab (5 задач) | Scheduler + rq workers | ✅ Готово |
| Web UI стримов (frontend) | `/panel/streams` в CFF Admin Panel | ✅ Готово |
| Web UI DLE sources | `/panel/dle-sources` в CFF Admin Panel | ✅ Готово |

---

## DLE Ingestion Pipeline

7 внешних MySQL серверов → CFF tasks → publishing worker → YouTube

```
DleClient (shared/ingestion/dle/client.py)
  → fetch_recent_posts() из dle_post + dle_post_extras
  → xfields_parser.py нормализует поля (author/avtor, cover/wallpaper, performer/chtec)
  → DleIngestionPipeline.run() создаёт CFF tasks
  → cff-dle-ingestion-worker потребляет из Redis queue 'dle_ingestion'
```

### DSN конфиг (prod/app/core/config.py → dle_settings)

Источники читаются из `prod/.env/.env.dle`:
```
DLE_DSN_KNIGI_AUDIO_BIZ=mysql+pymysql://knigiaudiobiz_u:j2yvMQh0hcW68nRJ@77.220.213.172:3306/knigi_audio_biz_db
DLE_DSN_AUDIOKNIGA_ONE_COM=mysql+pymysql://audiokniga_one_com_u:lR9sU3dC@185.154.15.251:3310/audiokniga_one_com_db
DLE_DSN_CLUB_BOOKS_RU=mysql+pymysql://club_books_ru_u:wC8mU6yR8t@185.244.217.9:3311/club_books_ru_db
DLE_DSN_BOOKS_ONLINE_INFO=mysql+pymysql://booksonlineinfo:fQ3wH9sL5i@91.211.251.57:3306/booksonlineinfo
DLE_DSN_SLUSHAT_KNIGI_COM=mysql+pymysql://slushat_knigi_com_u:sW6jA6dN0q@80.85.141.91:3310/slushat_knigi_com_db
DLE_DSN_KNIGI_ONLINE_CLUB=mysql+pymysql://knigi_online_club_u:gY2yE2lD1z@185.224.133.132:3310/knigi_online_club_db
DLE_DSN_BAZAKNIG_NET=mysql+pymysql://bazaknig_net_u:tG5xR3eF8n@185.224.133.132:3310/bazaknig_net_db
```

### XFields нормализация (несовместимости между источниками)

| Поле | Стандарт | Исключения |
|------|---------|-----------|
| author | `author` | slushat_knigi_com использует `avtor` |
| performer | `performer` | slushat_knigi_com использует `chtec` |
| cover | `cover` | books_online_info использует `wallpaper` |
| playerlist | `1` | audiokniga_one_com использует `txt` |

`xfields_parser.py` нормализует всё это в единый формат перед созданием task.

### Маппинг DLE источник → YouTube канал

| DLE источник | channel_id в CFF |
|-------------|-----------------|
| knigi_audio_biz | 3, 6 |
| audiokniga_one_com | 5 |
| club_books_ru | 21 |
| books_online_info | 23 |
| slushat_knigi_com | 25 |
| bazaknig_net | 26, 27, 29, 30, 32, 47, 48 |

---

## Live Streams (9 каналов)

Управляются через systemd. Каждый стрим — ffmpeg loop на RTMP.

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

**Важно:** есть дубли `stream-stream-*.service.service` — баг скрипта `mass_create_streams.sh`. Не трогать, они не активны.

`knigiaudiobiz` использует кастомный `my_runner.sh` (видео + фоновая музыка + звуки огня + мурлыканье). Остальные — стандартный `yt_stream_runner.sh`.

Управление через CFF:
```python
from shared.streams.systemd_manager import SystemdManager
mgr = SystemdManager()
mgr.start("stream-knigaza30sekund")
mgr.status("stream-knigaza30sekund")
```

---

## Shorts Pipeline

```
ShortsPayload (donor_video_url, channel_id, limit)
  → download_video() — yt-dlp
  → transcribe_with_timestamps() — OpenAI Whisper
  → find_highlights() — GPT-4 (5 лучших моментов 10-30 сек)
  → cut_segment() — ffmpeg VERT (1080x1920)
  → pick_best_thumbnail() — GPT Vision оценивает кадры
  → create_task() — CFF task готов к публикации
```

Worker: `cff-shorts-worker` → queue `shorts`

---

## Новые Admin Panel маршруты (добавлены в feat/yii-integration)

| Путь | Описание |
|------|---------|
| `/panel/streams` | Мониторинг и управление 9 стримами (Start/Stop/Restart) |
| `/panel/dle-sources` | Статус 7 DLE источников, ручной триггер |
| `/panel/stats` | Глобальная статистика (просмотры, подписчики, видео) |
| `/panel/logs` | Расширенный лог-вьюер (5 новых воркеров) |

---

## Новые systemd сервисы (добавлены в feat/yii-integration)

Файлы в `prod/deploy/systemd/`:
- `cff-dle-ingestion-worker.service`
- `cff-shorts-worker.service`
- `cff-stats-worker.service`
- `cff-stream-control-worker.service`

Запуск: `python -m workers.{dle_ingestion,shorts,stats,stream}_worker`

---

## Новые Redis очереди

| Очередь | Worker | Payload тип |
|---------|--------|------------|
| `dle_ingestion` | cff-dle-ingestion-worker | `DleIngestionPayload` |
| `shorts` | cff-shorts-worker | `ShortsPayload` |
| `stats` | cff-stats-worker | `StatsPayload` |
| `stream_control` | cff-stream-control-worker | `StreamControlPayload` |

Все типы в `shared/queue/types.py`.

---

## Weekend Cutover Plan

**Порядок действий:**

1. **Freeze Yii** — остановить crontab (`crontab -r` или закомментировать все строки)
2. **Freeze streams** — `systemctl stop stream-*.service` (все 9)
3. **DB migration** — выполнить `database/DDL/migrations/004_yii_decommission.sql`
4. **Deploy** — `git pull origin feat/yii-integration` на сервере
5. **Env** — создать `prod/.env/.env.dle` с DSN для 7 баз
6. **Install services** — `bash prod/deploy/install-services.sh` (4 новых воркера)
7. **Start streams** — `systemctl start stream-*.service`
8. **Verify** — `python3 -m scripts.compare_yii_cff_data` + `pytest tests/ -v`

**Rollback:** `git checkout main`, восстановить crontab из `yii-audit/crontab-root.txt`

---

## Общая БД (важно)

Yii и CFF пишут в одну БД `content_fabric`. После cutover Yii больше не пишет.

Таблицы, которые писал Yii (теперь только читает CFF или мигрированы):
- `youtube_account` — OAuth credentials (теперь `platform_oauth_credentials`)
- `youtube_channels` — каналы (теперь `platform_channels`)
- `stream` — конфиги стримов (теперь `live_stream_configurations`)
- `tasks` — старая очередь (теперь `content_upload_queue_tasks`)
- `youtube_channel_daily` — статистика (теперь `channel_daily_statistics`)

---

## Тесты (15 новых в feat/yii-integration)

```
test_web_ui.py                  — новые admin panel маршруты
test_scheduler_routing.py       — smart task routing по DLE источникам
test_dle_pipeline_integration.py — полный DLE→CFF цикл
test_dle_ingestion.py           — xfields парсинг и нормализация
test_shorts_pipeline.py         — AI-driven video processing
```

Запуск: `cd prod && python -m pytest tests/ -v --tb=short`
