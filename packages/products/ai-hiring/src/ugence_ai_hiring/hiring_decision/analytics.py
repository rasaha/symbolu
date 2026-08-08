"""Overall Fit Index — ANALYTICS ONLY.

This module computes a role-specific weighted fit value and a range label
(HIGH / MEDIUM / LOW) for funnels, heatmaps, and cohort comparison.

HARD BOUNDARY: the Overall Fit Index must never determine a gate, eligibility,
recommendation, or policy decision. Nothing in the decision plane
(``gates``, ``eligibility``, ``recommendation``, ``decision_case``) nor the
policy plane (``hiring_policy``) may import this module — enforced by a source
scan in the package tests. It is intentionally NOT re-exported from
``hiring_decision/__init__.py``, so importing the decision plane never loads it;
consumers must import it explicitly by path.
"""

from __future__ import annotations

from pydantic import Field

from ..domain.base import DomainModel
from .assessment import DimensionAssessment
from .enums import AssessmentOutcome, FitRange

_HIGH_THRESHOLD = 80.0
_MEDIUM_THRESHOLD = 50.0
_LOW_CONFIDENCE_THRESHOLD = 0.5


class OverallFitResult(DomainModel):
    """A non-binding analytics fit summary."""

    value: float = Field(ge=0.0, le=100.0)
    range: FitRange
    confidence_qualifier: str = ""  # "low confidence" when aggregate confidence is low
    analytics_only: bool = True


def compute_overall_fit(
    assessments: tuple[DimensionAssessment, ...],
    dimension_weights: dict[str, float],
) -> OverallFitResult:
    """Weighted mean of scored dimensions using role weights; analytics only.

    Only SCORED dimensions contribute; weights are renormalized over the scored,
    weighted subset. Returns 0/LOW when nothing scored.
    """
    scored = {
        a.dimension: a
        for a in assessments
        if a.outcome is AssessmentOutcome.SCORED and a.score is not None
    }
    contributing = {d: w for d, w in dimension_weights.items() if d in scored and w > 0}
    total_w = sum(contributing.values())
    if not contributing or total_w <= 0:
        return OverallFitResult(value=0.0, range=FitRange.LOW, confidence_qualifier="no scored evidence")

    value = round(
        sum(scored[d].score * (w / total_w) for d, w in contributing.items()), 6
    )
    if value >= _HIGH_THRESHOLD:
        rng = FitRange.HIGH
    elif value >= _MEDIUM_THRESHOLD:
        rng = FitRange.MEDIUM
    else:
        rng = FitRange.LOW

    agg_conf = sum(scored[d].confidence for d in contributing) / len(contributing)
    qualifier = "low confidence" if agg_conf < _LOW_CONFIDENCE_THRESHOLD else ""
    return OverallFitResult(value=value, range=rng, confidence_qualifier=qualifier)
