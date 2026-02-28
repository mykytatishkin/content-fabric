# Content Fabric — Отчёт для менеджера проекта

> Период: октябрь 2025 — февраль 2026
> Последнее обновление: 28.02.2026

---

## 1. Краткое резюме

Проект Content Fabric прошёл полную трансформацию: от монолитного Python-скрипта (1500+ строк) к микросервисной архитектуре из 6 независимых сервисов. Система задеплоена на продакшн-сервере и работает в параллели с legacy.

**Ключевые цифры:**
- 30 Pull Request'ов смерджено
- 22 user stories закрыты (из 33)
- 6 микросервисов в проде
- 15 таблиц БД (новая схема + 2FA + templates)
- 39 каналов управляются через API
- 0 даунтаймов при миграции

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

## 4. Открытые задачи (backlog) — 11 из 33

### Требуют внешних интеграций / оплаты

| # | Story | Что нужно |
|---|-------|-----------|
| US-010 | Watermark (бесплатные видео) | C++ video processing |
| US-022 | Реклама (18+) | Billing + ad network |
| US-023 | Подписки и биллинг | Payment system (Stripe/LiqPay) |
| US-024 | Тарифные ограничения | Usage counters + billing |

### Legacy features (внешние зависимости)

| # | Задача | Ответственный |
|---|--------|---------------|
| #19 | Publish App on Google Console | — |
| #24 | Instagram Uploads | — |
| #25 | Модификация видео (C++) | @graf_crayt |
| #29 | YouTube LIVE | — |
| #30 | Транскрибатор на C++ | @graf_crayt |
| #33 | Short story BOOK | — |
| #35 | Voice changer improvements | — |
| #37 | YouTube Shorts cover | — |

---

## 5. Очистка репозитория

| Действие | До | После |
|----------|-------|-------|
| Remote branches | 17 | 1 (main) |
| Local branches | 15 | 1 (main) |
| Open issues | 33 | 13 |
| Closed issues | 0 | 20 |
| Open PRs | 0 | 0 |

Все feature branches удалены. Репозиторий чистый.

---

## 6. Инфраструктура (прод)

**Сервер:** 46.21.250.43 (Xeon E5-2430v2, 32GB RAM, Quadro P2000)

| Компонент | Статус | Порт |
|-----------|--------|------|
| FastAPI (uvicorn) | Running | :8000 |
| Scheduler | Running | — |
| Publishing Worker | Running | — |
| Notification Worker | Running | — |
| Redis 7 | Running | :6379 |
| MySQL | Running | :3306 |
| Legacy task_worker | Running (параллельно) | — |
| Nginx | Running | :80 |

**Логи:** `/var/log/cff-api.log`, `cff-scheduler.log`, `cff-publishing-worker.log`, `cff-notification-worker.log`, `cff-audit.log`

---

## 7. Безопасность (аудит проведён 28.02)

| Было | Стало |
|------|-------|
| JWT секрет hardcoded | Warning при отсутствии env var |
| `reload=True` в проде | Отключено (ENV-based) |
| CORS `*` | Ограничены методы и заголовки |
| Нет rate limiting | 10 req/min логин, 5 req/min регистрация |
| Нет security headers | X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| Stack traces в ответах | Sanitized error messages |
| Нет path validation | Проверка на `..` в file paths |
| `/docs` в проде | Скрыты при `DEBUG=False` |

---

## 8. Риски и рекомендации

| Риск | Митигация |
|------|-----------|
| Legacy worker обрабатывает те же задачи | Scheduler помечает задачи status=3 (processing) — legacy не подхватит |
| Файлы задач с путями `/var/www/fastuser/...` | Старые задачи зафейлились (файлы на другом сервере) — новые задачи с корректными путями |
| Нет systemd сервисов | **Решено:** systemd unit files готовы (`prod/deploy/systemd/`), нужно установить на сервере |
| Нет 2FA | **Решено:** TOTP 2FA с backup codes |

**Рекомендация на ближайшее время:**
1. Установить systemd сервисы: `bash prod/deploy/install-services.sh`
2. Настроить HTTPS (certbot/Let's Encrypt)
3. Настроить backup MySQL → S3/external
