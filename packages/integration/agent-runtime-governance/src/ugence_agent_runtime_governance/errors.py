"""Typed failures. Every one of them is a refusal, never a downgrade.

Nothing in this package converts a failure into permission. The hook never raises
into the runtime's hot path — a failure becomes a fail-closed ``GovernanceEvaluation``
— so these exist for wiring-time problems and for tests that assert the reason.
"""
from __future__ import annotations

__all__ = [
    "GovernanceHookError",
    "CompositionUnavailable",
    "MalformedDecision",
]


class GovernanceHookError(Exception):
    """Base for every failure raised by this package."""


class CompositionUnavailable(GovernanceHookError):
    """The governance inputs could not be obtained, or composition itself failed.

    Never an authoritative negative about the request — a missing authority input is
    not a denial — but it is never permission either. The hook renders it as BLOCK.
    """


class MalformedDecision(GovernanceHookError):
    """Composition returned something that is not a usable ``GovernedExecutionDecision``."""
