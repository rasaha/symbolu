"""
SOULPI FusionEngine v3.1
Deterministic reasoning fusion for HYBRID tier

Blends three channels:
- HRM (High-Reasoning Module): symbolic/abstract "WHY"
- LCM (Linguistic Coherence Module): semantic clarity "WHAT"  
- MoE (Mixture of Experts): domain-specific facts "HOW"

Part of mechanical layer - NO Symbol-U dependencies
Deterministic, explainable, patent-safe
"""

from .fusion_engine import FusionEngine, FusionResult
from .scorer import ChannelScorer, FusionScorer
from .conflict_resolver import ConflictResolver
from .routing import RoutingDecider
from .explanation import ExplanationGenerator

__version__ = "3.1.0"

__all__ = [
    "FusionEngine",
    "FusionResult",
    "ChannelScorer",
    "FusionScorer",
    "ConflictResolver",
    "RoutingDecider",
    "ExplanationGenerator",
]
