#!/usr/bin/env python3
"""
Runner script for adding project_id and redirect_uris fields to google_consoles.
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.database.migrations.add_google_consoles_fields_migration import main


if __name__ == "__main__":
    main()

