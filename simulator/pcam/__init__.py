"""
PCAM (Phase-Coherent Attention Memory) — public package surface.

This package exposes two layers:

1. The KV-cache policy runtime (Phase 1 of the software-product roadmap):

       from simulator.pcam import (
           KVCachePolicy,
           FrequencySketch,
           InferencePhase,
           PositionClass,
           PCAMConfig,
           TierHint,
           PolicyMetrics,
       )

   ``KVCachePolicy`` is the runtime policy and the bit-parity port of
   the canonical reference at
   ``simulator/pcam/reference/attention_evictor_vendored.py`` per
   ADR-0001. ``PCAMConfig`` is the policy configuration object.

2. The cycle-accurate simulator framework (pre-existing):

       from simulator.pcam import (
           PCAMSimulator,
           SimulationResult,
           PCAMInterface,
           PCAMSimulatorConfig,
           PCAMMetrics,
           MetricsCollector,
           AttentionState,
           BlockScore,
       )

   ``PCAMSimulatorConfig`` is the same class previously exported as
   ``PCAMConfig`` from this package; the rename here is to free up the
   ``PCAMConfig`` name for the policy config per the Phase 1 public
   API. The underlying class in ``simulator/pcam/core/config.py`` is
   unchanged — only the package-root export name is different.
"""

# ---- Phase 1: KV-cache policy runtime --------------------------------------
from .config import PCAMConfig
from .kv_policy import (
    FrequencySketch,
    InferencePhase,
    KVCachePolicy,
    PositionClass,
    TierHint,
)
from .metrics import PolicyMetrics

# ---- Pre-existing simulator framework --------------------------------------
from .core.config import PCAMConfig as PCAMSimulatorConfig
from .core.metrics import MetricsCollector, PCAMMetrics
from .core.state import AttentionState, BlockScore
from .interface import PCAMInterface
from .simulator import PCAMSimulator, SimulationResult

__all__ = [
    # Phase 1 KV-cache policy public API
    "KVCachePolicy",
    "FrequencySketch",
    "InferencePhase",
    "PositionClass",
    "PCAMConfig",
    "TierHint",
    "PolicyMetrics",
    # Pre-existing simulator framework
    "PCAMSimulator",
    "SimulationResult",
    "PCAMInterface",
    "PCAMSimulatorConfig",
    "PCAMMetrics",
    "MetricsCollector",
    "AttentionState",
    "BlockScore",
]

__version__ = "0.2.0"
