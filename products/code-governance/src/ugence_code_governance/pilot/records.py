"""Immutable shadow-pilot records: evaluation records + reviewer feedback.

Both are content-addressed and execution-neutral. Reviewer feedback is **audit
data only** — it never retrains, modifies, or overrides policy, and never changes
the original clearance result. Execution status is always ``DISABLED``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from ..fingerprints import domain_hash

DOMAIN_PILOT_EVALUATION = "cg.pilot.evaluation.v1"
DOMAIN_PILOT_FEEDBACK = "cg.pilot.feedback.v1"


class FeedbackAgreement(str, Enum):
    """Curated reviewer-agreement categories (no free-form sensitive text required)."""

    AGREE = "AGREE"
    DISAGREE_STATUS = "DISAGREE_STATUS"
    DISAGREE_INTERVENTION_REQUIRED = "DISAGREE_INTERVENTION_REQUIRED"
    DISAGREE_INTERVENTION_TYPE = "DISAGREE_INTERVENTION_TYPE"
    DISAGREE_REQUIRED_AUTHORITY = "DISAGREE_REQUIRED_AUTHORITY"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    SOURCE_DATA_INCORRECT = "SOURCE_DATA_INCORRECT"
    POLICY_CONFIGURATION_ISSUE = "POLICY_CONFIGURATION_ISSUE"


class ObservedResolution(str, Enum):
    """Curated observed-resolution categories."""

    PROCEEDED_WITHOUT_CHANGE = "PROCEEDED_WITHOUT_CHANGE"
    WAITED_FOR_CONDITION = "WAITED_FOR_CONDITION"
    REFRESHED_SIGNAL = "REFRESHED_SIGNAL"
    REAUTHORIZED = "REAUTHORIZED"
    CODE_CHANGED = "CODE_CHANGED"
    HUMAN_EXCEPTION_APPROVED = "HUMAN_EXCEPTION_APPROVED"
    ABANDONED = "ABANDONED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ShadowPilotEvaluationRecord:
    """An immutable record of one shadow-pilot evaluation. Execution DISABLED."""

    pilot_id: str
    tenant_id: str
    workflow_id: str
    workflow_revision_id: str
    change_fingerprint: str
    adapter_request_ref: str
    adapter_result_refs: Tuple[str, ...]
    signal_refs: Tuple[str, ...]
    clearance_evaluation_ref: str
    clearance_status: str
    action_clearance_status: str
    intervention_assessment_ref: str
    human_intervention_required: bool
    collection_started_at: datetime
    collection_completed_at: datetime
    evaluation_time: datetime
    pilot_profile_ref: str
    stale: bool = False
    conflicts: Tuple[str, ...] = ()
    source_failures: Tuple[str, ...] = ()
    execution_status: str = "DISABLED"

    @property
    def record_id(self) -> str:
        return f"pilot-eval:{self.pilot_id}:{self.workflow_revision_id}"

    @property
    def record_fingerprint(self) -> str:
        return domain_hash(DOMAIN_PILOT_EVALUATION, {
            "pilot_id": self.pilot_id, "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id, "workflow_revision_id": self.workflow_revision_id,
            "change_fingerprint": self.change_fingerprint,
            "adapter_request_ref": self.adapter_request_ref,
            "adapter_result_refs": sorted(self.adapter_result_refs),
            "signal_refs": sorted(self.signal_refs),
            "clearance_evaluation_ref": self.clearance_evaluation_ref,
            "clearance_status": self.clearance_status,
            "action_clearance_status": self.action_clearance_status,
            "intervention_assessment_ref": self.intervention_assessment_ref,
            "human_intervention_required": self.human_intervention_required,
            "pilot_profile_ref": self.pilot_profile_ref,
            "stale": self.stale, "conflicts": sorted(self.conflicts),
            "source_failures": sorted(self.source_failures),
            "execution_status": self.execution_status,
        })


@dataclass(frozen=True)
class PilotReviewerFeedback:
    """Immutable, curated reviewer feedback. Audit data only — never changes policy."""

    feedback_id: str
    pilot_id: str
    tenant_id: str
    workflow_id: str
    workflow_revision_id: str
    reviewer_ref: str
    reviewer_role: str
    reviewed_clearance_status: str
    reviewed_intervention_required: bool
    agreement: FeedbackAgreement
    observed_resolution: ObservedResolution
    submitted_at: datetime
    false_positive_category: str = ""
    false_negative_concern: str = ""
    comment_classification: str = "NONE"
    policy_refs: Tuple[str, ...] = ()

    @property
    def record_id(self) -> str:
        return f"pilot-feedback:{self.feedback_id}"

    @property
    def feedback_fingerprint(self) -> str:
        return domain_hash(DOMAIN_PILOT_FEEDBACK, {
            "feedback_id": self.feedback_id, "pilot_id": self.pilot_id,
            "tenant_id": self.tenant_id, "workflow_id": self.workflow_id,
            "workflow_revision_id": self.workflow_revision_id,
            "reviewer_ref": self.reviewer_ref, "reviewer_role": self.reviewer_role,
            "reviewed_clearance_status": self.reviewed_clearance_status,
            "reviewed_intervention_required": self.reviewed_intervention_required,
            "agreement": self.agreement.value,
            "observed_resolution": self.observed_resolution.value,
            "false_positive_category": self.false_positive_category,
            "false_negative_concern": self.false_negative_concern,
            "comment_classification": self.comment_classification,
        })


__all__ = [
    "FeedbackAgreement", "ObservedResolution",
    "ShadowPilotEvaluationRecord", "PilotReviewerFeedback",
    "DOMAIN_PILOT_EVALUATION", "DOMAIN_PILOT_FEEDBACK",
]
