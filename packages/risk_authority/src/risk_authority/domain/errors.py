"""Domain-level errors. All are fail-closed signals."""

from __future__ import annotations

__all__ = [
    "RiskAuthorityError",
    "IllegalTransitionError",
    "AuthorityDeniedError",
    "MonotonicityViolationError",
]


class RiskAuthorityError(Exception):
    """Base class for all risk-authority domain errors."""


class IllegalTransitionError(RiskAuthorityError):
    """A RiskDecisionCase state transition was not legal."""


class AuthorityDeniedError(RiskAuthorityError):
    """A principal attempted to issue a decision outside its granted scope."""

    def __init__(self, reasons: "list[str]") -> None:
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons) or "authority denied")


class MonotonicityViolationError(RiskAuthorityError):
    """An envelope scope exceeded its binding decision scope."""

    def __init__(self, reasons: "list[str]") -> None:
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons) or "scope monotonicity violated")
