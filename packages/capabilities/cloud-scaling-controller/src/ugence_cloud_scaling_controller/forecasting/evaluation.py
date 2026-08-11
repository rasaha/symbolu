"""``ForecastEvaluationRecord`` and deterministic aggregate evaluation (shadow mode only).

Evaluation compares a forecast, produced at a cutoff using only history at or before that
cutoff, against a *later* actual canonical observation. It is a shadow measurement: it
never promotes a model, never changes controller configuration, and never feeds a live
recommendation.

Matching is explicit: an actual observation matches a forecast when it belongs to the same
subject, carries the target, and its event time lies within a stated tolerance of the
forecast-for time. An abstention is recorded (not scored); an unmatched or subject-mismatched
outcome is recorded as such rather than silently dropped.

The aggregate report intentionally omits percentage-error metrics (MAPE/SMAPE): several
targets (queue depth, error rate, replicas) are legitimately zero, which makes a percentage
denominator invalid. Errors are reported in the target's own units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..canonical.serialization import content_digest
from ..canonical.state import CanonicalCapacityState
from .abstention import AbstentionReason
from .evidence import CapacityForecastEvidence
from .series import _as_utc
from .targets import extract_sample

EVALUATION_RECORD_SCHEMA_VERSION = "capacity-forecast-evaluation-1"
AGGREGATE_EVALUATION_SCHEMA_VERSION = "capacity-forecast-aggregate-1"


class EvaluationError(ValueError):
    """Raised when an evaluation cannot be constructed safely (fail closed)."""


class EvaluationStatus(str, Enum):
    EVALUATED = "evaluated"              # matched actual + scored a point forecast
    ABSTAINED = "abstained"             # forecast was a typed abstention (not scored)
    UNMATCHED = "unmatched"            # no actual matched within tolerance
    SUBJECT_MISMATCH = "subject_mismatch"  # candidate actual belonged to a different subject


@dataclass(frozen=True)
class ForecastEvaluationRecord:
    """Immutable, versioned outcome of matching one forecast against a later actual."""

    schema_version: str
    forecast_evidence_digest: str
    actual_state_digest: Optional[str]
    target: str
    horizon_seconds: float
    forecast_cutoff: datetime
    forecast_for: datetime
    actual_event_time: Optional[datetime]
    match_tolerance_seconds: float
    match_delta_seconds: Optional[float]
    status: EvaluationStatus
    reason: Optional[str]

    point_forecast: Optional[float] = None
    actual_value: Optional[float] = None
    signed_error: Optional[float] = None
    absolute_error: Optional[float] = None
    squared_error: Optional[float] = None

    interval_lower: Optional[float] = None
    interval_upper: Optional[float] = None
    interval_covered: Optional[bool] = None
    interval_width: Optional[float] = None

    def to_canonical_dict(self, *, include_digest: bool = True) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "forecast_evidence_digest": self.forecast_evidence_digest,
            "actual_state_digest": self.actual_state_digest,
            "target": self.target,
            "horizon_seconds": self.horizon_seconds,
            "forecast_cutoff": self.forecast_cutoff,
            "forecast_for": self.forecast_for,
            "actual_event_time": self.actual_event_time,
            "match_tolerance_seconds": self.match_tolerance_seconds,
            "match_delta_seconds": self.match_delta_seconds,
            "status": self.status.value,
            "reason": self.reason,
            "point_forecast": self.point_forecast,
            "actual_value": self.actual_value,
            "signed_error": self.signed_error,
            "absolute_error": self.absolute_error,
            "squared_error": self.squared_error,
            "interval_lower": self.interval_lower,
            "interval_upper": self.interval_upper,
            "interval_covered": self.interval_covered,
            "interval_width": self.interval_width,
        }
        if include_digest:
            data["evaluation_digest"] = self.digest()
        return data

    def digest(self) -> str:
        data = {k: v for k, v in self.to_canonical_dict(include_digest=False).items()}
        return content_digest("forecast_evaluation_record", self.schema_version, data)


def evaluate_forecast(
    evidence: CapacityForecastEvidence,
    actual_state: Optional[CanonicalCapacityState],
    *,
    match_tolerance_seconds: float,
) -> ForecastEvaluationRecord:
    """Match ``evidence``'s forecast against ``actual_state`` and record the outcome.

    ``actual_state`` is a later observation (its event time is compared to the forecast-for
    time). ``None`` means no candidate actual was available for this forecast.
    """
    if not isinstance(evidence, CapacityForecastEvidence):
        raise EvaluationError("evidence must be a CapacityForecastEvidence")
    if isinstance(match_tolerance_seconds, bool) or not isinstance(match_tolerance_seconds, (int, float)) or match_tolerance_seconds < 0:
        raise EvaluationError("match_tolerance_seconds must be a real number >= 0")

    fc = evidence.forecast
    base = dict(
        schema_version=EVALUATION_RECORD_SCHEMA_VERSION,
        forecast_evidence_digest=evidence.digest(),
        target=fc.target.value,
        horizon_seconds=fc.horizon.seconds,
        forecast_cutoff=fc.forecast_cutoff,
        forecast_for=fc.forecast_for,
        match_tolerance_seconds=float(match_tolerance_seconds),
    )

    # Abstention: recorded, not scored.
    if fc.is_abstained:
        return ForecastEvaluationRecord(
            actual_state_digest=(actual_state.digest() if actual_state is not None else None),
            actual_event_time=(actual_state.observed_at if actual_state is not None else None),
            match_delta_seconds=None,
            status=EvaluationStatus.ABSTAINED,
            reason=(fc.abstention_reason.value if fc.abstention_reason else None),
            **base,
        )

    # No candidate actual.
    if actual_state is None:
        return ForecastEvaluationRecord(
            actual_state_digest=None, actual_event_time=None, match_delta_seconds=None,
            status=EvaluationStatus.UNMATCHED, reason="no_actual_available",
            point_forecast=fc.point_estimate, **base,
        )

    # Subject/scope must match (never score across subjects/tenants).
    if actual_state.subject != fc.subject:
        return ForecastEvaluationRecord(
            actual_state_digest=actual_state.digest(),
            actual_event_time=actual_state.observed_at, match_delta_seconds=None,
            status=EvaluationStatus.SUBJECT_MISMATCH, reason="actual_subject_differs",
            point_forecast=fc.point_estimate, **base,
        )

    delta = (_as_utc(actual_state.observed_at) - _as_utc(fc.forecast_for)).total_seconds()
    sample = extract_sample(actual_state, fc.target)
    if sample is None:
        return ForecastEvaluationRecord(
            actual_state_digest=actual_state.digest(),
            actual_event_time=actual_state.observed_at, match_delta_seconds=delta,
            status=EvaluationStatus.UNMATCHED, reason="actual_missing_target",
            point_forecast=fc.point_estimate, **base,
        )
    if abs(delta) > match_tolerance_seconds:
        return ForecastEvaluationRecord(
            actual_state_digest=actual_state.digest(),
            actual_event_time=actual_state.observed_at, match_delta_seconds=delta,
            status=EvaluationStatus.UNMATCHED, reason="actual_outside_tolerance",
            point_forecast=fc.point_estimate, actual_value=sample.value, **base,
        )

    point = float(fc.point_estimate)
    actual_value = float(sample.value)
    signed = point - actual_value
    interval_covered: Optional[bool] = None
    interval_width: Optional[float] = None
    lower = upper = None
    if fc.uncertainty.available and fc.uncertainty.lower is not None and fc.uncertainty.upper is not None:
        lower = fc.uncertainty.lower
        upper = fc.uncertainty.upper
        interval_covered = bool(lower <= actual_value <= upper)
        interval_width = upper - lower

    return ForecastEvaluationRecord(
        actual_state_digest=actual_state.digest(),
        actual_event_time=actual_state.observed_at,
        match_delta_seconds=delta,
        status=EvaluationStatus.EVALUATED,
        reason=None,
        point_forecast=point,
        actual_value=actual_value,
        signed_error=signed,
        absolute_error=abs(signed),
        squared_error=signed * signed,
        interval_lower=lower,
        interval_upper=upper,
        interval_covered=interval_covered,
        interval_width=interval_width,
        **base,
    )


@dataclass(frozen=True)
class AggregateEvaluation:
    """Deterministic aggregate metrics over a set of evaluation records (shadow only)."""

    schema_version: str
    model_id: str
    record_count: int
    forecast_count: int
    abstention_count: int
    abstention_rate: float
    evaluated_count: int
    unmatched_count: int
    subject_mismatch_count: int
    mean_absolute_error: Optional[float]
    root_mean_squared_error: Optional[float]
    mean_signed_error: Optional[float]
    interval_evaluated_count: int
    interval_empirical_coverage: Optional[float]
    average_interval_width: Optional[float]

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "record_count": self.record_count,
            "forecast_count": self.forecast_count,
            "abstention_count": self.abstention_count,
            "abstention_rate": self.abstention_rate,
            "evaluated_count": self.evaluated_count,
            "unmatched_count": self.unmatched_count,
            "subject_mismatch_count": self.subject_mismatch_count,
            "mean_absolute_error": self.mean_absolute_error,
            "root_mean_squared_error": self.root_mean_squared_error,
            "mean_signed_error": self.mean_signed_error,
            "interval_evaluated_count": self.interval_evaluated_count,
            "interval_empirical_coverage": self.interval_empirical_coverage,
            "average_interval_width": self.average_interval_width,
        }

    def digest(self) -> str:
        return content_digest("forecast_aggregate_evaluation", self.schema_version, self.to_canonical_dict())


def aggregate_evaluations(
    records: Sequence[ForecastEvaluationRecord], *, model_id: str = ""
) -> AggregateEvaluation:
    """Compute deterministic aggregate metrics (MAE/RMSE/bias/coverage) over ``records``."""
    records = list(records)
    n = len(records)
    abstentions = [r for r in records if r.status is EvaluationStatus.ABSTAINED]
    evaluated = [r for r in records if r.status is EvaluationStatus.EVALUATED]
    unmatched = [r for r in records if r.status is EvaluationStatus.UNMATCHED]
    mismatched = [r for r in records if r.status is EvaluationStatus.SUBJECT_MISMATCH]
    # A "forecast" was produced (point emitted) for every non-abstention record.
    forecast_count = n - len(abstentions)

    def _mean(xs: List[float]) -> Optional[float]:
        return (sum(xs) / len(xs)) if xs else None

    abs_errs = [r.absolute_error for r in evaluated if r.absolute_error is not None]
    sq_errs = [r.squared_error for r in evaluated if r.squared_error is not None]
    signed_errs = [r.signed_error for r in evaluated if r.signed_error is not None]
    covered = [r.interval_covered for r in evaluated if r.interval_covered is not None]
    widths = [r.interval_width for r in evaluated if r.interval_width is not None]

    mae = _mean(abs_errs)
    mse = _mean(sq_errs)
    rmse = math.sqrt(mse) if mse is not None else None
    bias = _mean(signed_errs)
    coverage = (sum(1 for c in covered if c) / len(covered)) if covered else None
    avg_width = _mean(widths)

    return AggregateEvaluation(
        schema_version=AGGREGATE_EVALUATION_SCHEMA_VERSION,
        model_id=model_id,
        record_count=n,
        forecast_count=forecast_count,
        abstention_count=len(abstentions),
        abstention_rate=(len(abstentions) / n) if n else 0.0,
        evaluated_count=len(evaluated),
        unmatched_count=len(unmatched),
        subject_mismatch_count=len(mismatched),
        mean_absolute_error=mae,
        root_mean_squared_error=rmse,
        mean_signed_error=bias,
        interval_evaluated_count=len(covered),
        interval_empirical_coverage=coverage,
        average_interval_width=avg_width,
    )


__all__ = [
    "EVALUATION_RECORD_SCHEMA_VERSION",
    "AGGREGATE_EVALUATION_SCHEMA_VERSION",
    "EvaluationError",
    "EvaluationStatus",
    "ForecastEvaluationRecord",
    "evaluate_forecast",
    "AggregateEvaluation",
    "aggregate_evaluations",
]
