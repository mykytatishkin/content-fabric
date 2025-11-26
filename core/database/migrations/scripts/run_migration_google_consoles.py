#!/usr/bin/env python3
"""
Runner script for adding Google Cloud Console support.
"""

import sys
import os
import argparse

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.database.migrations.add_google_consoles_migration import main


if __name__ == "__main__":
    # Allow passing --config argument
    parser = argparse.ArgumentParser(description="Run Google Cloud Console migration")
    parser.add_argument('--config', type=str, default=None,
                       help='Path to MySQL config file (e.g., config/mysql_config_prod.yaml)')
    args = parser.parse_args()
    
    # Pass config to main function via sys.argv
    if args.config:
        sys.argv = [sys.argv[0], '--config', args.config]
    
    main()

