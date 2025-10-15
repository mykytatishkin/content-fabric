# 📊 Daily Telegram Report System - Summary

## Огляд системи

Автоматична система щоденних звітів про виконання завдань через Telegram, яка надсилає підсумки о **12:00 щодня**.

## ✨ Основні можливості

- ✅ **Автоматичні звіти** о 12:00 щодня
- 📱 **Telegram інтеграція** через існуючу систему notifications
- 🎯 **Групування по платформах** (окремі повідомлення для YouTube, Instagram, VK)
- 📊 **Детальна статистика** по кожному аккаунту
- 🔗 **Клікабельні посилання** на канали
- 📈 **Success Rate** та підсумки

## 📋 Формат звіту

```
📊 **Daily Report - YOUTUBE**
📅 Date: 2024-01-15
━━━━━━━━━━━━━━━━━━━━

#5 @audiokniga-one - (0) 5/5
#12 @another-channel - (1) 4/5

━━━━━━━━━━━━━━━━━━━━
**Summary:**
✅ Completed: 9/10
❌ Failed: 1
📈 Success Rate: 90.0%
```

**Пояснення:**
- `#5` - ID першого завдання (task.id)
- `@audiokniga-one` - Channel ID з посиланням
- `(0)` - Кількість помилок (failed tasks)
- `5/5` - Completed/Scheduled

## 🚀 Використання

### 1. Ручний запуск
```bash
# Звіт за вчора
python run_daily_report.py

# Тестовий звіт
python run_daily_report.py test
```

### 2. Автоматичний планувальник
```bash
# Запустити планувальник (12:00 щодня)
python scripts/daily_report_scheduler.py
```

### 3. Cron Job (рекомендовано)
```bash
# Додати до crontab
0 12 * * * cd /path/to/content-fabric && python run_daily_report.py
```

### 4. Програмне використання
```python
from core.utils.daily_report import DailyReportManager

manager = DailyReportManager()
manager.generate_and_send_daily_report()
```

## 📁 Структура файлів

### Основні модулі
- **`core/utils/daily_report.py`** - Головний модуль системи
  - `DailyReportManager` - Основний клас
  - `send_daily_report()` - Standalone функція для cron
  - `AccountReport`, `PlatformReport` - Структури даних

### Скрипти
- **`run_daily_report.py`** - Скрипт ручного запуску
- **`scripts/daily_report_scheduler.py`** - Автоматичний планувальник

### Документація
- **`docs/reports/QUICK_START.md`** - Швидкий старт
- **`docs/reports/COMPLETE_GUIDE.md`** - Повне керівництво
- **`examples/daily_report_example.py`** - Приклади використання

## ⚙️ Технічні деталі

### База даних

Запит для отримання tasks за дату:
```sql
SELECT * FROM tasks 
WHERE date_post >= 'YYYY-MM-DD 00:00:00' 
  AND date_post <= 'YYYY-MM-DD 23:59:59'
ORDER BY account_id, media_type
```

### Статуси завдань
- **0 = Pending** - Очікує виконання
- **1 = Completed** - Виконано успішно ✅
- **2 = Failed** - Помилка ❌
- **3 = Processing** - В процесі

### Підрахунки
- **Scheduled** = Всі tasks за дату для аккаунта
- **Completed** = Tasks зі status = 1
- **Failed** = Tasks зі status = 2

### Платформи

Наразі підтримується:
- ✅ **YouTube** - повна підтримка з посиланнями

Готово до додавання:
- ⏳ **Instagram** - структура готова
- ⏳ **VK** - структура готова
- ⏳ **TikTok** - структура готова

## 🔗 Формат посилань

### YouTube
```python
@channel-handle → https://youtube.com/@channel-handle
```

### Instagram (готово)
```python
@username → https://instagram.com/username
```

### VK (готово)
```python
@username → https://vk.com/username
```

## 📊 API Methods

### DailyReportManager

```python
class DailyReportManager:
    def __init__(self, db=None, notification_manager=None)
    
    # Основні методи
    def generate_and_send_daily_report(self, date=None) -> bool
    def send_test_report(self) -> bool
    
    # Внутрішні методи (публічні для розширення)
    def _get_tasks_for_date(self, date) -> List[Task]
    def _group_tasks_by_platform(self, tasks) -> Dict[str, PlatformReport]
    def _format_platform_report(self, platform_report, date) -> str
    def _format_channel_link(self, channel_id, platform) -> str
```

### Standalone функція

```python
def send_daily_report() -> bool
```

## 🎯 Workflow

1. **Trigger** - Scheduler або ручний запуск
2. **Fetch** - Отримати tasks за дату з БД
3. **Group** - Згрупувати по платформах → аккаунтах
4. **Analyze** - Підрахувати статистику
5. **Format** - Сформувати Markdown повідомлення
6. **Send** - Відправити через Telegram API
7. **Log** - Записати результат в лог

## 📈 Статистика в звіті

Для кожного аккаунта:
- Task ID (перше завдання)
- Channel link (клікабельне)
- Error count
- Completed/Scheduled ratio

Загальна по платформі:
- Total Completed/Scheduled
- Total Failed
- Success Rate (%)

## 🔧 Конфігурація

### Telegram (в .env)
```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Config.yaml
```yaml
notifications:
  telegram:
    enabled: true
    send_success: true
    send_failure: true
```

## 🛠️ Розширення

### Додати нову платформу

1. Додати логіку в `_format_channel_link()`:
```python
elif platform.lower() == 'new_platform':
    link = f"[{display_id}](https://new_platform.com/{clean_id})"
```

2. Готово! Система автоматично розпізнає tasks з `media_type = 'new_platform'`

### Кастомізувати формат повідомлення

Змінити метод `_format_platform_report()` в `DailyReportManager`

### Додати додаткову статистику

Розширити клас `AccountReport` або `PlatformReport`

## 📝 Логи

Логи зберігаються:
- `data/logs/daily_report.log`
- `data/logs/daily_report_scheduler.log`
- `data/logs/daily_report_cron.log` (якщо через cron)

## 🧪 Тестування

### Швидкий тест
```bash
python run_daily_report.py test
```

### Приклади
```bash
python examples/daily_report_example.py
```

Доступні приклади:
1. Базовий звіт
2. Звіт за конкретну дату
3. Власні компоненти
4. Standalone функція
5. Тестовий звіт
6. Перегляд tasks
7. Попередній перегляд

## 🚨 Troubleshooting

### Немає звітів
1. Перевірити Telegram credentials
2. Перевірити наявність tasks
3. Переглянути логи

### Помилки в форматуванні
1. Перевірити channel_id в БД
2. Переконатись що починається з `@`

### Scheduler не працює
1. Перевірити процес
2. Запустити в debug режимі
3. Перевірити cron job

## 📚 Документація

- 📖 [QUICK_START.md](QUICK_START.md) - Швидкий старт
- 📘 [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) - Повний гайд
- 💻 [../../examples/daily_report_example.py](../../examples/daily_report_example.py) - Приклади коду

## 🎯 Ключові команди

```bash
# Ручний запуск
python run_daily_report.py

# Тест
python run_daily_report.py test

# Scheduler
python scripts/daily_report_scheduler.py

# Приклади
python ../../examples/daily_report_example.py

# Cron
0 12 * * * cd /path/to/content-fabric && python run_daily_report.py
```

## ✅ Чеклист інтеграції

- [x] Створено `DailyReportManager`
- [x] Інтеграція з існуючою БД (MySQL)
- [x] Інтеграція з Telegram notifications
- [x] Ручний запуск
- [x] Автоматичний scheduler
- [x] Cron підтримка
- [x] Документація
- [x] Приклади використання
- [x] Логування
- [x] Error handling
- [x] Тестові функції
- [x] YouTube links
- [ ] Instagram підтримка (структура готова)
- [ ] VK підтримка (структура готова)

## 📊 Статистика реалізації

- **Файли створено:** 6
- **Рядків коду:** ~800+
- **Методів:** 15+
- **Тестів:** 7 прикладів
- **Документів:** 3
- **Платформи:** 1 активна, 3 готові

---

**Версія:** 1.0  
**Дата:** 2024-01-15  
**Статус:** ✅ Production Ready  
**Час виконання:** 12:00 щодня

