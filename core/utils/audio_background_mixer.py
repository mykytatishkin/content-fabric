"""
Audio Background Mixer

Separates voice from background (music/effects) and mixes new voice with original background.
"""

import os
import tempfile
from typing import Optional, Tuple
from pydub import AudioSegment
from audio_separator.separator import Separator

from core.utils.logger import get_logger

logger = get_logger(__name__)


class AudioBackgroundMixer:
    """
    Separates voice from background and mixes processed voice with original background
    """
    
    def __init__(self, model_name: str = 'UVR-MDX-NET-Inst_HQ_3'):
        """
        Initialize Audio Background Mixer
        
        Args:
            model_name: Model to use for separation
                - 'UVR-MDX-NET-Inst_HQ_3' - Best quality (default)
                - 'UVR_MDXNET_KARA_2' - Faster
                - 'Kim_Vocal_2' - Good balance
        """
        self.model_name = model_name
        self.separator = None
        logger.info(f"Audio Background Mixer initialized with model: {model_name}")
    
    def separate_vocals(
        self,
        input_file: str,
        output_dir: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Separate vocals from background
        
        Args:
            input_file: Input audio file
            output_dir: Directory to save separated files
            
        Returns:
            Tuple of (vocals_file, background_file)
        """
        if output_dir is None:
            output_dir = tempfile.mkdtemp()
        
        os.makedirs(output_dir, exist_ok=True)
        
        logger.info(f"Separating vocals from: {input_file}")
        logger.info(f"Using model: {self.model_name}")
        
        # Initialize separator
        if self.separator is None:
            self.separator = Separator(
                log_level=30,  # WARNING level (10=DEBUG, 20=INFO, 30=WARNING)
                model_file_dir=os.path.join(os.path.expanduser('~'), '.audio-separator', 'models'),
                output_dir=output_dir  # Set output directory
            )
        
        # Load model (will auto-download if not present)
        try:
            self.separator.load_model(model_filename=self.model_name)
        except Exception as e:
            logger.warning(f"Could not load model {self.model_name}: {e}")
            logger.info("Trying to download model...")
            # Try with .pth extension
            if not self.model_name.endswith('.pth'):
                try:
                    self.separator.load_model(model_filename=f"{self.model_name}.pth")
                except:
                    # Try alternative model names
                    logger.info("Using default model: UVR_MDXNET_KARA_2.onnx")
                    self.separator.load_model(model_filename="UVR_MDXNET_KARA_2.onnx")
        
        # Separate (audio-separator 0.39.0 API)
        output_files = self.separator.separate(input_file)
        
        # Find vocals and instrumental files
        vocals_file = None
        instrumental_file = None
        
        for file in output_files:
            # Make sure we have full path
            if not os.path.isabs(file):
                file = os.path.join(output_dir, file)
            
            if 'Vocals' in file or 'vocals' in file:
                vocals_file = file
            elif 'Instrumental' in file or 'instrumental' in file or 'Instrum' in file:
                instrumental_file = file
        
        if not vocals_file or not instrumental_file:
            raise ValueError(f"Could not find vocals/instrumental files in output: {output_files}")
        
        # Verify files exist
        if not os.path.exists(vocals_file):
            # Try to find in output_dir
            vocals_basename = os.path.basename(vocals_file)
            vocals_file = os.path.join(output_dir, vocals_basename)
        
        if not os.path.exists(instrumental_file):
            # Try to find in output_dir
            inst_basename = os.path.basename(instrumental_file)
            instrumental_file = os.path.join(output_dir, inst_basename)
        
        logger.info(f"✅ Vocals separated:")
        logger.info(f"   Vocals: {vocals_file}")
        logger.info(f"   Background: {instrumental_file}")
        
        return vocals_file, instrumental_file
    
    def mix_audio(
        self,
        vocals_file: str,
        background_file: str,
        output_file: str,
        vocals_gain: float = 0.0,
        background_gain: float = 0.0
    ) -> str:
        """
        Mix vocals with background
        
        Args:
            vocals_file: Processed vocals file
            background_file: Original background/instrumental
            output_file: Output mixed file
            vocals_gain: Volume adjustment for vocals (dB)
            background_gain: Volume adjustment for background (dB)
            
        Returns:
            Path to mixed file
        """
        logger.info(f"Mixing audio:")
        logger.info(f"   Vocals: {vocals_file} (gain: {vocals_gain} dB)")
        logger.info(f"   Background: {background_file} (gain: {background_gain} dB)")
        
        # Load audio files
        vocals = AudioSegment.from_file(vocals_file)
        background = AudioSegment.from_file(background_file)
        
        # Apply gain adjustments
        if vocals_gain != 0:
            vocals = vocals + vocals_gain
        
        if background_gain != 0:
            background = background + background_gain
        
        # Match lengths (use longer one)
        if len(vocals) > len(background):
            # Extend background with silence
            silence = AudioSegment.silent(duration=len(vocals) - len(background))
            background = background + silence
        elif len(background) > len(vocals):
            # Extend vocals with silence
            silence = AudioSegment.silent(duration=len(background) - len(vocals))
            vocals = vocals + silence
        
        # Mix (overlay)
        mixed = background.overlay(vocals)
        
        # Export
        mixed.export(output_file, format=os.path.splitext(output_file)[1][1:])
        
        logger.info(f"✅ Mixed audio saved: {output_file}")
        
        return output_file
    
    def process_with_background_preservation(
        self,
        input_file: str,
        voice_processor_func,
        output_file: str,
        vocals_gain: float = 0.0,
        background_gain: float = -3.0,
        temp_dir: Optional[str] = None
    ) -> str:
        """
        Complete pipeline: separate -> process vocals -> mix with background
        
        Args:
            input_file: Original audio file
            voice_processor_func: Function to process vocals (takes input_file, output_file)
            output_file: Final output file
            vocals_gain: Volume adjustment for processed vocals (dB)
            background_gain: Volume adjustment for background (dB, -3 recommended)
            temp_dir: Temporary directory for intermediate files
            
        Returns:
            Path to final mixed file
        """
        logger.info("=" * 60)
        logger.info("Starting Audio Background Preservation Pipeline")
        logger.info("=" * 60)
        
        # Create temp directory
        if temp_dir is None:
            temp_dir = tempfile.mkdtemp(prefix='audio_bg_')
        else:
            os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # Step 1: Separate vocals from background
            logger.info("Step 1: Separating vocals from background...")
            vocals_file, background_file = self.separate_vocals(input_file, temp_dir)
            
            # Step 2: Process vocals (voice change)
            logger.info("Step 2: Processing vocals with voice changer...")
            processed_vocals_file = os.path.join(temp_dir, 'processed_vocals.mp3')
            voice_processor_func(vocals_file, processed_vocals_file)
            
            # Step 3: Mix processed vocals with original background
            logger.info("Step 3: Mixing processed vocals with original background...")
            final_file = self.mix_audio(
                processed_vocals_file,
                background_file,
                output_file,
                vocals_gain=vocals_gain,
                background_gain=background_gain
            )
            
            logger.info("=" * 60)
            logger.info("✅ Background Preservation Complete!")
            logger.info("=" * 60)
            
            return final_file
            
        except Exception as e:
            logger.error(f"Error in background preservation pipeline: {str(e)}")
            raise
        finally:
            # Cleanup temp files (optional - comment out if you want to keep them)
            pass


def get_available_models():
    """Get list of available separation models"""
    return {
        'UVR-MDX-NET-Inst_HQ_3': {
            'description': 'Лучшее качество (рекомендуется)',
            'quality': 'Excellent',
            'speed': 'Slow'
        },
        'UVR_MDXNET_KARA_2': {
            'description': 'Быстрее, хорошее качество',
            'quality': 'Very Good',
            'speed': 'Fast'
        },
        'Kim_Vocal_2': {
            'description': 'Баланс скорости и качества',
            'quality': 'Good',
            'speed': 'Medium'
        }
    }

