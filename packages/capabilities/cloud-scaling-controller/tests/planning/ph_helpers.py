"""Deterministic builders for Phase-3 capacity-planning tests (no clocks, no randomness).

Every timestamp is caller-supplied and timezone-aware; every value is explicit. Forecast
evidence is produced through the REAL Phase-2 service path (point-only uncertainty) so the
tests exercise genuine, digest-bound forecast evidence rather than a hand-built stub.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence

from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState,
    CapacityState,
    CapacitySubject,
    Measurement,
    NormalizationMethod,
    NormalizationPolicy,
    ReliabilityState,
    Unit,
)
from ugence_cloud_scaling_controller.forecasting import (
    ForecastHorizon,
    ForecastTarget,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    forecast_with_evidence,
    CanonicalCapacitySeries,
)
from ugence_cloud_scaling_controller.planning import (
    CostBasis,
    CostBook,
    CostEvidence,
    DependencyEdge,
    DependencyKind,
    DependencyTopology,
    Money,
    OperatingConstraints,
    RecommendationPolicy,
)

T0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def subject(workload_id: str = "app", tenant_id: Optional[str] = "tenant-1") -> CapacitySubject:
    return CapacitySubject(workload_id=workload_id, tenant_id=tenant_id)


def at(seconds: float, start: datetime = T0) -> datetime:
    return start + timedelta(seconds=seconds)


def replicas_state(
    when: datetime, running: int, *, subj: Optional[CapacitySubject] = None,
    error_rate: Optional[float] = None,
) -> CanonicalCapacityState:
    rel = ReliabilityState(error_rate=Measurement(error_rate, Unit.RATE)) if error_rate is not None else None
    return CanonicalCapacityState(
        subject=subj or subject(),
        observed_at=when,
        capacity=CapacityState(running_replicas=running),
        reliability=rel,
    )


def _np() -> NormalizationPolicy:
    # RUNNING_REPLICAS is projected without conversion; the policy is required to be present
    # but its methods are not consulted for the replica target.
    return NormalizationPolicy(policy_id="np-1", method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO})


def build_forecast_evidence(
    predicted_replicas: int,
    *,
    subj: Optional[CapacitySubject] = None,
    cutoff: datetime = None,
    horizon_seconds: float = 900.0,
    history: int = 4,
):
    """Build genuine RUNNING_REPLICAS point-forecast evidence (persistence == last value)."""
    subj = subj or subject()
    cutoff = cutoff or at(180.0)
    # Persistence forecaster returns the last observed value: make the series end at the
    # predicted replica count.
    states = [replicas_state(at(60.0 * i), predicted_replicas, subj=subj) for i in range(history)]
    series = CanonicalCapacitySeries.build(states)
    horizon = ForecastHorizon(seconds=horizon_seconds, label=f"{int(horizon_seconds)}s")
    return forecast_with_evidence(
        series, ForecastTarget.RUNNING_REPLICAS, cutoff, horizon, PersistenceForecaster(),
        normalization_policy=_np(),
        uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE),
    )


def build_abstained_forecast(*, subj: Optional[CapacitySubject] = None, cutoff: datetime = None):
    """A genuine RUNNING_REPLICAS forecast that ABSTAINS (normalized space is unsupported)."""
    from ugence_cloud_scaling_controller.forecasting import ForecastValueSpace
    subj = subj or subject()
    cutoff = cutoff or at(180.0)
    states = [replicas_state(at(60.0 * i), 6, subj=subj) for i in range(4)]
    series = CanonicalCapacitySeries.build(states)
    horizon = ForecastHorizon(seconds=900.0, label="900s")
    return forecast_with_evidence(
        series, ForecastTarget.RUNNING_REPLICAS, cutoff, horizon, PersistenceForecaster(),
        normalization_policy=_np(),
        uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE),
        forecast_space=ForecastValueSpace.NORMALIZED,  # unsupported for replicas -> abstains
    )


def build_cpu_forecast_evidence(*, subj: Optional[CapacitySubject] = None, cutoff: datetime = None):
    """A genuine point forecast on a NON-planning target (cpu_utilization)."""
    from ugence_cloud_scaling_controller.canonical import InfrastructureState
    subj = subj or subject()
    cutoff = cutoff or at(180.0)
    states = []
    for i in range(4):
        states.append(CanonicalCapacityState(
            subject=subj, observed_at=at(60.0 * i),
            infrastructure=InfrastructureState(cpu_utilization=Measurement(50.0, Unit.PERCENT))))
    series = CanonicalCapacitySeries.build(states)
    horizon = ForecastHorizon(seconds=900.0, label="900s")
    return forecast_with_evidence(
        series, ForecastTarget.CPU_UTILIZATION, cutoff, horizon, PersistenceForecaster(),
        normalization_policy=_np(),
        uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE),
    )


def cost_book(
    *, subj: Optional[CapacitySubject] = None, app_price_minor: int = 1000, currency: str = "USD",
    dependency: Optional[CapacitySubject] = None, dep_price_minor: int = 50,
    effective_from: datetime = None, effective_until: datetime = None,
    app_basis: CostBasis = CostBasis.PER_REPLICA_HOUR,
) -> CostBook:
    subj = subj or subject()
    effective_from = effective_from or at(-3600.0)
    effective_until = effective_until or at(36000.0)
    entries = [CostEvidence(subj, Money(app_price_minor, currency), app_basis,
                            effective_from, effective_until, evidence_source="fixture")]
    if dependency is not None:
        entries.append(CostEvidence(dependency, Money(dep_price_minor, currency),
                                    CostBasis.PER_CONNECTION_HOUR, effective_from, effective_until,
                                    evidence_source="fixture"))
    return CostBook(subject=subj, entries=tuple(entries))


def constraints(
    *, min_capacity: int = 1, max_capacity: int = 50, allowed_step: int = 1,
    **kw,
) -> OperatingConstraints:
    return OperatingConstraints(min_capacity=min_capacity, max_capacity=max_capacity,
                                allowed_step=allowed_step, **kw)


def policy(**kw) -> RecommendationPolicy:
    return RecommendationPolicy(**kw)


def make_ctx(
    *, predicted: int = 8, current: int = 6, subj: Optional[CapacitySubject] = None,
    con: Optional[OperatingConstraints] = None, cb: Optional[CostBook] = None,
    topo=None, recommendation_time: datetime = None,
):
    """Build a deterministic EvaluationContext for feasibility/scoring unit tests."""
    from ugence_cloud_scaling_controller.planning import build_context
    subj = subj or subject()
    fe = build_forecast_evidence(predicted, subj=subj)
    st = replicas_state(at(180.0), current, subj=subj)
    con = con or constraints()
    cb = cb or cost_book(subj=subj)
    recommendation_time = recommendation_time or at(190.0)
    return build_context(fe, st, topo, cb, con, recommendation_time=recommendation_time)


def topology(
    *, subj: Optional[CapacitySubject] = None, dependency: Optional[CapacitySubject] = None,
    kind: DependencyKind = DependencyKind.CAPACITY_BOUND,
    downstream_current: Optional[int] = 100, required_per_upstream_unit: Optional[float] = 20.0,
    as_of: datetime = None, extra_edges: Sequence[DependencyEdge] = (),
) -> DependencyTopology:
    subj = subj or subject()
    as_of = as_of or at(120.0)
    edges = list(extra_edges)
    if dependency is not None:
        edges.append(DependencyEdge(subj, dependency, kind,
                                    downstream_current_capacity=downstream_current,
                                    required_per_upstream_unit=required_per_upstream_unit))
    return DependencyTopology(subject=subj, as_of=as_of, edges=tuple(edges),
                             evidence_source="fixture")
