"""Explicit measurement → normalized-signal contracts.

Provider and monitoring systems produce different units and scales. This module keeps
``raw measurement != normalized controller signal`` explicit and policy-driven. It never
invents a universal enterprise threshold: any method that needs an external baseline
(a latency SLO, a queue capacity) fails closed unless the policy supplies it.

A :class:`NormalizedSignal` preserves enough to explain *how* a raw value became a
controller signal: the raw value + unit, the source measurement, the method, the
threshold/bounds used, whether clamping occurred, the policy identity, and a provenance
reference. Normalization is deterministic for a fixed (measurement, policy).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from .measurement import Measurement, Unit
from .provenance import ObservationProvenance
from .serialization import content_digest

NORMALIZATION_POLICY_SCHEMA_VERSION = "capacity-normalization-policy-1"


class NormalizationError(ValueError):
    """Raised when normalization cannot proceed safely (fail closed)."""


class NormalizationMethod(str, Enum):
    RATIO_PASSTHROUGH = "ratio_passthrough"          # value already in [0, 1]
    PERCENT_TO_RATIO = "percent_to_ratio"            # percent / 100
    LATENCY_MS_TO_THRESHOLD = "latency_ms_to_threshold"   # observed_ms / threshold_ms
    LATENCY_S_TO_THRESHOLD = "latency_s_to_threshold"     # observed_s / threshold_s
    ERROR_PERCENT_TO_RATIO = "error_percent_to_ratio"     # percent / 100
    QUEUE_TO_CAPACITY = "queue_to_capacity"          # observed_count / capacity_baseline


# Units each method is willing to accept. Anything else fails closed.
_METHOD_UNITS: Dict[NormalizationMethod, frozenset] = {
    NormalizationMethod.RATIO_PASSTHROUGH: frozenset({Unit.RATIO, Unit.RATE}),
    NormalizationMethod.PERCENT_TO_RATIO: frozenset({Unit.PERCENT}),
    NormalizationMethod.LATENCY_MS_TO_THRESHOLD: frozenset({Unit.MILLISECONDS}),
    NormalizationMethod.LATENCY_S_TO_THRESHOLD: frozenset({Unit.SECONDS}),
    NormalizationMethod.ERROR_PERCENT_TO_RATIO: frozenset({Unit.PERCENT}),
    NormalizationMethod.QUEUE_TO_CAPACITY: frozenset({Unit.COUNT}),
}

# Methods that require an explicit policy threshold/baseline (never invented).
_THRESHOLD_METHODS = frozenset({
    NormalizationMethod.LATENCY_MS_TO_THRESHOLD,
    NormalizationMethod.LATENCY_S_TO_THRESHOLD,
    NormalizationMethod.QUEUE_TO_CAPACITY,
})


@dataclass(frozen=True)
class NormalizationPolicy:
    """Deterministic, versioned normalization policy.

    Fields:
        policy_id: Stable identifier for this policy (part of evidence).
        method_by_signal: Signal name -> :class:`NormalizationMethod`.
        thresholds: Signal name -> threshold/baseline for threshold methods (SLO ms/s,
            queue capacity). Must be finite and > 0.
        clamp: Whether normalized values are clamped to ``[clamp_low, clamp_high]``.
            If clamping is disabled, an out-of-range result fails closed.
        description: Human-readable note.
    """

    policy_id: str
    method_by_signal: Mapping[str, NormalizationMethod]
    thresholds: Mapping[str, float] = field(default_factory=dict)
    clamp: bool = True
    clamp_low: float = 0.0
    clamp_high: float = 1.0
    # Explicitly-named opt-in: allow p95 latency to stand in for a missing p99 during
    # projection. Default False (prefer failing closed); when True, the projection
    # discloses the substitution in its warnings and the evidence records it.
    allow_latency_p95_substitution: bool = False
    description: str = ""
    schema_version: str = NORMALIZATION_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or self.policy_id == "":
            raise NormalizationError("policy_id must be a non-empty string")
        if not isinstance(self.method_by_signal, Mapping):
            raise NormalizationError("method_by_signal must be a mapping")
        for name, method in self.method_by_signal.items():
            if not isinstance(name, str) or name == "":
                raise NormalizationError("method_by_signal keys must be non-empty strings")
            if not isinstance(method, NormalizationMethod):
                raise NormalizationError(f"unsupported normalization method for {name!r}")
        if not isinstance(self.thresholds, Mapping):
            raise NormalizationError("thresholds must be a mapping")
        for name, thr in self.thresholds.items():
            if isinstance(thr, bool) or not isinstance(thr, (int, float)):
                raise NormalizationError(f"threshold for {name!r} must be a real number")
            if math.isnan(thr) or math.isinf(thr):
                raise NormalizationError(f"threshold for {name!r} must be finite")
            if thr <= 0:
                raise NormalizationError(f"threshold for {name!r} must be > 0, got {thr}")
        if self.clamp and not (self.clamp_low < self.clamp_high):
            raise NormalizationError("clamp_low must be < clamp_high")
        # Freeze mappings as immutable copies.
        object.__setattr__(self, "method_by_signal", dict(self.method_by_signal))
        object.__setattr__(self, "thresholds", dict(self.thresholds))

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "method_by_signal": {k: v.value for k, v in self.method_by_signal.items()},
            "thresholds": dict(self.thresholds),
            "clamp": self.clamp,
            "clamp_low": self.clamp_low,
            "clamp_high": self.clamp_high,
            "allow_latency_p95_substitution": self.allow_latency_p95_substitution,
            "description": self.description,
        }

    def digest(self) -> str:
        return content_digest(
            "normalization_policy", self.schema_version, self.to_canonical_dict()
        )


@dataclass(frozen=True)
class NormalizedSignal:
    """The auditable record of one raw measurement becoming a controller signal."""

    name: str
    raw_value: float
    raw_unit: str
    method: str
    normalized_value: float
    threshold: Optional[float] = None
    clamped: bool = False
    policy_id: str = ""
    provenance_source_id: Optional[str] = None

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "raw_value": self.raw_value,
            "raw_unit": self.raw_unit,
            "method": self.method,
            "normalized_value": self.normalized_value,
            "threshold": self.threshold,
            "clamped": self.clamped,
            "policy_id": self.policy_id,
            "provenance_source_id": self.provenance_source_id,
        }


def normalize_signal(
    name: str,
    measurement: Measurement,
    policy: NormalizationPolicy,
    provenance: Optional[ObservationProvenance] = None,
) -> NormalizedSignal:
    """Normalize one measurement into a controller signal under ``policy`` (fail-closed).

    Fails closed on: unsupported/absent method, unit incompatible with the method,
    missing/zero/negative threshold for threshold methods, division by zero, and an
    out-of-range result when clamping is disabled.
    """
    method = policy.method_by_signal.get(name)
    if method is None:
        raise NormalizationError(f"no normalization method configured for signal {name!r}")
    if measurement.unit not in _METHOD_UNITS[method]:
        raise NormalizationError(
            f"signal {name!r}: unit {measurement.unit.value!r} is not supported by "
            f"method {method.value!r} (expected one of "
            f"{sorted(u.value for u in _METHOD_UNITS[method])})"
        )

    raw = float(measurement.value)
    threshold: Optional[float] = None

    if method in (NormalizationMethod.RATIO_PASSTHROUGH,):
        value = raw
    elif method in (NormalizationMethod.PERCENT_TO_RATIO,
                    NormalizationMethod.ERROR_PERCENT_TO_RATIO):
        value = raw / 100.0
    elif method in (NormalizationMethod.LATENCY_MS_TO_THRESHOLD,
                    NormalizationMethod.LATENCY_S_TO_THRESHOLD,
                    NormalizationMethod.QUEUE_TO_CAPACITY):
        if name not in policy.thresholds:
            raise NormalizationError(
                f"signal {name!r}: method {method.value!r} requires an explicit "
                f"threshold/baseline; none supplied (thresholds are never invented)"
            )
        threshold = float(policy.thresholds[name])
        if threshold <= 0:  # defensive; policy validation already enforces > 0
            raise NormalizationError(f"signal {name!r}: threshold must be > 0")
        value = raw / threshold
    else:  # pragma: no cover - exhaustive above
        raise NormalizationError(f"unsupported normalization method: {method!r}")

    if math.isnan(value) or math.isinf(value):
        raise NormalizationError(f"signal {name!r}: normalized value is not finite")

    clamped = False
    if policy.clamp:
        low, high = policy.clamp_low, policy.clamp_high
        if value < low:
            value, clamped = low, True
        elif value > high:
            value, clamped = high, True
    else:
        if not (0.0 <= value <= 1.0):
            raise NormalizationError(
                f"signal {name!r}: normalized value {value!r} outside [0, 1] and "
                f"clamping is disabled by policy"
            )

    return NormalizedSignal(
        name=name,
        raw_value=raw,
        raw_unit=measurement.unit.value,
        method=method.value,
        normalized_value=value,
        threshold=threshold,
        clamped=clamped,
        policy_id=policy.policy_id,
        provenance_source_id=(provenance.source_id if provenance is not None else None),
    )


__all__ = [
    "NORMALIZATION_POLICY_SCHEMA_VERSION",
    "NormalizationError",
    "NormalizationMethod",
    "NormalizationPolicy",
    "NormalizedSignal",
    "normalize_signal",
]
