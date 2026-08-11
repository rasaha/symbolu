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
from .forecasters import BaselineForecaster
from .series import (
    CanonicalCapacitySeries,
    SeriesConstructionPolicy,
    _as_utc,
)
from .targets import ForecastTarget, extract_sample
from .uncertainty import UncertaintyConfig
from .window import FeatureConfig, ForecastHorizon


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
) -> ReplayEvaluationResult:
    """Replay ``observations`` through ``cutoffs`` and return evidences + evaluation records.

    All observations share one subject (a series requires it); cross-subject inputs fail
    closed in series construction. ``cutoffs`` defaults to the observation event times.
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

        evidence = forecast_with_evidence(
            series, target, cutoff, horizon, forecaster,
            normalization_policy=normalization_policy,
            feature_config=feature_config,
            uncertainty_config=uncertainty_config,
            admission_policy=admission_policy,
            correlation_id=None,
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
