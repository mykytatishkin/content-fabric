# Daily Telegram Report System

Автоматична система щоденних звітів про виконання завдань через Telegram.

## 📋 Огляд

Система відправляє щоденні звіти о **12:00** з підсумком виконання завдань за вчора. Звіти групуються по платформах (YouTube, Instagram, VK) для зручності.

## 🎯 Формат звіту

### Структура повідомлення

Кожна платформа отримує окреме повідомлення:

```
📊 **Daily Report - YOUTUBE**
📅 Date: 2024-01-15
━━━━━━━━━━━━━━━━━━━━

#5 @audiokniga-one - (0) 5/5
#12 @another-channel - (1) 4/5
#18 @third-channel - (2) 3/5

━━━━━━━━━━━━━━━━━━━━
**Summary:**
✅ Completed: 12/15
❌ Failed: 3
📈 Success Rate: 80.0%
```

### Пояснення формату

- **#5** - ID першого завдання для аккаунта (з таблиці tasks)
- **@audiokniga-one** - Channel ID з посиланням на канал (клікабельне)
- **(0)** - Кількість помилок (failed tasks)
- **5/5** - Виконано/Заплановано

## 🚀 Використання

### 1. Ручний запуск

Відправити звіт за вчора:
```bash
python run_daily_report.py
```

Тестовий звіт:
```bash
python run_daily_report.py test
```

### 2. Автоматичний запуск (Scheduler)

Запустити планувальник для щоденних звітів о 12:00:
```bash
python scripts/daily_report_scheduler.py
```

Планувальник працює постійно і автоматично відправляє звіти щодня.

### 3. Cron Job (Linux/Mac)

Додати до crontab:
```bash
# Щоденний звіт о 12:00
0 12 * * * cd /path/to/content-fabric && python run_daily_report.py
```

Редагувати crontab:
```bash
crontab -e
```

## ⚙️ Налаштування

### Telegram конфігурація

Переконайтесь що в `.env` файлі є:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

В `config/config.yaml` повинно бути:
```yaml
notifications:
  telegram:
    enabled: true
    send_success: true
    send_failure: true
```

### Перевірка налаштувань

Протестувати Telegram підключення:
```python
from core.utils.notifications import NotificationManager

notifier = NotificationManager()
results = notifier.test_notifications()
print(results)
```

## 📊 Статуси завдань

- **0 (Pending)** - Очікує виконання
- **1 (Completed)** - Виконано успішно ✅
- **2 (Failed)** - Помилка ❌
- **3 (Processing)** - В процесі

Звіт враховує:
- **Scheduled** = Всі tasks за вчора для аккаунта
- **Completed** = Tasks зі статусом 1
- **Failed** = Tasks зі статусом 2

## 🔗 Формат посилань

### YouTube
- Формат: `@channel-handle`
- Посилання: `https://youtube.com/@channel-handle`

### Instagram (майбутнє)
- Формат: `@username`
- Посилання: `https://instagram.com/username`

### VK (майбутнє)
- Формат: `@username`
- Посилання: `https://vk.com/username`

## 📝 Приклади

### Приклад 1: Успішний день
```
📊 **Daily Report - YOUTUBE**
📅 Date: 2024-01-15
━━━━━━━━━━━━━━━━━━━━

#45 @audiokniga-one - (0) 10/10
#56 @stories-channel - (0) 5/5

━━━━━━━━━━━━━━━━━━━━
**Summary:**
✅ Completed: 15/15
❌ Failed: 0
📈 Success Rate: 100.0%
```

### Приклад 2: З помилками
```
📊 **Daily Report - YOUTUBE**
📅 Date: 2024-01-15
━━━━━━━━━━━━━━━━━━━━

#45 @audiokniga-one - (2) 8/10
#56 @stories-channel - (1) 4/5

━━━━━━━━━━━━━━━━━━━━
**Summary:**
✅ Completed: 12/15
❌ Failed: 3
📈 Success Rate: 80.0%
```

## 🛠️ Технічна інформація

### Файли системи

- **`core/utils/daily_report.py`** - Основна логіка звітів
- **`run_daily_report.py`** - Скрипт ручного запуску
- **`scripts/daily_report_scheduler.py`** - Автоматичний планувальник

### База даних

Система використовує таблицю `tasks` з MySQL:
```sql
SELECT * FROM tasks 
WHERE date_post >= 'YYYY-MM-DD 00:00:00' 
  AND date_post <= 'YYYY-MM-DD 23:59:59'
```

### Логи

Логи зберігаються в:
- `data/logs/daily_report.log`
- `data/logs/daily_report_scheduler.log`

## 🐛 Troubleshooting

### Звіти не приходять

1. Перевірте Telegram credentials:
```bash
python -c "from core.utils.notifications import NotificationManager; nm = NotificationManager(); print(nm.get_notification_status())"
```

2. Перевірте наявність завдань:
```bash
python -c "from core.utils.daily_report import DailyReportManager; drm = DailyReportManager(); print(drm._get_tasks_for_date(datetime.now() - timedelta(days=1)))"
```

3. Перевірте логи:
```bash
tail -f data/logs/daily_report.log
```

### Scheduler не працює

1. Перевірте чи процес запущений:
```bash
ps aux | grep daily_report_scheduler
```

2. Запустіть в режимі debug:
```bash
python scripts/daily_report_scheduler.py
```

### Помилки в форматуванні

1. Перевірте формат channel_id в базі даних:
```sql
SELECT id, name, channel_id FROM youtube_channels;
```

2. Переконайтесь що channel_id починається з `@` або є валідним handle

## 📚 API Reference

### DailyReportManager

```python
from core.utils.daily_report import DailyReportManager
from datetime import datetime, timedelta

# Створити менеджер
manager = DailyReportManager()

# Відправити звіт за вчора
manager.generate_and_send_daily_report()

# Відправити звіт за конкретну дату
specific_date = datetime(2024, 1, 15)
manager.generate_and_send_daily_report(date=specific_date)

# Тестовий звіт
manager.send_test_report()
```

### Standalone функція

```python
from core.utils.daily_report import send_daily_report

# Проста функція для cron/scheduler
success = send_daily_report()
```

## 🔄 Workflow

1. **12:00** - Scheduler активується
2. Отримує tasks за вчора з БД
3. Групує по платформам (youtube, instagram, vk)
4. Для кожної платформи:
   - Групує по аккаунтам
   - Підраховує статистику
   - Форматує повідомлення
   - Відправляє в Telegram
5. Логує результати

## 📈 Майбутні покращення

- [ ] Підтримка Instagram та VK
- [ ] Детальні графіки в повідомленнях
- [ ] Email звіти як альтернатива
- [ ] Тижневі та місячні звіти
- [ ] Порівняння з попередніми періодами
- [ ] Автоматичне виявлення проблемних аккаунтів

## 📞 Підтримка

Якщо виникають питання або проблеми:
1. Перевірте документацію
2. Перегляньте логи
3. Запустіть тестовий звіт
4. Перевірте налаштування Telegram

---

**Версія:** 1.0  
**Остання оновлення:** 2024-01-15

