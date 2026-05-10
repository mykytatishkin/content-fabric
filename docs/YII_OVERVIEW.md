# Yii2 App — Quick Overview

> 1-сторінковий пояснювач: що таке `aiyoutube.pbnbots.com` і як він працює. Деталі — в `YII_FULL_BREAKDOWN.md`.

## Що це таке

Yii2 PHP застосунок (advanced template) на shared hosting `fastuser`. Призначення — **повний цикл автогенерації відео для YouTube** з різних джерел. Працює на тому ж сервері і тій же БД (`content_fabric`) що й Content Fabric (Python). Поступово мігрується в CFF.

## 6 pipeline-ів

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 7 DLE-сайтів    │    │ YouTube donor   │    │ sora.chatgpt    │
│ (книги MariaDB) │    │ канали (API)    │    │ (Zenrows)       │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         │ news_read DESC       │ duration ≥ 600s      │ views > 1000
         │                      │                      │
┌────────▼────────┐    ┌────────▼────────┐    ┌────────▼────────┐
│ TTS (15 styles) │    │ yt-dlp+Whisper  │    │ GPT-Vision 3    │
│ + slideshow     │    │ +GPT highlights │    │ кадрів +meme    │
│ 1920×1080 mp4   │    │ +3 ffmpeg vars  │    │ caption         │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         └──────────┬───────────┴──────────────────────┘
                    │
              ┌─────▼──────┐         ┌─────────────────┐
              │ tasks (DB) │◄────────│ RBC RSS news    │
              │  status=0  │  TTS    │ + SerpAPI img   │
              └─────┬──────┘         └─────────────────┘
                    │
              ┌─────▼──────────┐
              │ CFF publishing │  → YouTube (OAuth refresh_token)
              │ worker         │
              └────────────────┘

      ┌─────────────────┐
      │ 9 systemd units │  → ffmpeg concat -stream_loop -1
      │ stream-*.service│  → rtmp://a.rtmp.youtube.com/live2/{KEY}
      └─────────────────┘
```

### 1. **Книжкові YouTube-канали** — DLE (DataLife Engine) → YouTube
   - 7 зовнішніх MySQL баз: audiokniga-one, knigi-audio.biz, club-books, books-online, slushat-knigi, knigi-online.club, bazaknig
   - Беруть `dle_post` сорт за `dle_post_extras.news_read DESC` (популярність на джерелі)
   - Обкладинку тягнуть з origin CDN `redirectto.cc` (bypass Cloudflare)
   - GPT-4-turbo генерує нову назву (для деяких джерел)
   - OpenAI TTS (15 стилів інтонації) озвучує `short_story`
   - ffmpeg компонує slideshow з cover image → 1920×1080 mp4
   - INSERT в `tasks` (черга на 3 слоти/день: 09:00 / 12:40 / 14:00)

### 2. **DLE shorts з цитат**
   - Окремий pipeline: ручний `quotes.txt` → одна цитата на день
   - Випадковий voice + випадковий стиль (з 14)
   - ASS-субтитри по 1 слову (Lena.ttf 140px, центр екрану)
   - 1080×1920 + bg_music на 0.35 гучності → INSERT в `tasks`

### 3. **YouTube Shorts з донорських відео** ⭐ найскладніший pipeline
   - 3 цільових канали: `@xobiATVUA` (квадроцикли, 1 донор), `@babysmilevlog` (дитячий, 6 донорів), `@Новини_1` (новини UA, 4 донори)
   - YouTube Data API: search by channelId, фільтр `duration ≥ 10хв`
   - **Python**: yt-dlp 1080p → ffmpeg → Whisper-1 транскрибує
   - **GPT-4o-mini** обирає 5 моментів 10-30с з критеріями `[кульмінація, емоції, сміх, важлива інформація]`
   - Для кожного: GPT генерує `{title ≤60, comment 1-2 sent}`
   - ffmpeg ріже 3 формати: VERT 1080×1920, ORIG, **VERT_BG** (з blurred-background)
   - **GPT-4o-mini Vision** оцінює кадри як thumbnail (1-10) → найвищий
   - INSERT × 5 в `tasks` з графіком 09:00 / 12:40 / 17:17 / 20:10

### 4. **Sora virality reposting**
   - `sora.chatgpt.com/backend/public/nf2/feed` через Zenrows premium_proxy
   - Фільтр `unique_view_count > 1000` (вже виральне)
   - 3 кадри на 20%/50%/80% timepoints → GPT-Vision описує (емоція, атмосфера, підтекст)
   - GPT-4o-mini генерує meme-caption (іронічний, 1-2 речення)
   - GPT-4o-mini повертає JSON `{title, description, hashtags ≤15, first_comment}` з retry до 5 спроб
   - ffmpeg drawtext знизу-центру (DejaVuSans-Bold 32px, чорний box, прозорість 50%)
   - INSERT × 3/день у 12:00 / 14:00 / 17:00

### 5. **News pipeline** (RBC RSS → Long video / Shorts)
   - RBC.ua RSS → перша непублікована новина
   - SerpAPI Google Images: 5 фото ≥ 1200px
   - TTS news-style → audio.mp3
   - `make_srt.py` synchronizes субтитри
   - **Long:** `makeYoutubeVideoFrom5Images` — 1920×1080 з Ken Burns ефектом (`zoompan=z='1+0.00012*on'`)
   - **Shorts:** 1080×1920 + burn-in субтитри (Arial 14px, white, MarginV=160)

### 6. **Live streaming** (9 systemd units)
   - `ffmpeg -f concat -stream_loop -1 -i playlist.txt -c:v copy -c:a copy -t 42900 -f flv rtmp://...`
   - 11h55min ліміт (YouTube Live max), `Restart=on-failure`
   - PHP frontend `/stream/` — реактивна адмінка (5-сек polling, bulk start/stop, log modal)
   - YouTube Live API через `YoutubeService::prepareBroadcastForStart` (broadcast ↔ stream key bind)
   - **CFF reconcile loop** додано бо systemd `Restart` не оновлює broadcast lifecycle

## Як це з'єднано

| Шар | Технологія | Призначення |
|---|---|---|
| Web frontend | Yii2 + Bootstrap5 | `/stream/` адмінка + OAuth flow |
| Backend admin | Yii2 (мінімальний) | login only — нема CRUD |
| CLI (cron) | Yii console controllers | Всі pipeline'и (`php yii <route>`) |
| Python venv | OpenAI SDK + yt-dlp + Playwright | shorts pipeline + TTS + cookies refresh |
| Live streams | systemd + ffmpeg + bash runner | 9 stream-*.service unit'ів |
| Спільна БД | MariaDB `content_fabric` | таблиці `tasks`, `stream`, `youtube_account`, `youtube_channels`, ... |
| 7 DLE баз | MariaDB 5.5.68 (зовнішні) | `dle_post`, `dle_post_extras` (з `news_read`) |
| Зовнішні API | OpenAI, YouTube Data API, Zenrows, SerpAPI | див. таблицю в FULL doc §18.4 |

## Метрики віральності — 5 окремих евристик

1. **DLE:** `dle_post_extras.news_read DESC` — найчитаніші пости на джерелі
2. **YouTube donor:** `duration ≥ 600s` + `order=date` (свіжість, не popularity)
3. **Sora:** `unique_view_count > 1000`
4. **GPT semantic** (тільки shorts): "знайди 5 фрагментів з кульмінацією, емоціями, сміхом, важливою інформацією"
5. **GPT Vision thumbnail scoring:** 1-10 score per frame
6. **News:** просто freshness (перший непрочитаний RSS item)

## Робоча модель — таблиця `tasks`

Все що генерує PHP → INSERT в `content_fabric.tasks` як рядок з `att_file_path` (mp4 path), `cover` (jpg), `title/description/keywords/post_comment`, `account_id` (FK → `youtube_account`), `media_type='youtube'`, `status=0`, `date_post` (запланована дата). Зовнішня черга (раніше — Yii task processor; **зараз — CFF Python `cff-publishing-worker`**) забирає → завантажує на YouTube через OAuth refresh_token.

## Cron-розклад

| Файл | Команда | Що робить |
|---|---|---|
| `shel_youtube.sh` | combined: stats + 7 DLE upload'ів + news | головний денний cron (~50-60 хв) |
| `shel_youtube_news.sh` | `news/shorts 55` | новинні shorts |
| `shel_youtube_shorts_from_video.sh` | `shorts_from_video/shorts_from_donors 28` | квадроцикли shorts |
| `shel_youtube_time.sh` | масовий `<source>/shorts <acc>` | DLE shorts |
| `shel_youtube_time_2.sh` | `slushat_knigi_com/shorts 25` | slushat shorts |

## Status міграції в CFF

| Done | TBD |
|---|---|
| ✅ DLE ingestion (7 баз) | ⏳ Shorts pipeline (yt-dlp + Whisper + GPT) |
| ✅ Stream broadcast lifecycle + reconcile | ⏳ Sora virality |
| ✅ systemd manager + admin UI | ⏳ News pipeline (RBC + slideshow) |
| ✅ Daily channel statistics | ⏳ Image compositor (`create_youtube_image`) |
| ✅ Tasks queue → publishing worker | ⏳ Donor channel configs (28/31/34) |
| ✅ OAuth flow (Playwright reauth) | ⏳ Voice TTS (15 styles) |

---

**Detailed:** див. `YII_FULL_BREAKDOWN.md` (4176 рядків з повною деталізацією кожної функції, схеми БД, GPT-prompts, ffmpeg-команд, security ризиків і port-контрактів).
