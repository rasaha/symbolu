"""Deterministic product-owned Workflow Service (coordination, no authority)."""
from __future__ import annotations

from .records import WorkflowRevision, revision_id_for, workflow_id_for
from .service import WorkflowRun, new_run
from .state_machine import LEGAL_TRANSITIONS, assert_transition, is_legal_transition

__all__ = [
    "WorkflowRevision",
    "workflow_id_for",
    "revision_id_for",
    "WorkflowRun",
    "new_run",
    "LEGAL_TRANSITIONS",
    "assert_transition",
    "is_legal_transition",
]
