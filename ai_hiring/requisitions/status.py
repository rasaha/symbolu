"""Requisition and job-definition lifecycle enums + transition rules (H1).

Structural lifecycle only — never a hiring decision. Transitions are validated
deterministically; terminal states admit no further transition.
"""

from __future__ import annotations

from enum import Enum


class RequisitionStatus(str, Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    ON_HOLD = "ON_HOLD"
    FILLED = "FILLED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


REQUISITION_TERMINAL_STATUSES = frozenset(
    {RequisitionStatus.FILLED, RequisitionStatus.CLOSED, RequisitionStatus.CANCELLED}
)

REQUISITION_ALLOWED_TRANSITIONS: dict[RequisitionStatus, frozenset[RequisitionStatus]] = {
    RequisitionStatus.DRAFT: frozenset({RequisitionStatus.OPEN, RequisitionStatus.CANCELLED}),
    RequisitionStatus.OPEN: frozenset(
        {RequisitionStatus.ON_HOLD, RequisitionStatus.FILLED,
         RequisitionStatus.CLOSED, RequisitionStatus.CANCELLED}
    ),
    RequisitionStatus.ON_HOLD: frozenset(
        {RequisitionStatus.OPEN, RequisitionStatus.CLOSED, RequisitionStatus.CANCELLED}
    ),
    RequisitionStatus.FILLED: frozenset(),
    RequisitionStatus.CLOSED: frozenset(),
    RequisitionStatus.CANCELLED: frozenset(),
}


def requisition_transition_allowed(src: RequisitionStatus, dst: RequisitionStatus) -> bool:
    return dst in REQUISITION_ALLOWED_TRANSITIONS.get(src, frozenset())


class JobDefinitionStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


JOB_DEFINITION_TERMINAL_STATUSES = frozenset({JobDefinitionStatus.RETIRED})

JOB_DEFINITION_ALLOWED_TRANSITIONS: dict[JobDefinitionStatus, frozenset[JobDefinitionStatus]] = {
    JobDefinitionStatus.DRAFT: frozenset({JobDefinitionStatus.PUBLISHED, JobDefinitionStatus.RETIRED}),
    JobDefinitionStatus.PUBLISHED: frozenset({JobDefinitionStatus.RETIRED}),
    JobDefinitionStatus.RETIRED: frozenset(),
}


def job_definition_transition_allowed(src: JobDefinitionStatus, dst: JobDefinitionStatus) -> bool:
    return dst in JOB_DEFINITION_ALLOWED_TRANSITIONS.get(src, frozenset())
