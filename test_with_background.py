#!/usr/bin/env python3
"""
Тест с сохранением фоновой музыки
"""

from core.utils.voice_changer import VoiceChanger

print("🎵 Тест с сохранением фоновой музыки")
print("=" * 60)

changer = VoiceChanger(
    enable_parallel=True,
    chunk_duration_minutes=5
)

result = changer.process_file(
    input_file='data/content/audio/input.mp3',
    output_file='data/content/processed/output_with_background.wav',
    method='silero',
    voice_model='kseniya',
    preserve_background=True,  # ← Главное!
    vocals_gain=2.0,          # Увеличить громкость вокала
    background_gain=-3.0      # Уменьшить громкость фона
)

changer.cleanup()

print(f"\n✅ Готово!")
print(f"   Выход: {result['output_file']}")
print(f"   Фоновая музыка сохранена!")

