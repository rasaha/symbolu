"""``ForecastInputWindow`` — the immutable, leakage-safe input to a baseline forecaster.

A window is built from a :class:`~.series.CanonicalCapacitySeries` for one target at one
forecast cutoff. Its defining invariant:

    every included observation's EVENT time is ``<= cutoff``.

That invariant is asserted at construction (:class:`WindowError` on violation) so no future
observation can ever enter a forecast input. Event time is
``CanonicalCapacityState.observed_at`` — never a record-insertion or evidence-production
time. The window also records, without imputing anything:

* the raw included samples (value + unit, unchanged),
* missingness (how many states in the lookback lacked the target),
* cadence statistics (observed gaps vs the expected cadence and tolerance),
* the :class:`FeatureConfig` version + digest, and the forecast horizon / forecast-for time.

The window computes facts only. Whether a given amount of missingness, staleness, or
cadence irregularity is *acceptable* is a policy decision made later by the forecast
service — the window never silently drops or fills data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..canonical.normalization import (
    NormalizationError,
    NormalizationPolicy,
    normalize_signal,
)
from ..canonical.serialization import content_digest
from .series import CanonicalCapacitySeries, _as_utc
from .targets import (
    TARGET_SIGNAL_NAME,
    ForecastTarget,
    TargetSample,
    extract_measurement,
    extract_sample,
)

INPUT_WINDOW_SCHEMA_VERSION = "capacity-forecast-window-1"
FEATURE_CONFIG_SCHEMA_VERSION = "capacity-forecast-feature-1"

# Normalized signals are ratios in [0, 1].
NORMALIZED_UNIT = "ratio"


class WindowError(ValueError):
    """Raised when a forecast input window would be unsafe or malformed (fail closed)."""


class NormalizationApplicabilityError(WindowError):
    """Raised when a requested normalization cannot be applied to the observations.

    Carries a ``reason`` label the forecast service maps to a typed abstention rather than
    propagating as a hard error (missing method vs. incompatible unit)."""

    def __init__(self, message: str, *, reason: str):
        super().__init__(message)
        self.reason = reason


class ForecastValueSpace(str, Enum):
    """The space a forecast's values live in — precisely disclosed, never implied.

    * ``PROJECTED_WITHOUT_CONVERSION`` — raw canonical target values, mapped to the
      controller-relevant signal WITHOUT unit conversion (the default; e.g. CPU percent
      stays percent, running_replicas stays an integer count → current_replicas).
    * ``NORMALIZED`` — values explicitly normalized to a ratio in ``[0, 1]`` by applying
      the supplied Phase-1 :class:`NormalizationPolicy` (the canonical authority).
    """

    PROJECTED_WITHOUT_CONVERSION = "projected_without_conversion"
    NORMALIZED = "normalized"


@dataclass(frozen=True)
class ForecastHorizon:
    """A forecast horizon expressed in seconds. Immutable; must be strictly positive."""

    seconds: float
    label: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.seconds, bool) or not isinstance(self.seconds, (int, float)):
            raise WindowError("horizon seconds must be a real number")
        if not (self.seconds > 0):
            raise WindowError("horizon seconds must be > 0")

    @classmethod
    def minutes(cls, n: float) -> "ForecastHorizon":
        return cls(seconds=float(n) * 60.0, label=f"{n}m")

    @property
    def delta(self) -> timedelta:
        return timedelta(seconds=self.seconds)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {"seconds": self.seconds, "label": self.label}


# Explicitly-configured standard horizons (nothing hardcodes behavior to them).
HORIZON_5M = ForecastHorizon.minutes(5)
HORIZON_15M = ForecastHorizon.minutes(15)
HORIZON_60M = ForecastHorizon.minutes(60)


@dataclass(frozen=True)
class FeatureConfig:
    """Deterministic, versioned configuration for building a forecast input window.

    Fields:
        feature_version: Stable identifier of this feature configuration (part of evidence).
        lookback_seconds: Only observations with ``cutoff - lookback <= event <= cutoff``
            enter the window. Must be > 0.
        expected_cadence_seconds: The cadence the source is expected to emit at (> 0).
        cadence_tolerance_seconds: Allowed +/- deviation from the expected cadence (>= 0).
    """

    feature_version: str = "feature-v1"
    lookback_seconds: float = 3600.0
    expected_cadence_seconds: float = 60.0
    cadence_tolerance_seconds: float = 5.0
    description: str = ""
    schema_version: str = FEATURE_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("lookback_seconds", "expected_cadence_seconds"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not (v > 0):
                raise WindowError(f"{name} must be a real number > 0")
        t = self.cadence_tolerance_seconds
        if isinstance(t, bool) or not isinstance(t, (int, float)) or t < 0:
            raise WindowError("cadence_tolerance_seconds must be a real number >= 0")

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "feature_version": self.feature_version,
            "lookback_seconds": self.lookback_seconds,
            "expected_cadence_seconds": self.expected_cadence_seconds,
            "cadence_tolerance_seconds": self.cadence_tolerance_seconds,
            "description": self.description,
        }

    def digest(self) -> str:
        return content_digest("forecast_feature_config", self.schema_version, self.to_canonical_dict())


@dataclass(frozen=True)
class MissingnessInfo:
    """How many lookback observations carried the target vs lacked it. No imputation."""

    considered_count: int
    present_count: int
    missing_count: int
    missing_fraction: float

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "considered_count": self.considered_count,
            "present_count": self.present_count,
            "missing_count": self.missing_count,
            "missing_fraction": self.missing_fraction,
        }


@dataclass(frozen=True)
class CadenceInfo:
    """Observed inter-sample gaps vs the expected cadence/tolerance. Facts only."""

    expected_cadence_seconds: float
    tolerance_seconds: float
    observed_gaps_seconds: Tuple[float, ...]
    irregular_gap_count: int
    max_gap_seconds: Optional[float]
    min_gap_seconds: Optional[float]

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "expected_cadence_seconds": self.expected_cadence_seconds,
            "tolerance_seconds": self.tolerance_seconds,
            "observed_gaps_seconds": list(self.observed_gaps_seconds),
            "irregular_gap_count": self.irregular_gap_count,
            "max_gap_seconds": self.max_gap_seconds,
            "min_gap_seconds": self.min_gap_seconds,
        }


@dataclass(frozen=True)
class ForecastInputWindow:
    """Immutable, leakage-safe forecast input for one target at one cutoff."""

    schema_version: str
    subject_digest_dict: Dict[str, Any]
    target: ForecastTarget
    cutoff: datetime
    horizon: ForecastHorizon
    forecast_for: datetime
    lookback_seconds: float
    samples: Tuple[TargetSample, ...]
    units_present: Tuple[str, ...]
    missingness: MissingnessInfo
    cadence: CadenceInfo
    feature_config: FeatureConfig
    source_series_digest: str
    # Normalization / projection disclosure (bound into the window digest).
    value_space: str = ForecastValueSpace.PROJECTED_WITHOUT_CONVERSION.value
    normalization_applied: bool = False
    normalization_policy_digest: Optional[str] = None
    applied_signal: Optional[str] = None
    applied_method: Optional[str] = None

    def __post_init__(self) -> None:
        # Hard leakage invariant: no included sample may be after the cutoff.
        c = _as_utc(self.cutoff)
        for s in self.samples:
            if _as_utc(s.event_time) > c:
                raise WindowError(
                    "leakage invariant violated: an included sample has event time "
                    f"{s.event_time.isoformat()} after cutoff {self.cutoff.isoformat()}"
                )

    @property
    def sample_count(self) -> int:
        return len(self.samples)

    @property
    def values(self) -> Tuple[float, ...]:
        return tuple(s.value for s in self.samples)

    @property
    def last_event_time(self) -> Optional[datetime]:
        return self.samples[-1].event_time if self.samples else None

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "subject": self.subject_digest_dict,
            "target": self.target.value,
            "cutoff": self.cutoff,
            "horizon": self.horizon.to_canonical_dict(),
            "forecast_for": self.forecast_for,
            "lookback_seconds": self.lookback_seconds,
            "samples": [
                {"event_time": s.event_time, "value": s.value, "unit": s.unit}
                for s in self.samples
            ],
            "units_present": list(self.units_present),
            "missingness": self.missingness.to_canonical_dict(),
            "cadence": self.cadence.to_canonical_dict(),
            "feature_config": self.feature_config.to_canonical_dict(),
            "source_series_digest": self.source_series_digest,
            "value_space": self.value_space,
            "normalization_applied": self.normalization_applied,
            "normalization_policy_digest": self.normalization_policy_digest,
            "applied_signal": self.applied_signal,
            "applied_method": self.applied_method,
        }

    def digest(self) -> str:
        return content_digest("forecast_input_window", self.schema_version, self.to_canonical_dict())


def build_input_window(
    series: CanonicalCapacitySeries,
    target: ForecastTarget,
    cutoff: datetime,
    horizon: ForecastHorizon,
    feature_config: Optional[FeatureConfig] = None,
    *,
    normalization_policy: Optional[NormalizationPolicy] = None,
    forecast_space: ForecastValueSpace = ForecastValueSpace.PROJECTED_WITHOUT_CONVERSION,
) -> ForecastInputWindow:
    """Build a leakage-safe input window from ``series`` for ``target`` at ``cutoff``.

    Only observations with ``cutoff - lookback <= event_time <= cutoff`` are considered.
    Missing observations are counted, never filled. Cadence gaps are measured between
    consecutive PRESENT samples.

    Value space (disclosed and digest-bound):

    * ``PROJECTED_WITHOUT_CONVERSION`` (default): present samples carry the RAW canonical
      value + unit — no unit conversion. The ``normalization_policy``, if supplied, is
      recorded as the canonical reference but is NOT applied to the values.
    * ``NORMALIZED``: for a measurement-backed target, each sample is normalized to a ratio
      in ``[0, 1]`` by applying the Phase-1 :func:`normalize_signal` authority under the
      supplied ``normalization_policy``. Requires a policy with a method for the target's
      signal; a missing method or an incompatible unit raises
      :class:`NormalizationApplicabilityError` (mapped to a typed abstention by the service).
      RUNNING_REPLICAS has no normalization method and cannot be normalized.
    """
    if not isinstance(series, CanonicalCapacitySeries):
        raise WindowError("series must be a CanonicalCapacitySeries")
    if not isinstance(target, ForecastTarget):
        raise WindowError("target must be a ForecastTarget")
    if not isinstance(horizon, ForecastHorizon):
        raise WindowError("horizon must be a ForecastHorizon")
    if not isinstance(cutoff, datetime):
        raise WindowError("cutoff must be a datetime")
    if not isinstance(forecast_space, ForecastValueSpace):
        raise WindowError("forecast_space must be a ForecastValueSpace")
    feature_config = feature_config or FeatureConfig()

    signal = TARGET_SIGNAL_NAME.get(target)
    do_normalize = forecast_space is ForecastValueSpace.NORMALIZED
    if do_normalize:
        if signal is None:
            raise NormalizationApplicabilityError(
                f"target {target.value} has no normalization method (projected without "
                "conversion); it cannot be normalized",
                reason="unsupported_target",
            )
        if normalization_policy is None:
            raise NormalizationApplicabilityError(
                "NORMALIZED forecast_space requires an explicit normalization_policy",
                reason="missing_normalization_policy",
            )
        if normalization_policy.method_by_signal.get(signal) is None:
            raise NormalizationApplicabilityError(
                f"normalization_policy has no method for signal {signal!r}",
                reason="missing_normalization_policy",
            )

    c = _as_utc(cutoff)
    lower = c - timedelta(seconds=feature_config.lookback_seconds)

    considered = [
        s for s in series.observations_at_or_before(cutoff)
        if _as_utc(s.observed_at) >= lower
    ]

    samples: List[TargetSample] = []
    missing_count = 0
    applied_method: Optional[str] = None
    for state in considered:
        sample = extract_sample(state, target)
        if sample is None:
            missing_count += 1
            continue
        if do_normalize:
            measurement = extract_measurement(state, target)
            if measurement is None:  # defensive; guarded above
                missing_count += 1
                continue
            try:
                ns = normalize_signal(signal, measurement, normalization_policy,
                                      state.provenance_for(signal))
            except NormalizationError as exc:
                raise NormalizationApplicabilityError(
                    f"normalization of signal {signal!r} failed: {exc}",
                    reason="inconsistent_unit",
                ) from exc
            applied_method = ns.method
            samples.append(TargetSample(
                event_time=sample.event_time, value=ns.normalized_value, unit=NORMALIZED_UNIT))
        else:
            samples.append(sample)

    present_count = len(samples)
    considered_count = len(considered)
    missing_fraction = (missing_count / considered_count) if considered_count else 0.0
    missingness = MissingnessInfo(
        considered_count=considered_count,
        present_count=present_count,
        missing_count=missing_count,
        missing_fraction=missing_fraction,
    )

    units_present = tuple(sorted({s.unit for s in samples}))

    gaps: List[float] = []
    for a, b in zip(samples, samples[1:]):
        gaps.append((_as_utc(b.event_time) - _as_utc(a.event_time)).total_seconds())
    tol = feature_config.cadence_tolerance_seconds
    exp = feature_config.expected_cadence_seconds
    irregular = sum(1 for g in gaps if abs(g - exp) > tol)
    cadence = CadenceInfo(
        expected_cadence_seconds=exp,
        tolerance_seconds=tol,
        observed_gaps_seconds=tuple(gaps),
        irregular_gap_count=irregular,
        max_gap_seconds=max(gaps) if gaps else None,
        min_gap_seconds=min(gaps) if gaps else None,
    )

    return ForecastInputWindow(
        schema_version=INPUT_WINDOW_SCHEMA_VERSION,
        subject_digest_dict=series.subject.to_canonical_dict(),
        target=target,
        cutoff=cutoff,
        horizon=horizon,
        forecast_for=cutoff + horizon.delta,
        lookback_seconds=feature_config.lookback_seconds,
        samples=tuple(samples),
        units_present=units_present,
        missingness=missingness,
        cadence=cadence,
        feature_config=feature_config,
        source_series_digest=series.digest(),
        value_space=forecast_space.value,
        normalization_applied=do_normalize,
        normalization_policy_digest=(
            normalization_policy.digest() if normalization_policy is not None else None),
        applied_signal=(signal if do_normalize else None),
        applied_method=applied_method,
    )


__all__ = [
    "INPUT_WINDOW_SCHEMA_VERSION",
    "FEATURE_CONFIG_SCHEMA_VERSION",
    "NORMALIZED_UNIT",
    "WindowError",
    "NormalizationApplicabilityError",
    "ForecastValueSpace",
    "ForecastHorizon",
    "HORIZON_5M",
    "HORIZON_15M",
    "HORIZON_60M",
    "FeatureConfig",
    "MissingnessInfo",
    "CadenceInfo",
    "ForecastInputWindow",
    "build_input_window",
]
