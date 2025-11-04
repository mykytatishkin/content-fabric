#!/usr/bin/env python3
"""
Run migration to add error_message column to tasks table.
"""

from core.database.migrations.add_error_message_migration import main

if __name__ == "__main__":
    main()

