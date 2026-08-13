"""Total investment — the ROI denominator, distinct from cost-to-serve.

ROI is ``Net Governed Value / Total Investment``. Total investment is **not** the
per-window operating cost-to-serve: it is the capital and one-time outlay that
the value is a return *on* (build, integration, capex), optionally plus an
amortized slice of cost-to-serve. Conflating the two (dividing net value by
cost-to-serve) misstates ROI, so the two are separate objects.

Each component is ``Optional[Money]`` on the same ``None`` ≠ explicit-zero
discipline as :class:`~governed_value.domain.cost.CostToServe`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .money import Money

__all__ = ["TotalInvestment", "INVESTMENT_COMPONENTS"]

INVESTMENT_COMPONENTS = (
    "capital_expenditure",
    "one_time_build",
    "integration",
    "amortized_cost_to_serve",
)


@dataclass(frozen=True)
class TotalInvestment:
    currency: str
    capital_expenditure: Optional[Money] = None
    one_time_build: Optional[Money] = None
    integration: Optional[Money] = None
    amortized_cost_to_serve: Optional[Money] = None

    def __post_init__(self) -> None:
        for name in INVESTMENT_COMPONENTS:
            component: Optional[Money] = getattr(self, name)
            if component is not None and component.currency != self.currency:
                raise ValueError(
                    f"investment component {name!r} currency {component.currency} "
                    f"!= {self.currency}"
                )

    def missing_components(self) -> tuple[str, ...]:
        return tuple(n for n in INVESTMENT_COMPONENTS if getattr(self, n) is None)

    def total(self) -> Money:
        acc = Money.zero(self.currency)
        for name in INVESTMENT_COMPONENTS:
            component: Optional[Money] = getattr(self, name)
            if component is not None:
                acc = acc + component
        return acc
