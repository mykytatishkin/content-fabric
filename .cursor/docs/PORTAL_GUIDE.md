# Content Fabric — Web Portal Guide

> Последнее обновление: 01.03.2026

---

## 1. Обзор

Веб-портал Content Fabric состоит из двух частей:

| Портал | URL | Доступ | Назначение |
|--------|-----|--------|------------|
| **User Portal** | `/app/` | Все зарегистрированные пользователи | Управление каналами, задачами, шаблонами |
| **Admin Panel** | `/panel/` | Только администраторы | Обзор всей системы, все юзеры/каналы/задачи |

**Продакшн:** http://46.21.250.43

---

## 2. Тестовые аккаунты

| Роль | Email | Пароль | Доступ |
|------|-------|--------|--------|
| Admin | `admin@cff.local` | `Admin123!` | `/app/` + `/panel/` |
| User | `demo@cff.local` | `Demo123!` | только `/app/` |

Новые аккаунты можно создать через `/app/register`.

---

## 3. Аутентификация

- **Cookie-based JWT** — при логине сервер ставит `HttpOnly` cookie `cff_token`
- Токен живёт **24 часа**, после чего нужно перелогиниться
- Поддержка **2FA (TOTP)** — если включена, при логине требуется код из authenticator app
- **Logout** очищает cookie и редиректит на логин

### Flow
```
/app/login  →  POST email+password  →  Set-Cookie: cff_token=<JWT>  →  Redirect /app/
/app/logout →  Clear cookie  →  Redirect /app/login
```

### Защита страниц
- Все `/app/*` страницы (кроме login/register) требуют валидный cookie
- Все `/panel/*` страницы требуют cookie + статус `admin` в БД
- Без cookie → редирект на `/app/login`
- User без admin → `/panel/` редиректит на `/app/`

---

## 4. User Portal — Страницы

### 4.1 Login (`/app/login`)
- Поля: email, password, 2FA code (опционально)
- Ошибки отображаются inline
- Ссылка на регистрацию

### 4.2 Register (`/app/register`)
- Поля: username, email, display name, password
- Валидация: уникальность email/username, пароль >= 6 символов
- После регистрации — автоматический логин

### 4.3 Dashboard (`/app/`)
- **Карточки:** каналы (active/total), total tasks, pending, completed, failed, success rate %
- **Upcoming Tasks:** ближайшие запланированные задачи (до 5)
- **Recent Tasks:** 10 последних задач с именами каналов и кликабельными ссылками
- **Quick actions:** кнопки "Add Channel" и "Create Task"

### 4.4 Channels (`/app/channels`)
- Таблица всех каналов: ID, name, YouTube ID, enabled, processing status, token status, created
- Имена каналов — кликабельные ссылки на детальную страницу
- Кнопки "Add Channel" и "Delete" для каждого канала

### 4.5 Channel Detail (`/app/channels/{id}`)
- **Информация о канале:** YouTube ID, enabled, tokens, дата создания
- **Task Statistics:** total / pending / processing / completed / failed / cancelled
- **Login Credentials:** email, TOTP status, proxy, last success/error
- **Recent Tasks:** последние 20 задач канала с кнопками Cancel/Retry
- **Действия:** Edit Channel, Delete Channel

### 4.6 Channel Edit (`/app/channels/{id}/edit`)
- Изменение имени канала, toggle enabled
- Обновление RPA credentials (email, password, TOTP secret)

### 4.7 Add Channel (`/app/channels/add`)
- **Основные поля:** Channel Name, YouTube Channel ID/@Handle, OAuth Console, Enabled
- **RPA Credentials:** Login email, password, TOTP secret (base32)
- После создания → редирект на список каналов

### 4.8 Tasks (`/app/tasks`)
- **Карточки статистики:** pending, processing, completed, failed
- **Фильтры:** по статусу, по каналу (dropdown с auto-submit)
- **Таблица:** ID, channel (ссылка), title (ссылка на детали), status, scheduled, created, error
- **Действия:** Cancel (pending), Retry (failed/cancelled)

### 4.9 Task Detail (`/app/tasks/{id}`)
- **Полная информация:** статус, канал, даты, файл, описание, keywords, thumbnail, upload ID, retries
- **Блок ошибки** для failed задач
- **Reschedule:** форма перепланирования для pending задач
- **Действия:** Cancel Task, Retry Task

### 4.10 Create Task (`/app/tasks/new`)
- **Обязательные поля:** Channel, Title, Source File Path
- **Загрузка файлов:** AJAX-загрузка видео и thumbnail прямо из браузера
  - Выбор файла → загрузка на сервер → автозаполнение пути
  - Поддержка: mp4, mkv, avi, mov, webm, flv, wmv, m4v (видео), jpg, png, webp (thumbnail)
- **Опциональные поля:** Scheduled At, Description, Keywords, Thumbnail, Post Comment
- Если scheduled_at не указано — задача создаётся на текущее время

### 4.11 Schedule Templates (`/app/templates`)
- Таблица шаблонов: ID, name, description, timezone, slots count, active/inactive
- Кликабельные имена → детальная страница
- Кнопки "Create Template" и "Delete" для каждого

### 4.12 Template Detail (`/app/templates/{id}`)
- **Информация:** timezone, количество слотов, статус (active/inactive)
- **Time Slots:** таблица слотов (день недели, время, канал, тип медиа)
- **Add Slot:** форма добавления (день, время, канал опционально)
- **Действия:** удаление отдельных слотов, удаление всего шаблона

### 4.13 Create Template (`/app/templates/new`)
- Поля: имя, описание, timezone (UTC, Europe/Kyiv, US/Eastern и др.)

### 4.14 Account Settings (`/app/settings`)
- **Профиль:** редактирование display name и timezone, сохранение
- **2FA:** полный UI-flow:
  - "Enable 2FA" → показ TOTP secret → ввод кода → backup codes
  - "Disable 2FA" с подтверждением пароля
- **Смена пароля:** текущий пароль, новый пароль, подтверждение

---

## 5. Admin Panel — Страницы

Доступен только для пользователей со статусом `admin` в БД.

### 5.1 Dashboard (`/panel/`)
- Каналы: active/total
- Пользователи: total
- Задачи: pending, completed, failed
- Очередь Redis: total jobs
- Таблица: последние 10 ошибок
- Таблица: каналы требующие реавторизации

### 5.2 Channels (`/panel/channels`)
- Все каналы системы с полными данными

### 5.3 Tasks (`/panel/tasks`)
- Все задачи (до 200) со статистикой

### 5.4 Users (`/panel/users`)
- Все пользователи: username, email, status, 2FA, дата регистрации

### 5.5 Credentials (`/panel/credentials`)
- Login credentials каналов: email, TOTP status, proxy, last success/error

### 5.6 Payment (`/panel/payment`)
- Заглушка с тарифными планами (Free/Pro/Enterprise)
- Требует интеграции с Stripe/LiqPay

---

## 6. API Documentation

Swagger UI доступен: http://46.21.250.43/docs

Все API endpoints используют JWT Bearer token (не cookie). Для работы с API:
1. `POST /api/v1/auth/login` → получить `access_token`
2. Добавлять заголовок `Authorization: Bearer <token>` к запросам

---

## 7. Навигация

### Sidebar User Portal
```
Dashboard      → /app/
Channels       → /app/channels
Tasks          → /app/tasks
Templates      → /app/templates
Settings       → /app/settings
Admin Panel*   → /panel/        (* только для админов)
API Docs       → /docs
Health         → /health
Logout         → /app/logout
```

---

## 8. Технические детали

| Компонент | Технология |
|-----------|-----------|
| Backend | FastAPI + Jinja2 SSR |
| Auth | JWT в HttpOnly cookie (HS256, 24h expiry) |
| Templates | `prod/app/templates/app_*.html` |
| Routes | `prod/app/views/app_portal.py` |
| Admin routes | `prod/app/views/panel.py` |
| DB queries | SQLAlchemy Core через `shared/db/repositories/` |
| Styles | Inline CSS (system-ui, card/table/badge components) |

### Файловая структура
```
prod/app/
├── views/
│   ├── app_portal.py          # User portal routes (30+ routes)
│   └── panel.py               # Admin panel routes (with admin auth check)
├── templates/
│   ├── app_base.html          # User portal layout (sidebar + content)
│   ├── app_login.html         # Login page (standalone)
│   ├── app_register.html      # Register page (standalone)
│   ├── app_dashboard.html     # User dashboard (stats + upcoming + recent)
│   ├── app_channels.html      # Channel list with delete buttons
│   ├── app_channel_add.html   # Add channel form
│   ├── app_channel_detail.html # Channel detail with stats & credentials
│   ├── app_channel_edit.html  # Edit channel form
│   ├── app_tasks.html         # Task list with filters, cancel & retry
│   ├── app_task_new.html      # Create task with file upload
│   ├── app_task_detail.html   # Task detail with reschedule & retry
│   ├── app_templates.html     # Schedule templates list
│   ├── app_template_new.html  # Create template form
│   ├── app_template_detail.html # Template detail with slot management
│   ├── app_settings.html      # Profile edit, 2FA UI, password change
│   ├── base.html              # Admin panel layout
│   ├── dashboard.html         # Admin dashboard
│   ├── channels.html          # Admin channels
│   ├── tasks.html             # Admin tasks
│   ├── users.html             # Admin users
│   ├── credentials.html       # Admin credentials
│   └── payment.html           # Payment stub
└── main.py                    # Mounts /app/ and /panel/ routers
```
