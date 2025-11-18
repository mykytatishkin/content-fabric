# video_tool

A cross-platform C++17 CLI for configurable video processing built on FFmpeg and OpenCV.

## English

### Features
- Batch or single-file processing with operations: subtitle translation, subtitle removal, watermark removal, voiceover replacement.
- JSON job configs with CLI overrides.
- Pluggable subtitle translation and TTS clients (stubs included).

### Build
```bash
cmake -S . -B build
cmake --build build
```

Dependencies: FFmpeg (avformat/avcodec/avfilter/avutil/swscale), OpenCV, CLI11, nlohmann::json, libcurl, optional spdlog.

Build options:
- `-DVIDEO_TOOL_BUILD_TOOLS=OFF` — build only lightweight components (useful when FFmpeg/OpenCV are unavailable).
- `-DVIDEO_TOOL_BUILD_TESTS=OFF` — skip test targets.

### Usage
```bash
./video_tool \
  --input ./input_videos \
  --output ./output_videos \
  --type watermark_remove \
  --config ./configs/watermark_sora.json
```

Run via job config:
```bash
./video_tool --config ./configs/examples/job_example.json
```

### Testing
Integration tests validate the config-to-job wiring and payload preparation without requiring FFmpeg/OpenCV runtime dependencies.
```bash
cmake -S . -B build -DVIDEO_TOOL_BUILD_TOOLS=OFF  # optional if dependencies are missing
cmake --build build
ctest --test-dir build
```

### Structure
- `src/main.cpp` – entry point.
- `src/cli` – argument parsing.
- `src/core` – jobs, context, pipeline engine.
- `src/operations` – video operations implementations.
- `src/adapters` – FFmpeg/OpenCV/TTS helpers.
- `src/utils` – logging/time utilities.
- `configs` – sample configurations.

### Notes
Current adapters are minimally implemented for scaffolding; integrate full FFmpeg/codec pipelines and networked TTS for production use.

## Русский

### Возможности
- Обработка одиночных файлов и пакетов: перевод субтитров, удаление субтитров, устранение водяных знаков, замена озвучки.
- Конфигурация задач в JSON с перекрытием параметров из CLI.
- Подключаемые переводчик субтитров и TTS-клиент (реализованы заглушки).

### Сборка
```bash
cmake -S . -B build
cmake --build build
```

Зависимости: FFmpeg (avformat/avcodec/avfilter/avutil/swscale), OpenCV, CLI11, nlohmann::json, libcurl, опционально spdlog.

Опции сборки:
- `-DVIDEO_TOOL_BUILD_TOOLS=OFF` — собирать только легковесные компоненты (полезно, если недоступны FFmpeg/OpenCV).
- `-DVIDEO_TOOL_BUILD_TESTS=OFF` — пропустить цели тестов.

### Использование
```bash
./video_tool \
  --input ./input_videos \
  --output ./output_videos \
  --type watermark_remove \
  --config ./configs/watermark_sora.json
```

Запуск по конфигу задачи:
```bash
./video_tool --config ./configs/examples/job_example.json
```

### Тестирование
Интеграционные тесты проверяют связку конфига с построением задач и подготовкой полезной нагрузки без необходимости FFmpeg/OpenCV во время выполнения.
```bash
cmake -S . -B build -DVIDEO_TOOL_BUILD_TOOLS=OFF  # опционально, если нет зависимостей
cmake --build build
ctest --test-dir build
```

### Структура
- `src/main.cpp` – точка входа.
- `src/cli` – разбор аргументов.
- `src/core` – задачи, контекст, движок конвейера.
- `src/operations` – реализации операций.
- `src/adapters` – вспомогательные модули FFmpeg/OpenCV/TTS.
- `src/utils` – утилиты логирования и времени.
- `configs` – примеры конфигов.

### Примечания
Текущие адаптеры минимальны и служат каркасом; для боевого использования необходимо подключить полноценную обработку FFmpeg/кодеков и сетевой TTS.
