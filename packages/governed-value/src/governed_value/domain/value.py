"""Realized value — already realized and already attributable.

    total benefit = attributable realized benefit + attributed avoided loss
    attributable realized benefit = labor displaced + throughput/revenue gained
    attributed avoided loss        = loss avoided

In a POST_DEPLOYMENT_VALUE calculation these are outcomes that have already
occurred and are already credited to the agent. **No realization, attribution,
decay or locale factor is applied to them** — discounting an already-realized,
already-attributed benefit is the double-discount error GV-1 exists to prevent.

Anything that is not one of these sources (satisfaction, "productivity",
adoption, story points) is a leading indicator, not value, and belongs in the
readiness stage (GV-3r), never in this numerator.
"""

from __future__ import annotations

from dataclasses import dataclass

from .money import Money

__all__ = ["RealizedValue"]


@dataclass(frozen=True)
class RealizedValue:
    labor_displaced: Money
    throughput_gained: Money
    loss_avoided: Money

    def __post_init__(self) -> None:
        # One currency across the numerator; ``+`` fails closed on mismatch.
        _ = self.labor_displaced + self.throughput_gained + self.loss_avoided

    @property
    def currency(self) -> str:
        return self.labor_displaced.currency

    def attributable_benefit(self) -> Money:
        """Realized benefit from labor + throughput (excludes avoided loss)."""

        return self.labor_displaced + self.throughput_gained

    def attributed_avoided_loss(self) -> Money:
        """Verified avoided loss credited as a benefit."""

        return self.loss_avoided

    def gross(self) -> Money:
        """Total benefit = attributable realized benefit + attributed avoided loss."""

        return self.labor_displaced + self.throughput_gained + self.loss_avoided
