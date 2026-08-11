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
from typing import Any, Dict, List, Optional, Tuple

from ..canonical.serialization import content_digest
from .series import CanonicalCapacitySeries, _as_utc
from .targets import ForecastTarget, TargetSample, extract_sample

INPUT_WINDOW_SCHEMA_VERSION = "capacity-forecast-window-1"
FEATURE_CONFIG_SCHEMA_VERSION = "capacity-forecast-feature-1"


class WindowError(ValueError):
    """Raised when a forecast input window would be unsafe or malformed (fail closed)."""


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
        }

    def digest(self) -> str:
        return content_digest("forecast_input_window", self.schema_version, self.to_canonical_dict())


def build_input_window(
    series: CanonicalCapacitySeries,
    target: ForecastTarget,
    cutoff: datetime,
    horizon: ForecastHorizon,
    feature_config: Optional[FeatureConfig] = None,
) -> ForecastInputWindow:
    """Build a leakage-safe input window from ``series`` for ``target`` at ``cutoff``.

    Only observations with ``cutoff - lookback <= event_time <= cutoff`` are considered.
    Present samples carry the raw value + unit; missing observations are counted, never
    filled. Cadence gaps are measured between consecutive PRESENT samples.
    """
    if not isinstance(series, CanonicalCapacitySeries):
        raise WindowError("series must be a CanonicalCapacitySeries")
    if not isinstance(target, ForecastTarget):
        raise WindowError("target must be a ForecastTarget")
    if not isinstance(horizon, ForecastHorizon):
        raise WindowError("horizon must be a ForecastHorizon")
    if not isinstance(cutoff, datetime):
        raise WindowError("cutoff must be a datetime")
    feature_config = feature_config or FeatureConfig()

    c = _as_utc(cutoff)
    lower = c - timedelta(seconds=feature_config.lookback_seconds)

    considered = [
        s for s in series.observations_at_or_before(cutoff)
        if _as_utc(s.observed_at) >= lower
    ]

    samples: List[TargetSample] = []
    missing_count = 0
    for state in considered:
        sample = extract_sample(state, target)
        if sample is None:
            missing_count += 1
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
    )


__all__ = [
    "INPUT_WINDOW_SCHEMA_VERSION",
    "FEATURE_CONFIG_SCHEMA_VERSION",
    "WindowError",
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
