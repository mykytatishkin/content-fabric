#!/usr/bin/env python3
"""
Text-to-Speech Example
Demonstrates how to synthesize text directly to audio using Silero TTS
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.voice import VoiceChanger
from core.utils.logger import get_logger

logger = get_logger(__name__)


def example_1_basic_synthesis():
    """Basic text-to-speech synthesis"""
    print("\n" + "="*70)
    print("Example 1: Basic Text-to-Speech Synthesis")
    print("="*70)
    
    # Initialize voice changer
    changer = VoiceChanger()
    
    # Text to synthesize
    text = "Привет! Это пример синтеза речи с помощью Silero TTS."
    
    # Synthesize
    result = changer.process_text(
        text=text,
        output_file="data/content/audio/text_synthesis_basic.wav",
        voice="kseniya",
        add_stress=True
    )
    
    print(f"\n✅ Success!")
    print(f"Output: {result['output_file']}")
    print(f"Voice: {result['voice']}")
    print(f"Duration: {result['duration']:.2f}s")
    print(f"Text: {result['text']}")


def example_2_different_voices():
    """Synthesize same text with different voices"""
    print("\n" + "="*70)
    print("Example 2: Different Voices")
    print("="*70)
    
    changer = VoiceChanger()
    
    text = "Это один и тот же текст, озвученный разными голосами."
    
    voices = ['kseniya', 'eugene', 'aidar', 'baya']
    
    for voice in voices:
        output_file = f"data/content/audio/text_synthesis_{voice}.wav"
        
        print(f"\nSynthesizing with voice: {voice}")
        result = changer.process_text(
            text=text,
            output_file=output_file,
            voice=voice,
            add_stress=True
        )
        
        print(f"  ✅ Saved: {result['output_file']}")


def example_3_long_text():
    """Synthesize long text (will be automatically split)"""
    print("\n" + "="*70)
    print("Example 3: Long Text (Automatic Chunking)")
    print("="*70)
    
    changer = VoiceChanger()
    
    # Long text
    text = """
    Искусственный интеллект продолжает развиваться с невероятной скоростью.
    Системы синтеза речи становятся все более естественными и выразительными.
    Silero TTS - это открытая библиотека для синтеза русской речи,
    которая позволяет создавать высококачественные голосовые записи.
    Она использует современные методы машинного обучения для достижения
    естественного звучания человеческого голоса.
    """
    
    result = changer.process_text(
        text=text.strip(),
        output_file="data/content/audio/text_synthesis_long.wav",
        voice="eugene",
        add_stress=True
    )
    
    print(f"\n✅ Success!")
    print(f"Output: {result['output_file']}")
    print(f"Duration: {result['duration']:.2f}s")
    print(f"Text length: {len(result['text'])} characters")


def example_4_without_stress():
    """Synthesize without stress marks (faster)"""
    print("\n" + "="*70)
    print("Example 4: Without Stress Marks")
    print("="*70)
    
    changer = VoiceChanger()
    
    text = "Это быстрый синтез без обработки ударений."
    
    result = changer.process_text(
        text=text,
        output_file="data/content/audio/text_synthesis_no_stress.wav",
        voice="kseniya",
        add_stress=False  # Faster processing
    )
    
    print(f"\n✅ Success!")
    print(f"Output: {result['output_file']}")
    print(f"Stress marks: Disabled (faster)")


def example_5_direct_api():
    """Use SileroVoiceChanger directly"""
    print("\n" + "="*70)
    print("Example 5: Direct API Usage")
    print("="*70)
    
    from core.voice import SileroVoiceChanger
    
    changer = SileroVoiceChanger()
    
    text = "Использование прямого API SileroVoiceChanger."
    
    result = changer.synthesize_text_to_audio(
        text=text,
        output_file="data/content/audio/text_synthesis_direct.wav",
        target_voice="baya",
        sample_rate=48000,
        add_stress=True
    )
    
    print(f"\n✅ Success!")
    print(f"Output: {result['output_file']}")
    print(f"Voice: {result['voice']}")
    print(f"Method: {result['method']}")
    print(f"Duration: {result['duration']:.2f}s")


def main():
    """Run all examples"""
    print("\n🎙️  Text-to-Speech Examples")
    print("="*70)
    print("This script demonstrates text-to-speech synthesis using Silero TTS")
    print("="*70)
    
    # Create output directory
    Path("data/content/audio").mkdir(parents=True, exist_ok=True)
    
    try:
        # Run examples
        example_1_basic_synthesis()
        example_2_different_voices()
        example_3_long_text()
        example_4_without_stress()
        example_5_direct_api()
        
        print("\n" + "="*70)
        print("✅ All examples completed successfully!")
        print("="*70)
        print("\nOutput files are in: data/content/audio/")
        print("You can play them with any audio player.")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        print(f"\n❌ Error: {str(e)}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

