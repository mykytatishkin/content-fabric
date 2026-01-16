# 📁 Новая структура проекта Content Fabric

## 🎯 Цель реорганизации:
- Четкое разделение по функциональности
- Удобная навигация
- Логическая группировка файлов
- Простота поддержки

## 📂 Предлагаемая структура:

```
content-fabric/
├── 📁 app/                          # Основное приложение
│   ├── __init__.py
│   ├── main.py                      # Главный файл приложения
│   ├── auto_poster.py               # Автоматический постер
│   └── scheduler.py                 # Планировщик задач
│
├── 📁 core/                         # Ядро системы
│   ├── __init__.py
│   ├── database/                    # База данных
│   │   ├── __init__.py
│   │   ├── mysql_db.py              # MySQL драйвер
│   │   └── base.py                  # Базовый класс
│   ├── api_clients/                 # API клиенты
│   │   ├── __init__.py
│   │   ├── base_client.py
│   │   ├── youtube_client.py
│   │   ├── instagram_client.py
│   │   └── tiktok_client.py
│   ├── auth/                        # Аутентификация
│   │   ├── __init__.py
│   │   ├── oauth_manager.py
│   │   └── token_manager.py
│   └── utils/                       # Утилиты
│       ├── __init__.py
│       ├── config_loader.py
│       ├── content_processor.py
│       ├── logger.py
│       └── notifications.py
│
├── 📁 scripts/                      # Скрипты и утилиты
│   ├── __init__.py
│   ├── account_manager.py           # Управление аккаунтами
│   ├── youtube_manager.py           # Управление YouTube
│   ├── database_migration.py        # Миграция БД
│   ├── setup_database.py            # Настройка БД
│   └── test_integration.py          # Тестирование
│
├── 📁 config/                       # Конфигурация
│   ├── config.yaml                  # Основная конфигурация
│   ├── mysql_config.yaml            # MySQL конфигурация
│   ├── mysql_schema.sql             # SQL схема
│   └── env_template.txt             # Шаблон переменных
│
├── 📁 docker/                        # Docker файлы
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── mysql.env
│
├── 📁 docs/                         # Документация
│   ├── setup/                       # Настройка
│   │   ├── MYSQL_SETUP_GUIDE.md
│   │   ├── PLATFORM_SETUP_GUIDE.md
│   │   └── QUICK_START.md
│   ├── guides/                       # Руководства
│   │   ├── CHANNEL_MANAGEMENT.md
│   │   ├── MULTIPLE_ACCOUNTS.md
│   │   └── YOUTUBE_SETUP.md
│   └── technical/                   # Техническая документация
│       ├── TECHNICAL_DOCS.md
│       └── MYSQL_MIGRATION.md
│
├── 📁 data/                         # Данные
│   ├── content/                     # Контент
│   ├── logs/                        # Логи
│   ├── tokens/                      # Токены (legacy)
│   └── databases/                   # Базы данных
│       └── (MySQL database)
│       └── backups/                 # Бэкапы
│
├── 📁 tests/                        # Тесты
│   ├── __init__.py
│   ├── test_database.py
│   ├── test_api_clients.py
│   └── test_integration.py
│
├── 📄 requirements.txt              # Зависимости
├── 📄 README.md                     # Основной README
└── 📄 .env                          # Переменные окружения
```

## 🎯 Преимущества новой структуры:

1. **Четкое разделение** - каждый компонент в своей папке
2. **Логическая группировка** - связанные файлы вместе
3. **Удобная навигация** - легко найти нужный файл
4. **Масштабируемость** - легко добавлять новые компоненты
5. **Чистота** - нет файлов в корне проекта
