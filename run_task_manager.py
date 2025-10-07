#!/usr/bin/env python3
"""
Task Manager Runner - Convenient wrapper for task_manager CLI.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run the task manager
from scripts.task_manager import main

if __name__ == '__main__':
    main()

