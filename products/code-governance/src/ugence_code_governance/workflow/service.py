"""Workflow Service — deterministic coordinator that owns no authority.

The service holds a mutable per-revision run context, validates each state
transition (fail closed), and snapshots an immutable :class:`WorkflowRevision`
when it persists. It never makes a governance decision, never authorizes an
action, and never executes anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from ..models.change_identity import GovernedChangeIdentity
from ..models.enums import WorkflowMode, WorkflowState
from .records import WorkflowRevision, revision_id_for, workflow_id_for
from .state_machine import assert_transition


@dataclass
class WorkflowRun:
    """Mutable orchestration context for one revision (product-internal)."""

    workflow_id: str
    revision_id: str
    change: GovernedChangeIdentity
    state: WorkflowState
    mode: WorkflowMode
    created_at: datetime
    updated_at: datetime

    evidence_ids: List[str] = field(default_factory=list)
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

    def transition(self, target: WorkflowState, *, at: datetime) -> None:
        assert_transition(self.state, target)
        self.state = target
        self.updated_at = at

    def snapshot(self) -> WorkflowRevision:
        return WorkflowRevision(
            workflow_id=self.workflow_id,
            revision_id=self.revision_id,
            tenant_id=self.change.tenant_id,
            repository=self.change.repository,
            pull_request_number=self.change.pull_request_number,
            change_fingerprint=self.change.fingerprint,
            base_sha=self.change.base_sha,
            head_sha=self.change.head_sha,
            state=self.state,
            mode=self.mode,
            created_at=self.created_at,
            updated_at=self.updated_at,
            evidence_ids=tuple(self.evidence_ids),
            claim_manifest_id=self.claim_manifest_id,
            claim_manifest_fingerprint=self.claim_manifest_fingerprint,
            tap_request_fingerprints=self.tap_request_fingerprints,
            tap_result_fingerprints=self.tap_result_fingerprints,
            recommendation_id=self.recommendation_id,
            recommendation_fingerprint=self.recommendation_fingerprint,
            decision_record_id=self.decision_record_id,
            cer_id=self.cer_id,
            cer_content_hash=self.cer_content_hash,
            prepared_action_fingerprint=self.prepared_action_fingerprint,
            action_request_fingerprint=self.action_request_fingerprint,
            action_result_fingerprint=self.action_result_fingerprint,
            chain_id=self.chain_id,
            policy_refs=self.policy_refs,
        )


def new_run(change: GovernedChangeIdentity, *, at: datetime) -> WorkflowRun:
    """Create a fresh run for a governed change (RECEIVED -> IDENTITY_BOUND)."""
    wid = workflow_id_for(change.tenant_id, change.repository, change.pull_request_number)
    rid = revision_id_for(wid, change.base_sha, change.head_sha)
    run = WorkflowRun(
        workflow_id=wid,
        revision_id=rid,
        change=change,
        state=WorkflowState.RECEIVED,
        mode=WorkflowMode.SHADOW,
        created_at=at,
        updated_at=at,
    )
    run.transition(WorkflowState.IDENTITY_BOUND, at=at)
    return run


__all__ = ["WorkflowRun", "new_run"]
