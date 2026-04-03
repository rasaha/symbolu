"""
Signal Adapters — Governance-time signal resolution.

These adapters bridge runtime signal modules (chitta_vritti, entropy)
into the governance decision path, with graceful fallback to existing
approximation logic when real signals are unavailable.

Phase 1: Governance signal rewiring.
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

__all__ = [
    "resolve_vritti_signal",
    "VrittiResolution",
    "VrittiSignalSource",
    "resolve_entropy_signal",
    "EntropyResolution",
]
