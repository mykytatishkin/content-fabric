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

from core.voice import VoiceChanger
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
  
  # Text-to-speech: synthesize text to audio
  python run_voice_changer.py --text "Привет, это тест" output.wav --voice-model kseniya
  
  # Text-to-speech without stress marks
  python run_voice_changer.py --text "Длинный текст..." output.wav --voice-model eugene --no-stress
  
  # List available presets
  python run_voice_changer.py --list-presets
  
Note: RVC uses AI-based WORLD vocoder for realistic voice transformation.
      Higher values = more dramatic changes. Recommended: pitch 6-10, formant 1.4-1.6
      Text-to-speech mode uses Silero TTS for Russian language synthesis.
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
        '--voice-model',
        type=str,
        help='RVC voice model to use (female_voice_1, male_voice_1, anime_female)'
    )
    parser.add_argument(
        '--list-models',
        action='store_true',
        help='List available RVC voice models'
    )
    parser.add_argument(
        '--method',
        choices=['sovits', 'silero'],
        default='sovits',
        help='Conversion method: sovits (voice-to-voice) or silero (TTS for Russian)'
    )
    parser.add_argument(
        '--list-silero-voices',
        action='store_true',
        help='List available Silero Russian voices'
    )
    parser.add_argument(
        '--preserve-background',
        action='store_true',
        help='Separate voice from background, process only voice, then mix back (keeps music/effects)'
    )
    parser.add_argument(
        '--separation-model',
        type=str,
        default='UVR-MDX-NET-Inst_HQ_3',
        help='Model for voice/background separation (default: UVR-MDX-NET-Inst_HQ_3)'
    )
    parser.add_argument(
        '--vocals-gain',
        type=float,
        default=0.0,
        help='Volume adjustment for processed vocals in dB (default: 0)'
    )
    parser.add_argument(
        '--background-gain',
        type=float,
        default=-3.0,
        help='Volume adjustment for background in dB (default: -3)'
    )
    parser.add_argument(
        '--no-preserve-quality',
        action='store_true',
        help='Disable quality preservation (faster but lower quality)'
    )
    
    # Text-to-speech mode
    parser.add_argument(
        '--text',
        type=str,
        help='Text to synthesize (enters text-to-speech mode, requires --voice-model)'
    )
    parser.add_argument(
        '--text-file',
        type=str,
        help='Read text from file (alternative to --text, requires --voice-model)'
    )
    parser.add_argument(
        '--no-stress',
        action='store_true',
        help='Disable Russian stress marks in text-to-speech mode'
    )
    parser.add_argument(
        '--speed',
        type=float,
        default=1.0,
        help='Speech rate (1.0 = normal, 0.9 = 10%% slower, 1.1 = 10%% faster, default: 1.0)'
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
    
    # List models
    if args.list_models:
        print_models()
        return 0
    
    # List Silero voices
    if args.list_silero_voices:
        print_silero_voices()
        return 0
    
    # Handle text-to-speech mode: output can be first positional arg
    if args.text or args.text_file:
        # Read text from file if --text-file is provided
        if args.text_file:
            try:
                with open(args.text_file, 'r', encoding='utf-8') as f:
                    args.text = f.read()
                print(f"📖 Read {len(args.text):,} characters from: {args.text_file}")
            except Exception as e:
                parser.error(f"Failed to read text file: {e}")
                return 1
        
        # In text mode, 'input' arg is actually the output file
        if args.input and not args.output:
            args.output = args.input
            args.input = None
        if not args.output:
            parser.error("Output file is required when using --text or --text-file")
            return 1
        if not args.voice_model:
            parser.error("--voice-model is required when using --text or --text-file")
            return 1
    else:
        # For normal mode, both input and output are required
        if not args.input or not args.output:
            parser.error("Input and output files/directories are required")
            return 1
    
    try:
        # Initialize voice changer
        changer = VoiceChanger(temp_dir=args.temp_dir)
        
        if args.text:
            # Text-to-speech mode
            result = process_text(changer, args)
            print_results(result, is_batch=False, is_text_mode=True)
        elif args.batch:
            # Batch processing mode
            result = process_batch(changer, args)
            print_results(result, is_batch=True, is_text_mode=False)
        else:
            # Single file processing mode
            result = process_file(changer, args)
            print_results(result, is_batch=False, is_text_mode=False)
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
    print(f"\n🎙️  RVC Voice Changer")
    print(f"{'='*60}")
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print(f"Type:   {args.type}")
    if args.voice_model:
        print(f"Model:  {args.voice_model} (RVC)")
    if args.pitch:
        print(f"Pitch:  {args.pitch} semitones")
    if args.formant:
        print(f"Formant: {args.formant}x")
    if args.preserve_background:
        print(f"Background: Will be preserved ✨")
        print(f"Sep. model: {args.separation_model}")
    print(f"{'='*60}\n")
    
    print("⏳ Processing...")
    
    # Check if we need to preserve background
    if args.preserve_background:
        from core.utils.audio_background_mixer import AudioBackgroundMixer
        
        mixer = AudioBackgroundMixer(model_name=args.separation_model)
        
        # Create voice processor function
        def voice_processor(vocals_file, output_vocals_file):
            changer.process_file(
                input_file=vocals_file,
                output_file=output_vocals_file,
                conversion_type=args.type,
                pitch_shift=args.pitch,
                formant_shift=args.formant,
                preserve_quality=not args.no_preserve_quality,
                voice_model=args.voice_model,
                method=args.method
            )
        
        # Process with background preservation
        mixer.process_with_background_preservation(
            input_file=args.input,
            voice_processor_func=voice_processor,
            output_file=args.output,
            vocals_gain=args.vocals_gain,
            background_gain=args.background_gain
        )
        
        result = {
            'output_file': args.output,
            'method': f'{args.method} + background preservation',
            'voice': args.voice_model,
            'separation_model': args.separation_model
        }
    else:
        # Normal processing without background preservation
        result = changer.process_file(
            input_file=args.input,
            output_file=args.output,
            conversion_type=args.type,
            pitch_shift=args.pitch,
            formant_shift=args.formant,
            preserve_quality=not args.no_preserve_quality,
            voice_model=args.voice_model,
            method=args.method
        )
    
    return result


def process_text(changer: VoiceChanger, args) -> dict:
    """
    Process text to audio using Silero TTS
    
    Args:
        changer: VoiceChanger instance
        args: Command line arguments
        
    Returns:
        Processing results
    """
    print(f"\n🎙️  Text-to-Speech Synthesis")
    print(f"{'='*60}")
    print(f"Text:     {args.text[:80]}..." if len(args.text) > 80 else f"Text:     {args.text}")
    print(f"Output:   {args.output}")
    print(f"Voice:    {args.voice_model}")
    print(f"Speed:    {args.speed:.2f}x ({'+' if args.speed > 1.0 else ''}{int((args.speed - 1.0) * 100)}%)")
    print(f"Stress:   Disabled (Silero handles Russian well)")
    print(f"{'='*60}\n")
    
    print("⏳ Synthesizing...")
    
    # Process text
    result = changer.process_text(
        text=args.text,
        output_file=args.output,
        voice=args.voice_model,
        sample_rate=48000,
        add_stress=False,  # Disabled by default - Silero handles Russian well
        speaking_rate=args.speed
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


def print_results(result: dict, is_batch: bool, is_text_mode: bool = False):
    """
    Print processing results
    
    Args:
        result: Processing results dictionary
        is_batch: Whether this was batch processing
        is_text_mode: Whether this was text-to-speech mode
    """
    print(f"\n{'='*60}")
    
    if is_text_mode:
        print(f"✅ Text-to-Speech Synthesis Complete!")
        print(f"{'='*60}")
        print(f"Output file: {result['output_file']}")
        if 'voice' in result:
            print(f"Voice:       {result['voice']}")
        if 'method' in result:
            print(f"Method:      {result['method']}")
        if 'duration' in result:
            print(f"Duration:    {result['duration']:.2f}s")
        if 'sample_rate' in result:
            print(f"Sample rate: {result['sample_rate']} Hz")
        if 'text' in result and len(result['text']) <= 100:
            print(f"Text:        {result['text']}")
    elif is_batch:
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
        
        # Handle different result formats
        if 'type' in result:
            print(f"Type:        {result['type']}")
        if 'method' in result:
            print(f"Method:      {result['method']}")
        if 'voice' in result:
            print(f"Voice:       {result['voice']}")
        if 'duration' in result:
            print(f"Duration:    {result['duration']:.2f}s")
        if 'pitch_shift' in result:
            print(f"Pitch shift: {result['pitch_shift']} semitones")
        if 'formant_shift' in result:
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


def print_models():
    """Print available RVC voice models"""
    from core.utils.rvc_model_manager import RVCModelManager
    
    manager = RVCModelManager()
    available = manager.list_available_models()
    installed = manager.list_installed_models()
    
    print("\n🎙️  RVC Voice Models")
    print(f"{'='*60}\n")
    
    print("📦 Available Models:\n")
    for model_id, info in available.items():
        is_installed = model_id in installed
        status = "✅ INSTALLED" if is_installed else "⬇️  AVAILABLE"
        
        print(f"  {status} - {model_id}")
        print(f"  Name: {info['name']}")
        print(f"  Type: {info['type']}")
        print(f"  Desc: {info['description']}")
        print()
    
    print(f"{'='*60}")
    print("ℹ️  Use --voice-model MODEL_ID to use a specific model")
    print("   Models download automatically on first use (~300-500 MB each)")
    print(f"{'='*60}\n")


def print_silero_voices():
    """Print available Silero Russian voices"""
    changer = VoiceChanger()
    voices = changer.get_silero_voices()
    
    print("\n🎙️  Silero Russian Voices (Natural TTS)")
    print(f"{'='*60}\n")
    
    for voice_id, info in voices.items():
        print(f"  🇷🇺 {voice_id}")
        print(f"     {info['description']}")
        print(f"     Gender: {info['gender']}")
        print()
    
    print(f"{'='*60}")
    print("ℹ️  Use --method silero --voice-model VOICE_ID")
    print("   Example: python3 run_voice_changer.py --method silero --voice-model kseniya input.mp3 output.mp3")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    sys.exit(main())
