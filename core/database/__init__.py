"""
Database module for Content Fabric
"""

from .mysql_db import YouTubeMySQLDatabase, get_mysql_database, YouTubeChannel, GoogleConsole

# Alias for backward compatibility
YouTubeDatabase = YouTubeMySQLDatabase
get_database = get_mysql_database
get_database_by_type = get_mysql_database

__all__ = [
    'YouTubeMySQLDatabase',
    'YouTubeDatabase',  # Alias for backward compatibility
    'YouTubeChannel',
    'GoogleConsole',
    'get_mysql_database',
    'get_database',  # Alias for backward compatibility
    'get_database_by_type',  # Alias for backward compatibility
]
