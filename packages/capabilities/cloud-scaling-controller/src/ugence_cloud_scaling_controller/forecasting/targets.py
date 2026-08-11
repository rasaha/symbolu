"""Forecast targets, their domains, and leakage-free extraction from canonical states.

A :class:`ForecastTarget` names one controller-relevant signal that Phase 2 may forecast.
Each target is bound to exactly one canonical field path — the SAME field the Phase-1
projection reads — so a forecast can never silently substitute a different replica
semantic or a different latency percentile:

    CPU_UTILIZATION     -> infrastructure.cpu_utilization   (Measurement)
    MEMORY_UTILIZATION  -> infrastructure.memory_utilization(Measurement)
    P99_LATENCY         -> performance.latency_p99           (Measurement)
    ERROR_RATE          -> reliability.error_rate            (Measurement)
    QUEUE_DEPTH         -> workload.queue_depth              (Measurement)
    RUNNING_REPLICAS    -> capacity.running_replicas         (int; the SAME field the
                            projection maps to ScalingObservation.current_replicas —
                            never desired/ready/healthy)

Extraction is *raw*: the observed value and its unit are returned unchanged. No unit
conversion, clamping, or imputation happens here — that separation ("no silent unit
conversion") is a Phase-2 invariant. A target that is absent on a state yields ``None``
(an explicit missing sample), never a fabricated value.

A :class:`SignalDomain` describes the admissible value range for a (target, unit) pair
so a forecaster can detect an out-of-domain extrapolation instead of silently clamping.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from ..canonical.measurement import Measurement, Unit
from ..canonical.state import CanonicalCapacityState


class TargetError(ValueError):
    """Raised when a target cannot be resolved safely (fail closed)."""


class ForecastTarget(str, Enum):
    """A controller-relevant signal that may be forecast in shadow mode."""

    CPU_UTILIZATION = "cpu_utilization"
    MEMORY_UTILIZATION = "memory_utilization"
    P99_LATENCY = "p99_latency"
    ERROR_RATE = "error_rate"
    QUEUE_DEPTH = "queue_depth"
    RUNNING_REPLICAS = "running_replicas"


# Synthetic unit label for the raw integer replica count (which is NOT a Measurement).
REPLICAS_UNIT = "replicas"


@dataclass(frozen=True)
class SignalDomain:
    """Admissible value domain for a target measured in a specific unit.

    ``lower``/``upper`` are inclusive finite bounds or ``None`` (unbounded). ``integer``
    marks integer-valued domains (counts, replica counts). Used to detect out-of-domain
    forecasts; the forecasting layer never silently clamps into the domain.
    """

    label: str
    lower: Optional[float]
    upper: Optional[float]
    integer: bool

    def contains(self, value: float, *, tol: float = 1e-9) -> bool:
        if self.lower is not None and value < self.lower - tol:
            return False
        if self.upper is not None and value > self.upper + tol:
            return False
        return True


@dataclass(frozen=True)
class TargetSample:
    """One extracted observation of a target: event time, raw value, and unit.

    ``event_time`` is the observation's event time (``CanonicalCapacityState.observed_at``)
    — never a collection or production time. ``unit`` is the raw unit string exactly as
    observed (or :data:`REPLICAS_UNIT` for the integer replica count).
    """

    event_time: datetime
    value: float
    unit: str


def _domain_for_unit(unit: str) -> SignalDomain:
    """Derive the admissible domain from a raw unit string (no conversion implied)."""
    if unit in (Unit.RATIO.value, Unit.RATE.value):
        return SignalDomain(unit, 0.0, 1.0, integer=False)
    if unit == Unit.PERCENT.value:
        return SignalDomain(unit, 0.0, 100.0, integer=False)
    if unit in (Unit.MILLISECONDS.value, Unit.SECONDS.value, Unit.PER_SECOND.value,
                Unit.BYTES.value, Unit.CORES.value):
        return SignalDomain(unit, 0.0, None, integer=False)
    if unit == Unit.COUNT.value:
        return SignalDomain(unit, 0.0, None, integer=True)
    if unit == REPLICAS_UNIT:
        return SignalDomain(unit, 0.0, None, integer=True)
    # Unknown/opaque unit: unbounded, non-integer. The forecaster still records it.
    return SignalDomain(unit, None, None, integer=False)


def domain_for(unit: str) -> SignalDomain:
    """Public accessor for the admissible domain of a raw unit string."""
    return _domain_for_unit(unit)


def _measurement_for(state: CanonicalCapacityState, target: ForecastTarget) -> Optional[Measurement]:
    if target is ForecastTarget.CPU_UTILIZATION:
        return None if state.infrastructure is None else state.infrastructure.cpu_utilization
    if target is ForecastTarget.MEMORY_UTILIZATION:
        return None if state.infrastructure is None else state.infrastructure.memory_utilization
    if target is ForecastTarget.P99_LATENCY:
        return None if state.performance is None else state.performance.latency_p99
    if target is ForecastTarget.ERROR_RATE:
        return None if state.reliability is None else state.reliability.error_rate
    if target is ForecastTarget.QUEUE_DEPTH:
        return None if state.workload is None else state.workload.queue_depth
    raise TargetError(f"{target.value} is not a Measurement-backed target")


def extract_sample(
    state: CanonicalCapacityState, target: ForecastTarget
) -> Optional[TargetSample]:
    """Extract the raw sample for ``target`` from ``state`` (``None`` if absent).

    RUNNING_REPLICAS reads ``capacity.running_replicas`` and never substitutes
    desired/ready/healthy — the same never-substitute rule the Phase-1 projection
    enforces for ``current_replicas``.
    """
    if not isinstance(state, CanonicalCapacityState):
        raise TargetError("state must be a CanonicalCapacityState")
    if not isinstance(target, ForecastTarget):
        raise TargetError("target must be a ForecastTarget")

    if target is ForecastTarget.RUNNING_REPLICAS:
        if state.capacity is None or state.capacity.running_replicas is None:
            return None
        return TargetSample(
            event_time=state.observed_at,
            value=float(int(state.capacity.running_replicas)),
            unit=REPLICAS_UNIT,
        )

    measurement = _measurement_for(state, target)
    if measurement is None:
        return None
    return TargetSample(
        event_time=state.observed_at,
        value=float(measurement.value),
        unit=measurement.unit.value,
    )


__all__ = [
    "TargetError",
    "ForecastTarget",
    "REPLICAS_UNIT",
    "SignalDomain",
    "TargetSample",
    "domain_for",
    "extract_sample",
]
