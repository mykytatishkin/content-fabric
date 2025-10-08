"""
Silero TTS Voice Changer
Natural Russian voice synthesis using Silero TTS
"""

import os
import torch
import tempfile
from pathlib import Path
from typing import Optional, List, Dict
import numpy as np

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    import librosa
except ImportError:
    librosa = None

try:
    import whisper
except ImportError:
    whisper = None

from core.utils.logger import get_logger
from core.utils.prosody_transfer import ProsodyTransfer

logger = get_logger(__name__)


class SileroVoiceChanger:
    """
    Silero TTS-based voice changer
    Transcribes source audio and synthesizes with target voice
    """
    
    # Available Silero voices
    AVAILABLE_VOICES = {
        # Russian voices
        'aidar': {'language': 'ru', 'gender': 'male', 'description': 'Айдар - мужской голос'},
        'baya': {'language': 'ru', 'gender': 'female', 'description': 'Бая - женский голос'},
        'kseniya': {'language': 'ru', 'gender': 'female', 'description': 'Ксения - женский голос'},
        'xenia': {'language': 'ru', 'gender': 'female', 'description': 'Ксения - женский голос (вариант)'},
        'eugene': {'language': 'ru', 'gender': 'male', 'description': 'Евгений - мужской голос'},
        'random': {'language': 'ru', 'gender': 'random', 'description': 'Случайный русский голос'},
    }
    
    def __init__(self, device: Optional[str] = None):
        """
        Initialize Silero Voice Changer
        
        Args:
            device: Device for processing
        """
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        self.silero_model = None
        self.whisper_model = None
        self.prosody_transfer = ProsodyTransfer()
        
        logger.info(f"Silero Voice Changer initialized on {self.device}")
    
    def load_models(self, whisper_size: str = 'base'):
        """
        Load Silero TTS and Whisper models
        
        Args:
            whisper_size: Whisper model size (tiny, base, small, medium, large)
        """
        if self.silero_model is None:
            logger.info("Loading Silero TTS model...")
            try:
                # Load Silero TTS model for Russian
                model_tuple = torch.hub.load(
                    repo_or_dir='snakers4/silero-models',
                    model='silero_tts',
                    language='ru',
                    speaker='v3_1_ru',
                    trust_repo=True
                )
                
                # torch.hub.load returns (model, example_text, ...) tuple
                if isinstance(model_tuple, tuple):
                    self.silero_model = model_tuple[0]
                else:
                    self.silero_model = model_tuple
                
                self.silero_model.to(self.device)
                logger.info("Silero TTS model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Silero: {str(e)}")
                raise
        
        if self.whisper_model is None and whisper is not None:
            logger.info(f"Loading Whisper model ({whisper_size})...")
            try:
                self.whisper_model = whisper.load_model(whisper_size, device=self.device)
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper: {str(e)}")
                raise
    
    def convert_voice(
        self,
        input_file: str,
        output_file: str,
        target_voice: str = 'kseniya',
        sample_rate: int = 48000,
        preserve_prosody: bool = True
    ) -> dict:
        """
        Convert voice using Silero TTS
        
        Args:
            input_file: Input audio file
            output_file: Output audio file
            target_voice: Target Silero voice (aidar, baya, kseniya, etc.)
            sample_rate: Output sample rate
            
        Returns:
            Conversion results
        """
        # Load models
        self.load_models()
        
        logger.info(f"Converting voice with Silero:")
        logger.info(f"  Input: {input_file}")
        logger.info(f"  Output: {output_file}")
        logger.info(f"  Target voice: {target_voice}")
        logger.info(f"  Preserve prosody: {preserve_prosody}")
        
        # Load original audio for prosody extraction
        if preserve_prosody:
            logger.info("Loading original audio for prosody extraction...")
            original_audio, original_sr = librosa.load(input_file, sr=None, mono=True)
        
        # Step 1: Transcribe audio to text
        logger.info("Step 1: Transcribing audio...")
        result = self._transcribe_with_timestamps(input_file)
        transcript = result['text']
        word_timestamps = result.get('segments', [])
        
        if not transcript:
            raise ValueError("Failed to transcribe audio")
        
        logger.info(f"Transcribed text: {transcript[:100]}...")
        
        # Step 2: Extract prosody from original
        source_prosody = None
        if preserve_prosody:
            logger.info("Step 2: Extracting prosody from original...")
            source_prosody = self.prosody_transfer.extract_prosody(
                original_audio, original_sr, word_timestamps
            )
        
        # Step 3: Synthesize with Silero
        logger.info(f"Step 3: Synthesizing with Silero voice '{target_voice}'...")
        audio_synthesized = self._synthesize(transcript, target_voice, sample_rate)
        
        # Step 4: Apply prosody transfer
        if preserve_prosody and source_prosody:
            logger.info("Step 4: Applying prosody transfer...")
            audio_final = self.prosody_transfer.apply_prosody(
                audio_synthesized, sample_rate, source_prosody
            )
        else:
            audio_final = audio_synthesized
        
        # Step 5: Save result
        logger.info("Step 5: Saving result...")
        sf.write(output_file, audio_final, sample_rate)
        
        logger.info(f"Silero conversion completed: {output_file}")
        
        return {
            'success': True,
            'output_file': output_file,
            'transcript': transcript,
            'voice': target_voice,
            'method': 'Silero TTS'
        }
    
    def _transcribe_with_timestamps(self, audio_file: str) -> Dict:
        """Transcribe audio using Whisper with word-level timestamps"""
        
        if self.whisper_model is None:
            logger.error("Whisper model not loaded")
            return {'text': '', 'segments': []}
        
        try:
            result = self.whisper_model.transcribe(
                audio_file,
                language='ru',
                fp16=False if self.device == 'cpu' else True,
                word_timestamps=True  # Get word-level timestamps
            )
            
            transcript = result['text'].strip()
            logger.info(f"Transcription completed: {len(transcript)} characters")
            
            return result
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            # Try without word timestamps as fallback
            try:
                result = self.whisper_model.transcribe(
                    audio_file,
                    language='ru',
                    fp16=False if self.device == 'cpu' else True
                )
                return result
            except:
                return {'text': '', 'segments': []}
    
    def _synthesize(
        self,
        text: str,
        voice: str,
        sample_rate: int
    ) -> np.ndarray:
        """Synthesize speech with Silero"""
        
        try:
            # Split long text into very small chunks (Silero has strict limits)
            chunks = self._split_text(text, max_length=100)
            
            audio_chunks = []
            
            for i, chunk in enumerate(chunks):
                logger.info(f"Synthesizing chunk {i+1}/{len(chunks)}...")
                
                audio_chunk = self.silero_model.apply_tts(
                    text=chunk,
                    speaker=voice,
                    sample_rate=sample_rate
                )
                
                # Convert to numpy
                if isinstance(audio_chunk, torch.Tensor):
                    audio_chunk = audio_chunk.cpu().numpy()
                
                audio_chunks.append(audio_chunk)
            
            # Concatenate all chunks
            if len(audio_chunks) > 1:
                audio_full = np.concatenate(audio_chunks)
            else:
                audio_full = audio_chunks[0]
            
            return audio_full
            
        except Exception as e:
            logger.error(f"Synthesis failed: {str(e)}")
            raise
    
    def _split_text(self, text: str, max_length: int = 200) -> List[str]:
        """Split text into small chunks for synthesis (Silero has limits)"""
        
        # Split by sentences
        sentences = text.replace('!', '.').replace('?', '.').split('.')
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Add sentence ending
            sentence = sentence + '.'
            
            # If single sentence is too long, split by words
            if len(sentence) > max_length:
                words = sentence.split()
                for word in words:
                    if len(current_chunk) + len(word) + 1 < max_length:
                        current_chunk += word + ' '
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = word + ' '
            else:
                # Check if adding this sentence exceeds limit
                if len(current_chunk) + len(sentence) < max_length:
                    current_chunk += sentence + ' '
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + ' '
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        logger.info(f"Split text into {len(chunks)} chunks (max {max_length} chars each)")
        
        return chunks if chunks else [text[:max_length]]
    
    def get_available_voices(self) -> dict:
        """Get available Silero voices"""
        return self.AVAILABLE_VOICES.copy()

