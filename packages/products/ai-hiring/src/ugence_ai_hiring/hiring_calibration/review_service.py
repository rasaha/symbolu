"""PostHireReviewService — records structured 1/3/6/12-month reviews.

Review evidence is **job-related and observable only** (the
:class:`~ugence_ai_hiring.hiring_decision.enums.OutcomeEvidenceType` vocabulary:
onboarding, manager review, performance goal, collaboration, delivery,
retention). No personality, culture-fit, psychological-resilience, health, or
protected-attribute inference is introduced — those are not representable, and
forbidden legacy dimensions are rejected.

Recording a review is **append-only**: it never mutates the historical decision,
recommendation, eligibility, or evidence on the case (see
:meth:`HiringDecisionCase.record_review`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..hiring_decision.decision_case import HiringDecisionCase
from ..hiring_decision.enums import DecisionDisposition, ReviewCheckpoint
from ..hiring_decision.reviews import ReviewObservation, ReviewRecord
from ..hiring_decision.enums import Trajectory
from ..hiring_policy.enums import FORBIDDEN_DIMENSIONS
from .errors import DuplicateReviewError, NotHiredError, ReviewTimingError

# Inclusive day windows for each checkpoint, measured from the hire date.
CHECKPOINT_WINDOW_DAYS: dict[ReviewCheckpoint, tuple[int, int]] = {
    ReviewCheckpoint.ONE_MONTH: (15, 60),
    ReviewCheckpoint.THREE_MONTH: (61, 150),
    ReviewCheckpoint.SIX_MONTH: (151, 300),
    ReviewCheckpoint.TWELVE_MONTH: (301, 450),
}


class PostHireReviewService:
    """Records post-hire reviews on a hired case."""

    def record_review(
        self,
        case: HiringDecisionCase,
        checkpoint: ReviewCheckpoint,
        observations: tuple[ReviewObservation, ...],
        *,
        trajectory: Trajectory = Trajectory.ON_TRACK,
        hire_date: Optional[datetime] = None,
        review_date: Optional[datetime] = None,
    ) -> tuple[HiringDecisionCase, ReviewRecord]:
        # Only actual hires get post-hire reviews.
        if case.decision is None or case.decision.disposition is not DecisionDisposition.ADVANCE:
            raise NotHiredError(
                "post-hire reviews require a case with a binding ADVANCE decision"
            )

        # One review per checkpoint per case.
        if any(r.checkpoint is checkpoint for r in case.reviews):
            raise DuplicateReviewError(f"a {checkpoint.value} review already exists for this case")

        # Timing validation (only when both dates are supplied).
        if hire_date is not None and review_date is not None:
            days = (review_date - hire_date).days
            lo, hi = CHECKPOINT_WINDOW_DAYS[checkpoint]
            if days < 0:
                raise ReviewTimingError("review_date precedes hire_date")
            if not (lo <= days <= hi):
                raise ReviewTimingError(
                    f"{checkpoint.value} review at {days}d is outside its window [{lo},{hi}]"
                )

        # Job-related, observable evidence only.
        self._validate_observations(observations)

        review = ReviewRecord(
            case_id=case.case_id,
            checkpoint=checkpoint,
            contract_ref=case.contract_ref,
            observations=observations,
            trajectory=trajectory,
        )
        return case.record_review(review), review

    @staticmethod
    def _validate_observations(observations: tuple[ReviewObservation, ...]) -> None:
        from ..errors import DomainValidationError

        for obs in observations:
            if obs.dimension.strip().upper() in FORBIDDEN_DIMENSIONS:
                raise DomainValidationError(
                    f"review dimension {obs.dimension!r} is removed from the model "
                    f"(no culture-fit / resilience constructs)"
                )
            # An observed value must be backed by job-related observable evidence.
            if obs.observed is not None and not obs.outcome_evidence:
                raise DomainValidationError(
                    f"observed value for {obs.dimension!r} must cite job-related outcome evidence"
                )
