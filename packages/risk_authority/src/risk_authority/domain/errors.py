"""Domain-level errors. All are fail-closed signals."""

from __future__ import annotations

__all__ = [
    "RiskAuthorityError",
    "IllegalTransitionError",
    "AuthorityDeniedError",
    "NoRemainingValidityError",
    "MonotonicityViolationError",
    "ProductionContainmentError",
    "SnapshotIntegrityError",
]


class RiskAuthorityError(Exception):
    """Base class for all risk-authority domain errors."""


class ProductionContainmentError(RiskAuthorityError):
    """A production-mode caller reached an execution-authority path that is deferred.

    Production Risk Authority integration (Phase 4) stops at a non-executable
    ``RiskDecision``. Envelope issuance and action authorization are Phase 5 (a
    separately-governed production ActionGate / provider seam) and are **not**
    implemented, so they fail closed in production mode rather than mint an
    execution-authority artifact through the reference components. Reference /
    conformance mode (``production_mode=False``) retains the full flow.
    """


class IllegalTransitionError(RiskAuthorityError):
    """A RiskDecisionCase state transition was not legal."""


class AuthorityDeniedError(RiskAuthorityError):
    """A principal attempted to issue a decision outside its granted scope."""

    def __init__(self, reasons: "list[str]") -> None:
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons) or "authority denied")


class NoRemainingValidityError(AuthorityDeniedError):
    """Every prerequisite held, but none of them leaves a forward window to grant.

    Raised when the decision's capped ``expires_at`` lands at or before ``now``. The
    prerequisites are *satisfied* — this is not "the principal is not entitled" — there is
    simply no positive validity remaining to bind, and a decision valid over an empty
    interval authorizes nothing at any instant.

    A subclass of :class:`AuthorityDeniedError` so every existing handler keeps working
    unchanged, and a distinct type so a caller that cares can tell the two apart without
    parsing a reason string. ``prerequisite`` names which bound decided, so a seam can map
    it to the right typed outcome rather than reporting a generic authority failure.
    """

    def __init__(self, reasons: "list[str]", *, prerequisite: str = "") -> None:
        self.prerequisite = prerequisite
        super().__init__(reasons)


class MonotonicityViolationError(RiskAuthorityError):
    """An envelope scope exceeded its binding decision scope."""

    def __init__(self, reasons: "list[str]") -> None:
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons) or "scope monotonicity violated")


class SnapshotIntegrityError(RiskAuthorityError):
    """A persisted case snapshot does not replay: its event chain or identity is broken."""
