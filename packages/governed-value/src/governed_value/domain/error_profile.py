"""The wrong-action term — the part most models omit.

Net value must be reduced by the cost of the agent's *wrong* actions:

    risk-adjusted value = gross value x (1 - p_error x severity)

``p_error`` is the probability an authorized action is wrong; ``severity`` is
the fraction of that action's value destroyed when it is wrong (0 = harmless,
1 = the whole value inverts). Both must be *priced* — an unpriced error term is
the single most common way an agent "looks strongly positive". The cost of
human review lives in :class:`~governed_value.domain.cost.CostToServe`
(``human_in_loop_review``) so it is counted once, in cost-to-serve, exactly as
in the portfolio identity *value − expected error cost − cost to serve*.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .money import Money
from .rates import ONE, unit_ratio

__all__ = ["ErrorProfile"]


@dataclass(frozen=True)
class ErrorProfile:
    p_error: Optional[Decimal]
    severity: Optional[Decimal]

    def __post_init__(self) -> None:
        if self.p_error is not None:
            object.__setattr__(self, "p_error", unit_ratio(self.p_error, "p_error"))
        if self.severity is not None:
            object.__setattr__(self, "severity", unit_ratio(self.severity, "severity"))

    @staticmethod
    def unpriced() -> "ErrorProfile":
        """An explicitly *unpriced* profile — scoring will fail closed on it."""

        return ErrorProfile(p_error=None, severity=None)

    def is_priced(self) -> bool:
        return self.p_error is not None and self.severity is not None

    def expected_error_fraction(self) -> Decimal:
        """``p_error x severity`` — the expected fraction of value destroyed."""

        if not self.is_priced():
            raise ValueError("error profile is unpriced; cannot compute error fraction")
        assert self.p_error is not None and self.severity is not None
        return self.p_error * self.severity

    def risk_multiplier(self) -> Decimal:
        """``1 - p_error x severity`` — the surviving fraction of value."""

        return ONE - self.expected_error_fraction()

    def expected_error_cost(self, value: Money) -> Money:
        """Expected value destroyed by wrong actions over ``value``."""

        return value.scaled(self.expected_error_fraction())
