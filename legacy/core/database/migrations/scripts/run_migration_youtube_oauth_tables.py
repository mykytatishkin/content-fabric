#!/usr/bin/env python3
"""
Runner script for creating YouTube OAuth automation tables.
"""

from core.database.migrations.add_youtube_oauth_tables_migration import main


if __name__ == "__main__":
    main()


