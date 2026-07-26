"""Requisition and job-definition contracts (H1)."""

from __future__ import annotations

from .job_definition import JobDefinition
from .requisition import JobRequisition
from .status import (
    JOB_DEFINITION_ALLOWED_TRANSITIONS,
    JOB_DEFINITION_TERMINAL_STATUSES,
    REQUISITION_ALLOWED_TRANSITIONS,
    REQUISITION_TERMINAL_STATUSES,
    JobDefinitionStatus,
    RequisitionStatus,
    job_definition_transition_allowed,
    requisition_transition_allowed,
)

__all__ = [
    "JobRequisition",
    "JobDefinition",
    "RequisitionStatus",
    "JobDefinitionStatus",
    "REQUISITION_ALLOWED_TRANSITIONS",
    "REQUISITION_TERMINAL_STATUSES",
    "JOB_DEFINITION_ALLOWED_TRANSITIONS",
    "JOB_DEFINITION_TERMINAL_STATUSES",
    "requisition_transition_allowed",
    "job_definition_transition_allowed",
]
