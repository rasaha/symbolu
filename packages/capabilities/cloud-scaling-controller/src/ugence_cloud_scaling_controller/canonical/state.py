"""``CanonicalCapacityState`` — the versioned, immutable, provider-neutral contract for
a rich observation of the operational world around the Cloud Scaling Controller.

This is the *observation* layer. It is intentionally richer than the controller's
five-signal decision model: it can carry workload, performance, infrastructure,
capacity, reliability, deployment, economics, topology and forecast observations. The
rich state does **not** change the controller's decision model — an explicit projection
(see :mod:`.projection`) maps only the controller's established inputs, and everything
else is reported as ignored context.

Design rules:
  * Every category is optional — partial observations are first-class.
  * Every value object is a frozen dataclass and JSON-serializable via
    ``to_canonical_dict`` / reconstructable via ``from_dict`` (fail-closed on unknown
    top-level fields, so a misspelled decision-relevant field cannot pass silently).
  * Ambiguous-unit quantities are :class:`~.measurement.Measurement` (value + unit);
    ``desired != running != ready != healthy`` replica counts are kept distinct.
  * ``economics`` is informational only and must never influence a recommendation.
  * ``forecast`` is an optional evidence contract; it manufactures no prediction and
    never feeds the controller.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Tuple

from .identity import CapacitySubject
from .measurement import Measurement
from .provenance import ObservationProvenance
from .serialization import content_digest

CANONICAL_STATE_SCHEMA_VERSION = "capacity-state-1"
SUPPORTED_CANONICAL_STATE_SCHEMA_VERSIONS = frozenset({CANONICAL_STATE_SCHEMA_VERSION})

# Provider-neutral operational time context understood by the controller's adaptive gain.
VALID_TIME_PHASES = ("peak", "normal", "off_peak", "maintenance")


class StateError(ValueError):
    """Raised when a canonical state or sub-state is malformed (fail closed)."""


# --- field-kind validation framework (keeps the many sub-states honest & terse) ------

_MEASURE, _COUNT, _BOOL, _STR, _STR_TUPLE = "measure", "count", "bool", "str", "str_tuple"


def _v(kind: str, name: str, value: Any) -> None:
    if value is None:
        return
    if kind == _MEASURE:
        if not isinstance(value, Measurement):
            raise StateError(f"{name} must be a Measurement or None")
    elif kind == _COUNT:
        if isinstance(value, bool) or not isinstance(value, int):
            raise StateError(f"{name} must be an int count or None")
        if value < 0:
            raise StateError(f"{name} must be >= 0, got {value}")
    elif kind == _BOOL:
        if not isinstance(value, bool):
            raise StateError(f"{name} must be a bool or None")
    elif kind == _STR:
        if not isinstance(value, str) or value == "":
            raise StateError(f"{name} must be a non-empty string or None")
    elif kind == _STR_TUPLE:
        if not isinstance(value, tuple) or any(
            (not isinstance(x, str) or x == "") for x in value
        ):
            raise StateError(f"{name} must be a tuple of non-empty strings")


def _validate(obj: Any) -> None:
    kinds = _FIELD_KINDS[type(obj)]
    for f in fields(obj):
        _v(kinds[f.name], f.name, getattr(obj, f.name))


def _canon(obj: Any) -> Dict[str, Any]:
    kinds = _FIELD_KINDS[type(obj)]
    out: Dict[str, Any] = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        if kinds[f.name] == _MEASURE:
            out[f.name] = value.to_canonical_dict() if value is not None else None
        elif kinds[f.name] == _STR_TUPLE:
            out[f.name] = list(value)
        else:
            out[f.name] = value
    return out


def _from_dict(cls: Any, data: Any) -> Any:
    if not isinstance(data, Mapping):
        raise StateError(f"{cls.__name__} must be a mapping")
    kinds = _FIELD_KINDS[cls]
    unknown = set(data) - set(kinds)
    if unknown:
        raise StateError(f"unknown {cls.__name__} field(s): {sorted(unknown)}")
    kwargs: Dict[str, Any] = {}
    for name, kind in kinds.items():
        if name not in data or data[name] is None:
            continue
        raw = data[name]
        if kind == _MEASURE:
            kwargs[name] = Measurement.from_dict(raw)
        elif kind == _STR_TUPLE:
            if not isinstance(raw, (list, tuple)):
                raise StateError(f"{name} must be a list of strings")
            kwargs[name] = tuple(raw)
        else:
            kwargs[name] = raw
    return cls(**kwargs)


# --- sub-states ----------------------------------------------------------------------

@dataclass(frozen=True)
class WorkloadState:
    request_rate: Optional[Measurement] = None
    queue_depth: Optional[Measurement] = None
    queue_age: Optional[Measurement] = None
    concurrency: Optional[Measurement] = None
    jobs_pending: Optional[Measurement] = None
    throughput: Optional[Measurement] = None
    requests_per_second: Optional[Measurement] = None
    tokens_per_second: Optional[Measurement] = None
    batch_size: Optional[Measurement] = None

    def __post_init__(self) -> None:
        _validate(self)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return _canon(self)

    @classmethod
    def from_dict(cls, data: Any) -> "WorkloadState":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class PerformanceState:
    latency_p50: Optional[Measurement] = None
    latency_p95: Optional[Measurement] = None
    latency_p99: Optional[Measurement] = None
    timeout_rate: Optional[Measurement] = None
    throttle_rate: Optional[Measurement] = None

    def __post_init__(self) -> None:
        _validate(self)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return _canon(self)

    @classmethod
    def from_dict(cls, data: Any) -> "PerformanceState":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class InfrastructureState:
    cpu_utilization: Optional[Measurement] = None
    memory_utilization: Optional[Measurement] = None
    gpu_utilization: Optional[Measurement] = None
    gpu_memory_utilization: Optional[Measurement] = None
    network_utilization: Optional[Measurement] = None
    disk_iops_utilization: Optional[Measurement] = None

    def __post_init__(self) -> None:
        _validate(self)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return _canon(self)

    @classmethod
    def from_dict(cls, data: Any) -> "InfrastructureState":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class CapacityState:
    """Replica/capacity observations. ``desired != running != ready != healthy`` — the
    distinctions matter for later execution and effect verification and are preserved."""

    desired_replicas: Optional[int] = None
    running_replicas: Optional[int] = None
    ready_replicas: Optional[int] = None
    healthy_replicas: Optional[int] = None
    min_replicas: Optional[int] = None
    max_replicas: Optional[int] = None
    available_capacity: Optional[Measurement] = None
    capacity_headroom: Optional[Measurement] = None

    def __post_init__(self) -> None:
        _validate(self)
        if (self.min_replicas is not None and self.max_replicas is not None
                and self.min_replicas > self.max_replicas):
            raise StateError(
                f"min_replicas ({self.min_replicas}) must be <= max_replicas "
                f"({self.max_replicas})"
            )

    def to_canonical_dict(self) -> Dict[str, Any]:
        return _canon(self)

    @classmethod
    def from_dict(cls, data: Any) -> "CapacityState":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class ReliabilityState:
    error_rate: Optional[Measurement] = None
    restart_count: Optional[int] = None
    oom_rate: Optional[Measurement] = None
    health_failure_rate: Optional[Measurement] = None

    def __post_init__(self) -> None:
        _validate(self)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return _canon(self)

    @classmethod
    def from_dict(cls, data: Any) -> "ReliabilityState":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class DeploymentState:
    deploy_active: Optional[bool] = None
    rollout_phase: Optional[str] = None
    canary_active: Optional[bool] = None
    version: Optional[str] = None
    deployment_age: Optional[Measurement] = None

    def __post_init__(self) -> None:
        _validate(self)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return _canon(self)

    @classmethod
    def from_dict(cls, data: Any) -> "DeploymentState":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class EconomicsState:
    """Informational only. Never influences a Phase-1 recommendation."""

    estimated_hourly_cost: Optional[Measurement] = None
    marginal_scale_out_cost: Optional[Measurement] = None
    pricing_model: Optional[str] = None
    currency: Optional[str] = None

    def __post_init__(self) -> None:
        _validate(self)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return _canon(self)

    @classmethod
    def from_dict(cls, data: Any) -> "EconomicsState":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class TopologyState:
    """Identifiers / references only. No dependency-graph reasoning is performed."""

    service_id: Optional[str] = None
    cluster_id: Optional[str] = None
    region: Optional[str] = None
    zone: Optional[str] = None
    dependency_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate(self)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return _canon(self)

    @classmethod
    def from_dict(cls, data: Any) -> "TopologyState":
        return _from_dict(cls, data)


_FIELD_KINDS: Dict[Any, Dict[str, str]] = {
    WorkloadState: {n: _MEASURE for n in (
        "request_rate", "queue_depth", "queue_age", "concurrency", "jobs_pending",
        "throughput", "requests_per_second", "tokens_per_second", "batch_size")},
    PerformanceState: {n: _MEASURE for n in (
        "latency_p50", "latency_p95", "latency_p99", "timeout_rate", "throttle_rate")},
    InfrastructureState: {n: _MEASURE for n in (
        "cpu_utilization", "memory_utilization", "gpu_utilization",
        "gpu_memory_utilization", "network_utilization", "disk_iops_utilization")},
    CapacityState: {
        "desired_replicas": _COUNT, "running_replicas": _COUNT, "ready_replicas": _COUNT,
        "healthy_replicas": _COUNT, "min_replicas": _COUNT, "max_replicas": _COUNT,
        "available_capacity": _MEASURE, "capacity_headroom": _MEASURE},
    ReliabilityState: {
        "error_rate": _MEASURE, "restart_count": _COUNT,
        "oom_rate": _MEASURE, "health_failure_rate": _MEASURE},
    DeploymentState: {
        "deploy_active": _BOOL, "rollout_phase": _STR, "canary_active": _BOOL,
        "version": _STR, "deployment_age": _MEASURE},
    EconomicsState: {
        "estimated_hourly_cost": _MEASURE, "marginal_scale_out_cost": _MEASURE,
        "pricing_model": _STR, "currency": _STR},
    TopologyState: {
        "service_id": _STR, "cluster_id": _STR, "region": _STR, "zone": _STR,
        "dependency_ids": _STR_TUPLE},
}


@dataclass(frozen=True)
class ForecastObservation:
    """Optional forecast *evidence*. This records a forecast supplied by an external
    source; it does NOT train a model, generate a prediction, or manufacture confidence,
    and it never affects the controller. Absent → no forecasting is implied."""

    horizon_seconds: float
    predicted_demand: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    confidence: Optional[float] = None
    method: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("horizon_seconds", "predicted_demand"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise StateError(f"{name} must be a real number")
        if self.horizon_seconds <= 0:
            raise StateError("horizon_seconds must be > 0")
        for name in ("lower_bound", "upper_bound", "confidence"):
            v = getattr(self, name)
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
                raise StateError(f"{name} must be a real number or None")
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise StateError("confidence must be in [0, 1]")
        if (self.lower_bound is not None and self.upper_bound is not None
                and self.lower_bound > self.upper_bound):
            raise StateError("lower_bound must be <= upper_bound")
        if self.method is not None and (not isinstance(self.method, str) or self.method == ""):
            raise StateError("method must be a non-empty string or None")

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "horizon_seconds": self.horizon_seconds,
            "predicted_demand": self.predicted_demand,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "confidence": self.confidence,
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ForecastObservation":
        if not isinstance(data, Mapping):
            raise StateError("forecast must be a mapping")
        known = {"horizon_seconds", "predicted_demand", "lower_bound",
                 "upper_bound", "confidence", "method"}
        unknown = set(data) - known
        if unknown:
            raise StateError(f"unknown forecast field(s): {sorted(unknown)}")
        if "horizon_seconds" not in data or "predicted_demand" not in data:
            raise StateError("forecast requires 'horizon_seconds' and 'predicted_demand'")
        return cls(
            horizon_seconds=data["horizon_seconds"],
            predicted_demand=data["predicted_demand"],
            lower_bound=data.get("lower_bound"),
            upper_bound=data.get("upper_bound"),
            confidence=data.get("confidence"),
            method=data.get("method"),
        )


# --- top-level canonical state -------------------------------------------------------

_TOP_LEVEL_FIELDS = {
    "schema_version", "subject", "observed_at", "correlation_id", "time_phase",
    "workload", "performance", "infrastructure", "capacity", "reliability",
    "deployment", "economics", "topology", "forecast",
    "provenance", "measurement_provenance",
}

_SUBSTATE_TYPES = {
    "workload": WorkloadState,
    "performance": PerformanceState,
    "infrastructure": InfrastructureState,
    "capacity": CapacityState,
    "reliability": ReliabilityState,
    "deployment": DeploymentState,
    "economics": EconomicsState,
    "topology": TopologyState,
}


@dataclass(frozen=True)
class CanonicalCapacityState:
    """Immutable, versioned, provider-neutral canonical capacity observation.

    Required: ``subject``, ``observed_at`` (caller-supplied observation time). Every
    observation category is optional. ``provenance`` is the state-level default;
    ``measurement_provenance`` overrides it for individual signals when they originate
    from different sources or time windows.
    """

    subject: CapacitySubject
    observed_at: datetime
    schema_version: str = CANONICAL_STATE_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    time_phase: Optional[str] = None
    workload: Optional[WorkloadState] = None
    performance: Optional[PerformanceState] = None
    infrastructure: Optional[InfrastructureState] = None
    capacity: Optional[CapacityState] = None
    reliability: Optional[ReliabilityState] = None
    deployment: Optional[DeploymentState] = None
    economics: Optional[EconomicsState] = None
    topology: Optional[TopologyState] = None
    forecast: Optional[ForecastObservation] = None
    provenance: Optional[ObservationProvenance] = None
    measurement_provenance: Mapping[str, ObservationProvenance] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version not in SUPPORTED_CANONICAL_STATE_SCHEMA_VERSIONS:
            raise StateError(
                f"unsupported canonical state schema_version: {self.schema_version!r}"
            )
        if not isinstance(self.subject, CapacitySubject):
            raise StateError("subject must be a CapacitySubject")
        if not isinstance(self.observed_at, datetime):
            raise StateError("observed_at must be a datetime")
        if self.correlation_id is not None and not isinstance(self.correlation_id, str):
            raise StateError("correlation_id must be a string or None")
        if self.time_phase is not None and not isinstance(self.time_phase, str):
            raise StateError("time_phase must be a string or None")
        for name, expected in _SUBSTATE_TYPES.items():
            v = getattr(self, name)
            if v is not None and not isinstance(v, expected):
                raise StateError(f"{name} must be a {expected.__name__} or None")
        if self.forecast is not None and not isinstance(self.forecast, ForecastObservation):
            raise StateError("forecast must be a ForecastObservation or None")
        if self.provenance is not None and not isinstance(self.provenance, ObservationProvenance):
            raise StateError("provenance must be an ObservationProvenance or None")
        if not isinstance(self.measurement_provenance, Mapping):
            raise StateError("measurement_provenance must be a mapping")
        for key, prov in self.measurement_provenance.items():
            if not isinstance(key, str) or key == "":
                raise StateError("measurement_provenance keys must be non-empty strings")
            if not isinstance(prov, ObservationProvenance):
                raise StateError("measurement_provenance values must be ObservationProvenance")
        # Freeze the provenance mapping as an immutable copy.
        object.__setattr__(self, "measurement_provenance", dict(self.measurement_provenance))

    def provenance_for(self, signal: str) -> Optional[ObservationProvenance]:
        """Return the measurement-level provenance for ``signal`` if present, else the
        state-level default. ``None`` only when neither exists."""
        return self.measurement_provenance.get(signal, self.provenance)

    def to_canonical_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "subject": self.subject.to_canonical_dict(),
            "observed_at": self.observed_at,
            "correlation_id": self.correlation_id,
            "time_phase": self.time_phase,
            "provenance": self.provenance.to_canonical_dict() if self.provenance else None,
            "measurement_provenance": {
                k: v.to_canonical_dict() for k, v in self.measurement_provenance.items()
            },
        }
        for name in _SUBSTATE_TYPES:
            v = getattr(self, name)
            out[name] = v.to_canonical_dict() if v is not None else None
        out["forecast"] = self.forecast.to_canonical_dict() if self.forecast else None
        return out

    def digest(self) -> str:
        """Stable ``sha256:`` content identity of this observation."""
        return content_digest("capacity_state", self.schema_version, self.to_canonical_dict())

    @classmethod
    def from_dict(cls, data: Any) -> "CanonicalCapacityState":
        if not isinstance(data, Mapping):
            raise StateError("canonical state must be a mapping")
        unknown = set(data) - _TOP_LEVEL_FIELDS
        if unknown:
            raise StateError(f"unknown canonical state field(s): {sorted(unknown)}")
        if "subject" not in data or "observed_at" not in data:
            raise StateError("canonical state requires 'subject' and 'observed_at'")
        observed_at = data["observed_at"]
        if not isinstance(observed_at, datetime):
            raise StateError("observed_at must be a datetime")

        kwargs: Dict[str, Any] = {
            "subject": CapacitySubject.from_dict(data["subject"]),
            "observed_at": observed_at,
            "schema_version": data.get("schema_version", CANONICAL_STATE_SCHEMA_VERSION),
            "correlation_id": data.get("correlation_id"),
            "time_phase": data.get("time_phase"),
        }
        for name, sub_cls in _SUBSTATE_TYPES.items():
            if data.get(name) is not None:
                kwargs[name] = sub_cls.from_dict(data[name])
        if data.get("forecast") is not None:
            kwargs["forecast"] = ForecastObservation.from_dict(data["forecast"])
        if data.get("provenance") is not None:
            kwargs["provenance"] = _provenance_from_dict(data["provenance"])
        if data.get("measurement_provenance"):
            kwargs["measurement_provenance"] = {
                k: _provenance_from_dict(v)
                for k, v in data["measurement_provenance"].items()
            }
        return cls(**kwargs)


def _provenance_from_dict(data: Any) -> ObservationProvenance:
    from .provenance import ObservationSourceType, ProvenanceError

    if not isinstance(data, Mapping):
        raise StateError("provenance must be a mapping")
    known = {"source_type", "source_id", "provider", "observed_at",
             "collected_at", "metric_window_seconds"}
    unknown = set(data) - known
    if unknown:
        raise StateError(f"unknown provenance field(s): {sorted(unknown)}")
    if "source_type" not in data or "observed_at" not in data:
        raise StateError("provenance requires 'source_type' and 'observed_at'")
    try:
        source_type = ObservationSourceType(data["source_type"])
    except ValueError as exc:
        raise StateError(f"unsupported source_type: {data['source_type']!r}") from exc
    try:
        return ObservationProvenance(
            source_type=source_type,
            observed_at=data["observed_at"],
            source_id=data.get("source_id"),
            provider=data.get("provider"),
            collected_at=data.get("collected_at"),
            metric_window_seconds=data.get("metric_window_seconds"),
        )
    except ProvenanceError as exc:
        raise StateError(str(exc)) from exc


__all__ = [
    "CANONICAL_STATE_SCHEMA_VERSION",
    "SUPPORTED_CANONICAL_STATE_SCHEMA_VERSIONS",
    "VALID_TIME_PHASES",
    "StateError",
    "WorkloadState",
    "PerformanceState",
    "InfrastructureState",
    "CapacityState",
    "ReliabilityState",
    "DeploymentState",
    "EconomicsState",
    "TopologyState",
    "ForecastObservation",
    "CanonicalCapacityState",
]
