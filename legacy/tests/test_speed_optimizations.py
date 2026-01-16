#!/usr/bin/env python3
"""
Тест различных оптимизаций скорости
"""

import os
import sys
import time
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.utils.voice_changer import VoiceChanger


def test_optimization(name, **kwargs):
    """Test single optimization"""
    print(f"\n{'='*80}")
    print(f"TEST: {name}")
    print(f"{'='*80}")
    
    input_file = "data/content/audio/input.mp3"
    output_file = f"data/content/processed/test_{name.lower().replace(' ', '_')}.wav"
    
    if not os.path.exists(input_file):
        print(f"❌ Файл не найден: {input_file}")
        return None
    
    try:
        # Create changer
        changer = VoiceChanger(**kwargs)
        
        # Process
        start = time.time()
        result = changer.process_file(
            input_file=input_file,
            output_file=output_file,
            method='silero',
            voice_model='kseniya',
            preserve_quality=kwargs.get('preserve_quality', True)
        )
        duration = time.time() - start
        
        # Cleanup
        changer.cleanup()
        
        print(f"\n✅ Завершено за {duration:.2f}s")
        
        return duration
        
    except Exception as e:
        print(f"\n❌ Ошибка: {str(e)}")
        return None


def main():
    print("="*80)
    print("🚀 ТЕСТ ОПТИМИЗАЦИЙ СКОРОСТИ")
    print("="*80)
    
    # Check GPU
    has_gpu = torch.cuda.is_available()
    print(f"\n🔍 GPU доступен: {'✅ Да' if has_gpu else '❌ Нет'}")
    print(f"   CPU ядер: {os.cpu_count()}")
    
    results = {}
    
    # Test 1: Baseline (sequential)
    print("\n" + "="*80)
    print("Baseline: Последовательная обработка")
    print("="*80)
    results['baseline'] = test_optimization(
        "Baseline (Sequential)",
        enable_parallel=False,
        device='cpu'
    )
    
    # Test 2: Parallel CPU
    results['parallel_cpu'] = test_optimization(
        "Parallel (CPU)",
        enable_parallel=True,
        chunk_duration_minutes=3,
        max_workers=4,
        device='cpu'
    )
    
    # Test 3: Parallel CPU (fast mode)
    results['parallel_cpu_fast'] = test_optimization(
        "Parallel CPU (Fast mode)",
        enable_parallel=True,
        chunk_duration_minutes=2,
        max_workers=6,
        device='cpu',
        preserve_quality=False  # No prosody
    )
    
    # Test 4: GPU if available
    if has_gpu:
        results['gpu'] = test_optimization(
            "GPU (CUDA)",
            enable_parallel=False,
            device='cuda'
        )
        
        results['parallel_gpu'] = test_optimization(
            "Parallel GPU",
            enable_parallel=True,
            chunk_duration_minutes=3,
            max_workers=2,  # Less workers for GPU
            device='cuda'
        )
    
    # Summary
    print("\n" + "="*80)
    print("📊 ИТОГИ")
    print("="*80)
    
    baseline = results.get('baseline')
    if baseline:
        print(f"\n{'Конфигурация':<30} {'Время':<12} {'Ускорение':<12}")
        print("-" * 54)
        
        for name, duration in results.items():
            if duration:
                speedup = baseline / duration
                print(f"{name:<30} {duration:>8.2f}s   {speedup:>8.2f}x")
        
        # Recommendations
        print("\n💡 РЕКОМЕНДАЦИИ:")
        
        if has_gpu:
            gpu_time = results.get('parallel_gpu') or results.get('gpu')
            if gpu_time and gpu_time < baseline * 0.5:
                print(f"   ✅ Используйте GPU! Ускорение: {baseline/gpu_time:.1f}x")
                print(f"      Команда: python run_parallel_voice.py input.mp3 output.mp3 --device cuda")
        
        fast_time = results.get('parallel_cpu_fast')
        if fast_time and fast_time < baseline * 0.5:
            print(f"   ✅ Быстрый режим дает {baseline/fast_time:.1f}x ускорение")
            print(f"      Команда: python run_parallel_voice.py input.mp3 output.mp3 --parallel --quality fast --chunks 2")
        
        parallel_time = results.get('parallel_cpu')
        if parallel_time and parallel_time < baseline * 0.7:
            print(f"   ✅ Параллельный CPU: {baseline/parallel_time:.1f}x ускорение")
            print(f"      Команда: python run_parallel_voice.py input.mp3 output.mp3 --parallel")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

