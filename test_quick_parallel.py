#!/usr/bin/env python3
"""
Быстрый тест параллельной обработки
"""

import os
import time
from pathlib import Path
from core.utils.voice_changer import VoiceChanger

def main():
    print("=" * 80)
    print("🚀 ТЕСТ ПАРАЛЛЕЛЬНОЙ ОБРАБОТКИ ГОЛОСА")
    print("=" * 80)
    
    # Пути
    input_file = "data/content/audio/input.mp3"
    output_dir = "data/content/processed/parallel_test"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Проверка входного файла
    if not os.path.exists(input_file):
        print(f"❌ Файл не найден: {input_file}")
        return
    
    file_size = os.path.getsize(input_file) / (1024 * 1024)  # MB
    print(f"\n📁 Входной файл: {input_file}")
    print(f"   Размер: {file_size:.2f} MB")
    
    # Тест 1: Последовательная обработка (baseline)
    print("\n" + "=" * 80)
    print("📊 ТЕСТ 1: Последовательная обработка (baseline)")
    print("=" * 80)
    
    output_sequential = os.path.join(output_dir, "output_sequential.wav")
    
    changer_seq = VoiceChanger(enable_parallel=False)
    
    start = time.time()
    result_seq = changer_seq.process_file(
        input_file=input_file,
        output_file=output_sequential,
        method='silero',
        voice_model='kseniya',
        preserve_quality=False  # Быстрее для теста
    )
    time_seq = time.time() - start
    changer_seq.cleanup()
    
    print(f"\n✅ Последовательная обработка завершена")
    print(f"   Время: {time_seq:.2f} секунд")
    print(f"   Выход: {output_sequential}")
    
    # Тест 2: Параллельная обработка
    print("\n" + "=" * 80)
    print("📊 ТЕСТ 2: Параллельная обработка")
    print("=" * 80)
    
    output_parallel = os.path.join(output_dir, "output_parallel.wav")
    
    changer_par = VoiceChanger(
        enable_parallel=True,
        chunk_duration_minutes=3,  # 3-минутные фрагменты для теста
        max_workers=4
    )
    
    start = time.time()
    result_par = changer_par.process_file(
        input_file=input_file,
        output_file=output_parallel,
        method='silero',
        voice_model='kseniya',
        preserve_quality=False,
        use_parallel=True  # Принудительно
    )
    time_par = time.time() - start
    changer_par.cleanup()
    
    print(f"\n✅ Параллельная обработка завершена")
    print(f"   Время: {time_par:.2f} секунд")
    print(f"   Выход: {output_parallel}")
    
    # Результаты
    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ")
    print("=" * 80)
    
    speedup = time_seq / time_par if time_par > 0 else 0
    
    print(f"\n⏱️  Последовательная: {time_seq:.2f}s")
    print(f"⚡ Параллельная:     {time_par:.2f}s")
    print(f"🚀 Ускорение:        {speedup:.2f}x")
    
    if speedup > 1.5:
        print("\n✅ Отлично! Параллельная обработка работает эффективно!")
    elif speedup > 1.0:
        print("\n✅ Хорошо! Есть ускорение, но можно улучшить (попробуйте меньше фрагменты)")
    else:
        print("\n⚠️  Параллельная обработка не дала ускорения (возможно, файл слишком короткий)")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()

