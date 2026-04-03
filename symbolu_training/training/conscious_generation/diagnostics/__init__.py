"""Validation and ablation diagnostics (Phase 5)."""

# Appendix F Stage 6: Stability and Orthogonality Verification
from symbolu.training.conscious_generation.diagnostics.stability_verifier import (
    StabilityConfig,
    PhaseControlOrthogonalityChecker,
    ModulationStabilityChecker,
    EntropyMonitor,
    LongSequenceAnalyzer,
    KillSwitchVerifier,
    StabilityVerifier,
)

# Appendix F Stage 7B: Adaptive Diagnostic Controller
from symbolu.training.conscious_generation.diagnostics.adaptive_diagnostic_controller import (
    AdaptiveDiagnosticController,
    AdaptiveDiagnosticConfig,
    DiagnosticSignals,
    AdaptiveResponse,
)

__all__ = [
    # Stage 6
    "StabilityConfig",
    "PhaseControlOrthogonalityChecker",
    "ModulationStabilityChecker",
    "EntropyMonitor",
    "LongSequenceAnalyzer",
    "KillSwitchVerifier",
    "StabilityVerifier",

    # Stage 7B
    "AdaptiveDiagnosticController",
    "AdaptiveDiagnosticConfig",
    "DiagnosticSignals",
    "AdaptiveResponse",
]
