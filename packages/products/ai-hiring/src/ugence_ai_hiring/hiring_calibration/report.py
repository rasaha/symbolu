"""Cohort-level calibration report.

Aggregates completed hires by role/policy version, decision-contract version,
dimension, review horizon, and confidence band, and reports calibration metrics:
prediction-vs-observed delta, over/underprediction, missing-evidence patterns,
dimension reliability by horizon, and optional descriptive retention/performance
and Overall-Fit summaries.

Overall Fit is descriptive/analytics-only here: it may be *examined* for cohort
calibration but never becomes a policy threshold or eligibility input, and it
plays no role in proposal generation (see :mod:`.proposal`).

The report preserves the three distinct quantities:
  * predicted compatibility  (at-hire DimensionAssessment.score)
  * observed outcome          (ReviewObservation.observed)
  * calibration error         (observed − predicted)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import new_id, utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..hiring_decision.assessment import DimensionAssessment
from ..hiring_decision.decision_case import HiringDecisionCase
from ..hiring_decision.enums import AssessmentOutcome, ReviewCheckpoint
from ..hiring_decision.refs import ContractRef
from .enums import (
    ACCURACY_TOLERANCE,
    CalibrationDirection,
    ConfidenceBand,
    confidence_band,
)
from .errors import CohortMismatchError


class CohortKey(DomainModel):
    """Aggregation key. Deliberately governance-scoped — role/policy/contract only,
    never candidate demographics, so calibration data cannot proxy a protected attribute."""

    role_id: str
    policy_id: str
    contract_id: str
    contract_version: int
    ir_digest: str


class CalibrationDelta(DomainModel):
    """Predicted vs observed for one (dimension, horizon, confidence band) cell."""

    dimension: str
    horizon: ReviewCheckpoint
    confidence_band: ConfidenceBand
    predicted_mean: Optional[float] = None
    observed_mean: Optional[float] = None
    delta: Optional[float] = None
    direction: CalibrationDirection
    sample_size: int = 0


class DimensionReliability(DomainModel):
    """How reliable a dimension's at-hire prediction was at a given horizon."""

    dimension: str
    horizon: ReviewCheckpoint
    mean_abs_delta: Optional[float] = None
    reliability: Optional[float] = None  # 1 - min(1, mean_abs_delta/100)
    sample_size: int = 0
    missing_evidence_count: int = 0


class HiringCalibrationReport(DomainModel):
    """Cohort-level calibration report. Descriptive; changes nothing."""

    report_id: str = Field(default_factory=lambda: new_id("hcalrpt"))
    cohort_key: CohortKey
    generated_at: datetime = Field(default_factory=utc_now)
    case_ids: tuple[str, ...] = ()
    receipt_ids: tuple[str, ...] = ()
    review_ids: tuple[str, ...] = ()
    deltas: tuple[CalibrationDelta, ...] = ()
    reliability: tuple[DimensionReliability, ...] = ()
    missing_evidence: dict[str, int] = {}
    retention_summary: Optional[dict] = None
    overall_fit_descriptive: Optional[dict] = None

    @model_validator(mode="after")
    def _validate(self) -> "HiringCalibrationReport":
        if not self.case_ids:
            raise DomainValidationError("a calibration report needs at least one case")
        return self


def _mean(xs: list[float]) -> Optional[float]:
    return round(sum(xs) / len(xs), 6) if xs else None


def _predicted_scores(case: HiringDecisionCase) -> dict[str, DimensionAssessment]:
    if case.recommendation is None:
        return {}
    return {
        a.dimension: a
        for a in case.recommendation.compatibility_assessment
        if a.outcome is AssessmentOutcome.SCORED and a.score is not None
    }


def _classify(delta: Optional[float]) -> CalibrationDirection:
    if delta is None:
        return CalibrationDirection.INSUFFICIENT
    if abs(delta) <= ACCURACY_TOLERANCE:
        return CalibrationDirection.ACCURATE
    # delta = observed - predicted; negative → we predicted too high
    return (
        CalibrationDirection.OVERPREDICTION
        if delta < 0
        else CalibrationDirection.UNDERPREDICTION
    )


def build_calibration_report(
    cases: tuple[HiringDecisionCase, ...],
    *,
    policy_id: str,
    receipt_ids_by_case: Optional[dict[str, str]] = None,
    retention_summary: Optional[dict] = None,
    overall_fit_descriptive: Optional[dict] = None,
    now: Optional[datetime] = None,
) -> HiringCalibrationReport:
    """Aggregate a homogeneous cohort (same role + contract version) into a report."""
    if not cases:
        raise DomainValidationError("build_calibration_report requires at least one case")

    first = cases[0].contract_ref
    for c in cases:
        if (
            c.role_id != cases[0].role_id
            or c.contract_ref.contract_id != first.contract_id
            or c.contract_ref.version != first.version
            or c.contract_ref.ir_digest != first.ir_digest
        ):
            raise CohortMismatchError(
                "calibration cohorts must share role, contract id, version, and IR digest"
            )

    cohort_key = CohortKey(
        role_id=cases[0].role_id,
        policy_id=policy_id,
        contract_id=first.contract_id,
        contract_version=first.version,
        ir_digest=first.ir_digest,
    )

    receipt_ids_by_case = receipt_ids_by_case or {}

    # Collect per (dimension, horizon, band) predicted/observed samples.
    cells: dict[tuple[str, ReviewCheckpoint, ConfidenceBand], dict[str, list[float]]] = {}
    abs_deltas: dict[tuple[str, ReviewCheckpoint], list[float]] = {}
    missing: dict[tuple[str, ReviewCheckpoint], int] = {}
    review_ids: list[str] = []

    for case in cases:
        predicted = _predicted_scores(case)
        for review in case.reviews:
            review_ids.append(review.review_id)
            for obs in review.observations:
                dim = obs.dimension
                pred = predicted.get(dim)
                band = confidence_band(pred.confidence) if pred is not None else ConfidenceBand.LOW
                key = (dim, review.checkpoint, band)
                cell = cells.setdefault(key, {"predicted": [], "observed": []})
                if pred is not None:
                    cell["predicted"].append(float(pred.score))
                if obs.observed is None:
                    missing[(dim, review.checkpoint)] = missing.get((dim, review.checkpoint), 0) + 1
                else:
                    cell["observed"].append(float(obs.observed))
                    if pred is not None and pred.score is not None:
                        abs_deltas.setdefault((dim, review.checkpoint), []).append(
                            abs(float(obs.observed) - float(pred.score))
                        )

    deltas: list[CalibrationDelta] = []
    for (dim, horizon, band), samples in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][1].value, kv[0][2].value)):
        pmean = _mean(samples["predicted"])
        omean = _mean(samples["observed"])
        delta = round(omean - pmean, 6) if (pmean is not None and omean is not None) else None
        deltas.append(
            CalibrationDelta(
                dimension=dim,
                horizon=horizon,
                confidence_band=band,
                predicted_mean=pmean,
                observed_mean=omean,
                delta=delta,
                direction=_classify(delta),
                sample_size=len(samples["observed"]),
            )
        )

    reliability: list[DimensionReliability] = []
    dims_horizons = sorted(
        {(d, h) for (d, h, _b) in cells}, key=lambda dh: (dh[0], dh[1].value)
    )
    for dim, horizon in dims_horizons:
        ad = abs_deltas.get((dim, horizon), [])
        mad = _mean(ad)
        rel = round(1.0 - min(1.0, mad / 100.0), 6) if mad is not None else None
        reliability.append(
            DimensionReliability(
                dimension=dim,
                horizon=horizon,
                mean_abs_delta=mad,
                reliability=rel,
                sample_size=len(ad),
                missing_evidence_count=missing.get((dim, horizon), 0),
            )
        )

    missing_by_dim: dict[str, int] = {}
    for (dim, _h), n in missing.items():
        missing_by_dim[dim] = missing_by_dim.get(dim, 0) + n

    kwargs = {
        "cohort_key": cohort_key,
        "case_ids": tuple(c.case_id for c in cases),
        "receipt_ids": tuple(
            receipt_ids_by_case[c.case_id] for c in cases if c.case_id in receipt_ids_by_case
        ),
        "review_ids": tuple(review_ids),
        "deltas": tuple(deltas),
        "reliability": tuple(reliability),
        "missing_evidence": missing_by_dim,
        "retention_summary": retention_summary,
        "overall_fit_descriptive": overall_fit_descriptive,
    }
    if now is not None:
        kwargs["generated_at"] = now
    return HiringCalibrationReport(**kwargs)
