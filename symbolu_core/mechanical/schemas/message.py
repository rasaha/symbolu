"""
Message Schema
===============

Message data structure.
EMPTY SCAFFOLD - No implementation yet.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class Message:
    """Message Schema - SCAFFOLD ONLY."""
    
    content: str = ""
    role: str = "user"
    metadata: Optional[Dict[str, Any]] = None
