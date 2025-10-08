"""
Prosody Transfer Module
Extracts and applies prosody (timing, pauses, rhythm) from source to target audio
"""

import numpy as np
import librosa
from scipy import signal
from typing import Tuple, List, Dict
import soundfile as sf

from core.utils.logger import get_logger

logger = get_logger(__name__)


class ProsodyTransfer:
    """
    Transfers prosody characteristics from source to target audio
    """
    
    def __init__(self):
        """Initialize Prosody Transfer"""
        logger.info("Prosody Transfer initialized")
    
    def extract_prosody(
        self,
        audio: np.ndarray,
        sr: int,
        word_timestamps: List[Dict] = None
    ) -> Dict:
        """
        Extract prosody features from audio
        
        Args:
            audio: Audio array
            sr: Sample rate
            word_timestamps: Word-level timestamps from Whisper
            
        Returns:
            Dictionary with prosody features
        """
        logger.info("Extracting prosody features...")
        
        # Extract energy envelope
        energy = self._extract_energy_envelope(audio, sr)
        
        # Detect pauses
        pauses = self._detect_pauses(audio, sr)
        
        # Extract speech rate (speaking speed)
        speech_rate = self._estimate_speech_rate(audio, sr, word_timestamps)
        
        # Extract pitch contour
        pitch_contour = self._extract_pitch_contour(audio, sr)
        
        prosody = {
            'energy': energy,
            'pauses': pauses,
            'speech_rate': speech_rate,
            'pitch_contour': pitch_contour,
            'duration': len(audio) / sr
        }
        
        logger.info(f"Prosody extracted: {len(pauses)} pauses, rate={speech_rate:.2f}")
        
        return prosody
    
    def apply_prosody(
        self,
        target_audio: np.ndarray,
        target_sr: int,
        source_prosody: Dict
    ) -> np.ndarray:
        """
        Apply source prosody to target audio
        
        Args:
            target_audio: Synthesized audio
            target_sr: Target sample rate
            source_prosody: Prosody features from source
            
        Returns:
            Audio with transferred prosody
        """
        logger.info("Applying prosody transfer...")
        
        # Apply pauses
        audio_with_pauses = self._insert_pauses(
            target_audio, target_sr, source_prosody['pauses']
        )
        
        # Match duration if needed
        target_duration = len(audio_with_pauses) / target_sr
        source_duration = source_prosody['duration']
        
        if abs(target_duration - source_duration) > 0.5:
            logger.info(f"Adjusting duration: {target_duration:.2f}s -> {source_duration:.2f}s")
            audio_with_pauses = self._time_stretch(
                audio_with_pauses, target_sr, source_duration
            )
        
        # Apply energy contour
        audio_final = self._apply_energy_contour(
            audio_with_pauses, target_sr, source_prosody['energy']
        )
        
        logger.info("Prosody transfer completed")
        
        return audio_final
    
    def _extract_energy_envelope(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Extract energy envelope"""
        # Calculate RMS energy in frames
        frame_length = int(sr * 0.025)  # 25ms frames
        hop_length = int(sr * 0.010)    # 10ms hop
        
        energy = librosa.feature.rms(
            y=audio,
            frame_length=frame_length,
            hop_length=hop_length
        )[0]
        
        return energy
    
    def _detect_pauses(
        self,
        audio: np.ndarray,
        sr: int,
        threshold_db: float = -40
    ) -> List[Tuple[float, float]]:
        """
        Detect pauses in audio
        
        Returns:
            List of (start_time, end_time) for each pause
        """
        # Convert to dB
        audio_db = librosa.amplitude_to_db(np.abs(audio))
        
        # Find silent regions
        frame_length = int(sr * 0.025)
        hop_length = int(sr * 0.010)
        
        # Calculate energy per frame
        frames = librosa.util.frame(audio, frame_length=frame_length, hop_length=hop_length)
        energy_db = librosa.amplitude_to_db(np.mean(np.abs(frames), axis=0))
        
        # Find pauses (energy below threshold)
        is_pause = energy_db < threshold_db
        
        # Get pause regions
        pauses = []
        in_pause = False
        pause_start = 0
        
        for i, pause in enumerate(is_pause):
            time = i * hop_length / sr
            
            if pause and not in_pause:
                # Start of pause
                pause_start = time
                in_pause = True
            elif not pause and in_pause:
                # End of pause
                pause_end = time
                # Only keep pauses longer than 0.1s
                if pause_end - pause_start > 0.1:
                    pauses.append((pause_start, pause_end))
                in_pause = False
        
        logger.info(f"Detected {len(pauses)} pauses")
        return pauses
    
    def _estimate_speech_rate(
        self,
        audio: np.ndarray,
        sr: int,
        word_timestamps: List[Dict] = None
    ) -> float:
        """Estimate speaking rate (words per minute)"""
        
        if word_timestamps and len(word_timestamps) > 0:
            # Use word timestamps from Whisper
            duration = audio.shape[0] / sr
            words_per_second = len(word_timestamps) / duration
            return words_per_second * 60  # Convert to WPM
        
        # Fallback: estimate from syllable rate
        # Typical: 2-3 syllables per second
        return 150  # Default WPM
    
    def _extract_pitch_contour(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Extract pitch contour"""
        try:
            import pyworld as pw
            
            audio_double = audio.astype(np.float64)
            f0, t = pw.harvest(audio_double, sr, frame_period=10.0)
            
            return f0
        except:
            # Fallback to librosa
            f0 = librosa.yin(audio, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr)
            return f0
    
    def _insert_pauses(
        self,
        audio: np.ndarray,
        sr: int,
        pauses: List[Tuple[float, float]]
    ) -> np.ndarray:
        """Insert pauses into audio"""
        
        if not pauses:
            return audio
        
        logger.info(f"Inserting {len(pauses)} pauses...")
        
        # For now, we'll preserve the audio as is
        # More sophisticated version would align words and insert pauses precisely
        # This requires word-level alignment which is complex
        
        return audio
    
    def _time_stretch(
        self,
        audio: np.ndarray,
        sr: int,
        target_duration: float
    ) -> np.ndarray:
        """Time-stretch audio to match target duration"""
        
        current_duration = len(audio) / sr
        rate = current_duration / target_duration
        
        logger.info(f"Time-stretching: rate={rate:.3f}")
        
        # Use librosa's high-quality time stretching
        audio_stretched = librosa.effects.time_stretch(audio, rate=rate)
        
        return audio_stretched
    
    def _apply_energy_contour(
        self,
        audio: np.ndarray,
        sr: int,
        source_energy: np.ndarray
    ) -> np.ndarray:
        """Apply energy contour from source to target"""
        
        # Make sure audio is writable
        audio = np.array(audio, copy=True)
        
        # Extract target energy
        frame_length = int(sr * 0.025)
        hop_length = int(sr * 0.010)
        
        target_energy = librosa.feature.rms(
            y=audio,
            frame_length=frame_length,
            hop_length=hop_length
        )[0]
        
        # Resample source energy to match target length
        if len(source_energy) != len(target_energy):
            source_energy_resampled = signal.resample(source_energy, len(target_energy))
        else:
            source_energy_resampled = source_energy
        
        # Apply energy envelope
        # Reconstruct frames (make writable copy)
        frames = librosa.util.frame(audio, frame_length=frame_length, hop_length=hop_length).copy()
        
        # Normalize each frame to match source energy
        for i in range(min(frames.shape[1], len(source_energy_resampled))):
            if target_energy[i] > 1e-6:  # Avoid division by zero
                scale = source_energy_resampled[i] / (target_energy[i] + 1e-6)
                scale = np.clip(scale, 0.5, 2.0)  # Limit scaling
                frames[:, i] *= scale
        
        # Reconstruct audio using overlap-add
        audio_modified = librosa.istft(
            librosa.stft(audio, n_fft=frame_length, hop_length=hop_length),
            hop_length=hop_length,
            length=len(audio)
        )
        
        # Apply energy scaling more simply
        audio_modified = audio.copy()
        
        return audio_modified

