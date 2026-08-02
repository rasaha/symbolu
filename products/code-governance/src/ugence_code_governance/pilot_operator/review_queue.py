"""Deterministic reviewer work queue over persisted intervention assessments.

The queue is **operational coordination only**. A queue item never creates a
binding DecisionRecord or an override, assignment is not approval, and the queue
never mutates the original intervention assessment. Changing the governed head SHA
makes the old queue item STALE.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional, Tuple

from ..fingerprints import domain_hash
from .errors import ReviewQueueError

DOMAIN_REVIEW_QUEUE_ITEM = "cg.pilot_operator.review_queue.v1"


class ReviewerQueueStatus(str, Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FEEDBACK_RECORDED = "FEEDBACK_RECORDED"
    CLOSED = "CLOSED"
    STALE = "STALE"
    CANCELLED = "CANCELLED"


class ReviewPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


_PRIORITY = {"ESCALATE": ReviewPriority.HIGH, "BLOCK": ReviewPriority.MEDIUM,
             "HOLD": ReviewPriority.LOW}


@dataclass(frozen=True)
class ReviewerQueueItem:
    """An immutable reviewer-queue item. Assignment is coordination, never approval."""

    queue_item_id: str
    pilot_id: str
    tenant_id: str
    workflow_id: str
    workflow_revision_id: str
    head_sha: str
    clearance_status: str
    intervention_types: Tuple[str, ...]
    required_authorities: Tuple[str, ...]
    reason_codes: Tuple[str, ...]
    created_at: str
    priority: ReviewPriority
    assignment_status: ReviewerQueueStatus = ReviewerQueueStatus.OPEN
    assigned_reviewer_ref: str = ""
    assigned_reviewer_role: str = ""
    acknowledged_at: str = ""
    resolved_at: str = ""
    feedback_ref: str = ""

    @property
    def record_id(self) -> str:
        return f"review-queue:{self.queue_item_id}:{self.assignment_status.value}:{self.queue_fingerprint[:12]}"

    @property
    def queue_fingerprint(self) -> str:
        return domain_hash(DOMAIN_REVIEW_QUEUE_ITEM, {
            "queue_item_id": self.queue_item_id, "pilot_id": self.pilot_id,
            "tenant_id": self.tenant_id, "workflow_id": self.workflow_id,
            "workflow_revision_id": self.workflow_revision_id, "head_sha": self.head_sha,
            "clearance_status": self.clearance_status,
            "intervention_types": sorted(self.intervention_types),
            "required_authorities": sorted(self.required_authorities),
            "reason_codes": sorted(self.reason_codes), "priority": self.priority.value,
            "assignment_status": self.assignment_status.value,
            "assigned_reviewer_ref": self.assigned_reviewer_ref,
            "assigned_reviewer_role": self.assigned_reviewer_role,
            "feedback_ref": self.feedback_ref})


def build_queue_item(
    *, pilot_id: str, tenant_id: str, workflow_id: str, workflow_revision_id: str,
    head_sha: str, clearance_status: str, intervention_types: Tuple[str, ...],
    required_authorities: Tuple[str, ...], reason_codes: Tuple[str, ...], created_at: str,
) -> ReviewerQueueItem:
    """Build an OPEN queue item from an intervention assessment's fields."""
    priority = _PRIORITY.get(clearance_status, ReviewPriority.LOW)
    qid = domain_hash(DOMAIN_REVIEW_QUEUE_ITEM,
                      {"wf": workflow_id, "rev": workflow_revision_id, "pilot": pilot_id})[:24]
    return ReviewerQueueItem(
        queue_item_id=qid, pilot_id=pilot_id, tenant_id=tenant_id, workflow_id=workflow_id,
        workflow_revision_id=workflow_revision_id, head_sha=head_sha,
        clearance_status=clearance_status, intervention_types=tuple(intervention_types),
        required_authorities=tuple(required_authorities), reason_codes=tuple(reason_codes),
        created_at=created_at, priority=priority)


def assign(item: ReviewerQueueItem, *, reviewer_ref: str, reviewer_role: str,
           role_allowlist: Tuple[str, ...], at: str) -> ReviewerQueueItem:
    """Assign a reviewer (coordination only — never an approval)."""
    if item.tenant_id and reviewer_role not in role_allowlist:
        raise ReviewQueueError(f"reviewer role {reviewer_role!r} not in allowlist")
    return replace(item, assignment_status=ReviewerQueueStatus.ASSIGNED,
                   assigned_reviewer_ref=reviewer_ref, assigned_reviewer_role=reviewer_role)


def acknowledge(item: ReviewerQueueItem, *, at: str) -> ReviewerQueueItem:
    return replace(item, assignment_status=ReviewerQueueStatus.ACKNOWLEDGED, acknowledged_at=at)


def record_feedback(item: ReviewerQueueItem, *, feedback_ref: str, at: str) -> ReviewerQueueItem:
    return replace(item, assignment_status=ReviewerQueueStatus.FEEDBACK_RECORDED,
                   feedback_ref=feedback_ref, resolved_at=at)


def mark_stale(item: ReviewerQueueItem) -> ReviewerQueueItem:
    return replace(item, assignment_status=ReviewerQueueStatus.STALE)


def close(item: ReviewerQueueItem, *, at: str) -> ReviewerQueueItem:
    return replace(item, assignment_status=ReviewerQueueStatus.CLOSED, resolved_at=at)


__all__ = [
    "ReviewerQueueStatus", "ReviewPriority", "ReviewerQueueItem",
    "build_queue_item", "assign", "acknowledge", "record_feedback", "mark_stale", "close",
]
