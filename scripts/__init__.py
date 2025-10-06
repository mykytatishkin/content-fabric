"""
Scripts module for Content Fabric
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Add core to path
sys.path.insert(0, str(project_root / 'core'))

# Add app to path  
sys.path.insert(0, str(project_root / 'app'))