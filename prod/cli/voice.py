"""CLI entry point for parallel voice processing.

Uses VoiceChanger with Silero/RVC/So-VITS-SVC for AI-based voice conversion
with optional parallel processing and background music preservation.

Usage:
    python -m cli.voice input.mp3 output.mp3
    python -m cli.voice input.mp3 output.mp3 --voice kseniya --parallel
    python -m cli.voice input.mp3 output.mp3 --preserve-background
    python -m cli.voice input.mp3 output.mp3 --parallel --chunks 3 --workers 8
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from shared.voice.voice_changer import VoiceChanger


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Параллельная обработка голоса",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python -m cli.voice input.mp3 output.mp3
  python -m cli.voice input.mp3 output.mp3 --voice kseniya
  python -m cli.voice input.mp3 output.mp3 --parallel
  python -m cli.voice input.mp3 output.mp3 --preserve-background
  python -m cli.voice input.mp3 output.mp3 --parallel --chunks 3 --workers 8
  python -m cli.voice input.mp3 output.mp3 --no-parallel

Доступные голоса (Silero):
  aidar    - мужской голос
  kseniya  - женский голос (по умолчанию)
  baya     - женский голос
  eugene   - мужской голос
        """,
    )

    # Required arguments
    parser.add_argument("input", help="Входной аудио/видео файл")
    parser.add_argument("output", help="Выходной файл")

    # Voice
    parser.add_argument(
        "--voice", "-v",
        default="kseniya",
        choices=["aidar", "kseniya", "baya", "eugene", "xenia"],
        help="Голос для озвучки (по умолчанию: kseniya)",
    )

    # Method
    parser.add_argument(
        "--method", "-m",
        default="silero",
        choices=["silero", "sovits", "rvc"],
        help="Метод обработки (по умолчанию: silero)",
    )

    # Parallel processing
    parallel_group = parser.add_mutually_exclusive_group()
    parallel_group.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Включить параллельную обработку (авто для файлов > 3 мин)",
    )
    parallel_group.add_argument(
        "--no-parallel",
        action="store_true",
        help="Отключить параллельную обработку",
    )

    # Parallel params
    parser.add_argument(
        "--chunks",
        type=int,
        default=5,
        help="Длительность фрагментов в минутах (по умолчанию: 5)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Количество параллельных потоков (по умолчанию: авто)",
    )

    # Background music
    parser.add_argument(
        "--preserve-background", "-b",
        action="store_true",
        help="Сохранить фоновую музыку",
    )
    parser.add_argument(
        "--vocals-gain",
        type=float,
        default=0.0,
        help="Громкость вокала в dB (по умолчанию: 0.0)",
    )
    parser.add_argument(
        "--background-gain",
        type=float,
        default=-3.0,
        help="Громкость фона в dB (по умолчанию: -3.0)",
    )

    # Quality
    parser.add_argument(
        "--quality",
        choices=["fast", "normal", "high"],
        default="normal",
        help="Качество обработки (по умолчанию: normal)",
    )

    # Device
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda", "auto"],
        default="auto",
        help="Устройство для обработки (по умолчанию: auto)",
    )

    # Quiet mode
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Тихий режим (меньше логов)",
    )

    args = parser.parse_args()

    # Validate input file
    if not os.path.exists(args.input):
        print(f"Ошибка: Файл не найден: {args.input}")
        sys.exit(1)

    # Create output directory
    output_dir = os.path.dirname(args.output)
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Print info
    if not args.quiet:
        print("=" * 80)
        print("ПАРАЛЛЕЛЬНАЯ ОБРАБОТКА ГОЛОСА")
        print("=" * 80)
        print(f"\nВход:  {args.input}")
        print(f"Выход: {args.output}")
        print(f"Голос: {args.voice}")
        print(f"Метод: {args.method}")

        if args.preserve_background:
            print(
                f"Фоновая музыка: Да "
                f"(вокал: {args.vocals_gain:+.1f}dB, фон: {args.background_gain:+.1f}dB)"
            )

        file_size = os.path.getsize(args.input) / (1024 * 1024)
        print(f"Размер: {file_size:.2f} MB")

    # Determine parallel mode
    enable_parallel = not args.no_parallel
    use_parallel = None  # auto
    if args.parallel:
        use_parallel = True
    elif args.no_parallel:
        use_parallel = False

    # Quality
    preserve_quality = args.quality == "high"

    try:
        if not args.quiet:
            print(f"\nИнициализация...")
            if enable_parallel:
                print(
                    f"   Параллельная обработка: Вкл "
                    f"(фрагменты: {args.chunks} мин, потоки: {args.workers or 'авто'})"
                )
            else:
                print("   Параллельная обработка: Выкл")

        # Determine device
        device = None if args.device == "auto" else args.device

        changer = VoiceChanger(
            enable_parallel=enable_parallel,
            chunk_duration_minutes=args.chunks,
            max_workers=args.workers,
            device=device,
        )

        if not args.quiet:
            print("\nНачинаю обработку...")

        result = changer.process_file(
            input_file=args.input,
            output_file=args.output,
            method=args.method,
            voice_model=args.voice,
            preserve_quality=preserve_quality,
            preserve_background=args.preserve_background,
            use_parallel=use_parallel,
            vocals_gain=args.vocals_gain,
            background_gain=args.background_gain,
        )

        changer.cleanup()

        if result.get("success", False):
            if not args.quiet:
                print("\n" + "=" * 80)
                print("ГОТОВО!")
                print("=" * 80)
                print(f"\nРезультат: {result['output_file']}")
                print(f"Метод: {result.get('method', 'Unknown')}")

                if os.path.exists(result["output_file"]):
                    output_size = os.path.getsize(result["output_file"]) / (1024 * 1024)
                    print(f"Размер: {output_size:.2f} MB")
            else:
                print(result["output_file"])

            sys.exit(0)
        else:
            print("Ошибка обработки")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\nОшибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
