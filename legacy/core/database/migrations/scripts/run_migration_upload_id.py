#!/usr/bin/env python3
"""
Runner script for upload_id migration.
Adds upload_id column to tasks table.
"""

import sys
from core.database.migrations.add_upload_id_migration import main

if __name__ == "__main__":
    main()

