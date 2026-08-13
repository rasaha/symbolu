"""Attribution context — the guardrails against the five common ROI failures.

Each field here maps to a documented way ROI models fail:

1. ``baseline_captured``          — no baseline captured before go-live
2. ``realization_rate`` +
   ``headcount_or_scope_changed`` — realization assumed at 100%
3. (TCO completeness lives in :class:`~governed_value.domain.cost.CostToServe`)
4. ``decay_per_period`` +
   ``periods_elapsed``            — no decay term; drift erodes value
5. ``concurrent_changes`` +
   ``holdout_or_staged``          — value credited fully amid several changes
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .rates import ONE, unit_ratio

__all__ = ["AttributionContext"]


@dataclass(frozen=True)
class AttributionContext:
    baseline_captured: bool
    realization_rate: Decimal = ONE
    headcount_or_scope_changed: bool = False
    attribution_fraction: Decimal = ONE
    concurrent_changes: int = 0
    holdout_or_staged: bool = False
    decay_per_period: Decimal = Decimal(0)
    periods_elapsed: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "realization_rate", unit_ratio(self.realization_rate, "realization_rate")
        )
        object.__setattr__(
            self,
            "attribution_fraction",
            unit_ratio(self.attribution_fraction, "attribution_fraction"),
        )
        object.__setattr__(
            self, "decay_per_period", unit_ratio(self.decay_per_period, "decay_per_period")
        )
        if not isinstance(self.concurrent_changes, int) or isinstance(
            self.concurrent_changes, bool
        ):
            raise ValueError("concurrent_changes must be an int")
        if self.concurrent_changes < 0:
            raise ValueError("concurrent_changes must be >= 0")
        if not isinstance(self.periods_elapsed, int) or isinstance(
            self.periods_elapsed, bool
        ):
            raise ValueError("periods_elapsed must be an int")
        if self.periods_elapsed < 0:
            raise ValueError("periods_elapsed must be >= 0")

    def decay_factor(self) -> Decimal:
        """``(1 - decay_per_period) ** periods_elapsed`` — value surviving drift.

        ROI is recomputed per period, not once; with ``periods_elapsed = 0`` the
        factor is 1 (the period the value was realized in).
        """

        return (ONE - self.decay_per_period) ** self.periods_elapsed

    def realization_composite(self) -> Decimal:
        """Organizational realization x attribution share x decay survival."""

        return self.realization_rate * self.attribution_fraction * self.decay_factor()
