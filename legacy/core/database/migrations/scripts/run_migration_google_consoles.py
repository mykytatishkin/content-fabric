#!/usr/bin/env python3
"""
Runner script for Google Consoles migration.
"""

import sys
import os

# Add migrations directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from add_google_consoles_migration import main

if __name__ == "__main__":
    main()

