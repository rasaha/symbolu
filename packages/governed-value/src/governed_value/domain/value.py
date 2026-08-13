"""Reported value — caller-asserted, already realized and already attributable.

    total benefit  = reported benefit + reported avoided loss
    reported benefit      = labor displaced + throughput/revenue gained
    reported avoided loss = loss avoided

**These are caller assertions about the supplied accounting period, not
determinations by this kernel.** The type is named ``ReportedValue`` (and its
accessors ``reported_*``) precisely so no name implies the kernel observed,
attributed or verified anything — it did not (every result is classified
``REPORTED / UNVERIFIED``). The caller states these amounts are realized and
attributable; the kernel takes them at face value and applies **no** realization,
attribution, decay, locale, adoption or probability discount to them — doing so
would discount an already-realized figure a second time.

Anything that is not one of these sources (satisfaction, "productivity",
adoption, story points) is a leading indicator, not value, and belongs in the
readiness stage (GV-3r), never in this numerator.
"""

from __future__ import annotations

from dataclasses import dataclass

from .money import Money

__all__ = ["ReportedValue"]


@dataclass(frozen=True)
class ReportedValue:
    labor_displaced: Money
    throughput_gained: Money
    loss_avoided: Money

    def __post_init__(self) -> None:
        # One currency across the numerator; ``+`` fails closed on mismatch.
        _ = self.labor_displaced + self.throughput_gained + self.loss_avoided

    @property
    def currency(self) -> str:
        return self.labor_displaced.currency

    def reported_benefit(self) -> Money:
        """Caller-reported benefit from labor + throughput (excludes avoided loss)."""

        return self.labor_displaced + self.throughput_gained

    def reported_avoided_loss(self) -> Money:
        """Caller-reported avoided loss credited as a benefit."""

        return self.loss_avoided

    def gross(self) -> Money:
        """Total benefit = reported benefit + reported avoided loss."""

        return self.labor_displaced + self.throughput_gained + self.loss_avoided
