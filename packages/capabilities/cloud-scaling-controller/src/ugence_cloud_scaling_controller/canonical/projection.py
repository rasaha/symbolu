"""Explicit, deterministic projection: ``CanonicalCapacityState`` → ``ScalingObservation``.

The rich canonical state must NOT silently expand the controller's five-signal decision
model. This projection maps *only* the controller's established inputs and reports
everything else as ignored context. It is deterministic, provider-neutral, side-effect
free (no network, no clock reads), and fails closed on ambiguous required mappings.

Established mappings (verified against the shipped ``ScalingObservation`` /
``Controller.step`` contract):

    infrastructure.cpu_utilization     -> metrics["cpu"]
    infrastructure.memory_utilization  -> metrics["memory"]
    performance.latency_p99            -> metrics["latency_p99"]
    reliability.error_rate             -> metrics["error_rate"]
    workload.queue_depth               -> metrics["queue_depth"]
    deployment.deploy_active           -> deploy_active
    reliability.restart_count          -> recent_pod_restarts
    capacity.running_replicas          -> current_replicas   (REQUIRED)
    time_phase                         -> phase
    correlation_id                     -> correlation_id
    observed_at                        -> timestamp (epoch seconds)

Capacity semantics: the controller documents ``current_replicas`` as the *current
running replica count*, so the projection reads ``capacity.running_replicas`` and never
silently substitutes ``ready``/``healthy``/``desired`` (which are distinct and matter for
later execution/effect verification). If ``running_replicas`` is absent the projection
fails closed rather than choosing a convenient field.

Latency: ``latency_p99 != latency_p95``. p95 is used only when the policy explicitly
opts in (``allow_latency_p95_substitution``); the substitution is then disclosed in the
projection warnings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..contracts import ScalingObservation
from .measurement import Measurement
from .normalization import NormalizationPolicy, NormalizedSignal, normalize_signal
from .state import CanonicalCapacityState

PROJECTION_SCHEMA_VERSION = "capacity-projection-1"

# The five decision-driving controller signals (order fixed for deterministic output).
CONTROLLER_SIGNALS = ("cpu", "memory", "latency_p99", "error_rate", "queue_depth")


class ProjectionError(ValueError):
    """Raised when the canonical state cannot be projected safely (fail closed)."""


@dataclass(frozen=True)
class ControllerProjection:
    """The result of projecting a canonical state onto the controller's inputs.

    Everything a reviewer needs to see what reached the controller and what did not.
    """

    schema_version: str
    observation: ScalingObservation
    normalized_signals: Tuple[NormalizedSignal, ...]
    projected_signals: Dict[str, float]
    used_canonical_fields: Tuple[str, ...]
    ignored_canonical_fields: Tuple[str, ...]
    missing_controller_signals: Tuple[str, ...]
    policy_id: str
    warnings: Tuple[str, ...] = field(default_factory=tuple)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "projected_signals": dict(self.projected_signals),
            "normalized_signals": [s.to_canonical_dict() for s in self.normalized_signals],
            "used_canonical_fields": list(self.used_canonical_fields),
            "ignored_canonical_fields": list(self.ignored_canonical_fields),
            "missing_controller_signals": list(self.missing_controller_signals),
            "policy_id": self.policy_id,
            "warnings": list(self.warnings),
            "current_replicas": self.observation.current_replicas,
            "deploy_active": self.observation.deploy_active,
            "recent_pod_restarts": self.observation.recent_pod_restarts,
            "phase": self.observation.phase,
            "correlation_id": self.observation.correlation_id,
            "timestamp": self.observation.timestamp,
        }


def _epoch_seconds(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _present_canonical_fields(state: CanonicalCapacityState) -> List[str]:
    """Every present (non-None) canonical field path, for the ignored/used accounting."""
    present: List[str] = []
    for group in ("workload", "performance", "infrastructure", "capacity",
                  "reliability", "deployment", "economics", "topology"):
        sub = getattr(state, group)
        if sub is None:
            continue
        for f_name, value in sub.to_canonical_dict().items():
            if value is None or value == [] or value == ():
                continue
            present.append(f"{group}.{f_name}")
    if state.forecast is not None:
        present.append("forecast")
    if state.time_phase is not None:
        present.append("time_phase")
    return present


def project_to_scaling_observation(
    state: CanonicalCapacityState,
    normalization_policy: NormalizationPolicy,
) -> ControllerProjection:
    """Deterministically project ``state`` onto a ``ScalingObservation`` (fail-closed)."""
    if not isinstance(state, CanonicalCapacityState):
        raise ProjectionError("state must be a CanonicalCapacityState")
    if not isinstance(normalization_policy, NormalizationPolicy):
        raise ProjectionError("normalization_policy must be a NormalizationPolicy")

    warnings: List[str] = []
    used: List[str] = []

    # --- current_replicas (required) -> capacity.running_replicas -------------------
    if state.capacity is None or state.capacity.running_replicas is None:
        raise ProjectionError(
            "capacity.running_replicas is required to project current_replicas; it maps "
            "to the controller's 'current running replica count' and is never substituted "
            "by ready/healthy/desired"
        )
    current_replicas = int(state.capacity.running_replicas)
    used.append("capacity.running_replicas")

    # --- five decision signals -------------------------------------------------------
    metrics: Dict[str, float] = {}
    normalized: List[NormalizedSignal] = []
    missing: List[str] = []

    def _emit(signal: str, measurement: Measurement, source_path: str) -> None:
        ns = normalize_signal(
            signal, measurement, normalization_policy, state.provenance_for(signal)
        )
        metrics[signal] = ns.normalized_value
        normalized.append(ns)
        used.append(source_path)

    # cpu, memory
    infra = state.infrastructure
    if infra is not None and infra.cpu_utilization is not None:
        _emit("cpu", infra.cpu_utilization, "infrastructure.cpu_utilization")
    else:
        missing.append("cpu")
    if infra is not None and infra.memory_utilization is not None:
        _emit("memory", infra.memory_utilization, "infrastructure.memory_utilization")
    else:
        missing.append("memory")

    # latency_p99 (with explicit, disclosed p95 opt-in)
    perf = state.performance
    if perf is not None and perf.latency_p99 is not None:
        _emit("latency_p99", perf.latency_p99, "performance.latency_p99")
    elif (perf is not None and perf.latency_p95 is not None
          and normalization_policy.allow_latency_p95_substitution):
        _emit("latency_p99", perf.latency_p95, "performance.latency_p95")
        warnings.append(
            "latency_p99 absent; policy-authorized substitution of latency_p95 for the "
            "latency_p99 controller signal (disclosed)"
        )
    else:
        missing.append("latency_p99")

    # error_rate
    rel = state.reliability
    if rel is not None and rel.error_rate is not None:
        _emit("error_rate", rel.error_rate, "reliability.error_rate")
    else:
        missing.append("error_rate")

    # queue_depth
    wl = state.workload
    if wl is not None and wl.queue_depth is not None:
        _emit("queue_depth", wl.queue_depth, "workload.queue_depth")
    else:
        missing.append("queue_depth")

    # --- non-signal controller inputs ------------------------------------------------
    deploy_active = False
    if state.deployment is not None and state.deployment.deploy_active is not None:
        deploy_active = bool(state.deployment.deploy_active)
        used.append("deployment.deploy_active")

    recent_pod_restarts = 0
    if state.reliability is not None and state.reliability.restart_count is not None:
        recent_pod_restarts = int(state.reliability.restart_count)
        used.append("reliability.restart_count")

    phase = "normal"
    if state.time_phase is not None:
        phase = state.time_phase
        used.append("time_phase")

    timestamp = _epoch_seconds(state.observed_at)

    observation = ScalingObservation(
        metrics=metrics,
        current_replicas=current_replicas,
        deploy_active=deploy_active,
        phase=phase,
        recent_pod_restarts=recent_pod_restarts,
        correlation_id=state.correlation_id,
        timestamp=timestamp,
    ).validate()

    # --- ignored accounting ----------------------------------------------------------
    present = _present_canonical_fields(state)
    used_set = set(used)
    ignored = tuple(sorted(p for p in present if p not in used_set))

    return ControllerProjection(
        schema_version=PROJECTION_SCHEMA_VERSION,
        observation=observation,
        normalized_signals=tuple(normalized),
        projected_signals=dict(metrics),
        used_canonical_fields=tuple(sorted(used_set)),
        ignored_canonical_fields=ignored,
        missing_controller_signals=tuple(m for m in CONTROLLER_SIGNALS if m in missing),
        policy_id=normalization_policy.policy_id,
        warnings=tuple(warnings),
    )


__all__ = [
    "PROJECTION_SCHEMA_VERSION",
    "CONTROLLER_SIGNALS",
    "ProjectionError",
    "ControllerProjection",
    "project_to_scaling_observation",
]
