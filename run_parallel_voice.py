#!/usr/bin/env python3
"""
CLI инструмент для параллельной обработки голоса
Использование:
    python run_parallel_voice.py input.mp3 output.mp3
    python run_parallel_voice.py input.mp3 output.mp3 --voice kseniya --parallel
    python run_parallel_voice.py input.mp3 output.mp3 --preserve-background
"""

import argparse
import sys
import os
from pathlib import Path
from core.utils.voice_changer import VoiceChanger

def main():
    parser = argparse.ArgumentParser(
        description='🎙️ Параллельная обработка голоса',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Базовое использование
  python run_parallel_voice.py input.mp3 output.mp3
  
  # С конкретным голосом
  python run_parallel_voice.py input.mp3 output.mp3 --voice kseniya
  
  # Параллельная обработка (авто для > 3 мин)
  python run_parallel_voice.py input.mp3 output.mp3 --parallel
  
  # С сохранением фоновой музыки
  python run_parallel_voice.py input.mp3 output.mp3 --preserve-background
  
  # Настройка параллелизма
  python run_parallel_voice.py input.mp3 output.mp3 --parallel --chunks 3 --workers 8
  
  # Без параллельной обработки
  python run_parallel_voice.py input.mp3 output.mp3 --no-parallel

Доступные голоса (Silero):
  aidar    - мужской голос
  kseniya  - женский голос (по умолчанию)
  baya     - женский голос
  eugene   - мужской голос
        """
    )
    
    # Обязательные аргументы
    parser.add_argument('input', help='Входной аудио/видео файл')
    parser.add_argument('output', help='Выходной файл')
    
    # Голос
    parser.add_argument(
        '--voice', '-v',
        default='kseniya',
        choices=['aidar', 'kseniya', 'baya', 'eugene', 'xenia'],
        help='Голос для озвучки (по умолчанию: kseniya)'
    )
    
    # Метод
    parser.add_argument(
        '--method', '-m',
        default='silero',
        choices=['silero', 'sovits', 'rvc'],
        help='Метод обработки (по умолчанию: silero)'
    )
    
    # Параллельная обработка
    parallel_group = parser.add_mutually_exclusive_group()
    parallel_group.add_argument(
        '--parallel', '-p',
        action='store_true',
        help='Включить параллельную обработку (авто для файлов > 3 мин)'
    )
    parallel_group.add_argument(
        '--no-parallel',
        action='store_true',
        help='Отключить параллельную обработку'
    )
    
    # Параметры параллелизма
    parser.add_argument(
        '--chunks',
        type=int,
        default=5,
        help='Длительность фрагментов в минутах (по умолчанию: 5)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='Количество параллельных потоков (по умолчанию: авто)'
    )
    
    # Фоновая музыка
    parser.add_argument(
        '--preserve-background', '-b',
        action='store_true',
        help='Сохранить фоновую музыку'
    )
    
    parser.add_argument(
        '--vocals-gain',
        type=float,
        default=0.0,
        help='Громкость вокала в dB (по умолчанию: 0.0)'
    )
    
    parser.add_argument(
        '--background-gain',
        type=float,
        default=-3.0,
        help='Громкость фона в dB (по умолчанию: -3.0)'
    )
    
    # Качество
    parser.add_argument(
        '--quality',
        choices=['fast', 'normal', 'high'],
        default='normal',
        help='Качество обработки (по умолчанию: normal)'
    )
    
    # Тихий режим
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Тихий режим (меньше логов)'
    )
    
    args = parser.parse_args()
    
    # Проверка входного файла
    if not os.path.exists(args.input):
        print(f"❌ Ошибка: Файл не найден: {args.input}")
        sys.exit(1)
    
    # Создать директорию для выходного файла
    output_dir = os.path.dirname(args.output)
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Вывод информации
    if not args.quiet:
        print("=" * 80)
        print("🎙️  ПАРАЛЛЕЛЬНАЯ ОБРАБОТКА ГОЛОСА")
        print("=" * 80)
        print(f"\n📁 Вход:  {args.input}")
        print(f"📁 Выход: {args.output}")
        print(f"🎤 Голос: {args.voice}")
        print(f"⚙️  Метод: {args.method}")
        
        if args.preserve_background:
            print(f"🎵 Фоновая музыка: Да (вокал: {args.vocals_gain:+.1f}dB, фон: {args.background_gain:+.1f}dB)")
        
        file_size = os.path.getsize(args.input) / (1024 * 1024)
        print(f"📊 Размер: {file_size:.2f} MB")
    
    # Определить режим параллельной обработки
    enable_parallel = not args.no_parallel
    use_parallel = None  # Авто режим
    
    if args.parallel:
        use_parallel = True
    elif args.no_parallel:
        use_parallel = False
    
    # Качество
    preserve_quality = args.quality == 'high'
    
    # Создать voice changer
    try:
        if not args.quiet:
            print(f"\n🔧 Инициализация...")
            if enable_parallel:
                print(f"   Параллельная обработка: Вкл (фрагменты: {args.chunks} мин, потоки: {args.workers or 'авто'})")
            else:
                print(f"   Параллельная обработка: Выкл")
        
        changer = VoiceChanger(
            enable_parallel=enable_parallel,
            chunk_duration_minutes=args.chunks,
            max_workers=args.workers
        )
        
        # Обработка
        if not args.quiet:
            print(f"\n⚡ Начинаю обработку...")
        
        result = changer.process_file(
            input_file=args.input,
            output_file=args.output,
            method=args.method,
            voice_model=args.voice,
            preserve_quality=preserve_quality,
            preserve_background=args.preserve_background,
            use_parallel=use_parallel,
            vocals_gain=args.vocals_gain,
            background_gain=args.background_gain
        )
        
        # Очистка
        changer.cleanup()
        
        # Результат
        if result.get('success', False):
            if not args.quiet:
                print("\n" + "=" * 80)
                print("✅ ГОТОВО!")
                print("=" * 80)
                print(f"\n📁 Результат: {result['output_file']}")
                print(f"⚙️  Метод: {result.get('method', 'Unknown')}")
                
                if os.path.exists(result['output_file']):
                    output_size = os.path.getsize(result['output_file']) / (1024 * 1024)
                    print(f"📊 Размер: {output_size:.2f} MB")
            else:
                print(f"✅ {result['output_file']}")
            
            sys.exit(0)
        else:
            print(f"\n❌ Ошибка обработки")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

