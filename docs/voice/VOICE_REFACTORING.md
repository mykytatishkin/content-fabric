# 🔄 Voice Module Refactoring

## Обзор

Проведен рефакторинг модулей голосовой обработки для улучшения организации кода и упрощения поддержки.

## 📁 Новая структура

```
core/voice/                    # Голосовая обработка
├── __init__.py               # Экспорт всех классов
├── voice_changer.py          # Главный модуль
├── silero.py                 # Silero TTS
├── parallel.py               # Параллельная обработка
├── prosody.py                # Прозодия
├── stress.py                 # Ударения
├── mixer.py                  # Фоновое микширование
├── stress_dictionaries.py    # Словари ударений
└── rvc/                      # RVC компоненты
    ├── __init__.py
    ├── inference.py          # RVC inference
    ├── model_manager.py      # Менеджер моделей
    └── sovits.py             # So-VITS конвертер
```

## 🔄 Изменения

### Переименования файлов

| Старое имя | Новое имя |
|------------|-----------|
| `silero_voice_changer.py` | `silero.py` |
| `audio_background_mixer.py` | `mixer.py` |
| `parallel_voice_processor.py` | `parallel.py` |
| `prosody_transfer.py` | `prosody.py` |
| `russian_stress.py` | `stress.py` |
| `rvc_inference.py` | `rvc/inference.py` |
| `rvc_model_manager.py` | `rvc/model_manager.py` |
| `sovits_converter.py` | `rvc/sovits.py` |

### Обновление импортов

#### Было:
```python
from core.utils.voice_changer import VoiceChanger
from core.utils.silero_voice_changer import SileroVoiceChanger
from core.utils.rvc_inference import RVCInference
```

#### Стало:
```python
from core.voice import VoiceChanger, SileroVoiceChanger
from core.voice.rvc import RVCInference
```

## ✨ Преимущества

1. **Логическая группировка** - все модули голоса в одной папке
2. **Короткие импорты** - удобнее использовать
3. **Чистая структура** - RVC компоненты в подпапке
4. **Упрощение поддержки** - проще найти нужный модуль

## 📝 Обновленные файлы

- `run_voice_changer.py` - CLI инструмент
- `app/task_worker.py` - обработчик задач
- `examples/text_to_speech_example.py` - примеры TTS
- `examples/voice_changer_example.py` - примеры voice conversion
- `tests/test_voice_changer.py` - тесты
- `VOICE_CHANGER.md` - документация

## 🧪 Тестирование

После рефакторинга все тесты пройдены успешно:

```bash
# Text-to-Speech
python run_voice_changer.py output.wav --text "Тест" --voice-model kseniya

# Voice Conversion
python run_voice_changer.py input.mp3 output.mp3 --method silero --voice-model kseniya
```

## 📖 Документация

- **Основная документация:** `VOICE_CHANGER.md`
- **Text-to-Speech:** `docs/TEXT_TO_SPEECH.md`
- **Примеры:** `examples/text_to_speech_example.py`

## ⚠️ Миграция

Если вы используете старые импорты, обновите их:

```python
# Старый код
from core.utils.voice_changer import VoiceChanger

# Новый код
from core.voice import VoiceChanger
```

## 🗑️ Удаленные файлы

Старые файлы из `core/utils/` были удалены:
- `voice_changer.py`
- `silero_voice_changer.py`
- `parallel_voice_processor.py`
- `prosody_transfer.py`
- `russian_stress.py`
- `stress_dictionaries.py`
- `audio_background_mixer.py`
- `rvc_inference.py`
- `rvc_model_manager.py`
- `sovits_converter.py`
- `voice_changer_old.py`
- `voice_changer_rvc.py`

## ✅ Готово!

Рефакторинг завершен. Все модули голосовой обработки теперь в `core/voice/`.

