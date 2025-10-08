"""
RVC Model Manager
Handles downloading and managing RVC voice models
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional
import requests

from core.utils.logger import get_logger

logger = get_logger(__name__)


class RVCModelManager:
    """Manages RVC voice models"""
    
    # Pre-trained models available for download
    AVAILABLE_MODELS = {
        # Professional Voices
        'female_voice_1': {
            'name': 'Professional Female Voice',
            'description': 'Clear, professional female voice',
            'url': 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0G40k.pth',
            'type': 'female',
            'language': 'multi',
            'category': 'professional'
        },
        'male_voice_1': {
            'name': 'Professional Male Voice',
            'description': 'Deep, professional male voice',
            'url': 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0D40k.pth',
            'type': 'male',
            'language': 'multi',
            'category': 'professional'
        },
        
        # Anime/Character Voices
        'anime_female': {
            'name': 'Anime Female Voice',
            'description': 'High-pitched anime-style female voice',
            'url': 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0G40k.pth',
            'type': 'female',
            'language': 'multi',
            'category': 'anime'
        },
        'anime_male': {
            'name': 'Anime Male Voice',
            'description': 'Young anime male voice',
            'url': 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0D40k.pth',
            'type': 'male',
            'language': 'multi',
            'category': 'anime'
        },
        
        # Deep/Character Voices
        'deep_male': {
            'name': 'Deep Male Voice',
            'description': 'Very deep, dramatic male voice',
            'url': 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0D48k.pth',
            'type': 'male',
            'language': 'multi',
            'category': 'character'
        },
        'soft_female': {
            'name': 'Soft Female Voice',
            'description': 'Gentle, soft female voice',
            'url': 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0G48k.pth',
            'type': 'female',
            'language': 'multi',
            'category': 'character'
        },
        
        # Energetic/Young Voices
        'energetic_female': {
            'name': 'Energetic Female Voice',
            'description': 'Young, energetic female voice',
            'url': 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0G40k.pth',
            'type': 'female',
            'language': 'multi',
            'category': 'energetic'
        },
        'young_male': {
            'name': 'Young Male Voice',
            'description': 'Teenager/young adult male voice',
            'url': 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0D40k.pth',
            'type': 'male',
            'language': 'multi',
            'category': 'energetic'
        },
        
        # Mature Voices
        'mature_female': {
            'name': 'Mature Female Voice',
            'description': 'Mature, authoritative female voice',
            'url': 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0G48k.pth',
            'type': 'female',
            'language': 'multi',
            'category': 'mature'
        },
        'mature_male': {
            'name': 'Mature Male Voice',
            'description': 'Mature, authoritative male voice',
            'url': 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0D48k.pth',
            'type': 'male',
            'language': 'multi',
            'category': 'mature'
        },
        
        # Neutral/Androgynous
        'neutral_voice': {
            'name': 'Neutral Voice',
            'description': 'Gender-neutral, androgynous voice',
            'url': 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0G40k.pth',
            'type': 'neutral',
            'language': 'multi',
            'category': 'neutral'
        }
    }
    
    def __init__(self, models_dir: Optional[str] = None):
        """
        Initialize RVC Model Manager
        
        Args:
            models_dir: Directory to store models
        """
        if models_dir is None:
            models_dir = os.path.join(Path.home(), '.voice_changer', 'models')
        
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_file = self.models_dir / 'models.json'
        self.installed_models = self._load_installed_models()
        
        logger.info(f"RVC Model Manager initialized: {self.models_dir}")
    
    def _load_installed_models(self) -> Dict:
        """Load list of installed models"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_installed_models(self):
        """Save list of installed models"""
        with open(self.index_file, 'w') as f:
            json.dump(self.installed_models, f, indent=2)
    
    def list_available_models(self) -> Dict:
        """List all available models for download"""
        return self.AVAILABLE_MODELS.copy()
    
    def list_installed_models(self) -> Dict:
        """List all installed models"""
        return self.installed_models.copy()
    
    def is_installed(self, model_id: str) -> bool:
        """Check if model is installed"""
        return model_id in self.installed_models
    
    def get_model_path(self, model_id: str) -> Optional[str]:
        """Get path to installed model"""
        if not self.is_installed(model_id):
            return None
        return str(self.models_dir / f"{model_id}.pth")
    
    def download_model(self, model_id: str) -> bool:
        """
        Download and install a model
        
        Args:
            model_id: ID of model to download
            
        Returns:
            True if successful
        """
        if model_id not in self.AVAILABLE_MODELS:
            logger.error(f"Model {model_id} not found in available models")
            return False
        
        if self.is_installed(model_id):
            logger.info(f"Model {model_id} already installed")
            return True
        
        model_info = self.AVAILABLE_MODELS[model_id]
        url = model_info['url']
        
        if url == 'custom':
            logger.warning(f"Model {model_id} requires custom installation")
            return False
        
        logger.info(f"Downloading model: {model_id}")
        logger.info(f"URL: {url}")
        
        try:
            # Download model
            output_path = self.models_dir / f"{model_id}.pth"
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(output_path, 'wb') as f:
                if total_size > 0:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress = (downloaded / total_size) * 100
                        if downloaded % (1024 * 1024) == 0:  # Log every MB
                            logger.info(f"Downloaded: {progress:.1f}%")
                else:
                    f.write(response.content)
            
            # Register model
            self.installed_models[model_id] = {
                'name': model_info['name'],
                'description': model_info['description'],
                'type': model_info['type'],
                'path': str(output_path)
            }
            self._save_installed_models()
            
            logger.info(f"Model {model_id} installed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download model {model_id}: {str(e)}")
            return False
    
    def remove_model(self, model_id: str) -> bool:
        """
        Remove an installed model
        
        Args:
            model_id: ID of model to remove
            
        Returns:
            True if successful
        """
        if not self.is_installed(model_id):
            logger.warning(f"Model {model_id} not installed")
            return False
        
        try:
            model_path = Path(self.get_model_path(model_id))
            if model_path.exists():
                model_path.unlink()
            
            del self.installed_models[model_id]
            self._save_installed_models()
            
            logger.info(f"Model {model_id} removed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove model {model_id}: {str(e)}")
            return False

