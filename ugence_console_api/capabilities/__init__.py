"""Capability adapters — one thin adapter per consolidated module.

Each adapter imports its platform module through the module's *frozen public API
surface only* and exposes an ``available() -> (bool, reason)`` probe plus a single
governance call. Imports are fail-safe: a module that cannot load degrades to
"unavailable" and is reported as such, rather than crashing the service.
"""

from __future__ import annotations

from . import (
    action_control,
    context_gateway,
    operational_safety,
    registry,
    truth_evidence,
)

__all__ = [
    "action_control",
    "context_gateway",
    "operational_safety",
    "registry",
    "truth_evidence",
]
