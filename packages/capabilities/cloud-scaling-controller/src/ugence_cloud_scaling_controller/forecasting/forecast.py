"""``CapacityForecast`` — the immutable, versioned, shadow-only forecast output contract.

A forecast is descriptive capacity intelligence. It is emphatically NOT a recommendation,
an authorization, a risk evaluation, or an execution instruction, and it says so in its
own fields:

    advisory_only = True
    shadow_only = True
    actuation_performed = False
    authority_class = ADVISORY
    execution_capability = NONE

Either the forecast carries a point estimate (``status = forecast``) or it is a typed
abstention (``status = abstained``) — both are valid, first-class outputs. An abstention
carries an :class:`~.abstention.AbstentionReason` and no point estimate; a forecast carries
a point estimate, a unit/domain label, and an uncertainty contract (which may itself be an
explicit 'unavailable').
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from ..canonical.evidence import AUTHORITY_CLASS_ADVISORY, EXECUTION_CAPABILITY_NONE
from ..canonical.identity import CapacitySubject
from .abstention import (
    FORECAST_STATUS_ABSTAINED,
    FORECAST_STATUS_FORECAST,
    AbstentionReason,
)
from .targets import ForecastTarget
from .uncertainty import UncertaintyInterval
from .window import ForecastHorizon

CAPACITY_FORECAST_SCHEMA_VERSION = "capacity-forecast-1"


class ForecastError(ValueError):
    """Raised when a forecast contract would be internally inconsistent (fail closed)."""


@dataclass(frozen=True)
class CapacityForecast:
    """Immutable shadow-only forecast (or typed abstention) for one target and horizon."""

    schema_version: str
    subject: CapacitySubject
    correlation_id: Optional[str]
    target: ForecastTarget
    forecast_cutoff: datetime
    horizon: ForecastHorizon
    forecast_for: datetime
    model_id: str
    model_version: str
    status: str
    unit: str
    input_window_digest: str
    model_config_digest: str
    uncertainty: UncertaintyInterval
    point_estimate: Optional[float] = None
    abstention_reason: Optional[AbstentionReason] = None
    warnings: Tuple[str, ...] = field(default_factory=tuple)

    # Fixed shadow-only, advisory-only classification.
    authority_class: str = AUTHORITY_CLASS_ADVISORY
    execution_capability: str = EXECUTION_CAPABILITY_NONE
    advisory_only: bool = True
    shadow_only: bool = True
    actuation_performed: bool = False

    def __post_init__(self) -> None:
        if self.advisory_only is not True:
            raise ForecastError("advisory_only must be True")
        if self.shadow_only is not True:
            raise ForecastError("shadow_only must be True")
        if self.actuation_performed is not False:
            raise ForecastError("actuation_performed must be False")
        if self.authority_class != AUTHORITY_CLASS_ADVISORY:
            raise ForecastError("authority_class must be ADVISORY")
        if self.execution_capability != EXECUTION_CAPABILITY_NONE:
            raise ForecastError("execution_capability must be NONE")
        if self.status not in (FORECAST_STATUS_FORECAST, FORECAST_STATUS_ABSTAINED):
            raise ForecastError(f"invalid forecast status: {self.status!r}")
        if self.status == FORECAST_STATUS_FORECAST:
            if self.point_estimate is None:
                raise ForecastError("a forecast status requires a point_estimate")
            if self.abstention_reason is not None:
                raise ForecastError("a forecast status must not carry an abstention_reason")
        else:  # abstained
            if self.point_estimate is not None:
                raise ForecastError("an abstained status must not carry a point_estimate")
            if not isinstance(self.abstention_reason, AbstentionReason):
                raise ForecastError("an abstained status requires an AbstentionReason")

    @property
    def is_forecast(self) -> bool:
        return self.status == FORECAST_STATUS_FORECAST

    @property
    def is_abstained(self) -> bool:
        return self.status == FORECAST_STATUS_ABSTAINED

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "subject": self.subject.to_canonical_dict(),
            "correlation_id": self.correlation_id,
            "target": self.target.value,
            "forecast_cutoff": self.forecast_cutoff,
            "horizon": self.horizon.to_canonical_dict(),
            "forecast_for": self.forecast_for,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "status": self.status,
            "unit": self.unit,
            "point_estimate": self.point_estimate,
            "abstention_reason": self.abstention_reason.value if self.abstention_reason else None,
            "uncertainty": self.uncertainty.to_canonical_dict(),
            "input_window_digest": self.input_window_digest,
            "model_config_digest": self.model_config_digest,
            "warnings": list(self.warnings),
            "authority_class": self.authority_class,
            "execution_capability": self.execution_capability,
            "advisory_only": self.advisory_only,
            "shadow_only": self.shadow_only,
            "actuation_performed": self.actuation_performed,
        }


__all__ = [
    "CAPACITY_FORECAST_SCHEMA_VERSION",
    "ForecastError",
    "CapacityForecast",
]
