# Yii2 Legacy App — Full Function-by-Function Breakdown

> Повний detailed розбір PHP/Yii2 застосунку `aiyoutube.pbnbots.com` з прода. Зібрано з `/var/www/fastuser/data/www/aiyoutube.pbnbots.com/` (без 8.2GB папки `data/`). 203 PHP-файли + 10 shell + 4 python = ~13 000 рядків коду. Дата збору: 2026-05-10.
>
> Документ — рівень "знаю кожен виклик і кожне поле БД". Локальна копія коду живе в `_yii_research/` поряд з цим репо.

---

## Зміст

1. [Огляд застосунку](#1-огляд-застосунку)
2. [Повне дерево файлів](#2-повне-дерево-файлів)
3. [Технологічний стек і архітектура](#3-технологічний-стек-і-архітектура)
4. [Точки входу і життєвий цикл](#4-точки-входу-і-життєвий-цикл)
5. [Хардкоджені паролі/ключі/шляхи (БЕЗПЕКА)](#5-хардкоджені-паролі-ключі-шляхи-безпека)
6. [Composer dependencies](#6-composer-dependencies)
7. [Конфігураційні файли](#7-конфігураційні-файли)
8. [Frontend layer (web UI)](#8-frontend-layer-web-ui)
9. [Backend layer (admin panel)](#9-backend-layer-admin-panel)
10. [Common models — ядро даних](#10-common-models--ядро-даних)
11. [Common services](#11-common-services)
12. [Common components — `MyFunction.php` (1377 рядків, 50+ функцій)](#12-common-components--myfunctionphp)
13. [Console pipelines — всі 17 контролерів](#13-console-pipelines)
14. [Console DLE моделі (5×7=35 ActiveRecord класів)](#14-console-dle-моделі)
15. [Python скрипти — повний розбір](#15-python-скрипти)
16. [Shell скрипти (cron entry points)](#16-shell-скрипти)
17. [Каталог donor channels](#17-каталог-donor-channels)
18. [Каталог datasources](#18-каталог-datasources)
19. [Метрики віральності](#19-метрики-віральності)
20. [Live streaming infrastructure](#20-live-streaming-infrastructure)
21. [Інтеграція з Content Fabric](#21-інтеграція-з-content-fabric)
22. [Безпекові ризики](#22-безпекові-ризики)
23. [Контракти на портування в CFF](#23-контракти-на-портування-в-cff)

---

## 1. Огляд застосунку

`aiyoutube.pbnbots.com` — Yii2 advanced template (PHP 8.0+) живе на shared hosting `fastuser`. Покриває **6 функціональних доменів**:

### 1.1 Книжкові YouTube-канали (DLE → YouTube long-form)
Щодня вибирає найпопулярніші пости з 7 сторонніх DLE-сайтів (engine DataLife) → MySQL-з'єднання, читає `dle_post` + `dle_post_extras` (метрика `news_read DESC` = віральність) → завантажує обкладинку через **origin CDN bypass** (Cloudflare blocked) → **OpenAI GPT-4-turbo** генерує нову коротку назву (для деяких джерел) → озвучує `short_story` через **OpenAI TTS** (`gpt-4o-mini-tts`, 6 мов, 15 стилів інтонації) → **ffmpeg slideshow** з обкладинкою на 1920x1080 → INSERT в `tasks` черга з `date_post` (3 слоти на день: 09:00 / 12:40 / 14:00).

### 1.2 Книжкові YouTube-канали (DLE → Shorts з цитат)
Окрема стратегія: ручний `quotes.txt` → беруть першу цитату → випадкова обкладинка з `backgrounds/` + випадкова bg_music з `bg_music/*.mp3` + випадковий voice (4 варіанти) + випадковий стиль (14 стилів) → TTS → нормалізують аудіо до 48kHz stereo, volume +1.4 → генерують **ASS-субтитри по 1 слову** (Lena.ttf, 140px, центр екрана) → ffmpeg merge: 1080×1920 30fps з накладеними субтитрами + bg_music на 0.35 гучності + TTS → final 9-22сек YouTube Shorts.

### 1.3 YouTube Shorts з донорських відео
**Pipeline №1 для virality:** PHP сканує канали-донори через **YouTube Data API v3** (`search?channelId&order=date&maxResults=50` + `videos?id&part=contentDetails`) → фільтр `duration >= 600s` (≥10хв) → стек URL у `youtube_links_<id>.txt` → Python (`shorts_from_video.py`) запускається з venv: `yt-dlp` качає 1080p mp4 (з cookies) → ffmpeg витягує `pcm_s16le` 16kHz mono wav → OpenAI **Whisper-1** транскрибує (з 25MB чанкуванням) → **GPT-4o-mini** обирає 5 фрагментів 10-30 сек з критеріями `[кульмінація, емоції, сміх, важлива інформація]` → для кожного: GPT-4o-mini генерує `{title ≤60 chars, comment 1-2 sentences}` → ffmpeg ріже 3 формати на кожен фрагмент: **VERT** (1080×1920 letterbox), **ORIG** (без масштабування), **VERT_BG** (blurred background composite через `[0:v]scale=4000:-1,boxblur=30:30[blur]`) → витягує кадри `fps=1/4` з ORIG → **GPT-4o-mini Vision** оцінює кожен кадр як thumbnail (1-10) → найвищий → `_H.png` → PHP робить `cropTo1080x1920` + накладає channel link з Lena.ttf → INSERT в `tasks` × 5 з графіком `[09:00, 12:40, 17:17, 20:10]`. Використовується VERT_BG як final mp4.

### 1.4 Sora virality reposting
Тягне публічний фід `sora.chatgpt.com/backend/public/nf2/feed` через **Zenrows premium_proxy** → фільтрує `unique_view_count > 1000` (вже віральні) → скіпає вже репостовані (`used_posts.txt`) → завантажує mp4 → витягає 3 кадри (20%/50%/80% timepoints) → **GPT-4o-mini Vision** описує кожен кадр (емоція, атмосфера, підтекст у 2-3 реченнях) → **GPT-4o-mini** генерує meme-caption (1-2 речення, іронічний легкий тон українською) → ще один GPT-4o-mini виклик повертає JSON `{title ≤70, description, hashtags ≤15, first_comment}` (з retry до 5 спроб якщо JSON parse fail) → strip emojis (Unicode ranges 1F300-1FAFF, 2600-26FF, 2700-27BF), wordwrap 40 chars → **ffmpeg drawtext** накладає підпис знизу-центру (DejaVuSans-Bold 32px, чорний бокс на 50% прозорості, padding 12) → INSERT в `tasks` × 3 на день у [12:00, 14:00, 17:00].

### 1.5 News pipeline (RBC RSS → Shorts/Long video)
- Long: тягне перший непрочитаний news з `rbc.ua/static/rss/all.ukr.rss.xml` (історія в `rbc_used_links.txt`) → **SerpAPI Google Images** шукає 5 фото за title (`width >= 1200`, jpg only) → завантажує в `images/` → **TTS news-style** озвучує `fulltext` → **make_srt.py** генерує синхронізовані субтитри з audio.mp3 + text.txt → **`makeYoutubeVideoFrom5Images`**: 5 фото з **Ken Burns** ефектом (`zoompan=z='1+0.00012*on'`), `duration/5` сек на фото, scale 1920×1080 → INSERT в `tasks`.
- Shorts: те ж саме але `description` (короткий) + scale 1080×1920 + `addSubtitlesToShorts` burn-in (Arial 14px, white з чорною обводкою 4px, MarginV=160, Alignment=2) → `shorts_final.mp4`.

### 1.6 Live streaming (9 systemd units)
9 ffmpeg-concat плейлистів `*.mp4` лються в RTMP YouTube Live з `-stream_loop -1` (нескінченний цикл відео). systemd `Restart=on-failure RuntimeMaxSec=42900` (~12 годин — YouTube Live ліміт). Frontend `/stream/` — реактивна адмінка (5-сек polling) з фільтрами/пошуком/bulk-діями (Start/Stop/Restart ALL), CSRF, log modal через `journalctl`. Створення нового стріму викликає `sudo -n php yii yt/sync-one --id={N}` що генерує `.env`+systemd unit ідемпотентно. YouTube Live API через `YoutubeService::prepareBroadcastForStart` — ensure broadcast → `findLiveStreamIdByStreamKey` (paginate 6 сторінок liveStreams) → `bindBroadcastToStream` → updateMeta → setThumbnail → `transitionBroadcast(live)`.

### 1.7 YouTube статистика (daily snapshots)
`Youtube_statsController::actionStat` бере `YoutubeChannels::find()->where(['stat'=>1])` → `resolveChannelId` (UC-id pass-through; `@handle` через `forHandle` API; fallback `search?type=channel`) → `fetchChannelStats` (`channels?part=statistics`) → UPSERT в `youtube_channel_daily` (key = `(channel_id, snapshot_date)`).

### 1.8 Web UI / OAuth
- **Frontend**: standard Yii signup/login/email-verify/contact + кастомний `/stream/` (live-status polling, bulk start/stop) + `/youtube-oauth/oauth` (Google OAuth 2.0 з CSRF state, scopes `youtube + youtube.upload`).
- **Backend**: тільки login (admin-only landing). Бізнес-логіки нема — все через CLI.

### 1.9 Робоча модель: таблиця `tasks`
Все що генерує PHP — складає в `content_fabric.tasks` як рядок з `att_file_path` (mp4), `cover` (jpg), `title/description/keywords/post_comment`, `account_id` (FK на `youtube_account.id`), `media_type='youtube'`, `status=0`, `date_post` (запланована дата). Зовнішня черга (раніше — Yii task processor; зараз — Content Fabric Python воркер `cff-publishing-worker`) забирає → публікує на YouTube через OAuth refresh_token.

---

## 2. Повне дерево файлів

```
/var/www/fastuser/data/www/aiyoutube.pbnbots.com/
├── composer.phar                                3.0 MB
├── data/                                          8.2 GB  (виключено з аналізу — runtime media)
├── index.php                                       28 KB  (legacy mobile-first router, не Yii)
├── python_scripts/
│   └── tts_openai/
│       ├── tts_openai.py                          105 рядків  (OpenAI TTS wrapper)
│       └── tts_openai/                            (venv для TTS — виключено)
└── yii/                                          12 MB (без vendor/venv/runtime)
    ├── LICENSE.md, README.md, Vagrantfile         (Yii2 boilerplate)
    ├── codeception.yml                            (test config)
    ├── composer.json                              57 рядків  (4 prod deps + 8 dev)
    ├── composer.lock
    ├── docker-compose.yml                         (не використовується на проді)
    ├── environments/
    │   ├── index.php                              (Yii init dispatcher)
    │   ├── dev/{backend,common,console,frontend}/config/{*-local.php}
    │   └── prod/{backend,common,console,frontend}/config/{*-local.php}
    ├── init                                       (init bash)
    ├── init.bat                                   (init Windows)
    ├── requirements.php                           (PHP requirements check)
    ├── shel_youtube.sh                            19 рядків  ⚡ CRON: stats + DLE/sora/news uploads
    ├── shel_youtube_news.sh                        3 рядки   ⚡ CRON: news/shorts 55
    ├── shel_youtube_shorts_from_video.sh           3 рядки   ⚡ CRON: shorts_from_video/shorts_from_donors 28
    ├── shel_youtube_time.sh                       12 рядків  ⚡ CRON: масовий <source>/shorts <acc>
    ├── shel_youtube_time_2.sh                      3 рядки   ⚡ CRON: slushat_knigi_com/shorts 25
    ├── mass_create_streams.sh                    314 рядків  ⚡ Bash-аналог StreamProvisionerService
    ├── yii, yii.bat                               (Yii CLI launchers)
    ├── yii_test, yii_test.bat                     (testing CLI launchers)
    ├── cookies.txt, cookies_28.txt                (YouTube session cookies для yt-dlp)
    │
    ├── backend/                                  ━━━━━━━━━━ ADMIN PANEL (мінімальний)
    │   ├── assets/AppAsset.php                    (CSS+JS бандл для админки)
    │   ├── config/{bootstrap.php, main.php, main-local.php, params.php, params-local.php,
    │   │           codeception-local.php, test.php, test-local.php}
    │   ├── controllers/SiteController.php         105 рядків  (тільки login + index)
    │   ├── tests/{...}                            (LoginCest functional)
    │   ├── views/
    │   │   ├── layouts/{blank.php, main.php}      (blank — для login екрану)
    │   │   └── site/{error.php, index.php, login.php}
    │   └── web/{index.php, index-test.php}
    │
    ├── common/                                   ━━━━━━━━━━ SHARED CODE
    │   ├── components/MyFunction.php             1377 рядків  ⭐ 50+ статичних утиліт
    │   ├── config/{bootstrap.php, main.php, params.php, ...}
    │   ├── fixtures/UserFixture.php
    │   ├── mail/                                  (Email шаблони)
    │   │   ├── emailVerify-html.php
    │   │   ├── emailVerify-text.php
    │   │   ├── passwordResetToken-html.php
    │   │   ├── passwordResetToken-text.php
    │   │   └── layouts/{html.php, text.php}
    │   ├── models/                               ━━━━ Active Record моделі
    │   │   ├── GoogleConsoles.php                 95 рядків   (google_consoles)
    │   │   ├── LoginForm.php                      79 рядків   (login form з validatePassword)
    │   │   ├── Stream.php                        133 рядки   ⭐ (stream + slugify + runner_path whitelist)
    │   │   ├── Tasks.php                          77 рядків   ⭐ (tasks — основна черга)
    │   │   ├── User.php                          213 рядків   (user + password reset/email verify tokens)
    │   │   ├── YoutubeAccount.php                 42 рядки    (youtube_account — legacy)
    │   │   ├── YoutubeChannelDaily.php            63 рядки    (youtube_channel_daily — stats snapshots)
    │   │   └── YoutubeChannels.php                83 рядки    (youtube_channels — нова схема)
    │   ├── services/                             ━━━━ Бізнес-сервіси
    │   │   ├── StreamProvisionerService.php      175 рядків   ⭐ (sync env+systemd unit для стрімів)
    │   │   ├── SystemdService.php                180 рядків   ⭐ (systemctl start/stop/status/tail wrapper)
    │   │   ├── YoutubeLiveService.php            159 рядків   (legacy minimal API — transition/refresh)
    │   │   └── YoutubeService.php                381 рядок   ⭐ (FULL YouTube Data API client)
    │   ├── tests/{...}                            (LoginFormTest)
    │   └── widgets/Alert.php                      77 рядків   (Bootstrap5 Alert wrapper для flash messages)
    │
    ├── console/                                  ━━━━━━━━━━ CRON / CLI PIPELINES
    │   ├── config/{bootstrap.php, main.php, params.php, ...}
    │   ├── controllers/                          ━━━━ ВСЯ БІЗНЕС-ЛОГІКА
    │   │   ├── ChatGPT.php                        92 рядки    (ДЕПРЕКЕЙТЕД OpenAI wrapper з зашитим ключем)
    │   │   ├── google-search-results.php         304 рядки    (SerpAPI client lib — для News)
    │   │   ├── restclient.php                    278 рядків   (SerpAPI HTTP helper)
    │   │   ├── Audiokniga_one_comController.php  778 рядків   ⭐ DLE: audiokniga-one.com
    │   │   ├── Bazaknig_netController.php        804 рядки    ⭐ DLE: bazaknig.net
    │   │   ├── Books_online_infoController.php   972 рядки    ⭐ DLE: books-online.info
    │   │   ├── Club_books_ruController.php       821 рядок    ⭐ DLE: club-books.ru
    │   │   ├── Knigi_online_clubController.php   500 рядків   ⭐ DLE: knigi-online.club (full-text)
    │   │   ├── Slushat_knigi_comController.php   812 рядків   ⭐ DLE: slushat-knigi.com (upload disabled)
    │   │   ├── Unique_audioController.php        825 рядків   ⭐ DLE: knigi-audio.biz (попаданцы)
    │   │   ├── NewsController.php                1049 рядків  ⭐ RBC RSS → Shorts/Long
    │   │   ├── Shorts_from_videoController.php   434 рядки    ⭐ YT donor → Whisper → 5 highlights
    │   │   ├── Stream_youtubeController.php      464 рядки    (~ Shorts_from_video дублікат + actionUpload_yt)
    │   │   ├── SoraController.php                672 рядки    ⭐ Sora feed → meme caption Shorts
    │   │   ├── StreamController.php              149 рядків   (HTTP-style start/stop/restart broadcast)
    │   │   ├── Youtube_statsController.php       178 рядків   (daily channels statistics)
    │   │   ├── YtController.php                  317 рядків   ⭐ sync-one + mass-sync-services (provisioning)
    │   │   └── shorts_from_video/                ━━━━ Python venv для shorts pipeline
    │   │       ├── shorts_from_video.py          514 рядків   ⭐ ОСНОВНИЙ: yt-dlp+Whisper+GPT-4o+ffmpeg
    │   │       └── yt-dlp/
    │   │           ├── shorts_from_video.py       (дублікат-копія)
    │   │           └── update_youtube_cookies.py 282 рядки    (3 fallback методи refresh)
    │   ├── migrations/
    │   │   ├── m130524_201442_init.php             (User table init)
    │   │   └── m190124_110200_add_verification_token_column_to_user_table.php
    │   └── models/                               ━━━━ DLE Active Records (за 7 джерелами)
    │       ├── audiokniga_one_com/{DlePost.php, DlePostExtras.php, DlePostExtrasCats.php,
    │       │                       DleCategory.php, DleTags.php, *.json}
    │       ├── bazaknig_net/{...}                 (5 моделей)
    │       ├── books_online_info/{...}            (5 моделей)
    │       ├── club_books_ru/{...}                (5 моделей)
    │       ├── knigi_audio_biz/{...}              (4 моделі — без DleTags)
    │       ├── knigi_online_club/{...}            (5 моделей)
    │       └── slushat_knigi_com/{...}            (5 моделей)
    │
    ├── frontend/                                 ━━━━━━━━━━ PUBLIC + STREAM CONTROL UI
    │   ├── assets/AppAsset.php                    (CSS+JS бандл)
    │   ├── config/{bootstrap.php, main.php, params.php, ...}
    │   ├── controllers/
    │   │   ├── SiteController.php                ~265 рядків  (login/signup/contact/email-verify)
    │   │   ├── StreamController.php              367 рядків   ⭐ Stream UI: index/status/start/stop/restart/tail/create/sync
    │   │   └── YoutubeOauthController.php        170 рядків   (Google OAuth 2.0 з CSRF state)
    │   ├── models/                               ━━━━ Form моделі
    │   │   ├── ContactForm.php                    62 рядки
    │   │   ├── PasswordResetRequestForm.php
    │   │   ├── ResetPasswordForm.php
    │   │   ├── ResendVerificationEmailForm.php
    │   │   ├── SignupForm.php                     81 рядок
    │   │   └── VerifyEmailForm.php
    │   ├── tests/{...}                            (Cest acceptance + functional + unit)
    │   ├── views/
    │   │   ├── layouts/main.php
    │   │   ├── site/{about, contact, error, index, login, requestPasswordResetToken,
    │   │   │       resendVerificationEmail, resetPassword, signup}.php
    │   │   └── stream/{create.php, index.php}    ⭐ index — реактивна адмінка з 5s polling
    │   └── web/{index.php, index-test.php}
    │
    └── vagrant/provision/{always-as-root.sh, common.sh, once-as-root.sh, once-as-vagrant.sh}
                                                  (Vagrant scripts — не на проді)
```

---

## 3. Технологічний стек і архітектура

### 3.1 Server stack
| Шар | Версія / опис |
|---|---|
| OS | Linux (FastUser shared hosting, Cloudways-style) |
| Web server | nginx + PHP-FPM (PHP 8.0+) |
| PHP | ≥7.4 (composer.json `"php": ">=7.4.0"`) — фактично 8.x |
| MariaDB (local) | проект `content_fabric` — версію не визначено |
| MariaDB (DLE × 7) | **5.5.68** — старий, без TLS, `charset=utf8mb4` НЕ підтримується |
| Cache | `\yii\caching\FileCache` (один rate-limited file cache) |
| systemd | для 9 stream units + 5 CFF workers |
| ffmpeg | системний (не контейнеризований) |
| Python | venv в `python_scripts/tts_openai/` (TTS), venv в `yii/venv/` (shorts pipeline) — pip пакети: openai, yt-dlp, ffmpeg-python, browser_cookie3, playwright, selenium |

### 3.2 Yii2 Application Layout (advanced template)
- **`backend/`** — admin panel (login only, blank ConfigSet)
- **`frontend/`** — публічний фронт + Stream Control UI + OAuth flow
- **`console/`** — CLI controllers (всі pipeline'и)
- **`common/`** — спільні моделі / сервіси / утиліти
- **`environments/{dev,prod}/`** — env-specific overlays для `*-local.php` (підставляються `php yii migrate` чи через Yii's environments tool)

### 3.3 Запит-відповідь flow (web)
```
nginx → /yii/frontend/web/index.php
         ↓
       require Yii.php (через vendor/autoload)
         ↓
       new yii\web\Application(merge(common/main, common/main-local, frontend/main, frontend/main-local))
         ↓
       Application.run() → routes → controller/action → view → Response
```

### 3.4 Cron flow (CLI)
```
crontab → bash shel_youtube*.sh
            ↓
          cd /var/www/.../yii
          php yii <controller>/<action> <args>
            ↓
          new yii\console\Application(merge(common/main, common/main-local, console/main, console/main-local))
            ↓
          Yii::$app->runAction("<controller>/<action>", [args])
            ↓
          Action виконується, INSERT в `tasks`, потім exit
```

### 3.5 Black-box модель між шарами
```
DLE-сайти             ┐                              ┌→ youtube_account.refresh_token
(7 MySQL)             │                              │
                      │   PHP cron                   │
YouTube Data API      ┤  (php yii ...) ─────────────►│ YouTube Data API
(donor channels)      │     ↓                        │ (upload, broadcasts)
                      │   ffmpeg                     │
sora.chatgpt.com      │     ↓                        │
(via Zenrows)         ┤  /opt/content-fabric/        │
                      │     prod/cli.voice           │
RBC RSS               │     ↓                        │
                      │   INSERT tasks               │
SerpAPI               │     ↓                        │
                      ┘   `tasks` queue ─────────────► CFF publishing worker
                                                    (Python, читає тасі і завантажує на YT)
```

---

## 4. Точки входу і життєвий цикл

### 4.1 Web entry points

| URL pattern | Handler | Auth |
|---|---|---|
| `/` (frontend) | `frontend\controllers\SiteController::actionIndex` | guest+auth |
| `/site/login`, `/signup`, `/contact`, `/about` | site/* | guest |
| `/site/logout` | site/logout (POST) | auth |
| `/site/request-password-reset`, `/reset-password/{token}`, `/verify-email/{token}`, `/resend-verification-email` | site/* | guest |
| **`/stream/index`** | StreamController::actionIndex | auth (`@`) |
| **`/stream/status`** (GET, JSON) | StreamController::actionStatus | auth |
| **`/stream/start`** (POST) | actionStart | auth (CSRF) |
| **`/stream/stop`** (POST) | actionStop | auth |
| **`/stream/restart`** (POST) | actionRestart | auth |
| **`/stream/tail?id=N&lines=40`** | actionTail (journalctl) | auth |
| **`/stream/debug?id=N`** | actionDebug (sanity) | auth |
| **`/stream/create`** | actionCreate (форма + auto-sync) | auth |
| **`/stream/sync`** (POST) | actionSync (yt/sync-one) | auth |
| **`/youtube-oauth/oauth?account_id=N`** | YoutubeOauthController (start + callback) | guest (CSRF в state) |
| `/admin/site/login` (backend) | backend\SiteController::actionLogin | guest |
| `/admin/site/index` | backend\SiteController::actionIndex | auth |
| `/admin/site/logout` (POST) | actionLogout | auth |

Backend і frontend живуть на ОДНОМУ домені, але окремі базові URL'и:
- `https://aiyoutube.pbnbots.com/yii/frontend/web/index.php?r=stream/index`
- `https://aiyoutube.pbnbots.com/yii/backend/web/index.php?r=site/index`

### 4.2 CLI entry points (через `php yii`)

Команди (формат `<controller>/<action> [args]`):

```
audiokniga_one_com/upload_to_youtube [limit=1] [id_yt_acc=5] [test=false]
audiokniga_one_com/shorts [id_yt_acc=5]
audiokniga_one_com/test

bazaknig_net/upload_to_youtube [limit=1] [id_yt_acc=26]
bazaknig_net/shorts [id_yt_acc=26]

books_online_info/upload_to_youtube [limit=1] [id_yt_acc=5]
books_online_info/upload_to_youtube_txt_file [limit=1] [id_yt_acc=5]   ← full-text
books_online_info/shorts [id_yt_acc=21]

club_books_ru/upload_to_youtube [limit=1] [id_yt_acc=5]
club_books_ru/shorts [id_yt_acc=21]

knigi_online_club/upload_to_youtube_txt_file [limit=1] [id_yt_acc=12]   ← головний flow

slushat_knigi_com/upload_to_youtube ← exit; на початку (вимкнено)
slushat_knigi_com/upload_to_youtube_txt_file
slushat_knigi_com/shorts [id_yt_acc=25]

unique_audio/upload_to_youtube [limit=1] [id_yt_acc=6]
unique_audio/shorts [id_yt_acc=6]
unique_audio/test

news/upload_to_youtube [limit=1] [id_yt_acc=55]
news/shorts [id_yt_acc=55]
news/test

shorts_from_video/shorts_from_donors [id_yt_acc=31]
shorts_from_video/shorts [id_yt_acc=28] [channel_link]

stream_youtube/upload_yt
stream_youtube/shorts_from_donors [id_yt_acc=31]
stream_youtube/shorts [id_yt_acc=28] [channel_link]

sora/get_video [channel_id=19]
sora/shorts [id_yt_acc=19] [video_path] [post_id] [modelDate]
sora/test

stream/start (потребує id у GET/POST)
stream/stop
stream/restart

yt/sync-one --id={N} [--restart=0] [--enable=0]
yt/mass-sync-services [--restart=1] [--enable=1]

youtube_stats/stat
youtube_stats/show_compare
```

### 4.3 Cron-розклад (з shell-скриптів)

| Файл | Що робить (точна послідовність) |
|---|---|
| `shel_youtube.sh` | `youtube_stats/stat` → `unique_audio/upload_to_youtube 3 6` → `unique_audio/shorts 6` → `audiokniga_one_com/shorts 5` → `audiokniga_one_com/upload_to_youtube 1 5` → ~~`sora/get_video 19, 20`~~ (закоментовано) → `club_books_ru/upload_to_youtube 1 21` → `books_online_info/upload_to_youtube 1 23` → `bazaknig_net/upload_to_youtube 2 26, 3 27, 3 29, 3 30, 3 32, 3 47, 3 48` → `news/upload_to_youtube 1 55` |
| `shel_youtube_news.sh` | `news/shorts 55` |
| `shel_youtube_shorts_from_video.sh` | `shorts_from_video/shorts_from_donors 28` (квадроцикли) |
| `shel_youtube_time.sh` | `club_books_ru/shorts 21` → `books_online_info/shorts 23` → `bazaknig_net/shorts 26, 27, 29, 30, 32, 33, 47, 48` |
| `shel_youtube_time_2.sh` | `slushat_knigi_com/shorts 25` |

Реальний cron на проді (з `crontab -l`) додає таймінги — типово такі скрипти запускаються щодоби або 2-3 рази на день. Точні `crontab` лежать у backup `/backup/crontab.bak`.

---

## 5. Хардкоджені паролі/ключі/шляхи (БЕЗПЕКА)

**ВСІ ці ключі ВЖЕ зливаються через GitHub якщо commit'нути код.** Перш ніж публікувати — revoke кожен.

### 5.1 OpenAI API keys

```
<REDACTED:OPENAI_KEY>
```
**ПОВТОРЮЄТЬСЯ в:**
- `Shorts_from_videoController::api_key` (рядок 22)
- `Stream_youtubeController::api_key` (рядок 22)
- `SoraController::api_gpt` (рядок 22)
- `Audiokniga_one_comController::actionTts_openai::api_gpt` (line 739)
- `Bazaknig_netController::actionTts_openai::api_gpt` (line 745)
- `Books_online_infoController::actionTts_openai::api_gpt` (line 911)
- `Club_books_ruController::actionTts_openai::api_gpt` (line 760)
- `Knigi_online_clubController::actionTts_openai::api_gpt` (line 441)
- `Slushat_knigi_comController::actionTts_openai::api_gpt` (line 751)
- `Unique_audioController::actionTts_openai::api_gpt` (line 785)
- `NewsController::actionTts_openai::api_gpt` (line 853)
- `python_scripts/tts_openai/tts_openai.py` (через ENV у генерованому .sh)
- `shorts_from_video.py` — рядок 11 (через `os.getenv` АЛЕ з literal default value):
  ```python
  openai.api_key = os.getenv("<REDACTED:OPENAI_KEY>")  # ← це 100% bug, треба було os.getenv("OPENAI_API_KEY", default)
  ```

**Старий злитий ключ:**
```
<REDACTED:OPENAI_KEY_OLD>  (ChatGPT.php — приватна змінна)
```

### 5.2 Google Cloud API keys (YouTube Data API)
```
<REDACTED:GOOGLE_API_KEY_SHORTS>   (Shorts_from_video, Stream_youtube — channelId search)
<REDACTED:GOOGLE_API_KEY_STATS>   (Youtube_stats — daily snapshot)
<REDACTED:GOOGLE_API_KEY_NEWS>   (NewsController — Custom Search)
```

### 5.3 Google Custom Search Engine ID
```
CX = <REDACTED:GOOGLE_CX>   (NewsController.googleImagesSearch)
```

### 5.4 Zenrows API (1 ключ для всього)
```
<REDACTED:ZENROWS_KEY>
```
Використовується в `MyFunction.getHtml_zenrows`, `getHtml_zenrows_2` (з `premium_proxy=true`), `postHtml_zenrows` (через `proxy.zenrows.com:8001`), `downloadFile_zenrows`. Обидва Sora pipeline і будь-який інший CDN bypass проходять тут.

### 5.5 SerpAPI (Google Images)
```
<REDACTED:SERPAPI_KEY>   (NewsController.rest_api_search_images)
```

### 5.6 DeepL Translate
```
<REDACTED:DEEPL_KEY>   (MyFunction.translate_deepl)
```

### 5.7 Proxy authentication
```
proxyauth = '<REDACTED:PROXY_AUTH>'   (MyFunction.get_html_proxy)
```

### 5.8 Cookies/session/legacy
```
<REDACTED:1lib.org session cookies (remix_userkey, remix_userid) — MyFunction.downloadFile_post>
<REDACTED:booknet.ua session cookies (litera-frontend, _csrf, ref, ...) — MyFunction.get_html_test1>
<REDACTED:lib.tech session cookies — у MyFunction headers>
```

### 5.9 Service Account JSON
- `yii/console/models/audiokniga_one_com/audiokniga-one-com-46ac50021541.json`
  - Google Cloud service account (project_id, private_key, client_email, token_uri)
  - Призначення невідоме (видимий код не використовує — можливо для Sheets чи Drive)

### 5.10 DLE database credentials (паролі)
В `console/config/main-local.php`:
```
db_audiokniga_one_com:  audiokniga_one_com_u:<REDACTED>@185.154.15.251:3310/audiokniga_one_com_db
db_knigi_audio_biz:     knigiaudiobiz_u:<REDACTED>@77.220.213.172:3306/knigi_audio_biz_db
db_club_books_ru:       club_books_ru_u:<REDACTED>@185.244.217.9:3311/club_books_ru_db
db_books_online_info:   booksonlineinfo:<REDACTED>@91.211.251.57:3306/booksonlineinfo
db_slushat_knigi_com:   slushat_knigi_com_u:<REDACTED>@80.85.141.91:3310/slushat_knigi_com_db
db_knigi_online_club:   knigi_online_club_u:<REDACTED>@185.224.133.132:3310/knigi_online_club_db
db_bazaknig_net:        bazaknig_net_u:<REDACTED>@185.224.133.132:3310/bazaknig_net_db
```

Усі — `@%` host (відкриті назовні з будь-якого IP), MariaDB 5.5.68 — критично застарілий, без TLS.

### 5.11 Хардкоджені шляхи (всюди)

| Шлях | Призначення |
|---|---|
| `/var/www/fastuser/data/www/aiyoutube.pbnbots.com` | $PROJECT_BASE — у 90% файлів |
| `…/data/<source>/` | робоча папка кожного DLE-pipeline'у |
| `…/data/<source>/shorts/quotes.txt` | seed для DLE shorts |
| `…/data/<source>/backgrounds/*.{jpg,jpeg,png,webp}` | випадкові фони для cover |
| `…/data/<source>/shorts/bg_music/*.mp3` | випадкова bg музика для shorts |
| `…/data/<source>/shorts/fonts/lena.ttf` | шрифт для ASS subtitles |
| `…/data/shorts_from_video/{youtube_links_<id>.txt, youtube_links_done_<id>.txt, transcript_<id>.json, shorts_meta_<id>.json, audio_<id>.wav, input_<id>.mp4, shorts_<id>/, thumbnails_<id>/, fonts/lena.ttf}` | shorts pipeline state |
| `…/data/sora/shorts/{used_posts.txt, frame_*.jpg, frames_description.txt, sora_<id>_shorts.mp4}` | sora state |
| `…/data/news/{rbc_used_links.txt, images/*.jpg, audio.mp3, sub.srt, text.txt, shorts.mp4, shorts_final.mp4, youtube_video.mp4, make_srt.py}` | news state |
| `…/data/streams/<name>/{videos/*.mp4, videos/playlist.txt, env.conf, yt_stream_runner.sh}` | live-стрім файли |
| `…/yii/cookies.txt`, `cookies_28.txt` | YouTube cookies для yt-dlp |
| `…/yii/venv/bin/python3` | shorts pipeline Python |
| `…/python_scripts/tts_openai/tts_openai/bin/activate` | TTS Python venv |
| `/etc/aiyoutube/streams/<name>.env` | systemd EnvironmentFile (StreamProvisioner) |
| `/etc/systemd/system/stream-<name>.service` | systemd unit file |
| `/usr/local/bin/yt_stream_runner.sh` | глобальний bash runner для всіх стрімів |
| `/opt/content-fabric/prod` | CFF (виклики `cli.voice` для unique audio) |
| `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` | системний шрифт для drawtext |
| `__DIR__ . '/bebasneuecyrillic.ttf'` | основний бренд-шрифт для cover (~поряд з контролерами) |

---

## 6. Composer dependencies

`composer.json` (зі стрипованих `require` та `require-dev`):

### 6.1 Production
| Пакет | Версія | Призначення |
|---|---|---|
| `php` | `>=7.4.0` | мінімум (фактично 8.x) |
| `yiisoft/yii2` | `~2.0.45` | Yii2 framework |
| `yiisoft/yii2-bootstrap5` | `~2.0.2` | Bootstrap 5 widgets (`Alert`, `ActiveForm`, etc.) |
| `yiisoft/yii2-symfonymailer` | `~2.0.3` | Email (Symfony Mailer wrapper) |
| `google/apiclient` | `^2.0` | Google API SDK (для Service Account JSON, не використовується у видимому коді) |

### 6.2 Implicitly imported (через use statements у controllers)
| Пакет | Звідки використовується |
|---|---|
| `phpseclib3\Net\SFTP` | `use phpseclib3\Net\SFTP;` у всіх console controllers (НЕ використовується в read коді — артефакт) |
| `yii2tech\spreadsheet` | `use yii2tech\spreadsheet\Spreadsheet;` (також не використовується) |
| `yii\imagine\Image` | image processing (не використовується явно) |
| `simplehtmldom` | `str_get_html($body)` у `MyFunction::get_epub_text` |
| `tidy` | `\tidy` extension для `MyFunction::get_tidy_pages` |

### 6.3 Dev/Tests
- `yiisoft/yii2-debug` ~2.1.0 — debug toolbar
- `yiisoft/yii2-gii` ~2.2.0 — code generator
- `yiisoft/yii2-faker` ~2.0.0 — fixtures
- `phpunit/phpunit` ~9.5.0
- `codeception/codeception` ^5.0 / ^4.0
- `codeception/lib-innerbrowser` ^4.0/^3.0/^1.1
- `codeception/module-asserts` ^3.0/^1.1
- `codeception/module-yii2` ^1.1
- `codeception/module-filesystem` ^3.0/^2.0/^1.1
- `codeception/verify` ^3.0/^2.2

### 6.4 Repositories
```json
"repositories": [
  { "type": "composer", "url": "https://asset-packagist.org" }
]
```
— для bower-asset / npm-asset (Yii2 pre-2.0.45 patterns).

---

## 7. Конфігураційні файли

### 7.1 Структура

Yii2 advanced template merge'ить 4 рівні:
```
common/config/params.php
  → common/config/params-local.php
    → console/config/params.php
      → console/config/params-local.php (gitignored, env-specific)
```
Те ж саме для `main.php`. Версія `*-local.php` — це override після `init` команди.

### 7.2 `common/config/params.php` (boilerplate)

```php
return [
    'adminEmail' => 'admin@example.com',
    'supportEmail' => 'support@example.com',
    'senderEmail' => 'noreply@example.com',
    'senderName' => 'Example.com mailer',
    'user.passwordResetTokenExpire' => 3600,
    'user.passwordMinLength' => 8,
];
```
Все default. На проді ймовірно overwrite через `params-local.php` (не у видимій частині — gitignored).

### 7.3 `common/config/main.php` (мінімальне налаштування)

```php
return [
    'aliases' => [
        '@bower' => '@vendor/bower-asset',
        '@npm'   => '@vendor/npm-asset',
    ],
    'vendorPath' => dirname(dirname(__DIR__)) . '/vendor',
    'components' => [
        'cache' => ['class' => \yii\caching\FileCache::class],
    ],
];
```

### 7.4 `console/config/main.php`

```php
return [
    'id' => 'app-console',
    'basePath' => dirname(__DIR__),
    'bootstrap' => ['log'],
    'controllerNamespace' => 'console\controllers',
    'aliases' => [
        '@bower' => '@vendor/bower-asset',
        '@npm'   => '@vendor/npm-asset',
    ],
    'controllerMap' => [
        'fixture' => [
            'class' => \yii\console\controllers\FixtureController::class,
            'namespace' => 'common\fixtures',
        ],
    ],
    'components' => [
        'log' => [
            'targets' => [
                ['class' => \yii\log\FileTarget::class, 'levels' => ['error', 'warning']],
            ],
        ],
    ],
    'params' => $params,  // merged
];
```

### 7.5 `*-local.php` (gitignored, env-specific)

Тут зберігаються:
- DB connection (`db`, `db_audiokniga_one_com`, `db_bazaknig_net`, ... 7 з'єднань)
- mailer credentials (SMTP host/user/password)
- cookieValidationKey
- request/response config
- urlManager (pretty URLs, якщо потрібно)
- sentry/log targets

Конкретний вміст не у видимій частині — він на проді в `*-local.php` файлах. Backup треба робити окремо.

### 7.6 `environments/{dev,prod}/`

Шаблони для `init` команди — копіюються в активні `*-local.php` під час setup. На проді запускався `php /init --env=Production`.

---

## 8. Frontend layer (web UI)

### 8.1 `frontend\controllers\SiteController` (~265 рядків)

Стандартний Yii2 advanced template SiteController. AccessControl: `signup` лише для guest (`?`), `logout` лише для auth (`@`). VerbFilter: `logout` тільки POST. Action map: `error` → `\yii\web\ErrorAction`, `captcha` → `\yii\captcha\CaptchaAction` (для ContactForm).

#### Actions

| Action | Method | Behavior |
|---|---|---|
| `actionIndex()` | GET | Render `views/site/index.php` (Yii boilerplate з трьома "Heading" блоками — НЕ кастомізовано). |
| `actionLogin()` | GET/POST | Якщо `!user->isGuest` → goHome(). Інакше new LoginForm; якщо POST та `$model->login()` повертає true → goBack(). На фейлі — clear password, render. |
| `actionLogout()` | POST | `Yii::$app->user->logout()` → goHome(). |
| `actionContact()` | GET/POST | new ContactForm; якщо validate, `sendEmail($params['adminEmail'])`. setFlash 'success'/'error'. |
| `actionAbout()` | GET | render `views/site/about.php` |
| `actionSignup()` | GET/POST | new SignupForm; `$model->signup()` → success flash → goHome. |
| `actionRequestPasswordReset()` | GET/POST | new PasswordResetRequestForm; `$model->sendEmail()` → setFlash + goHome. |
| `actionResetPassword($token)` | GET/POST | `new ResetPasswordForm($token)` (constructor throws InvalidArgumentException → BadRequestHttpException). |
| `actionVerifyEmail($token)` | GET | `new VerifyEmailForm($token)` → `$model->verifyEmail()` → setFlash + goHome. |
| `actionResendVerificationEmail()` | GET/POST | `$model->sendEmail()`. |

### 8.2 `frontend\controllers\StreamController` (367 рядків) ⭐

**Це критичний контролер** — реактивна адмінка живих стрімів.

#### `behaviors()`
- AccessControl: всі дії — auth (`['allow' => true, 'roles' => ['@']]`)
- VerbFilter: `start, stop, restart` → POST; `status, tail, debug, auth` → GET
- `beforeAction()`: для `[status, tail, start, stop, restart, debug]` — `Yii::$app->response->format = JSON`

#### `actionIndex()`
```php
$streams = Stream::find()->where(['enabled' => 1])->orderBy(['id' => SORT_ASC])->all();
return $this->render('index', ['streams' => $streams]);
```

#### `actionStatus(): array`
Для кожного `Stream::find()->where(['enabled'=>1])` викликає `SystemdService::status($s->service_name)`. Returns:
```php
['ok' => true, 'data' => [
    [
        'id' => 7, 'yid' => 5, 'name' => 'audiokniga-one',
        'channel' => 'AudioKniga One', 'service' => 'stream-audiokniga-one.service',
        'stream_key' => 'xxxx-xxxx-xxxx-xxxx',
        'workdir' => 'audiokniga-one',  // ← strip /var/www/.../data/streams/ prefix
        'runner_path' => 'yt_stream_runner.sh',  // basename
        'status' => [
            'unit', 'active' => true, 'activeState' => 'active', 'subState' => 'running',
            'pid' => 1234, 'since_ts' => 1714838400, 'runtime_max_sec' => 42900,
            'elapsed_sec' => 3600, 'remaining_sec' => 39300, 'end_ts' => 1714881300, 'code' => 0
        ]
    ]
], 'ts' => 1714842000]
```

#### `actionTail($id, $lines=40): array`
- `Stream::findOne($id)` або 404
- `SystemdService::tail($model->service_name, $lines)` → `journalctl -u {unit} -n {lines} --no-pager -o short-iso`
- return `['ok' => true, 'log' => $log_text]`

#### `actionStart()`: повна послідовність
1. POST `id` parameter, або `['ok' => false, 'error' => 'Missing id']`
2. `Stream::findOne($id)`; перевірка `enabled=1`
3. `YoutubeAccount::findOne($stream->youtube_account_id)`
4. Збір meta:
   ```php
   $meta = [
       'title' => $stream->yt_title ?: $stream->name,
       'description' => $stream->yt_description ?? '',
       'tags' => $stream->yt_tags ? preg_split('/\s*,\s*/', $stream->yt_tags) : [],
       'privacy' => 'public',
       'thumbnail' => !empty($stream->yt_thumbnail) ? $stream->yt_thumbnail : null,
   ];
   ```
5. `$svc = new SystemdService(true);`
6. `$stNow = $svc->status($service_name)`; `$isRunning = (activeState==='active' && subState==='running')`
7. **Try-catch блок:**
   ```php
   $yt = new YoutubeService();
   $prep = $yt->prepareBroadcastForStart($acc, $stream, $meta);
   if (!$isRunning) {
       [$code, $out] = $svc->start($service_name);
       if ($code !== 0) return jsonFail("systemctl start failed ($code)", ['output' => $out]);
   }
   $st = $svc->status($service_name);
   ```
8. Return JSON з `['youtube_broadcast_id', 'youtube_stream_id' => $prep['streamId'], 'systemd' => ['was_running', 'status'], 'meta_applied' => ['title','tags_count','thumbnail'], 'ts']`.

#### `actionStop()`
1. POST id; Stream::findOne; SystemdService.
2. **Optional**: `transitionBroadcast($acc, $bid, 'complete')` — у try-catch.
   - **bug**: код читає `$stream->youtube_account` замість `youtube_account_id` — отже завжди skipped.
3. `$svc->stop($service_name)` → returns full status JSON.

#### `actionRestart()`
- Тільки `$svc->restart($service_name)` — без YouTube transition.

#### `actionCreate()`
1. validate model (slug, service_name auto-fill через beforeValidate)
2. **Створити дирки:**
   ```php
   ensureDir($workdir);
   ensureDir($videosDir);
   if (!is_file("$videosDir/playlist.txt")) file_put_contents($playlist, "");
   chmod($playlist, 0664);
   ```
3. `$model->save()`
4. **Виклик:** `sudo -n /usr/bin/php /var/www/.../yii/yii yt/sync-one --id={id} --enable=1` через `exec()`. Якщо exit_code !== 0 → flash error.
5. Redirect to `view`.

`ensureDir($path)` — приватний:
- if `is_dir` → return
- if parent !exists → throw "Parent dir not exists"
- if !is_writable parent → throw з permission octal
- mkdir 0775 recursive; chmod 0775

#### `actionSync()`
```php
$cmd = "sudo -n php /var/www/.../yii/yii yt/sync-one --id={$id} --restart=0 --enable=0";
exec($cmd . ' 2>&1', $output, $code);
return ['ok' => $code === 0, 'output' => trim(implode("\n", $output))];
```

### 8.3 `frontend\controllers\YoutubeOauthController` (170 рядків)

OAuth 2.0 authorization code flow. CSRF disabled (`enableCsrfValidation = false`) — захист через `state`.

#### `redirectUri()`
```
https://aiyoutube.pbnbots.com/yii/frontend/web/index.php?r=youtube-oauth/oauth
```
**Hardcoded домен!** При переїзді на CFF → треба переробляти Google Cloud Console redirect URIs.

#### `actionOauth($account_id = 2)`

**START FLOW (no `code`):**
```php
$csrf = security->generateRandomString(24);
session->set('yt_oauth_csrf', $csrf);
$state = "{$accountId}|{$csrf}";

$scopes = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.upload',  // обов'язково для thumbnails.set
];

$params = [
    'client_id', 'redirect_uri', 'response_type=code',
    'access_type=offline',
    'prompt=consent',                  // ← КРИТИЧНО: інакше refresh_token не повернеться
    'include_granted_scopes=true',
    'scope=...',
    'state=...',
];

return redirect('https://accounts.google.com/o/oauth2/v2/auth?' . http_build_query($params));
```

**CALLBACK:**
1. Validate `state` format `{accountId}|{csrf}`
2. `hash_equals($csrfSaved, $stCsrf)` — або `'CSRF mismatch'`
3. `YoutubeAccount::findOne($stAccountId)` (вдруге, з URL state — anti-tampering)
4. `exchangeAuthCode`:
   ```php
   POST oauth2.googleapis.com/token
       client_id, client_secret, code, grant_type='authorization_code', redirect_uri
   → ['access_token', 'refresh_token', 'expires_in', ...]
   ```
5. Save:
   ```php
   $acc->access_token = $accessToken;
   if ($refreshToken !== '') $acc->refresh_token = $refreshToken;  // НЕ перезаписуємо якщо порожній
   $acc->token_expires = time() + ($expiresIn > 0 ? $expiresIn : 3500);
   $acc->updated_at = date('Y-m-d H:i:s');
   $acc->save(false);
   $session->remove('yt_oauth_csrf');
   ```
6. Plain text response для дебагу.

### 8.4 Frontend форми

#### `SignupForm` (81 рядок)

```php
public $username, $email, $password;

rules() = [
    ['username', 'trim'],
    ['username', 'required'],
    ['username', 'unique', 'targetClass' => User::class, 'message' => 'This username has already been taken.'],
    ['username', 'string', 'min' => 2, 'max' => 255],
    ['email', 'trim'],
    ['email', 'required'],
    ['email', 'email'],
    ['email', 'string', 'max' => 255],
    ['email', 'unique', 'targetClass' => User::class, 'message' => 'This email address has already been taken.'],
    ['password', 'required'],
    ['password', 'string', 'min' => Yii::$app->params['user.passwordMinLength']],   // = 8
];

signup() {
    if (!validate) return null;
    $user = new User();
    $user->username = $this->username;
    $user->email = $this->email;
    $user->setPassword($this->password);          // generates hash
    $user->generateAuthKey();                      // remember-me cookie key
    $user->generateEmailVerificationToken();
    return $user->save() && sendEmail($user);
}

sendEmail($user) {
    return mailer
        ->compose(['html' => 'emailVerify-html', 'text' => 'emailVerify-text'], ['user' => $user])
        ->setFrom([params['supportEmail'] => app->name . ' robot'])
        ->setTo($this->email)
        ->setSubject('Account registration at ' . app->name)
        ->send();
}
```

#### `ContactForm` (62 рядки)

```php
public $name, $email, $subject, $body, $verifyCode;

rules() = [
    [['name','email','subject','body'], 'required'],
    ['email', 'email'],
    ['verifyCode', 'captcha'],   // ← CAPTCHA обов'язкова
];

sendEmail($email) {
    return mailer->compose()
        ->setTo($email)
        ->setFrom([params['senderEmail'] => params['senderName']])
        ->setReplyTo([$this->email => $this->name])
        ->setSubject($this->subject)
        ->setTextBody($this->body)
        ->send();
}
```

### 8.5 Frontend views

#### `views/stream/index.php` (446 рядків) ⭐ Реактивна адмінка

**HTML-структура:**
- Title: "Streams Control Center"
- Top bar: title + "Last update: —" + 3 кнопки (`btnRefresh`, `btnPause`, `Create Stream`)
- Filters: search box `q`, dropdown `flt` (all/running/stopped/failed), `Start ALL`/`Stop ALL`/`Restart ALL`
- Table: `#`, `Стрім` (name + channel), `Service / Workdir + stream_key (зеленим) + runner_path (синім)`, `Статус` (badge), `Uptime`, `PID`, `Дії` (Auth, Sync, Log, Restart, Stop, Start)
- Modal: `logModal` (Bootstrap 5) з pre-textarea для journalctl tail

**JavaScript (вбудований inline, ~250 рядків):**

```javascript
const URLs = { sync, status, start, stop, restart, tail };
const CSRF = { param, token };
let paused = false, timer = null;
let data = <?= $initialJson ?>;   // initial render server-side

function statusBadge(st) {
    if (active && running) → "LIVE • running" (зелений)
    if (inactive || dead || deactivating) → "STOPPED • dead" (сірий)
    if (failed) → "FAILED • failed" (червоний)
    if (sudo_required) → "sudo_required" (жовтий)
    if (loading) → "…"
}

function fmtDur(sec):
    if (h > 0) return `${h}h ${m}m`
    if (m > 0) return `${m}m ${s}s`
    return `${s}s`

function uptimeHtml(st):
    if (!isRunning) return '—'
    if (!runtime_max_sec) → "⏱ {elapsed} | ⏳ без ліміту"
    else → "⏱ {elapsed} | ⏳ до {endTs} ({remaining})"

async function refreshStatus():
    GET URLs.status → оновити data, render(), update lastUpdate timestamp

async function unitAction(action, id):
    POST URLs[action] з CSRF, body x-www-form-urlencoded
    if !ok → alert(`❌ ${action.toUpperCase()} #${id}\n${output||error}`)

async function doBulk(action):
    confirm(`${action.toUpperCase()} ALL (${count} streams)?`)
    for of ids: await unitAction(action, id); await sleep(400ms); await refreshStatus()

async function openLog(id):
    показати Bootstrap modal
    GET URLs.tail?id=&lines=120

// Per-row buttons:
// <a href="...?r=youtube-oauth/oauth&account_id=${yid}">Auth</a>
// <button class="act-sync">Sync</button>
// ... (Log, Restart, Stop, Start)

elTbody.click → дізнатись який кнопка → unitAction(action, id) + refreshStatus
btnRefresh.click → refreshStatus
btnPause.click → toggle paused (Resume button з зеленим border)
btnStartAll/StopAll/RestartAll → doBulk
elQ.input/elFlt.change → render

render(); refreshStatus();
timer = setInterval(refreshStatus, 5000);   // ⭐ 5-сек polling
```

**Filter:**
```javascript
matchesFilter(row):
    let q = elQ.value.lowercase()
    let f = elFlt.value
    let hay = [row.name, row.channel, row.service, row.workdir, row.status?.activeState, row.status?.subState].join(' ').lowercase()
    if (q && !hay.includes(q)) return false
    if (f === 'running') return active && running
    if (f === 'stopped') return inactive || dead || deactivating
    if (f === 'failed') return failed
    return true
```

**YouTube channel link на title:** `https://www.youtube.com/@${name}`.

#### `views/stream/create.php` (35 рядків)

```php
ActiveForm::begin();
$form->field($model, 'name')->textInput(['placeholder' => 'audiokniga-one']);
$form->field($model, 'stream_key')->textInput(['placeholder' => 'xxxx-xxxx-xxxx-xxxx']);
$form->field($model, 'youtube_account_id')->dropDownList($accounts, ['prompt' => '— Select YouTube account —']);
$form->field($model, 'channel_name')->textarea(['rows' => 5]);
$form->field($model, 'yt_tags')->textInput(['placeholder' => 'tag1, tag2, tag3']);
$form->field($model, 'duration_sec')->textInput(['type' => 'number']);
Html::submitButton('Create + Sync Service', ['class' => 'btn btn-success']);
ActiveForm::end();
```

#### `views/site/index.php` — Yii2 boilerplate (3 lorem ipsum heading блоки), не кастомізовано.

---

## 9. Backend layer (admin panel)

### 9.1 `backend\controllers\SiteController` (105 рядків)

```php
behaviors() {
    'access' => AccessControl: [
        ['actions' => ['login', 'error'], 'allow' => true],
        ['actions' => ['logout', 'index'], 'allow' => true, 'roles' => ['@']],
    ],
    'verbs' => VerbFilter: ['logout' => ['post']],
}
actions() = ['error' => ErrorAction]

actionIndex()  → render('index')          (auth)
actionLogin()  → if guest, layout='blank', LoginForm
actionLogout() → user->logout(); goHome()
```

### 9.2 Backend views

- `views/layouts/main.php` — admin layout (Bootstrap5 navbar з logout)
- `views/layouts/blank.php` — порожній (для login екрану — без навігації)
- `views/site/index.php` — admin landing (placeholder)
- `views/site/login.php` — login форма
- `views/site/error.php` — error page

**Admin panel ефективно НЕ ВИКОРИСТОВУЄТЬСЯ** — всі бізнес-операції через CLI. Backend живе як placeholder з валідним SiteController але без adminCRUD для Streams/Tasks/etc.

---

## 10. Common models — ядро даних

### 10.1 `common\models\User` (213 рядків)

```php
class User extends ActiveRecord implements IdentityInterface
{
    const STATUS_DELETED = 0;
    const STATUS_INACTIVE = 9;   // після signup, до email verify
    const STATUS_ACTIVE = 10;    // після verify

    behaviors() => [TimestampBehavior]   // auto created_at, updated_at

    rules() => [
        ['status', 'default', 'value' => STATUS_INACTIVE],
        ['status', 'in', 'range' => [ACTIVE, INACTIVE, DELETED]],
    ];

    findIdentity($id)                → User::findOne(['id'=>$id, 'status'=>ACTIVE])
    findIdentityByAccessToken($t)   → throw NotSupportedException
    findByUsername($u)               → User::findOne(['username'=>$u, 'status'=>ACTIVE])
    findByPasswordResetToken($t)     → if !valid → null; інакше findOne([token, ACTIVE])
    findByVerificationToken($t)      → findOne([token, INACTIVE])

    isPasswordResetTokenValid($t):
        $timestamp = (int) substr($t, strrpos($t, '_') + 1);
        return $timestamp + Yii::$app->params['user.passwordResetTokenExpire'] >= time();

    getId()        → primaryKey
    getAuthKey()   → $this->auth_key
    validateAuthKey($k) → $this->auth_key === $k

    validatePassword($p) → Yii::$app->security->validatePassword($p, $this->password_hash)
    setPassword($p)      → password_hash = security->generatePasswordHash($p)

    generateAuthKey()                  → security->generateRandomString()
    generatePasswordResetToken()       → randomString . '_' . time()
    generateEmailVerificationToken()   → randomString . '_' . time()
    removePasswordResetToken()         → password_reset_token = null
}
```

**Token format:** `{32-char-random}_{unix_timestamp}` — `substr(strrpos('_'))` витягує timestamp для перевірки expiry. `passwordResetTokenExpire = 3600s` = 1 година.

### 10.2 `common\models\LoginForm` (79 рядків)

```php
public $username, $password, $rememberMe = true;
private $_user;

rules() = [
    [['username','password'], 'required'],
    ['rememberMe', 'boolean'],
    ['password', 'validatePassword'],   // inline validator
];

validatePassword($attribute, $params) {
    if (!hasErrors()) {
        $user = getUser();
        if (!$user || !$user->validatePassword($this->password)) {
            addError($attribute, 'Incorrect username or password.');
        }
    }
}

login() {
    if (validate()) {
        return Yii::$app->user->login($this->getUser(), $this->rememberMe ? 3600*24*30 : 0);
        // 30 днів якщо rememberMe, інакше session-only
    }
}
```

### 10.3 `common\models\Stream` (133 рядки) ⭐

```php
class Stream extends ActiveRecord {
    public $use_custom_runner = false;   // form-only (не в БД)
    public static tableName() = 'stream';

    rules() = [
        [['name','service_name','workdir','youtube_account_id'], 'required'],
        ['enabled', 'boolean'],
        ['youtube_account_id', 'integer'],
        ['youtube_account_id', 'exist', 'targetClass' => YoutubeAccount, 'targetAttribute' => ['youtube_account_id'=>'id']],
        [['youtube_broadcast_id','youtube_stream_id'], 'string', 'max' => 64],
        ['youtube_stream_key', 'string', 'max' => 128],
        ['notes', 'string'],
        [['created_at','updated_at'], 'integer'],
        [['name','service_name','workdir','channel_name'], 'string', 'max' => 255],
        ['service_name', 'unique'],
        ['runner_path', 'string', 'max' => 255],
        ['runner_path', 'default', 'value' => null],
        ['use_custom_runner', 'boolean'],
        ['runner_path', 'validateRunnerPath'],   // ⭐ whitelist!
    ];

    beforeValidate() {
        $slug = MyFunction::mso_slug($this->name);

        if (empty(service_name))
            $this->service_name = "stream-{$slug}.service";

        if (empty(workdir)) {
            $base = Yii::$app->params['streamsBaseDir'] ?? '/var/www/.../data/streams';
            $this->workdir = $base . '/' . $slug;
        }

        if (!use_custom_runner) {
            $this->runner_path = null;
        } else {
            $base = '/var/www/.../data/streams/';
            if (empty(runner_path) && !empty(name))
                $this->runner_path = $base . $this->name . '/runner.sh';
        }
    }

    static slugify($s):    // alternative slug
        lowercase utf8; preg_replace; iconv UTF-8→ASCII//TRANSLIT//IGNORE; preg_replace lowercase a-z0-9-

    beforeSave($insert):
        $t = time();
        if ($insert) created_at = $t;
        updated_at = $t;

    afterFind() { $this->use_custom_runner = !empty($this->runner_path); }

    getYoutubeAccount() = hasOne(YoutubeAccount, ['id' => 'youtube_account_id']);

    validateRunnerPath($attribute) {
        $p = trim($this->$attribute);
        if ($p === '') { $this->$attribute = null; return; }

        // ⭐ WHITELIST — тільки 2 валідних шляхи:
        if ($p === '/usr/local/bin/yt_stream_runner.sh') return;
        $expected = '/var/www/fastuser/data/www/aiyoutube.pbnbots.com/data/streams/' . $this->name . '/runner.sh';
        if ($p === $expected) return;

        addError($attribute, 'Runner path is not allowed (must be default or stream-local runner.sh).');
    }
}
```

**Поля у БД (з rules + видимих use):** `id, name, service_name, workdir, stream_key, youtube_account_id, youtube_broadcast_id, youtube_stream_id, youtube_stream_key, channel_id, channel_name, yt_title, yt_description, yt_tags, yt_thumbnail, runner_path, duration_sec, rtmp_base, enabled, notes, created_at, updated_at`.

### 10.4 `common\models\Tasks` (77 рядків) ⭐ Центральна черга

```php
public static tableName() = 'tasks';

rules() = [
    [['account_id','date_add','att_file_path','title','description','keywords','post_comment','add_info','date_post','date_done'], 'default', 'value' => null],
    ['cover', 'default', 'value' => ''],
    ['status', 'default', 'value' => 0],
    [['account_id','status'], 'integer'],
    [['date_add','date_post','date_done'], 'safe'],   // ← TIMESTAMP/DATETIME
    [['description','post_comment','add_info'], 'string'],
    ['media_type', 'string', 'max' => 20],
    [['att_file_path','cover','title','keywords'], 'string', 'max' => 255],
];
```

**Поля БД та значення:**
| Поле | Тип | Значення |
|---|---|---|
| `id` | INT PK | auto |
| `account_id` | INT | FK на `youtube_account.id` |
| `media_type` | VARCHAR(20) | 'youtube' (єдине використовуване значення) |
| `status` | INT | 0=pending, далі CFF: 1=processing, 2=done, 3=failed |
| `date_add` | DATETIME | `NOW()` через `Expression('NOW()')` |
| `att_file_path` | VARCHAR(255) | path до .mp4 |
| `cover` | VARCHAR(255) | path до .jpg (опц.) |
| `title` | VARCHAR(255) | YT title |
| `description` | TEXT | YT description (з link'ами + хештегами) |
| `keywords` | VARCHAR(255) | comma-separated tags |
| `post_comment` | TEXT | первий comment під відео (PHP більше не публікує — це для CFF worker) |
| `add_info` | TEXT | НЕ використовується (legacy) |
| `date_post` | DATETIME | запланована дата публікації |
| `date_done` | DATETIME | NULL коли pending |

### 10.5 Інші common моделі

#### `YoutubeAccount` (42 рядки) — legacy схема
Поля: `id, name, client_id, client_secret, access_token, refresh_token, token_expires (unix int), created_at, updated_at`.

#### `YoutubeChannels` (83 рядки) — нова схема
Поля: `id, name, channel_id, client_id, client_secret, access_token, refresh_token, token_expires_at (TIMESTAMP), enabled, console_id (FK→GoogleConsoles), stat (boolean — для Youtube_stats), created_at, updated_at`.

`getYoutubeTokens() = hasMany(YoutubeTokens::class, ['channel_name' => 'name'])` — окрема таблиця токенів за іменем каналу (legacy).

#### `GoogleConsoles` (95 рядків)
Поля: `id, name, client_id, client_secret, credentials_file, description, project_id, redirect_uris, enabled, created_at, updated_at`.

Зв'язки:
```php
getYoutubeChannels()  = hasMany(YoutubeChannels, ['console_id' => 'id']);
getYoutubeChannels0() = hasMany(YoutubeChannels, ['console_name' => 'name']);   // legacy by-name lookup
```

Один Google Cloud Project per row. Тримаючи декілька проєктів — масштабування на 100+ youtube_channels без OAuth quota issues.

#### `YoutubeChannelDaily` (63 рядки)
UPSERT по `(channel_id, snapshot_date)`. Поля: `id, yt_channel_id, channel_id, snapshot_date, subscribers, views, videos, created_at`.

### 10.6 `common\widgets\Alert` (77 рядків) — Bootstrap5 flash messages

```php
class Alert extends \yii\bootstrap5\Widget {
    public $alertTypes = [
        'error'   => 'alert-danger',
        'danger'  => 'alert-danger',
        'success' => 'alert-success',
        'info'    => 'alert-info',
        'warning' => 'alert-warning',
    ];

    run() {
        foreach (Yii::$app->session->getAllFlashes() as $type => $flash) {
            if (!isset($this->alertTypes[$type])) continue;
            foreach ((array) $flash as $i => $message) {
                echo \yii\bootstrap5\Alert::widget([
                    'body' => $message, 'closeButton' => $this->closeButton,
                    'options' => ['id' => $this->getId() . '-' . $type . '-' . $i,
                                  'class' => $this->alertTypes[$type] . $appendClass],
                ]);
            }
            $session->removeFlash($type);
        }
    }
}
```

### 10.7 Mail templates

- `common/mail/emailVerify-html.php` / `-text.php` — для signup confirmation
- `common/mail/passwordResetToken-html.php` / `-text.php` — для password reset
- `common/mail/layouts/{html.php, text.php}` — wrapper layout
- Стандартні Yii2 advanced template strings з `{{user}}` placeholders.

---

## 11. Common services

### 11.1 `YoutubeService` (381 рядок) — повний YouTube Data API клієнт ⭐

**Базовий URL:** `const API = 'https://www.googleapis.com/youtube/v3/';`

#### `getValidAccessToken(YoutubeAccount $acc): string`
1. Якщо `access_token` живий і `token_expires > now+60s` → повернути existing
2. Якщо `refresh_token` empty → throw `'No refresh_token in youtube_account'`
3. POST `oauth2.googleapis.com/token`:
   ```
   client_id, client_secret, refresh_token, grant_type=refresh_token
   ```
4. Якщо HTTP < 200 || >= 300 → throw `'Token refresh failed: HTTP ...'`
5. Save `acc->access_token, token_expires = now + (expires_in ?: 3500), updated_at = NOW()`, `save(false)`.

#### `private api(method, url, accessToken, ?jsonBody): array`
- Headers: `Authorization: Bearer {token}`, `Accept: application/json`
- Якщо jsonBody → `Content-Type: application/json`, encode як `JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES`
- TIMEOUT: 40s
- Throw на curl error або не-JSON відповідь
- Якщо HTTP < 200 || >= 300 → throw `'YouTube API {code}: {msg} ({reason})'`

#### `getBroadcast(acc, broadcastId): ?array`
GET `liveBroadcasts?part=id,snippet,status,contentDetails&id={bid}` → `items[0]` або null.

#### `createBroadcast(acc, params): array`
POST `liveBroadcasts?part=snippet,status,contentDetails`:
```php
$body = [
    'snippet' => [
        'title' => $params['title'] ?? 'Live Stream',
        'description' => $params['description'] ?? '',
        'scheduledStartTime' => gmdate('Y-m-d\TH:i:s\Z', time() + 10),   // ⚠️ +10s, не +30s
    ],
    'status' => [
        'privacyStatus' => $params['privacy'] ?? 'public',
        'selfDeclaredMadeForKids' => false,
    ],
    'contentDetails' => [
        'enableAutoStart' => true,
        'enableAutoStop'  => true,
    ],
];
```

#### `updateBroadcastMeta(acc, broadcastId, meta): array`
PUT `liveBroadcasts?part=snippet`:
```php
$body = [
    'id' => $broadcastId,
    'snippet' => [
        'title' => $meta['title'] ?? '',
        'description' => $meta['description'] ?? '',
        'scheduledStartTime' => $scheduled,   // використовує переданий або з getBroadcast або gmdate(now+30)
    ],
];
```

#### `updateVideoMeta(acc, videoId, meta): array`
PUT `videos?part=snippet`:
```php
$snippet = [
    'title' => $meta['title'] ?? '',
    'description' => $meta['description'] ?? '',
    'categoryId' => '22',   // ← People & Blogs (хардкод!)
];
if (!empty($meta['tags']) && is_array($meta['tags'])) {
    $tags = array_filter(array_map('trim', $meta['tags']));
    if ($tags) $snippet['tags'] = $tags;
}
$body = ['id' => $videoId, 'snippet' => $snippet];
```

#### `setThumbnail(acc, videoId, imagePath): array`
1. Validate file exists, не порожній
2. Detect MIME через `mime_content_type` (fallback `'image/jpeg'`)
3. POST `https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={id}`
   - Headers: `Authorization`, `Content-Type: {mime}`, `Content-Length: {len}`
   - Body: raw bytes
   - TIMEOUT: 80s

#### `findLiveStreamIdByStreamKey(acc, streamKey): ?string`
- Pagination: до 6 сторінок
- GET `liveStreams?part=id,cdn&mine=true&maxResults=50[&pageToken=]`
- Шукає `items[*].cdn.ingestionInfo.streamName == streamKey`
- Повертає `items[i].id` (string) або null

#### `bindBroadcastToStream(acc, broadcastId, streamId): array`
POST `liveBroadcasts/bind?part=id,contentDetails&id={bid}&streamId={sid}` (без body)

#### `transitionBroadcast(acc, broadcastId, toStatus): array`
POST `liveBroadcasts/transition?part=id,status&broadcastStatus={status}&id={bid}` (status: testing/live/complete)

#### `ensureBroadcastForStream(acc, stream, metaFromDb): string`
1. Якщо `stream->youtube_broadcast_id` непорожній → `getBroadcast` ; якщо живий → return existing id
2. Інакше null'ить `stream->youtube_broadcast_id`, save
3. `createBroadcast(...)` з `stream->name` як title fallback
4. Save id в `stream->youtube_broadcast_id`, save
5. Return new id

#### `prepareBroadcastForStart(acc, stream, meta): array` ⭐ Головна публічна функція

**Послідовність:**
1. `$broadcastId = ensureBroadcastForStream(...)` — створити/повторно використати
2. Якщо `stream->stream_key` непорожній:
   - `$streamId = findLiveStreamIdByStreamKey(...)` — paginate liveStreams
   - Якщо знайдено → try `bindBroadcastToStream(broadcastId, streamId)` (try-catch — не валимо весь старт)
3. `updateBroadcastMeta($broadcastId, $meta)`
4. Try `updateVideoMeta($broadcastId, $meta)` (не валимо при failure — video може ще не бути)
5. Якщо `$meta['thumbnail']` — try `setThumbnail($broadcastId, $thumb)` (не валимо при failure)
6. Return `['broadcastId' => $broadcastId, 'streamId' => $streamId]`

**Помилки тут:**
- `RefreshError: invalid_grant` — refresh_token revoked → треба `cli.reauth --all-failed` (CFF) або redo `/youtube-oauth/oauth?account_id=N` (Yii)
- bind помилка — broadcast вже live або streamKey не зв'язаний

#### `static parseTags(?string $tags): array`
```php
return array_values(array_filter(array_map('trim', preg_split('/[,;\n]+/', $tags))));
```

### 11.2 `YoutubeLiveService` (159 рядків) — Legacy minimal API

Дублює лише `transitionBroadcast` + token refresh з YoutubeService. Відмінність — повертає `['ok'=>bool, 'access_token'=>...]` замість throw'ів. Скоріше за все застаріле, але є fallback.

```php
public function goLive(int $accountId, string $broadcastId): array {
    return $this->transitionBroadcast($accountId, $broadcastId, 'live');
}

public function complete(int $accountId, string $broadcastId): array {
    return $this->transitionBroadcast($accountId, $broadcastId, 'complete');
}

private function getValidAccessToken(int $accountId): array {
    $acc = YoutubeAccount::findOne($accountId);
    if (!$acc) return ['ok' => false, 'error' => "YoutubeAccount not found: {$accountId}"];

    if (живий) return ['ok' => true, 'access_token' => $acc->access_token];

    if (нема refresh) return ['ok' => false, 'error' => "Token expired and refresh_token/client not configured for account {$accountId}"];

    $resp = refreshToken($client_id, $client_secret, $refresh_token);
    save acc;
    return ['ok' => true, 'access_token' => $acc->access_token];
}
```

### 11.3 `StreamProvisionerService` (175 рядків) ⭐ Провіжинг стрімів

```php
public string $projectBase = '/var/www/fastuser/data/www/aiyoutube.pbnbots.com';
public string $streamsBase;     // = projectBase . '/data/streams'
public string $envBase = '/etc/aiyoutube/streams';
public string $systemdDir = '/etc/systemd/system';
public string $runnerPath = '/usr/local/bin/yt_stream_runner.sh';
```

#### `syncOne(Stream $s, bool $enable=true, bool $restart=false): array`

1. Validate `name`, `stream_key` непорожні
2. **Створити дирки:**
   - `$workDir = streamsBase/{name}`
   - `$videosDir = $workDir/videos` — `mkdir 0755 recursive`
   - `$envBase` — `mkdir 0755`
3. **Записати env файл:**
   ```
   /etc/aiyoutube/streams/{name}.env:
   STREAM_NAME={name}
   STREAM_KEY={stream_key}
   INPUT_DIR={videosDir}
   RTMP_HOST=a.rtmp.youtube.com
   RUNTIME_MAX=42900
   ```
   `chmod 0600` (тільки root читає)
4. `ensureRunnerInstalled()`:
   ```php
   if (!is_file($runnerPath)) {
       mkdir(dirname);
       file_put_contents($runnerPath, runnerScript());
       chmod 0755;
   }
   ```
5. **Записати systemd unit:**
   ```php
   $unitName = "stream-{name}.service";
   $unitPath = "/etc/systemd/system/{unitName}";
   file_put_contents($unitPath, renderUnit($name, $workDir, $envPath));
   chmod 0644;
   ```
6. `systemctl daemon-reload`
7. Якщо `$enable`: `systemctl enable {unitName}` (allowFail)
8. Якщо `$restart`: `systemctl restart {unitName}` (allowFail)
9. Return array з усіма paths.

#### `renderUnit($name, $workDir, $envPath): string`

```ini
[Unit]
Description=YouTube Stream: {$name}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={$workDir}
EnvironmentFile={$envPath}
ExecStart=/usr/bin/env bash {$this->runnerPath}

Restart=on-failure
RestartSec=5

KillSignal=SIGINT
KillMode=control-group
TimeoutStopSec=60
SuccessExitStatus=0 130 255

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### `runnerScript(): string`

```bash
#!/usr/bin/env bash
set -euo pipefail

STREAM_NAME="${STREAM_NAME:-stream}"
STREAM_KEY="${STREAM_KEY:-}"
INPUT_DIR="${INPUT_DIR:-}"
RTMP_HOST="${RTMP_HOST:-a.rtmp.youtube.com}"
RUNTIME_MAX="${RUNTIME_MAX:-42900}"

if [[ -z "$STREAM_KEY" || -z "$INPUT_DIR" ]]; then
  echo "ERROR: STREAM_KEY or INPUT_DIR is empty"; exit 2
fi

PLAYLIST="$INPUT_DIR/playlist.txt"
RTMP_URL="rtmp://${RTMP_HOST}/live2/${STREAM_KEY}"

cd "$INPUT_DIR"
shopt -s nullglob; : > "$PLAYLIST"
for f in $(ls -1 *.mp4 2>/dev/null | sort); do
  echo "file '${PWD}/${f}'" >> "$PLAYLIST"
done

[[ -s "$PLAYLIST" ]] || { echo "ERROR: playlist is empty"; exit 3; }

exec ffmpeg -hide_banner -loglevel info -nostdin -re \
  -f concat -safe 0 -stream_loop -1 -i "$PLAYLIST" \
  -fflags +genpts -avoid_negative_ts make_zero \
  -c:v copy -c:a copy \
  -t "$RUNTIME_MAX" \
  -f flv "$RTMP_URL"
```

**Параметри ffmpeg detail:**
- `-nostdin`: не чекати на stdin (важливо для systemd)
- `-re`: realtime read (RTMP вимагає)
- `-f concat -safe 0 -stream_loop -1`: нескінченний concat-плейлист
- `-c:v copy -c:a copy`: zero CPU re-encode (передбачає що всі mp4 однакові кодеки)
- `-fflags +genpts -avoid_negative_ts make_zero`: фікси PTS дрейфу між сегментами
- `-t {RUNTIME_MAX}`: жорсткий таймаут (~12 годин YouTube ліміт)
- `-f flv`: RTMP вимагає FLV контейнер

#### `private run($cmd, $allowFail=false): void`
```php
exec($cmd . ' 2>&1', $out, $ret);
if ($ret !== 0 && !$allowFail) throw new \RuntimeException("CMD failed ({$ret}): {$cmd}\n" . implode("\n", $out));
```

### 11.4 `SystemdService` (180 рядків) ⭐ systemctl wrapper

```php
private $sudo, $systemctl, $journalctl;
public ?string $lastCmd = null;

__construct(bool $useSudo = true):
    $sudo = $useSudo ? '/usr/bin/sudo -n ' : '';   // -n = non-interactive (не питати пароль)
    $systemctl = '/usr/bin/systemctl';
    $journalctl = '/usr/bin/journalctl';
```

#### `private runBinary($bin, $args=[]): array`
```php
$cmd = $this->sudo . $bin;
foreach ($args as $a) $cmd .= ' ' . escapeshellarg($a);
$this->lastCmd = $cmd;
exec($cmd . ' 2>&1', $out, $code);
return [$code, implode("\n", $out)];
```

#### `start(unit) / stop(unit) / restart(unit) / resetFailed(unit): array`
Просто wrapper над `runBinary($systemctl, [action, $unit])`.

#### `tail($unit, $lines=50): string`
`journalctl -u {unit} -n {lines} --no-pager -o short-iso` → returns stdout.

#### `status($unit): array`

```php
[$code, $txt] = runBinary($systemctl, [
    'show', $unit, '--no-page',
    '--property=Id,ActiveState,SubState,MainPID,ExecMainStatus,'
    . 'ActiveEnterTimestamp,ActiveEnterTimestampUSec,StateChangeTimestampUSec,ActiveEnterTimestampMonotonic,'
    . 'RuntimeMaxUSec,RuntimeMaxSec'
]);

if ($code !== 0 && (str_contains($txt, 'password') || str_contains($txt, 'sudo'))) {
    return ['unit', 'active' => false, 'activeState' => 'sudo_required', 'error', 'code'];
}

// parse "key=value" lines
$data = [];
foreach (explode("\n", $txt) as $line) {
    if (strpos($line, '=') === false) continue;
    [$k, $v] = explode('=', $line, 2);
    $data[$k] = $v;
}

$sinceStr = trim($data['ActiveEnterTimestamp'] ?? '');
$sinceTs = $sinceStr && lower($sinceStr) !== 'n/a' ? strtotime($sinceStr) : null;

$runtime = parseTimeSpanToSec($data['RuntimeMaxUSec'] ?? null);
if ($runtime === null || $runtime === 0)
    $runtime = parseTimeSpanToSec($data['RuntimeMaxSec'] ?? null) ?? $runtime;
$runtime = $runtime ?? 0;

$now = time();
$endTs = ($sinceTs && $runtime) ? ($sinceTs + $runtime) : null;

return [
    'unit' => $unit,
    'active' => ($data['ActiveState'] ?? '') === 'active',
    'activeState' => $data['ActiveState'] ?? 'unknown',
    'subState' => $data['SubState'] ?? '',
    'pid' => (int) ($data['MainPID'] ?? 0),
    'since_ts' => $sinceTs,
    'runtime_max_sec' => $runtime,
    'elapsed_sec' => $sinceTs ? max(0, $now - $sinceTs) : null,
    'remaining_sec' => $endTs ? max(0, $endTs - $now) : null,
    'end_ts' => $endTs,
    'code' => $code,
];
```

#### `private parseTimeSpanToSec(?string $v): ?int`

Підтримує:
- `'0'` або порожньо → 0
- `'infinity'` → null
- digits-only (наприклад `42900000000`) → microseconds → `intdiv($n, 1_000_000)` секунд
- format string `'11h 55min'`, `'5min 30s'`, `'1h'`, `'42900s'` → парсинг units:
  ```
  y/year/years   = 31536000
  month/months   = 2592000
  w/week/weeks   = 604800
  d/day/days     = 86400
  h/hr/hour/hours = 3600
  min/m/minute/minutes = 60
  s/sec/second/seconds = 1
  ms = 0.001
  us = 0.000001
  ```

---

## 12. Common components — `MyFunction.php`

Один великий статичний клас (~50 функцій, 1377 рядків). Розгрупую по доменах.

### 12.1 String/text утиліти

#### `splitTextByLength($text, $maxLen=4096): array`
Ділить текст на чанки до `maxLen` UTF-8 символів, ріжучи на пробілах (якщо знаходить пробіл у останніх 30%, інакше hard cut на maxLen). Використовується для TTS чанкінгу (OpenAI 4096 char limit).

#### `mso_slug(string $slug): string`
Переклад кирилиця→латиниця через велику таблицю замін (~85 правил):
- Російська (а→a, б→b, в→v, …, ы→y, э→e, ю→ju, я→ja)
- Українська (є→ye, і→i, ї→yi, ґ→g)
- Білоруська (ў→u)
- Знаки пунктуації, smart quotes (`«`, `»`, `—`, `™`, `©`, `®`, `…`) → відповідні latin
- Spaces → `-`, multiple `-` → одне `-`

Зберігає розширення `.htm` (через спец-токен `@HTM@`). Точно: lowercase output.

#### `cyrillicToLatin($text, $toLowCase=true): string`
Альтернативна транслітерація з maxLength=100 (через wordwrap). Менше правил ніж `mso_slug`.

#### `cropStr($str, $size)` — **повертає $str без обрізки** (legacy stub)

#### `cropStr2($string)` — strip_tags, substr 200, rtrim '!,.-', ріже до останнього пробілу.

#### `getRegexpr($regexp, $str, $num): string` — преg_match → matches[$num] або ''
#### `getRegexprall($regexp, $str, $num, $char=';'): string` — preg_match_all → join by $char
#### `getRegexprall_arr($regexp, $str, $num): array` — preg_match_all → array of matches[$num][i]

### 12.2 HTTP / curl утиліти (15+ варіантів)

#### `getHtml($url, $post=null): string`
Базовий curl з Yii's options:
```php
curl_setopt: SSL_VERIFYPEER=0, SSL_VERIFYHOST=2, FOLLOWLOCATION=1, HEADER=false, RETURNTRANSFER=1, SSLVERSION=1
if (!empty $post): POST + URL-encoded body (key=value&...)
```

#### `getHtml_referer($url, $post=null, $referer=''): string`
Те ж саме + `CURLOPT_REFERER` + UA `Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.17 ... Chrome/24.0.1312.52 Safari/537.17` (старий Chrome 24 — для bypass anti-bot).

#### `downloadFile($url, $path)`
Stream-copy через `fopen` + `stream_context_create` (SSL relaxed). Без UA/headers.

#### `downloadFileffmpeg($url, $path, $referer='ffmpeg.in')` ⭐
**Найпопулярніша функція** у DLE-контролерах. Curl з:
- `CURLOPT_REFERER => $referer`
- `CURLOPT_USERAGENT => 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.17 ... Chrome/24.0.1312.52'`
- `CURLOPT_FOLLOWLOCATION => 1`
- write до `fopen($path, 'w')`

Використовується для всіх DLE-cover'ів і MP3-завантажень.

#### `downloadFile_post($url, $path, $post=null, $referer='https://ffmpeg.in/')` 
Розширений варіант з:
- Headers `Accept`, `Accept-Encoding`, `Accept-Language`, `Cache-Control`, `Content-Type: application/x-www-form-urlencoded`
- Cookies `siteLanguage=ua; remix_userkey=<REDACTED>; remix_userid=<REDACTED>` (1lib.org session — leaked!)
- UA Chrome 93 / macOS
- `sec-ch-ua`, `sec-ch-ua-platform: "macOS"`, `Sec-Fetch-*` headers (mimic real browser)

#### `get_html_test1($url, $post=null, $referer)` 
Те ж саме що `downloadFile_post` але без download (returns body string). Cookies — booknet.ua сесія.

#### `get_http_response_code($url): string`
`get_headers` → перші 9-12 chars (HTTP code) — **не використовує curl, через `stream_context_create`**.

#### `get_http_response_code_curl/_2/_3` — Курли з proxy / без.

#### `getHtml_zenrows($url): string` ⭐ Zenrows free tier
GET `https://api.zenrows.com/v1/?apikey={K}&url={U}&js_render=true`

#### `getHtml_zenrows_2($url): string` ⭐ Zenrows premium
GET `https://api.zenrows.com/v1/?apikey={K}&url={U}&js_render=true&premium_proxy=true`

Використовується для Sora — `sora.chatgpt.com` блокує без headless browser.

#### `postHtml_zenrows($url): string`
POST через Zenrows як HTTP proxy: `CURLOPT_PROXY = 'http://<REDACTED:ZENROWS_KEY>@proxy.zenrows.com:8001'`.

#### `downloadFile_zenrows($url, $path, $referer)` — варіант для бінарних файлів через Zenrows.

#### `get_html_proxy($url, $host=''): string` — proxy + auth `<REDACTED:PROXY_AUTH>`.
#### `get_html_proxy_file($url, $file='', $referer='')` — proxy з рандомним вибором з файлу.
#### `downloadFile_proxy_file($url, $path, $file, $referer)` — те ж саме для бінарних.
#### `downloadFileProxy($url, $path, $host)` — простіша версія.

#### `uploadFile($url, $filename, $access_token): string`
multipart/form-data POST з `curl_file_create` (PHP 5.5+) або `@realpath` (legacy). Параметри: `access_token, upload_file, account_id=1`.

#### `downloadImageCurl($url, $savePath): bool`
Curl з UA `Mozilla/5.0`, `Referer: https://paraknig.org/`, timeout 15. Returns `bool` based on HTTP 200.

### 12.3 DLE-формат

#### `imgurl($img_id): string` ⭐
```php
$result = '';
for ($i = 0; $i < strlen($ids); $i++)
    $result .= $ids[$i] . "/";
return $result;
```
**Приклад:** `imgurl('275374')` = `'2/7/5/3/7/4/'`. DLE розкладає id у директорну ієрархію для статичних ресурсів — це bypass'ить переповнення FS-inode'ів коли мільйони книг.

#### `book_xfields($xfields): array`
Парсер пропрієтарного DLE-формату custom-полів `key1|val1||key2|val2||…`:
```php
str_replace('|||', '|-||')   // edge case: empty value
$book_xfields_arr = explode('||', $xfields);
foreach ($book_xfields_arr as $field) {
    $kv = explode('|', $field);
    $bookXfields[$kv[0]] = $kv[1];
}
return $bookXfields;
```

Приклад xfields: `cover|images/cover.jpg||namebook|Война и мир||author|Толстой||tr_id|275374||youtube|0||youtube_track_start|15`.

#### `book_xfields_to_str($xfields): string`
Зворотній серіалізатор:
```php
foreach ($xfields as $k => $v) $xf_str .= "{$k}|{$v}||";
return substr($xf_str, 0, -2);
```

### 12.4 Image processing (GD library)

#### `resize_cover($input_cover, $fixed=false): bool`
- `getimagesize` → mime detection
- `imagecreatefromjpeg/png/webp` за mime
- $maxWidth=240, $maxHeight=372
- Якщо `$fixed`: фіксує висоту, обчислює пропорційно ширину
- Інакше: якщо `originalWidth*1.5 > originalHeight` — фіксує ширину 360 (= 240*1.5), інакше — висоту 372
- `imagecreatetruecolor`, `imagealphablending(false)`, `imagesavealpha(true)`
- `imagecopyresampled`
- `imagejpeg/png/webp` назад у тот самий файл (jpeg quality=90)

**В DLE-контролерах є переписана версія:** `static resize_cover($input_cover)` — фіксована до 192×298 (без $fixed).

### 12.5 Бізнес-утиліти

#### `generatePlannedDates(string $startDate, int $count=50, $times=['19:00','20:00','21:00']): array`
Генерує масив `Y-m-d H:i` для планування публікацій:
```php
foreach (від startDate далі по днях):
    foreach ($times as $time) {
        if ($generated >= $count) break;
        $datetime->setTime($h, $m);
        $result[] = $datetime->format('Y-m-d H:i');
        $generated++;
    }
    $startDate->modify('+1 day');
```

**Часові слоти за призначеннями:**
- `Shorts_from_video::actionShorts`: `['09:00', '12:40', '17:17', '20:10']` (4 слоти/день)
- DLE controllers `actionUpload_to_youtube`: `['09:00', '12:40', '14:00']` (3 слоти/день)
- `Sora::actionGet_video`: `['12:00', '14:00', '17:00']` (3 слоти/день)
- DLE `actionShorts`: `['9:00']` (1 на день)
- Default: `['19:00', '20:00', '21:00']` (вечір)

#### `sec2ass($t): string`
```php
$h = floor($t / 3600);
$m = floor(($t % 3600) / 60);
$s = fmod($t, 60);
return sprintf('%01d:%02d:%05.2f', $h, $m, $s);
// Приклад: 12.34s → "0:00:12.34"
```

#### `shuffle_assoc($array): array`
Shuffle зі збереженням ключів (PHP `shuffle` втрачає string keys).

#### `columnLetterFromNumber($col): string`
Excel-стиль (1→A, 27→AA): base-26 з `chr(temp+65)`.

### 12.6 File system

#### `copy_directory($source, $destination)` — Рекурсивне копіювання директорії.

#### `deleteDir($dirPath)` — Рекурсивне видалення:
```php
$files = glob($dirPath . '*', GLOB_MARK);
foreach ($files as $file) {
    if (is_dir($file)) deleteDir($file);
    else unlink($file);
}
rmdir($dirPath);
```

#### `formatSizeUnits($bytes): string` — `1.23 MB`, `567 KB`, `42 bytes`

#### `get_count_filesindir($dir_path): int` — count `*.jpg` files (через glob).

### 12.7 EPUB / PDF / HTML helpers

#### `get_tidy_pages($body): array`
Розбиває текст на сторінки (1000 слів кожна) і прикріплює HTML Tidy (clean=true, output-xhtml=true, show-body-only=true).

#### `get_epub_text($dir): string`
Парсить EPUB (через `simplehtmldom::str_get_html`):
1. Шукає `book.opf` / `content.opf` / `volume.opf` / `epub.opf` у вкладених директоріях OEBPS/EPUB/OPS/Ops
2. Парсить `<spine itemref idref="X">` → шукає `<item href="..." id="X">`
3. Завантажує кожен chapter HTML, бере `<body>` innertext
4. Конкатенує

#### `text_telegram($input_text): string`
Чистка HTML для Telegram Bot API: видаляє `<p>`, `<br>`, замінює `<h1>`, `<h2>`, `<em>`, `<strong>` → `<b>`. `strip_tags($content_text, '<a>')`.

### 12.8 Зовнішні API helpers

#### `translate_deepl($from='', $to='', $text=''): string`
POST `api.deepl.com/v2/translate`:
```php
$post = [
    'auth_key' => '<REDACTED:DEEPL_KEY>',
    'text' => $text, 'source_lang' => $from, 'target_lang' => $to,
];
return json_decode($response, true)['translations'][0]['text'];
```

#### `uploadMediaTelegram($file): string`
POST `https://telegra.ph/upload`:
```php
$post = ['file' => curl_file_create($file_name_with_full_path)];
return 'https://telegra.ph' . $res[0]['src'];   // або '' на failure
```

#### `sendPhoto($botToken, $chatId, $filePath): array`
POST `https://api.telegram.org/bot{token}/sendPhoto` з `multipart/form-data`:
```php
$postFields = ['chat_id' => $chatId, 'photo' => new \CURLFile(realpath($filePath))];
return json_decode($response, true);
```

### 12.9 Misc

#### `lastmodified($date, $date_upd=null): void`
HTTP 304 Not Modified handler:
- Determine which date is most recent
- Send `Last-Modified: ...GMT` header
- If `HTTP_IF_MODIFIED_SINCE >= $LastModified_unix` → exit з 304

#### `getPathPic(): string` — `return "Hello"` (legacy stub).

#### `showPdfs($model)` / `showPdfs_search($model)` — рендерить HTML preview (legacy frontend block).

#### `close_tags($content): string`
Авто-закриває непарні HTML теги (для безпечного truncate).

---

## 13. Console pipelines

### 13.1 `Audiokniga_one_comController` (778 рядків) ⭐ DLE → audiokniga-one.com

**`$path = '/var/www/.../data/audiokniga-one.com/'`**
**`$path_shorts = '...audiokniga-one.com/shorts/'`**

#### `actionTest()`
Закоментований приклад виклику CFF: `python3 /opt/content-fabric/run_voice_changer.py --method silero --voice-model kseniya --no-preserve-quality --preserve-background data/0.mp3 data/out___0.mp3`. Не використовується на проді.

#### `actionUpload_to_youtube($limit=1, $id_yt_acc=5, $test=false)`

```php
ini_set('memory_limit', '512M');

// 1) Беремо $limit найпопулярніших постів
$models = \console\models\audiokniga_one_com\DlePost::find()
    ->joinWith(['postextras'])
    ->limit($limit)
    ->orderBy('dle_post_extras.news_read DESC')   // ⭐ VIRALITY
    ->all();

$dates = MyFunction::generatePlannedDates(today, $limit);   // default [19:00, 20:00, 21:00]

foreach ($models as $key_d => $model) {
    $modelDate = $dates[$key_d] ?? null;
    $xfields = MyFunction::book_xfields($model->xfields);

    // 2) Категорія
    $cats_m = $model->categories[0] ?? null;
    $cat_name = $cats_m->name;   // приклад: "Фантастика"

    // 3) GPT-4-turbo генерує НОВУ назву
    $new_title = $this->get_new_text(
        "Мне нужно придумать новое короткое название книги. Жанр книги: {$cat_name}. Старое название было: {$xfields['namebook']}. Язык: русский. Дай один вариант.",
        'gpt-4-turbo'
    );

    // 4) Skip якщо обкладинки нема
    if (($xfields['cover'] ?? '') === 'images/no-cover.jpg') {
        $xfields['youtube'] = 2;   // mark as skipped
        DlePost::getDb()->close(); DlePost::getDb()->open();   // workaround MySQL gone away
        $model->xfields = book_xfields_to_str($xfields);
        $model->save(false);
        continue;
    }

    // 5) Випадковий background
    $background_array = glob($path . 'backgrounds/*.{jpg,jpeg,png}', GLOB_BRACE);
    $background_path = $background_array[array_rand($background_array)];

    // 6) Cover image (1920×1080)
    $cover = $dataDir . '/output_yt_' . $model->id . '.jpg';
    $this->create_youtube_image(
        $cover,
        $background_path,
        $new_title,
        strtoupper($cat_name),       // top label (приклад: "ФАНТАСТИКА")
        ''
    );
    if (!is_file($cover) || filesize($cover) < 1024) continue;   // failed

    // 7) Завантаження плейлисту з origin CDN (bypass Cloudflare)
    $pl_txt = "https://vvoqhuz9dcid9zx9.redirectto.cc/s01/" . MyFunction::imgurl($model->book_id) . $model->book_id . ".pl.txt";
    MyFunction::downloadFileffmpeg($pl_txt, $path . '/' . $model->book_id . '.pl.txt', 'https://vvoqhuz9dcid9zx9.redirectto.cc');

    // 8) Парсимо JSON-плейлист (PHP regex)
    $text_pl = file_get_contents($path . '/' . $model->book_id . '.pl.txt');
    unlink($path . '/' . $model->book_id . '.pl.txt');
    $mp3_arr = MyFunction::getRegexprall_arr('/"file":"(.*?)"\}/', $text_pl, 1);

    // 9) Для першого MP3 (інші пропускаємо через break;)
    foreach ($mp3_arr as $key_mp3 => $mp3_path) {
        $output = $path . '/final_output_' . $model->id . '_part_' . $key_mp3 . '.mp4';
        if (!file_exists($output)) {
            // Download MP3
            MyFunction::downloadFileffmpeg($mp3_path, $path . '/' . basename($mp3_path), 'https://vvoqhuz9dcid9zx9.redirectto.cc');

            // ffmpeg trim with offset з xfields
            $in = escapeshellarg($path . '/' . basename($mp3_path));
            $out_mp3_part = escapeshellarg($path . 'out_' . $key_mp3 . '.mp3');
            if (!isset($xfields['youtube_track_start'])) $xfields['youtube_track_start'] = 0;
            $cmd = 'ffmpeg -y -ss ' . $xfields['youtube_track_start'] . ' -i ' . $in . ' -c copy ' . $out_mp3_part;
            exec($cmd, $o, $ret);
            unlink($in);

            // ⭐ Voice unique-fy через CFF
            $out_mp3_part_unique = escapeshellarg($path . 'unique_out_' . $key_mp3 . '.mp3');
            $cmd = 'cd /opt/content-fabric/prod && python3 -m cli.voice ' . $out_mp3_part . ' ' . $out_mp3_part_unique . ' --parallel --preserve-background';
            exec($cmd);

            // ffmpeg compose 1280×720 з cover image + unique mp3
            $vf = 'scale=1280:-2:flags=lanczos,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=5';
            exec(
                "ffmpeg -y -loop 1 -i $cover -i $out_mp3_part_unique " .
                "-vf \"$vf\" -c:v libx264 -preset veryfast -tune stillimage -crf 24 -pix_fmt yuv420p " .
                "-map 0:v:0 -map 1:a:0 -c:a aac -b:a 96k -ar 48000 " .
                "-shortest -movflags +faststart " . $output
            );
            unlink($out_mp3_part);
        }
        break;   // ⭐ ТІЛЬКИ ПЕРШИЙ MP3
    }

    // 10) Insert task
    $task = new \common\models\Tasks();
    $task->account_id = $id_yt_acc;
    $task->media_type = 'youtube';
    $task->status = 0;
    $task->date_add = new Expression('NOW()');
    $task->att_file_path = $output;
    $task->cover = $cover;
    $task->title = 'Полные аудиоверсии онлайн ' . $new_title;
    $task->description = "Больше аудиокниг на сайте audiokniga-one.com по ссылке:\n👉 https://audiokniga-one.com/\n👉 https://audiokniga-one.com/popadancy/\n\nПрослушайте книгу онлайн на audiokniga-one.com ";
    $task->keywords = 'книги онлайн бесплатно, аудиокниги, слушать онлайн, читать онлайн';
    $task->post_comment = 'Слушайте полные версии аудиокниг здесь: https://audiokniga-one.com/ — наслаждайтесь лучшими аудиокнигами онлайн без регистрации';
    $task->date_post = $modelDate;
    $task->save(false);

    // 11) Mark як завантажено
    $xfields['youtube'] = 1;
    DlePost::getDb()->close(); DlePost::getDb()->open();
    $model->xfields = book_xfields_to_str($xfields);
    $model->save(false);
}
```

#### `actionShorts($id_yt_acc=5)` — DLE shorts з цитат

```php
$dates = generatePlannedDates(today, 1);   // default [19:00,20:00,21:00] → беремо [0]
$modelDate = $dates[0];

// Cleanup попередніх артефактів
unlink shorts.mp4, audio_tts_1.mp3, text.ass

// Беремо першу цитату з quotes.txt і ВИДАЛЯЄМО її
$file = $path_shorts . 'quotes.txt';
$lines = file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
$anotation = $lines[0];
if (trim($anotation) == '') exit;
array_shift($lines);
file_put_contents($file, implode(PHP_EOL, $lines));

// Випадкові ресурси
$background_path = random_pick(glob($path_shorts . 'backgrounds/*.{jpg,jpeg,png}'));
$bg_music = random_pick(glob($path_shorts . 'bg_music/*.mp3'));

// Випадковий voice (4 варіанти)
$voice_variants = [
    ['gender' => 'male', 'voice' => 'fable'],
    ['gender' => 'male', 'voice' => 'echo'],
    ['gender' => 'female', 'voice' => 'alloy'],
    ['gender' => 'female', 'voice' => 'shimmer'],
];
$voice_choice = random_pick($voice_variants);

// Випадковий стиль (14 з 15, без 'whisper')
$styles = ['fairytale','serious','emotional','joyful','calm','mysterious','dramatic',
           'storytelling','sad','romantic','strict','robotic','motivational','news'];
$style = $styles[array_rand($styles)];

// TTS → audio_tts_1.mp3
$audio = $path_shorts . 'audio_tts_1.mp3';
$this->actionTts_openai(1, $anotation, $audio, 'ru', $voice_choice['gender'], '', $voice_choice['voice'], $style);

// Перевірити TTS файл
if (!is_file($audio) || filesize($audio) < 1024) return;

// Нормалізація: 48kHz stereo, volume +1.4, PCM s16le
$tts_wav = $path_shorts . 'tts_norm.wav';
$norm_cmd = "ffmpeg -y -i $audio -ac 2 -ar 48000 -af \"volume=1.4\" -c:a pcm_s16le $tts_wav";
exec($norm_cmd);
$audio_duration = (float) trim(shell_exec("ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 $tts_wav"));

// ASS субтитри (по 1 слову, Lena.ttf 140px, центр екрану)
$words = preg_split('/\s+/', $anotation);
$blocks_count = count($words);
$min_last_block = 2.0;     // резерв на останнє слово
$min_word_dur = 0.22;      // мінімум 220ms на слово

$fontPath = $path_shorts . 'fonts/lena.ttf';
$fontFamily = trim(shell_exec("fc-scan --format='%{family}\\n' $fontPath 2>/dev/null"));
if ($fontFamily === '') $fontFamily = 'Lena';   // fallback

$fontSize = 140; $outline = 4; $shadow = 0; $align = 5;   // ⭐ align=5 = центр екрану

$ass = <<<EOT
[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{$fontFamily},{$fontSize},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{$outline},{$shadow},{$align},60,60,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text

EOT;

// Розподіл слова рівномірно
$usable_time = max(0, $audio_duration - $min_last_block);
$per_word = max($min_word_dur, $usable_time / max(1, $blocks_count - 1));

// Кожне слово отримує per_word, останнє — залишок
for ($i = 0; $i < $blocks_count - 1; $i++) {
    $start = $t;
    $end = $t + $per_word;
    $ass .= "Dialogue: 0," . sec2ass($start) . "," . sec2ass($end) . ",Default,,0,0,0,," . $blocks[$i] . "\n";
    $t = $end;
}
// Останнє слово
$ass .= "Dialogue: 0," . sec2ass($t) . "," . sec2ass($audio_duration) . ",Default,,0,0,0,," . $blocks[last] . "\n";

file_put_contents($path_shorts . "text.ass", $ass);

// Final ffmpeg compose: bg + tts + bg_music (volume 0.35) + ass overlay
$cmd = sprintf(
    'ffmpeg -y -loop 1 -framerate 30 -t %.3f -i %s -i %s -i %s ' .
    '-filter_complex "[2:a]atrim=0:%.3f,asetpts=N/SR/TB,volume=0.35[a2];' .
    '[1:a][a2]amix=inputs=2:duration=shortest:dropout_transition=0[aout]" ' .
    '-map 0:v -map "[aout]" -vf "ass=%s" -c:v libx264 -pix_fmt yuv420p ' .
    '-c:a aac -b:a 192k -shortest %s',
    $audio_duration, escapeshellarg($background_path), escapeshellarg($audio), escapeshellarg($bg_music),
    $audio_duration, escapeshellarg($assPath), escapeshellarg($outVid)
);
exec($cmd);

// Insert task (короткий)
$task = new Tasks();
$task->title = strip_tags($anotation);
$task->description = "Больше аудиокниг для чтения онлайн на сайте audiokniga-one.com:\n👉 https://audiokniga-one.com/\n\nОткройте для себя новые истории и слушайте бесплатно прямо в браузере! " . $anotation;
$task->keywords = 'цитаты, книги онлайн, аудиокниги бесплатно, аудио книги';
$task->post_comment = 'Слушайте полные версии аудиокниг здесь: https://audiokniga-one.com/ — наслаждайтесь лучшими аудиокнигами онлайн без регистрации';
$task->save(false);
```

#### `create_youtube_image($outputfile, $backgroundPath, $text1='', $topText='', $overlayPath='')` 

GD-композитор обкладинок 1920×1080:
1. Завантажити PNG bg, scale 1.01x, random offset crop до 1920×1080
2. Якщо `$overlayPath` (cover image): 2x scale, вставити в верхній-лівий кут (offset 30,30), `$overlayShiftX = targetWidth + 60`
3. Top text (`$topText`) — fontSize 100px, bg-rect (alpha 60/127 чорний), centered у `(width-overlayShiftX-textWidth)/2`
4. Body text (`$text1`):
   - if `wordCount > 10`: split на 3 рядки
   - elif `wordCount > 3`: split на 2 рядки
   - else: 1 рядок
   - Per-line dynamic font size: cycle from 150 → 40 поки `totalWidth <= textZoneWidth`
   - Розрахунок `letterSpacing=10`, char-by-char render
   - Bg-rect під рядок з padding 30
5. `imagejpeg($image, $outputfile, 100)` — quality 100

**Кольори:**
- Audiokniga: `imagecolorallocate($image, 49, 232, 74)` — **зелений неон**
- Bazaknig, Books_online, Slushat, Club_books: `imagecolorallocate(255, 255, 255)` — **білий**
- Knigi_online_club: `imagecolorallocate(255, 255, 255)` — **білий**

#### `actionTts_openai($model_id, $input_text, $output_file, $language='uk', $gender='female', $instructions='', $voice='nova', $style='fairytale')`

Генерує тимчасовий bash-скрипт що активує venv і запускає Python TTS:

```bash
#!/bin/bash
clear
cd /var/www/fastuser/data/www/aiyoutube.pbnbots.com/python_scripts/tts_openai/
source tts_openai/bin/activate
export OPENAI_API_KEY="<REDACTED:OPENAI_KEY>"
python3 /var/www/.../python_scripts/tts_openai/tts_openai.py \
    --input_file "{tmp_input_text_path}" \
    --output_file "{output_file}" \
    --language "{language}" --gender "{gender}" \
    [--instructions "..." \]
    --voice "{voice}" --style "{style}"
deactivate
```

Текст пишеться в `tmp_input_text_{model_id}.txt`. Bash в `tts_openai_{model_id}.sh`. Обидва видаляються після `bash {sh}`.

#### `get_new_text($prompt, $gtp_v='gpt-3.5-turbo'): string`
```php
include_once('ChatGPT.php');
$ai = new \ChatGPT();
$desc = trim($ai->createTextRequest($prompt, $gtp_v, 0.7, 1000));
if (strpos($desc, '<p>') != -1) $desc = nl2br($desc);
return trim($desc, '"');
```

#### `getMp3Duration($filePath): int`
```php
$cmd = "ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 \"$filePath\"";
return round((float) shell_exec($cmd));
```

### 13.2 `Bazaknig_netController` (804 рядки)

`$path = '...data/bazaknig.net/'`. account: 26 (також 27, 29, 30, 32, 47, 48 — масштабовано на 7 каналів).

#### `actionUpload_to_youtube($limit=1, $id_yt_acc=26)`
**Відрізняється від Audiokniga:**
- DLE filter: `andWhere(['!=','short_story',''])`, `CHAR_LENGTH(short_story) > 1000`, `not like xfields '|youtube'`
- Cover URL: `redirectto.cc/s01/{imgurl(baza_knig_info_id)}/{xfields[cover]}`, referer `cdn.bazaknig.net`
- Стандартний TTS pipeline (`MyFunction::splitTextByLength` 4096, ffmpeg concat для multi-chunk audio)
- ffmpeg compose: 1920×1080 (без `tune stillimage`)
- Background — random з backgrounds/, BG color у `create_youtube_image` — **білий**.
- НЕ має GPT-4-turbo title regeneration.
- НЕ має cli.voice unique-fy.

#### `actionShorts($id_yt_acc=26)`
**Відмінність:** output mp4 named `shorts_{id_yt_acc}.mp4` (per-account scope для distinct accounts на тому ж source). Решта логіки 1-в-1 з Audiokniga.

### 13.3 `Books_online_infoController` (972 рядки)

#### `actionUpload_to_youtube($limit=1, $id_yt_acc=5)` (закоментована більшість)
- DLE filter: `category like '15'`, `xfields like 'tr_id'` (необхідні поля)
- Cover URL: `cdn.my-library.info/{xfields[wallpaper]}` referer `cdn.my-library.info`
- TTS pipeline + ffmpeg slideshow 1920×1080.

#### `actionUpload_to_youtube_txt_file($limit=1, $id_yt_acc=5)` (теж закоментовано)
**Інший pipeline:** для full-text озвучки книги:
- Завантажує всі глави з `redirectto.cc/s20/{imgurl(tr_id)}/text/p-{i}.txt` for i=1..tr_cnt_p
- Strip HTML, html_entity_decode, NBSP→space, collapse spaces
- Об'єднує в `book_{id}.txt`
- Викликає **`run_voice_changer.py book_{id}.wav --text-file book_{id}.txt --voice-model kseniya --speed 0.9`** (CFF voice cloning)
- ffmpeg compose 1920×1080

**Активна частина** — тільки `actionShorts($id_yt_acc=21)` — стандартний DLE shorts pattern.

`create_youtube_image` — color **білий**, з extra `$color_2 = imagecolorallocate(6, 69, 173)` (синій — резервний, не використовується).

`resize_cover` static — fixed 192×298.

### 13.4 `Club_books_ruController` (821 рядок)

`$path = '...data/club-books.ru/'`. account: 21.

#### `actionUpload_to_youtube($limit=1, $id_yt_acc=5)`
**Спец фільтри:** `category like '15'`, `not like xfields 'tr_cover|0'`, `xfields like 'tr_id'`. Cover URL: `redirectto.cc/s20/{imgurl(tr_id)}/{tr_id}.jpg`. Стандартний TTS pipeline 1920×1080.

`description` має 6 копій link'у (масштаб для SEO).

#### `actionShorts($id_yt_acc=21)`
Стандартний DLE shorts.

### 13.5 `Knigi_online_clubController` (500 рядків) — special full-text

`$path = '...data/knigi-online.club/'`. account: 12.

#### `actionUpload_to_youtube_txt_file($limit=1, $id_yt_acc=12)` ⭐ Унікальний pipeline

```php
foreach DlePost (orderBy news_read DESC, limit 1) {
    $output_file = $path . 'book_' . $model->id . '.wav';
    $image = $path . 'output_yt_' . $model->id . '_' . $id_yt_acc . '.jpg';

    if (!file_exists($output_file)) {
        // 1. Cover з origin CDN
        $cover_path = "redirectto.cc/s20/" . imgurl(tr_id) . "{tr_id}.jpg";
        downloadFileffmpeg($cover_path, $path . id . '.jpg', 'redirectto.cc');
        self::resize_cover($path . id . '.jpg');   // 192×298

        // 2. Background
        $bg = random_pick(glob($path . 'backgrounds/*.{png,jpg,jpeg,webp}'));

        // 3. Cover image 1920×1080 (білий цвіт)
        create_youtube_image($image, $bg, $xfields['namebook'], $xfields['author'], $path . id . '.jpg');

        // 4. Завантажити ВСІ chapters як текст
        if ($xfields['tr_cnt_p'] > 1) {
            $finalFile = $path . 'book_' . id . '.txt';
            file_put_contents($finalFile, "");

            for ($i = 1; $i <= $xfields['tr_cnt_p']; $i++) {
                $url = "redirectto.cc/s20/" . imgurl(tr_id) . "text/p-{$i}.txt";
                downloadFileffmpeg($url, $internal_file, "https://knigi-online.club/");
                $content = file_get_contents($internal_file);
                $text = strip_tags($content);
                $text = html_entity_decode($text, ENT_QUOTES | ENT_HTML5, 'UTF-8');
                $text = str_replace("\xc2\xa0", ' ', $text);   // NBSP → пробіл
                $text = preg_replace("/\s{2,}/u", " ", $text);
                file_put_contents($finalFile, trim($text) . PHP_EOL . PHP_EOL, FILE_APPEND);
                unlink($internal_file);
            }

            // 5. ⭐ CFF voice changer kseniya, speed 0.8
            $cmd = 'bash -c "cd /opt/content-fabric/ && source venv/bin/activate && '
                 . 'python3 run_voice_changer.py ' . $output_file . ' '
                 . '--text-file ' . $finalFile . ' '
                 . '--voice-model kseniya '
                 . '--speed 0.8"';
            exec($cmd, $output_data, $returnCode);
        }

        // 6. ffmpeg compose з cover (loop) + WAV
        $duration = getMp3Duration($output_file);
        $output_file_video = $path . 'full_video_book_' . id . '.mp4';
        exec("ffmpeg -y -loop 1 -i $image -i $output_file -c:v libx264 -tune stillimage -pix_fmt yuv420p "
           . "-vf \"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2\" "
           . "-c:a aac -b:a 192k -shortest $output_file_video");
    }

    // 7. Insert task
    $task->account_id = $id_yt_acc;     // 12
    $task->title = "{namebook} - {author} читать книгу";
    $task->description = "Более 100тыс книг найдете по ссылке:\n👉 https://knigi-online.club/{id}-{alt_name}.html\n\n🛍️ {short_story}\nБольше книг найдете по ссылке:\n👉 https://knigi-online.club/{id}-{alt_name}.html";
    $task->keywords = "{namebook}, {author}, читать книги, слушать онлайн";
    $task->post_comment = "Читайте полные версии книг здесь: https://knigi-online.club/{id}-{alt_name}.html — наслаждайтесь лучшими книгами онлайн без регистрации";
    $task->save(false);

    $xfields['youtube'] = 1;
    save model;
}
```

**Schedule:** `generatePlannedDates(today, $limit, ['09:00','12:40','14:00'])` — 3 слоти/день.

### 13.6 `Slushat_knigi_comController` (812 рядків)

`$path = '...data/slushat-knigi.com/'`. account: 25.

#### `actionUpload_to_youtube` — **ВИМКНЕНО**
```php
public function actionUpload_to_youtube($limit=1, $id_yt_acc=5, $test=false) {
    // Не налаштовано
    exit;
    ... (legacy код далі — не виконується)
}
```

#### `actionShorts($id_yt_acc=25)` — стандартний DLE shorts (квоут).

### 13.7 `Unique_audioController` (825 рядків) — knigi-audio.biz pipeline

`$path = '...data/unique_audio'`. account: 6. **Читає `\console\models\knigi_audio_biz\DlePost`** (а не unique_audio).

#### `actionUpload_to_youtube($limit=1, $id_yt_acc=6)` — спец-флоу

**Унікальні фільтри:**
- `andWhere(['like','xfields','youtube|1'])` — **ВЖЕ позначені для youtube** (повторна обробка існуючих)
- `andWhere(['like','xfields','youtube_track_start'])` — мають offset
- `andWhere(['like','category','12'])` — категорія "попаданцы"

**Спеціальний GPT-4-turbo prompt:**
```php
$new_title = $this->get_new_text(
    "Мне нужно придумать новое короткое название книги. Жанр книги: попаданцы. Старое название было: {$xfields['namebook']}. Язык: русский. Дай один вариант.",
    'gpt-4-turbo'
);
```

Cover image — top label hardcoded `'ПОПАДАНЦЫ'` (uppercase).

Решта pipeline — копія Audiokniga: pl.txt → MP3 → cli.voice unique-fy → 1280×720 mp4. Mark `xfields[youtube]=2` (note: 2, не 1!) після завантаження.

#### `actionShorts($id_yt_acc=6)` — quotes_popadanci.txt

**Окремий quotes файл:** `$path_shorts . 'quotes_popadanci.txt'` (не `quotes.txt` як у решти).

`create_youtube_image` тут — **зелений** колір `imagecolorallocate(49, 232, 74)`.

### 13.8 `NewsController` (1049 рядків) ⭐ RBC RSS pipeline

```php
public $api_search_GOOGLE_API_KEY = '<REDACTED:GOOGLE_API_KEY_NEWS>';
public $api_search_GOOGLE_CX = '<REDACTED:GOOGLE_CX>';
public $path = '...data/news/';
public $path_shorts = '...data/news/shorts/';
public $keywords = 'новини, останні новини, ...';   // 50+ ключів
```

#### `actionUpload_to_youtube($limit=1, $id_yt_acc=55)`

```php
ini_set('memory_limit', '512M');

$voice_choice = random([{male,fable},{male,echo},{female,alloy},{female,shimmer}]);
$audio = $path . 'audio.mp3';
$modelDate = (new DateTime('+0 hours', 'Europe/Kyiv'))->format('Y-m-d H:i');

// 1) Тягнемо нову новину
$news = $this->actionRbcFirstNews();   // {title, link, description, fulltext, pubDate, image}

// 2) SerpAPI Google Images
$images = $this->rest_api_search_images($news['title']);   // 5 фото >= 1200px wide

MyFunction::deleteDir($path . 'images/');
mkdir($path . 'images/', 0775, true);
foreach ($images as $i => $img) downloadImage($img, $path . 'images/' . ($i+1) . '.jpg');

// 3) TTS озвучка fulltext
$text_audio = $this->cleanNewsText($news['fulltext']);   // strip "Читайте также", "Фото:", URLs etc.
$this->actionTts_openai(1, $text_audio, $audio, 'uk', $voice_choice['gender'], '', $voice_choice['voice'], 'news');

// 4) Генерація субтитрів через make_srt.py
$textFile = $path . 'text.txt';
$this->makeTextFileFromNews($news['title'], $news['fulltext'], $textFile);
$cmd = sprintf('python3 %s %s %s %s 2>&1',
    escapeshellarg($path . 'make_srt.py'),
    escapeshellarg($path . 'audio.mp3'),
    escapeshellarg($textFile),
    escapeshellarg($path . 'sub.srt')
);
exec($cmd, $output, $code);

// 5) Slideshow з 5 фото + Ken Burns ефектом → youtube_video.mp4
$this->makeYoutubeVideoFrom5Images($path);

// 6) Insert task
$task->account_id = $id_yt_acc;   // 55
$task->title = $title . ' ' . return_hashtag(2);
$task->description = $news['fulltext'] . ' ' . return_hashtag(5);
$task->keywords = return_hashtag(5);
$task->att_file_path = $path . 'youtube_video.mp4';
$task->save(false);
```

#### `actionShorts($id_yt_acc=55)` — те ж саме, але:
- Слухає `$news['description']` (короткий, не fulltext)
- ffmpeg `makeShortsFrom5Images($path_shorts)` — 1080×1920
- `addSubtitlesToShorts($path_shorts)` — burn-in
- `att_file_path = $path_shorts . 'shorts_final.mp4'`

#### `actionRbcFirstNews(): ?array`

```php
$url = 'https://www.rbc.ua/static/rss/all.ukr.rss.xml';
$usedFile = $path_shorts . 'rbc_used_links.txt';

$xml = simplexml_load_string(file_get_contents($url), 'SimpleXMLElement', LIBXML_NOCDATA);
$usedLinks = file($usedFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);

foreach ($xml->channel->item as $item) {
    $link = trim($item->link);
    if (in_array($link, $usedLinks)) continue;

    // image: спочатку enclosure, потім media:content
    $image = $item->enclosure?->attributes()['url']
          ?? $item->children('media', true)?->content?->attributes()['url']
          ?? null;

    $news = [
        'title' => trim($item->title),
        'link' => $link,
        'description' => trim(strip_tags($item->description)),
        'fulltext' => trim(strip_tags($item->fulltext)),
        'pubDate' => trim($item->pubDate),
        'image' => $image,
    ];

    file_put_contents($usedFile, $link . PHP_EOL, FILE_APPEND | LOCK_EX);
    return $news;
}

return null;   // нових новин нема
```

#### `rest_api_search_images($q): array` — SerpAPI

```php
require 'google-search-results.php';
require 'restclient.php';

$query = [
    "engine" => "google_images",
    "q" => $q,
    "google_domain" => "google.com",
    "hl" => "en", "gl" => "us",
];

$search = new \GoogleSearch('<REDACTED:SERPAPI_KEY>');
$result = $search->get_json($query);

$cnt = 0;
foreach ($result->images_results as $img) {
    if ($img->original_width >= 1200) {
        if (getExtensionFromUrl($img->original) == 'jpg') {
            $images_results_total[] = $img->original;
            $cnt++;
        }
    }
    if ($cnt >= 5) break;
}
return $images_results_total;
```

#### `googleImagesSearch($query, $limit=3): array` — fallback Google Custom Search

```php
$url = 'https://www.googleapis.com/customsearch/v1?' . http_build_query([
    'key' => $apiKey, 'cx' => $cx, 'q' => $query,
    'searchType' => 'image', 'num' => min($limit, 10),
    'safe' => 'active', 'imgSize' => 'large', 'fileType' => 'jpg',
    'rights' => 'cc_publicdomain,cc_attribute,cc_sharealike',
]);
```

#### `makeYoutubeVideoFrom5Images($workDir): string` — Long video з Ken Burns

```php
$audio = "$workDir/audio.mp3";
$output = "$workDir/youtube_video.mp4";
$images = ["$workDir/images/1.jpg", ..., "$workDir/images/5.jpg"];
$count = 5; $fps = 25; $width = 1920; $height = 1080;

$duration = (float) trim(shell_exec('ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 ' . escapeshellarg($audio)));
$perImage = round($duration / $count, 3);
$frames = (int) round(($duration / $count) * $fps);

// 5 inputs з -loop 1
$inputs = '';
foreach ($images as $img) $inputs .= ' -loop 1 -i ' . escapeshellarg($img);

// Filter complex з Ken Burns ефектом
$filters = '';
$concat = '';
foreach ($images as $i => $img) {
    $filters .= "[{$i}:v]"
        . "scale={$width}:{$height}:force_original_aspect_ratio=increase,"
        . "crop={$width}:{$height},"
        . "setsar=1,"
        . "zoompan=z='1+0.00012*on':d={$frames}:s={$width}x{$height}:fps={$fps},"   // ⭐ Ken Burns
        . "trim=duration={$perImage},"
        . "setpts=PTS-STARTPTS,"
        . "format=yuv420p"
        . "[v{$i}];\n";
    $concat .= "[v{$i}]";
}
$filters .= "{$concat}concat=n={$count}:v=1:a=0[v]";

$cmd = 'ffmpeg -y'
    . $inputs
    . ' -i ' . escapeshellarg($audio)
    . ' -filter_complex ' . escapeshellarg($filters)
    . ' -map "[v]" -map ' . count . ':a'
    . ' -c:v libx264 -preset veryfast -r ' . $fps
    . ' -c:a aac -b:a 192k'
    . ' -movflags +faststart '
    . escapeshellarg($output);

exec($cmd, $log, $code);
```

`zoompan=z='1+0.00012*on'` — повільний зум (на 0.012% per frame, ~3% за 5сек) — Ken Burns effect.

#### `makeShortsFrom5Images($workDir)` — те ж саме але `scale=1080:1920, crop=1080:1920` → `shorts.mp4`.

#### `addSubtitlesToShorts($workDir)` — burn-in субтитри

```php
$style = "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
       . "BorderStyle=1,Outline=4,Shadow=2,Alignment=2,MarginV=160";

$subsForFilter = str_replace("'", "\\'", $subs);
$vf = "subtitles='{$subsForFilter}':force_style='{$style}'";

exec('ffmpeg -y -i ' . escapeshellarg($input) . ' -vf ' . escapeshellarg($vf) . ' -c:a copy ' . escapeshellarg($output));
```

ASS-style: white text, black 4px outline, shadow 2px, Alignment 2 (bottom-center), MarginV 160 (від низу).

#### `makeTextFileFromNews($title, $content, $outFile)`

```php
$text = $title . ". " . $content;
$text = strip_tags($text);
$text = html_entity_decode($text, ENT_QUOTES | ENT_HTML5, 'UTF-8');

// Видалити патерни
$removePatterns = [
    '/Читайте також:.*/iu',
    '/Об этом сообщает.*$/iu',
    '/Про це повідомляє.*$/iu',
    '/Фото:.*$/iu',
    '/Источник:.*$/iu',
    '/Джерело:.*$/iu',
];
foreach ($removePatterns as $p) $text = preg_replace($p, ' ', $text);
$text = preg_replace('~https?://\S+~iu', ' ', $text);   // remove URLs
$text = preg_replace('/\s+/u', ' ', $text);             // collapse whitespace
$text = trim($text);

if (!$text) throw 'Порожній текст новини після очистки';
file_put_contents($outFile, $text);
```

#### `cleanNewsText($text): string` — інша clean функція (без regex remove patterns):
- html_entity_decode, strip_tags
- regex remove "Читайте также:" line, "Фото: ..." line, parens `(...)` 
- `preg_replace('/^\s*[-–•]\s*/mu', '', $text)` — remove list markers
- collapse whitespace, trim

#### `create_youtube_image()` (NewsController version)
Те ж саме що в DLE-контролерах + спец-логіка:
- Top text background — нюанс зі сторонами
- Якщо текст > 10 слів — ділиться на 3 рядки; > 3 — на 2; інакше 1
- Колір — `imagecolorallocate(49, 232, 74)` (зелений)

#### `actionTest()` — placeholder з hardcoded sample про ОАЕ + ОПЕК (мова ru, стиль news).

### 13.9 `Shorts_from_videoController` (434 рядки) ⭐ Donor → Whisper → 5 highlights

```php
public $path = '...data/shorts_from_video/';
var $api_key_google = '<REDACTED:GOOGLE_API_KEY_SHORTS>';
var $api_key = '<REDACTED:OPENAI_KEY>';

public $arr_data = [
    28 => [...],   // @xobiATVUA (квадроцикли)
    31 => [...],   // @babysmilevlog (дитячий) — 6 донорів
    34 => [...],   // @Новини_1 (новини UA) — 4 донори
];
```

(Конфіг arr_data — див. §17 для повного.)

#### `actionShorts_from_donors($id_yt_acc=31)` — оркестратор

```php
$done_path = $path . "youtube_links_done_{$id_yt_acc}.txt";
$links_file = $path . 'youtube_links_' . $id_yt_acc . '.txt';

if (file_exists($links_file)) unlink($links_file);

$lines = file_exists($done_path) ? file($done_path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];

$donors = $this->arr_data[$id_yt_acc]['donors'];

$all_videos = [];
foreach ($donors as $donor) {
    $videos = $this->get_youtube_links($donor['channel_id']);   // ⭐ YouTube Data API
    $all_videos = array_merge($all_videos, $videos);
}

// Dedup by videoId
$unique = [];
foreach ($all_videos as $item) $unique[$item['videoId']] = $item;
$all_videos = array_values($unique);

// Sort by date desc
usort($all_videos, fn($a, $b) => strtotime($b['date']) - strtotime($a['date']));

foreach ($all_videos as $video) {
    if (!in_array($video['videoId'], $lines)) {
        file_put_contents($links_file, 'https://www.youtube.com/watch?v=' . $video['videoId'] . PHP_EOL, FILE_APPEND);
    }
}

$this->actionShorts($id_yt_acc, $this->arr_data[$id_yt_acc]['channel_id']);
```

#### `get_youtube_links($channelId): array`

```php
$maxResults = 50;
$url = "https://www.googleapis.com/youtube/v3/search?key={$this->api_key_google}"
     . "&channelId={$channelId}&part=snippet,id&order=date&maxResults={$maxResults}";

$data = json_decode(file_get_contents($url), true);

$result = [];
foreach ($data['items'] as $item) {
    if ($item['id']['kind'] !== 'youtube#video') continue;
    $videoId = $item['id']['videoId'];

    // Get duration через videos endpoint
    $vinfo_url = "https://www.googleapis.com/youtube/v3/videos?key={$this->api_key_google}"
              . "&id={$videoId}&part=snippet,contentDetails";
    $vinfo = json_decode(file_get_contents($vinfo_url), true);
    if (empty($vinfo['items'])) continue;

    $duration_iso = $vinfo['items'][0]['contentDetails']['duration'];   // ISO8601 PT12M30S
    $seconds = $this->convertYouTubeDurationToSeconds($duration_iso);   // через DateInterval

    // ⭐ Filter: тільки відео > 10 хвилин
    if ($seconds < 600) continue;

    $result[] = [
        'title' => $item['snippet']['title'],
        'date' => $item['snippet']['publishedAt'],
        'videoId' => $videoId,
        'duration_seconds' => $seconds,
        'thumb' => $item['snippet']['thumbnails']['high']['url'],
    ];
}
return $result;
```

#### `actionShorts($id_yt_acc=28, $channel_link)`

```php
// 1) Cleanup
unlink old artifacts (input, audio, transcript, meta), deleteDir(shorts_<id>, thumbnails_<id>)

// 2) Run Python
$python_bin = '/var/www/.../yii/venv/bin/python3';
$script_path = '/var/www/.../yii/console/controllers/shorts_from_video/shorts_from_video.py';
$links_file = '...data/shorts_from_video/youtube_links_' . $id_yt_acc . '.txt';
$lang = $this->arr_data[$id_yt_acc]['lang'];

$cmd = "OPENAI_API_KEY='$this->api_key' $python_bin $script_path $links_file $id_yt_acc $lang 2>&1";
exec($cmd, $output, $return_var);

// 3) Read shorts_meta_<id>.json (5 highlights)
$meta = json_decode(file_get_contents($path . "shorts_meta_$id_yt_acc.json"), true);

// 4) Schedule 4 публікації за фіксованими годинами
$dates = generatePlannedDates(today, 4, ['09:00', '12:40', '17:17', '20:10']);

foreach ($meta as $key => $highlight) {
    $modelDate = $dates[$key] ?? null;

    $output_file_mp4 = $path . 'shorts_' . $id_yt_acc . '/short_0' . ($key + 1) . '_VERT_BG.mp4';   // ⭐ використовується VERT_BG variant
    $title = $highlight['title'];
    $video_description = $highlight['summary'];
    $comment = $highlight['comment'];

    // Thumbnail processing
    $input_thumb = $path . "thumbnails_$id_yt_acc/short_0" . ($key + 1) . "_H.png";
    $output_thumb = $path . "thumbnails_$id_yt_acc/short_0" . ($key + 1) . "_H_final.png";
    $output_thumb_text = $path . "results/short_0" . ($key + 1) . "_H_final_t.png";
    $fontPath = $path . "fonts/lena.ttf";

    $this->cropTo1080x1920($input_thumb, $output_thumb);
    $this->addTextToImage($output_thumb, $output_thumb_text, $channel_link, $fontPath);

    // Insert task
    $task = new Tasks();
    $task->account_id = $id_yt_acc;
    $task->media_type = 'youtube';
    $task->status = 0;
    $task->date_add = new Expression('NOW()');
    $task->att_file_path = $output_file_mp4;
    $task->cover = $input_thumb;
    $task->title = $title . ' ' . return_hashtag(2, $id_yt_acc);
    $task->description = $video_description . ' ' . return_hashtag(5, $id_yt_acc);
    $task->keywords = return_hashtag(5, $id_yt_acc);
    $task->post_comment = $comment;
    $task->date_post = $modelDate;
    $task->save(false);
}

// 5) Pop URL з queue file
array_shift($lines);
file_put_contents($links_file, implode(PHP_EOL, $lines));
```

#### `cropTo1080x1920($input, $output)` — smart crop preserving aspect ratio

```php
$src_w = imagesx($img); $src_h = imagesy($img);
$dst_w = 1080; $dst_h = 1920;
$src_ratio = $src_w / $src_h;
$dst_ratio = $dst_w / $dst_h;   // = 0.5625

if ($src_ratio > $dst_ratio) {
    // Source ширше → crop по ширині (fix висоту)
    $new_w = intval($src_h * $dst_ratio);  $new_h = $src_h;
    $src_x = ($src_w - $new_w) / 2;        $src_y = 0;
} else {
    // Source вище → crop по висоті
    $new_w = $src_w;                       $new_h = intval($src_w / $dst_ratio);
    $src_x = 0;                            $src_y = ($src_h - $new_h) / 2;
}

$dst = imagecreatetruecolor($dst_w, $dst_h);
imagecopyresampled($dst, $img, 0, 0, $src_x, $src_y, $dst_w, $dst_h, $new_w, $new_h);
imagejpeg($dst, $output, 90);
```

#### `addTextToImage($input, $output, $text, $fontPath)` — overlay channel link

- White text, font size 70px
- Black shadow `(x+4, y+4)`
- Centered horizontally
- Position `y = height - 120` (внизу на 120px відступ)

#### `return_hashtag($cnt=5, $id_yt_acc): string`

```php
$keywords = $this->arr_data[$id_yt_acc]['keywords'];
$keywords_arr = array_map('trim', explode(',', $keywords));
shuffle($keywords_arr);
$rnd = array_slice($keywords_arr, 0, $cnt);
$with_hash = array_map(fn($k) => '#' . str_replace(' ', '_', $k), $rnd);
return implode(' ', $with_hash);
```

#### `convertYouTubeDurationToSeconds($duration): int` — ISO 8601 → seconds через `\DateInterval`.

### 13.10 `Stream_youtubeController` (464 рядки)

**Дублікат `Shorts_from_videoController`** з ідентичним arr_data (28+31, без 34) + 1 додаткова дія.

#### `actionUpload_yt()` — yt-dlp downloader

```php
$urls = [
    'https://www.youtube.com/shorts/BZ7JbTYNva0',
    'https://www.youtube.com/shorts/Flt05vbPaPE',
    'https://www.youtube.com/shorts/9z1zxCC6jVM',
    'https://www.youtube.com/shorts/p0f9stNeS-s',
    'https://www.youtube.com/shorts/JhXs_-_SMzU',
    'https://www.youtube.com/shorts/8qxHhGqsaOo',
    'https://www.youtube.com/shorts/Hd37a3-PZLY',
];   // hardcoded 7 URLs

$downloadDir = '...data/streams/downloads_shorts';
$ytDlpPath = trim(shell_exec('which yt-dlp'));

foreach ($urls as $url) {
    $cmd = sprintf('%s -f mp4 -o %s/%s %s 2>&1',
        escapeshellarg($ytDlpPath),
        escapeshellarg($downloadDir),
        escapeshellarg('%(id)s.%(ext)s'),
        escapeshellarg($url));
    exec($cmd, $output, $returnVar);
}
```

Чисто seed-функція. Решта логіки 1-в-1 з Shorts_from_video.

### 13.11 `SoraController` (672 рядки) ⭐ Sora virality

```php
public $path = '...data/unique_audio';            // ⚠️ note: shared with Unique_audio!
public $path_shorts = '...data/sora/shorts/';
public $api_gpt = '<REDACTED:OPENAI_KEY>';
```

#### `actionTest()`
```php
$url = 'https://sora.chatgpt.com/backend/public/nf2/feed';
$data_url = MyFunction::getHtml_zenrows_2($url);
$json = json_decode($data_url, 1);
print_r($json);
```

#### `actionGet_video($channel_id=19)` — оркестратор

```php
$url = 'https://sora.chatgpt.com/backend/public/nf2/feed';
$file_ids = $path_shorts . 'used_posts.txt';
$dates = generatePlannedDates(today, 3, ['12:00', '14:00', '17:00']);

if (!file_exists($file_ids)) file_put_contents($file_ids, '');
$used_ids = file($file_ids, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);

$data_url = MyFunction::getHtml_zenrows_2($url);   // ⚠️ premium_proxy=true
$json = json_decode($data_url, 1);

$done = 0;
foreach ($json['items'] as $key_d => $data) {
    $post_id = $data['post']['id'];
    $video_url = $data['post']['attachments'][0]['url'];
    $views = $data['post']['unique_view_count'];

    // ⭐ FILTER: views > 1000
    if ($views > 1000 && !in_array($post_id, $used_ids)) {
        $modelDate = $dates[$done] ?? null;

        downloadFileffmpeg($video_url, $path_shorts . $post_id . '.mp4', 'https://sora.chatgpt.com');
        $this->actionShorts($channel_id, $path_shorts . $post_id . '.mp4', $post_id, $modelDate);

        file_put_contents($file_ids, $post_id . PHP_EOL, FILE_APPEND);
        $done++;
        if ($done > 2) exit;   // ⭐ MAX 3 за раз
    }
}
```

#### `actionShorts($id_yt_acc=19, $video_path, $post_id, $modelDate)` — повна послідовність

```php
// 1) Get duration
$audio_duration = (float) trim(shell_exec("ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 \"$video_path\""));

// 2) Витягнути 3 кадри: 20%, 50%, 80%
$points = [$audio_duration * 0.2, $audio_duration * 0.5, $audio_duration * 0.8];

$results = [];
foreach ($points as $i => $time) {
    $frame_file = "{$path_shorts}frame_" . ($i + 1) . ".jpg";
    $timeFormatted = gmdate("H:i:s", (int) $time);
    exec("ffmpeg -ss $timeFormatted -i $video_path -vframes 1 -q:v 2 $frame_file");

    // 3) GPT-4o-mini Vision опис
    $imageData = base64_encode(file_get_contents($frame_file));
    $payload = [
        "model" => "gpt-4o-mini",
        "messages" => [[
            "role" => "user",
            "content" => [
                ["type" => "text", "text" => "Опиши коротко цей кадр у 2-3 реченнях. Вкажи емоцію, атмосферу і можливий підтекст."],
                ["type" => "image_url", "image_url" => ["url" => "data:image/jpeg;base64," . $imageData]]
            ]
        ]]
    ];

    POST api.openai.com/v1/chat/completions з payload;
    $description = $json['choices'][0]['message']['content'];
    $results[] = ['frame' => $frame_file, 'description' => $description];
}

// 4) Save frame descriptions
$descFile = $path_shorts . "frames_description.txt";
$text = '';
foreach ($results as $r) $text .= basename($r['frame']) . ":\n" . $r['description'] . "\n\n";
file_put_contents($descFile, $text);

// 5) Generate funny meme caption (GPT-4o-mini)
$anotation = $this->generateFunnyCaption($descFile);

// 6) Generate JSON metadata з retry до 5 спроб
$maxAttempts = 5;
$attempt = 0;
$meta = false;
while ($meta === false && $attempt < $maxAttempts) {
    $attempt++;
    $meta = $this->generateShortsMetaWithAI($anotation);
    if ($meta === false) sleep(3);
}

// 7) Strip emojis
$anotation = preg_replace('/[\x{1F300}-\x{1FAFF}]/u', '', $anotation);
$anotation = preg_replace('/[\x{2600}-\x{26FF}]/u', '', $anotation);
$anotation = preg_replace('/[\x{2700}-\x{27BF}]/u', '', $anotation);
$anotation = trim($anotation);

// 8) Wordwrap 40 chars
$wrapped = wordwrap($anotation, 40, "\n", true);

// Escape для ffmpeg drawtext
$wrapped = str_replace("'", "\\'", $wrapped);
$wrapped = str_replace('"', '\\"', $wrapped);
$wrapped = str_replace(":", "\\:", $wrapped);

// 9) ffmpeg drawtext знизу-центру
$font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf";
$outVid = $path_shorts . "sora_{$post_id}_shorts.mp4";

$cmd = "ffmpeg -i " . escapeshellarg($video_path)
     . " -vf \"drawtext=text='$wrapped':"
     . "fontcolor=white:"
     . "fontsize=32:"
     . "fontfile=" . escapeshellarg($font) . ":"
     . "line_spacing=8:"
     . "box=1:boxcolor=black@0.5:boxborderw=12:"
     . "x=(w-text_w)/2:y=h-text_h-50:"
     . "fix_bounds=true:text_shaping=1\""
     . " -codec:a copy -y " . escapeshellarg($outVid);
exec($cmd, $out, $res);

// 10) Insert task
$shuffle_hashtags = $meta['hashtags'];
shuffle($shuffle_hashtags);

$task = new Tasks();
$task->account_id = $id_yt_acc;   // 19 by default
$task->media_type = 'youtube';
$task->status = 0;
$task->date_add = new Expression('NOW()');
$task->att_file_path = trim($outVid, "'");
$task->cover = '';
$task->title = $meta['title'] . implode(' ', array_slice($shuffle_hashtags, 0, 2));
$task->description = $meta['description'] . ' ' . implode(' ', $meta['hashtags']);
$task->keywords = implode(' ', $meta['hashtags']);
$task->post_comment = $meta['first_comment'];
$task->date_post = $modelDate;
$task->save(false);
```

#### `generateFunnyCaption($desc_file): string|false`

```php
$prompt = <<<PROMPT
Ти — креативний сценарист для TikTok / YouTube Shorts.
На основі коротких описів трьох кадрів з відео створи 1 гумористичний опис (1-2 речення), у стилі мемів або короткої фрази або легкий гумор для підпису до відео.

Будь дотепним, але не грубим. Стиль — іронічний, легкий, ніби короткий мем у соцмережах.

Ось описи кадрів:
$descriptions

Формат відповіді: тільки готовий короткий текст для опису (без пояснень і лапок).
PROMPT;

$payload = ['model' => 'gpt-4o-mini', 'messages' => [['role' => 'user', 'content' => $prompt]],
            'temperature' => 0.9, 'max_tokens' => 100];

POST openai → return $caption;
```

#### `generateShortsMetaWithAI($caption_text): array|false`

```php
$prompt = <<<PROMPT
Ти — креативний сценарист YouTube Shorts, який створює короткі гумористичні тексти.

На основі цього тексту створи:
1. "title" — коротку, чіпляючу назву (до 70 символів, у стилі мемів);
2. "description" — 1–2 речення з легким гумором і розмовним тоном українською;
3. "hashtags" — до 15 штук, у форматі #shorts #гумор #меми ...;
4. "first_comment" — перший коментар від автора (жарт, запитання до глядачів, або дотепна реакція, щоб стимулювати коментарі).

Текст із відео:
---
$caption_text
---

Відповідь поверни строго у JSON:
{
  "title": "...",
  "description": "...",
  "hashtags": ["#...", "#...", "..."],
  "first_comment": "..."
}
PROMPT;

$payload = ['model' => 'gpt-4o-mini', 'temperature' => 0.9, 'max_tokens' => 300];
$reply = response;
$meta = json_decode($reply, true);
if (!$meta || !isset($meta['title'])) return false;
return $meta;
```

### 13.12 `StreamController (console)` (149 рядків)

HTTP-style controller, але в console namespace. AccessControl `@`.

```php
private function jsonOk(array $data = []) → response = JSON, return ['ok' => true, ...$data]
private function jsonFail(string $message, array $extra = []) → return ['ok' => false, 'message' => ..., ...$extra]
private function requireId(): int → throw BadRequestHttpException якщо нема
private function sh(string $cmd): array → exec, return [code, stdout]
private function systemctl(string $action, string $serviceName): array → sh('sudo systemctl {action} {service}')

actionStart() — Stream::findOne → YoutubeAccount → YoutubeService::prepareBroadcastForStart → systemctl start
actionStop() — systemctl stop + try transitionBroadcast(complete)
actionRestart() — systemctl restart
```

### 13.13 `YtController` (317 рядків) ⭐ Provisioning

```php
public $restart = 0;   // CLI option
public $enable = 0;

options($actionID) = ['restart', 'enable']
optionAliases() = ['r' => 'restart', 'e' => 'enable']
```

#### `actionSyncOne($id, $restart=0, $enable=0): int` — синк одного стріму

```php
$s = Stream::findOne($id);
return $this->syncStream($s, (int)$restart === 1, (int)$enable === 1);
```

#### `private syncStream(Stream $s, bool $restart, bool $enable): int`

1. Validate `name` непорожній
2. mkdir `data/streams/{name}/videos` 0755 recursive
3. **Install global runner** якщо немає або md5 differs:
   ```php
   if (!is_file($runnerPath) || md5_file($runnerPath) !== md5($runner)) {
       file_put_contents($runnerPath, $runner);
       chmod($runnerPath, 0755);
   }
   ```
4. Якщо `$s->runner_path` непорожнє і не існує → копіює global runner туди
5. **Write env file** (ідемпотентно — only якщо contents differ):
   ```
   STREAM_NAME={name}
   STREAM_KEY={stream_key}
   INPUT_DIR={videosDir}
   RTMP_HOST=a.rtmp.youtube.com
   RUNTIME_MAX=42900
   ```
   chmod 0600.
6. **Write systemd unit** (ідемпотентно):
   ```ini
       # {name}
       [Unit]
       Description=YouTube Stream: {name}
       After=network-online.target
       Wants=network-online.target
       
       [Service]
       Type=simple
       WorkingDirectory={workDir}
       EnvironmentFile={envPath}
       ExecStart=/usr/bin/env bash {runnerPath}
       Restart=on-failure
       RestartSec=3
       KillSignal=SIGINT
       KillMode=control-group
       TimeoutStopSec=60
       SuccessExitStatus=0 130 255
       StandardOutput=journal
       StandardError=journal
       
       [Install]
       WantedBy=multi-user.target
   ```
   chmod 0644.
7. `systemctl daemon-reload`. Optional `enable` + `restart`.
8. **Sync DB:**
   ```php
   $s->service_name = "stream-{name}.service";
   $s->workdir = $workDir;
   $s->save(false);
   ```

#### `actionMassSyncServices(): int` — синк ВСІХ stream rows

1. Force install runner (без md5-check)
2. mkdir base dirs
3. `Stream::find()->orderBy(['id'=>SORT_ASC])->all()` → for each: `syncStream($s, $restart, $enable)`
4. Підраховує `changed` vs `skipped`

#### `private getRunnerScript(): string` — same як в StreamProvisionerService.

### 13.14 `Youtube_statsController` (178 рядків)

```php
public const API_KEY = '<REDACTED:GOOGLE_API_KEY_STATS>';
```

#### `actionStat()`

```php
date_default_timezone_set('Europe/Kyiv');
$today = (new DateTime('today'))->format('Y-m-d');

$models = YoutubeChannels::find()->where(['stat' => 1])->all();   // ⭐ тільки з прапором stat=1

foreach ($models as $model) {
    $channelId = $this->resolveChannelId($model->channel_id);
    if (!$channelId) continue;

    $stats = $this->fetchChannelStats($channelId);
    if (!$stats) continue;

    $this->saveDailySnapshot($model->id, $channelId, $today, $stats);
}
```

#### `resolveChannelId($input): ?string`

```php
// Якщо вже UC-id (regex ^UC[0-9A-Za-z_-]{22}$) → pass-through
if (preg_match('~^UC[0-9A-Za-z_-]{22}$~', $input)) return $input;

// Якщо @handle
if ($input[0] === '@') {
    $id = $this->resolveViaForHandle($input);   // GET channels?part=id&forHandle=
    if ($id) return $id;
    
    $id = $this->resolveViaSearch($input);      // GET search?type=channel&maxResults=1&q=
    return $id;
}

// Інакше — fallback search
return $this->resolveViaSearch($input);
```

#### `fetchChannelStats($channelId): ?array`

```php
$url = "https://www.googleapis.com/youtube/v3/channels?part=statistics&id={$channelId}&key=" . self::API_KEY;
$json = $this->httpGetJson($url);
$st = $json['items'][0]['statistics'];

return [
    'subscribers' => $st['hiddenSubscriberCount'] ? null : (int)$st['subscriberCount'],
    'views' => (int) ($st['viewCount'] ?? null),
    'videos' => (int) ($st['videoCount'] ?? null),
];
```

#### `saveDailySnapshot($yt_id, $channelId, $date, $stats)` — UPSERT в `youtube_channel_daily`

#### `static actionShow_compare()` — пустий заглушок (yesterday vs day-before).

### 13.15 `ChatGPT.php` (92 рядки) — застарілий wrapper

```php
class ChatGPT {
    private $API_KEY = "<REDACTED:OPENAI_KEY_OLD>";   // ⚠️ leaked
    private $textURL = "https://api.openai.com/v1/chat/completions";
    private $imageURL = "https://api.openai.com/v1/images/generations";

    public function createTextRequest($prompt, $model='text-davinci-003', $temperature=0.5, $maxTokens=1000): string|int {
        // ⚠️ text-davinci-003 ВИВЕДЕНА (deprecated by OpenAI 2024-01-04)
        // На практиці викликають з gpt-4-turbo / gpt-3.5-turbo (DLE controllers)
        $messages = ['role' => 'user', 'content' => $prompt];
        $data["model"] = $model;
        $data["messages"][] = $messages;
        $data["temperature"] = $temperature;
        $data["max_tokens"] = $maxTokens;
        POST textURL з API_KEY;
        return $response['choices'][0]['message']['content'] ?? -1;
    }

    public function generateImage($prompt, $imageSize='512x512', $numberOfImages=1): string|int {
        $data["prompt"] = $prompt; $data["n"] = $numberOfImages; $data["size"] = $imageSize;
        POST imageURL;
        return $response['data'][0]['url'] ?? -1;
    }
}
```

Використовується в DLE-контролерах (Audiokniga, Books_online_info, ...) через `get_new_text(prompt, 'gpt-4-turbo')`. Для Sora/Shorts — використовують прямі POST'и до chat/completions замість цього wrapper'а.

### 13.16 SerpAPI helper files

#### `console/controllers/google-search-results.php` (304 рядки)
SerpAPI PHP client (від офіційного `serpapi/google-search-results-php` пакету). Класи `GoogleSearch`, `BaseSearch`. Методи:
- `get_json($params)` — GET-запит з API key
- `get_html($params)`
- `get_search_archive($search_id)`

#### `console/controllers/restclient.php` (278 рядків)
Generic HTTP REST-client (curl wrapper з parse JSON). Foundation для google-search-results.php.

---

## 14. Console DLE моделі

Кожен з 7 DLE-сайтів має 4-5 ActiveRecord моделей в `console/models/<source>/`. Усі мають `getDb()` що повертає `Yii::$app->get('db_<source>')` — окреме MySQL з'єднання, налаштоване в `console/config/main-local.php`.

### 14.1 `DlePost` — основна таблиця книги

```php
namespace console\models\<source>;
class DlePost extends ActiveRecord {
    static tableName() = 'dle_post';
    static getDb() = Yii::$app->get('db_<source>');

    rules() = [
        ['date', 'safe'],
        [['short_story','full_story','xfields','keywords'], 'required'],
        [['short_story','full_story','xfields','keywords'], 'string'],
        [['comm_num','allow_comm','allow_main','approve','fixed','allow_br'], 'integer'],
        ['autor', 'string', 'max' => 40],
        [['title','tags','metatitle','url_dest'], 'string', 'max' => 255],
        ['descr', 'string', 'max' => 300],
        [['category','alt_name'], 'string', 'max' => 190],
        ['symbol', 'string', 'max' => 3],
        ['status', 'safe'],
    ];

    getExtrasCats() = hasMany(DlePostExtrasCats, ['news_id' => 'id']);
    getCategories() = hasMany(DleCategory, ['id' => 'cat_id'])->via('extrasCats');
    getPostextras() = hasOne(DlePostExtras, ['news_id' => 'id']);
}
```

**Поля БД:**
| Поле | Тип | Опис |
|---|---|---|
| `id` | INT | PK |
| `autor` | VARCHAR(40) | Автор поста (admin user, не книжний автор!) |
| `date` | DATETIME | created |
| `short_story` | TEXT | Короткий опис (анотація) — використовується для TTS |
| `full_story` | TEXT | Повний опис |
| `xfields` | TEXT | DLE custom fields (key1\|val1\|\|key2\|val2\|\|...) |
| `title` | VARCHAR(255) | Назва поста |
| `descr` | VARCHAR(300) | Meta description |
| `keywords` | TEXT | Meta keywords |
| `category` | VARCHAR(190) | comma-separated cat IDs |
| `alt_name` | VARCHAR(190) | URL slug |
| `comm_num` | INT | Кількість коментарів |
| `allow_comm`, `allow_main`, `approve`, `fixed`, `allow_br` | INT (0/1) | Прапори DLE |
| `symbol` | VARCHAR(3) | DLE symbol |
| `tags` | VARCHAR(255) | comma-separated tags |
| `metatitle` | VARCHAR(255) | OG title |
| `url_dest` | VARCHAR(255) | redirect URL |
| `book_id` | INT | DLE book unique id (на 5 з 7 — knigi-audio, audiokniga, club-books, slushat, bazaknig) |

### 14.2 `DlePostExtras` — статистика читань ⭐ VIRALITY

```php
class DlePostExtras extends ActiveRecord {
    static tableName() = 'dle_post_extras';
    static getDb() = ...db_<source>;
}
```

**Поля БД:**
| Поле | Тип | Призначення |
|---|---|---|
| `eid` | INT | PK |
| `news_id` | INT | FK на dle_post.id |
| **`news_read`** | **INT** | **⭐ КЛЮЧОВА МЕТРИКА — кількість читань на DLE-сайті** |
| `allow_rate` | INT | 0/1 |
| `rating` | INT | сума оцінок |
| `vote_num` | INT | кількість голосів |
| `votes` | INT | агрегований bytes |
| `view_edit` | INT | 0/1 |
| `disable_index` | INT | 0/1 SEO flag |
| `related_ids` | VARCHAR(255) | comma-separated related |
| `access` | VARCHAR(150) | access list |
| `editdate` | INT | unix timestamp |
| `editor` | VARCHAR(40) | username |
| `reason` | VARCHAR(255) | edit reason |
| `user_id` | INT | author |
| `disable_search` | INT | 0/1 |
| `need_pass` | INT | 0/1 (paywall) |

**Yii2 query використовує `dle_post_extras.news_read DESC` як virality criterion:**
```php
DlePost::find()->joinWith(['postextras'])->orderBy('dle_post_extras.news_read DESC')
```

### 14.3 `DlePostExtrasCats` — M:N зв'язок постів і категорій

```php
class DlePostExtrasCats extends ActiveRecord {
    static tableName() = 'dle_post_extras_cats';
    rules() = [[['news_id', 'cat_id'], 'integer']];
}
```

Поля: `id, news_id, cat_id`. Один DLE-пост може належати до кількох категорій.

### 14.4 `DleCategory` — DLE категорії

```php
class DleCategory extends ActiveRecord {
    static tableName() = 'dle_category';
    rules() = [
        [['parentid','posi','news_number','show_sub','allow_rss','disable_search','disable_main','disable_rating','disable_comments'], 'integer'],
        [['keywords','fulldescr','xfields'], 'required'],
        [['keywords','fulldescr','xfields'], 'string'],
        [['name','alt_name','skin'], 'string', 'max' => 50],
        ['icon', 'string', 'max' => 200],
        ['descr', 'string', 'max' => 300],
        ['news_sort', 'string', 'max' => 10],
        ['news_msort', 'string', 'max' => 4],
        [['short_tpl','full_tpl'], 'string', 'max' => 40],
        ['metatitle', 'string', 'max' => 255],
    ];
}
```

Поля: `id, parentid (для tree-структури), posi (порядок), name, alt_name, icon, skin, descr, keywords, news_sort, news_msort, news_number, short_tpl, full_tpl, metatitle, show_sub, allow_rss, fulldescr, disable_search, disable_main, disable_rating, disable_comments, xfields`.

**Категорії що використовуються в коді:**
- `'15'` (книжкова) — `Books_online_info`, `Slushat_knigi_com`, `Club_books_ru`
- `'12'` (попаданцы) — `Unique_audio` (knigi_audio_biz)

### 14.5 `DleTags` — теги (на 6 з 7 DBs)

Поля: `id, news_id, tag`. M:N теги для постів. `knigi_audio_biz` НЕ має цієї моделі.

### 14.6 Stati xfields у книжкових pipeline'ах

Найпоширеніші xfields keys (з усіх 7 DLE):

| Key | Тип | Походження | Використання |
|---|---|---|---|
| `cover` | string (filename) | DLE post field | URL обкладинки (filename без шляху) |
| `namebook` | string | DLE | Назва книги |
| `author` | string | DLE | Автор книги |
| `tr_id` | int | DLE (tr=track?) | Внутрішній ID для CDN-шляхів `s20/{imgurl(tr_id)}` |
| `tr_cnt_p` | int | DLE | Кількість сторінок/глав (для full-text) |
| `tr_cover` | int (0/1) | DLE | Прапор наявності обкладинки |
| `baza_knig_info_id` | int | bazaknig.net only | ID для `s01/{imgurl(...)}` |
| `wallpaper` | string (path) | books-online/slushat | Path до cover на cdn.my-library.info |
| `book_id` | int | knigi-audio/audiokniga | ID для `s01/{imgurl(book_id)}` |
| `time` | string `H:M:S` | DLE | Тривалість аудіо книги |
| `youtube` | int | **СТЕЙТ-МАШИНА Yii** | 0/відсутнє=новий, 1=завантажено, 2=skip (no-cover), 4=skip (>2год) |
| `youtube_track_start` | int (sec) | **Yii-introduced** | Offset в секундах для ffmpeg trim |

---

## 15. Python скрипти

### 15.1 `console/controllers/shorts_from_video/shorts_from_video.py` (514 рядків)

**Виклик:** `OPENAI_API_KEY=... python3 shorts_from_video.py {links_file} {id_yt_acc} {lang}`

#### Step 1: Args і paths
```python
links_file, id_yt_acc, lang = sys.argv[1], sys.argv[2], sys.argv[3]
base_dir = "/var/www/.../data/shorts_from_video"
transcript_json = f"{base_dir}/transcript_{id_yt_acc}.json"
meta_json = f"{base_dir}/shorts_meta_{id_yt_acc}.json"
audio_path = f"{base_dir}/audio_{id_yt_acc}.wav"
video_path = f"{base_dir}/input_{id_yt_acc}.mp4"
output_folder = f"{base_dir}/shorts_{id_yt_acc}"
model_gpt = "gpt-4o-mini"
MAX_SIZE = 25 * 1024 * 1024   # 25 MB Whisper-1 limit
```

#### Step 2: yt-dlp download

```python
youtube_url = lines[0]   # перший URL з queue file (НЕ pop'ається!)

yt_cmd = [
    "yt-dlp",
    "--cookies", "/var/www/.../yii/cookies.txt",
    "--extractor-args", "youtube:player_client=android,web",   # ⭐ bypass SABR/403
    "--no-playlist",
    "--retries", "10",
    "--fragment-retries", "10",
    "--retry-sleep", "3",
    "-f", "bv*[height>=1080]+ba/b",   # best video >=1080 + best audio, fallback best combined
    "--merge-output-format", "mp4",
    "-o", video_path,
    youtube_url
]

p = subprocess.run(yt_cmd, ...)
if p.returncode != 0 or not os.path.exists(video_path) or os.path.getsize(video_path) < 1024*1024:
    sys.exit(2)   # < 1MB → fail
```

#### Step 3: Audio extraction (mono 16kHz)

```python
ffmpeg -y -i {video_path} -vn -ac 1 -ar 16000 -acodec pcm_s16le {audio_path}
```

#### Step 4: Whisper-1 transcription

```python
if os.path.getsize(audio_path) > MAX_SIZE:
    # Split in 600s segments
    ffmpeg -i {audio_path} -f segment -segment_time 600 -c copy part_%02d.wav
    audio_files = sorted(glob.glob("part_*.wav"))
else:
    audio_files = [audio_path]

full_segments, all_text = [], []
for part in audio_files:
    resp = openai.audio.transcriptions.create(
        model="whisper-1",
        file=open(part, "rb"),
        response_format="verbose_json"   # повертає segments[] з start/end/text
    )
    segments = resp.segments  # list of TranscriptionSegment objects
    full_segments.extend(segments)
    all_text.extend([s.text for s in segments])

# Save як JSON
with open(transcript_json, "w") as f:
    json.dump([s.__dict__ if hasattr(s, "__dict__") else s for s in full_segments], f, ensure_ascii=False, indent=2)

full_text = "\n".join(all_text)
```

#### Step 5: GPT-4o-mini обирає 5 моментів

```python
prompt = f"""
Ось транскрипція відео. Знайди 5 найцікавіших фрагментів тривалістю 10–30 секунд,
які містять кульмінацію, емоції, сміх або важливу інформацію.
Поверни у форматі JSON масив. Мова {lang}:
[{{"start": "00:01:25", "end": "00:01:45", "summary": "опис сцени"}}, ...]
Текст:
{full_text[:18000]}
"""

gpt_response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
reply = gpt_response.choices[0].message.content.strip()

try:
    highlights = json.loads(reply)
except:
    json_text = re.search(r"\[.*\]", reply, re.S)
    highlights = json.loads(json_text.group(0)) if json_text else []
```

#### Step 6: Per-highlight title+comment

```python
for i, h in enumerate(highlights, start=1):
    prompt_meta = f"""
    На основі короткого опису сцени:
    "{h['summary']}"

    створи 2 тексти. Мова {lang}:
    1. Назву для YouTube Shorts (макс. 60 символів, яскраву, емоційну, без лапок)
    2. Короткий коментар (1–2 речення, щоб зацікавити глядача).
    Формат відповіді:
    {{
      "title": "...",
      "comment": "..."
    }}
    """
    gpt_meta = openai.chat.completions.create(model="gpt-4o-mini", messages=[...])
    meta = json.loads(gpt_meta.choices[0].message.content.strip())
    h["title"] = meta["title"]; h["comment"] = meta["comment"]

# Save meta
with open(meta_json, "w") as f:
    json.dump(highlights, f, ensure_ascii=False, indent=2)
```

#### Step 7: ffmpeg cut 3 variants

Helpers:
```python
def parse_ts(ts):  # "00:01:25" → 85.0 sec, also accepts numeric
def sanitize_filename(text, maxlen=40):  # snake_case + remove non-word chars
def ffprobe_duration(path):  # ffprobe show_entries format=duration
```

Параметри:
- `min_len = 9.5`, `max_len = 22.0` (clamp)

```python
video_len = ffprobe_duration(video_path) or 1e9

for i, h in enumerate(highlights, 1):
    start_sec = parse_ts(h.get('start'))
    end_sec = parse_ts(h.get('end'))
    duration = end_sec - start_sec
    if duration < min_len: end_sec = start_sec + min_len
    if duration > max_len: end_sec = start_sec + max_len
    if start_sec >= video_len: skip

    base_name = f"short_{i:02d}"

    # === VERT 1080×1920 letterbox ===
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_sec:.3f}", "-i", video_path,
        "-t", f"{duration:.3f}",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k",
        f"{output_folder}/{base_name}_VERT.mp4"
    ]
    subprocess.run(cmd, ...)

    # === ORIG (без масштабування — copy спершу, fallback на encode) ===
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-ss", f"{start_sec:.3f}", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k",
        f"{output_folder}/{base_name}_ORIG.mp4"
    ]
    subprocess.run(cmd, ...)
    # fallback: -ss before -i якщо перша спроба fail
    
    # === VERT_BG — blurred background ===
    cmd_vert_bg = [
        "ffmpeg", "-y",
        "-ss", f"{start_sec:.3f}", "-i", video_path,
        "-t", f"{duration:.3f}",
        "-filter_complex",
        "[0:v]scale=4000:-1,boxblur=30:30[blur]; "      # huge upscale + blur
        "[blur]crop=1080:1920:(iw-1080)/2:(ih-1920)/2[bg]; "
        "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg]; "
        "[bg][fg]overlay=(W-w)/2:(H-h)/2",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        f"{output_folder}/{base_name}_VERT_BG.mp4"
    ]
    subprocess.run(cmd_vert_bg, ...)
```

#### Step 8: GPT-4o-mini Vision thumbnail selection

```python
thumb_dir = f"{base_dir}/thumbnails_{id_yt_acc}"
orig_video = f"{output_folder}/{base_name}_ORIG.mp4"

# Extract frames each 4 seconds
frames_tmp = f"{thumb_dir}/frames_{i:02d}"
subprocess.run([
    "ffmpeg", "-i", orig_video,
    "-vf", "fps=1/4",
    f"{frames_tmp}/frame_%04d.jpg"
])

frames = sorted(glob.glob(f"{frames_tmp}/frame_*.jpg"))

best_frame = None; best_score = -1
for frame_path in frames:
    with open(frame_path, "rb") as img:
        b64 = base64.b64encode(img.read()).decode()

    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text":
                    "Оціни цей кадр як можливу горизонтальну обкладинку для YouTube. "
                    "Дай оцінку від 1 до 10. Відповідь строго JSON: {\"score\": число}"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            ]
        }]
    )
    score = float(json.loads(resp.choices[0].message.content).get("score", 0))
    if score > best_score:
        best_score = score; best_frame = frame_path

    # Save як short_XX_H.png
    thumb_output = f"{thumb_dir}/short_{i:02d}_H.png"
    shutil.copy(best_frame, thumb_output)
```

PHP після цього: `cropTo1080x1920(_H.png)` + `addTextToImage(channel_link)` + INSERT в Tasks.

### 15.2 `python_scripts/tts_openai/tts_openai.py` (105 рядків)

OpenAI TTS wrapper. Async streaming:

```python
LANGUAGE_INSTRUCTIONS = {
    'ru': "говори четко, на русском языке, без акцента",
    'uk': "говори чітко, українською мовою, без акцента",
    'en': "speak clearly in English with native pronunciation",
    'de': "sprich deutlich auf Deutsch mit korrekter Aussprache",
    'fr': "parle clairement en français avec une bonne prononciation",
    'es': "habla claramente en español con buena pronunciación",
}

AVAILABLE_VOICES = {
    'male': ['onyx', 'echo', 'fable'],
    'female': ['nova', 'shimmer', 'alloy'],
    'neutral': ['shimmer', 'alloy'],
}

STYLE_PRESETS = {
    'fairytale': "розповідай як чарівну казку, з легким натхненням і теплою інтонацією",
    'serious': "серйозним, впевненим голосом, як диктор телебачення",
    'emotional': "емоційно, з глибокими почуттями та виразною інтонацією",
    'joyful': "радісно, із посмішкою в голосі, ніби вітаєш з днем народження",
    'calm': "спокійно, м'яко, як у медитації чи перед сном",
    'mysterious': "таємничо, трохи повільно, з ефектом інтриги, як у детективі",
    'dramatic': "з високим напруженням, як актор у театрі під час кульмінації",
    'storytelling': "живо і виразно, як захоплений оповідач історії біля багаття",
    'sad': "сумно, з нотками жалю та співчуття",
    'romantic': "ніжно, з інтимною інтонацією, як в любовному листі",
    'strict': "строго і формально, як викладач або чиновник",
    'robotic': "механічно, беземоційно, як штучний інтелект",
    'motivational': "натхненно, підбадьорливо, як тренер або коуч",
    'news': "інформативно, нейтрально, як ведучий новин",
    'whisper': "пошепки, дуже тихо, наче секрет",
}

async def synthesize_speech(input_file, output_file, language, gender, instructions, voice, style):
    text = open(input_file).read().strip()

    selected_voice = voice or random.choice(AVAILABLE_VOICES.get(gender, AVAILABLE_VOICES['female']))

    # Priority: instructions > style > ''; lang_hint always prepended якщо instructions empty
    base_instruction = instructions or STYLE_PRESETS.get(style, '')
    if not instructions and language in LANGUAGE_INSTRUCTIONS:
        lang_hint = LANGUAGE_INSTRUCTIONS[language]
        final_instructions = f"{lang_hint}. {base_instruction}" if base_instruction else lang_hint
    else:
        final_instructions = base_instruction

    async with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice=selected_voice,
        input=text,
        instructions=final_instructions,
        response_format='mp3'
    ) as response:
        async for chunk in response.iter_bytes():
            out.write(chunk)
```

CLI:
```bash
python3 tts_openai.py \
  --input_file=text.txt --output_file=audio.mp3 \
  --language=uk --gender=female \
  [--instructions="..."] \
  --voice=nova --style=fairytale
```

### 15.3 `update_youtube_cookies.py` (282 рядки)

Refresh `cookies.txt` через 3 fallback методи:

#### Method 1: `browser_cookie3` (швидкий)
```python
import browser_cookie3
for browser_name, browser_func in [('Chrome', chrome), ('Firefox', firefox), ('Safari', safari), ('Edge', edge), ('Opera', opera)]:
    cj = browser_func(domain_name='youtube.com')
    cookies_list = [{'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path,
                     'secure': c.secure, 'expiry': c.expires} for c in cj]
    if cookies_list: break
```

Читає cookies прямо з SQLite БД встановлених браузерів. Найшвидший метод.

#### Method 2: Playwright (chromium headless)
```python
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    page = context.new_page()
    page.goto("https://www.youtube.com", wait_until="networkidle")
    time.sleep(3)
    cookies = context.cookies()
    youtube_cookies = [c for c in cookies if 'youtube.com' in c.get('domain', '')]
```

#### Method 3: Selenium (Chrome → Firefox fallback, headless)
Same idea — open YouTube, get cookies через `driver.get_cookies()`.

#### Save в Netscape format
```
# Netscape HTTP Cookie File
# This file was generated by update_youtube_cookies.py
# Generated: 2026-05-10T...

domain  TRUE/FALSE  path  TRUE/FALSE(secure)  expiry  name  value
```

Path: `/var/www/fastuser/data/www/aiyoutube.pbnbots.com/yii/cookies.txt`.

### 15.4 `console/controllers/shorts_from_video/yt-dlp/shorts_from_video.py`

Дублікат основного файлу (можлива legacy версія, не використовується активно).

### 15.5 `data/news/make_srt.py` (НЕ в нашій вибірці — у `data/`)

Згідно з контексту виклику в `NewsController`:
```python
python3 make_srt.py audio.mp3 text.txt sub.srt
```

Призначення: forced alignment між audio.mp3 і text.txt (Whisper-аналог). Виводить `.srt` з timing.

---

## 16. Shell скрипти

### 16.1 `shel_youtube.sh` (19 рядків) — головний combined cron

```bash
#!/bin/bash
clear
cd /var/www/fastuser/data/www/aiyoutube.pbnbots.com/yii
php yii youtube_stats/stat                     # daily snapshot всіх stat=1 каналів
php yii unique_audio/upload_to_youtube 3 6     # 3 пости попаданцы → канал id=6
php yii unique_audio/shorts 6                  # quotes_popadanci → канал id=6
php yii audiokniga_one_com/shorts 5            # quotes → audiokniga-one канал id=5
php yii audiokniga_one_com/upload_to_youtube 1 5
# php yii sora/get_video 19                    # ⚠️ закоментовано
# php yii sora/get_video 20
php yii club_books_ru/upload_to_youtube 1 21
php yii books_online_info/upload_to_youtube 1 23
php yii bazaknig_net/upload_to_youtube 2 26    # 2 пости → bazaknig канал id=26
php yii bazaknig_net/upload_to_youtube 3 27    # 3 пости → канал id=27
php yii bazaknig_net/upload_to_youtube 3 29
php yii bazaknig_net/upload_to_youtube 3 30
php yii bazaknig_net/upload_to_youtube 3 32
php yii bazaknig_net/upload_to_youtube 3 47
php yii bazaknig_net/upload_to_youtube 3 48
php yii news/upload_to_youtube 1 55
```

**Виконується щоранку (cron) — total ~50-60 хв** (TTS, ffmpeg, GPT-4-turbo).

### 16.2 `shel_youtube_news.sh` (3 рядки)
```bash
cd /var/www/.../yii
php yii news/shorts 55
```

### 16.3 `shel_youtube_shorts_from_video.sh` (3 рядки)
```bash
cd /var/www/.../yii
php yii shorts_from_video/shorts_from_donors 28   # квадроцикли → @xobiATVUA
```

### 16.4 `shel_youtube_time.sh` (12 рядків)
```bash
cd /var/www/.../yii
php yii club_books_ru/shorts 21
php yii books_online_info/shorts 23
php yii bazaknig_net/shorts 26
php yii bazaknig_net/shorts 27
php yii bazaknig_net/shorts 29
php yii bazaknig_net/shorts 30
php yii bazaknig_net/shorts 32
php yii bazaknig_net/shorts 33
php yii bazaknig_net/shorts 47
php yii bazaknig_net/shorts 48
```

### 16.5 `shel_youtube_time_2.sh` (3 рядки)
```bash
cd /var/www/.../yii
php yii slushat_knigi_com/shorts 25
```

### 16.6 `mass_create_streams.sh` (314 рядків) — bash StreamProvisionerService

Найбільший shell-скрипт. Робить те, що `yt/mass-sync-services` тільки на bash:

1. **Bootstraps Yii з PHP**:
   - Створює tmpfile `streams_dump_*.php`
   - PHP завантажує `vendor/autoload.php` + `yii\Yii.php`
   - `new yii\console\Application(require 'console/config/main.php')`
   - `Stream::find()->orderBy(['id'=>SORT_ASC])->all()`
   - Виводить TSV: `id\tname\tservice_name\tworkdir\tstream_key\tduration_sec\trtmp_base\tenabled`
2. **Парсить TSV в bash через `while IFS=$'\t' read -r ID NAME ...`**
3. Для кожного stream (paragraph nullglob):
   - mkdir `${WORKDIR}/videos`
   - Write `${WORKDIR}/env.conf` (HEREDOC)
   - Write `${WORKDIR}/yt_stream_runner.sh` (через `runner_template`)
   - Write `${SYSTEMD_DIR}/${SERVICE_UNIT}` (через `service_template`)
4. systemd reload + reset-failed
5. Якщо `--restart` — restart usable services (`enabled=1`)

`runner_template`, `wrapper_template`, `service_template` — bash heredoc'и.

Особливості:
- `RestartPreventExitStatus=2 3` — НЕ авто-restart на config errors (env empty / playlist empty)
- `RuntimeMaxSec=42900` (12h)
- `KillSignal=SIGINT` для graceful ffmpeg shutdown

---

## 17. Каталог donor channels

### 17.1 YouTube donor channels (для Shorts_from_video / Stream_youtube)

**Конфіг `arr_data` повністю** (`Shorts_from_videoController` + `Stream_youtubeController`):

```php
$arr_data = [
    28 => [
        'donors' => [
            ['channel_id' => 'UCGz5TPWPY4TdnK1Bug04thg', 'channel_name' => '@xobiATVUA'],
        ],
        'lang' => 'українська',
        'channel_id' => '@xobiATVUA',
        'channel_name' => 'Хобі ATV  UA',
        'keywords' => 'квадроцикл, квадроциклы, atv, утв, квадрик, offroad, оффроуд, бездоріжжя, грязьові покатушки, mud riding, mudding, cross country, atv adventure, екстрим, екстремальні покатушки, квадро тури, atv tours, квадротур, квадропробіг, полювання на квадроциклі, рибалка на квадроциклі, polaris, can-am, yamaha grizzly, honda atv, sport atv, utility atv, квадроциклы 4x4, 4x4 offroad, повний привід, мотовсюдихід, квадро тюнінг, atv tuning, лебідка atv, шини atv, грязьові шини, mud tires, atv accessories, захист квадроцикла, квадроекіп, мотошолом, мотозахист, позашляхові пригоди, offroad action, atv racing, гонки atv, квадр після off-road, перегрів квадроцикла, ремонт квадроцикла, обслуговування atv, квадро клуб, квадро ком'юніті, atv vlog, покатушки 2025, atv extreme, лісові покатушки, гори на квадроциклі, водні перешкоди atv, глибока грязь atv',
    ],
    31 => [
        'donors' => [
            ['channel_id' => 'UCJplp5SjeGSdVdwsfb9Q7lQ', 'channel_name' => '@LikeNastya_Vlog'],
            ['channel_id' => 'UCx790OVgpTC1UVBQIqu3gnQ', 'channel_name' => '@KidsDianaShow'],
            ['channel_id' => 'UCk8GzjMOrta8yxDcKfylJYw', 'channel_name' => '@KidsRomaShow'],
            ['channel_id' => 'UCP9MW9ATjUwwulqEYTbp-Mw', 'channel_name' => '@VladandNiki'],
            ['channel_id' => 'UC_8PAD0Qmi6_gpe77S1Atgg', 'channel_name' => '@MrMaxLife'],
            ['channel_id' => 'UCcartHVtvAUzfajflyeT_Gg', 'channel_name' => '@misskaty1133'],
        ],
        'lang' => 'російська',
        'channel_id' => '@babysmilevlog',
        'channel_name' => 'Baby Smile Vlog',
        'keywords' => 'дети, детский канал, детские видео, малыш, малыши, детское развлечение, игры для детей, детский юмор, детские игры, детское шоу, семья, семейный канал, детские песни, детские сказки, обучающие видео, развивающие видео, развивающие игры, учим цвета, учим цифры, детские истории, мультики, детская анимация, детские игрушки, обзор игрушек, играем вместе, дошкольники, раннее развитие, детские приключения, детский смех, детский контент, детские занятия, веселые дети, смешные дети, детские танцы, песни для детей, сказки на ночь, творческие игры, детские поделки, развлечение для детей, детское обучение',
    ],
    34 => [
        'donors' => [
            ['channel_id' => 'UCkyrSWEcjZKpIwMxiPfOcgg', 'channel_name' => '@5channel'],
            ['channel_id' => 'UCKCVeAihEfJr-pGH7B73Wyg', 'channel_name' => '@unian'],
            ['channel_id' => 'UCjAg2-3PgoksLAkYE88S_6g', 'channel_name' => '@UKRAINETODAY24'],
            ['channel_id' => 'UChparf_xrUZ_CJGQY5g4aEg', 'channel_name' => '@УкраїнськаПравда'],
        ],
        'lang' => 'українська',
        'channel_id' => '@Новини_1',
        'channel_name' => 'Новини',
        'keywords' => 'новини україни, новини сьогодні, останні новини, українські новини, головні новини, хроніка подій, війна в україні, політика україни, економіка україни, новини онлайн, термінові новини, оперативні новини, новини україна зараз, ситуація в україні, новини києва, новини львова, новини одеси, новини харкова, актуальні новини, день новин, гарячі новини, щоденні новини, короткі новини, стрічка новин, топ новини дня, новини тижня, розслідування, аналітика, фактчек, новини суспільства, новини світу, новини європи, новини сша, міжнародні новини, міжнародна політика, новини нато, новини фронту, міжнародні події, міжнародний огляд, короткі новини україна, новина за 60 секунд, терміново україна, головне за день',
    ],
];
```

⚠️ Тільки `Shorts_from_videoController` має `34`, а `Stream_youtubeController` — лише `28+31`.

**Метод вибірки:**
- `https://www.googleapis.com/youtube/v3/search?key={K}&channelId={cid}&part=snippet,id&order=date&maxResults=50`
- Для кожного `videoId` — `videos?id&part=snippet,contentDetails`
- Парс ISO8601 `duration` → секунди через `\DateInterval`
- **Filter `seconds >= 600`** (тільки відео ≥10 хв)
- Dedup by `videoId`, sort by `publishedAt` desc

### 17.2 DLE donor sites (книжкові)

| Site | DB host | Account ID(s) | Cover URL | Spec |
|---|---|---|---|---|
| audiokniga-one.com | 185.154.15.251:3310 | **5** (також 1) | `vvoqhuz9dcid9zx9.redirectto.cc/s01/{imgurl(book_id)}{book_id}.pl.txt` | Audio через `.pl.txt` JSON, GPT-4-turbo title regen, cli.voice unique-fy, 1280×720 mp4 |
| knigi-audio.biz | 77.220.213.172:3306 | **6** | те ж саме (через `Unique_audioController`) | Жанр '12' (попаданцы), `quotes_popadanci.txt`, `xfields[youtube]=2` після завантаження |
| club-books.ru | 185.244.217.9:3311 | **21** (5) | `redirectto.cc/s20/{imgurl(tr_id)}{tr_id}.jpg` | Standard TTS slideshow 1920×1080 |
| books-online.info | 91.211.251.57:3306 | **23** (5) | `cdn.my-library.info/{wallpaper}` | Standard, БЕЗ `book_id`. Має додатковий `actionUpload_to_youtube_txt_file` (закоментований). |
| slushat-knigi.com | 80.85.141.91:3310 | **25** (5) | `cdn.my-library.info/{wallpaper}` | upload **DISABLED** (exit;), тільки shorts |
| knigi-online.club | 185.224.133.132:3310 | **12** | `redirectto.cc/s20/{imgurl(tr_id)}{tr_id}.jpg` | **Full-text book** через `run_voice_changer.py kseniya speed 0.8`, заливає всі глави в єдиний WAV |
| bazaknig.net | 185.224.133.132:3310 | **26-32, 47, 48** | `redirectto.cc/s01/{imgurl(baza_knig_info_id)}{xfields[cover]}` | Найбільше акаунтів — масштабовано на 9 каналів |

**Метрика віральності:** `dle_post_extras.news_read DESC` — найчитаніші пости на оригінальному DLE-сайті.

### 17.3 Account ID → cron mapping (з shel_youtube.sh)

| Account ID | Канал | Pipeline | Cron |
|---|---|---|---|
| 5 | audiokniga-one | DLE upload+shorts | shel_youtube.sh: `audiokniga_one_com/{shorts,upload}` |
| 6 | knigi-audio.biz | DLE upload+shorts (через unique_audio) | `unique_audio/{upload,shorts}` |
| 12 | knigi-online.club | DLE full-text | (вручну, не у видимих cron) |
| 21 | club-books.ru | DLE upload+shorts | `club_books_ru/{upload,shorts}` |
| 23 | books-online.info | DLE upload+shorts | `books_online_info/{upload,shorts}` |
| 25 | slushat-knigi.com | DLE shorts only | `slushat_knigi_com/shorts` |
| 26-32, 47, 48 | bazaknig.net (9 каналів) | DLE upload+shorts | масовий `bazaknig_net/{upload,shorts}` |
| 28 | @xobiATVUA (квадроцикли) | YT shorts donor | `shorts_from_video/shorts_from_donors 28` |
| 31 | @babysmilevlog (дитячий) | YT shorts donor (6 донорів) | (вручну?) |
| 34 | @Новини_1 | YT shorts donor (4 донори) | (вручну?) |
| 19, 20 | Sora канали | Sora virality | `sora/get_video` (закоментовано в cron) |
| 55 | Новини UA (RBC) | News pipeline | `news/{shorts,upload}` |

---

## 18. Каталог datasources

### 18.1 Локальна БД `content_fabric`
- 10 таблиць: `user, tasks, stream, youtube_account, youtube_channels, youtube_channel_daily, google_consoles, dle_post_extras_cats?, content_upload_queue_tasks (CFF), live_stream_configurations (CFF), platform_oauth_credentials (CFF), platform_channels (CFF)`

### 18.2 7 DLE MySQL DBs (зовнішні)
Див. §17.2 — `audiokniga_one_com_db`, `knigi_audio_biz_db`, `club_books_ru_db`, `booksonlineinfo`, `slushat_knigi_com_db`, `knigi_online_club_db`, `bazaknig_net_db`. Усі на MariaDB 5.5.68.

### 18.3 Origin CDN (бай-пас Cloudflare)

| URL | Призначення | Referer |
|---|---|---|
| `vvoqhuz9dcid9zx9.redirectto.cc/s01/...` | audiokniga, knigi-audio, bazaknig (`s01` schema, по book_id) | `https://vvoqhuz9dcid9zx9.redirectto.cc` або `https://cdn.bazaknig.net` |
| `vvoqhuz9dcid9zx9.redirectto.cc/s20/...` | club-books, knigi-online (`s20` schema, по tr_id) | `https://vvoqhuz9dcid9zx9.redirectto.cc` |
| `cdn.my-library.info/{wallpaper}` | books-online, slushat (mirror, dead для нових) | `https://cdn.my-library.info` |
| `Xp4sTM90BVzr.frontroute.org/s11/...` | альтернативний legacy CDN (тільки в MyFunction.showPdfs* — unused) | — |
| `slushat-knigi.com/uploads/posts/...` | slushat не за Cloudflare, прямі URL'и | (CFF використовує) |

### 18.4 Public APIs

| API | Endpoint | Auth | Use |
|---|---|---|---|
| **YouTube Data API v3** | `googleapis.com/youtube/v3/{search,videos,channels,liveBroadcasts,liveStreams}` | API Key (3 keys) + OAuth | shorts donor, stats, broadcasts |
| **YouTube Live API** | `googleapis.com/upload/youtube/v3/thumbnails/set` | OAuth | thumbnails |
| **OpenAI Whisper-1** | `api.openai.com/v1/audio/transcriptions` | API Key | shorts transcription |
| **OpenAI GPT-4o-mini** | `api.openai.com/v1/chat/completions` | API Key | highlights, captions, JSON meta |
| **OpenAI GPT-4o-mini Vision** | те ж | API Key | thumbnail scoring, frame description (Sora) |
| **OpenAI GPT-4-turbo** | те ж | API Key | book title regeneration (Audiokniga, Unique_audio) |
| **OpenAI GPT-4o-mini-tts** | `api.openai.com/v1/audio/speech` | API Key | TTS озвучка |
| **DeepL** | `api.deepl.com/v2/translate` | auth_key | (MyFunction.translate_deepl — не використовується активно) |
| **SerpAPI Google Images** | `api.serpapi.com/search.json?engine=google_images` | API Key | News images search |
| **Google Custom Search** | `googleapis.com/customsearch/v1?searchType=image` | API Key + CX | News images fallback |
| **Zenrows** | `api.zenrows.com/v1/?apikey=...&js_render=true[&premium_proxy=true]` | API Key | Sora feed scraping (anti-bot bypass) |
| **Telegram Bot API** | `api.telegram.org/bot{token}/sendPhoto` | bot token | (MyFunction.sendPhoto — не використовується) |
| **Telegra.ph** | `https://telegra.ph/upload` | none | (MyFunction.uploadMediaTelegram — unused) |

### 18.5 RSS / scraping

| Source | URL | Method | Filter |
|---|---|---|---|
| RBC.ua | `rbc.ua/static/rss/all.ukr.rss.xml` | `simplexml_load_string` | `!in_array($link, $usedLinks)` (rbc_used_links.txt) |
| Sora | `sora.chatgpt.com/backend/public/nf2/feed` | через Zenrows premium_proxy | `unique_view_count > 1000 && !in used_posts.txt` |

---

## 19. Метрики віральності

Yii не має алгоритмічного "score" — це 5 окремих евристик:

### 19.1 DLE: `news_read DESC` (популярність на джерелі)
Усі книжкові DLE-controller'и сортують `dle_post_extras.news_read DESC LIMIT $limit`. Це кількість читань поста на оригінальному DLE-сайті — найбільш надійний proxy для популярності у цільової аудиторії.

Filters також забезпечують якість:
- `short_story != ''` — є опис
- `CHAR_LENGTH(short_story) > 1000` — не плейсхолдер
- `xfields not like '|youtube'` — ще не оброблено
- `category like '15'` — книжкова (для деяких)
- `xfields like 'tr_id'` — є cover URL

### 19.2 YouTube donor: `duration >= 600s` + `order=date`
Лише довгі відео (≥10 хв) щоб мати з чого нарізати 5 shorts. Сортування за датою — пріоритет на свіжість, не накопичену популярність. Шумовий фільтр через dedup history `youtube_links_done_<id>.txt`.

### 19.3 Sora: `unique_view_count > 1000`
Threshold консервативний — пост вже привернув увагу на Sora feed. Дедуп `used_posts.txt`, max 3 на день.

### 19.4 GPT-4o-mini semantic highlight detection
**Найскладніший layer** — тільки для shorts_from_video pipeline:
```
"Знайди 5 найцікавіших фрагментів тривалістю 10–30 секунд,
 які містять кульмінацію, емоції, сміх або важливу інформацію."
```
Семантично шукає peak moments в transcript.

### 19.5 GPT-4o-mini Vision thumbnail scoring
Для кожного кадру (1 кадр кожні 4 сек) → score 1-10. Найвищий → final thumbnail.

### 19.6 News: just freshness
Перший непрочитаний RSS item — без сортування за popularity. Швидкість, не якість.

---

## 20. Live streaming infrastructure

### 20.1 9 systemd units

Кожен `stream-{name}.service` живе в `/etc/systemd/system/`:

```ini
# {name}
[Unit]
Description=YouTube Stream: {name}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={workDir}
EnvironmentFile={envPath}
ExecStart=/usr/bin/env bash {runner_path}

Restart=on-failure
RestartSec=3-5
RestartPreventExitStatus=2 3   # ⭐ НЕ auto-restart на config errors

KillSignal=SIGINT
KillMode=control-group
TimeoutStopSec=60
SuccessExitStatus=0 130 255
RuntimeMaxSec=42900   # ⭐ 11h55min = YouTube Live limit

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

EnvironmentFile (`/etc/aiyoutube/streams/{name}.env`):
```
STREAM_NAME=knigiaudiobiz
STREAM_KEY=xxxx-xxxx-xxxx-xxxx
INPUT_DIR=/var/www/.../data/streams/knigiaudiobiz/videos
RTMP_HOST=a.rtmp.youtube.com
RUNTIME_MAX=42900
```
chmod 0600.

### 20.2 Runner — `/usr/local/bin/yt_stream_runner.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

PLAYLIST="$INPUT_DIR/playlist.txt"
RTMP_URL="rtmp://${RTMP_HOST}/live2/${STREAM_KEY}"

# Rebuild playlist
shopt -s nullglob
: > "$PLAYLIST"
for f in $(ls -1 *.mp4 | sort); do
  echo "file '${PWD}/${f}'" >> "$PLAYLIST"
done

[[ -s "$PLAYLIST" ]] || exit 3

exec ffmpeg -nostdin -re \
  -f concat -safe 0 -stream_loop -1 -i "$PLAYLIST" \
  -fflags +genpts -avoid_negative_ts make_zero \
  -c:v copy -c:a copy -t "$RUNTIME_MAX" \
  -f flv "$RTMP_URL"
```

**Параметри ffmpeg:**
- `-nostdin`: не чекати на stdin
- `-re`: realtime read (RTMP)
- `-f concat -safe 0 -stream_loop -1`: нескінченний concat
- `-c:v copy -c:a copy`: zero CPU
- `-fflags +genpts -avoid_negative_ts make_zero`: фікси PTS дрейфу
- `-t 42900`: жорсткий таймаут (~12 годин)
- `-f flv`: RTMP формат

### 20.3 Live broadcast lifecycle (PHP-керування)

**При `actionStart`:**
1. `prepareBroadcastForStart`:
   - якщо `stream.youtube_broadcast_id` живий — re-use
   - інакше `liveBroadcasts.insert(scheduledStartTime=now+10s, autoStart=true, autoStop=true)`
   - `liveStreams.list?mine=true` paginate → знайти за `streamName == stream_key`
   - `liveBroadcasts/bind` → з'єднати broadcast + stream
   - updateBroadcastMeta + updateVideoMeta + setThumbnail
2. `systemctl start` → ffmpeg починає лити в RTMP
3. (CFF — не Yii) — `transition to 'live'` через 8-15 секунд

**При `actionStop`:**
1. (try) `transitionBroadcast(bid, 'complete')`
2. `systemctl stop`

### 20.4 Чому Yii setup ламається (чого CFF reconcile був потрібен)
- systemd `Restart=on-failure` рестартить ffmpeg якщо процес впав
- Але **broadcast lifecycle не оновлюється автоматично** (broadcast потрібно `transition` вручну після зміни стану)
- Якщо broadcast завершився (12 год ліміт), а ffmpeg все ще тиче — стрім "стирчить" в YouTube RTMP error
- CFF додав `reconcile_streams()` що детектить це і `prepareBroadcastForStart` + `start_stream` повторно

---

## 21. Інтеграція з Content Fabric

PHP вже частково перетинається з CFF Python-стеком:

### 21.1 cli.voice (Audiokniga / Unique_audio)
```bash
cd /opt/content-fabric/prod && python3 -m cli.voice {in.mp3} {out.mp3} --parallel --preserve-background
```
RVC voice unique-fy для bypass YouTube duplication detection. Викликається з PHP через `exec()`.

### 21.2 run_voice_changer.py (Knigi_online_club, Books_online_info)
```bash
cd /opt/content-fabric/ && source venv/bin/activate && \
python3 run_voice_changer.py {output.wav} \
    --text-file {input.txt} \
    --voice-model kseniya \
    --speed 0.8
```
TTS через RVC kseniya (свій особистий голос). Speed 0.8 — повільніше (для чіткішого розуміння). Books_online_info використовує speed 0.9.

### 21.3 Спільна БД `content_fabric`
- Yii пише в `tasks` (legacy назва)
- CFF читає з `content_upload_queue_tasks` (CFF-native)
- 004_yii_decommission.sql робить INSERT IGNORE з `tasks` → `content_upload_queue_tasks`
- Подвійний state — обидві таблиці існують одночасно

### 21.4 CFF поступово заміщає PHP контролери
- ✅ `prod/shared/ingestion/dle/{client.py, sources.py, xfields_parser.py, processor.py}` — 1:1 порт DLE
- ✅ `prod/shared/streams/lifecycle.py` — порт `prepareBroadcastForStart` + reconcile
- ✅ `prod/scheduler/jobs.py` — Yii cron emulator (60s tick)
- ✅ `prod/workers/stream_worker.py` — RQ handler
- ✅ `prod/app/api/endpoints/streams.py` — REST API
- ✅ `prod/app/templates/app_streams.html` — нова адмінка `/panel/streams` з Heal buttons
- ⏳ Shorts pipeline (`shorts_from_video.py` + `Shorts_from_videoController`) — НЕ портовано
- ⏳ Sora pipeline — НЕ портовано
- ⏳ News pipeline (RBC + SerpAPI + slideshow) — НЕ портовано
- ⏳ Image compositor `create_youtube_image` — НЕ портовано
- ⏳ Donor channels конфіг (28/31/34) — у PHP arr_data, треба в DB

---

## 22. Безпекові ризики

| # | Ризик | Рівень | Mitigation |
|---|---|---|---|
| 1 | **OpenAI/Google/Zenrows/SerpAPI/DeepL ключі hardcoded в коді** | КРИТИЧНИЙ | Revoke + rotate усі. Перенести в `.env`, не commit. |
| 2 | **DLE-credentials** в `console/config/main-local.php` (паролі MySQL) | ВИСОКИЙ | Move to `.env`. Hardening: створити `@'1.2.3.4'` host (whitelist server IP) + видалити `@'%'`. |
| 3 | **MariaDB 5.5.68** (без TLS, кінець підтримки 2020) | ВИСОКИЙ | Migrate to MariaDB 10.11. Додати TLS via `mysql_ssl_required`. |
| 4 | **`Xp4sTM90BVzr.frontroute.org`** і `vvoqhuz9dcid9zx9.redirectto.cc` — origin CDN з obfuscated subdomains | СЕРЕДНІЙ | Це bypass Cloudflare. При revoke з боку DLE — ламається весь pipeline. Backup plan: переключитись на CF з cookies/UA. |
| 5 | **cookies.txt** з повною YouTube user session | СЕРЕДНІЙ | Cron `update_youtube_cookies.py` (раз на день). При зливі — атакуючий може скачати donors як вас. |
| 6 | **Service Account JSON `audiokniga-one-com-46ac50021541.json`** з privateKey | СЕРЕДНІЙ | Перевірити чи активний service account, revoke якщо unused. |
| 7 | **OAuth `redirect_uri` = aiyoutube.pbnbots.com** hardcoded | СЕРЕДНІЙ | Реєструвати додатковий redirect_uri у Google Cloud Console для CFF. |
| 8 | `exec()` з `escapeshellarg` — на більшості шляхів є | НИЗЬКИЙ | Audit usage, особливо в `actionUpload_to_youtube` де `xfields[youtube_track_start]` йде в shell |
| 9 | `1lib.org` cookies в `MyFunction::downloadFile_post` (legacy) | НИЗЬКИЙ | Видалити невикористовуваний код, ці session id зливаються при commit. |
| 10 | `ChatGPT.php` з hardcoded `text-davinci-003` model — model вже виведена з обігу 2024-01-04 | ОПЕРАЦІЙНИЙ | Замінити wrapper на gpt-4o-mini. |

---

## 23. Контракти на портування в CFF

### 23.1 Done (already in CFF)
| Yii Source | CFF локація | Commit |
|---|---|---|
| DLE post fetcher (7 БД) + xfields parser + cover URLs + book_id auto-detect | `prod/shared/ingestion/dle/{client.py, sources.py, xfields_parser.py, processor.py}` | `c98642b` |
| Stream broadcast lifecycle | `prod/shared/streams/lifecycle.py` + `youtube/broadcasts.py` | `4823232` |
| systemd manager + reconcile | `prod/shared/streams/systemd_manager.py` + `scheduler/jobs.py:reconcile_streams()` | `4823232` |
| YouTube stats collector | `prod/shared/youtube/stats.py` + `cff-stats-worker` | (earlier) |
| Tasks queue → publishing worker | `prod/shared/db/repositories/task_repo.py` + `cff-publishing-worker` | (earlier) |
| OAuth flow (web) | `prod/shared/youtube/reauth/` (Playwright reauth) | (earlier) |

### 23.2 To-do
| Yii Source | CFF цільова локація | Складність |
|---|---|---|
| Stream provisioner (sync env+unit) | `prod/shared/streams/provisioner.py` | Low |
| Shorts pipeline (yt-dlp + Whisper + GPT-4o-mini + 3 ffmpeg variants + Vision thumbnail) | `prod/shared/shorts/{downloader.py, transcriber.py, highlight.py, cutter.py, thumbnail.py}` + `cff-shorts-worker` | High |
| Sora virality scraper + GPT meme caption | `prod/shared/sora/scraper.py` + `cff-sora-worker` | Medium |
| News pipeline (RBC RSS + SerpAPI + slideshow + subtitles) | `prod/shared/news/{rss.py, images.py, video.py, srt.py}` + `cff-news-worker` | Medium |
| Voice TTS (15 styles, 6 langs) | `prod/shared/voice/tts_openai.py` (Async streaming) | Low |
| Donor channel configs (28/31/34) | DB `donor_channel_configs` table → seed migration | Low |
| Cookies refresh для yt-dlp | `prod/shared/shorts/cookies_refresh.py` | Low |
| Image compositor `create_youtube_image` | `prod/shared/video/compositor.py` (Pillow або MoviePy) | Medium |
| ASS subtitle generator (per-word, Lena.ttf) | `prod/shared/video/subtitles.py` | Low |
| GPT-4-turbo book title regeneration | `prod/shared/voice/title_gen.py` | Low |
| `mass_create_streams.sh` логіка → CFF dashboard "Provision ALL" | `prod/app/api/endpoints/streams.py:provision_all` | Low |
| `Stream::index` JS UI з 5s polling | `prod/app/templates/app_streams.html` (вже є базовий) — додати search/filter/bulk actions | Medium |
| `make_srt.py` (forced alignment) | `prod/shared/news/srt_aligner.py` (через Whisper word-level timestamps) | Medium |
| RBC RSS deduplication file → DB table | `prod/shared/news/used_links.py` (table `news_processed_urls`) | Low |
| Sora `used_posts.txt` → DB | table `sora_processed_posts` | Low |

### 23.3 Architecture notes для CFF портування
1. **Не переносити legacy `MyFunction.php` як-є.** Розбити по доменах: `cff/shared/http/curl_helpers.py` (HTTP), `cff/shared/dle/xfields.py` (DLE), `cff/shared/text/slugify.py` (text utils), `cff/shared/scheduling/dates.py` (`generatePlannedDates`).
2. **Не дублювати TTS бой-плейт у кожному контролері.** В CFF — один сервіс `voice/tts_openai.py` що приймає `(text, voice, style, lang)`.
3. **Не повторювати `create_youtube_image` 7 разів.** Один `compositor.py` з параметрами (color, top_text, body_text, cover_overlay).
4. **Donor configs у БД, не в коді.** Створити таблицю `donor_channel_configs` (`id_yt_acc, target_channel, target_handle, lang, keywords, donors_json`).
5. **Tasks queue → use existing CFF `content_upload_queue_tasks`** (не дублювати).

---

*Кінець документа.*

*Документ покриває ~13 000 рядків PHP/Python код з деталізацією рівня "знаю який саме curl-параметр використовується для кожного API виклику". Якщо щось не покрите — поглянь на `_yii_research/` поряд з цим репо (extracted source) або зайди на сервер `46.21.250.43:/var/www/fastuser/data/www/aiyoutube.pbnbots.com/`.*

*Дата збору: 2026-05-10. Аналізував: Hlib Sorvenkov.*

