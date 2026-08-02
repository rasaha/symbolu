"""Append-only reviewer annotations over pilot evaluations.

An annotation records a reviewer's curated assessment of one evaluation, bound to
the exact workflow revision + head SHA. It never modifies the original clearance
or intervention record. The preferred protocol records an *initial independent*
assessment before the Ugence result is revealed; when blinding is impossible the
annotation is marked ``REVIEW_NOT_BLINDED`` and independent agreement is not claimed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from ..fingerprints import domain_hash
from .errors import AnnotationError
from .vocab import (
    ActualOutcome,
    IncrementalValue,
    IncrementalValueLabel,
    InterventionAssessment,
    PilotEvidenceClass,
    ReviewMode,
    RootCause,
    StatusAssessment,
    UNIQUE_VALUE_LABELS,
)

DOMAIN_ANNOTATION = "cg.pilot_study.annotation.v1"


@dataclass(frozen=True)
class PilotEvaluationAnnotation:
    """An append-only reviewer annotation for one pilot evaluation."""

    annotation_id: str
    pilot_id: str
    evaluation_id: str
    tenant_id: str
    workflow_id: str
    workflow_revision_id: str
    head_sha: str
    reviewer_ref: str
    reviewer_role: str
    review_mode: ReviewMode
    evidence_class: PilotEvidenceClass
    initial_reviewer_status: StatusAssessment
    ugence_clearance_status: str
    status_assessment: StatusAssessment
    intervention_assessment: InterventionAssessment
    required_authority_correct: bool
    incremental_value: IncrementalValue
    incremental_value_labels: Tuple[IncrementalValueLabel, ...]
    root_cause_categories: Tuple[RootCause, ...]
    actual_outcome: ActualOutcome
    would_ci_have_detected: bool
    created_at: str
    unique_value_evidence_ref: str = ""
    note_classification: str = "NONE"

    def __post_init__(self) -> None:
        # A claim of unique detection requires a supporting evidence reference.
        if any(l in UNIQUE_VALUE_LABELS for l in self.incremental_value_labels) \
                and not self.unique_value_evidence_ref:
            raise AnnotationError("a unique-value claim requires an evidence reference")

    @property
    def annotation_fingerprint(self) -> str:
        return domain_hash(DOMAIN_ANNOTATION, {
            "annotation_id": self.annotation_id, "pilot_id": self.pilot_id,
            "evaluation_id": self.evaluation_id, "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id, "workflow_revision_id": self.workflow_revision_id,
            "head_sha": self.head_sha, "reviewer_ref": self.reviewer_ref,
            "reviewer_role": self.reviewer_role, "review_mode": self.review_mode.value,
            "evidence_class": self.evidence_class.value,
            "initial_reviewer_status": self.initial_reviewer_status.value,
            "ugence_clearance_status": self.ugence_clearance_status,
            "status_assessment": self.status_assessment.value,
            "intervention_assessment": self.intervention_assessment.value,
            "required_authority_correct": self.required_authority_correct,
            "incremental_value": self.incremental_value.value,
            "incremental_value_labels": sorted(l.value for l in self.incremental_value_labels),
            "root_cause_categories": sorted(c.value for c in self.root_cause_categories),
            "actual_outcome": self.actual_outcome.value,
            "would_ci_have_detected": self.would_ci_have_detected,
            "unique_value_evidence_ref": self.unique_value_evidence_ref,
            "note_classification": self.note_classification})

    @property
    def record_id(self) -> str:
        return f"pilot-annotation:{self.annotation_id}:{self.annotation_fingerprint[:12]}"

    @property
    def blinded(self) -> bool:
        return self.review_mode is ReviewMode.BLINDED_INITIAL_THEN_REVEALED

    @property
    def disagrees_on_status(self) -> bool:
        return self.status_assessment is not StatusAssessment.AGREE


__all__ = ["PilotEvaluationAnnotation", "DOMAIN_ANNOTATION"]
