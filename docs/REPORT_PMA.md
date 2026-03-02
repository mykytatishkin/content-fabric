# Content Fabric — Отчёт для менеджера проекта

> Период: октябрь 2025 — март 2026
> Последнее обновление: 02.03.2026 (Phase 14 — Legacy Port, Reauth Module, Cleanup)

---

## 1. Краткое резюме

Проект Content Fabric прошёл полную трансформацию: от монолитного Python-скрипта (1500+ строк) к микросервисной архитектуре из 6 независимых сервисов. Система задеплоена на продакшн-сервере и работает автономно (legacy код вычищен).

**Ключевые цифры:**
- 30 Pull Request'ов смерджено
- 22 user stories закрыты (из 33)
- 6 микросервисов в проде
- 15 таблиц БД (новая схема + 2FA + templates)
- 39 каналов управляются через API
- 0 даунтаймов при миграции
- **User Portal** — 16 SSR-страниц с cookie auth + role-based access
- **Admin Panel** — 6 SSR-страниц, защищён авторизацией
- **202 теста** — все зелёные (удвоение покрытия)
- **Полный CRUD** — каналы, задачи, шаблоны через веб-портал

---

## 2. Что было сделано

### Фаза 1: Рефакторинг базы данных (PRs #69-73)

| Что | Результат |
|-----|-----------|
| Новая схема БД | 13 таблиц вместо плоской структуры |
| Миграционные скрипты | 8 миграций (001-008), каждая идемпотентная и с rollback |
| RBAC | Пользователи, проекты, роли, приглашения |
| Multi-console OAuth | Несколько Google Cloud Console для обхода квот |
| Legacy совместимость | Весь legacy-код обновлён для работы с новой схемой |
| Локальная среда | Docker auto-setup для разработки без доступа к серверу |

### Фаза 2: Микросервисы (PRs #86-95)

| Сервис | Функция | Статус |
|--------|---------|--------|
| **API Gateway** | REST API (FastAPI) — каналы, задачи, авторизация | Работает в проде |
| **Scheduler** | Поллинг БД каждые 60 сек, постановка задач в очередь | Работает в проде |
| **Publishing Worker** | Загрузка видео на YouTube (resumable upload) | Работает в проде |
| **Notification Worker** | Telegram/Email уведомления | Работает в проде |
| **Voice Worker** | Смена голоса (обёртка над legacy) | Готов к запуску |
| **Redis** | Очередь сообщений между сервисами | Работает в проде |

### Фаза 3: Деплой и стабилизация (28.02.2026)

| Действие | Результат |
|----------|-----------|
| Деплой на 46.21.250.43 | Все сервисы запущены |
| JWT авторизация | Регистрация + логин + защищённые endpoints |
| Тестирование на проде | Health check, каналы, задачи, OAuth refresh — всё OK |
| Параллельный запуск | Legacy task_worker работает рядом с новым стеком |
| Аудит-логи | Все критические действия записываются в JSON |

### Фаза 4: Дополнительные фичи (28.02.2026)

| Фича | Endpoint | Описание |
|------|----------|----------|
| Отмена задач | `POST /tasks/{id}/cancel` | Отмена запланированных публикаций |
| Перепланирование | `PUT /tasks/{id}` | Смена даты/времени публикации |
| История задач | `GET /tasks/history` | Фильтрация по дате, каналу, статусу |
| Аудит | `/var/log/cff-audit.log` | Логины, регистрации, создание/отмена задач |

### Фаза 5: Расширение функциональности (28.02.2026)

| Фича | Endpoint | Описание |
|------|----------|----------|
| 2FA (TOTP) | `POST /auth/2fa/setup,verify,disable` | Двухфакторная аутентификация + backup codes |
| Шаблоны расписаний | `CRUD /templates/` | Шаблоны с time slots по дням недели |
| Пакетная загрузка | `POST /tasks/batch` | До 100 задач за один запрос |
| Прогресс загрузки | `GET /tasks/{id}/progress` | Redis-backed polling (stage + percentage) |
| Календарь | `GET /tasks/calendar` | Задачи сгруппированные по дням |
| Превью файлов | `GET /tasks/{id}/preview` | Инфо о файле + YouTube URL |
| Статистика | `GET /tasks/stats/summary` | Агрегация задач по статусам |
| Admin API | `GET /admin/dashboard,users,queue` | Обзор системы, управление юзерами |
| Channel Stats | `GET /channels/{id}/stats` | Ежедневная статистика каналов |
| Systemd | `prod/deploy/systemd/` | Unit files для всех 5 сервисов |
| Security | Rate limiting, headers, validation | Полный аудит и хардинг |

---

## 3. Закрытые user stories

| # | Story | Статус |
|---|-------|--------|
| US-001 | Регистрация пользователя | Done |
| US-002 | Авторизация (JWT) | Done |
| US-005 | Подключение YouTube-канала (OAuth) | Done |
| US-006 | Управление несколькими каналами | Done |
| US-007 | Статус каналов и токенов | Done |
| US-009 | Загрузка видео | Done |
| US-014 | Планирование публикации | Done |
| US-017 | Изменение и отмена публикации | Done |
| US-018 | Scheduler | Done |
| US-019 | Publishing Worker | Done |
| US-020 | Retry при ошибках | Done |
| US-021 | История публикаций | Done |
| US-026 | Аудит и логи | Done |
| #34 | Multiple GCC (мульти-консоль) | Done |
| #15 | Clean up project files | Done |
| US-003 | 2FA (TOTP) | Done |
| US-011 | Прогресс обработки | Done |
| US-012 | Предпросмотр видео | Done |
| US-013 | Пакетная загрузка | Done |
| US-015 | Шаблоны расписаний | Done |
| US-016 | Календарь публикаций | Done |
| US-025 | Admin Panel (API) | Done |

**Итого: 22 задачи закрыто из 33**

---

### Фаза 6: Финальная стабилизация (28.02.2026, вечер)

| Фича | Описание | Статус |
|------|----------|--------|
| **Test Suite** | 91 тест (security, repos, API, upload logic) — все проходят на проде | Done |
| **File Upload API** | `POST /uploads/video` + `POST /uploads/thumbnail` | Done, задеплоен |
| **SSR Admin Panel** | 6 SSR-страниц: dashboard, каналы, задачи, юзеры, credentials, оплата | Done, задеплоен |
| **Legacy убит** | task_worker + 4 зомби-процесса реавторизации — убиты на проде | Done |
| **Анализ каналов** | Детальный анализ всех 13 проблемных каналов с логами | Done |
| **GitHub Issues** | 9 issues создано (#96-104) с детальными описаниями и назначениями | Done |

### Фаза 7: User Portal (28.02.2026, ночь)

| Фича | Описание | Статус |
|------|----------|--------|
| **User Portal** | 10 SSR-страниц: login, register, dashboard, channels, add channel, tasks, create task, templates, settings, logout | Done, задеплоен |
| **Cookie Auth** | JWT в HttpOnly cookie, 24h expiry, поддержка 2FA при логине | Done |
| **Admin Protection** | Admin panel (`/panel/`) теперь требует логин + статус admin | Done |
| **Role Separation** | Admin видит всё, обычный user — только свои данные | Done |
| **Test Accounts** | admin@cff.local (Admin123!) + demo@cff.local (Demo123!) | Done |
| **Swagger Docs** | `/docs` теперь доступен на проде (ранее скрыт) | Done |
| **Bug fix** | `/tasks/history` — IntEnum не сериализовался в mysql-connector | Done |
| **SSL + Domain issues** | #105 (SSL), #106 (домен) — созданы и назначены на @mykytatishkin | Done |
| **Portal Guide** | `docs/PORTAL_GUIDE.md` — полная документация портала | Done |

### Фаза 8: Расширение портала (01.03.2026)

| Фича | Описание | Статус |
|------|----------|--------|
| **Channel Detail** | `/app/channels/{id}` — per-channel stats, credentials, recent tasks | Done, задеплоен |
| **Channel Edit** | `/app/channels/{id}/edit` — rename, toggle enabled, update RPA credentials | Done, задеплоен |
| **Delete Channel** | Кнопка удаления на списке каналов и на детальной странице | Done, задеплоен |
| **Task Detail** | `/app/tasks/{id}` — полная информация, reschedule, retry | Done, задеплоен |
| **Retry Tasks** | Кнопка retry для failed/cancelled задач (reset to pending) | Done, задеплоен |
| **Cancel Tasks** | Кнопка cancel для pending задач на списке и детальной странице | Done, задеплоен |
| **File Upload** | AJAX-загрузка видео и thumbnail прямо из формы создания задачи | Done, задеплоен |
| **Profile Edit** | Редактирование display name и timezone на /app/settings | Done, задеплоен |
| **2FA UI** | Полный flow: setup → verify → backup codes → disable через портал | Done, задеплоен |
| **Password Change** | Смена пароля с валидацией на /app/settings | Done, задеплоен |
| **Template CRUD** | Создание шаблонов, детальная страница, добавление/удаление слотов | Done, задеплоен |
| **Dashboard v2** | Active/total channels, success rate %, upcoming tasks, channel names | Done, задеплоен |

### Фаза 9: Безопасность и изоляция данных (28.02.2026)

| Фича | Описание | Статус |
|------|----------|--------|
| **User-scoped data** | Обычный пользователь видит только свои каналы/задачи/шаблоны, admin — всё | Done, задеплоен |
| **Access control** | Проверка ownership на всех detail/edit/delete маршрутах портала | Done, задеплоен |
| **UUID URLs** | Замена числовых ID на UUID в URL для защиты от IDOR атак | Done, задеплоен |
| **UUID колонки в БД** | `uuid VARCHAR(36) NOT NULL UNIQUE` в 3 таблицах: channels, tasks, templates | Done, задеплоен |
| **Admin check fix** | Исправлена проверка admin — сравнение status как int (1), а не string | Done, задеплоен |
| **Template ownership** | Добавлены проверки ownership на template detail/slots/delete | Done, задеплоен |

### Фаза 10: Legacy cleanup (28.02.2026)

| Фича | Описание | Статус |
|------|----------|--------|
| **Legacy code removal** | Удалены 220+ legacy файлов (app, config, docs, scripts, tests) — -61K строк | Done |
| **Rename legacy/ → unported/** | Оставлены только непортированные модули: voice/ и cpp/video/ | Done |
| **DDL cleanup** | Удалены 11 legacy reference DDL файлов, Docker init | Done |
| **Dead references** | Вычищены мёртвые ссылки на legacy/ из 7 файлов | Done |
| **Porting issue** | GitHub issue #107 — задача на портирование оставшихся модулей | Done |

### Фаза 11: Security Pentest & Remediation (02.03.2026)

Независимый пентест всей кодовой базы — найдено и исправлено 12 уязвимостей.

| Severity | Фикс | Описание | Статус |
|----------|------|----------|--------|
| **CRITICAL** | Channels auth | Все 6 API endpoints `/api/v1/channels/*` работали БЕЗ авторизации | Fixed |
| **CRITICAL** | CORS wildcard | `allow_origins=["*"]` + `allow_credentials=True` → CSRF через JS | Fixed |
| **CRITICAL** | JWT fallback | Hardcoded fallback ключ → `raise RuntimeError` при старте | Fixed |
| **CRITICAL** | Demo endpoint | `/api/v1/items/*` без auth (DoS на RAM) — удалён | Fixed |
| **HIGH** | Task IDOR | API tasks без фильтрации по user + нет ownership check | Fixed |
| **HIGH** | Path traversal | `_file_info()` позволяла пробить произвольные пути на сервере | Fixed |
| **MEDIUM** | Security headers | Добавлены CSP, Permissions-Policy | Fixed |
| **MEDIUM** | Rate limiting | Добавлены лимиты: uploads 10/min, channels 10/min, tasks 20/min, batch 5/min | Fixed |
| **MEDIUM** | Weak passwords | Минимум пароля 6→8 символов | Fixed |
| **MEDIUM** | Backup codes | Энтропия 32→48 бит (`token_hex(4)`→`token_hex(6)`) | Fixed |
| **MEDIUM** | Bind address | `uvicorn 0.0.0.0` → `127.0.0.1` | Fixed |
| **WARNING** | Deprecation | `datetime.utcnow()` → `datetime.now(UTC)` в 4 файлах | Fixed |

### Фаза 12: Ops, Logging & Server Hardening (02.03.2026)

| Категория | Описание | Статус |
|-----------|----------|--------|
| **Dependencies** | Обновлены все до последних: fastapi 0.115.12, uvicorn 0.34.2, pydantic 2.11.3, jinja2 3.1.6 | Done |
| **Task mismatch fix** | API create_task/batch не передавали `created_by`, dashboard без processing/cancelled, `completed_at` NULL | Fixed |
| **Centralized auth** | Создан `app/core/auth.py`, убраны 4 дубликата auth-функций | Done |
| **Code dedup** | `_task_cols()` вместо 3 inline копий, consolidated auth helpers | Done |
| **Systemd hardening** | bind 127.0.0.1, MemoryMax, LimitNOFILE, SyslogIdentifier, restart limits | Done |
| **Logrotate** | Daily rotation (14 дней) для сервисов, weekly (52 недели) для audit | Done |
| **Nginx** | Upstream keepalive, gzip, security headers, health bypass, static alias | Done |
| **Detailed logging** | 11 файлов: все repos, auth, admin, templates, queue — 97 новых log statements | Done |
| **Server packages** | apt upgrade 50 пакетов: nginx 1.28.2, MySQL 8.0.44, systemd, security patches | Done |
| **Python 3.10 compat** | `datetime.UTC` (3.11+) → `timezone.utc` в 4 файлах | Fixed |
| **orjson** | Добавлен для быстрой JSON-сериализации | Done |

### Фаза 13: Tests, Monitoring & Critical Bug Fixes (02.03.2026)

| Категория | Описание | Статус |
|-----------|----------|--------|
| **Test coverage x2** | 89→202 теста: 7 новых test files (db_utils, auth_core, channels, templates, repos_extended, logging, 2fa) | Done |
| **Scheduler bug fix** | `TaskStatus.PENDING` (IntEnum) не конвертировался в int в SQL → scheduler не видел pending задачи | **Critical fix** |
| **Shared DB utils** | `shared/db/utils.py` — serialize_json, deserialize_json, build_update, is_duplicate_key_error, truncate_error | Done |
| **Centralized logging** | `shared/logging_config.py` — JSON logging (python-json-logger), единая настройка для всех 5 сервисов | Done |
| **Health check panel** | `/panel/health` — статус сервисов, диск/память, MySQL/Redis latency, очереди | Done |
| **Logs viewer panel** | `/panel/logs` — просмотр journalctl логов, фильтры по сервису/уровню, auto-refresh | Done |
| **Anti-patterns fixed** | Убраны дублирующиеся column lists (3 в console_repo), JSON serialize/deserialize, error truncation | Done |
| **Workers logging** | Все 3 воркера + scheduler переведены на centralized logging | Done |
| **PROD_README update** | Секция по логам, ошибкам, troubleshooting, systemd командам | Done |

---

## 4. Проблемные каналы (требуют ручного вмешательства)

### Категория 1: «Verify it's you» — Google security challenge (9 каналов, issue #96)
Google не доверяет серверу (46.21.250.43). После email+пароль показывает «Verify it's you».
**Каналы:** girl_vibestv, youtubebaza-h8s, ytub-b9i, YouTube9, YouTube11, YouTube7_0, Дитячі канали, Блог чоловіки, Блогери жінки
**Решение:** залогиниться вручную с сервера через VNC (~5 мин/аккаунт)
**Ответственный:** @mykytatishkin

### Категория 2: OAuth app не верифицирован (1 канал, issue #97)
**Канал:** Канали новин (kanalinovin831@gmail.com)
**Решение:** добавить email в test users GCP Console

### Категория 3: Аккаунт не найден (1 канал, issue #98)
**Канал:** Топ шоу ру (topsooru@gmail.com) — Google не находит аккаунт
**Решение:** проверить email с командой

### Рабочие каналы: 17 из 30 enabled (15 processing + 2 исправлены)

---

## 5. Открытые задачи (backlog)

### Ручные задачи (назначены на @mykytatishkin)

| Issue | Задача | Приоритет |
|-------|--------|-----------|
| #105 | SSL/HTTPS сертификаты (Let's Encrypt) | Высокий |
| #106 | Настройка доменного имени | Высокий |
| #96 | Реавторизация 9 каналов (VNC) | Высокий |
| #97 | Канали новин — test user в GCP | Средний |
| #98 | Топ шоу ру — проверить email | Средний |
| #99 | TOTP секреты от команды | Средний |
| #19 | Верификация OAuth app в Google | Низкий (долгий процесс) |

### Задачи на разработку (ответственные указаны)

| Issue | Задача | Ответственный | Статус |
|-------|--------|---------------|--------|
| #107 | Портирование unported/ (voice + cpp) в prod | @mykytatishkin | Issue создан |
| #100 | Voice worker — ML портирование | @mykytatishkin | Stub готов |
| #101 | Подключение оплаты (LiqPay/Stripe) | @mykytatishkin | UI-заглушка готова |
| #102 | YouTube LIVE стриминг | @mykytatishkin | Backlog |
| #104 | C++ модуль (ватермарки, субтитры) | Дима (@graf_crayt) | В разработке |

### Требуют внешних интеграций

| # | Story | Что нужно |
|---|-------|-----------|
| US-010 | Watermark | C++ модуль (Дима) |
| US-022 | Реклама (18+) | Billing + ad network |
| US-023 | Подписки и биллинг | Payment system — UI-заглушка готова |
| US-024 | Тарифные ограничения | Зависит от US-023 |

---

## 6. Очистка репозитория

| Действие | До | После |
|----------|-------|-------|
| Remote branches | 17 | 1 (main) |
| Local branches | 15 | 1 (main) |
| Open issues | 33 | 22 (9 новых) |
| Closed issues | 0 | 21 |
| Open PRs | 0 | 0 |
| Legacy процессы | 5 | 0 (убиты) |
| Legacy код | 269 файлов (27MB) | 50 файлов в unported/ (342K) |

---

## 7. Инфраструктура (прод)

**Сервер:** 46.21.250.43 (Xeon E5-2430v2, 32GB RAM, Quadro P2000)

| Компонент | Статус | Порт |
|-----------|--------|------|
| FastAPI (uvicorn) | Running | :8000 |
| SSR Admin Panel | Running | :8000/panel/ |
| Scheduler | Running | — |
| Publishing Worker | Running | — |
| Notification Worker | Running | — |
| Redis 7 | Running | :6379 |
| MySQL | Running | :3306 |
| Legacy task_worker | **УБИТ** | — |
| Nginx | Running | :80 |

**Health check:** `GET /health` — api=ok, mysql=ok, redis=ok

---

## 8. Безопасность (аудит проведён 28.02)

| Было | Стало |
|------|-------|
| JWT секрет hardcoded | `raise RuntimeError` при отсутствии env var |
| `reload=True` в проде | Отключено (ENV-based) |
| CORS `*` + credentials | Origins ограничены, credentials=False |
| Нет rate limiting | 10/min логин, 5/min регистрация, 20/min задачи, 10/min каналы |
| Нет security headers | X-Frame-Options, CSP, Permissions-Policy, Referrer-Policy |
| Stack traces в ответах | Sanitized error messages |
| Нет path validation | Проверка на `..` + UPLOAD_DIR prefix в file paths |
| `/docs` в проде | Скрыты при `DEBUG=False` |
| Bind `0.0.0.0` | Bind `127.0.0.1` (nginx перед) |
| Нет логирования | Детальное логирование во всех 11 модулях |
| Нет logrotate | Daily rotation (14 дней) + weekly audit (52 недели) |
| Нет тестов | **202 теста, все зелёные** |

---

---

## Phase 14 — Legacy Port, Reauth Module, Cleanup (02.03.2026)

### Playwright Reauth Module — восстановлен и переписан
- Восстановлены 4 файла из git history (4200+ строк): models.py, oauth_flow.py, playwright_client.py, service.py
- `service.py` полностью переписан: legacy `YouTubeMySQLDatabase` → prod repos (`channel_repo`, `console_repo`, `credential_repo`, `audit_repo`)
- `playwright_client.py` (3249 строк) — обновлены импорты, заменена система уведомлений на `shared.notifications.telegram`
- CLI tool: `python -m cli.reauth --channel-id 9` / `--all-failed` / `--all`
- `audit_repo.py` — добавлены `trigger_reason` и `error_code` параметры

### Voice Module — портирован из unported/
- 12 файлов скопированы: voice_changer.py, mixer.py, silero.py, prosody.py, stress.py, rvc/* и др.
- Все импорты `core.voice.*` → `shared.voice.*`, `core.utils.logger` → `logging`
- Stub `changer.py` обновлён (docstring, реальный VoiceChanger уже lazy-загружается)

### Pydantic Improvements
- `Channel` schema: добавлены `uuid`, `has_tokens`, `token_expires_at` поля
- `ChannelUpdate` schema — новая
- `TaskResponse`: добавлен `uuid` field
- `TaskUpdate.status` — валидация `ge=0, le=4`
- `TaskCreate` — переписан `field_validator` на Pydantic v2 стиль
- Удалены `items.py` и `item.py` (legacy demo endpoint)

### Расхождения исправлены
- `channel_repo.add_login_credentials` — дубликат удалён, call sites переведены на `credential_repo.add_credentials`
- `console_repo._CONSOLE_COLS` — добавлен `project_id`
- C++ module перенесён: `unported/core/cpp/video/` → `prod/cpp/video/`
- `unported/` директория удалена полностью

### Тесты
- 202 теста — все проходят (0 failures)
- Тесты console_repo обновлены под новый `project_id` field

---

## 9. Риски и рекомендации

| Риск | Митигация |
|------|-----------|
| 12 каналов stuck (Timeout) | Reauth CLI готов: `python -m cli.reauth --all-failed` |
| Voice worker нужны ML зависимости | torch, librosa, pyworld нужно установить на сервер |
| Нет CI/CD | Руками справляемся, автоматизация отложена |
| Нет HTTPS | Рекомендация: certbot/Let's Encrypt |
| Нет backup MySQL | Рекомендация: cron + mysqldump → S3 |

**Ближайший приоритет:**
1. Установить Playwright + pyotp на прод и запустить `python -m cli.reauth --all-failed`
2. @mykytatishkin — настроить домен + SSL/HTTPS
3. @mykytatishkin — добавить Канали новин в GCP test users
4. @graf_crayt — C++ модуль ватермарков/субтитров (scaffold перенесён в prod/cpp/)
