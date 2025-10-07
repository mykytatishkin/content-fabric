"""
Database module for Content Fabric
"""

from .sqlite_db import (
    YouTubeDatabase,
    YouTubeChannel,
    get_database,
    get_database_by_type
)

try:
    from .mysql_db import YouTubeMySQLDatabase, get_mysql_database
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

__all__ = [
    'YouTubeDatabase',
    'YouTubeChannel',
    'get_database',
    'get_database_by_type',
]

if MYSQL_AVAILABLE:
    __all__.extend(['YouTubeMySQLDatabase', 'get_mysql_database'])
