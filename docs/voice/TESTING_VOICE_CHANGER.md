# Тестування Voice Changer 🧪

## Швидка перевірка

### Крок 1: Встановіть залежності

```bash
pip install -r requirements.txt
```

Це встановить:
- `pydub` - обробка аудіо
- `praat-parselmouth` - трансформація голосу
- `soundfile` - читання/запис аудіо
- `numpy` - математичні операції
- `librosa` - аналіз аудіо
- `moviepy` - обробка відео

### Крок 2: Встановіть FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

### Крок 3: Запустіть тестовий скрипт

```bash
# Базова перевірка (без обробки файлів)
python test_voice_changer.py

# Повна перевірка з тестовим файлом
python test_voice_changer.py /path/to/test/video.mp4
```

## Що перевіряє тестовий скрипт

1. ✅ **Залежності** - чи встановлені всі необхідні пакети
2. ✅ **FFmpeg** - чи встановлений FFmpeg
3. ✅ **Імпорт** - чи можна імпортувати VoiceChanger
4. ✅ **Ініціалізація** - чи можна створити екземпляр VoiceChanger
5. ✅ **Пресети** - чи доступні готові пресети
6. ✅ **Інтеграція** - чи інтегровано з системою задач
7. ✅ **Обробка файлу** - чи працює обробка реальних файлів (якщо передано тестовий файл)

## Ручне тестування

### Тест 1: Перевірка CLI

```bash
# Показати доступні пресети
python run_voice_changer.py --list-presets

# Показати довідку
python run_voice_changer.py --help
```

Очікуваний результат: список пресетів та опції команди.

### Тест 2: Конвертація аудіо файлу

Створіть простий тестовий аудіо файл або використайте існуючий:

```bash
python run_voice_changer.py test_audio.wav output_audio.wav --type male_to_female
```

Очікуваний результат:
- Файл `output_audio.wav` створений
- Голос змінений з чоловічого на жіночий
- Немає помилок

### Тест 3: Конвертація відео файлу

```bash
python run_voice_changer.py test_video.mp4 output_video.mp4 --type male_to_female
```

Очікуваний результат:
- Файл `output_video.mp4` створений
- Відео залишилось таким самим
- Аудіодоріжка змінена

### Тест 4: Пакетна обробка

```bash
# Створіть папку з тестовими файлами
mkdir test_videos
# Додайте туди відео/аудіо файли

# Запустіть пакетну обробку
python run_voice_changer.py --batch test_videos/ output_videos/ --type male_to_female
```

Очікуваний результат:
- Всі файли оброблені
- Показана статистика (скільки успішно, скільки з помилками)

### Тест 5: Програмне використання

Створіть тестовий скрипт `test_api.py`:

```python
from core.utils.voice_changer import change_voice

result = change_voice(
    input_file='test.mp4',
    output_file='output.mp4',
    conversion_type='male_to_female'
)

print(f"Success: {result['success']}")
print(f"Output: {result['output_file']}")
```

Запустіть:
```bash
python test_api.py
```

### Тест 6: Інтеграція з системою задач

```python
from core.database.mysql_db import YouTubeMySQLDatabase
from datetime import datetime
import json

db = YouTubeMySQLDatabase()

# Створіть задачу
task_id = db.add_task(
    account_id=0,
    media_type='voice_change',
    title='Тестова зміна голосу',
    description='Конвертація чоловічого голосу на жіночий',
    att_file_path='/path/to/test/video.mp4',
    scheduled_time=datetime.now(),
    add_info=json.dumps({
        'conversion_type': 'male_to_female'
    })
)

print(f"Задача створена: ID = {task_id}")

# Запустіть воркера
# python run_task_worker.py

# Перевірте статус
task = db.get_task_by_id(task_id)
print(f"Статус: {task.status}")
```

## Очікувані результати

### ✅ Успішне тестування

```
🎙️  Voice Changer Test Suite
============================================================
Checking Dependencies
============================================================
✅ pydub               - Audio processing
✅ parselmouth        - Voice transformation (Praat)
✅ soundfile          - Audio I/O
✅ numpy              - Numerical operations
✅ librosa            - Audio analysis
✅ moviepy            - Video processing

✅ All dependencies installed!

============================================================
Checking FFmpeg
============================================================
✅ FFmpeg installed: ffmpeg version X.X.X

============================================================
Test Summary
============================================================
Dependencies         ✅ PASSED
FFmpeg              ✅ PASSED
Import              ✅ PASSED
Initialization      ✅ PASSED
Presets             ✅ PASSED
Task Integration    ✅ PASSED
File Processing     ✅ PASSED
============================================================
Total: 7 | Passed: 7 | Failed: 0 | Skipped: 0
============================================================

🎉 All tests passed! Voice Changer is ready to use!
```

## Можливі проблеми та рішення

### ❌ FFmpeg not found

**Проблема:**
```
❌ FFmpeg not found
```

**Рішення:**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Перевірка
ffmpeg -version
```

### ❌ Missing dependencies

**Проблема:**
```
❌ parselmouth - Voice transformation (MISSING)
```

**Рішення:**
```bash
pip install praat-parselmouth
# або
pip install -r requirements.txt
```

### ❌ Import error

**Проблема:**
```
ImportError: No module named 'parselmouth'
```

**Рішення:**
```bash
# Перевстановіть залежності
pip uninstall praat-parselmouth
pip install praat-parselmouth

# Або встановіть всі залежності заново
pip install -r requirements.txt --force-reinstall
```

### ❌ Processing error

**Проблема:**
```
Error during voice conversion: ...
```

**Можливі причини:**
1. Невірний формат файлу
2. Пошкоджений файл
3. Недостатньо пам'яті
4. Недостатньо місця на диску

**Рішення:**
1. Перевірте формат файлу (має бути MP4, WAV, MP3 тощо)
2. Спробуйте інший файл
3. Закрийте інші програми
4. Звільніть місце на диску

## Приклади тестових файлів

### Створення тестового аудіо (за допомогою FFmpeg)

```bash
# Створити 5-секундний тестовий тон
ffmpeg -f lavfi -i "sine=frequency=440:duration=5" test_tone.wav

# Конвертувати існуюче відео у WAV
ffmpeg -i video.mp4 -vn -acodec pcm_s16le test_audio.wav
```

### Використання існуючого відео

Використайте будь-яке відео з `data/content/videos/`:
```bash
python run_voice_changer.py data/content/videos/your_video.mp4 output.mp4 --type male_to_female
```

## Benchmark тестування

Виміряйте продуктивність:

```python
import time
from core.utils.voice_changer import VoiceChanger

changer = VoiceChanger()

start_time = time.time()

result = changer.process_file(
    input_file='test.mp4',
    output_file='output.mp4',
    conversion_type='male_to_female',
    preserve_quality=True
)

elapsed_time = time.time() - start_time

print(f"Duration: {result.get('duration', 0)}s")
print(f"Processing time: {elapsed_time:.2f}s")
print(f"Speed ratio: {result.get('duration', 0) / elapsed_time:.2f}x")
```

## Наступні кроки

Після успішного тестування:

1. ✅ Використайте CLI для обробки реальних файлів
2. ✅ Інтегруйте в автоматичні робочі процеси
3. ✅ Створюйте задачі через систему задач
4. ✅ Налаштуйте власні параметри pitch/formant

## Документація

Повна документація: [Voice Changer Guide](docs/guides/VOICE_CHANGER_GUIDE.md)  
Швидкий старт: [Quick Start Guide](VOICE_CHANGER_QUICK_START.md)

---

**Успішного тестування! 🚀**
