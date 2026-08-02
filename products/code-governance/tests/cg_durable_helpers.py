"""Shared builders for MVP 1C (durable shadow persistence) tests."""
from __future__ import annotations

import os
import tempfile

from cg_clearance_helpers import drive_to_action_evaluated, run_clearance
from cg_helpers import (
    LOW_CLAIMS,
    T0,
    claim_inputs_for,
    make_evidence,
    make_payload,
    revision_of,
)
from ugence_code_governance import (
    CodeGovernanceService,
    PersistenceMode,
    RiskTier,
)


def durable_service(path: str | None = None) -> CodeGovernanceService:
    """A service backed by a durable shadow store (in-memory sqlite by default)."""
    if path is None:
        return CodeGovernanceService(persistence_mode=PersistenceMode.DURABLE_SHADOW)
    return CodeGovernanceService(store_path=path)


def temp_db_path() -> str:
    return os.path.join(tempfile.mkdtemp(prefix="cg-durable-"), "cg.db")


def drive_full_1b_durable(svc: CodeGovernanceService, *, head_sha: str = "head-sha-1"):
    """Drive a full MVP 1B pipeline (through SHADOW_COMPLETE) in durable mode."""
    change, rid, action, shadow = drive_to_action_evaluated(svc, head_sha=head_sha)
    record, assessment = run_clearance(svc, rid, action)
    return change, rid, action, shadow, record, assessment


def drive_partial(svc: CodeGovernanceService, *, head_sha: str = "head-sha-1", stop: str = "claims"):
    """Drive a partial pipeline and stop mid-workflow (for recovery tests)."""
    change = svc.ingest_change_event(
        make_payload(head_sha=head_sha), tenant_id="acme", captured_at=T0, delivery_id=head_sha)
    rid = revision_of(change)
    if stop == "identity":
        return change, rid
    for ct in LOW_CLAIMS:
        svc.record_evidence("acme", rid, make_evidence(change, ct))
    if stop == "evidence":
        return change, rid
    svc.build_claim_manifest("acme", rid, risk_tier=RiskTier.LOW,
                             claim_inputs=claim_inputs_for(change, LOW_CLAIMS), captured_at=T0)
    svc.evaluate_claim_requirements("acme", rid, at=T0)
    return change, rid
