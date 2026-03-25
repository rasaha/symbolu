"""
CTM+ Simulator: Coherence-Tier Memory Plus Validation Framework

This simulator validates the CTM+ memory controller algorithm by replaying
memory access traces and comparing hit rates against baseline algorithms.

CTM+ is a CONTROLLER ARCHITECTURE, not a new memory cell. It uses existing
DRAM and NAND but makes smarter placement decisions using coherence math.

Usage:
    from ctm_plus import Simulator, CTMPlusController, LRUController
    from ctm_plus.traces import load_trace

    trace = load_trace("path/to/trace.csv")
    sim = Simulator(tier0_size=1000, tier1_size=100000)

    results_ctm = sim.run(trace, CTMPlusController())
    results_lru = sim.run(trace, LRUController())

    print(f"CTM+ hit rate: {results_ctm.hit_rate:.2%}")
    print(f"LRU hit rate:  {results_lru.hit_rate:.2%}")
    print(f"Improvement:   {results_ctm.hit_rate / results_lru.hit_rate - 1:.2%}")
"""

__version__ = "0.1.0"
__author__ = "Symbol-U Research"

from .core.config import (
    SimulatorConfig, CTMPlusConfig, TenantPriority, TenantConfig,
    MultiTenancyConfig, NUMAConfig, CostTieringConfig, WritebackSchedulingConfig,
    CompressionTierConfig,
)
from .core.state import PageState, TierState
from .core.metrics import SimulationMetrics, MetricsCollector
from .controllers.base import BaseController
from .controllers.lru import LRUController
from .controllers.arc import ARCController
from .controllers.ctm_plus import CTMPlusController
from .controllers.s3fifo import S3FIFOController
from .simulator import Simulator
from .traces.loader import load_trace, TraceEvent

__all__ = [
    # Config
    "SimulatorConfig",
    "CTMPlusConfig",
    "TenantPriority",
    "TenantConfig",
    "MultiTenancyConfig",
    "NUMAConfig",
    "CostTieringConfig",
    "WritebackSchedulingConfig",
    "CompressionTierConfig",
    # State
    "PageState",
    "TierState",
    # Metrics
    "SimulationMetrics",
    "MetricsCollector",
    # Controllers
    "BaseController",
    "LRUController",
    "ARCController",
    "CTMPlusController",
    "S3FIFOController",
    # Simulator
    "Simulator",
    # Traces
    "load_trace",
    "TraceEvent",
]
