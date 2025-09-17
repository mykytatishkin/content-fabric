# 🚀 Быстрый старт - Social Media Auto-Poster

## ⚡ За 5 минут до первого теста

### 1. Установка зависимостей
```bash
cd content-fabric
pip3 install -r requirements.txt
```

### 2. Базовая настройка
```bash
# Скопируйте шаблон конфигурации
cp config.env.example .env

# Отредактируйте .env (добавьте хотя бы email для уведомлений)
nano .env
```

### 3. Добавьте тестовое видео
```bash
# Поместите ваше видео в папку
cp /path/to/your/video.mp4 content/videos/
```

### 4. Проверьте систему
```bash
# Проверка статуса
python3 main.py status

# Тестовый запуск (платформы отключены - безопасно)
python3 main.py post \
  --content content/videos/your_video.mp4 \
  --caption "Тестовый пост #test" \
  --platforms "instagram"
```

---

## 📋 Что дальше?

### Для продакшена нужно настроить:

1. **API ключи платформ** → см. [PLATFORM_SETUP_GUIDE.md](PLATFORM_SETUP_GUIDE.md)
2. **Включить платформы** → в `config.yaml` поставить `enabled: true`
3. **Настроить аккаунты** → добавить реальные токены в `config.yaml`
4. **Уведомления** → настроить Telegram/Email в `.env`

### Полезные команды:

```bash
# Проверка аккаунтов
python3 main.py validate-accounts

# Планирование постов
python3 main.py schedule --content video.mp4 --caption "Post" --platforms "instagram"

# Запуск планировщика
python3 main.py start-scheduler

# Статистика
python3 main.py stats
```

### Документация:
- **[README.md](README.md)** - общее описание
- **[TECHNICAL_DOCS.md](TECHNICAL_DOCS.md)** - техническая документация  
- **[PLATFORM_SETUP_GUIDE.md](PLATFORM_SETUP_GUIDE.md)** - настройка API платформ

---

## ⚠️ Важные моменты

- **Платформы отключены по умолчанию** для безопасности
- **Без API ключей** система работает в режиме симуляции
- **Логи** сохраняются в `logs/auto_posting.log`
- **Планировщик** нужно запускать отдельно для автоматических постов
