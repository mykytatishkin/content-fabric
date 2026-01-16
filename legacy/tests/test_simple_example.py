#!/usr/bin/env python3
"""
Простейший пример использования параллельной обработки
"""

from core.utils.voice_changer import VoiceChanger

# Создать voice changer с параллельной обработкой
changer = VoiceChanger(
    enable_parallel=True,        # Включить параллельную обработку
    chunk_duration_minutes=5,    # Фрагменты по 5 минут
    max_workers=4                # 4 потока
)

# Обработать файл
print("🎙️ Начинаю обработку...")

result = changer.process_file(
    input_file='data/content/audio/input.mp3',
    output_file='data/content/processed/output.wav',
    method='silero',
    voice_model='kseniya',
    preserve_quality=True
)

# Очистка
changer.cleanup()

print(f"✅ Готово! {result.get('output_file')}")
print(f"   Метод: {result.get('method')}")

