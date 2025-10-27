"""
RVC-based Voice Changer Module
Uses AI-based voice conversion for realistic voice transformation
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Literal
import tempfile
import numpy as np

try:
    import torch
    import torchaudio
except ImportError:
    raise ImportError("PyTorch is required. Install with: pip install torch torchaudio")

try:
    import soundfile as sf
except ImportError:
    raise ImportError("soundfile is required. Install with: pip install soundfile")

try:
    import librosa
except ImportError:
    raise ImportError("librosa is required. Install with: pip install librosa")

try:
    from scipy import signal
except ImportError:
    raise ImportError("scipy is required. Install with: pip install scipy")

try:
    import pyworld as pw
except ImportError:
    raise ImportError("pyworld is required. Install with: pip install pyworld")

try:
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip
    except (ImportError, AttributeError):
        from moviepy import VideoFileClip, AudioFileClip
except ImportError:
    raise ImportError("moviepy is required. Install with: pip install moviepy")

from core.utils.logger import get_logger
from core.voice.rvc.model_manager import RVCModelManager
from core.voice.rvc.inference import RVCInference
from core.voice.rvc.sovits import SoVITSConverter
from core.voice.silero import SileroVoiceChanger
from core.voice.parallel import ParallelVoiceProcessor
from core.voice.mixer import AudioBackgroundMixer

logger = get_logger(__name__)


class VoiceChanger:
    """
    RVC-based Voice Changer with AI voice conversion
    """
    
    # Voice conversion presets
    VOICE_PRESETS = {
        'male_to_female': {
            'pitch_shift': 6,  # semitones
            'formant_shift': 1.4,
            'f0_method': 'crepe',
            'description': 'Convert male voice to female (AI-based)'
        },
        'female_to_male': {
            'pitch_shift': -6,
            'formant_shift': 0.7,
            'f0_method': 'crepe',
            'description': 'Convert female voice to male (AI-based)'
        },
        'male_to_child': {
            'pitch_shift': 8,
            'formant_shift': 1.5,
            'f0_method': 'crepe',
            'description': 'Convert male voice to child'
        },
        'female_to_child': {
            'pitch_shift': 6,
            'formant_shift': 1.4,
            'f0_method': 'crepe',
            'description': 'Convert female voice to child'
        },
        'dramatic_change': {
            'pitch_shift': 10,
            'formant_shift': 1.6,
            'f0_method': 'crepe',
            'description': 'Extreme voice transformation'
        }
    }
    
    def __init__(
        self, 
        temp_dir: Optional[str] = None, 
        device: Optional[str] = None,
        enable_parallel: bool = True,
        chunk_duration_minutes: int = 5,
        max_workers: Optional[int] = None
    ):
        """
        Initialize RVC Voice Changer
        
        Args:
            temp_dir: Directory for temporary files
            device: Device for processing ('cpu', 'cuda', or None for auto)
            enable_parallel: Enable parallel processing for faster conversion
            chunk_duration_minutes: Duration of each chunk in minutes (for parallel processing)
            max_workers: Maximum number of parallel workers
        """
        self.temp_dir = temp_dir or tempfile.gettempdir()
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        
        # Auto-detect device
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        # Initialize voice conversion components
        self.model_manager = RVCModelManager()
        self.rvc_inference = RVCInference(self.model_manager, self.device)
        self.sovits_converter = SoVITSConverter(self.device)
        self.silero_changer = SileroVoiceChanger(self.device)
        
        # Initialize parallel processor
        self.enable_parallel = enable_parallel
        if enable_parallel:
            self.parallel_processor = ParallelVoiceProcessor(
                chunk_duration_minutes=chunk_duration_minutes,
                max_workers=max_workers,
                temp_dir=os.path.join(self.temp_dir, 'parallel')
            )
            logger.info(f"Parallel processing enabled: {chunk_duration_minutes}min chunks, {max_workers or 'auto'} workers")
        else:
            self.parallel_processor = None
        
        # Initialize background mixer
        self.background_mixer = AudioBackgroundMixer()
        
        logger.info("Voice Changer initialized with RVC + So-VITS-SVC + Silero")
        logger.info(f"Device: {self.device}")
        logger.info(f"Temp dir: {self.temp_dir}")
    
    def process_file(
        self,
        input_file: str,
        output_file: str,
        conversion_type: str = 'male_to_female',
        pitch_shift: Optional[int] = None,
        formant_shift: Optional[float] = None,
        preserve_quality: bool = True,
        voice_model: Optional[str] = None,
        method: str = 'sovits',
        preserve_background: bool = False,
        use_parallel: bool = None,
        vocals_gain: float = 0.0,
        background_gain: float = -3.0
    ) -> Dict[str, any]:
        """
        Process audio or video file with AI voice conversion
        
        Args:
            input_file: Path to input file
            output_file: Path to output file
            conversion_type: Type of conversion
            pitch_shift: Custom pitch shift in semitones
            formant_shift: Custom formant shift multiplier
            preserve_quality: Preserve maximum quality
            voice_model: Specific RVC voice model to use (e.g., 'female_voice_1')
            method: Conversion method ('sovits', 'silero', 'rvc')
            preserve_background: If True, separate and preserve background music
            use_parallel: If True, use parallel processing (default: auto based on duration)
            vocals_gain: Volume adjustment for vocals in dB (default: 0.0)
            background_gain: Volume adjustment for background in dB (default: -3.0)
            
        Returns:
            Processing results
        """
        logger.info(f"Starting RVC voice conversion: {input_file} -> {output_file}")
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
            # Use Silero for Russian (if specified)
            if method == 'silero':
                # Allow disabling prosody for faster processing
                preserve_prosody = preserve_quality  # Use quality flag for prosody
                
                # Check if we should preserve background
                if preserve_background:
                    return self._process_with_background_preservation(
                        input_file, 
                        output_file, 
                        voice_model or 'kseniya',
                        method='silero',
                        preserve_prosody=preserve_prosody,
                        use_parallel=use_parallel,
                        vocals_gain=vocals_gain,
                        background_gain=background_gain
                    )
                else:
                    return self._process_with_silero(
                        input_file, 
                        output_file, 
                        voice_model or 'kseniya', 
                        preserve_prosody,
                        use_parallel=use_parallel
                    )
            
            if is_video:
                result = self._process_video(
                    input_file, output_file, pitch_shift, formant_shift, preserve_quality, voice_model
                )
            else:
                result = self._process_audio(
                    input_file, output_file, pitch_shift, formant_shift, preserve_quality, voice_model
                )
            
            logger.info(f"RVC voice conversion completed: {output_file}")
            return result
            
        except Exception as e:
            logger.error(f"Error during RVC conversion: {str(e)}")
            raise
    
    def process_text(
        self,
        text: str,
        output_file: str,
        voice: str = 'kseniya',
        sample_rate: int = 48000,
        add_stress: bool = True
    ) -> Dict[str, any]:
        """
        Process text directly to audio using Silero TTS
        
        This method synthesizes text into speech without requiring source audio.
        Useful for creating voiceovers, narrations, or converting text to voice.
        
        Args:
            text: Input text to synthesize
            output_file: Path to output audio file
            voice: Target Silero voice (aidar, baya, kseniya, eugene, etc.)
            sample_rate: Output sample rate (default: 48000)
            add_stress: Add Russian stress marks for better pronunciation
            
        Returns:
            Processing results with text, voice, and output file
        
        Example:
            >>> changer = VoiceChanger()
            >>> result = changer.process_text(
            ...     text="Привет, это тест синтеза голоса",
            ...     output_file="output.wav",
            ...     voice="kseniya"
            ... )
        """
        logger.info(f"Processing text to audio:")
        logger.info(f"  Text length: {len(text)} characters")
        logger.info(f"  Output: {output_file}")
        logger.info(f"  Voice: {voice}")
        
        # Use SileroVoiceChanger for text-to-speech
        result = self.silero_changer.synthesize_text_to_audio(
            text=text,
            output_file=output_file,
            target_voice=voice,
            sample_rate=sample_rate,
            add_stress=add_stress
        )
        
        logger.info(f"Text-to-speech processing completed: {output_file}")
        return result
    
    def _process_video(
        self,
        input_file: str,
        output_file: str,
        pitch_shift: int,
        formant_shift: float,
        preserve_quality: bool,
        voice_model: Optional[str] = None
    ) -> Dict[str, any]:
        """Process video file"""
        logger.info("Processing video file...")
        
        temp_audio_original = os.path.join(self.temp_dir, "temp_audio_original.wav")
        temp_audio_converted = os.path.join(self.temp_dir, "temp_audio_converted.wav")
        
        try:
            # Extract audio
            logger.info("Extracting audio from video...")
            video_clip = VideoFileClip(input_file)
            video_clip.audio.write_audiofile(temp_audio_original, codec='pcm_s16le')
            
            fps = video_clip.fps
            duration = video_clip.duration
            size = video_clip.size
            
            # Convert voice
            logger.info("Converting voice with RVC...")
            self._convert_voice_rvc(
                temp_audio_original,
                temp_audio_converted,
                pitch_shift,
                formant_shift,
                voice_model
            )
            
            # Merge back
            logger.info("Merging converted audio with video...")
            new_audio = AudioFileClip(temp_audio_converted)
            final_video = video_clip.set_audio(new_audio)
            
            final_video.write_videofile(
                output_file,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(self.temp_dir, 'temp-audio.m4a'),
                remove_temp=True,
                preset='slow' if preserve_quality else 'medium',
                bitrate='8000k' if preserve_quality else '5000k'
            )
            
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
                'formant_shift': formant_shift,
                'method': 'RVC'
            }
            
        finally:
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
        pitch_shift: int,
        formant_shift: float,
        preserve_quality: bool,
        voice_model: Optional[str] = None
    ) -> Dict[str, any]:
        """Process audio file"""
        logger.info("Processing audio file...")
        
        duration = self._convert_voice_rvc(
            input_file,
            output_file,
            pitch_shift,
            formant_shift,
            voice_model
        )
        
        return {
            'success': True,
            'output_file': output_file,
            'type': 'audio',
            'duration': duration,
            'pitch_shift': pitch_shift,
            'formant_shift': formant_shift,
            'method': 'RVC'
        }
    
    def _convert_voice_rvc(
        self,
        input_file: str,
        output_file: str,
        pitch_shift: int,
        formant_shift: float,
        voice_model: Optional[str] = None
    ) -> float:
        """
        Convert voice using RVC with voice models
        
        Uses:
        - RVC inference engine with voice models
        - WORLD vocoder for feature extraction
        - Model-based voice characteristics
        """
        logger.info(f"RVC conversion: pitch={pitch_shift}, formant={formant_shift}, model={voice_model}")
        
        # Load audio
        audio, sr = librosa.load(input_file, sr=None, mono=True)
        audio = audio.astype(np.float64)
        duration = len(audio) / sr
        
        logger.info(f"Loaded audio: {duration:.2f}s, {sr}Hz")
        
        # Use voice model if specified (So-VITS-SVC for better quality)
        if voice_model:
            logger.info(f"Using So-VITS-SVC with model: {voice_model}")
            audio_converted, sr = self.sovits_converter.convert_voice(
                audio, sr, 
                target_voice=voice_model,
                f0_method='harvest',
                pitch_shift=pitch_shift,
                cluster_ratio=0.5  # Balance between source and target
            )
            sf.write(output_file, audio_converted, sr)
            logger.info(f"So-VITS-SVC conversion completed: {output_file}")
            return duration
        
        # Extract F0 (pitch), spectral envelope, and aperiodicity using WORLD
        logger.info("Extracting features with WORLD vocoder...")
        f0, sp, ap = self._world_decompose(audio, sr)
        
        # Modify pitch
        logger.info(f"Applying pitch shift: {pitch_shift} semitones...")
        f0_shifted = self._shift_pitch(f0, pitch_shift)
        
        # Modify formants (spectral envelope)
        logger.info(f"Applying formant shift: {formant_shift}x...")
        sp_shifted = self._shift_formants(sp, formant_shift, sr)
        
        # Synthesize modified audio
        logger.info("Synthesizing modified audio...")
        audio_modified = pw.synthesize(
            f0_shifted.astype(np.float64),
            sp_shifted.astype(np.float64),
            ap.astype(np.float64),
            sr,
            frame_period=5.0
        )
        
        # Normalize
        audio_modified = audio_modified / np.max(np.abs(audio_modified)) * 0.9
        
        # Save
        sf.write(output_file, audio_modified, sr)
        logger.info(f"RVC conversion completed: {output_file}")
        
        return duration
    
    def _world_decompose(self, audio: np.ndarray, sr: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Decompose audio using WORLD vocoder"""
        # Convert to double precision
        audio = audio.astype(np.float64)
        
        # Extract F0 (pitch)
        f0, t = pw.dio(audio, sr, frame_period=5.0)
        f0 = pw.stonemask(audio, f0, t, sr)
        
        # Extract spectral envelope
        sp = pw.cheaptrick(audio, f0, t, sr)
        
        # Extract aperiodicity
        ap = pw.d4c(audio, f0, t, sr)
        
        return f0, sp, ap
    
    def _shift_pitch(self, f0: np.ndarray, semitones: int) -> np.ndarray:
        """Shift pitch by semitones"""
        factor = 2 ** (semitones / 12.0)
        f0_shifted = f0.copy()
        # Only shift non-zero F0 values (voiced regions)
        voiced = f0 > 0
        f0_shifted[voiced] = f0[voiced] * factor
        return f0_shifted
    
    def _shift_formants(self, sp: np.ndarray, ratio: float, sr: int) -> np.ndarray:
        """
        Shift formants by modifying spectral envelope
        Uses frequency warping technique
        """
        # Get frequency bins
        n_fft = (sp.shape[1] - 1) * 2
        freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
        
        # Create warping function
        # ratio > 1.0: shift formants up (female/child)
        # ratio < 1.0: shift formants down (male)
        warped_freqs = freqs * ratio
        
        # Interpolate spectral envelope
        sp_shifted = np.zeros_like(sp)
        for i in range(sp.shape[0]):
            # Interpolate in log domain for better results
            sp_log = np.log(sp[i] + 1e-7)
            sp_shifted[i] = np.exp(np.interp(freqs, warped_freqs, sp_log, left=sp_log[0], right=sp_log[-1]))
        
        return sp_shifted
    
    def batch_process(
        self,
        input_files: list,
        output_dir: str,
        conversion_type: str = 'male_to_female',
        **kwargs
    ) -> Dict[str, any]:
        """Batch process multiple files"""
        logger.info(f"Starting RVC batch processing of {len(input_files)} files")
        
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
                output_file = os.path.join(output_dir, f"rvc_converted_{filename}")
                
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
        
        logger.info(f"RVC batch processing completed: {results['successful']} successful, {results['failed']} failed")
        return results
    
    def _process_with_silero(
        self,
        input_file: str,
        output_file: str,
        voice: str,
        preserve_prosody: bool = False,
        use_parallel: bool = None
    ) -> Dict[str, any]:
        """Process with Silero TTS (for Russian)"""
        logger.info(f"Processing with Silero TTS (Russian), preserve_prosody={preserve_prosody}")
        
        # Determine if we should use parallel processing
        if use_parallel is None:
            use_parallel = self.enable_parallel
        
        # Check audio duration to decide if parallel processing is worth it
        if use_parallel and self.parallel_processor:
            try:
                # Use librosa to get duration (works with any format)
                duration_seconds = librosa.get_duration(path=input_file)
                
                # Only use parallel if duration > 3 minutes
                if duration_seconds > 180:
                    logger.info(f"Audio duration: {duration_seconds/60:.1f} minutes - using parallel multiprocessing")
                    return self._process_with_silero_parallel(input_file, output_file, voice, preserve_prosody)
                else:
                    logger.info(f"Audio duration: {duration_seconds/60:.1f} minutes - using sequential processing")
            except Exception as e:
                logger.warning(f"Could not determine duration: {e}, defaulting to parallel")
        
        result = self.silero_changer.convert_voice(
            input_file,
            output_file,
            target_voice=voice,
            sample_rate=48000,
            preserve_prosody=preserve_prosody
        )
        
        return result
    
    def _process_with_silero_parallel(
        self,
        input_file: str,
        output_file: str,
        voice: str,
        preserve_prosody: bool = False
    ) -> Dict[str, any]:
        """Process with Silero TTS using parallel chunks with multiprocessing"""
        logger.info("=" * 70)
        logger.info("PARALLEL SILERO PROCESSING (MULTIPROCESSING)")
        logger.info("=" * 70)
        
        # Prepare processor parameters for multiprocessing
        processor_params = {
            'voice': voice,
            'sample_rate': 48000,
            'preserve_prosody': preserve_prosody,
            'device': self.device
        }
        
        # Use parallel processor with true multiprocessing
        result_file = self.parallel_processor.process_with_background(
            input_file=input_file,
            output_file=output_file,
            voice_processor_func=None,  # Use multiprocessing mode
            background_separator_func=None,
            vocals_gain=0.0,
            background_gain=-3.0,
            processor_params=processor_params,
            use_processes=True  # TRUE PARALLELISM!
        )
        
        logger.info("=" * 70)
        logger.info("PARALLEL SILERO PROCESSING COMPLETE (MULTIPROCESSING)")
        logger.info("=" * 70)
        
        return {
            'success': True,
            'output_file': result_file,
            'voice': voice,
            'method': 'Silero TTS (Parallel Multiprocessing)'
        }
    
    def _process_with_background_preservation(
        self,
        input_file: str,
        output_file: str,
        voice: str,
        method: str = 'silero',
        preserve_prosody: bool = False,
        use_parallel: bool = None,
        vocals_gain: float = 0.0,
        background_gain: float = -3.0
    ) -> Dict[str, any]:
        """
        Process with background music preservation
        
        Pipeline:
        1. Separate vocals from background
        2. Split vocals into chunks (if parallel enabled)
        3. Process chunks in parallel
        4. Reassemble chunks
        5. Mix with original background
        """
        logger.info("=" * 70)
        logger.info("VOICE PROCESSING WITH BACKGROUND PRESERVATION")
        logger.info("=" * 70)
        
        # Determine if we should use parallel processing
        if use_parallel is None:
            use_parallel = self.enable_parallel
        
        # Prepare processor parameters for multiprocessing
        processor_params = {
            'voice': voice,
            'sample_rate': 48000,
            'preserve_prosody': preserve_prosody,
            'device': self.device
        }
        
        # Create background separator function
        def separate_background(audio_file: str, temp_dir: str) -> Tuple[str, str]:
            """Separate vocals from background"""
            return self.background_mixer.separate_vocals(audio_file, temp_dir)
        
        # Use parallel processor if enabled
        if use_parallel and self.parallel_processor:
            # Check duration
            try:
                # Use librosa to get duration (works with any format)
                duration_seconds = librosa.get_duration(path=input_file)
                
                if duration_seconds > 180:  # > 3 minutes
                    logger.info(f"Audio duration: {duration_seconds/60:.1f} minutes - using parallel multiprocessing with background")
                    
                    result_file = self.parallel_processor.process_with_background(
                        input_file=input_file,
                        output_file=output_file,
                        voice_processor_func=None,  # Use multiprocessing
                        background_separator_func=separate_background,
                        vocals_gain=vocals_gain,
                        background_gain=background_gain,
                        processor_params=processor_params,
                        use_processes=True  # TRUE PARALLELISM!
                    )
                    
                    logger.info("=" * 70)
                    logger.info("✅ BACKGROUND PRESERVATION COMPLETE (PARALLEL MULTIPROCESSING)")
                    logger.info("=" * 70)
                    
                    return {
                        'success': True,
                        'output_file': result_file,
                        'voice': voice,
                        'method': f'{method.capitalize()} (Parallel Multiprocessing + Background Preservation)'
                    }
            except Exception as e:
                logger.warning(f"Could not determine duration: {e}, using sequential processing")
        
        # Sequential processing with background preservation
        logger.info("Using sequential processing with background preservation...")
        
        temp_dir = os.path.join(self.temp_dir, 'background_preservation')
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        
        # Step 1: Separate vocals
        logger.info("Step 1: Separating vocals from background...")
        vocals_file, background_file = separate_background(input_file, temp_dir)
        
        # Step 2: Process vocals
        logger.info("Step 2: Processing vocals...")
        processed_vocals = os.path.join(temp_dir, 'processed_vocals.wav')
        
        # Use silero directly for sequential mode
        self.silero_changer.convert_voice(
            vocals_file,
            processed_vocals,
            target_voice=voice,
            sample_rate=48000,
            preserve_prosody=preserve_prosody
        )
        
        # Step 3: Mix with background
        logger.info("Step 3: Mixing with original background...")
        self.background_mixer.mix_audio(
            processed_vocals,
            background_file,
            output_file,
            vocals_gain=vocals_gain,
            background_gain=background_gain
        )
        
        logger.info("=" * 70)
        logger.info("✅ BACKGROUND PRESERVATION COMPLETE (SEQUENTIAL)")
        logger.info("=" * 70)
        
        return {
            'success': True,
            'output_file': output_file,
            'voice': voice,
            'method': f'{method.capitalize()} (Sequential + Background Preservation)'
        }
    
    def get_available_presets(self) -> Dict[str, Dict]:
        """Get available RVC voice conversion presets"""
        return self.VOICE_PRESETS.copy()
    
    def get_silero_voices(self) -> Dict[str, Dict]:
        """Get available Silero Russian voices"""
        return self.silero_changer.get_available_voices()
    
    def cleanup(self):
        """Clean up temporary files"""
        if self.parallel_processor:
            self.parallel_processor.cleanup()


# Convenience function
def change_voice(
    input_file: str,
    output_file: str,
    conversion_type: str = 'male_to_female',
    **kwargs
) -> Dict[str, any]:
    """
    Convenience function for RVC voice changing
    
    Args:
        input_file: Path to input file
        output_file: Path to output file
        conversion_type: Type of conversion
        **kwargs: Additional parameters
        
    Returns:
        Processing results
    """
    changer = VoiceChanger()
    return changer.process_file(input_file, output_file, conversion_type, **kwargs)

