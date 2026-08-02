"""Immutable workflow lineage + revision records.

Identity model:

```
one repository + PR  ->  one workflow lineage (workflow_id)
                      ->  many immutable revisions keyed by head/base identity
```

* ``workflow_id`` is stable across revisions (tenant + repository + PR).
* ``revision_id`` binds the exact base/head — a new synchronization event that
  changes ``head_sha`` produces a NEW revision; a prior revision is never
  overwritten (its record stays reconstructable but non-current).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple

from ..fingerprints import domain_hash
from ..models.enums import WorkflowMode, WorkflowState


def workflow_id_for(tenant_id: str, repository: str, pull_request_number: int) -> str:
    """Stable lineage id for a repository + PR under a tenant."""
    return domain_hash(
        "workflow_lineage.v1",
        {"tenant_id": tenant_id, "repository": repository,
         "pull_request_number": pull_request_number},
    )


def revision_id_for(workflow_id: str, base_sha: str, head_sha: str) -> str:
    """Revision id bound to the exact base/head identity."""
    return domain_hash(
        "workflow_revision.v1",
        {"workflow_id": workflow_id, "base_sha": base_sha, "head_sha": head_sha},
    )


@dataclass(frozen=True)
class WorkflowRevision:
    """An immutable snapshot of one workflow revision's state + references."""

    workflow_id: str
    revision_id: str
    tenant_id: str
    repository: str
    pull_request_number: int
    change_fingerprint: str
    base_sha: str
    head_sha: str
    state: WorkflowState
    mode: WorkflowMode
    created_at: datetime
    updated_at: datetime

    # accumulated references (empty until the corresponding stage completes)
    evidence_ids: Tuple[str, ...] = ()
    claim_manifest_id: Optional[str] = None
    claim_manifest_fingerprint: Optional[str] = None
    tap_request_fingerprints: Tuple[str, ...] = ()
    tap_result_fingerprints: Tuple[str, ...] = ()
    recommendation_id: Optional[str] = None
    recommendation_fingerprint: Optional[str] = None
    decision_record_id: Optional[str] = None
    cer_id: Optional[str] = None
    cer_content_hash: Optional[str] = None
    prepared_action_fingerprint: Optional[str] = None
    action_request_fingerprint: Optional[str] = None
    action_result_fingerprint: Optional[str] = None
    chain_id: Optional[str] = None
    policy_refs: Tuple[str, ...] = ()
    # MVP 1B — shadow Action Clearance stage
    clearance_stage_state: Optional[str] = None
    clearance_evaluation_ref: Optional[str] = None
    clearance_result_id: Optional[str] = None
    clearance_status: Optional[str] = None
    intervention_assessment_ref: Optional[str] = None
    human_intervention_required: Optional[bool] = None


__all__ = ["WorkflowRevision", "workflow_id_for", "revision_id_for"]
