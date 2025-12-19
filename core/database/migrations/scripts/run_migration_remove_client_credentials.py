#!/usr/bin/env python3
"""
Script to run the migration that removes client_id and client_secret columns
from youtube_channels table.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from core.database.migrations.remove_client_credentials_migration import main

if __name__ == "__main__":
    sys.exit(main())

