"""Recommendation lifecycle enum + transition rules (H2).

Advisory lifecycle only. There is **no binding decision status** — a recommendation
never becomes a hiring decision. Terminal states are REJECTED_BY_REVIEW and
SUPERSEDED. The generation service constructs a recommendation directly in its
computed initial status (DRAFT / EVIDENCE_INCOMPLETE / ASSERTION_REVIEW_REQUIRED /
READY_FOR_HUMAN_REVIEW); reviewer/supersession moves are validated transitions.
"""

from __future__ import annotations

from enum import Enum


class RecommendationStatus(str, Enum):
    DRAFT = "DRAFT"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    ASSERTION_REVIEW_REQUIRED = "ASSERTION_REVIEW_REQUIRED"
    READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"
    REJECTED_BY_REVIEW = "REJECTED_BY_REVIEW"
    SUPERSEDED = "SUPERSEDED"


RECOMMENDATION_TERMINAL_STATUSES = frozenset(
    {RecommendationStatus.REJECTED_BY_REVIEW, RecommendationStatus.SUPERSEDED}
)

# Statuses a freshly generated recommendation may be constructed in.
RECOMMENDATION_INITIAL_STATUSES = frozenset(
    {RecommendationStatus.DRAFT, RecommendationStatus.EVIDENCE_INCOMPLETE,
     RecommendationStatus.ASSERTION_REVIEW_REQUIRED, RecommendationStatus.READY_FOR_HUMAN_REVIEW}
)

RECOMMENDATION_ALLOWED_TRANSITIONS: dict[RecommendationStatus, frozenset[RecommendationStatus]] = {
    RecommendationStatus.DRAFT: frozenset(
        {RecommendationStatus.EVIDENCE_INCOMPLETE, RecommendationStatus.ASSERTION_REVIEW_REQUIRED,
         RecommendationStatus.READY_FOR_HUMAN_REVIEW, RecommendationStatus.SUPERSEDED}),
    RecommendationStatus.EVIDENCE_INCOMPLETE: frozenset({RecommendationStatus.SUPERSEDED}),
    RecommendationStatus.ASSERTION_REVIEW_REQUIRED: frozenset(
        {RecommendationStatus.READY_FOR_HUMAN_REVIEW, RecommendationStatus.REJECTED_BY_REVIEW,
         RecommendationStatus.SUPERSEDED}),
    RecommendationStatus.READY_FOR_HUMAN_REVIEW: frozenset(
        {RecommendationStatus.REJECTED_BY_REVIEW, RecommendationStatus.SUPERSEDED}),
    RecommendationStatus.REJECTED_BY_REVIEW: frozenset(),
    RecommendationStatus.SUPERSEDED: frozenset(),
}


def recommendation_transition_allowed(src: RecommendationStatus, dst: RecommendationStatus) -> bool:
    return dst in RECOMMENDATION_ALLOWED_TRANSITIONS.get(src, frozenset())
