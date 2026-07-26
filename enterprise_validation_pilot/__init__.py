"""Enterprise Validation Pilot — a bounded cross-provider validation of the DGM ecosystem.

An **application-level** pilot that composes the frozen kernel (decision-governance),
the provider framework, the TAP assertion-governance provider, and the ActionGate
action-governance provider through their public APIs only, and runs realistic
enterprise decision workflows end to end:

    Enterprise Evidence → Proposed Assertion → TAP → Assertion Assessment →
    Recommendation → Decision → Proposed Action → ActionGate →
    Authorization/Constraints/Obligations → External Execution → Reconciliation

The pilot does not build new architecture. It measures whether the existing
architecture operates coherently while preserving its boundaries and fail-safe
governance invariants. It owns no kernel/framework/provider source, never couples
TAP and ActionGate directly, and requires no change to any frozen tree.

Import the public surface from ``enterprise_validation_pilot`` submodules; run the
pilot via ``python -m enterprise_validation_pilot.run``.
"""
from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
