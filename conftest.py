"""
Pytest configuration for the symbolu project.

Adds the project root to sys.path so that tests can import from docs.experiments.
"""
import sys
from pathlib import Path

# Add project root to sys.path for tests
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
