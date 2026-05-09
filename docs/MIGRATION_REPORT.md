# Migration Report: Yii2 (PHP) to Content Fabric (Python/FastAPI)

**Date:** 2026-05-02
**Status:** Ready for Weekend Cutover (Big Bang)
**Branch:** `feat/yii-integration`

## 1. Overview
The legacy PHP stack (Yii2) has been fully integrated into the Content Fabric (CFF) application. CFF now handles all backend pipelines, automation tasks, and administrative management that were previously split between the two systems.

## 2. Integrated Components

### 2.1 Backend Pipelines
- **DLE Ingestion:** Automated fetching of content from 7 external MySQL databases.
  - *Module:* `shared/ingestion/dle/`
  - *Worker:* `cff-dle-ingestion-worker`
  - **Asset fetching strategy** (1:1 port of Yii PHP controllers, see `shared/ingestion/dle/sources.py`):
    - Public sites (audiokniga-one.com, knigi-audio.biz, club-books.ru, knigi-online.club, bazaknig.net) sit behind Cloudflare's "Managed Challenge" → bare HTTP cannot reach them. PHP never went through the public site for asset fetches and neither do we. Covers and audio playlists are fetched directly from origin CDN `vvoqhuz9dcid9zx9.redirectto.cc` (no Cloudflare).
    - Path layouts mirror PHP exactly: `s01/{imgurl(book_id)}{book_id}.jpg|.pl.txt` for audiokniga/knigi-audio/bazaknig, `s20/{imgurl(tr_id)}{tr_id}.jpg` for club-books/knigi-online.
    - `imgurl(id)` splits each digit with `/` (port of `MyFunction::imgurl`): `275374` → `2/7/5/3/7/4/`.
    - books-online.info uses `cdn.my-library.info/{wallpaper}` (mirror, no Cloudflare).
    - slushat-knigi.com is *not* behind Cloudflare and serves covers from its own `/uploads/posts/{cover}` path (PHP code points at `cdn.my-library.info` but that mirror is dead for new posts — verified 2026-05-09).
    - audiokniga / knigi-audio audio: download `<book_id>.pl.txt` JSON playlist → parse `"file":"<URL>"` matches → fetch each MP3 with `Referer: redirectto.cc` → ffmpeg-concat into one source_audio.mp3.
  - *DB columns expected:* `book_id` exists on 5 of 7 DLE installs (knigi-audio, audiokniga, club-books, slushat, bazaknig); books-online + knigi-online lack it. `client.py` auto-detects via `SHOW COLUMNS` and adapts the SELECT.
- **Shorts Pipeline:** End-to-end automation from YouTube donor download to AI processing.
  - *Tools:* `yt-dlp`, OpenAI Whisper, GPT-4, FFmpeg VERT.
  - *Worker:* `cff-shorts-worker`
- **Sora Scraper:** Integration with Sora AI public feed via Zenrows.
  - *Module:* `shared/sora/`
- **Daily Stats:** Collection of YouTube channel and video metrics.
  - *Worker:* `cff-stats-worker`
- **Stream Control:** Management of 9 ongoing YouTube live streams via systemd.
  - *Worker:* `cff-stream-control-worker`

### 2.2 Web User Interface (Admin Panel)
New administrative routes added to `/panel/`:
- **Live Streams:** Monitoring and control (Start/Stop/Restart) of systemd stream units.
- **DLE Sources:** Status and manual trigger for the 7 content donor sites.
- **System Stats:** Global overview of views, subscribers, and video counts.
- **Logs:** Enhanced log viewer supporting the 5 new specialized workers.

### 2.3 Observability & Logging
Gigantic layer of structured logging implemented across all modules:
- Prefixes: `[DLE PIPELINE]`, `[SCHEDULER]`, `[DLE PROCESSOR]`, `[DLE CLIENT]`.
- Detailed tracing of task routing, asset downloading, and FFmpeg assembly.

## 3. Automated Testing (15 Tests)
The system is covered by a comprehensive test suite verified on the production server:
- `test_web_ui.py`: Verifies all new admin panels render correctly.
- `test_scheduler_routing.py`: Tests the 'smart' task distribution logic.
- `test_dle_pipeline_integration.py`: Full DLE-to-CFF integration cycle.
- `test_dle_ingestion.py`: Unit tests for xfields parsing and normalization.
- `test_shorts_pipeline.py`: Unit tests for AI-driven video processing modules.

## 4. Weekend Cutover Plan
1. **Freeze:** Stop Yii2 cron tasks and existing live streams.
2. **Database:** Execute `database/DDL/migrations/004_yii_decommission.sql` to migrate data from legacy tables.
3. **Deploy:** Pull `feat/yii-integration` on the server and update `.env`.
4. **Launch:** Start the 5 new systemd workers.
5. **Verify:** Run `python3 -m scripts.compare_yii_cff_data` and the 15-test suite.

## 5. Security Note
All database credentials (DSNs) and API keys have been moved to `.env` files. Ensure `/opt/content-fabric/prod/.env/.env.dle` is properly secured.
