"""
Schemas for SOULPI Mechanical Layer
Data structures for candidates, fusion results, and MLCR decisions
"""

from .candidate import Candidate, CandidateSource
from .fusion_result import FusionResult, FusionContext

__all__ = [
    "Candidate",
    "CandidateSource",
    "FusionResult",
    "FusionContext",
]
