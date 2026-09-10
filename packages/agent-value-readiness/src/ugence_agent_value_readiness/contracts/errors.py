"""Error taxonomy for the Agent Value Readiness contracts."""

from __future__ import annotations

__all__ = ["ReadinessContractError"]


class ReadinessContractError(ValueError):
    """A structural readiness-contract invariant was violated at construction.

    Subclasses :class:`ValueError`. It signals a *structural* rejection only — it
    is **never** an assertion that a readiness decision was computed, that a
    policy was approved/verified, or that any authority acted. Readiness
    evaluation (the precedence calculus, tier selection, authority resolution)
    belongs to the GV-3R-b evaluator, which is out of scope for these shapes.
    """
