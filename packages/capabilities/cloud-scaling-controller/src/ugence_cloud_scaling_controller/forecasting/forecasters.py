"""Deterministic baseline forecasters (persistence and linear trend).

These are the *only* forecasting methods Phase 2 ships. They are intentionally simple,
transparent, and fully deterministic — no training, no mutation during a forecast, no
neural network, no external model service, no hyperparameter search, no automatic model
promotion. A forecaster exposes a stable model identity, an explicit configuration with a
digest, a minimum-history requirement, and the targets/horizons it supports.

Each forecaster's core prediction is a pure function of ``(event_times, values,
forecast_for_time)`` so the SAME function drives both the headline forecast and the
rolling-origin residual calibration used for uncertainty — the model never behaves one
way for the forecast and another way for its own error estimate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..canonical.serialization import content_digest
from .abstention import AbstentionReason
from .series import _as_utc
from .targets import ForecastTarget
from .window import ForecastHorizon, ForecastInputWindow

FORECASTER_CONFIG_SCHEMA_VERSION = "capacity-forecaster-config-1"

# The set of targets the shipped baselines can forecast (all controller-relevant signals).
_ALL_TARGETS = frozenset(ForecastTarget)


class ForecasterError(ValueError):
    """Raised when a forecaster is configured or invoked incorrectly (fail closed)."""


def _epoch(t: datetime) -> float:
    return _as_utc(t).timestamp()


class BaselineForecaster:
    """Base class for deterministic baseline forecasters.

    Subclasses implement :meth:`_predict` (a pure point predictor) and set ``model_id`` /
    ``model_version`` / ``min_history``. The base class provides config digesting, target
    / horizon support checks, and the public :meth:`point_estimate` used by the service.
    """

    model_id: str = "baseline"
    model_version: str = "0"
    min_history: int = 1

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config: Dict[str, Any] = dict(config or {})

    # ---- identity / configuration -------------------------------------------------
    @property
    def config(self) -> Dict[str, Any]:
        return dict(self._config)

    def config_digest(self) -> str:
        payload = {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "min_history": self.min_history,
            "config": self._config,
        }
        return content_digest("forecaster_config", FORECASTER_CONFIG_SCHEMA_VERSION, payload)

    # ---- capability declaration ---------------------------------------------------
    def supported_targets(self) -> frozenset:
        return _ALL_TARGETS

    def supports_target(self, target: ForecastTarget) -> bool:
        return target in self.supported_targets()

    def supports_horizon(self, horizon: ForecastHorizon) -> bool:
        # Baselines are horizon-agnostic: they extrapolate to any strictly-positive
        # horizon. No horizon-specific behavior is hardcoded.
        return isinstance(horizon, ForecastHorizon) and horizon.seconds > 0

    # ---- prediction ---------------------------------------------------------------
    def _predict(
        self, event_times: Sequence[datetime], values: Sequence[float], forecast_for: datetime
    ) -> Optional[float]:  # pragma: no cover - abstract
        raise NotImplementedError

    def decline_reason(self, window: ForecastInputWindow) -> Optional["AbstentionReason"]:
        """Typed reason this forecaster declined ``window``, or ``None`` for the default.

        Pure and stateless: it re-derives the reason from the window rather than remembering
        the last call, so it cannot disagree with a concurrent or repeated ``point_estimate``.
        Returning ``None`` preserves the historical behaviour (``INSUFFICIENT_HISTORY``).
        """
        return None

    def point_estimate(self, window: ForecastInputWindow) -> Optional[float]:
        """Deterministic point estimate for ``window`` (``None`` if it cannot predict)."""
        if not isinstance(window, ForecastInputWindow):
            raise ForecasterError("window must be a ForecastInputWindow")
        if window.sample_count < self.min_history:
            return None
        times = [s.event_time for s in window.samples]
        values = [s.value for s in window.samples]
        return self._predict(times, values, window.forecast_for)

    def predict_from(
        self, event_times: Sequence[datetime], values: Sequence[float], forecast_for: datetime
    ) -> Optional[float]:
        """Pure predictor over an explicit sub-window (used for residual calibration)."""
        if len(values) < self.min_history:
            return None
        return self._predict(list(event_times), list(values), forecast_for)


class PersistenceForecaster(BaselineForecaster):
    """Last-value (naive) forecaster: predicts the most recent observed value.

    The canonical hard-to-beat baseline. Horizon-agnostic; requires one observation.
    """

    model_id = "persistence"
    model_version = "1"
    min_history = 1

    def _predict(self, event_times, values, forecast_for) -> Optional[float]:
        if not values:
            return None
        return float(values[-1])


class LinearTrendForecaster(BaselineForecaster):
    """Deterministic ordinary-least-squares linear-trend forecaster.

    Fits ``value ~ a + b * t`` (t in seconds) over the window by closed-form OLS and
    extrapolates to the forecast-for time. Requires ``min_history`` (default 3) points and
    at least two distinct timestamps; otherwise it declines (returns ``None``). No fitted
    state is retained between calls — the fit is recomputed from the supplied window.
    """

    model_id = "linear_trend"
    model_version = "1"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        mh = int(self._config.get("min_history", 3))
        if mh < 2:
            raise ForecasterError("linear_trend min_history must be >= 2")
        self.min_history = mh
        # Normalize config so the digest reflects the effective value.
        self._config["min_history"] = mh

    def _predict(self, event_times, values, forecast_for) -> Optional[float]:
        n = len(values)
        if n < 2:
            return None
        t0 = _epoch(event_times[0])
        xs = [_epoch(t) - t0 for t in event_times]
        ys = [float(v) for v in values]
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        sxx = sum((x - mean_x) ** 2 for x in xs)
        if sxx == 0.0:  # all timestamps identical — cannot fit a trend
            return None
        sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        slope = sxy / sxx
        intercept = mean_y - slope * mean_x
        x_target = _epoch(forecast_for) - t0
        return intercept + slope * x_target


__all__ = [
    "FORECASTER_CONFIG_SCHEMA_VERSION",
    "ForecasterError",
    "BaselineForecaster",
    "PersistenceForecaster",
    "LinearTrendForecaster",
]
