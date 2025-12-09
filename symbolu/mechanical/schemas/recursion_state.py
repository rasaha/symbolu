"""
Recursion State
================

State tracking for recursive processing.
EMPTY SCAFFOLD - No implementation yet.
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class RecursionState:
    """Recursion State - SCAFFOLD ONLY."""
    
    depth: int = 0
    max_depth: int = 3
    history: List[Dict[str, Any]] = None
