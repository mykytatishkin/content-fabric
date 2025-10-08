# RVC Voice Changer - AI-based зміна голосу 🎙️

**Повна трансформація голосу** використовуючи AI-based WORLD vocoder.  
Результат: голос звучить як зовсім інша людина!

## ⚡ Що нового

- ✅ **RVC + WORLD vocoder** замість Praat
- ✅ **Драматична зміна голосу** - як інша людина
- ✅ **AI-based обробка** для реалістичного результату
- ✅ 5 пресетів + нові опції

## 🚀 Швидкий старт

```bash
# 1. Встановити залежності (один раз)
pip3 install torch torchaudio soundfile librosa scipy pyworld torchcrepe
brew install ffmpeg  # macOS

# 2. Конвертувати голос (повна трансформація!)
python3 run_voice_changer.py input.mp4 output.mp4 --type male_to_female

# 3. Або екстремальна зміна
python3 run_voice_changer.py input.mp4 output.mp4 --type dramatic_change
```

## 📋 Доступні пресети

- `male_to_female` - Чоловічий → Жіночий
- `female_to_male` - Жіночий → Чоловічий  
- `male_to_child` - Чоловічий → Дитячий
- `female_to_child` - Жіночий → Дитячий

## 📚 Документація

- **Швидкий старт**: [docs/VOICE_CHANGER_QUICK_START.md](VOICE_CHANGER_QUICK_START.md)
- **Повний гід**: [docs/guides/VOICE_CHANGER_GUIDE.md](guides/VOICE_CHANGER_GUIDE.md)
- **Тестування**: [docs/TESTING_VOICE_CHANGER.md](TESTING_VOICE_CHANGER.md)
- **Підсумок**: [docs/VOICE_CHANGER_SUMMARY.md](VOICE_CHANGER_SUMMARY.md)

## 🧪 Тестування

```bash
# Базова перевірка
python3 tests/test_voice_changer.py

# Тест з файлом
python3 tests/test_voice_changer.py /path/to/video.mp4
```

## 💡 Приклади використання

Див. [examples/voice_changer_example.py](../examples/voice_changer_example.py)

```bash
# Запустити приклади
python3 examples/voice_changer_example.py
```

## 🎯 Основні можливості

- ✅ Підтримка відео: MP4, AVI, MOV, MKV, WebM, FLV
- ✅ Підтримка аудіо: WAV, MP3, M4A, OGG, FLAC
- ✅ Висока якість обробки (Praat)
- ✅ Пакетна обробка
- ✅ CLI та програмний API
- ✅ Інтеграція з task system

## 📖 CLI команди

```bash
# Список пресетів
python3 run_voice_changer.py --list-presets

# Базова конвертація
python3 run_voice_changer.py input.mp4 output.mp4 --type male_to_female

# Власні параметри
python3 run_voice_changer.py input.mp4 output.mp4 --pitch 4.0 --formant 1.3

# Пакетна обробка
python3 run_voice_changer.py --batch videos/ output/ --type male_to_female
```

## 🔧 API

```python
from core.utils.voice_changer import change_voice

result = change_voice(
    input_file='video.mp4',
    output_file='output.mp4',
    conversion_type='male_to_female'
)
```

## 📂 Структура файлів

```
content-fabric/
├── core/utils/
│   └── voice_changer.py          # Основний модуль
├── run_voice_changer.py           # CLI інструмент
├── tests/
│   └── test_voice_changer.py     # Тести
├── examples/
│   └── voice_changer_example.py  # Приклади
└── docs/
    ├── VOICE_CHANGER.md          # Цей файл
    ├── VOICE_CHANGER_QUICK_START.md
    ├── VOICE_CHANGER_SUMMARY.md
    ├── TESTING_VOICE_CHANGER.md
    └── guides/
        ├── VOICE_CHANGER_GUIDE.md
        └── VOICE_CHANGER_README.md
```

---

**Статус: ✅ Готово до використання**
