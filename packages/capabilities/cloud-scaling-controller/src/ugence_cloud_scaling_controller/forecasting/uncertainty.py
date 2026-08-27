"""Deterministic baseline uncertainty via empirical rolling-origin residuals.

Uncertainty here is a *calibrated empirical* interval, not a distributional assumption.
For a forecaster and a requested coverage, we replay the forecaster over rolling origins
*inside the already-leakage-safe input window* (every origin and its matched actual are at
or before the cutoff), collect the signed horizon-ahead residuals, and take empirical
quantiles of those residuals. No Gaussian residual assumption is made.

The interval is available only when enough residuals were collected
(``min_calibration_samples``). When it is not, the contract distinguishes three states:

* **method NONE** — uncertainty was not requested; a point-only forecast is intended.
* **insufficient calibration** — the empirical method was requested but too few residuals
  exist; the caller decides (via ``allow_point_only_when_uncalibrated``) whether to keep a
  point-only forecast or abstain.
* **available** — a lower/upper interval computed from real residuals.

A heuristic score is never presented as a probability: an interval is reported only when
it is backed by actual replayed residuals at the requested coverage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from ..canonical.serialization import content_digest
from .series import _as_utc
from .window import ForecastInputWindow

UNCERTAINTY_CONFIG_SCHEMA_VERSION = "capacity-forecast-uncertainty-1"

REASON_NOT_REQUESTED = "uncertainty_method_none"
REASON_INSUFFICIENT_CALIBRATION = "insufficient_calibration_history"


class UncertaintyMethod(str, Enum):
    NONE = "none"
    EMPIRICAL_ROLLING_ORIGIN_RESIDUAL = "empirical_rolling_origin_residual"
    #: Residuals supplied by a caller-owned causal prequential bank rather than collected
    #: in-window. The interval mathematics is identical; only the provenance differs, which
    #: is why this is a distinct method value and not a flag.
    EMPIRICAL_PREQUENTIAL_RESIDUAL_BANK = "empirical_prequential_residual_bank"


class UncertaintyError(ValueError):
    """Raised when an uncertainty configuration is invalid (fail closed)."""


@dataclass(frozen=True)
class UncertaintyConfig:
    """Deterministic, versioned uncertainty configuration.

    Fields:
        method: :class:`UncertaintyMethod`. ``NONE`` means a point-only forecast is
            intended (no interval, not an abstention).
        requested_coverage: Target interval coverage in ``(0, 1)`` (e.g. 0.8).
        min_calibration_samples: Minimum residuals required to report an interval.
        match_tolerance_seconds: Tolerance for matching a rolling-origin forecast-for time
            to an in-window actual observation (>= 0).
        allow_point_only_when_uncalibrated: If True, a forecast with too few residuals is
            retained as point-only; if False (safe default) the service abstains.
        calibration_window_id: Stable identity/label for the calibration configuration.
    """

    method: UncertaintyMethod = UncertaintyMethod.EMPIRICAL_ROLLING_ORIGIN_RESIDUAL
    requested_coverage: float = 0.8
    min_calibration_samples: int = 5
    match_tolerance_seconds: float = 5.0
    allow_point_only_when_uncalibrated: bool = False
    calibration_window_id: str = "rolling-origin-v1"
    schema_version: str = UNCERTAINTY_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.method, UncertaintyMethod):
            raise UncertaintyError("method must be an UncertaintyMethod")
        if not (0.0 < self.requested_coverage < 1.0):
            raise UncertaintyError("requested_coverage must be in (0, 1)")
        if isinstance(self.min_calibration_samples, bool) or not isinstance(
            self.min_calibration_samples, int
        ) or self.min_calibration_samples < 1:
            raise UncertaintyError("min_calibration_samples must be an int >= 1")
        t = self.match_tolerance_seconds
        if isinstance(t, bool) or not isinstance(t, (int, float)) or t < 0:
            raise UncertaintyError("match_tolerance_seconds must be a real number >= 0")

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "method": self.method.value,
            "requested_coverage": self.requested_coverage,
            "min_calibration_samples": self.min_calibration_samples,
            "match_tolerance_seconds": self.match_tolerance_seconds,
            "allow_point_only_when_uncalibrated": self.allow_point_only_when_uncalibrated,
            "calibration_window_id": self.calibration_window_id,
        }

    def digest(self) -> str:
        return content_digest("forecast_uncertainty_config", self.schema_version, self.to_canonical_dict())


@dataclass(frozen=True)
class UncertaintyInterval:
    """The uncertainty contract attached to a forecast (available or explicitly not)."""

    method: str
    requested_coverage: float
    calibration_sample_count: int
    available: bool
    lower: Optional[float] = None
    upper: Optional[float] = None
    unavailable_reason: Optional[str] = None
    calibration_window_id: str = ""
    #: Digest of the externally supplied calibration input, for bank-sourced intervals only.
    #: ``None`` on the legacy in-window path, where it is omitted from the canonical payload
    #: so historical digests are byte-identical.
    calibration_input_digest: Optional[str] = None

    @property
    def insufficient_calibration(self) -> bool:
        return self.unavailable_reason == REASON_INSUFFICIENT_CALIBRATION

    @property
    def width(self) -> Optional[float]:
        if self.available and self.lower is not None and self.upper is not None:
            return self.upper - self.lower
        return None

    def to_canonical_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "method": self.method,
            "requested_coverage": self.requested_coverage,
            "calibration_sample_count": self.calibration_sample_count,
            "available": self.available,
            "lower": self.lower,
            "upper": self.upper,
            "unavailable_reason": self.unavailable_reason,
            "calibration_window_id": self.calibration_window_id,
        }
        # Legacy payload preservation: the key appears ONLY for bank-sourced intervals, so
        # every previously-computed evidence digest is unchanged.
        if self.calibration_input_digest is not None:
            payload["calibration_input_digest"] = self.calibration_input_digest
        return payload


def _quantile(sorted_xs: List[float], q: float) -> float:
    """Deterministic linear-interpolation quantile (type-7), ``q`` in ``[0, 1]``."""
    n = len(sorted_xs)
    if n == 1:
        return sorted_xs[0]
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_xs[lo]
    frac = pos - lo
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * frac


def rolling_origin_residuals(
    window: ForecastInputWindow, forecaster: Any, config: UncertaintyConfig
) -> List[float]:
    """Signed horizon-ahead residuals from rolling origins inside the window.

    For each origin ``i``, the forecaster is fit on ``samples[:i+1]`` and predicts the
    forecast-for time ``event_time_i + horizon``; that prediction is compared against the
    in-window actual sample whose event time is closest to the forecast-for time within
    ``match_tolerance_seconds``. Every origin and matched actual is at or before the cutoff,
    so no future information enters. Residual = actual - predicted.
    """
    samples = window.samples
    horizon = window.horizon.delta
    tol = timedelta(seconds=config.match_tolerance_seconds)
    residuals: List[float] = []
    n = len(samples)
    for i in range(n):
        history = samples[: i + 1]
        if len(history) < getattr(forecaster, "min_history", 1):
            continue
        origin_time = _as_utc(history[-1].event_time)
        target_time = origin_time + horizon
        # Find the closest later actual within tolerance of the forecast-for time.
        best_j = None
        best_gap = None
        for j in range(i + 1, n):
            jt = _as_utc(samples[j].event_time)
            gap = abs((jt - target_time).total_seconds())
            if jt > origin_time and gap <= tol.total_seconds():
                if best_gap is None or gap < best_gap:
                    best_gap = gap
                    best_j = j
        if best_j is None:
            continue
        actual = samples[best_j]
        pred = forecaster.predict_from(
            [s.event_time for s in history], [s.value for s in history], actual.event_time
        )
        if pred is None:
            continue
        residuals.append(float(actual.value) - float(pred))
    return residuals


def _finite_float(value: Any, what: str) -> float:
    """Coerce ``value`` to a finite float or fail closed."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UncertaintyError(f"{what} must be a real number")
    v = float(value)
    if not math.isfinite(v):
        raise UncertaintyError(f"{what} must be finite")
    return v


def interval_from_residuals(
    point: float,
    residuals: Sequence[float],
    config: UncertaintyConfig,
    *,
    calibration_input_digest: Optional[str] = None,
) -> UncertaintyInterval:
    """Build the canonical uncertainty interval from an ordered signed-residual collection.

    This is the **single** definition of the interval mathematics. Both residual-production
    paths delegate here and neither may reimplement it:

    * the shipped in-window path — :func:`rolling_origin_residuals` then this function, which
      is exactly what :func:`compute_uncertainty` does;
    * the evaluation path — a caller-owned causal prequential residual bank supplies the
      collection and its ``calibration_input_digest``.

    ``residuals`` are **signed** (``actual - predicted``), in the representation produced by
    :func:`rolling_origin_residuals`. Ordering of the input is irrelevant to the result — the
    quantiles are taken over a sorted copy — but the caller's order is never mutated.

    Malformed input (non-real, non-finite, or a non-``UncertaintyConfig``) fails closed with
    :class:`UncertaintyError`. Too *few* residuals is not an error: it is the existing typed
    ``unavailable`` contract, which the service turns into an abstention unless the config
    explicitly permits point-only.
    """
    if not isinstance(config, UncertaintyConfig):
        raise UncertaintyError("config must be an UncertaintyConfig")
    if calibration_input_digest is not None and (
        not isinstance(calibration_input_digest, str) or calibration_input_digest == ""
    ):
        raise UncertaintyError("calibration_input_digest must be a non-empty string or None")

    if config.method is UncertaintyMethod.NONE:
        return UncertaintyInterval(
            method=config.method.value,
            requested_coverage=config.requested_coverage,
            calibration_sample_count=0,
            available=False,
            unavailable_reason=REASON_NOT_REQUESTED,
            calibration_window_id=config.calibration_window_id,
            calibration_input_digest=calibration_input_digest,
        )

    point_value = _finite_float(point, "point")
    if isinstance(residuals, (str, bytes)):
        raise UncertaintyError("residuals must be a sequence of real numbers")
    values = [_finite_float(r, "residual") for r in residuals]
    count = len(values)

    if count < config.min_calibration_samples:
        return UncertaintyInterval(
            method=config.method.value,
            requested_coverage=config.requested_coverage,
            calibration_sample_count=count,
            available=False,
            unavailable_reason=REASON_INSUFFICIENT_CALIBRATION,
            calibration_window_id=config.calibration_window_id,
            calibration_input_digest=calibration_input_digest,
        )

    values.sort()
    alpha = 1.0 - config.requested_coverage
    lo_q = alpha / 2.0
    hi_q = 1.0 - alpha / 2.0
    lower_offset = _quantile(values, lo_q)
    upper_offset = _quantile(values, hi_q)
    return UncertaintyInterval(
        method=config.method.value,
        requested_coverage=config.requested_coverage,
        calibration_sample_count=count,
        available=True,
        lower=point_value + lower_offset,
        upper=point_value + upper_offset,
        calibration_window_id=config.calibration_window_id,
        calibration_input_digest=calibration_input_digest,
    )


def compute_uncertainty(
    window: ForecastInputWindow, forecaster: Any, point: float, config: UncertaintyConfig
) -> UncertaintyInterval:
    """Compute the empirical uncertainty interval around ``point`` (fail-open to a typed
    'unavailable' contract, never a fabricated interval).

    Unchanged in signature and behaviour: it collects in-window rolling-origin residuals and
    hands them to :func:`interval_from_residuals`, which owns the mathematics.
    """
    if config.method is UncertaintyMethod.NONE:
        return UncertaintyInterval(
            method=config.method.value,
            requested_coverage=config.requested_coverage,
            calibration_sample_count=0,
            available=False,
            unavailable_reason=REASON_NOT_REQUESTED,
            calibration_window_id=config.calibration_window_id,
        )
    if config.method is UncertaintyMethod.EMPIRICAL_PREQUENTIAL_RESIDUAL_BANK:
        # The config demands caller-supplied bank residuals; this path collects its own.
        # Fail closed rather than silently substituting a different calibration source.
        raise UncertaintyError(
            "method empirical_prequential_residual_bank requires supplied calibration; "
            "compute_uncertainty collects in-window residuals only"
        )

    residuals = rolling_origin_residuals(window, forecaster, config)
    return interval_from_residuals(point, residuals, config)


__all__ = [
    "UNCERTAINTY_CONFIG_SCHEMA_VERSION",
    "REASON_NOT_REQUESTED",
    "REASON_INSUFFICIENT_CALIBRATION",
    "UncertaintyMethod",
    "UncertaintyError",
    "UncertaintyConfig",
    "UncertaintyInterval",
    "rolling_origin_residuals",
    "interval_from_residuals",
    "compute_uncertainty",
]
