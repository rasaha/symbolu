"""
Signal Adapters — Governance-time and output-time signal resolution.

These adapters bridge runtime signal modules (chitta_vritti, entropy,
DHA, guna_modulation) into the governance and output paths, with
graceful fallback when real signals are unavailable.

Phase 1: Governance signal rewiring.
Phase 2: Output modulation path wiring.
"""

from agentic.agentic_framework.signal_adapters.vritti_adapter import (
    resolve_vritti_signal,
    VrittiResolution,
    VrittiSignalSource,
)
from agentic.agentic_framework.signal_adapters.entropy_adapter import (
    resolve_entropy_signal,
    EntropyResolution,
)
from agentic.agentic_framework.signal_adapters.output_modulation_adapter import (
    resolve_output_modulation,
    OutputModulationResolution,
)

__all__ = [
    "resolve_vritti_signal",
    "VrittiResolution",
    "VrittiSignalSource",
    "resolve_entropy_signal",
    "EntropyResolution",
    "resolve_output_modulation",
    "OutputModulationResolution",
]
