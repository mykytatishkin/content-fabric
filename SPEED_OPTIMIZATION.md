# ⚡ Оптимизация скорости обработки

## 🎯 Текущие оптимизации

✅ **Реализовано:**
- ProcessPoolExecutor для настоящего параллелизма
- Разделение на фрагменты
- Многопроцессорная обработка

## 🚀 Дополнительные оптимизации

### 1. GPU Ускорение (2-5x быстрее)

**Использовать CUDA если доступно:**

```python
# Автоматически использует GPU если доступен
changer = VoiceChanger(device='cuda')  # Вместо 'cpu'
```

**Проверить наличие GPU:**
```bash
python -c "import torch; print('GPU доступен:', torch.cuda.is_available())"
```

**Если GPU доступен - ускорение 2-5x!**

### 2. Отключить Prosody Transfer (2x быстрее)

Prosody transfer - медленный процесс. Для быстрой обработки:

```bash
python run_parallel_voice.py input.mp3 output.mp3 \
  --parallel \
  --quality fast  # ← Отключает prosody
```

Или из кода:
```python
result = changer.process_file(
    input_file='input.mp3',
    output_file='output.mp3',
    method='silero',
    preserve_quality=False  # ← Отключает prosody
)
```

### 3. Меньше фрагменты = больше параллелизма

Для CPU с 8+ ядрами:

```bash
python run_parallel_voice.py input.mp3 output.mp3 \
  --parallel \
  --chunks 2 \      # 2-минутные фрагменты (вместо 5)
  --workers 8       # 8 параллельных процессов
```

### 4. Использовать меньшую модель Whisper

Whisper - самый медленный компонент. Используйте меньшую модель:

**В `silero_voice_changer.py`, метод `load_models()`:**
```python
# Вместо 'medium' используйте 'base' или 'small'
self.whisper_model = whisper.load_model('small', device=self.device)
# small = 2-3x быстрее чем medium
# base = 4-5x быстрее чем medium
```

### 5. Кэширование транскрипций

Если обрабатываете один файл несколько раз:

```python
# Сохранить транскрипцию
transcription = whisper_model.transcribe(audio)
with open('transcription.json', 'w') as f:
    json.dump(transcription, f)

# Загрузить позже
with open('transcription.json', 'r') as f:
    transcription = json.load(f)
```

### 6. Пропустить stress marking

Отключить Russian stress detection (небольшое ускорение):

В `silero_voice_changer.py`:
```python
self.stress_marker = None  # Отключить
```

### 7. Batch обработка для Whisper

Для нескольких файлов - обработайте все транскрипции сразу:

```python
# Вместо:
for file in files:
    transcribe(file)

# Используйте:
transcriptions = batch_transcribe(files)  # Все сразу
```

### 8. Оптимизация I/O

Использовать RAM disk для временных файлов:

```bash
# macOS
mkdir /tmp/ramdisk
diskutil erasevolume HFS+ "ramdisk" `hdiutil attach -nomount ram://2048000`

# Использовать
python run_parallel_voice.py input.mp3 output.mp3 --temp-dir /tmp/ramdisk
```

### 9. Использовать faster-whisper

Замена Whisper на faster-whisper (2-4x быстрее):

```bash
pip install faster-whisper
```

```python
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cuda", compute_type="float16")
segments, info = model.transcribe("audio.mp3")
```

## 📊 Сравнение оптимизаций

| Оптимизация | Ускорение | Качество | Сложность |
|------------|-----------|----------|-----------|
| GPU (CUDA) | 3-5x | Без потерь | ⭐ Легко |
| Отключить prosody | 2x | -10% | ⭐ Легко |
| Меньше фрагменты | 1.2-1.5x | Без потерь | ⭐ Легко |
| Whisper small | 3x | -15% | ⭐ Легко |
| Whisper base | 5x | -25% | ⭐ Легко |
| faster-whisper | 2-4x | Без потерь | ⭐⭐ Средне |
| RAM disk | 1.1-1.3x | Без потерь | ⭐⭐⭐ Сложно |
| Кэширование | ∞ (повтор) | Без потерь | ⭐⭐ Средне |

## 🎯 Рекомендуемые комбинации

### Максимальная скорость (без GPU)
```bash
python run_parallel_voice.py input.mp3 output.mp3 \
  --parallel \
  --chunks 2 \
  --workers 8 \
  --quality fast
```

**Ожидаемое ускорение: 4-6x**

### Максимальная скорость (с GPU)
```bash
python run_parallel_voice.py input.mp3 output.mp3 \
  --parallel \
  --chunks 3 \
  --workers 4 \
  --quality fast \
  --device cuda
```

**Ожидаемое ускорение: 8-12x**

### Баланс скорость/качество
```bash
python run_parallel_voice.py input.mp3 output.mp3 \
  --parallel \
  --chunks 3 \
  --workers 6 \
  --quality normal
```

**Ожидаемое ускорение: 3-5x**

## 🔧 Быстрые модификации кода

### 1. Добавить device в CLI

Добавить в `run_parallel_voice.py`:

```python
parser.add_argument(
    '--device',
    choices=['cpu', 'cuda', 'auto'],
    default='auto',
    help='Device для обработки (cpu/cuda/auto)'
)

# В коде:
changer = VoiceChanger(
    device=args.device if args.device != 'auto' else None,
    enable_parallel=enable_parallel,
    ...
)
```

### 2. Использовать faster-whisper

В `silero_voice_changer.py`:

```python
try:
    from faster_whisper import WhisperModel
    USE_FASTER_WHISPER = True
except:
    import whisper
    USE_FASTER_WHISPER = False

def load_models(self, whisper_size: str = 'small'):
    if USE_FASTER_WHISPER:
        # 2-4x быстрее!
        self.whisper_model = WhisperModel(
            whisper_size, 
            device=self.device,
            compute_type="float16" if self.device == "cuda" else "int8"
        )
    else:
        self.whisper_model = whisper.load_model(whisper_size, device=self.device)
```

### 3. Меньшая модель Whisper по умолчанию

```python
# В silero_voice_changer.py
def load_models(self, whisper_size: str = 'small'):  # Вместо 'medium'
    ...
```

### 4. Отключить stress marking для скорости

```python
# В silero_voice_changer.py __init__
self.stress_marker = None  # Отключить совсем

# ИЛИ только для быстрого режима:
if fast_mode:
    self.stress_marker = None
```

## 📈 Ожидаемые результаты

### Текущая скорость (с оптимизациями)
- 10 минут аудио → ~90 секунд (6x ускорение)

### С GPU + все оптимизации
- 10 минут аудио → ~30 секунд (20x ускорение)

### С faster-whisper + GPU
- 10 минут аудио → ~20 секунд (30x ускорение)

## 🚀 Быстрый старт оптимизаций

1. **Проверьте GPU:**
```bash
python -c "import torch; print(torch.cuda.is_available())"
```

2. **Если GPU доступен:**
```bash
# Установите CUDA версию PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Используйте GPU
python run_parallel_voice.py input.mp3 output.mp3 --parallel --device cuda
```

3. **Если GPU нет - оптимизируйте CPU:**
```bash
python run_parallel_voice.py input.mp3 output.mp3 \
  --parallel \
  --chunks 2 \
  --workers 8 \
  --quality fast
```

4. **Установите faster-whisper:**
```bash
pip install faster-whisper

# Модифицируйте silero_voice_changer.py для использования
```

## 💡 Профилирование

Чтобы найти узкие места:

```python
import time
import cProfile

def profile_processing():
    start = time.time()
    
    # Ваш код
    changer.process_file(...)
    
    print(f"Total: {time.time() - start:.2f}s")

# Детальный профиль
cProfile.run('profile_processing()', sort='cumtime')
```

Это покажет какой компонент самый медленный.

