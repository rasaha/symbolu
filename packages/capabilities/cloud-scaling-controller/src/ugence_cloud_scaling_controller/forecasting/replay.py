"""Deterministic shadow replay/evaluation harness with hard leakage prevention.

The harness replays a sequence of canonical observations as if time advanced through a set
of cutoffs. For each cutoff it:

1. builds history from ONLY the observations whose event time is ``<= cutoff``,
2. constructs a :class:`~.series.CanonicalCapacitySeries` from that history,
3. produces a forecast + evidence at the cutoff,
4. advances replay time and matches the forecast against a *strictly later* actual
   observation using explicit horizon + timestamp-tolerance rules,
5. records an immutable :class:`~.evaluation.ForecastEvaluationRecord`,

and it NEVER lets a future actual enter the forecast window. Two independent guards enforce
this: the window's own leakage invariant, and a harness assertion that the constructed
series ends at or before the cutoff. The candidate actual is drawn only from observations
whose event time is strictly greater than the cutoff, so the value being scored can never
have been a feature. The harness is robust to adversarial input — future records preloaded
into the source, randomized input order, duplicate timestamps — because it filters by event
time rather than trusting input position, and fails closed on any residual leakage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..canonical.normalization import NormalizationPolicy
from ..canonical.state import CanonicalCapacityState
from .evaluation import (
    AggregateEvaluation,
    EvaluationStatus,
    ForecastEvaluationRecord,
    REASON_AMBIGUOUS_MATCH,
    aggregate_evaluations,
    evaluate_forecast,
    unscored_record,
)
from .evidence import (
    AdmissionPolicy,
    CapacityForecastEvidence,
    forecast_with_evidence,
)
from .calibration import CalibrationProvider
from .forecasters import BaselineForecaster
from .series import (
    CanonicalCapacitySeries,
    SeriesConstructionPolicy,
    _as_utc,
)
from .targets import ForecastTarget, extract_sample
from .uncertainty import UncertaintyConfig
from .window import FeatureConfig, ForecastHorizon, build_input_window


class ReplayError(ValueError):
    """Raised when replay detects an unsafe condition, e.g. residual leakage (fail closed)."""


@dataclass(frozen=True)
class ReplayEvaluationResult:
    """The complete result of a replay: paired evidences+records plus the aggregate."""

    evidences: Tuple[CapacityForecastEvidence, ...]
    records: Tuple[ForecastEvaluationRecord, ...]
    aggregate: AggregateEvaluation


def default_cutoffs(observations: Sequence[CanonicalCapacityState]) -> Tuple[datetime, ...]:
    """Sorted, unique observation event times — the natural replay cutoffs."""
    seen = {}
    for o in observations:
        key = _as_utc(o.observed_at)
        seen[key] = o.observed_at
    return tuple(seen[k] for k in sorted(seen))


def _history_at_or_before(
    observations: Sequence[CanonicalCapacityState], cutoff: datetime
) -> List[CanonicalCapacityState]:
    """Observations with event time ``<= cutoff`` (the ONLY data a forecast may see)."""
    c = _as_utc(cutoff)
    return [o for o in observations if _as_utc(o.observed_at) <= c]


# Matcher outcome kinds.
MATCH_UNIQUE = "unique"        # exactly one closest eligible candidate
MATCH_NONE = "none"           # no eligible candidate within tolerance
MATCH_AMBIGUOUS = "ambiguous"  # >1 candidate equally closest under the full policy

_MATCH_TOL = 1e-9


def _match_actual(
    observations: Sequence[CanonicalCapacityState],
    cutoff: datetime,
    forecast_for: datetime,
    tolerance_seconds: float,
    subject,
    target: ForecastTarget,
) -> Tuple[str, Optional[CanonicalCapacityState]]:
    """Deterministic, order-independent matcher (fail closed on ambiguity).

    Eligibility (documented matching policy): an actual is eligible iff it has the SAME
    subject/tenant/scope, carries the target, has event time STRICTLY greater than the
    cutoff (so the scored value was never available to the forecast), and lies within
    ``tolerance_seconds`` of the forecast-for time. Among eligible candidates the one with
    the smallest gap to the forecast-for time is chosen. If two or more candidates share
    the minimum gap, the result is AMBIGUOUS (never silently break the tie by input order).
    Returns ``(kind, state_or_None)``.
    """
    c = _as_utc(cutoff)
    tgt = _as_utc(forecast_for)
    eligible = []
    for o in observations:
        ot = _as_utc(o.observed_at)
        if ot <= c:  # never a past/at-cutoff observation — that would be leakage
            continue
        if o.subject != subject:  # full subject equality covers tenant/scope
            continue
        if extract_sample(o, target) is None:
            continue
        gap = abs((ot - tgt).total_seconds())
        if gap <= tolerance_seconds:
            eligible.append((gap, ot, o.digest(), o))
    if not eligible:
        return MATCH_NONE, None
    # Deterministic total order independent of input position.
    eligible.sort(key=lambda e: (e[0], e[1], e[2]))
    min_gap = eligible[0][0]
    at_min = [e for e in eligible if abs(e[0] - min_gap) <= _MATCH_TOL]
    if len(at_min) > 1:
        return MATCH_AMBIGUOUS, None
    return MATCH_UNIQUE, at_min[0][3]


def _calibration_residual(
    series: CanonicalCapacitySeries,
    observations: Sequence[CanonicalCapacityState],
    target: ForecastTarget,
    cutoff: datetime,
    horizon: ForecastHorizon,
    forecaster: BaselineForecaster,
    feature_config: FeatureConfig,
    match_tolerance_seconds: float,
) -> Optional[Tuple[datetime, float]]:
    """``(actual_event_time, signed residual)`` for one calibration origin, or ``None``.

    Deliberately independent of the gating outcome. Calibration residuals are accounted
    separately from gating records (run manifest §9.3), and during the calibration block no
    forecast is scored at all — feeding the bank only from scored records would deadlock: no
    residuals means no interval, no interval means an abstention, and an abstention means no
    residual.

    Leakage safety is unchanged: the window is the same leakage-safe construction used by the
    service, and the actual is matched by the same strictly-future matcher. The residual is
    *timestamped* with that actual's event time, so the bank can refuse to serve it until it
    was observable.
    """
    try:
        window = build_input_window(series, target, cutoff, horizon, feature_config)
    except Exception:  # a window we cannot build yields no calibration — never a hard failure
        return None
    point = forecaster.point_estimate(window)
    if point is None or not isinstance(point, (int, float)) or not math.isfinite(float(point)):
        return None
    kind, actual = _match_actual(
        observations, cutoff, window.forecast_for, match_tolerance_seconds, series.subject, target,
    )
    if kind != MATCH_UNIQUE or actual is None:
        return None
    sample = extract_sample(actual, target)
    if sample is None or not math.isfinite(float(sample.value)):
        return None
    return actual.observed_at, float(sample.value) - float(point)


def run_replay_evaluation(
    observations: Sequence[CanonicalCapacityState],
    target: ForecastTarget,
    horizon: ForecastHorizon,
    forecaster: BaselineForecaster,
    *,
    normalization_policy: Optional[NormalizationPolicy],
    cutoffs: Optional[Sequence[datetime]] = None,
    feature_config: Optional[FeatureConfig] = None,
    uncertainty_config: Optional[UncertaintyConfig] = None,
    admission_policy: Optional[AdmissionPolicy] = None,
    series_policy: Optional[SeriesConstructionPolicy] = None,
    match_tolerance_seconds: float = 5.0,
    calibration_provider: Optional[CalibrationProvider] = None,
) -> ReplayEvaluationResult:
    """Replay ``observations`` through ``cutoffs`` and return evidences + evaluation records.

    All observations share one subject (a series requires it); cross-subject inputs fail
    closed in series construction. ``cutoffs`` defaults to the observation event times.

    ``calibration_provider`` is optional evaluation machinery. When ``None`` — the default and
    the only production behaviour — every forecast uses the shipped in-window rolling-origin
    uncertainty path and the evidence is byte-identical to a run without this parameter. When
    supplied, each cutoff asks the provider for a causally admissible residual collection, and
    each *scored* forecast feeds its own residual back so later cutoffs can use it. Residuals
    are fed strictly forward: a residual is admitted with the origin and the matched actual's
    event time, and the provider itself refuses to serve it before that actual was observable.
    """
    observations = list(observations)
    if not observations:
        raise ReplayError("replay requires at least one observation")
    if cutoffs is None:
        cutoffs = default_cutoffs(observations)

    evidences: List[CapacityForecastEvidence] = []
    records: List[ForecastEvaluationRecord] = []

    for cutoff in cutoffs:
        history = _history_at_or_before(observations, cutoff)
        if not history:
            continue
        series = CanonicalCapacitySeries.build(history, series_policy)

        # Independent leakage guard (belt-and-suspenders with the window invariant).
        if _as_utc(series.end_event_time) > _as_utc(cutoff):
            raise ReplayError(
                "leakage detected: constructed series extends beyond the cutoff "
                f"({series.end_event_time.isoformat()} > {cutoff.isoformat()})"
            )

        calibration = None
        if calibration_provider is not None:
            calibration = calibration_provider.calibration_for(
                series.subject, target, horizon, forecaster.model_id, cutoff
            )

        evidence = forecast_with_evidence(
            series, target, cutoff, horizon, forecaster,
            normalization_policy=normalization_policy,
            feature_config=feature_config,
            uncertainty_config=uncertainty_config,
            admission_policy=admission_policy,
            correlation_id=None,
            calibration=calibration,
        )

        if evidence.forecast.is_forecast:
            kind, actual = _match_actual(
                observations, cutoff, evidence.forecast.forecast_for,
                match_tolerance_seconds, series.subject, target,
            )
            if actual is not None and _as_utc(actual.observed_at) <= _as_utc(cutoff):
                raise ReplayError("leakage detected: matched actual is not strictly future")
            if kind == MATCH_AMBIGUOUS:
                record = unscored_record(
                    evidence, status=EvaluationStatus.AMBIGUOUS, reason=REASON_AMBIGUOUS_MATCH,
                    match_tolerance_seconds=match_tolerance_seconds,
                )
            else:  # MATCH_UNIQUE (actual set) or MATCH_NONE (actual is None -> UNMATCHED)
                record = evaluate_forecast(evidence, actual, match_tolerance_seconds=match_tolerance_seconds)
        else:
            record = evaluate_forecast(evidence, None, match_tolerance_seconds=match_tolerance_seconds)
        evidences.append(evidence)
        records.append(record)

        # Feed the bank causally and independently of the gating outcome. A residual becomes
        # usable only from a LATER cutoff, and the provider re-checks observability itself, so
        # a residual can never calibrate its own origin.
        if calibration_provider is not None and hasattr(calibration_provider, "observe"):
            fed = _calibration_residual(
                series, observations, target, cutoff, horizon, forecaster,
                feature_config or FeatureConfig(), match_tolerance_seconds,
            )
            if fed is not None:
                actual_time, residual = fed
                calibration_provider.observe(
                    subject=series.subject,
                    target=target,
                    horizon=horizon,
                    arm_model_id=forecaster.model_id,
                    origin=cutoff,
                    actual_event_time=actual_time,
                    residual=residual,
                )

    aggregate = aggregate_evaluations(records, model_id=forecaster.model_id)
    return ReplayEvaluationResult(
        evidences=tuple(evidences),
        records=tuple(records),
        aggregate=aggregate,
    )


__all__ = [
    "ReplayError",
    "ReplayEvaluationResult",
    "default_cutoffs",
    "run_replay_evaluation",
]
