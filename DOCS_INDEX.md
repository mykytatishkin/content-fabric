# 📚 Content Fabric - Индекс документации

> Полный справочник по документации проекта Content Fabric

**Версия**: 2.0  
**Последнее обновление**: 2025-01-16

---

## 🚀 Быстрый старт

| Документ | Описание | Для кого |
|----------|----------|----------|
| **[README.md](../README.md)** | Главная страница проекта | Все |
| **[docs/setup/QUICK_START.md](setup/QUICK_START.md)** | Быстрая установка за 5 минут | Новички |
| **[CLI_USAGE.md](../CLI_USAGE.md)** | Справочник по командам CLI | Все пользователи |

---

## 📖 Основные разделы

### 🎙️ Voice Processing System

**Изменение голоса и синтез речи**

| Документ | Описание |
|----------|----------|
| **[VOICE_CHANGER.md](voice/VOICE_CHANGER.md)** | Полное руководство по Voice Changer |
| **[TEXT_TO_SPEECH.md](voice/TEXT_TO_SPEECH.md)** | Text-to-Speech синтез речи |
| **[BACKGROUND_PRESERVATION_GUIDE.md](voice/BACKGROUND_PRESERVATION_GUIDE.md)** | Сохранение фона/музыки |
| **[RUSSIAN_STRESS_GUIDE.md](voice/RUSSIAN_STRESS_GUIDE.md)** | Правильное ударение в русском языке |

**Производительность и оптимизация**

| Документ | Описание |
|----------|----------|
| **[PARALLEL_VOICE_PROCESSING.md](voice/PARALLEL_VOICE_PROCESSING.md)** | Параллельная обработка (2-4x ускорение) |
| **[SPEED_OPTIMIZATION.md](voice/SPEED_OPTIMIZATION.md)** | Оптимизация скорости обработки |

**Примеры кода**

- `examples/voice_changer_example.py` - Примеры использования Voice Changer
- `examples/text_to_speech_example.py` - Примеры TTS синтеза
- `examples/russian_stress_example.py` - Примеры работы с ударениями

---

### 📋 Task Management System

**Управление задачами через MySQL**

| Документ | Описание |
|----------|----------|
| **[TASK_QUICK_START.md](guides/TASK_QUICK_START.md)** | Быстрый старт с Task Management |
| **[TASK_MANAGEMENT.md](guides/TASK_MANAGEMENT.md)** | Полное руководство по системе задач |
| **[TASK_MANAGEMENT_SUMMARY.md](TASK_MANAGEMENT_SUMMARY.md)** | Краткая сводка возможностей |

**Дополнительные функции**

| Документ | Описание |
|----------|----------|
| **[AUTO_LIKE_COMMENT.md](guides/AUTO_LIKE_COMMENT.md)** | Автоматический лайк и комментарий после загрузки |
| **[UPLOAD_ID_TRACKING.md](guides/UPLOAD_ID_TRACKING.md)** | Отслеживание ID загруженных видео |

---

### 📺 YouTube Integration

**Настройка и управление**

| Документ | Описание |
|----------|----------|
| **[youtube/README.md](youtube/README.md)** | Оглавление YouTube документации |
| **[youtube/01-SETUP.md](youtube/01-SETUP.md)** | Полная настройка с нуля |
| **[youtube/02-CLI-GUIDE.md](youtube/02-CLI-GUIDE.md)** | Детальный гайд по CLI командам |
| **[youtube/03-ARCHITECTURE.md](youtube/03-ARCHITECTURE.md)** | Архитектура системы |
| **[youtube/04-TROUBLESHOOTING.md](youtube/04-TROUBLESHOOTING.md)** | Решение проблем |

**Продвинутые функции**

| Документ | Описание |
|----------|----------|
| **[youtube/05-TOKEN-REAUTH-GUIDE.md](youtube/05-TOKEN-REAUTH-GUIDE.md)** | Полное руководство по переавторизации |
| **[youtube/COMPLETE_WORKFLOW.md](youtube/COMPLETE_WORKFLOW.md)** | Полный рабочий процесс |
| **[youtube/HOW_PUBLISHING_WORKS.md](youtube/HOW_PUBLISHING_WORKS.md)** | Как работает публикация |
| **[youtube/MULTI_CONSOLE_GUIDE.md](youtube/MULTI_CONSOLE_GUIDE.md)** | Работа с несколькими Google Console |
| **[youtube/PUBLISHING_WITH_CONSOLES.md](youtube/PUBLISHING_WITH_CONSOLES.md)** | Публикация через Google Consoles |
| **[GOOGLE_CONSOLES_PUBLISHING.md](GOOGLE_CONSOLES_PUBLISHING.md)** | Публикация через Google Consoles (общее) |

---

### 🔐 OAuth и Безопасность

**Переавторизация и управление токенами**

| Документ | Описание |
|----------|----------|
| **[reauth/REAUTH_README.md](reauth/REAUTH_README.md)** | Быстрое решение проблем с токенами |
| **[reauth/REAUTH_USER_GUIDE.md](reauth/REAUTH_USER_GUIDE.md)** | Полное руководство пользователя |
| **[reauth/REAUTH_CHANGELOG_RPA_AUTH.md](reauth/REAUTH_CHANGELOG_RPA_AUTH.md)** | Changelog ветки rpa-auth |
| **[reauth/BUTTON_CLICK_SEQUENCE.md](reauth/BUTTON_CLICK_SEQUENCE.md)** | Последовательность кликов для авторизации |
| **[reauth/REAUTH_BRANCH_SUMMARY.md](reauth/REAUTH_BRANCH_SUMMARY.md)** | Сводка изменений в ветке reauth |

**Безопасность**

| Документ | Описание |
|----------|----------|
| **[../SECURITY.md](../SECURITY.md)** | Политика безопасности |
| **[TESTING_TOKEN_REVOCATION.md](TESTING_TOKEN_REVOCATION.md)** | Тестирование отзыва токенов |
| **[TOKEN_FIX_SUMMARY.md](TOKEN_FIX_SUMMARY.md)** | Сводка исправлений токенов |

---

### 📊 Отчеты и Мониторинг

**Telegram Daily Reports**

| Документ | Описание |
|----------|----------|
| **[../TELEGRAM_DAILY_REPORT.md](../TELEGRAM_DAILY_REPORT.md)** | Главная страница ежедневных отчетов |
| **[reports/QUICK_START.md](reports/QUICK_START.md)** | Быстрый старт с отчетами |
| **[reports/COMPLETE_GUIDE.md](reports/COMPLETE_GUIDE.md)** | Полное руководство по отчетам |
| **[reports/TECHNICAL_SUMMARY.md](reports/TECHNICAL_SUMMARY.md)** | Техническая документация |
| **[reports/IMPLEMENTATION.md](reports/IMPLEMENTATION.md)** | Детали реализации |
| **[reports/BROADCAST_SETUP.md](reports/BROADCAST_SETUP.md)** | Настройка broadcast в Telegram |
| **[reports/FILE_ORGANIZATION.md](reports/FILE_ORGANIZATION.md)** | Организация файлов отчетов |
| **[reports/INACTIVE_CHANNELS.md](reports/INACTIVE_CHANNELS.md)** | Работа с неактивными каналами |

---

### 🚀 Установка и Настройка

**Быстрый старт**

| Документ | Описание |
|----------|----------|
| **[setup/QUICK_START.md](setup/QUICK_START.md)** | Быстрая установка за 5 минут |
| **[setup/PLATFORM_SETUP_GUIDE.md](setup/PLATFORM_SETUP_GUIDE.md)** | Настройка всех платформ |
| **[setup/GOOGLE_CLOUD_CONSOLE_SETUP.md](setup/GOOGLE_CLOUD_CONSOLE_SETUP.md)** | Google Cloud Console с нуля |

**База данных**

| Документ | Описание |
|----------|----------|
| **[setup/MYSQL_SETUP_GUIDE.md](setup/MYSQL_SETUP_GUIDE.md)** | Настройка MySQL |
| **[DOCKER_MYSQL_SETUP.md](DOCKER_MYSQL_SETUP.md)** | Docker + MySQL |
| **[technical/MYSQL_MIGRATION.md](technical/MYSQL_MIGRATION.md)** | Миграция MySQL |

**Развертывание**

| Документ | Описание |
|----------|----------|
| **[SERVER_DEPLOYMENT_CHECKLIST.md](SERVER_DEPLOYMENT_CHECKLIST.md)** | Чеклист развертывания на сервере |

---

### 👥 Управление аккаунтами

| Документ | Описание |
|----------|----------|
| **[guides/CHANNEL_MANAGEMENT.md](guides/CHANNEL_MANAGEMENT.md)** | Управление каналами |
| **[guides/MULTIPLE_ACCOUNTS.md](guides/MULTIPLE_ACCOUNTS.md)** | Работа с множественными аккаунтами |

---

### 🔧 Техническая документация

| Документ | Описание |
|----------|----------|
| **[technical/TECHNICAL_DOCS.md](technical/TECHNICAL_DOCS.md)** | Техническая информация и API |
| **[technical/MYSQL_MIGRATION.md](technical/MYSQL_MIGRATION.md)** | Миграция MySQL |
| **[../PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md)** | Структура проекта |

---

### 🐛 Troubleshooting

**Решение проблем**

| Документ | Описание |
|----------|----------|
| **[youtube/04-TROUBLESHOOTING.md](youtube/04-TROUBLESHOOTING.md)** | Решение проблем YouTube |
| **[troubleshooting/MAIN_LOOP_PROTECTION.md](troubleshooting/MAIN_LOOP_PROTECTION.md)** | Защита главного цикла |
| **[troubleshooting/MEMORY_CORRUPTION_FIX.md](troubleshooting/MEMORY_CORRUPTION_FIX.md)** | Исправление коррупции памяти |
| **[troubleshooting/SSH_TUNNEL_VNC_FIX.md](troubleshooting/SSH_TUNNEL_VNC_FIX.md)** | Исправление SSH туннеля VNC |
| **[troubleshooting/WORKER_STOP_ISSUE.md](troubleshooting/WORKER_STOP_ISSUE.md)** | Проблемы с остановкой Worker |

---

## 🎯 Быстрые команды

### Voice Changer
```bash
python3 run_voice_changer.py --help
python3 run_voice_changer.py input.mp4 output.mp4 --method silero --voice-model kseniya
```

### Task Management
```bash
python3 run_task_manager.py create --account "Channel" --video "video.mp4" --title "Title"
python3 run_task_manager.py list --status pending
python3 run_task_manager.py stats
```

### YouTube Management
```bash
python3 run_youtube_manager.py list
python3 run_youtube_manager.py check-tokens
python3 run_youtube_manager.py add "ChannelName" --channel-id "UC..."
```

### OAuth Re-authentication
```bash
python3 reauth_multiple_channels.py audiokniga-one    # Один канал
python3 reauth_multiple_channels.py --expired          # Все истекшие
python3 check_token_limit.py                          # Диагностика лимитов
```

### Daily Reports
```bash
python3 run_daily_report.py              # Отправить вчерашний отчет
python3 run_daily_report.py test         # Тестовый отчет
python3 scripts/daily_report_scheduler.py # Автопланировщик (12:00 ежедневно)
```

### Database Setup
```bash
python3 run_setup_database.py
```

---

## 📁 Структура документации

```
docs/
├── setup/              # Установка и настройка
├── guides/             # Руководства пользователя
├── voice/              # Voice Processing System
├── youtube/            # YouTube интеграция
├── reauth/             # OAuth и переавторизация
├── reports/            # Отчеты и мониторинг
├── technical/         # Техническая документация
└── troubleshooting/   # Решение проблем
```

---

## 🔍 Поиск по темам

### Начало работы
- Новый пользователь → [setup/QUICK_START.md](setup/QUICK_START.md)
- Настройка YouTube → [youtube/01-SETUP.md](youtube/01-SETUP.md)
- Настройка MySQL → [setup/MYSQL_SETUP_GUIDE.md](setup/MYSQL_SETUP_GUIDE.md)

### Основные функции
- Изменение голоса → [voice/VOICE_CHANGER.md](voice/VOICE_CHANGER.md)
- Управление задачами → [guides/TASK_MANAGEMENT.md](guides/TASK_MANAGEMENT.md)
- Публикация на YouTube → [youtube/02-CLI-GUIDE.md](youtube/02-CLI-GUIDE.md)

### Проблемы
- Ошибки токенов → [reauth/REAUTH_README.md](reauth/REAUTH_README.md)
- Проблемы YouTube → [youtube/04-TROUBLESHOOTING.md](youtube/04-TROUBLESHOOTING.md)
- Проблемы Worker → [troubleshooting/WORKER_STOP_ISSUE.md](troubleshooting/WORKER_STOP_ISSUE.md)

### Продвинутые темы
- Архитектура → [youtube/03-ARCHITECTURE.md](youtube/03-ARCHITECTURE.md)
- Параллельная обработка → [voice/PARALLEL_VOICE_PROCESSING.md](voice/PARALLEL_VOICE_PROCESSING.md)
- Техническая документация → [technical/TECHNICAL_DOCS.md](technical/TECHNICAL_DOCS.md)

---

## 📞 Поддержка

- **Документация**: Этот файл и [README.md](../README.md)
- **Безопасность**: [SECURITY.md](../SECURITY.md)
- **Telegram**: [@mykytatishkin](https://t.me/mykytatishkin)

---

**Начните с [setup/QUICK_START.md](setup/QUICK_START.md) или [README.md](../README.md)!**
