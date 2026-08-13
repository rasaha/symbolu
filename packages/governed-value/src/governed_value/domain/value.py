"""Realized value — the numerator, decomposed into exactly three sources.

    realized value = labor displaced + throughput/revenue gained + loss avoided

Anything a caller is tempted to add here that is *not* one of these three
(satisfaction, "productivity", adoption, story points) is a leading indicator,
not value, and belongs in a separate leading-indicator channel — never in the
ROI numerator.
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
        # One currency across the numerator; combining is exact and total-able.
        c = self.labor_displaced.currency
        # ``+`` fails closed on any currency mismatch.
        _ = self.labor_displaced + self.throughput_gained + self.loss_avoided
        object.__setattr__(self, "_currency", c)

    @property
    def currency(self) -> str:
        return self.labor_displaced.currency

    def gross(self) -> Money:
        """Total realized value before realization / attribution / risk terms."""

        return self.labor_displaced + self.throughput_gained + self.loss_avoided
