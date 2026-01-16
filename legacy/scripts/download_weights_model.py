#!/usr/bin/env python3
"""
Download model from weights.com/weights.gg
"""

import sys
import os
import argparse
import requests
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils.rvc_model_manager import RVCModelManager
from core.utils.logger import get_logger

logger = get_logger(__name__)


def extract_model_id(url: str) -> str:
    """Extract model ID from weights URL"""
    # Handle both weights.com and weights.gg
    if '/models/' in url:
        return url.split('/models/')[-1].split('?')[0].split('/')[0]
    return url


def download_from_weights(url: str, model_id: str, name: str, voice_type: str):
    """
    Download model from weights.com/weights.gg
    
    Args:
        url: URL to model page or direct download
        model_id: Unique ID for the model
        name: Display name
        voice_type: Type (male/female/neutral)
    """
    manager = RVCModelManager()
    
    print(f"\n🎙️  Downloading RVC Model from Weights")
    print("="*60)
    print(f"Model ID: {model_id}")
    print(f"Name: {name}")
    print(f"Type: {voice_type}")
    print("="*60 + "\n")
    
    # Try to find direct download link
    # For weights.gg/weights.com, usually need to access via API or page
    print("⚠️  Note: For Weights.gg/Weights.com models:")
    print("   1. Go to the model page in browser")
    print("   2. Click 'Download' button")
    print("   3. Save the .pth file")
    print("   4. Then run:")
    print(f"\n   python3 scripts/add_custom_model.py \\")
    print(f"     --file ~/Downloads/MODEL.pth \\")
    print(f"     --id {model_id} \\")
    print(f"     --name \"{name}\" \\")
    print(f"     --type {voice_type}\n")
    
    print("="*60)
    print(f"📋 Model page: {url}")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description='Download model from Weights.gg/Weights.com')
    parser.add_argument('url', help='URL to model on weights.gg or weights.com')
    parser.add_argument('--id', required=True, help='Model ID to use locally')
    parser.add_argument('--name', required=True, help='Model name')
    parser.add_argument('--type', required=True, choices=['male', 'female', 'neutral'], help='Voice type')
    
    args = parser.parse_args()
    
    download_from_weights(args.url, args.id, args.name, args.type)


if __name__ == '__main__':
    main()

