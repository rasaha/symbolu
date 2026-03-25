"""Core data structures for CTM+ simulator."""

from .config import (
    SimulatorConfig, CTMPlusConfig,
    AdmissionConfig, IRRConfig, SizeAwareConfig, RefaultConfig,
    AdaptiveWeightConfig, LazyPromotionConfig, ExternalHintConfig,
)
from .state import PageState, TierState, PageHint
from .metrics import SimulationMetrics, MetricsCollector

__all__ = [
    "SimulatorConfig",
    "CTMPlusConfig",
    "AdmissionConfig",
    "IRRConfig",
    "SizeAwareConfig",
    "RefaultConfig",
    "AdaptiveWeightConfig",
    "LazyPromotionConfig",
    "ExternalHintConfig",
    "PageState",
    "TierState",
    "PageHint",
    "SimulationMetrics",
    "MetricsCollector",
]
