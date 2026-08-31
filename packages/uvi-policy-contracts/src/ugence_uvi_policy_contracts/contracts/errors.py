"""Error taxonomy for the UVI policy & assessment-context contracts."""

from __future__ import annotations

__all__ = ["PolicyContractError"]


class PolicyContractError(ValueError):
    """A structural policy/assessment-context invariant was violated.

    Subclasses :class:`ValueError` so existing ``ValueError`` handling still
    catches it. It signals a *structural* rejection at construction time — it is
    **never** an assertion that a policy was approved, signed, resolved, or
    otherwise trust-verified. Trust evaluation (signature, approval, revocation,
    freshness) belongs to the Policy Authority and later admission milestones,
    which are explicitly out of scope for these contract shapes.
    """
