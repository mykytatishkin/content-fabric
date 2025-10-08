#!/usr/bin/env python3
"""
Voice Changer CLI Tool
Provides command-line interface for voice changing functionality
"""

import argparse
import sys
import os
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.utils.voice_changer import VoiceChanger
from core.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='RVC Voice Changer - AI-based voice transformation for audio/video files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert male voice to female (AI-based, dramatic change)
  python run_voice_changer.py input.mp4 output.mp4 --type male_to_female
  
  # Convert female voice to male
  python run_voice_changer.py input.wav output.wav --type female_to_male
  
  # Extreme transformation
  python run_voice_changer.py input.mp4 output.mp4 --type dramatic_change
  
  # Custom pitch and formant shift (more extreme = more different)
  python run_voice_changer.py input.mp4 output.mp4 --pitch 10 --formant 1.6
  
  # Batch process multiple files
  python run_voice_changer.py --batch input_dir/ output_dir/ --type male_to_female
  
  # List available presets
  python run_voice_changer.py --list-presets
  
Note: RVC uses AI-based WORLD vocoder for realistic voice transformation.
      Higher values = more dramatic changes. Recommended: pitch 6-10, formant 1.4-1.6
        """
    )
    
    # Main arguments
    parser.add_argument(
        'input',
        nargs='?',
        help='Input audio/video file or directory (for batch mode)'
    )
    parser.add_argument(
        'output',
        nargs='?',
        help='Output audio/video file or directory (for batch mode)'
    )
    
    # Voice conversion options
    parser.add_argument(
        '-t', '--type',
        choices=['male_to_female', 'female_to_male', 'male_to_child', 'female_to_child', 'dramatic_change'],
        default='male_to_female',
        help='Voice conversion type (default: male_to_female, RVC-based)'
    )
    parser.add_argument(
        '-p', '--pitch',
        type=int,
        help='Custom pitch shift in semitones (RVC: 6-12 recommended, overrides preset)'
    )
    parser.add_argument(
        '-f', '--formant',
        type=float,
        help='Custom formant shift multiplier (RVC: 1.4-1.8 recommended, overrides preset)'
    )
    parser.add_argument(
        '--no-preserve-quality',
        action='store_true',
        help='Disable quality preservation (faster but lower quality)'
    )
    
    # Batch processing
    parser.add_argument(
        '-b', '--batch',
        action='store_true',
        help='Batch process all files in input directory'
    )
    parser.add_argument(
        '--pattern',
        default='*',
        help='File pattern for batch mode (e.g., "*.mp4")'
    )
    
    # Information
    parser.add_argument(
        '--list-presets',
        action='store_true',
        help='List available voice conversion presets'
    )
    parser.add_argument(
        '--temp-dir',
        help='Temporary directory for processing (default: system temp)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    # List presets
    if args.list_presets:
        print_presets()
        return 0
    
    # Validate required arguments
    if not args.input or not args.output:
        parser.error("Input and output files/directories are required")
        return 1
    
    try:
        # Initialize voice changer
        changer = VoiceChanger(temp_dir=args.temp_dir)
        
        if args.batch:
            # Batch processing mode
            result = process_batch(changer, args)
        else:
            # Single file processing mode
            result = process_file(changer, args)
        
        print_results(result, args.batch)
        return 0
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        print(f"\n❌ Error: {str(e)}", file=sys.stderr)
        return 1


def process_file(changer: VoiceChanger, args) -> dict:
    """
    Process a single file
    
    Args:
        changer: VoiceChanger instance
        args: Command line arguments
        
    Returns:
        Processing results
    """
    print(f"\n🎙️  Voice Changer")
    print(f"{'='*60}")
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print(f"Type:   {args.type}")
    if args.pitch:
        print(f"Pitch:  {args.pitch} semitones")
    if args.formant:
        print(f"Formant: {args.formant}x")
    print(f"{'='*60}\n")
    
    print("⏳ Processing...")
    
    result = changer.process_file(
        input_file=args.input,
        output_file=args.output,
        conversion_type=args.type,
        pitch_shift=args.pitch,
        formant_shift=args.formant,
        preserve_quality=not args.no_preserve_quality
    )
    
    return result


def process_batch(changer: VoiceChanger, args) -> dict:
    """
    Process multiple files in batch
    
    Args:
        changer: VoiceChanger instance
        args: Command line arguments
        
    Returns:
        Batch processing results
    """
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not input_dir.is_dir():
        raise ValueError(f"Input path is not a directory: {input_dir}")
    
    # Find all matching files
    input_files = list(input_dir.glob(args.pattern))
    
    if not input_files:
        raise ValueError(f"No files found matching pattern: {args.pattern}")
    
    print(f"\n🎙️  Voice Changer - Batch Mode")
    print(f"{'='*60}")
    print(f"Input dir:  {input_dir}")
    print(f"Output dir: {output_dir}")
    print(f"Pattern:    {args.pattern}")
    print(f"Files:      {len(input_files)}")
    print(f"Type:       {args.type}")
    print(f"{'='*60}\n")
    
    print(f"⏳ Processing {len(input_files)} files...\n")
    
    result = changer.batch_process(
        input_files=[str(f) for f in input_files],
        output_dir=str(output_dir),
        conversion_type=args.type,
        pitch_shift=args.pitch,
        formant_shift=args.formant,
        preserve_quality=not args.no_preserve_quality
    )
    
    return result


def print_results(result: dict, is_batch: bool):
    """
    Print processing results
    
    Args:
        result: Processing results dictionary
        is_batch: Whether this was batch processing
    """
    print(f"\n{'='*60}")
    
    if is_batch:
        print(f"✅ Batch Processing Complete!")
        print(f"{'='*60}")
        print(f"Total files:  {result['total']}")
        print(f"Successful:   {result['successful']} ✅")
        print(f"Failed:       {result['failed']} ❌")
        
        if result['failed'] > 0:
            print(f"\n{'='*60}")
            print("Failed files:")
            for file_info in result['files']:
                if file_info['status'] == 'failed':
                    print(f"  ❌ {file_info['input']}: {file_info['error']}")
    else:
        print(f"✅ Voice Conversion Complete!")
        print(f"{'='*60}")
        print(f"Output file: {result['output_file']}")
        print(f"Type:        {result['type']}")
        if 'duration' in result:
            print(f"Duration:    {result['duration']:.2f}s")
        print(f"Pitch shift: {result['pitch_shift']} semitones")
        print(f"Formant:     {result['formant_shift']}x")
    
    print(f"{'='*60}\n")


def print_presets():
    """Print available voice conversion presets"""
    changer = VoiceChanger()
    presets = changer.get_available_presets()
    
    print("\n🎙️  RVC Voice Conversion Presets (AI-based)")
    print(f"{'='*60}\n")
    
    for name, preset in presets.items():
        print(f"📋 {name}")
        print(f"   Description:  {preset['description']}")
        print(f"   Pitch shift:  {preset['pitch_shift']} semitones")
        print(f"   Formant:      {preset['formant_shift']}x")
        print(f"   Method:       {preset.get('f0_method', 'WORLD vocoder')}")
        print()
    
    print(f"{'='*60}")
    print("ℹ️  RVC uses WORLD vocoder for realistic voice transformation")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    sys.exit(main())
