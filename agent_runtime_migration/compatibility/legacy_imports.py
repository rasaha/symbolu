"""Guard against importing legacy GOVERNANCE authority through the compatibility layer.

The compatibility layer NEVER re-exposes the legacy authoritative governance
(SafetyGate, SafeMCPGateway, GovernanceService, approval enforcement, policy
enforcement). Attempting to obtain them via this layer fails explicitly with a
migration message — governance moved to the AI Control Plane.

This module deliberately does NOT import ``agentic.agentic_framework`` (that package's
__init__ pulls research-signal code); the compatibility layer is duck-typed.
"""
from __future__ import annotations

from ..contracts.errors import GovernanceBoundaryError

_REMOVED_AUTHORITY = {
    "SafetyGate", "SafeMCPGateway", "GovernanceService", "ConfidenceGate",
    "ApprovalController", "ApprovalStore", "GatewayDecision", "policy_control_plane",
}


def get_legacy(name: str):
    """Explicitly refuse legacy governance authority (migration guidance)."""
    if name in _REMOVED_AUTHORITY:
        raise GovernanceBoundaryError(
            f"legacy governance authority {name!r} is not available through the Agent "
            "Runtime; authorization/operational-safety are owned by the AI Control Plane "
            "(submit a CER via control_plane.ControlPlaneClient).")
    raise ImportError(f"{name!r} is not provided by the compatibility layer")
