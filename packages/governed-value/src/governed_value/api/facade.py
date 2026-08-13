"""Application facade — the one entry point most callers need.

``GovernedValueApplication`` scores a case (emitting a governance event),
projects value under decay, and normalizes a set of results into a comparable
portfolio. It is transport-neutral: an HTTP adapter can wrap it, but the facade
has no web dependency.
"""

from __future__ import annotations

from typing import Optional

from ..domain.case import AgentValueCase
from ..domain.events import GovernedValueEvent
from ..observability.events import EventBus
from ..services.decay import project_periods
from ..services.portfolio import PortfolioSummary, normalize_portfolio
from ..services.scorer import GovernedValueResult, score_case

__all__ = ["GovernedValueApplication"]


class GovernedValueApplication:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._events = event_bus or EventBus()

    @property
    def events(self) -> EventBus:
        return self._events

    def score(self, case: AgentValueCase) -> GovernedValueResult:
        result = score_case(case)
        self._events.publish(
            GovernedValueEvent(
                event_type="governed_value.scored",
                tenant_id=result.tenant_id,
                agent_id=result.agent_id,
                scorability=result.scorability,
                measurement_method=result.measurement_method,
                net_governed_value_minor_units=result.net_governed_value.minor_units,
                authorized_actions=result.authorized_actions,
                ngva_per_action=result.ngva_per_action,
                reasons=result.reasons,
                advisories=result.advisories,
            )
        )
        return result

    def project(self, case: AgentValueCase, horizon: int) -> list[GovernedValueResult]:
        return project_periods(case, horizon)

    def compare(
        self,
        cases: list[AgentValueCase],
        *,
        base_currency: str,
        include_degraded: bool = True,
    ) -> PortfolioSummary:
        results = [self.score(c) for c in cases]
        return normalize_portfolio(
            results, base_currency=base_currency, include_degraded=include_degraded
        )
