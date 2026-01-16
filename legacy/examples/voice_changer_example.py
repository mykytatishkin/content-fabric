#!/usr/bin/env python3
"""
Voice Changer - Example Usage
Демонстрація різних способів використання Voice Changer
"""

import sys
import os

# Add project root to path (go up one level from examples/ to project root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.voice import VoiceChanger, change_voice
from core.utils.logger import get_logger

logger = get_logger(__name__)


def example_1_simple():
    """Приклад 1: Простий спосіб - використання функції change_voice"""
    print("\n" + "="*60)
    print("Приклад 1: Проста конвертація")
    print("="*60)
    
    # Найпростіший спосіб
    result = change_voice(
        input_file='data/content/videos/your_video.mp4',
        output_file='output/converted_video.mp4',
        conversion_type='male_to_female'
    )
    
    if result['success']:
        print(f"✅ Успішно конвертовано!")
        print(f"   Вихідний файл: {result['output_file']}")
        print(f"   Тривалість: {result['duration']}s")
    else:
        print(f"❌ Помилка конвертації")


def example_2_with_class():
    """Приклад 2: Використання класу VoiceChanger з налаштуваннями"""
    print("\n" + "="*60)
    print("Приклад 2: Використання класу з налаштуваннями")
    print("="*60)
    
    # Створюємо екземпляр з власною temp директорією
    changer = VoiceChanger(temp_dir='/tmp/my_voice_processing')
    
    # Обробляємо з власними параметрами
    result = changer.process_file(
        input_file='data/content/videos/your_video.mp4',
        output_file='output/custom_voice.mp4',
        conversion_type='male_to_female',
        pitch_shift=4.0,      # Власний pitch
        formant_shift=1.25,   # Власний formant
        preserve_quality=True  # Максимальна якість
    )
    
    if result['success']:
        print(f"✅ Успішно!")
        print(f"   Pitch shift: {result['pitch_shift']} semitones")
        print(f"   Formant shift: {result['formant_shift']}x")


def example_3_batch():
    """Приклад 3: Пакетна обробка"""
    print("\n" + "="*60)
    print("Приклад 3: Пакетна обробка файлів")
    print("="*60)
    
    changer = VoiceChanger()
    
    # Список файлів для обробки
    input_files = [
        'data/content/videos/video1.mp4',
        'data/content/videos/video2.mp4',
        'data/content/videos/audio1.wav',
    ]
    
    # Пакетна обробка
    result = changer.batch_process(
        input_files=input_files,
        output_dir='output/batch/',
        conversion_type='male_to_female',
        preserve_quality=False  # Швидша обробка
    )
    
    print(f"Оброблено: {result['total']} файлів")
    print(f"Успішно: {result['successful']} ✅")
    print(f"Помилки: {result['failed']} ❌")
    
    # Показати результати
    for file_info in result['files']:
        if file_info['status'] == 'success':
            print(f"  ✅ {file_info['input']} -> {file_info['output']}")
        else:
            print(f"  ❌ {file_info['input']}: {file_info['error']}")


def example_4_presets():
    """Приклад 4: Використання різних пресетів"""
    print("\n" + "="*60)
    print("Приклад 4: Різні пресети")
    print("="*60)
    
    changer = VoiceChanger()
    
    # Показати доступні пресети
    presets = changer.get_available_presets()
    print(f"\nДоступні пресети: {len(presets)}\n")
    
    for name, preset in presets.items():
        print(f"📋 {name}")
        print(f"   {preset['description']}")
        print(f"   Pitch: {preset['pitch_shift']}, Formant: {preset['formant_shift']}")
    
    # Обробити з різними пресетами
    presets_to_try = ['male_to_female', 'female_to_male', 'male_to_child']
    
    for preset_name in presets_to_try:
        output_file = f'output/{preset_name}_output.mp4'
        
        print(f"\n🎙️  Обробка з пресетом: {preset_name}")
        
        result = changer.process_file(
            input_file='data/content/videos/your_video.mp4',
            output_file=output_file,
            conversion_type=preset_name
        )
        
        if result['success']:
            print(f"   ✅ Готово: {output_file}")


def example_5_task_integration():
    """Приклад 5: Інтеграція з системою задач"""
    print("\n" + "="*60)
    print("Приклад 5: Створення задачі зміни голосу")
    print("="*60)
    
    from core.database.mysql_db import YouTubeMySQLDatabase
    from datetime import datetime
    import json
    
    try:
        db = YouTubeMySQLDatabase()
        
        # Створити задачу зміни голосу
        task_id = db.add_task(
            account_id=0,  # Не потрібен для voice_change
            media_type='voice_change',
            title='Конвертація голосу - чоловічий на жіночий',
            description='Автоматична зміна голосу через task worker',
            att_file_path='/path/to/your/video.mp4',
            scheduled_time=datetime.now(),
            add_info=json.dumps({
                'conversion_type': 'male_to_female',
                'pitch_shift': 3.5,
                'formant_shift': 1.2
            })
        )
        
        print(f"✅ Задачу створено!")
        print(f"   Task ID: {task_id}")
        print(f"   Тип: voice_change")
        print(f"   Статус: Pending")
        print(f"\n   Запустіть task worker:")
        print(f"   python3 run_task_worker.py")
        
        # Перевірити статус (опціонально)
        task = db.get_task_by_id(task_id)
        print(f"\n   Поточний статус: {task.status}")
        
    except Exception as e:
        print(f"❌ Помилка: {str(e)}")
        print(f"   Переконайтесь що MySQL база даних налаштована")


def example_6_error_handling():
    """Приклад 6: Обробка помилок"""
    print("\n" + "="*60)
    print("Приклад 6: Обробка помилок")
    print("="*60)
    
    changer = VoiceChanger()
    
    try:
        result = changer.process_file(
            input_file='nonexistent_file.mp4',
            output_file='output.mp4',
            conversion_type='male_to_female'
        )
    except FileNotFoundError as e:
        print(f"❌ Файл не знайдено: {str(e)}")
    except Exception as e:
        print(f"❌ Помилка обробки: {str(e)}")
    
    # Перевірка існування файлу перед обробкою
    import os
    
    input_file = 'data/content/videos/your_video.mp4'
    
    if not os.path.exists(input_file):
        print(f"⚠️  Файл не існує: {input_file}")
    else:
        print(f"✅ Файл знайдено: {input_file}")
        result = changer.process_file(
            input_file=input_file,
            output_file='output/safe_output.mp4',
            conversion_type='male_to_female'
        )


def main():
    """Головна функція - запускає всі приклади"""
    print("\n🎙️  Voice Changer - Приклади використання")
    print("="*60)
    
    examples = [
        ("1", "Простий спосіб", example_1_simple),
        ("2", "З класом VoiceChanger", example_2_with_class),
        ("3", "Пакетна обробка", example_3_batch),
        ("4", "Різні пресети", example_4_presets),
        ("5", "Інтеграція з task system", example_5_task_integration),
        ("6", "Обробка помилок", example_6_error_handling),
    ]
    
    print("\nДоступні приклади:")
    for num, desc, _ in examples:
        print(f"  {num}. {desc}")
    
    print("\nВикористання:")
    print(f"  python3 {__file__} [номер прикладу]")
    print(f"  python3 {__file__} 1    # Запустити приклад 1")
    print(f"  python3 {__file__}      # Показати пресети (приклад 4)")
    
    # Якщо вказано номер прикладу
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        
        for num, desc, func in examples:
            if num == example_num:
                print(f"\n🚀 Запуск прикладу {num}: {desc}")
                func()
                return
        
        print(f"\n❌ Невірний номер прикладу: {example_num}")
        print(f"   Доступні: 1-{len(examples)}")
    else:
        # За замовчуванням показуємо пресети
        example_4_presets()


if __name__ == '__main__':
    main()
