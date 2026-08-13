"""Portfolio normalization — commensurability across domains and geographies.

The whole reason to normalize to *net governed value per authorized action* is
to make heterogeneous agents comparable: a support agent in Manila and an
underwriting agent in Frankfurt line up on one axis. This service ranks scorable
agents by NGVA, aggregates a portfolio-wide NGVA, and — critically — **excludes**
``NOT_SCORABLE`` agents from the ranking rather than letting an indefensible
figure contaminate the comparison. Mixed currencies fail closed: normalization
requires one base currency (bring your own FX upstream).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from ..domain.enums import Scorability
from .scorer import GovernedValueResult

__all__ = ["PortfolioEntry", "PortfolioSummary", "normalize_portfolio"]


@dataclass(frozen=True)
class PortfolioEntry:
    agent_id: str
    ngva_per_action: Decimal
    scorability: Scorability
    net_governed_value_minor_units: int
    authorized_actions: int


@dataclass(frozen=True)
class PortfolioSummary:
    base_currency: str
    ranked: tuple[PortfolioEntry, ...]  # scorable + degraded, best NGVA first
    excluded: tuple[tuple[str, str], ...] = field(default_factory=tuple)  # (agent, reason)
    total_net_governed_value_minor_units: int = 0
    total_authorized_actions: int = 0

    @property
    def portfolio_ngva(self) -> Optional[Decimal]:
        if self.total_authorized_actions <= 0:
            return None
        return Decimal(self.total_net_governed_value_minor_units) / Decimal(
            self.total_authorized_actions
        )


def normalize_portfolio(
    results: list[GovernedValueResult],
    *,
    base_currency: str,
    include_degraded: bool = True,
) -> PortfolioSummary:
    """Rank agents by NGVA in one base currency.

    ``NOT_SCORABLE`` agents and any agent whose currency differs from
    ``base_currency`` are excluded from the ranking with a stated reason — never
    silently coerced.
    """

    entries: list[PortfolioEntry] = []
    excluded: list[tuple[str, str]] = []
    total_net = 0
    total_actions = 0

    for r in results:
        if r.currency != base_currency:
            excluded.append(
                (r.agent_id, f"currency {r.currency} != base {base_currency}; needs FX")
            )
            continue
        if r.scorability is Scorability.NOT_SCORABLE or r.ngva_per_action is None:
            excluded.append((r.agent_id, "not scorable: " + "; ".join(r.reasons)))
            continue
        if r.scorability is Scorability.DEGRADED and not include_degraded:
            excluded.append((r.agent_id, "degraded excluded by policy"))
            continue
        entries.append(
            PortfolioEntry(
                agent_id=r.agent_id,
                ngva_per_action=r.ngva_per_action,
                scorability=r.scorability,
                net_governed_value_minor_units=r.net_governed_value.minor_units,
                authorized_actions=r.authorized_actions,
            )
        )
        total_net += r.net_governed_value.minor_units
        total_actions += r.authorized_actions

    # Deterministic order: NGVA desc, then agent_id asc as a stable tiebreak.
    ranked = tuple(
        sorted(entries, key=lambda e: (-e.ngva_per_action, e.agent_id))
    )
    return PortfolioSummary(
        base_currency=base_currency,
        ranked=ranked,
        excluded=tuple(excluded),
        total_net_governed_value_minor_units=total_net,
        total_authorized_actions=total_actions,
    )
