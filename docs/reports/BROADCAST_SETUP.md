# 📡 Telegram Auto-Broadcast Setup

Автоматична розсилка щоденних звітів о **12:00 за київським часом**.

## 🎯 Як працює

1. **Користувач натискає /start** у боті → автоматично додається до розсилки
2. **Щодня о 12:00 (Київ)** → всі отримують звіт за вчора
3. **Автосинхронізація** → нові користувачі додаються перед кожною розсилкою

## 📋 Що потрібно

### 1. Telegram Bot Token
```bash
# У .env файлі:
TELEGRAM_BOT_TOKEN=your_bot_token
```

**Як створити бота:**
1. Знайдіть [@BotFather](https://t.me/BotFather) в Telegram
2. Відправте `/newbot`
3. Вкажіть ім'я та username бота
4. Скопіюйте токен → додайте в `.env`

### 2. Користувачі натискають /start
- Кожен хто натисне `/start` автоматично додається в список
- Видаляти вручну не потрібно - все автоматично

## 🚀 Швидкий старт

### 1. Перевірка що бот працює
```bash
# Натисніть /start у вашому боті, потім:
python3 manage_subscribers.py sync
python3 manage_subscribers.py list
```

### 2. Тестова розсилка
```bash
python3 manage_subscribers.py test
```

### 3. Запуск автоматичного scheduler
```bash
python3 scripts/daily_report_scheduler.py
```

## ⏰ Налаштування часового поясу

Scheduler працює за **київським часом (Europe/Kiev)**.

### Якщо ваша система в іншому timezone:

**Варіант 1: Встановити TZ змінну**
```bash
export TZ=Europe/Kiev
python3 scripts/daily_report_scheduler.py
```

**Варіант 2: Налаштувати в cron**
```bash
crontab -e
# Додати:
TZ=Europe/Kiev
0 12 * * * cd /path/to/content-fabric && python3 run_daily_report.py
```

**Варіант 3: Docker з timezone**
```dockerfile
ENV TZ=Europe/Kiev
```

## 🔧 Управління підписниками

```bash
# Показати всіх користувачів
python3 manage_subscribers.py list

# Синхронізувати нових (хто натиснув /start)
python3 manage_subscribers.py sync

# Тестове повідомлення
python3 manage_subscribers.py test
```

## 🤖 Автозапуск (Production)

### macOS (launchd)

Створіть файл: `~/Library/LaunchAgents/com.contentfabric.dailyreport.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.contentfabric.dailyreport</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/path/to/content-fabric/scripts/daily_report_scheduler.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>TZ</key>
        <string>Europe/Kiev</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/daily_report.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/daily_report.error.log</string>
</dict>
</plist>
```

Завантажити:
```bash
launchctl load ~/Library/LaunchAgents/com.contentfabric.dailyreport.plist
```

### Linux (systemd)

Створіть файл: `/etc/systemd/system/daily-report.service`

```ini
[Unit]
Description=Daily Telegram Report Scheduler
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/content-fabric
Environment="TZ=Europe/Kiev"
ExecStart=/usr/bin/python3 /path/to/content-fabric/scripts/daily_report_scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запустити:
```bash
sudo systemctl enable daily-report
sudo systemctl start daily-report
sudo systemctl status daily-report
```

### Cron (простіший варіант)

```bash
crontab -e

# Додати:
TZ=Europe/Kiev
0 12 * * * cd /path/to/content-fabric && /usr/bin/python3 run_daily_report.py >> /tmp/daily_report.log 2>&1
```

## 📊 Моніторинг

### Перевірити логи
```bash
tail -f data/logs/daily_report.log
tail -f data/logs/daily_report_scheduler.log
```

### Перевірити статус scheduler
```bash
ps aux | grep daily_report_scheduler
```

### Перевірити кількість підписників
```bash
python3 manage_subscribers.py list
```

## 🔍 Troubleshooting

### Звіти не приходять?
1. Перевірте що scheduler запущений
2. Перевірте логи
3. Перевірте що є підписники: `python3 manage_subscribers.py list`
4. Перевірте час: `python3 -c "from datetime import datetime; import pytz; print(datetime.now(pytz.timezone('Europe/Kiev')))"`

### Неправильний час відправки?
1. Перевірте системний timezone: `date`
2. Встановіть TZ=Europe/Kiev в scheduler
3. Перевірте що pytz встановлений: `pip3 install pytz`

### Користувачі не додаються?
1. Перевірте що вони натиснули /start
2. Запустіть sync: `python3 manage_subscribers.py sync`
3. Перевірте TELEGRAM_BOT_TOKEN в .env

## 📈 Статистика

Файл з підписниками: `data/telegram_subscribers.json`

```json
{
  "subscribers": [
    876386326,
    123456789,
    ...
  ]
}
```

---

**Версія:** 1.0  
**Часовий пояс:** Europe/Kiev (Київ, UTC+2/UTC+3)  
**Час розсилки:** 12:00 щодня

