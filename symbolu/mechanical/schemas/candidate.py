"""
Candidate Schema
=================

Response candidate data structure.
EMPTY SCAFFOLD - No implementation yet.
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Candidate:
    """Candidate Schema - SCAFFOLD ONLY."""
    
    text: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = None
