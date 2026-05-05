"""``CalibrationDriftDetector`` — fires when live fleet
aggregates leave the calibration's expected ranges.

Composes with :class:`StreamingFleetMonitor` via the same
``WindowedFleetSummary`` surface ``AlertRule`` walks: the
calibration's ``expected_metrics`` carries `{metric_path:
{"min": float, "max": float}}` entries; the detector resolves
each path against the fleet summary and emits one
:class:`CalibrationDriftAlert` per range violation.

The detector is intentionally NOT integrated into
:class:`StreamingFleetMonitor` itself — the monitor stays
calibration-agnostic; the deployment partner runs the detector
alongside the monitor's existing :meth:`evaluate_alerts` and
unions both alert streams.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .bundle import CalibrationSet
from .errors import CalibrationSetError


@dataclass(frozen=True)
class CalibrationDriftAlert:
    """One drift-range violation.

    Same shape as ``analysis.Alert`` but with the calibration-
    range context (expected_min / expected_max + calibration_id)
    that an ad-hoc :class:`AlertRule` doesn't carry. A downstream
    consumer who wants a unified alert stream can convert via
    :meth:`to_dict` and route alongside the monitor's existing
    :class:`Alert` records.
    """

    metric: str
    observed_value: float
    expected_min: float
    expected_max: float
    direction: str            # "above" | "below"
    calibration_id: str
    n_episodes_in_window: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "observed_value": float(self.observed_value),
            "expected_min": float(self.expected_min),
            "expected_max": float(self.expected_max),
            "direction": self.direction,
            "calibration_id": self.calibration_id,
            "n_episodes_in_window": int(self.n_episodes_in_window),
        }


def _resolve_metric_path(
    view: Dict[str, Any], path: str
) -> Optional[float]:
    """Walk a dotted-path metric key into the fleet-summary
    dict. Returns the resolved numeric value, or ``None`` if
    the path lands on a ``None`` (legitimately-missing metric
    like ``v2_engaged_fraction`` when V2 was never enabled).

    Raises :class:`KeyError` with the offending path if any
    intermediate segment is missing — same loud-failure
    discipline ``analysis.streaming._resolve_metric_path``
    enforces.
    """
    cursor: Any = view
    for part in path.split("."):
        if cursor is None:
            return None
        if not isinstance(cursor, dict) or part not in cursor:
            raise KeyError(
                f"metric path {path!r} does not resolve in fleet summary "
                f"(missing segment {part!r})"
            )
        cursor = cursor[part]
    if cursor is None:
        return None
    if isinstance(cursor, bool):
        return None
    if not isinstance(cursor, (int, float)):
        return None
    return float(cursor)


class CalibrationDriftDetector:
    """Compares live fleet aggregates against a calibration
    bundle's :attr:`expected_metrics` ranges.

    Args:
        calibration: the deployed :class:`CalibrationSet`. The
            detector reads :attr:`calibration.expected_metrics`
            once at init and caches the parsed ranges.

    Usage:

        detector = CalibrationDriftDetector(calibration)
        windowed = monitor.summary(window=timedelta(hours=24))
        alerts = detector.evaluate(windowed)
        for alert in alerts:
            log.warning("%s out of range: %s", alert.metric, alert)
    """

    def __init__(self, calibration: CalibrationSet) -> None:
        if not isinstance(calibration, CalibrationSet):
            raise CalibrationSetError(
                f"calibration must be a CalibrationSet; got "
                f"{type(calibration).__name__}"
            )
        self._calibration = calibration

    @property
    def calibration(self) -> CalibrationSet:
        return self._calibration

    @property
    def n_metrics(self) -> int:
        """Number of expected-range entries the detector will
        evaluate per :meth:`evaluate` call."""
        return len(self._calibration.expected_metrics)

    def evaluate(self, windowed_fleet_summary) -> Tuple[CalibrationDriftAlert, ...]:
        """Walk every expected-metric range; emit a
        :class:`CalibrationDriftAlert` for each range violated
        by the windowed-summary value.

        Returns an empty tuple if every metric is in-range OR
        if no metrics are defined on the calibration. A metric
        path that resolves to ``None`` (legitimately missing —
        V2 disabled, etc.) is skipped without raising. A path
        that doesn't resolve at all raises ``KeyError`` — same
        loud-failure discipline ``StreamingFleetMonitor``
        enforces for typo'd ``AlertRule.metric`` paths.
        """
        if not self._calibration.expected_metrics:
            return ()
        # Pull the fleet view once. WindowedFleetSummary.to_dict
        # returns a top-level dict with a "fleet" key that holds
        # the actual metrics — same indexing AlertRule.metric
        # uses.
        ws_dict = windowed_fleet_summary.to_dict()
        view = ws_dict.get("fleet", {})
        n_episodes = int(ws_dict.get("n_observed_in_window", 0))
        # Audit-fix Finding 4: zero-observation windows have an
        # empty "fleet" dict (no metrics at all). Walking the
        # expected_metrics map against that view raises KeyError
        # on the first metric path — which is wrong: a cold-start
        # poll firing before any vehicle has reported is not a
        # drift signal, it's no-data. Mirrors
        # ``StreamingFleetMonitor.evaluate_alerts``'s
        # ``min_episodes`` gate.
        if n_episodes == 0:
            return ()
        out = []
        for metric, bounds in self._calibration.expected_metrics.items():
            value = _resolve_metric_path(view, metric)
            if value is None:
                continue  # missing metric — not a drift signal
            lo = float(bounds["min"])
            hi = float(bounds["max"])
            if value < lo:
                out.append(CalibrationDriftAlert(
                    metric=metric,
                    observed_value=value,
                    expected_min=lo,
                    expected_max=hi,
                    direction="below",
                    calibration_id=self._calibration.calibration_id,
                    n_episodes_in_window=n_episodes,
                ))
            elif value > hi:
                out.append(CalibrationDriftAlert(
                    metric=metric,
                    observed_value=value,
                    expected_min=lo,
                    expected_max=hi,
                    direction="above",
                    calibration_id=self._calibration.calibration_id,
                    n_episodes_in_window=n_episodes,
                ))
        return tuple(out)
