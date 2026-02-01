"""
Baseline implementations for PCAM validation.

Mandatory baselines from Appendix H.1.2:
- Sink+LRU: Pin first K tokens (sinks), LRU for rest
- H2O (Heavy Hitters): Evict based on accumulated attention mass
- Industry-Style: Sinks + attention-aware + ghost/adaptation
"""

from .base import BaselineController
from .sink_lru import SinkLRUController
from .h2o import H2OController
from .industry_style import IndustryStyleController

__all__ = [
    "BaselineController",
    "SinkLRUController",
    "H2OController",
    "IndustryStyleController",
]
