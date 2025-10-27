"""
Voice Processing Module
Contains all voice conversion and TTS functionality
"""

from core.voice.voice_changer import VoiceChanger, change_voice
from core.voice.silero import SileroVoiceChanger
from core.voice.prosody import ProsodyTransfer
from core.voice.stress import RussianStressMarker
from core.voice.parallel import ParallelVoiceProcessor
from core.voice.mixer import AudioBackgroundMixer

# RVC components
from core.voice.rvc.model_manager import RVCModelManager
from core.voice.rvc.inference import RVCInference
from core.voice.rvc.sovits import SoVITSConverter

__all__ = [
    'VoiceChanger',
    'change_voice',
    'SileroVoiceChanger',
    'ProsodyTransfer',
    'RussianStressMarker',
    'ParallelVoiceProcessor',
    'AudioBackgroundMixer',
    'RVCModelManager',
    'RVCInference',
    'SoVITSConverter',
]

