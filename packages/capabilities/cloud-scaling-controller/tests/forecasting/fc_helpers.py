"""Deterministic builders for Phase-2 forecasting tests (no clocks, no randomness).

Every timestamp is caller-supplied and timezone-aware; every value is explicit. These
helpers only assemble canonical states — they never impute or normalize.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence

from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState,
    CapacitySubject,
    CapacityState,
    InfrastructureState,
    Measurement,
    NormalizationMethod,
    NormalizationPolicy,
    PerformanceState,
    ReliabilityState,
    Unit,
    WorkloadState,
)

T0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def subject(workload_id: str = "wl-1", tenant_id: Optional[str] = "tenant-1") -> CapacitySubject:
    return CapacitySubject(workload_id=workload_id, tenant_id=tenant_id)


def cpu_state(
    at: datetime,
    cpu_percent: Optional[float] = None,
    *,
    subj: Optional[CapacitySubject] = None,
    running_replicas: Optional[int] = 4,
    correlation_id: Optional[str] = None,
) -> CanonicalCapacityState:
    infra = InfrastructureState(cpu_utilization=Measurement(cpu_percent, Unit.PERCENT)) if cpu_percent is not None else None
    cap = CapacityState(running_replicas=running_replicas) if running_replicas is not None else None
    return CanonicalCapacityState(
        subject=subj or subject(),
        observed_at=at,
        infrastructure=infra,
        capacity=cap,
        correlation_id=correlation_id,
    )


def replicas_state(at: datetime, running: int, *, subj: Optional[CapacitySubject] = None) -> CanonicalCapacityState:
    return CanonicalCapacityState(
        subject=subj or subject(),
        observed_at=at,
        capacity=CapacityState(running_replicas=running),
    )


def cpu_series_states(
    values: Sequence[float],
    *,
    start: datetime = T0,
    cadence_seconds: float = 60.0,
    subj: Optional[CapacitySubject] = None,
) -> List[CanonicalCapacityState]:
    """One CPU-percent observation per value, at a fixed cadence."""
    subj = subj or subject()
    out: List[CanonicalCapacityState] = []
    for i, v in enumerate(values):
        at = start + timedelta(seconds=cadence_seconds * i)
        out.append(cpu_state(at, v, subj=subj))
    return out


def cpu_norm_policy(policy_id: str = "cpu-p1") -> NormalizationPolicy:
    return NormalizationPolicy(
        policy_id=policy_id,
        method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO},
    )


def at(seconds: float, start: datetime = T0) -> datetime:
    return start + timedelta(seconds=seconds)
