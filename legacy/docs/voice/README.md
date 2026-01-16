# 🎙️ Voice Processing Documentation

Полная документация по модулям голосовой обработки.

## 📚 Документация

### Основные руководства

- **[VOICE_CHANGER.md](VOICE_CHANGER.md)** - Основное руководство по смене голоса
- **[TEXT_TO_SPEECH.md](TEXT_TO_SPEECH.md)** - Синтез речи из текста
- **[VOICE_REFACTORING.md](VOICE_REFACTORING.md)** - История рефакторинга модулей

### Функциональность

- **[BACKGROUND_PRESERVATION_GUIDE.md](BACKGROUND_PRESERVATION_GUIDE.md)** - Сохранение фоновой музыки
- **[RUSSIAN_STRESS_GUIDE.md](RUSSIAN_STRESS_GUIDE.md)** - Русские ударения (основной гайд)
- **[RUSSIAN_STRESS_README.md](RUSSIAN_STRESS_README.md)** - Русские ударения (детальный)
- **[STRESS_ACCURACY_GUIDE.md](STRESS_ACCURACY_GUIDE.md)** - Точность ударений
- **[STRESS_FEATURE_SUMMARY.md](STRESS_FEATURE_SUMMARY.md)** - Резюме функции ударений

### Производительность

- **[PARALLEL_VOICE_PROCESSING.md](PARALLEL_VOICE_PROCESSING.md)** - Параллельная обработка
- **[PARALLEL_PROCESSING_README.md](PARALLEL_PROCESSING_README.md)** - Параллельная обработка (основы)
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Итоги реализации
- **[MULTIPROCESSING_FIX.md](MULTIPROCESSING_FIX.md)** - Исправление многопроцессорности
- **[PERFORMANCE_FIX_README.md](PERFORMANCE_FIX_README.md)** - Оптимизация производительности
- **[SPEED_OPTIMIZATION.md](SPEED_OPTIMIZATION.md)** - Оптимизация скорости

## 🚀 Быстрый старт

### Text-to-Speech

```bash
python run_voice_changer.py output.wav \
  --text "Привет! Это тест синтеза речи." \
  --voice-model kseniya
```

### Voice Conversion

```bash
python run_voice_changer.py input.mp3 output.mp3 \
  --method silero \
  --voice-model kseniya \
  --preserve-background
```

## 📖 Использование в коде

```python
from core.voice import VoiceChanger

changer = VoiceChanger()

# Text-to-Speech
result = changer.process_text(
    text="Привет!",
    output_file="output.wav",
    voice="kseniya"
)

# Voice Conversion
result = changer.process_file(
    input_file="input.mp3",
    output_file="output.mp3",
    method="silero",
    voice_model="kseniya"
)
```

## 🎤 Доступные голоса

- `kseniya` - Женский (⭐ Лучший)
- `baya` - Женский
- `eugene` - Мужской (⭐ Лучший)
- `aidar` - Мужской

## 📁 Структура модулей

```
core/voice/
├── voice_changer.py    # Главный модуль
├── silero.py           # Silero TTS
├── parallel.py         # Параллельная обработка
├── prosody.py          # Прозодия
├── stress.py           # Ударения
├── mixer.py            # Фоновое микширование
└── rvc/                # RVC компоненты
    ├── inference.py
    ├── model_manager.py
    └── sovits.py
```

## 📖 Дополнительные ресурсы

- **Примеры:** `examples/text_to_speech_example.py`
- **Тесты:** `tests/test_voice_changer.py`
- **CLI:** `run_voice_changer.py`

