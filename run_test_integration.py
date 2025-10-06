#!/usr/bin/env python3
"""
Integration Test - запуск с правильными путями
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'core'))
sys.path.insert(0, str(project_root / 'app'))

# Import and run the actual script
from scripts.test_integration import main

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
