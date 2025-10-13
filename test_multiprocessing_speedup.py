#!/usr/bin/env python3
"""
Тест реального параллелизма: ProcessPoolExecutor vs ThreadPoolExecutor

Этот скрипт демонстрирует разницу между:
1. Последовательной обработкой
2. ThreadPoolExecutor (псевдо-параллелизм из-за GIL)
3. ProcessPoolExecutor (настоящий параллелизм)
"""

import os
import sys
import time
import concurrent.futures
import multiprocessing as mp
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def simulate_cpu_work(duration: float = 2.0) -> str:
    """
    Simulate CPU-intensive work (like audio processing)
    Uses pure Python to ensure GIL is active
    """
    start = time.time()
    result = 0
    
    # CPU-intensive calculation
    while time.time() - start < duration:
        result += sum(range(10000))
    
    return f"Process {mp.current_process().name}: {duration:.1f}s work done"


def test_sequential(num_chunks: int = 4, work_duration: float = 2.0):
    """Test 1: Sequential processing"""
    print("\n" + "=" * 80)
    print("TEST 1: ПОСЛЕДОВАТЕЛЬНАЯ ОБРАБОТКА (baseline)")
    print("=" * 80)
    
    start_time = time.time()
    
    results = []
    for i in range(num_chunks):
        print(f"  Processing chunk {i}...")
        result = simulate_cpu_work(work_duration)
        results.append(result)
    
    total_time = time.time() - start_time
    
    print(f"\n✅ Завершено")
    print(f"   Время: {total_time:.2f}s")
    print(f"   Ожидалось: ~{num_chunks * work_duration:.1f}s")
    
    return total_time


def test_threading(num_chunks: int = 4, work_duration: float = 2.0):
    """Test 2: ThreadPoolExecutor (псевдо-параллелизм)"""
    print("\n" + "=" * 80)
    print("TEST 2: ThreadPoolExecutor (псевдо-параллелизм из-за GIL)")
    print("=" * 80)
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_chunks) as executor:
        futures = [executor.submit(simulate_cpu_work, work_duration) for _ in range(num_chunks)]
        
        results = []
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            print(f"  {result}")
            results.append(result)
    
    total_time = time.time() - start_time
    
    print(f"\n⚠️  Завершено")
    print(f"   Время: {total_time:.2f}s")
    print(f"   Ожидалось (если бы параллельно): ~{work_duration:.1f}s")
    print(f"   Реально (из-за GIL): ~{num_chunks * work_duration:.1f}s")
    
    if total_time > work_duration * 1.5:
        print(f"   ❌ GIL блокирует параллелизм! Работает последовательно.")
    else:
        print(f"   ✅ Параллелизм работает")
    
    return total_time


def test_multiprocessing(num_chunks: int = 4, work_duration: float = 2.0):
    """Test 3: ProcessPoolExecutor (настоящий параллелизм)"""
    print("\n" + "=" * 80)
    print("TEST 3: ProcessPoolExecutor (настоящий параллелизм)")
    print("=" * 80)
    
    start_time = time.time()
    
    ctx = mp.get_context('spawn')
    
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=num_chunks,
        mp_context=ctx
    ) as executor:
        futures = [executor.submit(simulate_cpu_work, work_duration) for _ in range(num_chunks)]
        
        results = []
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            print(f"  {result}")
            results.append(result)
    
    total_time = time.time() - start_time
    
    print(f"\n✅ Завершено")
    print(f"   Время: {total_time:.2f}s")
    print(f"   Ожидалось (параллельно): ~{work_duration:.1f}s")
    
    speedup = (num_chunks * work_duration) / total_time
    print(f"   Ускорение: {speedup:.2f}x")
    
    if speedup > 1.5:
        print(f"   ✅ Настоящий параллелизм работает!")
    else:
        print(f"   ⚠️  Параллелизм работает плохо")
    
    return total_time


def main():
    print("=" * 80)
    print("🧪 ТЕСТ ПАРАЛЛЕЛИЗМА: Threading vs Multiprocessing")
    print("=" * 80)
    
    num_chunks = 4
    work_duration = 2.0  # секунды CPU работы на фрагмент
    
    print(f"\nПараметры теста:")
    print(f"  Количество фрагментов: {num_chunks}")
    print(f"  Работа на фрагмент: {work_duration}s")
    print(f"  CPU ядер: {os.cpu_count()}")
    
    # Test 1: Sequential
    time_sequential = test_sequential(num_chunks, work_duration)
    
    # Test 2: Threading
    time_threading = test_threading(num_chunks, work_duration)
    
    # Test 3: Multiprocessing
    time_multiprocessing = test_multiprocessing(num_chunks, work_duration)
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 ИТОГИ")
    print("=" * 80)
    
    print(f"\n⏱️  Последовательная:      {time_sequential:.2f}s (baseline)")
    print(f"⏱️  ThreadPoolExecutor:    {time_threading:.2f}s (ускорение: {time_sequential/time_threading:.2f}x)")
    print(f"⏱️  ProcessPoolExecutor:   {time_multiprocessing:.2f}s (ускорение: {time_sequential/time_multiprocessing:.2f}x)")
    
    # Analysis
    print(f"\n📈 Анализ:")
    
    threading_speedup = time_sequential / time_threading
    multiprocessing_speedup = time_sequential / time_multiprocessing
    
    if threading_speedup < 1.3:
        print(f"   ❌ ThreadPoolExecutor: Почти нет ускорения ({threading_speedup:.2f}x) - GIL блокирует!")
    else:
        print(f"   ✅ ThreadPoolExecutor: Есть ускорение ({threading_speedup:.2f}x)")
    
    if multiprocessing_speedup > 2:
        print(f"   ✅ ProcessPoolExecutor: Отличное ускорение ({multiprocessing_speedup:.2f}x) - параллелизм работает!")
    elif multiprocessing_speedup > 1.5:
        print(f"   ✅ ProcessPoolExecutor: Хорошее ускорение ({multiprocessing_speedup:.2f}x)")
    else:
        print(f"   ⚠️  ProcessPoolExecutor: Слабое ускорение ({multiprocessing_speedup:.2f}x)")
    
    # Recommendations
    print(f"\n💡 Рекомендации:")
    if multiprocessing_speedup > threading_speedup * 1.5:
        print(f"   ✅ Используйте ProcessPoolExecutor для CPU-intensive задач!")
        print(f"   ✅ Ожидаемое ускорение для обработки голоса: {multiprocessing_speedup:.1f}x")
    else:
        print(f"   ⚠️  На вашей системе разница небольшая")
        print(f"   ℹ️  Возможно, мало CPU ядер или большие накладные расходы")
    
    print("\n" + "=" * 80)
    print("✅ ТЕСТ ЗАВЕРШЕН")
    print("=" * 80)


if __name__ == "__main__":
    main()

