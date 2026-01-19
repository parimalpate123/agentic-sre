# Agent Core Package
import sys
import os

# Add this directory to path so relative imports like "from models.schemas" work
_agent_core_dir = os.path.dirname(os.path.abspath(__file__))
if _agent_core_dir not in sys.path:
    sys.path.insert(0, _agent_core_dir)

__version__ = '0.1.0'

