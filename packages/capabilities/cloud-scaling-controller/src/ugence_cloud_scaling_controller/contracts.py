"""Versioned, provider-neutral public contract for the Cloud Scaling Controller.

This module defines the stable boundary types exchanged with the independent
package: :class:`ScalingObservation` (normalized input) and
:class:`ScalingRecommendation` (deterministic, JSON-serializable output). It also
declares the *optional* actuation seam (:class:`ScalingExecutor` /
:class:`ExecutionReceipt`) as an interface only — no write-capable executor ships
in this package.

The contract is intentionally cloud-provider neutral: it names no AWS/Azure/GCP
concept and carries only normalized signals. Validation happens here, *before* the
underlying control algorithm runs; the algorithm itself is never altered to
implement validation.

Field ranges, missing/unknown-signal handling, and fail-closed rules are documented
in ``docs/API.md`` and ``docs/BOUNDARIES.md`` and are enforced by
:meth:`ScalingObservation.validate` / :func:`normalize_observation`.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Mapping, Optional, Protocol, runtime_checkable

# The stable schema version for both the input and output contracts. Bump only on a
# breaking change to the field set or semantics. Output schema 1.1 adds the
# ``determinism`` disclosure block (see ScalingRecommendation).
SCHEMA_VERSION = "1.1"

# Fields that are NOT decision-deterministic. ``identity_deviation`` is derived from
# an unseeded IdentityEMA baseline and varies between fresh controller instances
# before a deterministic bootstrap; the "Identity Drift" line of ``explanation``
# reflects it. No decision field depends on it.
NONDETERMINISTIC_FIELDS = ("identity_deviation",)

# Canonical, currently-CONSUMED normalized signal keys — exactly the controller's
# metric groups (INFRA_KEYS + APP_KEYS + BUSINESS_KEYS). Only these five affect the
# decision. Other names (e.g. ``request_rate``, ``disk``) appear in legacy docstrings
# but are NOT consumed by the algorithm; like any unknown key they are accepted and
# ignored (documented pass-through policy). We deliberately do not claim support for
# signals the controller does not read.
KNOWN_METRIC_KEYS = (
    "cpu",
    "memory",
    "latency_p99",
    "error_rate",
    "queue_depth",
)

VALID_PHASES = ("peak", "normal", "off_peak", "maintenance")


class ContractError(ValueError):
    """Raised when a :class:`ScalingObservation` violates the input contract.

    The boundary fails closed (raises) rather than guessing when an input cannot be
    safely normalized (e.g. NaN/infinity metrics, negative replica counts,
    wrong-typed fields).
    """


@dataclass(frozen=True)
class ScalingObservation:
    """Normalized workload/infrastructure observation — the package's input contract.

    Required fields:
        metrics: Mapping of normalized signal name -> value. Values are expected in
            ``[0, 1]``; out-of-range finite values are clamped by the control
            algorithm (unchanged legacy behavior). Missing known signals are simply
            not counted; unknown signals are accepted but ignored by the algorithm.
            NaN / infinity values fail closed.
        current_replicas: Current running replica count. Must be an int ``>= 0``.
            (The control algorithm treats the effective floor as ``>= 1``.)

    Optional fields:
        deploy_active: Whether a rollout is in progress (adds scaling resistance).
        phase: Time context — one of ``VALID_PHASES``. Unknown strings are accepted
            and treated by the algorithm as the neutral/default phase.
        recent_pod_restarts: Restart count in the recent window (adds resistance).
            Must be an int ``>= 0``.
        correlation_id: Opaque request identifier echoed on the recommendation.
        timestamp: Optional caller-supplied epoch seconds (never generated here).
        metadata: Opaque mapping passed through untouched; never interpreted.
    """

    metrics: Mapping[str, float]
    current_replicas: int
    deploy_active: bool = False
    phase: str = "normal"
    recent_pod_restarts: int = 0
    correlation_id: Optional[str] = None
    timestamp: Optional[float] = None
    metadata: Optional[Mapping[str, Any]] = None

    def validate(self) -> "ScalingObservation":
        """Validate and return a normalized copy (fail-closed on invalid input)."""
        return normalize_observation(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScalingObservation":
        """Build an observation from a plain mapping (e.g. parsed JSON)."""
        if not isinstance(data, Mapping):
            raise ContractError("observation must be a JSON object / mapping")
        unknown_top = set(data) - {
            "metrics", "current_replicas", "deploy_active", "phase",
            "recent_pod_restarts", "correlation_id", "timestamp", "metadata",
        }
        # Unknown TOP-LEVEL keys fail closed (protects against typo'd contract fields);
        # unknown METRIC keys are tolerated (see normalize_observation).
        if unknown_top:
            raise ContractError(f"unknown observation field(s): {sorted(unknown_top)}")
        if "metrics" not in data or "current_replicas" not in data:
            raise ContractError("observation requires 'metrics' and 'current_replicas'")
        return cls(
            metrics=data["metrics"],
            current_replicas=data["current_replicas"],
            deploy_active=data.get("deploy_active", False),
            phase=data.get("phase", "normal"),
            recent_pod_restarts=data.get("recent_pod_restarts", 0),
            correlation_id=data.get("correlation_id"),
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata"),
        )


def normalize_observation(obs: ScalingObservation) -> ScalingObservation:
    """Validate an observation, failing closed, and return a normalized copy.

    Policy (documented in docs/BOUNDARIES.md):
      * ``metrics`` must be a mapping of str -> finite real number. NaN/inf ->
        :class:`ContractError`. Non-numeric values -> :class:`ContractError`.
        Values are otherwise passed through unchanged (the algorithm clamps to
        ``[0, 1]``). Unknown metric names are kept but ignored by the algorithm.
      * ``current_replicas`` must be int-like and ``>= 0``. Negative -> fail closed.
      * ``recent_pod_restarts`` must be int-like and ``>= 0``. Negative -> fail closed.
      * ``deploy_active`` coerced to bool. ``phase`` must be a str (value not
        restricted; unknown -> default handling downstream).
    """
    if not isinstance(obs.metrics, Mapping):
        raise ContractError("metrics must be a mapping of name -> value")

    clean_metrics: Dict[str, float] = {}
    for key, value in obs.metrics.items():
        if not isinstance(key, str):
            raise ContractError(f"metric key must be a string, got {type(key).__name__}")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ContractError(f"metric '{key}' must be a real number, got {value!r}")
        fvalue = float(value)
        if math.isnan(fvalue) or math.isinf(fvalue):
            raise ContractError(f"metric '{key}' must be finite, got {value!r}")
        clean_metrics[key] = fvalue

    if isinstance(obs.current_replicas, bool) or not isinstance(obs.current_replicas, int):
        raise ContractError("current_replicas must be an int")
    if obs.current_replicas < 0:
        raise ContractError(f"current_replicas must be >= 0, got {obs.current_replicas}")

    if isinstance(obs.recent_pod_restarts, bool) or not isinstance(obs.recent_pod_restarts, int):
        raise ContractError("recent_pod_restarts must be an int")
    if obs.recent_pod_restarts < 0:
        raise ContractError(
            f"recent_pod_restarts must be >= 0, got {obs.recent_pod_restarts}"
        )

    if not isinstance(obs.phase, str):
        raise ContractError("phase must be a string")

    return ScalingObservation(
        metrics=clean_metrics,
        current_replicas=int(obs.current_replicas),
        deploy_active=bool(obs.deploy_active),
        phase=obs.phase,
        recent_pod_restarts=int(obs.recent_pod_restarts),
        correlation_id=obs.correlation_id,
        timestamp=obs.timestamp,
        metadata=dict(obs.metadata) if obs.metadata is not None else None,
    )


@dataclass(frozen=True)
class ScalingRecommendation:
    """Deterministic, JSON-serializable scaling recommendation — the output contract.

    Invariants for this advisory-only package: ``advisory_only`` is always ``True``
    and ``actuation_performed`` is always ``False``.
    """

    schema_version: str
    correlation_id: Optional[str]
    recommendation: str
    replica_delta: int
    current_replicas: int
    recommended_replicas: int
    action_score: float
    pressure: float
    component_breakdown: Dict[str, Any]
    identity_deviation: float
    explanation: str
    controller_step: int
    metrics_snapshot: Dict[str, float]
    # Honest determinism disclosure (output schema 1.1). Example::
    #   {"scope": "decision-deterministic", "identity_bootstrapped": false,
    #    "nondeterministic_fields": ["identity_deviation"]}
    # The decision fields (recommendation, replica_delta, recommended_replicas,
    # action_score, pressure, and the plasticity/gain/damping/coherence breakdowns)
    # are deterministic for a fixed config + input sequence. Fields listed in
    # ``nondeterministic_fields`` are diagnostic and vary before bootstrap.
    determinism: Dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True
    actuation_performed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict with deterministic (sorted) key ordering."""
        return {k: asdict(self)[k] for k in sorted(asdict(self))}

    def to_json(self, *, indent: Optional[int] = None) -> str:
        """Return a JSON string with deterministic field ordering."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent)


@dataclass(frozen=True)
class ExecutionReceipt:
    """Result of an *optional* external actuation. Never produced by this package.

    Provided as a typed seam so downstream, separately-audited systems can implement
    :class:`ScalingExecutor`. The core package neither ships nor calls an executor.
    """

    correlation_id: Optional[str]
    applied: bool
    detail: str = ""


@runtime_checkable
class ScalingExecutor(Protocol):
    """Optional actuation seam (interface only).

    A conforming executor lives OUTSIDE this package and is never invoked
    automatically. The advisory core produces recommendations only.
    """

    def apply(self, recommendation: ScalingRecommendation) -> ExecutionReceipt:
        ...


__all__ = [
    "SCHEMA_VERSION",
    "KNOWN_METRIC_KEYS",
    "VALID_PHASES",
    "ContractError",
    "ScalingObservation",
    "ScalingRecommendation",
    "ExecutionReceipt",
    "ScalingExecutor",
    "normalize_observation",
]
