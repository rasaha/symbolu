"""Typed, immutable calibration input for externally supplied uncertainty residuals.

The shipped uncertainty path collects its own residuals in-window
(:func:`~.uncertainty.rolling_origin_residuals`). A replay **evaluation** may instead supply
residuals from a causal prequential bank: origins on a preregistered schedule, and only
actuals that were observable at the evaluation cutoff. Both paths compute the interval with
the same function, :func:`~.uncertainty.interval_from_residuals` — only the residual
*provenance* differs, which is why bank-sourced intervals carry a distinct
:class:`~.uncertainty.UncertaintyMethod` value and a calibration-input digest.

This module owns the *contract*, not the collection policy: :class:`CalibrationResiduals` is
what a provider must hand over, and :func:`validate_calibration` is the fail-closed check
applied before any supplied residual can influence an interval. The bank that produces these
objects lives in the evaluation layer (:mod:`.calibration_bank`).

**Authority.** A calibration input supplies calibration evidence, never a forecast. It cannot
change the point estimate, the requested coverage, the minimum sample count, the match
tolerance or the point-only policy — all of those come from the frozen ``UncertaintyConfig``.
It cannot contribute residuals from another subject, target, horizon or arm, and it cannot
carry an actual that was not observable at the evaluation cutoff. Validation failures raise
:class:`~.uncertainty.UncertaintyError` (the existing hierarchy; no second one is introduced).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Sequence, Tuple

from ..canonical.serialization import content_digest
from ..canonical.identity import CapacitySubject
from .series import _as_utc
from .targets import ForecastTarget
from .uncertainty import UncertaintyConfig, UncertaintyError, UncertaintyMethod
from .window import ForecastHorizon

CALIBRATION_RESIDUALS_SCHEMA_VERSION = "capacity-forecast-calibration-residuals-1"

#: Provenance of a residual collection. The in-window value exists so the shipped path can be
#: described honestly by the same vocabulary; it is never carried on supplied calibration.
SOURCE_IN_WINDOW_ROLLING_ORIGIN = "in_window_rolling_origin"
SOURCE_EVALUATION_RESIDUAL_BANK = "evaluation_residual_bank"


def _iso(t: datetime) -> str:
    return _as_utc(t).isoformat()


@dataclass(frozen=True)
class CalibrationResiduals:
    """An immutable, fully-bound residual collection supplied by an evaluation provider.

    The binding fields are not decoration: they are what makes cross-subject, cross-target,
    cross-horizon, cross-arm and out-of-time calibration detectable rather than plausible.
    ``residual_bank_digest`` is recomputed on validation, so a mutated or hand-assembled
    payload fails closed instead of silently calibrating an interval.
    """

    subject: CapacitySubject
    target: ForecastTarget
    horizon_seconds: float
    arm_model_id: str
    evaluation_cutoff: datetime
    values: Tuple[float, ...]
    earliest_origin: Optional[datetime]
    latest_origin: Optional[datetime]
    bank_cap: int
    config_digest: str
    cutoff_sequence_digest: str
    source: str = SOURCE_EVALUATION_RESIDUAL_BANK
    schema_version: str = CALIBRATION_RESIDUALS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.subject, CapacitySubject):
            raise UncertaintyError("calibration subject must be a CapacitySubject")
        if not isinstance(self.target, ForecastTarget):
            raise UncertaintyError("calibration target must be a ForecastTarget")
        if isinstance(self.horizon_seconds, bool) or not isinstance(
            self.horizon_seconds, (int, float)
        ):
            raise UncertaintyError("calibration horizon_seconds must be a real number")
        if not (float(self.horizon_seconds) > 0):
            raise UncertaintyError("calibration horizon_seconds must be > 0")
        if not isinstance(self.arm_model_id, str) or self.arm_model_id == "":
            raise UncertaintyError("calibration arm_model_id must be a non-empty string")
        if not isinstance(self.evaluation_cutoff, datetime):
            raise UncertaintyError("calibration evaluation_cutoff must be a datetime")
        if not isinstance(self.values, tuple):
            raise UncertaintyError("calibration values must be a tuple (immutable)")
        for v in self.values:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
                raise UncertaintyError("calibration values must be finite real numbers")
        if isinstance(self.bank_cap, bool) or not isinstance(self.bank_cap, int) or self.bank_cap < 1:
            raise UncertaintyError("calibration bank_cap must be an int >= 1")
        if len(self.values) > self.bank_cap:
            raise UncertaintyError(
                f"calibration holds {len(self.values)} residuals, exceeding bank_cap {self.bank_cap}"
            )
        for name in ("config_digest", "cutoff_sequence_digest"):
            v = getattr(self, name)
            if not isinstance(v, str) or v == "":
                raise UncertaintyError(f"calibration {name} must be a non-empty string")
        if self.source != SOURCE_EVALUATION_RESIDUAL_BANK:
            raise UncertaintyError(
                "supplied calibration must declare the evaluation_residual_bank source"
            )
        if self.schema_version != CALIBRATION_RESIDUALS_SCHEMA_VERSION:
            raise UncertaintyError("unsupported calibration schema_version")

        # Origin bounds: present together, ordered, and strictly before the cutoff. A residual
        # produced at or after the cutoff could not have had an observable outcome by then.
        has_origins = (self.earliest_origin is not None, self.latest_origin is not None)
        if any(has_origins) and not all(has_origins):
            raise UncertaintyError("calibration origin bounds must be present together")
        if self.values and not all(has_origins):
            raise UncertaintyError("non-empty calibration must carry both origin bounds")
        if all(has_origins):
            for name in ("earliest_origin", "latest_origin"):
                if not isinstance(getattr(self, name), datetime):
                    raise UncertaintyError(f"calibration {name} must be a datetime")
            if _as_utc(self.earliest_origin) > _as_utc(self.latest_origin):
                raise UncertaintyError("calibration earliest_origin must not follow latest_origin")
            if _as_utc(self.latest_origin) >= _as_utc(self.evaluation_cutoff):
                raise UncertaintyError(
                    "calibration latest_origin must be strictly before the evaluation cutoff"
                )

    @property
    def count(self) -> int:
        return len(self.values)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": self.source,
            "subject": self.subject.to_canonical_dict(),
            "target": self.target.value,
            "horizon_seconds": float(self.horizon_seconds),
            "arm_model_id": self.arm_model_id,
            "evaluation_cutoff": _iso(self.evaluation_cutoff),
            "values": [float(v) for v in self.values],
            "count": self.count,
            "earliest_origin": _iso(self.earliest_origin) if self.earliest_origin else None,
            "latest_origin": _iso(self.latest_origin) if self.latest_origin else None,
            "bank_cap": self.bank_cap,
            "config_digest": self.config_digest,
            "cutoff_sequence_digest": self.cutoff_sequence_digest,
        }

    def digest(self) -> str:
        """Content identity over the residuals **and** their binding, not the values alone."""
        return content_digest(
            "forecast_calibration_residuals", self.schema_version, self.to_canonical_dict()
        )


class CalibrationProvider:
    """Evaluation-owned source of :class:`CalibrationResiduals`, one per forecast origin.

    Implementations are supplied by the replay/evaluation layer and are never required by the
    shipped path. Returning ``None`` means "no calibration for this origin", which is a normal
    outcome early in a run — the service then treats the interval as uncalibrated under the
    configured policy rather than falling back to in-window collection.
    """

    def calibration_for(
        self,
        subject: CapacitySubject,
        target: ForecastTarget,
        horizon: ForecastHorizon,
        arm_model_id: str,
        cutoff: datetime,
    ) -> Optional[CalibrationResiduals]:  # pragma: no cover - interface
        raise NotImplementedError


def validate_calibration(
    calibration: CalibrationResiduals,
    *,
    subject: CapacitySubject,
    target: ForecastTarget,
    horizon: ForecastHorizon,
    arm_model_id: str,
    cutoff: datetime,
    config: UncertaintyConfig,
) -> str:
    """Fail closed unless ``calibration`` may calibrate this exact forecast; return its digest.

    Every rejection here is a case where a supplied interval would otherwise look plausible:
    residuals from a neighbouring arm, a different horizon, another tenant's subject, or a
    later cutoff whose outcomes were not yet observable.
    """
    if not isinstance(calibration, CalibrationResiduals):
        raise UncertaintyError("calibration must be a CalibrationResiduals")
    if not isinstance(config, UncertaintyConfig):
        raise UncertaintyError("config must be an UncertaintyConfig")
    if config.method is not UncertaintyMethod.EMPIRICAL_PREQUENTIAL_RESIDUAL_BANK:
        raise UncertaintyError(
            "supplied calibration requires the empirical_prequential_residual_bank method; "
            f"config declares {config.method.value}"
        )
    if calibration.subject != subject:
        raise UncertaintyError("calibration subject does not match the forecast subject")
    if calibration.target is not target:
        raise UncertaintyError("calibration target does not match the forecast target")
    if float(calibration.horizon_seconds) != float(horizon.seconds):
        raise UncertaintyError("calibration horizon does not match the forecast horizon")
    if calibration.arm_model_id != arm_model_id:
        raise UncertaintyError("calibration arm does not match the forecasting model")
    if _as_utc(calibration.evaluation_cutoff) != _as_utc(cutoff):
        raise UncertaintyError("calibration evaluation_cutoff does not match the forecast cutoff")
    return calibration.digest()


__all__ = [
    "CALIBRATION_RESIDUALS_SCHEMA_VERSION",
    "SOURCE_IN_WINDOW_ROLLING_ORIGIN",
    "SOURCE_EVALUATION_RESIDUAL_BANK",
    "CalibrationResiduals",
    "CalibrationProvider",
    "validate_calibration",
]
