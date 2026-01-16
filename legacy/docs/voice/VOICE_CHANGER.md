# 🎙️ Voice Changer - Полное руководство

## ✨ Возможности

1. **Замена голоса** (русский TTS с Silero)
2. **Text-to-Speech** - синтез речи из текста ⭐ NEW!
3. **Сохранение фона** (музыка/эффекты остаются) ⭐
4. **Автоматические паузы** (из оригинала)
5. **6 русских голосов** (3 женских, 3 мужских)
6. **🎯 Правильное ударение** (нормативное/орфоэпическое) ⭐

---

## 🚀 Быстрый старт

### 1. Установка

```bash
pip3 install -r requirements.txt
```

### 2. Простая замена голоса

```bash
python3 run_voice_changer.py \
  --method silero \
  --voice-model kseniya \
  --no-preserve-quality \
  /полный/путь/к/input.mp3 \
  /полный/путь/к/output.mp3
```

### 3. Text-to-Speech: синтез текста в голос ⭐ NEW!

```bash
python3 run_voice_changer.py output.wav \
  --text "Привет! Это тест синтеза речи." \
  --voice-model kseniya
```

### 4. С сохранением музыки ⭐

```bash
python3 run_voice_changer.py \
  --method silero \
  --voice-model kseniya \
  --no-preserve-quality \
  --preserve-background \
  /полный/путь/к/music_video.mp4 \
  /полный/путь/к/output.mp4
```

---

## 🎤 Доступные голоса

```bash
python3 run_voice_changer.py --list-silero-voices
```

| Голос | Пол | Рекомендация |
|-------|-----|--------------|
| `kseniya` | Женский | ⭐ Лучший |
| `baya` | Женский | Хорошо |
| `xenia` | Женский | Вариант |
| `eugene` | Мужской | ⭐ Лучший |
| `aidar` | Мужской | Хорошо |

---

## 📝 Основные параметры

### Text-to-Speech режим

| Параметр | Описание | Пример |
|----------|----------|--------|
| `--text TEXT` | Текст для синтеза | Обязательно |
| `--voice-model NAME` | Выбор голоса | `kseniya`, `eugene` |
| `--no-stress` | Без ударений (быстрее) | Опционально |

### Voice Conversion режим

| Параметр | Описание | Пример |
|----------|----------|--------|
| `--method silero` | Использовать Silero TTS | Обязательно |
| `--voice-model NAME` | Выбор голоса | `kseniya`, `eugene` |
| `--no-preserve-quality` | Быстрее (без prosody) | Рекомендуется |
| `--preserve-background` | Сохранить фон/музыку | Опционально |
| `--separation-model` | Модель разделения | `UVR_MDXNET_KARA_2` |

---

## ⏱️ Время обработки

| Длительность | Без фона | С фоном |
|--------------|----------|---------|
| 3 минуты | ~5-7 мин | ~15-20 мин |
| 5 минут | ~8-12 мин | ~25-30 мин |

---

## ⚠️ Важно

1. **Используйте ПОЛНЫЕ АБСОЛЮТНЫЕ ПУТИ** к файлам
2. **Добавляйте `--no-preserve-quality`** для скорости
3. **Первый запуск дольше** (загрузка моделей)

---

## 📖 Дополнительно

- **Text-to-Speech Guide:** [TEXT_TO_SPEECH.md](TEXT_TO_SPEECH.md) ⭐ NEW!
- **Background Preservation:** [BACKGROUND_PRESERVATION_GUIDE.md](BACKGROUND_PRESERVATION_GUIDE.md)
- **🎯 Правильное ударение:** [RUSSIAN_STRESS_GUIDE.md](RUSSIAN_STRESS_GUIDE.md)
- **Производительность:** [PARALLEL_VOICE_PROCESSING.md](PARALLEL_VOICE_PROCESSING.md)
- **Requirements:** `../../requirements.txt`
- **Примеры:** `../../examples/voice_changer_example.py`
- **Примеры TTS:** `../../examples/text_to_speech_example.py` ⭐ NEW!
- **Примеры ударений:** `../../examples/russian_stress_example.py`

## 🔧 Использование в коде

```python
from core.voice import VoiceChanger

# Инициализация
changer = VoiceChanger()

# Text-to-Speech
result = changer.process_text(
    text="Привет! Это тест синтеза речи.",
    output_file="output.wav",
    voice="kseniya",
    add_stress=True
)

# Voice Conversion
result = changer.process_file(
    input_file="input.mp3",
    output_file="output.mp3",
    method="silero",
    voice_model="kseniya",
    preserve_background=True
)
```

---

## 💡 Примеры команд

### Text-to-Speech (синтез из текста):

```bash
# Простой синтез
python3 run_voice_changer.py output.wav \
  --text "Привет! Это тест синтеза речи." \
  --voice-model kseniya

# Без ударений (быстрее)
python3 run_voice_changer.py output.wav \
  --text "Длинный текст для синтеза..." \
  --voice-model eugene \
  --no-stress
```

### Для видео с музыкой:

```bash
python3 run_voice_changer.py \
  --method silero \
  --voice-model kseniya \
  --no-preserve-quality \
  --preserve-background \
  --separation-model UVR_MDXNET_KARA_2 \
  /Users/user/video.mp4 \
  /Users/user/output.mp4
```

### Для подкаста:

```bash
python3 run_voice_changer.py \
  --method silero \
  --voice-model eugene \
  --no-preserve-quality \
  --preserve-background \
  --vocals-gain 2 \
  --background-gain -5 \
  /Users/user/podcast.mp3 \
  /Users/user/output.mp3
```

---

## ✅ Checklist

- [ ] Python 3.8+
- [ ] Установлены зависимости: `pip3 install -r requirements.txt`
- [ ] Используются **ПОЛНЫЕ ПУТИ** к файлам
- [ ] Добавлен `--method silero`
- [ ] Добавлен `--no-preserve-quality`

---

**Готово к работе! 🎉**

