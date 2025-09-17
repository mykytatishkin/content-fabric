#!/usr/bin/env python3
"""
Setup script for Social Media Auto-Poster
"""

import os
import sys
import shutil
from pathlib import Path


def create_directories():
    """Create necessary directories."""
    directories = [
        'content/videos',
        'content/descriptions', 
        'content/thumbnails',
        'content/processed',
        'logs'
    ]
    
    print("📁 Creating directories...")
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {directory}")
    
    # Create .gitkeep files
    gitkeep_dirs = ['content/videos', 'content/processed', 'content/thumbnails']
    for directory in gitkeep_dirs:
        gitkeep_file = Path(directory) / '.gitkeep'
        if not gitkeep_file.exists():
            gitkeep_file.write_text("# This file ensures the directory is tracked by git\n")


def setup_environment():
    """Setup environment file."""
    env_example = Path("config.env.example")
    env_file = Path(".env")
    
    if env_example.exists() and not env_file.exists():
        print("📝 Creating .env file from template...")
        shutil.copy(env_example, env_file)
        print("  ✅ Created .env file")
        print("  ⚠️  Please edit .env file with your API credentials")
    elif env_file.exists():
        print("  ℹ️  .env file already exists")


def validate_config():
    """Validate configuration file."""
    config_file = Path("config.yaml")
    
    if not config_file.exists():
        print("❌ config.yaml not found!")
        print("Please create config.yaml with your configuration")
        return False
    
    try:
        import yaml
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Basic validation
        required_sections = ['platforms', 'accounts', 'schedule']
        missing_sections = []
        
        for section in required_sections:
            if section not in config:
                missing_sections.append(section)
        
        if missing_sections:
            print(f"❌ Missing configuration sections: {', '.join(missing_sections)}")
            return False
        
        print("✅ Configuration file is valid")
        return True
        
    except ImportError:
        print("❌ PyYAML not installed. Run: pip install pyyaml")
        return False
    except Exception as e:
        print(f"❌ Configuration file error: {str(e)}")
        return False


def check_dependencies():
    """Check if required dependencies are installed."""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        'requests',
        'python-dotenv',
        'schedule',
        'Pillow',
        'moviepy',
        'google-api-python-client',
        'google-auth-httplib2',
        'google-auth-oauthlib',
        'facebook-sdk',
        'python-telegram-bot',
        'colorama',
        'rich',
        'pydantic',
        'pyyaml'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"  ❌ {package}")
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies are installed")
    return True


def main():
    """Main setup function."""
    print("🚀 Social Media Auto-Poster Setup")
    print("=" * 40)
    
    # Create directories
    create_directories()
    print()
    
    # Setup environment
    setup_environment()
    print()
    
    # Check dependencies
    deps_ok = check_dependencies()
    print()
    
    # Validate config
    config_ok = validate_config()
    print()
    
    if deps_ok and config_ok:
        print("🎉 Setup completed successfully!")
        print("\nNext steps:")
        print("1. Edit .env file with your API credentials")
        print("2. Configure your accounts in config.yaml")
        print("3. Add your content to content/videos/")
        print("4. Test with: python main.py validate-accounts")
        print("5. Start posting: python main.py post --help")
        return 0
    else:
        print("❌ Setup incomplete. Please fix the issues above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

