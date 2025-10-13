"""
Russian Stress/Accent Module
Автоматическая расстановка нормативного (орфоэпического) ударения в русском тексте

Правильное ударение важно для:
- Естественного произношения при синтезе речи
- Различения омографов (например: за́мок vs замо́к, му́ка vs мука́)
- Корректной интонации и ритма
"""

import logging
from typing import Optional, List, Dict, Tuple
import re

try:
    # Попытка использовать russtress (легковесная библиотека)
    from russtress import Accent
    RUSSTRESS_AVAILABLE = True
except ImportError:
    RUSSTRESS_AVAILABLE = False

try:
    # Альтернатива: russian-accentuate (более точная)
    import russian_accentuate
    RUSSIAN_ACCENTUATE_AVAILABLE = True
except ImportError:
    RUSSIAN_ACCENTUATE_AVAILABLE = False

try:
    # RUSpellPy - словарь с ударениями
    import pymorphy3
    PYMORPHY_AVAILABLE = True
except ImportError:
    PYMORPHY_AVAILABLE = False

from core.utils.logger import get_logger

# Импортируем расширенный словарь
try:
    from core.utils.stress_dictionaries import (
        EXTENDED_STRESS_DICT,
        WORD_FORMS,
        get_stress_position
    )
    EXTENDED_DICT_AVAILABLE = True
except ImportError:
    EXTENDED_DICT_AVAILABLE = False
    EXTENDED_STRESS_DICT = {}
    WORD_FORMS = {}

logger = get_logger(__name__)


class RussianStressMarker:
    """
    Класс для расстановки нормативного ударения в русском тексте
    
    Поддерживает:
    - Автоматическое определение ударений
    - Словарь исключений для частых слов
    - Различные форматы маркировки (символ + после ударной гласной, ё вместо е и т.д.)
    """
    
    # Словарь частых слов с правильным ударением
    # Формат: слово -> позиция ударной гласной (0-based)
    COMMON_WORDS_STRESS = {
        # Омографы (разное значение - разное ударение)
        'замок': [(1, 'за́мок - строение'), (4, 'замо́к - устройство')],
        'мука': [(1, 'му́ка - мучение'), (4, 'мука́ - продукт')],
        'атлас': [(0, 'а́тлас - ткань'), (4, 'атла́с - книга карт')],
        'угольный': [(0, 'у́гольный - от угол'), (3, 'уго́льный - от уголь')],
        'хлопок': [(1, 'хло́пок - растение'), (5, 'хлопо́к - звук')],
        'белки': [(1, 'бе́лки - животные'), (4, 'белки́ - вещества')],
        'пропасть': [(3, 'про́пасть - бездна'), (6, 'пропа́сть - исчезнуть')],
        'духи': [(1, 'ду́хи - призраки'), (4, 'духи́ - парфюм')],
        'ирис': [(0, 'и́рис - цветок'), (4, 'ири́с - конфета')],
        'орган': [(0, 'о́рган - инструмент/часть тела')],
        'язык': [(4, 'язы́к')],
        'окно': [(4, 'окно́')],
        'вода': [(4, 'вода́')],
        'стол': [(4, 'сто́л')],
        'дом': [(2, 'до́м')],
        'город': [(1, 'го́род')],
        'человек': [(5, 'челове́к')],
        'работа': [(4, 'рабо́та')],
        'время': [(2, 'вре́мя')],
        'сегодня': [(5, 'сего́дня')],
        'завтра': [(1, 'за́втра')],
        'вчера': [(4, 'вчера́')],
        'спасибо': [(4, 'спаси́бо')],
        'пожалуйста': [(6, 'пожа́луйста')],
        'здравствуйте': [(1, 'здра́вствуйте')],
        'до свидания': [(7, 'до свида́ния')],
    }
    
    # Гласные буквы русского алфавита
    VOWELS = 'аеёиоуыэюяАЕЁИОУЫЭЮЯ'
    
    # Символы ударения
    STRESS_SYMBOLS = {
        'acute': '\u0301',      # ́  (combining acute accent) - стандарт Unicode
        'plus': '+',            # + (символ после ударной гласной)
        'apostrophe': "'",      # ' (апостроф после ударной гласной)
        'grave': '\u0300',      # ̀  (combining grave accent)
        'yo': 'ё'              # автоматическая замена е→ё в ударной позиции
    }
    
    def __init__(self, stress_symbol: str = 'acute', use_yo: bool = True):
        """
        Инициализация модуля ударений
        
        Args:
            stress_symbol: Тип символа ударения ('acute', 'plus', 'apostrophe', 'grave')
            use_yo: Заменять ли 'е' на 'ё' в ударной позиции
        """
        self.stress_symbol = self.STRESS_SYMBOLS.get(stress_symbol, self.STRESS_SYMBOLS['acute'])
        self.use_yo = use_yo
        
        # Инициализация библиотеки для автоматической расстановки
        self.accent_engine = None
        self.engine_type = None
        
        if RUSSTRESS_AVAILABLE:
            try:
                self.accent_engine = Accent()
                self.engine_type = 'russtress'
                logger.info("✓ Loaded russtress for automatic stress detection")
            except Exception as e:
                logger.warning(f"Failed to load russtress: {e}")
        
        if not self.accent_engine and RUSSIAN_ACCENTUATE_AVAILABLE:
            try:
                self.accent_engine = russian_accentuate
                self.engine_type = 'russian_accentuate'
                logger.info("✓ Loaded russian_accentuate for automatic stress detection")
            except Exception as e:
                logger.warning(f"Failed to load russian_accentuate: {e}")
        
        if not self.accent_engine:
            logger.warning("⚠ No automatic stress detection library available")
            logger.warning("  Install with: pip install russtress")
            logger.warning("  Will use fallback dictionary-based approach")
        
        # Добавляем слова из расширенного словаря
        if EXTENDED_DICT_AVAILABLE:
            for word, position in EXTENDED_STRESS_DICT.items():
                if word not in self.COMMON_WORDS_STRESS:
                    self.COMMON_WORDS_STRESS[word] = [(position, f"{word}")]
            logger.info(f"✓ Loaded {len(EXTENDED_STRESS_DICT)} words from extended dictionary")
        
        logger.info(f"Russian Stress Marker initialized (symbol: {stress_symbol}, use_yo: {use_yo})")
        logger.info(f"Total dictionary size: {len(self.COMMON_WORDS_STRESS)} words")
    
    def add_stress(self, text: str, handle_homographs: bool = True) -> str:
        """
        Добавить ударения к русскому тексту
        
        Args:
            text: Исходный текст без ударений
            handle_homographs: Обрабатывать ли омографы (слова с разным ударением)
            
        Returns:
            Текст с расставленными ударениями
        """
        if not text or not text.strip():
            return text
        
        logger.info(f"Adding stress marks to text ({len(text)} chars)...")
        
        # Используем автоматическую библиотеку если доступна
        if self.accent_engine and self.engine_type == 'russtress':
            try:
                # russtress использует символ +
                text_with_stress = self.accent_engine.put_stress(text, stress_symbol='+')
                
                # Конвертируем в нужный формат
                text_with_stress = self._convert_stress_format(text_with_stress, from_symbol='+')
                
                logger.info("✓ Stress marks added using russtress")
                return text_with_stress
                
            except Exception as e:
                logger.warning(f"Russtress failed: {e}, using fallback")
        
        elif self.accent_engine and self.engine_type == 'russian_accentuate':
            try:
                # russian_accentuate
                text_with_stress = self.accent_engine.accentuate(text)
                
                # Конвертируем в нужный формат
                text_with_stress = self._convert_stress_format(text_with_stress, from_symbol='acute')
                
                logger.info("✓ Stress marks added using russian_accentuate")
                return text_with_stress
                
            except Exception as e:
                logger.warning(f"Russian_accentuate failed: {e}, using fallback")
        
        # Fallback: словарный подход
        text_with_stress = self._add_stress_dictionary(text, handle_homographs)
        logger.info("✓ Stress marks added using dictionary")
        
        return text_with_stress
    
    def _add_stress_dictionary(self, text: str, handle_homographs: bool) -> str:
        """
        Добавить ударения используя встроенный словарь
        
        Args:
            text: Исходный текст
            handle_homographs: Обрабатывать омографы
            
        Returns:
            Текст с ударениями
        """
        # Разбиваем на слова, сохраняя пунктуацию и пробелы
        words = re.findall(r'\w+|[^\w]', text, re.UNICODE)
        
        result_words = []
        
        for word in words:
            if not word.strip() or not any(c.isalpha() for c in word):
                # Пробелы и пунктуация
                result_words.append(word)
                continue
            
            word_lower = word.lower()
            
            # Проверяем в словаре
            if word_lower in self.COMMON_WORDS_STRESS:
                stress_positions = self.COMMON_WORDS_STRESS[word_lower]
                
                if isinstance(stress_positions, list) and len(stress_positions) > 1:
                    # Омограф - берем первый вариант
                    if handle_homographs:
                        position, note = stress_positions[0]
                        stressed_word = self._apply_stress_at_position(word, position)
                        logger.debug(f"Homograph: {word} -> {stressed_word} ({note})")
                        result_words.append(stressed_word)
                    else:
                        result_words.append(word)
                else:
                    # Обычное слово
                    if isinstance(stress_positions, list):
                        position, _ = stress_positions[0]
                    else:
                        position = stress_positions[0] if isinstance(stress_positions[0], tuple) else stress_positions
                        if isinstance(position, tuple):
                            position, _ = position
                    
                    stressed_word = self._apply_stress_at_position(word, position)
                    result_words.append(stressed_word)
            else:
                # Слово не в словаре - пытаемся определить ударение эвристически
                stressed_word = self._guess_stress(word)
                result_words.append(stressed_word)
        
        return ''.join(result_words)
    
    def _apply_stress_at_position(self, word: str, position: int) -> str:
        """
        Применить ударение на указанной позиции
        
        Args:
            word: Слово
            position: Позиция ударной гласной (0-based)
            
        Returns:
            Слово с ударением
        """
        if position < 0 or position >= len(word):
            return word
        
        # Находим гласные
        vowel_positions = [i for i, c in enumerate(word) if c.lower() in self.VOWELS.lower()]
        
        if not vowel_positions:
            return word
        
        # Находим ближайшую гласную к указанной позиции
        closest_vowel_pos = min(vowel_positions, key=lambda x: abs(x - position))
        
        # Применяем ударение
        if self.use_yo and word[closest_vowel_pos].lower() == 'е':
            # Заменяем е на ё
            result = list(word)
            if word[closest_vowel_pos].isupper():
                result[closest_vowel_pos] = 'Ё'
            else:
                result[closest_vowel_pos] = 'ё'
            return ''.join(result)
        else:
            # Добавляем символ ударения
            if self.stress_symbol in ['+', "'"]:
                # Символ после гласной
                return word[:closest_vowel_pos + 1] + self.stress_symbol + word[closest_vowel_pos + 1:]
            else:
                # Combining accent (перед следующим символом или в конце)
                return word[:closest_vowel_pos + 1] + self.stress_symbol + word[closest_vowel_pos + 1:]
    
    def _guess_stress(self, word: str) -> str:
        """
        Эвристическое определение ударения
        
        Правила:
        - Односложные слова не требуют ударения
        - Ё всегда ударная
        - В остальных случаях - ударение на предпоследний слог (частый случай)
        
        Args:
            word: Слово
            
        Returns:
            Слово с предполагаемым ударением
        """
        # Находим гласные
        vowels = [(i, c) for i, c in enumerate(word) if c.lower() in self.VOWELS.lower()]
        
        if not vowels:
            return word
        
        # Односложное слово
        if len(vowels) == 1:
            return word
        
        # Если есть ё - она всегда ударная
        for i, c in vowels:
            if c.lower() == 'ё':
                return self._apply_stress_at_position(word, i)
        
        # Эвристика: ударение на предпоследний слог (типично для русского)
        if len(vowels) >= 2:
            stress_pos = vowels[-2][0]  # предпоследняя гласная
        else:
            stress_pos = vowels[-1][0]  # последняя гласная
        
        return self._apply_stress_at_position(word, stress_pos)
    
    def _convert_stress_format(self, text: str, from_symbol: str) -> str:
        """
        Конвертировать формат ударения из одного в другой
        
        Args:
            text: Текст с ударениями
            from_symbol: Исходный символ ('acute', 'plus', etc.)
            
        Returns:
            Текст с конвертированными ударениями
        """
        # Если формат совпадает - возвращаем как есть
        if from_symbol == self.stress_symbol:
            return text
        
        # Конвертация между форматами
        from_sym = self.STRESS_SYMBOLS.get(from_symbol, '+')
        to_sym = self.stress_symbol
        
        # Простая замена символов
        if from_sym in ['+', "'"]:
            # Символ после гласной
            if to_sym in ['+', "'"]:
                # Просто заменяем символ
                return text.replace(from_sym, to_sym)
            else:
                # Combining accent - убираем + и добавляем combining
                result = []
                for i, char in enumerate(text):
                    if char == from_sym and i > 0:
                        # Вставляем combining accent перед текущим символом
                        result[-1] += to_sym
                    else:
                        result.append(char)
                return ''.join(result)
        else:
            # Combining accent -> другой формат
            if to_sym in ['+', "'"]:
                # Убираем combining, добавляем символ после
                text_cleaned = text.replace(from_sym, to_sym)
                return text_cleaned
            else:
                # Combining -> combining
                return text.replace(from_sym, to_sym)
    
    def remove_stress(self, text: str) -> str:
        """
        Удалить все символы ударения из текста
        
        Args:
            text: Текст с ударениями
            
        Returns:
            Текст без ударений
        """
        # Удаляем все known stress symbols
        result = text
        for symbol in self.STRESS_SYMBOLS.values():
            result = result.replace(symbol, '')
        
        # Заменяем ё обратно на е (опционально)
        # result = result.replace('ё', 'е').replace('Ё', 'Е')
        
        return result
    
    def get_stressed_words(self, text: str) -> List[Tuple[str, int]]:
        """
        Извлечь список слов с ударениями и их позициями
        
        Args:
            text: Текст
            
        Returns:
            Список кортежей (слово_с_ударением, позиция_ударной_гласной)
        """
        text_with_stress = self.add_stress(text)
        
        words = re.findall(r'\w+', text_with_stress, re.UNICODE)
        
        stressed_words = []
        for word in words:
            # Найти позицию ударения
            stress_pos = -1
            for i, char in enumerate(word):
                if char in self.STRESS_SYMBOLS.values():
                    stress_pos = i - 1  # Ударение после гласной
                    break
                elif char == 'ё' or char == 'Ё':
                    stress_pos = i
                    break
            
            if stress_pos >= 0:
                stressed_words.append((word, stress_pos))
        
        return stressed_words
    
    def validate_stress(self, word: str, expected_position: int) -> bool:
        """
        Проверить правильность ударения в слове
        
        Args:
            word: Слово с ударением
            expected_position: Ожидаемая позиция ударения
            
        Returns:
            True если ударение правильное
        """
        # Найти текущую позицию ударения
        for i, char in enumerate(word):
            if char in self.STRESS_SYMBOLS.values():
                current_pos = i - 1
                return current_pos == expected_position
            elif char in 'ёЁ':
                return i == expected_position
        
        return False
    
    def get_homograph_info(self, word: str) -> Optional[List[str]]:
        """
        Получить информацию об омографе
        
        Args:
            word: Слово
            
        Returns:
            Список вариантов с описаниями или None
        """
        word_lower = word.lower()
        if word_lower in self.COMMON_WORDS_STRESS:
            stress_info = self.COMMON_WORDS_STRESS[word_lower]
            if isinstance(stress_info, list) and len(stress_info) > 1:
                return [note for _, note in stress_info]
        
        return None


# Convenience function
def add_russian_stress(text: str, stress_symbol: str = 'acute', use_yo: bool = True) -> str:
    """
    Удобная функция для добавления ударений к русскому тексту
    
    Args:
        text: Текст без ударений
        stress_symbol: Тип символа ('acute', 'plus', 'apostrophe', 'grave')
        use_yo: Заменять е на ё в ударной позиции
        
    Returns:
        Текст с ударениями
    """
    marker = RussianStressMarker(stress_symbol=stress_symbol, use_yo=use_yo)
    return marker.add_stress(text)


# Тестовый код
if __name__ == "__main__":
    # Примеры использования
    marker = RussianStressMarker(stress_symbol='acute', use_yo=True)
    
    test_texts = [
        "Привет, как дела?",
        "Замок был закрыт на замок.",
        "Мука приносит муку.",
        "Сегодня хорошая погода.",
        "Я люблю читать книги.",
    ]
    
    print("🎯 Тестирование модуля русских ударений\n")
    print("=" * 60)
    
    for text in test_texts:
        stressed = marker.add_stress(text)
        print(f"\nОригинал: {text}")
        print(f"С ударением: {stressed}")
    
    print("\n" + "=" * 60)
    print("\n✅ Тестирование завершено")

