"""Application facade — the single entry point for realized-value scoring.

Transport-neutral: it scores a case and emits a governance event carrying the
full classification. Forecast, readiness and portfolio comparison are separate
engines/phases and are not exposed here.
"""

from __future__ import annotations

from typing import Optional

from ..domain.case import AgentValueCase
from ..domain.events import GovernedValueEvent
from ..observability.events import EventBus
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
                stage=result.stage,
                evidence_status=result.evidence_status,
                authority_status=result.authority_status,
                scorability=result.scorability,
                measurement_method=result.measurement_method,
                reported_net_governed_value_minor_units=(
                    result.reported_net_governed_value.minor_units
                ),
                risk_adjusted_net_governed_value_minor_units=(
                    result.risk_adjusted_net_governed_value.minor_units
                ),
                reported_roi=result.reported_roi,
                reasons=result.reasons,
                advisories=result.advisories,
            )
        )
        return result
