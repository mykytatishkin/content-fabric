#!/usr/bin/env python3
"""
Helper script to add custom RVC models
"""

import sys
import os
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils.rvc_model_manager import RVCModelManager
from core.utils.logger import get_logger

logger = get_logger(__name__)


def add_custom_model_from_file(file_path: str, model_id: str, name: str, description: str, voice_type: str):
    """
    Add a custom RVC model from a local file
    
    Args:
        file_path: Path to .pth model file
        model_id: Unique ID for the model
        name: Display name
        description: Description
        voice_type: Type (male/female/neutral)
    """
    manager = RVCModelManager()
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        return False
    
    # Check if it's a .pth file
    if not file_path.endswith('.pth'):
        print(f"❌ Error: File must be a .pth file")
        return False
    
    # Copy to models directory
    target_path = manager.models_dir / f"{model_id}.pth"
    
    print(f"📦 Installing model: {name}")
    print(f"   From: {file_path}")
    print(f"   To:   {target_path}")
    
    try:
        shutil.copy(file_path, target_path)
        
        # Register model
        manager.installed_models[model_id] = {
            'name': name,
            'description': description,
            'type': voice_type,
            'path': str(target_path),
            'category': 'custom'
        }
        manager._save_installed_models()
        
        print(f"✅ Model installed successfully!")
        print(f"\n🎙️  Use it with:")
        print(f"   python3 run_voice_changer.py --voice-model {model_id} input.mp3 output.mp3")
        
        return True
        
    except Exception as e:
        print(f"❌ Error installing model: {str(e)}")
        return False


def add_custom_model_from_url(url: str, model_id: str, name: str, description: str, voice_type: str):
    """
    Add a custom RVC model from URL
    
    Args:
        url: Direct URL to .pth file
        model_id: Unique ID for the model
        name: Display name
        description: Description
        voice_type: Type (male/female/neutral)
    """
    manager = RVCModelManager()
    
    # Add to available models temporarily
    manager.AVAILABLE_MODELS[model_id] = {
        'name': name,
        'description': description,
        'url': url,
        'type': voice_type,
        'language': 'multi',
        'category': 'custom'
    }
    
    print(f"📦 Downloading model: {name}")
    print(f"   URL: {url}")
    
    # Download
    success = manager.download_model(model_id)
    
    if success:
        print(f"✅ Model downloaded and installed successfully!")
        print(f"\n🎙️  Use it with:")
        print(f"   python3 run_voice_changer.py --voice-model {model_id} input.mp3 output.mp3")
    else:
        print(f"❌ Failed to download model")
    
    return success


def main():
    """Main CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Add custom RVC voice models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add from local file
  python3 scripts/add_custom_model.py \
    --file ~/Downloads/model.pth \
    --id my_voice \
    --name "My Voice" \
    --desc "Custom voice model" \
    --type female
  
  # Add from URL
  python3 scripts/add_custom_model.py \
    --url https://example.com/model.pth \
    --id professional_voice \
    --name "Professional Voice" \
    --desc "High-quality voice" \
    --type male
  
  # List installed models
  python3 run_voice_changer.py --list-models
        """
    )
    
    parser.add_argument('--file', help='Path to local .pth model file')
    parser.add_argument('--url', help='URL to download .pth model file')
    parser.add_argument('--id', required=True, help='Unique model ID (e.g., my_voice)')
    parser.add_argument('--name', required=True, help='Display name')
    parser.add_argument('--desc', required=True, help='Description')
    parser.add_argument('--type', required=True, choices=['male', 'female', 'neutral'], help='Voice type')
    
    args = parser.parse_args()
    
    # Validate
    if not args.file and not args.url:
        parser.error("Either --file or --url must be provided")
        return 1
    
    if args.file and args.url:
        parser.error("Provide either --file or --url, not both")
        return 1
    
    print("\n🎙️  Custom Model Installer")
    print("="*60)
    
    # Add model
    if args.file:
        success = add_custom_model_from_file(
            args.file, args.id, args.name, args.desc, args.type
        )
    else:
        success = add_custom_model_from_url(
            args.url, args.id, args.name, args.desc, args.type
        )
    
    print("="*60)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

