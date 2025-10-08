"""
Voice Changer Module
Provides functionality to change voice characteristics in audio/video files
Supports male-to-female, female-to-male voice conversion
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Literal
import tempfile
import shutil

try:
    from pydub import AudioSegment
    from pydub.effects import normalize
except ImportError:
    raise ImportError("pydub is required. Install with: pip install pydub")

try:
    import parselmouth
    from parselmouth.praat import call
except ImportError:
    raise ImportError("praat-parselmouth is required. Install with: pip install praat-parselmouth")

try:
    import soundfile as sf
except ImportError:
    raise ImportError("soundfile is required. Install with: pip install soundfile")

try:
    import numpy as np
except ImportError:
    raise ImportError("numpy is required. Install with: pip install numpy")

try:
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip
    except (ImportError, AttributeError):
        # Fallback for moviepy 2.x
        from moviepy import VideoFileClip, AudioFileClip
except ImportError:
    raise ImportError("moviepy is required. Install with: pip install moviepy")

from core.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceChanger:
    """
    Voice changer class that modifies voice characteristics in audio/video files
    """
    
    # Voice conversion presets
    VOICE_PRESETS = {
        'male_to_female': {
            'pitch_shift': 6.0,  # semitones - более драматично
            'formant_shift': 1.4,  # более агрессивно
            'description': 'Convert male voice to female (dramatic change)'
        },
        'female_to_male': {
            'pitch_shift': -6.0,  # semitones - более драматично
            'formant_shift': 0.7,  # более агрессивно
            'description': 'Convert female voice to male (dramatic change)'
        },
        'male_to_child': {
            'pitch_shift': 8.0,  # очень высокий
            'formant_shift': 1.5,
            'description': 'Convert male voice to child'
        },
        'female_to_child': {
            'pitch_shift': 6.0,
            'formant_shift': 1.4,
            'description': 'Convert female voice to child'
        },
        'robot': {
            'pitch_shift': 0,
            'formant_shift': 0.8,
            'description': 'Robot-like voice'
        },
        'deep_voice': {
            'pitch_shift': -8.0,
            'formant_shift': 0.6,
            'description': 'Very deep voice'
        }
    }
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        Initialize voice changer
        
        Args:
            temp_dir: Directory for temporary files (optional)
        """
        self.temp_dir = temp_dir or tempfile.gettempdir()
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"VoiceChanger initialized with temp dir: {self.temp_dir}")
    
    def process_file(
        self,
        input_file: str,
        output_file: str,
        conversion_type: Literal['male_to_female', 'female_to_male', 'male_to_child', 'female_to_child'] = 'male_to_female',
        pitch_shift: Optional[float] = None,
        formant_shift: Optional[float] = None,
        preserve_quality: bool = True
    ) -> Dict[str, any]:
        """
        Process audio or video file with voice conversion
        
        Args:
            input_file: Path to input audio/video file
            output_file: Path to output file
            conversion_type: Type of voice conversion preset
            pitch_shift: Custom pitch shift in semitones (overrides preset)
            formant_shift: Custom formant shift multiplier (overrides preset)
            preserve_quality: Whether to preserve maximum quality
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting voice conversion: {input_file} -> {output_file}")
        logger.info(f"Conversion type: {conversion_type}")
        
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        # Get preset values
        preset = self.VOICE_PRESETS.get(conversion_type, self.VOICE_PRESETS['male_to_female'])
        pitch_shift = pitch_shift if pitch_shift is not None else preset['pitch_shift']
        formant_shift = formant_shift if formant_shift is not None else preset['formant_shift']
        
        # Determine if input is video or audio
        file_ext = os.path.splitext(input_file)[1].lower()
        is_video = file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']
        
        try:
            if is_video:
                result = self._process_video(
                    input_file, output_file, pitch_shift, formant_shift, preserve_quality
                )
            else:
                result = self._process_audio(
                    input_file, output_file, pitch_shift, formant_shift, preserve_quality
                )
            
            logger.info(f"Voice conversion completed successfully: {output_file}")
            return result
            
        except Exception as e:
            logger.error(f"Error during voice conversion: {str(e)}")
            raise
    
    def _process_video(
        self,
        input_file: str,
        output_file: str,
        pitch_shift: float,
        formant_shift: float,
        preserve_quality: bool
    ) -> Dict[str, any]:
        """
        Process video file by extracting audio, converting voice, and merging back
        
        Args:
            input_file: Path to input video file
            output_file: Path to output video file
            pitch_shift: Pitch shift in semitones
            formant_shift: Formant shift multiplier
            preserve_quality: Whether to preserve maximum quality
            
        Returns:
            Processing results dictionary
        """
        logger.info("Processing video file...")
        
        # Create temporary files
        temp_audio_original = os.path.join(self.temp_dir, "temp_audio_original.wav")
        temp_audio_converted = os.path.join(self.temp_dir, "temp_audio_converted.wav")
        
        try:
            # Extract audio from video
            logger.info("Extracting audio from video...")
            video_clip = VideoFileClip(input_file)
            video_clip.audio.write_audiofile(
                temp_audio_original,
                codec='pcm_s16le'
            )
            
            # Get video properties
            fps = video_clip.fps
            duration = video_clip.duration
            size = video_clip.size
            
            # Convert voice in extracted audio
            logger.info("Converting voice in audio track...")
            self._convert_voice(
                temp_audio_original,
                temp_audio_converted,
                pitch_shift,
                formant_shift,
                preserve_quality
            )
            
            # Create new video with converted audio
            logger.info("Merging converted audio with video...")
            new_audio = AudioFileClip(temp_audio_converted)
            final_video = video_clip.set_audio(new_audio)
            
            # Write output video
            final_video.write_videofile(
                output_file,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(self.temp_dir, 'temp-audio.m4a'),
                remove_temp=True,
                preset='slow' if preserve_quality else 'medium',
                bitrate='8000k' if preserve_quality else '5000k'
            )
            
            # Clean up
            video_clip.close()
            new_audio.close()
            final_video.close()
            
            return {
                'success': True,
                'output_file': output_file,
                'type': 'video',
                'duration': duration,
                'fps': fps,
                'size': size,
                'pitch_shift': pitch_shift,
                'formant_shift': formant_shift
            }
            
        finally:
            # Clean up temporary files
            for temp_file in [temp_audio_original, temp_audio_converted]:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
    
    def _process_audio(
        self,
        input_file: str,
        output_file: str,
        pitch_shift: float,
        formant_shift: float,
        preserve_quality: bool
    ) -> Dict[str, any]:
        """
        Process audio file with voice conversion
        
        Args:
            input_file: Path to input audio file
            output_file: Path to output audio file
            pitch_shift: Pitch shift in semitones
            formant_shift: Formant shift multiplier
            preserve_quality: Whether to preserve maximum quality
            
        Returns:
            Processing results dictionary
        """
        logger.info("Processing audio file...")
        
        # Convert voice
        duration = self._convert_voice(
            input_file,
            output_file,
            pitch_shift,
            formant_shift,
            preserve_quality
        )
        
        return {
            'success': True,
            'output_file': output_file,
            'type': 'audio',
            'duration': duration,
            'pitch_shift': pitch_shift,
            'formant_shift': formant_shift
        }
    
    def _convert_voice(
        self,
        input_file: str,
        output_file: str,
        pitch_shift: float,
        formant_shift: float,
        preserve_quality: bool
    ) -> float:
        """
        Convert voice using Praat (Parselmouth)
        
        Args:
            input_file: Path to input audio file
            output_file: Path to output audio file
            pitch_shift: Pitch shift in semitones
            formant_shift: Formant shift multiplier
            preserve_quality: Whether to preserve maximum quality
            
        Returns:
            Duration of processed audio
        """
        logger.info(f"Converting voice with pitch_shift={pitch_shift}, formant_shift={formant_shift}")
        
        # Load audio with Parselmouth
        sound = parselmouth.Sound(input_file)
        duration = sound.duration
        
        # Get pitch factor (2^(semitones/12))
        pitch_factor = 2 ** (pitch_shift / 12.0)
        
        logger.info(f"Pitch factor: {pitch_factor}")
        logger.info(f"Formant shift: {formant_shift}")
        
        # Strategy: Use resampling to shift both pitch and formants together
        # This is simple and very reliable
        
        # Step 1: Change pitch using PSOLA (keeps formants)
        pitch_floor = 75
        pitch_ceiling = 600
        
        # Create manipulation object
        manipulation = call(sound, "To Manipulation", 0.01, pitch_floor, pitch_ceiling)
        
        # Extract and modify pitch
        pitch_tier = call(manipulation, "Extract pitch tier")
        call(pitch_tier, "Multiply frequencies", sound.xmin, sound.xmax, pitch_factor)
        call([pitch_tier, manipulation], "Replace pitch tier")
        
        # Synthesize with new pitch
        sound_pitch_shifted = call(manipulation, "Get resynthesis (overlap-add)")
        
        logger.info("Applied pitch shift using PSOLA")
        
        # Step 2: Apply formant shift if needed
        if abs(formant_shift - 1.0) > 0.01:  # Only if significantly different from 1.0
            # Change formants by resampling
            # When we resample, formant frequencies change proportionally
            original_rate = sound_pitch_shifted.sampling_frequency
            
            # Resample to shift formants
            # Higher sample rate = higher formant frequencies
            new_rate = original_rate * formant_shift
            
            # Resample to new rate (this shifts formants)
            sound_resampled = sound_pitch_shifted.resample(new_rate)
            
            # Resample back to original rate to maintain compatibility
            sound_modified = sound_resampled.resample(original_rate)
            
            logger.info(f"Applied formant shift via resampling: {formant_shift}x")
        else:
            sound_modified = sound_pitch_shifted
            logger.info("Skipped formant shift (formant_shift ~= 1.0)")
        
        # Normalize to prevent clipping and maintain consistent volume
        # Note: scale_intensity modifies in place, doesn't return new object
        try:
            # Use Scale intensity command
            sound_final = call(sound_modified, "Scale intensity", 70)
            if sound_final is None:
                # If it returns None, use the original
                sound_final = sound_modified
                logger.info("Using original sound (scale_intensity returned None)")
            else:
                logger.info("Applied intensity scaling")
        except:
            # If scaling fails, just use the sound as is
            sound_final = sound_modified
            logger.info("Skipped intensity scaling")
        
        # Save the result
        sound_final.save(output_file, 'WAV')
        
        logger.info(f"Voice conversion completed. Duration: {duration}s")
        
        return duration
    
    def batch_process(
        self,
        input_files: list,
        output_dir: str,
        conversion_type: str = 'male_to_female',
        **kwargs
    ) -> Dict[str, any]:
        """
        Process multiple files in batch
        
        Args:
            input_files: List of input file paths
            output_dir: Output directory for processed files
            conversion_type: Type of voice conversion
            **kwargs: Additional arguments for process_file
            
        Returns:
            Batch processing results
        """
        logger.info(f"Starting batch processing of {len(input_files)} files")
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        results = {
            'total': len(input_files),
            'successful': 0,
            'failed': 0,
            'files': []
        }
        
        for input_file in input_files:
            try:
                filename = os.path.basename(input_file)
                output_file = os.path.join(output_dir, f"converted_{filename}")
                
                result = self.process_file(
                    input_file,
                    output_file,
                    conversion_type,
                    **kwargs
                )
                
                results['successful'] += 1
                results['files'].append({
                    'input': input_file,
                    'output': output_file,
                    'status': 'success',
                    'result': result
                })
                
            except Exception as e:
                logger.error(f"Failed to process {input_file}: {str(e)}")
                results['failed'] += 1
                results['files'].append({
                    'input': input_file,
                    'output': None,
                    'status': 'failed',
                    'error': str(e)
                })
        
        logger.info(f"Batch processing completed: {results['successful']} successful, {results['failed']} failed")
        return results
    
    def get_available_presets(self) -> Dict[str, Dict]:
        """
        Get available voice conversion presets
        
        Returns:
            Dictionary of available presets
        """
        return self.VOICE_PRESETS.copy()


# Convenience function
def change_voice(
    input_file: str,
    output_file: str,
    conversion_type: str = 'male_to_female',
    **kwargs
) -> Dict[str, any]:
    """
    Convenience function to change voice in a file
    
    Args:
        input_file: Path to input file
        output_file: Path to output file
        conversion_type: Type of conversion ('male_to_female', 'female_to_male', etc.)
        **kwargs: Additional parameters
        
    Returns:
        Processing results
    """
    changer = VoiceChanger()
    return changer.process_file(input_file, output_file, conversion_type, **kwargs)
