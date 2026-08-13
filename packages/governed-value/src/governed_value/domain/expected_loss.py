"""Expected loss — additive, absolute money, unbounded relative to benefit.

The prior model priced the wrong-action term as a *fraction* of realized value
(``value x (1 - p_error x severity)``), which capped expected loss at 100% of
benefit and made catastrophic/tail risk unrepresentable. GV-1 corrects this:
expected loss is the sum of independent items, each a probability times an
**absolute monetary loss magnitude**:

    ExpectedLoss = Σ_i  probability_i × loss_magnitude_i

There is no bound tying this to benefit — a single low-probability, high-magnitude
item (a wrongful large disbursement, a safety incident) can exceed total benefit
and drive net governed value deeply negative. That is the point.

This term is the *forward / residual* expected loss (risk-adjusted view). It is
distinct from **actual, historical incurred losses**, which are absolute money
subtracted directly in the realized calculation (see the scorer). Do not mix the
two.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .money import Money
from .rates import unit_ratio

__all__ = ["ExpectedLossItem", "ExpectedLoss"]


@dataclass(frozen=True)
class ExpectedLossItem:
    label: str
    probability: Decimal  # [0, 1]
    loss_magnitude: Money  # absolute, >= 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "probability", unit_ratio(self.probability, "probability"))
        if self.loss_magnitude.is_negative:
            raise ValueError("loss_magnitude must be >= 0")

    def expected_value(self) -> Money:
        """``probability × loss_magnitude`` — an absolute expected loss in money."""

        return self.loss_magnitude.scaled(self.probability)


@dataclass(frozen=True)
class ExpectedLoss:
    """An ordered set of expected-loss items in one currency.

    An *empty* ExpectedLoss is a legitimate, explicit statement that no forward
    loss is modelled (the risk-adjusted view then equals the realized view); the
    scorer flags it as a caveat, not a hard failure.
    """

    currency: str
    items: tuple[ExpectedLossItem, ...] = ()

    def __post_init__(self) -> None:
        for item in self.items:
            if item.loss_magnitude.currency != self.currency:
                raise ValueError(
                    f"expected-loss item {item.label!r} currency "
                    f"{item.loss_magnitude.currency} != {self.currency}"
                )

    @staticmethod
    def none(currency: str) -> "ExpectedLoss":
        return ExpectedLoss(currency=currency, items=())

    def total(self) -> Money:
        acc = Money.zero(self.currency)
        for item in self.items:
            acc = acc + item.expected_value()
        return acc

    def is_empty(self) -> bool:
        return len(self.items) == 0
