# Content Fabric — Web Portal Guide

> Последнее обновление: 28.02.2026

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
- **Карточки:** количество каналов, pending/completed/failed задачи
- **Таблица:** 10 последних задач (id, channel, title, status, scheduled, created)
- **Quick actions:** кнопки "Add Channel" и "Create Task"

### 4.4 Channels (`/app/channels`)
- Таблица всех каналов: ID, name, YouTube ID, enabled, processing status, token status, created
- Кнопка "Add Channel"
- Статусы токенов: OK (зелёный) / Missing (красный)

### 4.5 Add Channel (`/app/channels/add`)
- **Основные поля:**
  - Channel Name (латиница)
  - YouTube Channel ID или @Handle
  - OAuth Console (выпадающий список из GCP credentials)
  - Checkbox: Enabled
- **RPA Credentials** (раскрывающийся блок):
  - Login email, password
  - TOTP secret (base32)
- После создания → редирект на список каналов

### 4.6 Tasks (`/app/tasks`)
- **Карточки статистики:** pending, processing, completed, failed
- **Фильтры:** по статусу, по каналу (dropdown с auto-submit)
- **Таблица:** ID, channel name, title, status badge, scheduled, created, error message
- Кнопка "Create Task"

### 4.7 Create Task (`/app/tasks/new`)
- **Обязательные поля:**
  - Channel (dropdown enabled каналов)
  - Title
  - Source File Path (путь к видео на сервере)
- **Опциональные поля:**
  - Scheduled At (datetime-local picker)
  - Description, Keywords, Thumbnail Path, Post Comment
- Если scheduled_at не указано — задача создаётся на текущее время

### 4.8 Schedule Templates (`/app/templates`)
- Таблица шаблонов: ID, name, description, timezone, slots count, active/inactive
- Создание шаблонов — через API (`POST /api/v1/templates/`)

### 4.9 Account Settings (`/app/settings`)
- **Профиль:** username, email, display name, status, timezone, дата регистрации
- **2FA секция:** статус (enabled/not enabled), инструкции по API для включения/отключения

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
│   ├── app_portal.py          # User portal routes (login, register, dashboard, etc.)
│   └── panel.py               # Admin panel routes (with admin auth check)
├── templates/
│   ├── app_base.html          # User portal layout (sidebar + content)
│   ├── app_login.html         # Login page (standalone)
│   ├── app_register.html      # Register page (standalone)
│   ├── app_dashboard.html     # User dashboard
│   ├── app_channels.html      # Channel list
│   ├── app_channel_add.html   # Add channel form
│   ├── app_tasks.html         # Task list with filters
│   ├── app_task_new.html      # Create task form
│   ├── app_templates.html     # Schedule templates
│   ├── app_settings.html      # Account settings
│   ├── base.html              # Admin panel layout
│   ├── dashboard.html         # Admin dashboard
│   ├── channels.html          # Admin channels
│   ├── tasks.html             # Admin tasks
│   ├── users.html             # Admin users
│   ├── credentials.html       # Admin credentials
│   └── payment.html           # Payment stub
└── main.py                    # Mounts /app/ and /panel/ routers
```
