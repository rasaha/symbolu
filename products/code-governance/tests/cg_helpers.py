"""Shared test helpers for the Code Governance product tests."""
from __future__ import annotations

from datetime import datetime, timezone

from ugence_code_governance import (
    AuthorizedActor,
    ClaimInput,
    ClaimStatus,
    ClaimType,
    CodeGovernanceService,
    DecisionInput,
    EvidenceRecord,
    MergeMethod,
    RiskTier,
    ValidatorTrustLevel,
)
from ugence_code_governance.workflow.records import (
    revision_id_for,
    workflow_id_for,
)


from ugence_code_governance import (  # noqa: E402
    AuthorizedActor,
    ClaimInput,
    ClaimStatus,
    ClaimType,
    CodeGovernanceService,
    DecisionInput,
    EvidenceRecord,
    MergeMethod,
    RiskTier,
    ValidatorTrustLevel,
)
from ugence_code_governance.workflow.records import (  # noqa: E402
    revision_id_for,
    workflow_id_for,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_payload(
    *,
    action: str = "opened",
    owner: str = "acme",
    name: str = "widgets",
    number: int = 42,
    base_sha: str = "base-sha-1",
    head_sha: str = "head-sha-1",
    base_ref: str = "main",
    head_ref: str = "feature/x",
    installation: str = "install-1",
) -> dict:
    return {
        "action": action,
        "repository": {"name": name, "owner": {"login": owner}},
        "pull_request": {
            "number": number,
            "base": {"ref": base_ref, "sha": base_sha},
            "head": {"ref": head_ref, "sha": head_sha},
        },
        "installation": {"id": installation},
    }


def make_evidence(
    change,
    claim_type: ClaimType,
    *,
    validator_id: str = "ci-runner",
    validator_version: str = "1.2.3",
    head_sha: str | None = None,
    trust: ValidatorTrustLevel = ValidatorTrustLevel.TRUSTED,
    result: str = "pass",
) -> EvidenceRecord:
    return EvidenceRecord.create(
        tenant_id=change.tenant_id,
        repository=change.repository,
        pull_request_number=change.pull_request_number,
        base_sha=change.base_sha,
        head_sha=head_sha or change.head_sha,
        evidence_type=claim_type.value,
        source_id=f"{claim_type.value}-run",
        source_kind="ci",
        validator_id=validator_id,
        validator_version=validator_version,
        captured_at=T0,
        normalized_payload={"result": result, "type": claim_type.value},
        validator_trust_level=trust,
    )


def revision_of(change) -> str:
    wid = workflow_id_for(change.tenant_id, change.repository, change.pull_request_number)
    return revision_id_for(wid, change.base_sha, change.head_sha)


def claim_inputs_for(change, claim_types, status: ClaimStatus = ClaimStatus.SATISFIED):
    return tuple(
        ClaimInput(
            claim_type=ct,
            status=status,
            evidence=(make_evidence(change, ct),),
        )
        for ct in claim_types
    )


LOW_CLAIMS = (ClaimType.BUILD, ClaimType.UNIT_TEST, ClaimType.STATIC_ANALYSIS)


def drive_to_shadow_complete(
    svc: CodeGovernanceService,
    change,
    *,
    outcome: str = "APPROVE",
    merge_method: MergeMethod = MergeMethod.SQUASH,
    claim_status: ClaimStatus = ClaimStatus.SATISFIED,
):
    """Drive one governed change all the way to SHADOW_COMPLETE (LOW tier)."""
    rid = revision_of(change)
    for ct in LOW_CLAIMS:
        svc.record_evidence(change.tenant_id, rid, make_evidence(change, ct))
    svc.build_claim_manifest(
        change.tenant_id, rid, risk_tier=RiskTier.LOW,
        claim_inputs=claim_inputs_for(change, LOW_CLAIMS, claim_status), captured_at=T0)
    svc.evaluate_claim_requirements(change.tenant_id, rid, at=T0)
    svc.evaluate_assertions(change.tenant_id, rid, at=T0)
    svc.create_recommendation(change.tenant_id, rid, created_at=T0)
    actor = AuthorizedActor(
        actor_id="user:approver", authority_id="role:code-approver",
        decision_scope="merge_pull_request")
    svc.record_authorized_decision(
        change.tenant_id, rid, actor=actor, decision=DecisionInput(outcome=outcome), at=T0)
    if outcome.upper() in ("DENY", "REJECT"):
        return rid
    svc.prepare_exact_action(change.tenant_id, rid, merge_method=merge_method, at=T0)
    svc.evaluate_action_shadow(change.tenant_id, rid, at=T0)
    return rid


