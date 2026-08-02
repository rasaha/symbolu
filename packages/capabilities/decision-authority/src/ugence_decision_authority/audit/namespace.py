"""Audit event namespace partitioning (kernel).

The audit catalog (:class:`AuditEventType`) was assembled incrementally and
retains every event name verbatim for backward compatibility. This module
*classifies* those names into disjoint namespaces **without renaming any value**:

* ``KERNEL``  — events the governance kernel itself emits (the DecisionCase →
  ActionRequest → Execution → Reconciliation chain, plus the cross-cutting
  policy/security events). These are domain-neutral.
* ``LEGACY``  — the foundational event vocabulary coined before the governance
  chain was partitioned (the initial workflow / evaluation / recommendation /
  decision names). Retained verbatim; owned by consuming domains.
* ``DOMAIN``  — runtime events emitted by a *consuming domain* (its evidence,
  capability, rubric, and assessment runtime), never by the kernel.

The partition is total and disjoint over :class:`AuditEventType`. It is a
read-only overlay: no member is added, removed, renamed, or re-valued. The
kernel deliberately does not name any specific consuming domain here — the
neutral fact it asserts is only *which events the kernel emits* versus which it
does not. A consuming domain may label its own slice within its own layer.
"""

from __future__ import annotations

from enum import Enum

from .events import AuditEventType


class AuditNamespace(str, Enum):
    """Ownership namespace of an audit event name."""

    KERNEL = "KERNEL"
    LEGACY = "LEGACY"
    DOMAIN = "DOMAIN"


# Events the governance kernel emits directly (DecisionCase / ActionRequest /
# Execution / Reconciliation / Compensation, plus the cross-cutting governance
# events). Grounded in the kernel service implementations.
KERNEL_EVENTS: frozenset[AuditEventType] = frozenset({
    AuditEventType.POLICY_DENIED,
    AuditEventType.SECURITY_VIOLATION,
    # Phase 4A — DecisionCase aggregate & lifecycle
    AuditEventType.DECISION_CASE_CREATED,
    AuditEventType.DECISION_CASE_ASSESSMENT_LINKED,
    AuditEventType.DECISION_CASE_RECOMMENDATION_ADDED,
    AuditEventType.DECISION_CASE_RECOMMENDATION_REJECTED,
    AuditEventType.DECISION_CASE_REVIEW_ASSIGNED,
    AuditEventType.DECISION_CASE_REVIEW_COMPLETED,
    AuditEventType.DECISION_CASE_READY_FOR_DECISION,
    AuditEventType.DECISION_RECORDED,
    AuditEventType.DECISION_OVERRIDE_RECORDED,
    AuditEventType.DECISION_CASE_SUPERSEDED,
    AuditEventType.DECISION_CASE_CANCELLED,
    AuditEventType.DECISION_CASE_CLOSED,
    AuditEventType.DECISION_CASE_ACCESS_DENIED,
    # Phase 4B — governed action request & CER binding
    AuditEventType.ACTION_REQUEST_CREATED,
    AuditEventType.ACTION_REQUEST_VALIDATED,
    AuditEventType.ACTION_MAPPING_SELECTED,
    AuditEventType.ACTION_MAPPING_PUBLISHED,
    AuditEventType.CER_CREATED,
    AuditEventType.CER_BOUND,
    AuditEventType.ACTION_AUTHORIZATION_SUBMITTED,
    AuditEventType.ACTION_AUTHORIZATION_GRANTED,
    AuditEventType.ACTION_AUTHORIZATION_CONSTRAINED,
    AuditEventType.ACTION_AUTHORIZATION_DENIED,
    AuditEventType.ACTION_AUTHORIZATION_INDETERMINATE,
    AuditEventType.ACTION_AUTHORIZATION_EXPIRED,
    AuditEventType.ACTION_REQUEST_CANCELLED,
    AuditEventType.ACTION_REQUEST_SUPERSEDED,
    AuditEventType.ACTION_REQUEST_ACCESS_DENIED,
    # Phase 4C — external execution & reconciliation
    AuditEventType.EXECUTION_INTENT_CREATED,
    AuditEventType.EXECUTION_VALIDATED,
    AuditEventType.EXECUTION_DISPATCH_SUBMITTED,
    AuditEventType.EXECUTION_DISPATCH_ACKNOWLEDGED,
    AuditEventType.EXECUTION_TRANSPORT_FAILED,
    AuditEventType.EXECUTION_TIMED_OUT,
    AuditEventType.EXECUTION_OUTCOME_RECORDED,
    AuditEventType.EXECUTION_SUCCEEDED,
    AuditEventType.EXECUTION_FAILED,
    AuditEventType.EXECUTION_PARTIALLY_SUCCEEDED,
    AuditEventType.EXECUTION_DUPLICATE_DETECTED,
    AuditEventType.EXECUTION_RECONCILIATION_STARTED,
    AuditEventType.EXECUTION_RECONCILED,
    AuditEventType.EXECUTION_MISMATCH_DETECTED,
    AuditEventType.EXECUTION_MANUAL_REVIEW_REQUIRED,
    AuditEventType.COMPENSATION_REQUIRED,
    AuditEventType.COMPENSATION_RESOLVED,
    AuditEventType.EXECUTION_RETRY_REQUESTED,
    AuditEventType.EXECUTION_ACCESS_DENIED,
})

# The foundational vocabulary coined before the governance chain existed.
LEGACY_EVENTS: frozenset[AuditEventType] = frozenset({
    AuditEventType.WORKFLOW_INITIALIZED,
    AuditEventType.WORKFLOW_TRANSITION,
    AuditEventType.EVALUATION_CREATED,
    AuditEventType.EVALUATION_UNBLOCKED,
    AuditEventType.RECOMMENDATION_CREATED,
    AuditEventType.DECISION_CREATED,
})

# Everything the kernel does not emit and that is not legacy foundation is a
# consuming-domain runtime event.
DOMAIN_EVENTS: frozenset[AuditEventType] = frozenset(AuditEventType) - KERNEL_EVENTS - LEGACY_EVENTS


def audit_namespace(event_type: AuditEventType) -> AuditNamespace:
    """Classify an audit event name into its ownership namespace."""
    if event_type in KERNEL_EVENTS:
        return AuditNamespace.KERNEL
    if event_type in LEGACY_EVENTS:
        return AuditNamespace.LEGACY
    return AuditNamespace.DOMAIN


def is_kernel_event(event_type: AuditEventType) -> bool:
    """True iff the governance kernel emits this event."""
    return event_type in KERNEL_EVENTS
