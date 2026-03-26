"""Core data structures for CTM+ simulator."""

from .config import (
    SimulatorConfig, CTMPlusConfig,
    PhaseIntegratorConfig, CoherenceConfig,
    AdmissionConfig, IRRConfig, SizeAwareConfig, RefaultConfig,
    AdaptiveWeightConfig, S3FIFOFastPathConfig, ExternalHintConfig,
    TenantPriority, TenantConfig, MultiTenancyConfig,
    NUMAConfig, CostTieringConfig, WritebackSchedulingConfig,
    CompressionTierConfig, CXL3PoolConfig,
    AutoFallbackConfig, GLCacheConfig,
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
    "PhaseIntegratorConfig",
    "CoherenceConfig",
    "AdaptiveWeightConfig",
    "S3FIFOFastPathConfig",
    "ExternalHintConfig",
    "AutoFallbackConfig",
    "GLCacheConfig",
    "TenantPriority",
    "TenantConfig",
    "MultiTenancyConfig",
    "NUMAConfig",
    "CostTieringConfig",
    "WritebackSchedulingConfig",
    "CompressionTierConfig",
    "CXL3PoolConfig",
    "PageState",
    "TierState",
    "PageHint",
    "SimulationMetrics",
    "MetricsCollector",
]
