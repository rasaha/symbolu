"""
SOULPI Mechanical Layer
Deterministic reasoning and decision components

Components:
- MLCR: Multi-Layer Cognitive Router (v3.1)
- Fusion: Channel fusion engine (v3.1)
- Schemas: Data structures
- Persona: Voice selection (v2.8.2)
- Renderer: Output rendering (v3.0)
- DHA: Delivery Harmonization Algorithm
"""

from .fusion import FusionEngine, FusionResult
from .schemas import Candidate, CandidateSource, FusionContext

__all__ = [
    "fusion",
    "schemas",
    "FusionEngine",
    "FusionResult",
    "Candidate",
    "CandidateSource",
    "FusionContext",
]
