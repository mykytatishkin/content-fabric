# 🎙️ CLI Инструмент для параллельной обработки голоса

## 📋 Использование из консоли

### Базовые команды

```bash
# Простейшая команда (автоматически выберет параллельную обработку для длинных файлов)
python run_parallel_voice.py input.mp3 output.mp3

# С конкретным голосом
python run_parallel_voice.py input.mp3 output.mp3 --voice kseniya

# Принудительная параллельная обработка
python run_parallel_voice.py input.mp3 output.mp3 --parallel

# Без параллельной обработки (классический режим)
python run_parallel_voice.py input.mp3 output.mp3 --no-parallel
```

### С сохранением фоновой музыки

```bash
# Сохранить фоновую музыку
python run_parallel_voice.py audio_with_music.mp3 output.mp3 --preserve-background

# С настройкой громкости
python run_parallel_voice.py audio_with_music.mp3 output.mp3 \
  --preserve-background \
  --vocals-gain 2.0 \
  --background-gain -5.0
```

### Настройка параллелизма

```bash
# Фрагменты по 3 минуты, 8 потоков
python run_parallel_voice.py long_audio.mp3 output.mp3 \
  --parallel \
  --chunks 3 \
  --workers 8

# Фрагменты по 10 минут, 2 потока (для экономии памяти)
python run_parallel_voice.py huge_file.mp3 output.mp3 \
  --parallel \
  --chunks 10 \
  --workers 2
```

### Разные голоса

```bash
# Мужской голос Айдар
python run_parallel_voice.py input.mp3 output.mp3 --voice aidar

# Женский голос Ксения
python run_parallel_voice.py input.mp3 output.mp3 --voice kseniya

# Женский голос Бая
python run_parallel_voice.py input.mp3 output.mp3 --voice baya

# Мужской голос Евгений
python run_parallel_voice.py input.mp3 output.mp3 --voice eugene
```

### Качество

```bash
# Быстрая обработка (без prosody)
python run_parallel_voice.py input.mp3 output.mp3 --quality fast

# Нормальное качество (по умолчанию)
python run_parallel_voice.py input.mp3 output.mp3 --quality normal

# Высокое качество (с prosody)
python run_parallel_voice.py input.mp3 output.mp3 --quality high
```

## 📚 Полная справка

### Посмотреть все параметры

```bash
python run_parallel_voice.py --help
```

### Параметры

| Параметр | Короткая форма | Описание | По умолчанию |
|----------|---------------|----------|--------------|
| `--voice` | `-v` | Голос для озвучки | `kseniya` |
| `--method` | `-m` | Метод обработки | `silero` |
| `--parallel` | `-p` | Включить параллельную обработку | авто |
| `--no-parallel` | - | Отключить параллельную обработку | - |
| `--chunks` | - | Длительность фрагментов (мин) | `5` |
| `--workers` | - | Количество потоков | авто |
| `--preserve-background` | `-b` | Сохранить фоновую музыку | `False` |
| `--vocals-gain` | - | Громкость вокала (dB) | `0.0` |
| `--background-gain` | - | Громкость фона (dB) | `-3.0` |
| `--quality` | - | Качество (fast/normal/high) | `normal` |
| `--quiet` | `-q` | Тихий режим | `False` |

### Доступные голоса (Silero)

- `aidar` - мужской голос
- `kseniya` - женский голос (по умолчанию)
- `baya` - женский голос
- `eugene` - мужской голос
- `xenia` - женский голос (вариант)

## 💡 Практические примеры

### Пример 1: Обработка подкаста

```bash
python run_parallel_voice.py \
  data/podcasts/episode_01.mp3 \
  data/output/episode_01_female.mp3 \
  --voice kseniya \
  --parallel \
  --chunks 5
```

### Пример 2: Аудиокнига с музыкой

```bash
python run_parallel_voice.py \
  audiobook.mp3 \
  audiobook_new_voice.mp3 \
  --voice aidar \
  --preserve-background \
  --vocals-gain 1.5 \
  --background-gain -4.0 \
  --parallel
```

### Пример 3: Быстрая обработка короткого файла

```bash
python run_parallel_voice.py \
  short_clip.mp3 \
  output.mp3 \
  --voice kseniya \
  --quality fast \
  --no-parallel
```

### Пример 4: Длинный файл с максимальным параллелизмом

```bash
python run_parallel_voice.py \
  long_video.mp3 \
  output.mp3 \
  --voice kseniya \
  --parallel \
  --chunks 3 \
  --workers 8 \
  --quality normal
```

### Пример 5: Batch обработка

```bash
# Обработать все файлы в директории
for file in data/audio/*.mp3; do
    output="data/output/$(basename "$file" .mp3)_processed.mp3"
    python run_parallel_voice.py "$file" "$output" --voice kseniya --parallel
done
```

## 📊 Рекомендации

### Выбор размера фрагментов

| Длительность файла | Рекомендуемый --chunks | Рекомендуемый --workers |
|-------------------|----------------------|------------------------|
| < 3 минут | - (без параллелизма) | - |
| 3-10 минут | 5 | 4 |
| 10-30 минут | 5 | 6-8 |
| 30-60 минут | 3 | 8 |
| > 60 минут | 2-3 | 8-16 |

### Выбор качества

- `fast` - для быстрого тестирования
- `normal` - для большинства случаев
- `high` - для финальной продакшн версии

### Работа с фоном

Если в аудио есть музыка или звуковые эффекты:
```bash
--preserve-background --vocals-gain 2.0 --background-gain -4.0
```

## 🚀 Быстрый старт

### 1. Простейшая обработка

```bash
python run_parallel_voice.py input.mp3 output.mp3
```

### 2. С вашими файлами

```bash
python run_parallel_voice.py \
  /path/to/your/audio.mp3 \
  /path/to/output.mp3 \
  --voice kseniya \
  --parallel
```

### 3. Проверка результата

```bash
# Результат будет в указанном файле
ls -lh /path/to/output.mp3
```

## 🔧 Troubleshooting

### Ошибка: "Файл не найден"

Проверьте путь:
```bash
ls -la input.mp3
```

### Медленная обработка

Увеличьте параллелизм:
```bash
--chunks 3 --workers 8
```

### Ошибки памяти

Уменьшите параллелизм:
```bash
--chunks 10 --workers 2
```

### Плохое качество

Используйте:
```bash
--quality high --preserve-background
```

## 📝 Примеры с реальными путями

```bash
# Обработать файл из data/content/audio
python run_parallel_voice.py \
  data/content/audio/input.mp3 \
  data/content/processed/output.mp3 \
  --voice kseniya \
  --parallel

# С сохранением фона
python run_parallel_voice.py \
  data/content/audio/podcast_with_music.mp3 \
  data/content/processed/podcast_new_voice.mp3 \
  --voice aidar \
  --preserve-background \
  --parallel

# Тихий режим (только результат)
python run_parallel_voice.py \
  input.mp3 \
  output.mp3 \
  --quiet
```

---

**Теперь можно просто запускать из консоли без изменения кода! 🎉**

