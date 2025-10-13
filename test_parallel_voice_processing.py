#!/usr/bin/env python3
"""
Test Script for Parallel Voice Processing
Demonstrates the new parallel processing capabilities with chunking
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.utils.voice_changer import VoiceChanger
from core.utils.logger import get_logger

logger = get_logger(__name__)


def test_parallel_processing():
    """Test parallel voice processing"""
    
    print("=" * 80)
    print("PARALLEL VOICE PROCESSING TEST")
    print("=" * 80)
    
    # Configuration
    input_file = "data/content/audio/input.mp3"
    output_dir = "data/content/processed/parallel_test"
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        print("\nPlease create a test audio file or update the input_file path")
        return
    
    # Test configurations
    test_configs = [
        {
            'name': 'Sequential Processing (baseline)',
            'enable_parallel': False,
            'preserve_background': False,
            'output_suffix': 'sequential'
        },
        {
            'name': 'Parallel Processing (5min chunks)',
            'enable_parallel': True,
            'chunk_duration_minutes': 5,
            'preserve_background': False,
            'output_suffix': 'parallel_5min'
        },
        {
            'name': 'Parallel Processing (3min chunks)',
            'enable_parallel': True,
            'chunk_duration_minutes': 3,
            'preserve_background': False,
            'output_suffix': 'parallel_3min'
        },
        {
            'name': 'Parallel + Background Preservation',
            'enable_parallel': True,
            'chunk_duration_minutes': 5,
            'preserve_background': True,
            'output_suffix': 'parallel_with_bg'
        }
    ]
    
    results = []
    
    for config in test_configs:
        print("\n" + "=" * 80)
        print(f"TEST: {config['name']}")
        print("=" * 80)
        
        output_file = os.path.join(output_dir, f"output_{config['output_suffix']}.wav")
        
        try:
            # Initialize voice changer
            voice_changer = VoiceChanger(
                enable_parallel=config['enable_parallel'],
                chunk_duration_minutes=config.get('chunk_duration_minutes', 5),
                max_workers=None  # Auto-detect
            )
            
            # Start timer
            start_time = time.time()
            
            # Process
            result = voice_changer.process_file(
                input_file=input_file,
                output_file=output_file,
                method='silero',
                voice_model='kseniya',
                preserve_quality=True,
                preserve_background=config['preserve_background'],
                use_parallel=config['enable_parallel']
            )
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Clean up
            voice_changer.cleanup()
            
            # Store results
            results.append({
                'name': config['name'],
                'duration': duration,
                'output': output_file,
                'success': result.get('success', False)
            })
            
            print(f"\n✅ Test completed in {duration:.2f} seconds")
            print(f"   Output: {output_file}")
            
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            results.append({
                'name': config['name'],
                'duration': 0,
                'output': None,
                'success': False,
                'error': str(e)
            })
    
    # Print summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"\n{status} {result['name']}")
        print(f"   Duration: {result['duration']:.2f}s")
        if result.get('output'):
            print(f"   Output: {result['output']}")
        if result.get('error'):
            print(f"   Error: {result['error']}")
    
    # Calculate speedup
    if len(results) >= 2 and results[0]['success'] and results[1]['success']:
        sequential_time = results[0]['duration']
        parallel_time = results[1]['duration']
        speedup = sequential_time / parallel_time if parallel_time > 0 else 0
        
        print(f"\n📊 SPEEDUP ANALYSIS:")
        print(f"   Sequential: {sequential_time:.2f}s")
        print(f"   Parallel:   {parallel_time:.2f}s")
        print(f"   Speedup:    {speedup:.2f}x")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


def test_parallel_processor_only():
    """Test parallel processor component in isolation"""
    
    print("=" * 80)
    print("PARALLEL PROCESSOR COMPONENT TEST")
    print("=" * 80)
    
    from core.utils.parallel_voice_processor import ParallelVoiceProcessor
    
    input_file = "data/content/audio/input.mp3"
    output_dir = "data/content/processed/parallel_test"
    
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return
    
    # Create processor
    processor = ParallelVoiceProcessor(
        chunk_duration_minutes=5,
        max_workers=4
    )
    
    # Test 1: Split audio
    print("\n📋 Test 1: Splitting audio into chunks...")
    chunks = processor.split_audio(input_file)
    print(f"   ✅ Created {len(chunks)} chunks")
    for chunk in chunks:
        print(f"      - Chunk {chunk['index']}: {chunk['duration']:.2f}s")
    
    # Test 2: Process chunks (simple passthrough)
    print("\n📋 Test 2: Processing chunks (passthrough)...")
    
    def passthrough_processor(input_path: str, output_path: str):
        """Simple passthrough for testing"""
        import shutil
        shutil.copy(input_path, output_path)
        return {'success': True}
    
    processed_chunks = processor.process_chunks_parallel(
        chunks,
        passthrough_processor
    )
    print(f"   ✅ Processed {len(processed_chunks)} chunks")
    
    # Test 3: Reassemble
    print("\n📋 Test 3: Reassembling chunks...")
    output_file = os.path.join(output_dir, "reassembled.wav")
    result = processor.reassemble_chunks(processed_chunks, output_file)
    print(f"   ✅ Reassembled: {result}")
    
    # Cleanup
    processor.cleanup()
    
    print("\n✅ Component test complete!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test parallel voice processing")
    parser.add_argument(
        '--mode',
        choices=['full', 'component'],
        default='full',
        help='Test mode: full (complete pipeline) or component (processor only)'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'component':
        test_parallel_processor_only()
    else:
        test_parallel_processing()

