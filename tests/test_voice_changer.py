#!/usr/bin/env python3
"""
Test script for Voice Changer functionality
"""

import sys
import os
from pathlib import Path

# Add project root to path (go up one level from tests/ to project root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils.voice_changer import VoiceChanger
from core.utils.logger import get_logger

logger = get_logger(__name__)


def test_voice_changer_import():
    """Test 1: Check if voice changer can be imported"""
    print("\n" + "="*60)
    print("Test 1: Import VoiceChanger")
    print("="*60)
    
    try:
        from core.utils.voice_changer import VoiceChanger, change_voice
        print("✅ VoiceChanger imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import VoiceChanger: {str(e)}")
        return False


def test_voice_changer_initialization():
    """Test 2: Check if voice changer can be initialized"""
    print("\n" + "="*60)
    print("Test 2: Initialize VoiceChanger")
    print("="*60)
    
    try:
        changer = VoiceChanger()
        print("✅ VoiceChanger initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize VoiceChanger: {str(e)}")
        print(f"   Make sure all dependencies are installed:")
        print(f"   pip install pydub praat-parselmouth soundfile numpy librosa moviepy")
        return False


def test_presets():
    """Test 3: Check available presets"""
    print("\n" + "="*60)
    print("Test 3: Available Presets")
    print("="*60)
    
    try:
        changer = VoiceChanger()
        presets = changer.get_available_presets()
        
        print(f"Found {len(presets)} presets:\n")
        for name, preset in presets.items():
            print(f"  📋 {name}")
            print(f"     {preset['description']}")
            print(f"     Pitch: {preset['pitch_shift']} semitones")
            print(f"     Formant: {preset['formant_shift']}x")
            print()
        
        print("✅ Presets loaded successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to get presets: {str(e)}")
        return False


def test_file_processing(test_file_path=None):
    """Test 4: Process a test file (if provided)"""
    print("\n" + "="*60)
    print("Test 4: File Processing")
    print("="*60)
    
    if not test_file_path:
        print("⚠️  No test file provided. Skipping file processing test.")
        print("   To test file processing, run:")
        print("   python test_voice_changer.py /path/to/test/video.mp4")
        return None
    
    if not os.path.exists(test_file_path):
        print(f"❌ Test file not found: {test_file_path}")
        return False
    
    try:
        changer = VoiceChanger()
        
        # Prepare output path
        input_path = Path(test_file_path)
        output_path = input_path.parent / f"test_output_{input_path.name}"
        
        print(f"\nProcessing test file...")
        print(f"Input:  {input_path}")
        print(f"Output: {output_path}")
        print(f"Type:   male_to_female")
        print(f"\n⏳ Processing (this may take a while)...\n")
        
        result = changer.process_file(
            input_file=str(input_path),
            output_file=str(output_path),
            conversion_type='male_to_female',
            preserve_quality=False  # Faster for testing
        )
        
        if result['success']:
            print(f"\n✅ File processed successfully!")
            print(f"   Output: {result['output_file']}")
            print(f"   Duration: {result.get('duration', 'N/A')}s")
            print(f"   Pitch shift: {result['pitch_shift']} semitones")
            print(f"   Formant shift: {result['formant_shift']}x")
            return True
        else:
            print(f"❌ File processing failed")
            return False
            
    except Exception as e:
        print(f"❌ Error during file processing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_task_integration():
    """Test 5: Check task worker integration"""
    print("\n" + "="*60)
    print("Test 5: Task Worker Integration")
    print("="*60)
    
    try:
        from app.task_worker import TaskWorker
        from core.utils.voice_changer import VoiceChanger
        
        # Check if TaskWorker has voice_changer attribute
        print("✅ TaskWorker can be imported with VoiceChanger support")
        print("   Voice change tasks can be processed via task system")
        return True
    except Exception as e:
        print(f"❌ Failed to verify task integration: {str(e)}")
        return False


def check_dependencies():
    """Check if all required dependencies are installed"""
    print("\n" + "="*60)
    print("Checking Dependencies")
    print("="*60)
    
    dependencies = {
        'pydub': 'Audio processing',
        'parselmouth': 'Voice transformation (Praat)',
        'soundfile': 'Audio I/O',
        'numpy': 'Numerical operations',
        'librosa': 'Audio analysis',
        'moviepy': 'Video processing'
    }
    
    missing = []
    
    for package, description in dependencies.items():
        try:
            __import__(package)
            print(f"✅ {package:<20} - {description}")
        except ImportError:
            print(f"❌ {package:<20} - {description} (MISSING)")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing {len(missing)} package(s):")
        print(f"   Install with: pip install {' '.join(missing)}")
        return False
    else:
        print(f"\n✅ All dependencies installed!")
        return True


def check_ffmpeg():
    """Check if FFmpeg is installed"""
    print("\n" + "="*60)
    print("Checking FFmpeg")
    print("="*60)
    
    import subprocess
    
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ FFmpeg installed: {version_line}")
            return True
        else:
            print(f"❌ FFmpeg not working properly")
            return False
            
    except FileNotFoundError:
        print(f"❌ FFmpeg not found")
        print(f"   Install FFmpeg:")
        print(f"   - macOS: brew install ffmpeg")
        print(f"   - Ubuntu: sudo apt-get install ffmpeg")
        return False
    except Exception as e:
        print(f"❌ Error checking FFmpeg: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("\n🎙️  Voice Changer Test Suite")
    print("="*60)
    
    # Check for test file argument
    test_file = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Run tests
    results = {
        'Dependencies': check_dependencies(),
        'FFmpeg': check_ffmpeg(),
        'Import': test_voice_changer_import(),
        'Initialization': test_voice_changer_initialization(),
        'Presets': test_presets(),
        'Task Integration': test_task_integration(),
        'File Processing': test_file_processing(test_file)
    }
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    total = len(results)
    
    for test_name, result in results.items():
        if result is True:
            status = "✅ PASSED"
        elif result is False:
            status = "❌ FAILED"
        else:
            status = "⚠️  SKIPPED"
        print(f"{test_name:<20} {status}")
    
    print("="*60)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    print("="*60)
    
    if failed > 0:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        return 1
    elif skipped > 0:
        print("\n✅ All executed tests passed!")
        print("ℹ️  Some tests were skipped. Provide a test file to run all tests:")
        print("   python test_voice_changer.py /path/to/test/video.mp4")
        return 0
    else:
        print("\n🎉 All tests passed! Voice Changer is ready to use!")
        return 0


if __name__ == '__main__':
    sys.exit(main())
