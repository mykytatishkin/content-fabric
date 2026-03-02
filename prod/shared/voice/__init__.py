"""
Voice Processing Module
Contains all voice conversion and TTS functionality
"""

from shared.voice.voice_changer import VoiceChanger, change_voice
from shared.voice.silero import SileroVoiceChanger
from shared.voice.prosody import ProsodyTransfer
from shared.voice.stress import RussianStressMarker
from shared.voice.parallel import ParallelVoiceProcessor
from shared.voice.mixer import AudioBackgroundMixer

# RVC components
from shared.voice.rvc.model_manager import RVCModelManager
from shared.voice.rvc.inference import RVCInference
from shared.voice.rvc.sovits import SoVITSConverter

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

