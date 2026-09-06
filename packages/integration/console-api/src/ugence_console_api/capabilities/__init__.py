"""Capability adapters — one thin adapter per consolidated module.

Each adapter imports its platform module through the module's *frozen public API
surface only* — the canonical distribution, never a legacy root namespace — and exposes
an ``available() -> (bool, reason)`` probe plus a single governance call.

The ``try`` guards are fail-safe: a module that cannot load degrades to "unavailable"
and is reported as such, rather than crashing the service. Ruling CP-5 keeps them for
development and closes the hole they would otherwise leave in a deployment: every
platform package named below is a declared dependency of ``ugence-console-api``, so a
missing one is an install-time failure. The guard can report a broken working copy; it
can no longer let an installed service answer while the governance it advertises is
absent.
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
