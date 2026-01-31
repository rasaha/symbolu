"""
PCAM (Phase-Coherent Attention Memory) Validation Framework.

This module implements the industry-grade simulation and validation plan
as specified in PCAM Specification Appendix H.

Key Components:
- PCAMSimulator: Cycle-accurate simulator for ATTEND/UPDATE operations
- Trace generators: Synthetic workload generation
- Baselines: Sink+LRU, H2O, Industry-Style implementations
- Metrics: tok/s, p50/p95/p99 latency, quality proxies
"""

from .simulator import PCAMSimulator, SimulationResult
from .interface import PCAMInterface
from .core.config import PCAMConfig
from .core.metrics import PCAMMetrics, MetricsCollector
from .core.state import AttentionState, BlockScore

__all__ = [
    "PCAMSimulator",
    "SimulationResult",
    "PCAMInterface",
    "PCAMConfig",
    "PCAMMetrics",
    "MetricsCollector",
    "AttentionState",
    "BlockScore",
]

__version__ = "0.1.0"
