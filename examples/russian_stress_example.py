"""
Примеры использования модуля русских ударений (RussianStressMarker)

Этот файл демонстрирует различные способы использования модуля для
расстановки нормативного (орфоэпического) ударения в русском тексте.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.utils.russian_stress import RussianStressMarker, add_russian_stress
from core.utils.logger import get_logger

logger = get_logger(__name__)


def example_1_basic_usage():
    """Пример 1: Базовое использование"""
    print("\n" + "=" * 80)
    print("ПРИМЕР 1: Базовое использование")
    print("=" * 80)
    
    # Создаём маркер ударений
    marker = RussianStressMarker(
        stress_symbol='plus',  # Символ + после ударной гласной
        use_yo=True           # Заменять е на ё в ударной позиции
    )
    
    # Простой текст
    text = "Привет! Как дела сегодня?"
    stressed = marker.add_stress(text)
    
    print(f"\nОригинал:     {text}")
    print(f"С ударением:  {stressed}")


def example_2_homographs():
    """Пример 2: Работа с омографами"""
    print("\n" + "=" * 80)
    print("ПРИМЕР 2: Омографы (слова с разным ударением)")
    print("=" * 80)
    
    marker = RussianStressMarker(stress_symbol='plus', use_yo=True)
    
    # Тексты с омографами
    test_cases = [
        "Замок был закрыт на замок",
        "Мука приносит много муки",
        "Я купил атлас и атлас мира",
        "Хлопок рос в поле, раздался хлопок",
        "Белки прыгали по деревьям, белки полезны",
    ]
    
    for text in test_cases:
        stressed = marker.add_stress(text, handle_homographs=True)
        print(f"\nОригинал:     {text}")
        print(f"С ударением:  {stressed}")
        
        # Показать варианты для омографов
        words = text.split()
        for word in words:
            homograph_info = marker.get_homograph_info(word.lower().strip(',.!?'))
            if homograph_info:
                print(f"  └─ Омограф '{word}': {', '.join(homograph_info)}")


def example_3_different_formats():
    """Пример 3: Различные форматы ударения"""
    print("\n" + "=" * 80)
    print("ПРИМЕР 3: Различные форматы ударения")
    print("=" * 80)
    
    text = "Вода в реке была холодная"
    
    formats = [
        ('plus', 'Символ +'),
        ('acute', 'Unicode acute accent'),
        ('apostrophe', 'Апостроф'),
        ('grave', 'Unicode grave accent'),
    ]
    
    print(f"\nОригинальный текст: {text}\n")
    
    for symbol, description in formats:
        marker = RussianStressMarker(stress_symbol=symbol, use_yo=True)
        stressed = marker.add_stress(text)
        print(f"{description:30} → {stressed}")


def example_4_with_silero_tts():
    """Пример 4: Интеграция с Silero TTS"""
    print("\n" + "=" * 80)
    print("ПРИМЕР 4: Подготовка текста для Silero TTS")
    print("=" * 80)
    
    # Silero TTS лучше всего работает с форматом 'plus' и заменой е→ё
    marker = RussianStressMarker(stress_symbol='plus', use_yo=True)
    
    # Длинный текст для синтеза
    text = """
    Добрый день! Сегодня мы расскажем о системе автоматического 
    синтеза речи. Система умеет правильно расставлять ударения 
    в словах, различать омографы и создавать естественную интонацию.
    """
    
    # Очищаем от лишних пробелов
    text = ' '.join(text.split())
    
    # Добавляем ударения
    stressed = marker.add_stress(text)
    
    print(f"\nОригинал:\n{text}")
    print(f"\nДля Silero TTS:\n{stressed}")
    
    # Этот текст можно передать в Silero TTS для синтеза


def example_5_convenience_function():
    """Пример 5: Использование функции-утилиты"""
    print("\n" + "=" * 80)
    print("ПРИМЕР 5: Функция-утилита add_russian_stress()")
    print("=" * 80)
    
    # Быстрый способ без создания объекта
    text = "Спасибо за внимание!"
    
    # С символом +
    stressed_plus = add_russian_stress(text, stress_symbol='plus', use_yo=True)
    print(f"\nС символом +:  {stressed_plus}")
    
    # С Unicode accent
    stressed_acute = add_russian_stress(text, stress_symbol='acute', use_yo=True)
    print(f"С Unicode:     {stressed_acute}")


def example_6_remove_stress():
    """Пример 6: Удаление ударений"""
    print("\n" + "=" * 80)
    print("ПРИМЕР 6: Удаление ударений")
    print("=" * 80)
    
    marker = RussianStressMarker()
    
    # Текст с ударениями
    text_with_stress = "Приве+т! Ка+к дела+?"
    
    # Удаляем ударения
    text_clean = marker.remove_stress(text_with_stress)
    
    print(f"\nС ударениями: {text_with_stress}")
    print(f"Очищенный:    {text_clean}")


def example_7_batch_processing():
    """Пример 7: Пакетная обработка текстов"""
    print("\n" + "=" * 80)
    print("ПРИМЕР 7: Пакетная обработка")
    print("=" * 80)
    
    marker = RussianStressMarker(stress_symbol='plus', use_yo=True)
    
    # Список текстов для обработки
    texts = [
        "Доброе утро!",
        "Как ваши дела?",
        "Спасибо за информацию.",
        "До свидания!",
    ]
    
    print("\nОбработка списка текстов:\n")
    
    results = []
    for i, text in enumerate(texts, 1):
        stressed = marker.add_stress(text)
        results.append(stressed)
        print(f"{i}. {text:30} → {stressed}")
    
    return results


def example_8_real_world_scenario():
    """Пример 8: Реальный сценарий использования"""
    print("\n" + "=" * 80)
    print("ПРИМЕР 8: Реальный сценарий - подготовка текста подкаста")
    print("=" * 80)
    
    marker = RussianStressMarker(stress_symbol='plus', use_yo=True)
    
    # Текст подкаста
    podcast_text = """
    Здравствуйте, дорогие слушатели! В сегодняшнем выпуске мы 
    поговорим о том, как правильное ударение влияет на качество 
    синтеза речи. Замок на воротах замка был открыт. Мука доставляла 
    много муки. Как видите, ударение имеет решающее значение для 
    понимания смысла. Спасибо за внимание!
    """
    
    # Очистка и подготовка
    podcast_text = ' '.join(podcast_text.split())
    
    # Добавление ударений
    podcast_stressed = marker.add_stress(podcast_text)
    
    print("\n📝 ОРИГИНАЛЬНЫЙ ТЕКСТ:")
    print("-" * 80)
    print(podcast_text)
    
    print("\n🎯 ТЕКСТ С УДАРЕНИЯМИ:")
    print("-" * 80)
    print(podcast_stressed)
    
    # Статистика
    words_count = len(podcast_text.split())
    stress_marks = podcast_stressed.count('+')
    
    print("\n📊 СТАТИСТИКА:")
    print(f"  Всего слов: {words_count}")
    print(f"  Добавлено ударений: {stress_marks}")
    print(f"  Покрытие: {stress_marks/words_count*100:.1f}%")


def example_9_error_handling():
    """Пример 9: Обработка ошибок"""
    print("\n" + "=" * 80)
    print("ПРИМЕР 9: Обработка ошибок и граничные случаи")
    print("=" * 80)
    
    marker = RussianStressMarker(stress_symbol='plus', use_yo=True)
    
    # Различные граничные случаи
    test_cases = [
        ("", "Пустая строка"),
        ("123 456", "Только цифры"),
        ("Hello world", "Английский текст"),
        ("Привет123мир", "Смешанный текст"),
        ("!!!???...", "Только пунктуация"),
        ("Привет\nМир", "С переносами строк"),
    ]
    
    print("\nОбработка граничных случаев:\n")
    
    for text, description in test_cases:
        try:
            stressed = marker.add_stress(text)
            print(f"✓ {description:25} '{text}' → '{stressed}'")
        except Exception as e:
            print(f"✗ {description:25} '{text}' → Ошибка: {e}")


def example_10_performance_test():
    """Пример 10: Тест производительности"""
    print("\n" + "=" * 80)
    print("ПРИМЕР 10: Тест производительности")
    print("=" * 80)
    
    import time
    
    marker = RussianStressMarker(stress_symbol='plus', use_yo=True)
    
    # Длинный текст
    long_text = """
    Искусственный интеллект становится всё более важной частью нашей 
    повседневной жизни. Системы распознавания речи, синтез голоса, 
    машинный перевод - всё это примеры применения современных технологий. 
    Правильное ударение в словах играет ключевую роль в создании 
    естественно звучащей речи. Когда мы слышим речь с правильными 
    ударениями, она воспринимается гораздо легче и приятнее.
    """ * 10  # Повторяем 10 раз для нагрузки
    
    print(f"\nТекст: {len(long_text)} символов, {len(long_text.split())} слов")
    
    # Замер времени
    start_time = time.time()
    stressed = marker.add_stress(long_text)
    elapsed = time.time() - start_time
    
    print(f"\nВремя обработки: {elapsed:.3f} секунд")
    print(f"Скорость: {len(long_text.split()) / elapsed:.0f} слов/сек")
    print(f"Добавлено ударений: {stressed.count('+')}")


def run_all_examples():
    """Запустить все примеры"""
    print("\n" + "🎯" * 40)
    print("ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ МОДУЛЯ РУССКИХ УДАРЕНИЙ")
    print("🎯" * 40)
    
    examples = [
        example_1_basic_usage,
        example_2_homographs,
        example_3_different_formats,
        example_4_with_silero_tts,
        example_5_convenience_function,
        example_6_remove_stress,
        example_7_batch_processing,
        example_8_real_world_scenario,
        example_9_error_handling,
        example_10_performance_test,
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            logger.error(f"Ошибка в {example.__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("✅ ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_all_examples()

