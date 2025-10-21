# 📚 Документация проекта

## 🎙️ Voice Changer

### Основные гайды:
- **[VOICE_CHANGER.md](VOICE_CHANGER.md)** - Полное руководство по Voice Changer
- **[BACKGROUND_PRESERVATION_GUIDE.md](BACKGROUND_PRESERVATION_GUIDE.md)** - Сохранение фона/музыки
- **[docs/guides/RUSSIAN_STRESS_GUIDE.md](docs/guides/RUSSIAN_STRESS_GUIDE.md)** - 🎯 Правильное ударение (NEW!)

### Примеры:
- `examples/voice_changer_example.py` - Примеры использования
- `examples/russian_stress_example.py` - 🎯 Примеры работы с ударениями

---

## 🚀 Установка и настройка

### Быстрый старт:
- **[docs/setup/QUICK_START.md](docs/setup/QUICK_START.md)** - Быстрая установка
- **[docs/setup/PLATFORM_SETUP_GUIDE.md](docs/setup/PLATFORM_SETUP_GUIDE.md)** - Настройка платформ

### База данных:
- **[docs/setup/MYSQL_SETUP_GUIDE.md](docs/setup/MYSQL_SETUP_GUIDE.md)** - MySQL
- **[docs/DOCKER_MYSQL_SETUP.md](docs/DOCKER_MYSQL_SETUP.md)** - Docker + MySQL

---

## 📋 Управление задачами

- **[docs/guides/TASK_QUICK_START.md](docs/guides/TASK_QUICK_START.md)** - Быстрый старт
- **[docs/guides/TASK_MANAGEMENT.md](docs/guides/TASK_MANAGEMENT.md)** - Полное руководство
- **[docs/TASK_MANAGEMENT_SUMMARY.md](docs/TASK_MANAGEMENT_SUMMARY.md)** - Сводка

---

## 📊 Уведомления и отчеты

- **[TELEGRAM_DAILY_REPORT.md](TELEGRAM_DAILY_REPORT.md)** - 📊 Главная страница ежедневных отчетов
- **[docs/reports/QUICK_START.md](docs/reports/QUICK_START.md)** - Быстрый старт
- **[docs/reports/COMPLETE_GUIDE.md](docs/reports/COMPLETE_GUIDE.md)** - Полное руководство
- **[docs/reports/TECHNICAL_SUMMARY.md](docs/reports/TECHNICAL_SUMMARY.md)** - Техническая документация
- Автоматические отчеты в Telegram о выполнении задач (12:00 ежедневно)

---

## 🎬 YouTube

### Настройка и управление:
- **[docs/guides/YOUTUBE_SETUP.md](docs/guides/YOUTUBE_SETUP.md)** - Настройка YouTube
- **[docs/YOUTUBE_DATABASE_GUIDE.md](docs/YOUTUBE_DATABASE_GUIDE.md)** - База данных каналов
- **[docs/guides/AUTO_LIKE_COMMENT.md](docs/guides/AUTO_LIKE_COMMENT.md)** - Автоматичний лайк та коментар після завантаження

### OAuth и токены:
- **[REAUTH_README.md](REAUTH_README.md)** - 🔐 Быстрое решение проблем с токенами (NEW!)
- **[docs/youtube/05-TOKEN-REAUTH-GUIDE.md](docs/youtube/05-TOKEN-REAUTH-GUIDE.md)** - 🔐 Полное руководство по переавторизации (NEW!)
- **[docs/youtube/04-TROUBLESHOOTING.md](docs/youtube/04-TROUBLESHOOTING.md)** - Устранение неполадок

---

## 👥 Управление аккаунтами

- **[docs/guides/CHANNEL_MANAGEMENT.md](docs/guides/CHANNEL_MANAGEMENT.md)** - Управление каналами
- **[docs/guides/MULTIPLE_ACCOUNTS.md](docs/guides/MULTIPLE_ACCOUNTS.md)** - Множественные аккаунты

---

## 🔧 Техническая документация

- **[docs/technical/TECHNICAL_DOCS.md](docs/technical/TECHNICAL_DOCS.md)** - Техническая информация
- **[docs/technical/MYSQL_MIGRATION.md](docs/technical/MYSQL_MIGRATION.md)** - Миграция MySQL

---

## 📁 Структура проекта

- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Структура файлов

---

## 🎯 Главные команды

```bash
# Voice Changer
python3 run_voice_changer.py --help

# Task Manager
python3 run_task_manager.py

# YouTube Manager
python3 run_youtube_manager.py
python3 run_youtube_manager.py check-tokens  # Проверка токенов

# Database Setup
python3 run_setup_database.py

# OAuth Token Re-authentication (NEW!)
python3 reauth_multiple_channels.py audiokniga-one    # Один канал
python3 reauth_multiple_channels.py --expired         # Все истекшие
python3 check_token_limit.py                          # Диагностика лимитов

# Daily Reports
python3 run_daily_report.py              # Send yesterday's report
python3 run_daily_report.py test         # Test report
python3 scripts/daily_report_scheduler.py # Auto-scheduler (12:00 daily)
```

---

**Начните с [VOICE_CHANGER.md](VOICE_CHANGER.md) или [docs/setup/QUICK_START.md](docs/setup/QUICK_START.md)!**
