"""Evaluation-only forecasters for the third-baseline replay (arms N and H).

**Nothing here is a production default.** The shipped baselines remain ``persistence`` and
``linear_trend``; these two are constructed explicitly by an evaluation and are registered
nowhere. Ratification of a third baseline requires an authorized replay on representative
data, which has not run.

The four-arm ladder the evaluation compares is:

===  ================  ============================================================
arm  ``model_id``      role
===  ================  ============================================================
P    ``persistence``   the hard-to-beat reference (shipped, unchanged)
T    ``linear_trend``  trend control (shipped, unchanged) — it exists so a win by H
                       caused only by H's own trend term cannot be credited to the
                       harmonic component
N    ``seasonal_naive``  the cheap seasonal control that can retire H outright
H    ``harmonic_phase``  the candidate
===  ================  ============================================================

T deliberately reuses the shipped :class:`~.forecasters.LinearTrendForecaster` rather than
adding a second class with the same identity: its closed-form fit already subtracts the mean
abscissa, so it *is* the centred least-squares trend, and duplicating the identity would make
two different models indistinguishable in evidence.

Standard library only — no NumPy, SciPy, pandas, or anything from the Hybrid LLM lab. The
4x4 solve is Gaussian elimination with partial pivoting.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .abstention import AbstentionReason
from .forecasters import BaselineForecaster, ForecasterError, _epoch
from .window import ForecastInputWindow

#: The single ratified period for this evaluation: one UTC-fixed day. A weekly period is NOT
#: ratified — it is not resolvable inside the ratified seven-day lookback.
DAILY_PERIOD_SECONDS = 86400.0

# --- ratified resolvability thresholds (run manifest §6) -----------------------------------
#: Observed span must cover the lookback less one expected 60 s endpoint interval.
MIN_CYCLE_SPAN_SECONDS = 604740.0
#: 95th percentile of positive consecutive gaps.
MAX_P95_GAP_SECONDS = 120.0
#: No single positive consecutive gap may exceed this.
MAX_GAP_SECONDS = 900.0
#: Each UTC day is split into this many equal phase bins.
PHASE_BINS = 96
#: At least this many bins must be occupied ...
MIN_OCCUPIED_BINS = 90
#: ... on at least this many of the seven lookback days.
MIN_DAYS_WITH_COVERAGE = 6
#: Lookback days the phase-bin rule is evaluated over.
LOOKBACK_DAYS = 7
#: Infinity-norm condition-number ceiling for the 4x4 normal matrix.
MAX_CONDITION_NUMBER = 1e8


def _percentile(sorted_xs: Sequence[float], q: float) -> float:
    """Type-7 linear-interpolation percentile, matching the uncertainty module's convention."""
    n = len(sorted_xs)
    if n == 0:
        raise ForecasterError("percentile of an empty sequence")
    if n == 1:
        return float(sorted_xs[0])
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_xs[lo])
    return float(sorted_xs[lo]) + (float(sorted_xs[hi]) - float(sorted_xs[lo])) * (pos - lo)


class SeasonalNaiveForecaster(BaselineForecaster):
    """Arm N — predict the value observed one period before the forecast-for time.

    The control that can retire the harmonic arm. If the cheapest possible use of periodicity
    matches or beats a fitted harmonic, the fit has bought nothing.

    Declines (``None``) when no observation lies within ``match_tolerance_seconds`` of
    ``forecast_for - period``: an interpolated stand-in would make N look better than the data
    supports, and quietly turn the control into a different model.
    """

    model_id = "seasonal_naive"
    model_version = "1"
    min_history = 2

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        period = float(self._config.get("period_seconds", DAILY_PERIOD_SECONDS))
        if not (period > 0):
            raise ForecasterError("seasonal_naive period_seconds must be > 0")
        tol = float(self._config.get("match_tolerance_seconds", 5.0))
        if tol < 0:
            raise ForecasterError("seasonal_naive match_tolerance_seconds must be >= 0")
        self._period = period
        self._tolerance = tol
        self._config["period_seconds"] = period
        self._config["match_tolerance_seconds"] = tol

    @property
    def period_seconds(self) -> float:
        return self._period

    def _predict(self, event_times, values, forecast_for) -> Optional[float]:
        if not values:
            return None
        target = _epoch(forecast_for) - self._period
        best_gap: Optional[float] = None
        best_value: Optional[float] = None
        for t, v in zip(event_times, values):
            gap = abs(_epoch(t) - target)
            if gap <= self._tolerance and (best_gap is None or gap < best_gap):
                best_gap, best_value = gap, float(v)
        return best_value


class HarmonicPhaseForecaster(BaselineForecaster):
    """Arm H — one joint least-squares fit of ``[1, u, cos(phi), sin(phi)]``.

    ``u = (epoch(t) - epoch(forecast_for)) / period`` is the centred, scaled time coordinate;
    ``phi = 2*pi * (epoch(t) mod period) / period`` is the UTC-fixed clock phase. The constant,
    trend and harmonic terms are solved **together** in a single 4x4 normal-equation system.

    The trend is part of the model, not a preprocessing step, and there is deliberately **no**
    detrend-then-accumulate variant: separately detrending and summing a complex phasor is a
    different estimator that coincides with this one only under assumptions real telemetry
    does not satisfy (uniform sampling, whole-cycle coverage, orthogonality of the trend and
    harmonic bases over the window). Nothing here claims equivalence to a streaming Phase
    accumulator; such a variant would need its own specified and verified error bound.

    Before fitting, five ratified checks must pass (run manifest §6); their failure maps to
    two distinct typed reasons under a fixed precedence, so an implementation cannot report
    the flattering one.
    """

    model_id = "harmonic_phase"
    model_version = "1"
    min_history = 4  # four basis functions

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        period = float(self._config.get("period_seconds", DAILY_PERIOD_SECONDS))
        if not (period > 0):
            raise ForecasterError("harmonic_phase period_seconds must be > 0")
        self._period = period
        self._config["period_seconds"] = period
        # Resolvability thresholds are part of the model's configuration digest: a run cannot
        # quietly relax them without changing the recorded model identity.
        self._min_span = float(self._config.get("min_cycle_span_seconds", MIN_CYCLE_SPAN_SECONDS))
        self._max_p95_gap = float(self._config.get("max_p95_gap_seconds", MAX_P95_GAP_SECONDS))
        self._max_gap = float(self._config.get("max_gap_seconds", MAX_GAP_SECONDS))
        self._phase_bins = int(self._config.get("phase_bins", PHASE_BINS))
        self._min_bins = int(self._config.get("min_occupied_bins", MIN_OCCUPIED_BINS))
        self._min_days = int(self._config.get("min_days_with_coverage", MIN_DAYS_WITH_COVERAGE))
        self._lookback_days = int(self._config.get("lookback_days", LOOKBACK_DAYS))
        self._max_condition = float(self._config.get("max_condition_number", MAX_CONDITION_NUMBER))
        self._config.update({
            "min_cycle_span_seconds": self._min_span,
            "max_p95_gap_seconds": self._max_p95_gap,
            "max_gap_seconds": self._max_gap,
            "phase_bins": self._phase_bins,
            "min_occupied_bins": self._min_bins,
            "min_days_with_coverage": self._min_days,
            "lookback_days": self._lookback_days,
            "max_condition_number": self._max_condition,
        })
        if self._phase_bins < 1 or self._min_bins < 1 or self._min_bins > self._phase_bins:
            raise ForecasterError("harmonic_phase phase-bin configuration is inconsistent")

    @property
    def period_seconds(self) -> float:
        return self._period

    # -- resolvability -------------------------------------------------------------------
    def resolvability_failure(
        self, event_times: Sequence[datetime]
    ) -> Optional[AbstentionReason]:
        """First failing ratified check under the fixed precedence, or ``None``.

        Precedence (run manifest §6.1): cycle span, phase-bin coverage, maximum gap, p95 gap,
        then rank/conditioning — which is evaluated in :meth:`_predict` where the design
        matrix exists. Everything below the first failure is still detectable by a caller
        re-running the individual checks; precedence governs *reporting*, not measurement.
        """
        if len(event_times) < self.min_history:
            return AbstentionReason.INSUFFICIENT_CYCLE_COVERAGE

        epochs = sorted(_epoch(t) for t in event_times)

        # 1. cycle span
        if (epochs[-1] - epochs[0]) < self._min_span:
            return AbstentionReason.INSUFFICIENT_CYCLE_COVERAGE

        # 2. phase-bin coverage, per lookback day, over the most recent days
        bin_width = self._period / self._phase_bins
        end = epochs[-1]
        days_ok = 0
        for d in range(self._lookback_days):
            day_end = end - d * self._period
            day_start = day_end - self._period
            occupied = {
                int((e % self._period) // bin_width)
                for e in epochs
                if day_start < e <= day_end
            }
            if len(occupied) >= self._min_bins:
                days_ok += 1
        if days_ok < self._min_days:
            return AbstentionReason.INSUFFICIENT_CYCLE_COVERAGE

        # 3./4. gap bounds
        gaps = [b - a for a, b in zip(epochs, epochs[1:]) if b > a]
        if not gaps:
            return AbstentionReason.PERIOD_NOT_RESOLVABLE
        if max(gaps) > self._max_gap:
            return AbstentionReason.PERIOD_NOT_RESOLVABLE
        if _percentile(sorted(gaps), 0.95) > self._max_p95_gap:
            return AbstentionReason.PERIOD_NOT_RESOLVABLE

        return None

    # -- fit -----------------------------------------------------------------------------
    def _design_row(self, t: datetime, origin_epoch: float) -> List[float]:
        e = _epoch(t)
        u = (e - origin_epoch) / self._period
        phi = 2.0 * math.pi * ((e % self._period) / self._period)
        return [1.0, u, math.cos(phi), math.sin(phi)]

    def _predict(self, event_times, values, forecast_for) -> Optional[float]:
        if self.resolvability_failure(event_times) is not None:
            return None
        origin = _epoch(forecast_for)
        rows = [self._design_row(t, origin) for t in event_times]
        ys = [float(v) for v in values]

        # Normal equations X'X beta = X'y, assembled in 4x4.
        n = 4
        xtx = [[0.0] * n for _ in range(n)]
        xty = [0.0] * n
        for row, y in zip(rows, ys):
            for i in range(n):
                xty[i] += row[i] * y
                for j in range(n):
                    xtx[i][j] += row[i] * row[j]

        if _infinity_condition_number(xtx) > self._max_condition:
            return None
        beta = _solve_4x4(xtx, xty)
        if beta is None:
            return None

        # forecast_for is the centring origin, so u = 0 there by construction.
        target_row = self._design_row(forecast_for, origin)
        out = sum(b * r for b, r in zip(beta, target_row))
        return out if math.isfinite(out) else None

    def decline_reason(self, window: ForecastInputWindow) -> Optional[AbstentionReason]:
        if not isinstance(window, ForecastInputWindow):
            return None
        times = [s.event_time for s in window.samples]
        failure = self.resolvability_failure(times)
        if failure is not None:
            return failure
        # Span and sampling are fine, so a decline here is rank or conditioning.
        if len(times) >= self.min_history:
            return AbstentionReason.PERIOD_NOT_RESOLVABLE
        return AbstentionReason.INSUFFICIENT_CYCLE_COVERAGE


def _infinity_condition_number(m: List[List[float]]) -> float:
    """``||M||_inf * ||M^-1||_inf``; ``inf`` when the matrix is singular."""
    inv = _invert(m)
    if inv is None:
        return float("inf")
    return _infinity_norm(m) * _infinity_norm(inv)


def _infinity_norm(m: List[List[float]]) -> float:
    return max(sum(abs(v) for v in row) for row in m)


def _solve_4x4(a: List[List[float]], b: List[float]) -> Optional[List[float]]:
    """Gaussian elimination with partial pivoting. ``None`` when singular or non-finite."""
    n = len(b)
    m = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) == 0.0:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(col + 1, n):
            factor = m[r][col] / m[col][col]
            if factor == 0.0:
                continue
            for c in range(col, n + 1):
                m[r][c] -= factor * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        acc = m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))
        if m[r][r] == 0.0:
            return None
        x[r] = acc / m[r][r]
    return x if all(math.isfinite(v) for v in x) else None


def _invert(a: List[List[float]]) -> Optional[List[List[float]]]:
    n = len(a)
    m = [list(a[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) == 0.0:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        piv = m[col][col]
        for c in range(2 * n):
            m[col][c] /= piv
        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            if factor == 0.0:
                continue
            for c in range(2 * n):
                m[r][c] -= factor * m[col][c]
    inv = [row[n:] for row in m]
    if any(not math.isfinite(v) for row in inv for v in row):
        return None
    return inv


__all__ = [
    "DAILY_PERIOD_SECONDS",
    "MIN_CYCLE_SPAN_SECONDS",
    "MAX_P95_GAP_SECONDS",
    "MAX_GAP_SECONDS",
    "PHASE_BINS",
    "MIN_OCCUPIED_BINS",
    "MIN_DAYS_WITH_COVERAGE",
    "MAX_CONDITION_NUMBER",
    "SeasonalNaiveForecaster",
    "HarmonicPhaseForecaster",
]
