"""Observation ingress (GV-PRODUCER) — bind typed observations to a case.

The kernel constructs no observation and attests none. It accepts
``MetricObservation`` values built elsewhere, checks that each one is about the
case in front of it, and records what it checked. Every failure is fail-closed:
:class:`ObservationBindingError` is raised and no result is produced, because a
figure scored beside a mis-bound observation is worse than one scored beside
none.

What this seam does **not** do: it does not lift ``evidence_status`` or
``authority_status``, it does not touch money, and it does not make an
observation true. See ``ADR_UGENCE_GOVERNED_VALUE_OBSERVATION_INGRESS.md`` §4.
"""

from __future__ import annotations

from typing import Iterable

from ugence_governance_contracts.contracts.evidence import MetricObservation

from ..domain.case import AgentValueCase
from ..domain.observation import ObservationBindingError, ObservedMetric

__all__ = ["admit_observations"]


def admit_observations(
    case: AgentValueCase, observations: Iterable[object]
) -> tuple[ObservedMetric, ...]:
    """Bind each observation to ``case`` or refuse the whole set."""

    admitted: list[ObservedMetric] = []
    seen: set[str] = set()
    for offered in observations:
        # Exact type: a subclass could relax the contract's own __post_init__.
        if type(offered) is not MetricObservation:
            raise ObservationBindingError(
                "observations must be MetricObservation values, got "
                f"{type(offered).__name__}"
            )
        if offered.tenant_id != case.tenant_id:
            raise ObservationBindingError(
                f"observation '{offered.observation_id}' belongs to tenant "
                f"'{offered.tenant_id}', not '{case.tenant_id}'"
            )
        if offered.governed_unit != case.domain.natural_unit:
            raise ObservationBindingError(
                f"observation '{offered.observation_id}' is measured in "
                f"'{offered.governed_unit}', but the case's natural unit is "
                f"'{case.domain.natural_unit}'"
            )
        if offered.observation_id in seen:
            raise ObservationBindingError(
                f"observation '{offered.observation_id}' offered twice"
            )
        seen.add(offered.observation_id)
        window = offered.assessment_window
        admitted.append(
            ObservedMetric(
                observation_id=offered.observation_id,
                metric_id=offered.metric_id,
                governed_unit=offered.governed_unit,
                window_start=window.start.isoformat(),
                window_end=window.end.isoformat(),
                evidence_reference_count=len(offered.evidence_refs),
                content_digest=offered.content_digest,
            )
        )
    return tuple(admitted)
