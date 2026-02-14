"""
USE-6G: Universal Synchronization Engine for 6G Massive MIMO.

Simulator for the USE chip targeting 6G phone applications,
specifically Massive MIMO antenna synchronization using
O(n) phase-based coherence from the USE patent (U1-U5).

Key capabilities:
- Massive MIMO phase synchronization across antenna arrays
- O(n) mean-field phase alignment (vs. O(n^2) pairwise)
- +/-100ps timing precision for beamforming
- Sub-THz carrier frequency support (100 GHz - 1 THz)
- UCP-Edge power envelope (10-20W) for mobile form factors
"""

from .core.config import USE6GConfig
from .core.state import AntennaArrayState
from .core.metrics import USE6GMetrics, MetricsCollector
from .simulator import USE6GSimulator

__all__ = [
    "USE6GConfig",
    "AntennaArrayState",
    "USE6GMetrics",
    "MetricsCollector",
    "USE6GSimulator",
]
