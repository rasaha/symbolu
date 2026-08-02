"""Deterministic, offline Code Governance MVP 1A shadow demonstration.

Uses ONLY fixtures — no live GitHub credentials, no network, no execution. Run:

    PYTHONPATH=... python products/code-governance/examples/shadow_demo.py

The demo proves the full shadow governance path and then shows head-SHA
invalidation making prior evidence and authorization stale.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

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
from ugence_code_governance.workflow.records import revision_id_for, workflow_id_for

# Caller-supplied deterministic time (no hidden current-time reads).
CLOCK = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
TENANT = "tenant-acme"

MANDATORY = (ClaimType.BUILD, ClaimType.UNIT_TEST, ClaimType.STATIC_ANALYSIS)


def _payload(head_sha: str, action: str = "opened") -> dict:
    return {
        "action": action,
        "repository": {"name": "billing", "owner": {"login": "acme"}},
        "pull_request": {
            "number": 128,
            "base": {"ref": "main", "sha": "base-000"},
            "head": {"ref": "feature/refund", "sha": head_sha},
        },
        "installation": {"id": "inst-acme"},
    }


def _evidence(change, claim_type: ClaimType, validator="ci-runner", version="4.1.0") -> EvidenceRecord:
    return EvidenceRecord.create(
        tenant_id=change.tenant_id, repository=change.repository,
        pull_request_number=change.pull_request_number, base_sha=change.base_sha,
        head_sha=change.head_sha, evidence_type=claim_type.value,
        source_id=f"{claim_type.value}-job", source_kind="ci",
        validator_id=validator, validator_version=version, captured_at=CLOCK,
        normalized_payload={"result": "pass", "claim": claim_type.value},
        validator_trust_level=ValidatorTrustLevel.TRUSTED)


def _revision(change) -> str:
    wid = workflow_id_for(change.tenant_id, change.repository, change.pull_request_number)
    return revision_id_for(wid, change.base_sha, change.head_sha)


def _p(step: str, detail: str = "") -> None:
    print(f"  [{step}] {detail}")


def run(verbose: bool = True) -> dict:
    out: dict = {}
    svc = CodeGovernanceService()

    if verbose:
        print("== Code Governance MVP 1A — offline shadow demonstration ==")

    # 1. ingest a GitHub PR event
    change = svc.ingest_change_event(_payload("head-AAA"), tenant_id=TENANT,
                                     captured_at=CLOCK, delivery_id="delivery-1")
    rid = _revision(change)
    if verbose:
        _p("1-2 ingest+identity", f"{change.repository}#{change.pull_request_number} "
                                  f"head={change.head_sha} fp={change.fingerprint[:12]}")

    # 3-5. record evidence, but hold back STATIC_ANALYSIS (one mandatory missing)
    for ct in (ClaimType.BUILD, ClaimType.UNIT_TEST):
        svc.record_evidence(TENANT, rid, _evidence(change, ct))
    partial_inputs = tuple(
        ClaimInput(claim_type=ct, status=ClaimStatus.SATISFIED, evidence=(_evidence(change, ct),))
        for ct in (ClaimType.BUILD, ClaimType.UNIT_TEST))
    svc.build_claim_manifest(TENANT, rid, risk_tier=RiskTier.MEDIUM,
                             claim_inputs=partial_inputs, captured_at=CLOCK)
    # 5-6. one mandatory claim missing -> fail closed as incomplete
    evaluation = svc.evaluate_claim_requirements(TENANT, rid, at=CLOCK)
    if verbose:
        _p("3-6 partial claims", f"proceed={evaluation.proceed} "
                                 f"missing={[c.value for c in evaluation.missing_required_claims]} "
                                 f"state={svc.get_workflow(TENANT, rid).state.value}")
    out["partial_proceed"] = evaluation.proceed
    out["partial_state"] = svc.get_workflow(TENANT, rid).state.value

    # 7. add the missing evidence — a NEW revision-scoped run (same head, re-evaluated).
    #    (In this demo we re-ingest the same head to get a fresh run for the complete pass.)
    svc2 = CodeGovernanceService()
    change = svc2.ingest_change_event(_payload("head-AAA"), tenant_id=TENANT,
                                      captured_at=CLOCK, delivery_id="delivery-1")
    rid = _revision(change)
    for ct in MANDATORY:
        svc2.record_evidence(TENANT, rid, _evidence(change, ct))
    # MEDIUM tier needs more mandatory families; supply them all.
    medium = MANDATORY + (ClaimType.DIFFERENTIAL_TEST, ClaimType.DEPENDENCY_DELTA,
                          ClaimType.PUBLIC_API_DELTA, ClaimType.PERFORMANCE_BUDGET)
    complete_inputs = tuple(
        ClaimInput(claim_type=ct, status=ClaimStatus.SATISFIED, evidence=(_evidence(change, ct),))
        for ct in medium)
    svc = svc2
    # 8. evaluate claims (now complete)
    svc.build_claim_manifest(TENANT, rid, risk_tier=RiskTier.MEDIUM,
                             claim_inputs=complete_inputs, captured_at=CLOCK)
    evaluation = svc.evaluate_claim_requirements(TENANT, rid, at=CLOCK)
    if verbose:
        _p("7-8 complete claims", f"proceed={evaluation.proceed} "
                                  f"state={svc.get_workflow(TENANT, rid).state.value}")
    out["complete_proceed"] = evaluation.proceed

    # 9. run TAP
    tap = svc.evaluate_assertions(TENANT, rid, at=CLOCK)
    if verbose:
        _p("9 TAP", f"{len(tap.results)} per-claim assertion results "
                    f"(coverage[0]={tap.results[0].coverage})")

    # 10. create an advisory recommendation
    rec = svc.create_recommendation(TENANT, rid, created_at=CLOCK)
    if verbose:
        _p("10 recommendation", f"{rec.disposition.value} (binding={rec.is_binding})")

    # 11. require explicit authorized-actor decision input
    actor = AuthorizedActor(actor_id="user:sre-lead", authority_id="role:merge-approver",
                            decision_scope="merge_pull_request")
    # 12. create DecisionRecord (through Decision Authority public API)
    decision = svc.record_authorized_decision(
        TENANT, rid, actor=actor, decision=DecisionInput(outcome="APPROVE"), at=CLOCK)
    if verbose:
        _p("11-12 decision", f"{type(decision).__name__} {decision.decision_id[:14]} "
                             f"outcome={decision.outcome.value} by={decision.decided_by}")

    # 13-14. bind CER (cer.v1) + prepare exact merge action
    action = svc.prepare_exact_action(TENANT, rid, merge_method=MergeMethod.SQUASH, at=CLOCK)
    if verbose:
        _p("13 CER", f"cer_id={action.cer_id[:14]} content_hash={action.cer_content_hash[:12]}")
        _p("14 prepared action", f"fp={action.fingerprint[:12]} method={action.merge_method.value}")

    # 15. invoke ActionGate in shadow mode
    shadow = svc.evaluate_action_shadow(TENANT, rid, at=CLOCK)
    if verbose:
        _p("15 ActionGate SHADOW", f"outcome={shadow.outcome} mode={shadow.mode.value} "
                                   f"(would_authorize={shadow.would_authorize})")

    # 16. reconstruct the entire chain
    result = svc.reconstruct_chain(TENANT, rid)
    if verbose:
        _p("16 reconstruction", f"state={result.state.value} "
                                f"verified_links={len(result.verified_links)}")
    out["reconstruction"] = result.state.value
    out["final_state"] = svc.get_workflow(TENANT, rid).state.value

    # 17. report execution disabled
    if verbose:
        _p("17 execution", f"execution_status()={svc.execution_status()}")
    out["execution_status"] = svc.execution_status()

    # 18. ingest a changed head SHA (synchronize)
    change_b = svc.ingest_change_event(_payload("head-BBB", action="synchronize"),
                                       tenant_id=TENANT, captured_at=CLOCK, delivery_id="delivery-2")
    rid_b = _revision(change_b)
    # 19. demonstrate prior evidence + authorization becoming stale
    old_evidence = _evidence(change, ClaimType.BUILD)  # bound to head-AAA
    stale = old_evidence.is_stale_for(change_b.head_sha)
    old_chain = svc.reconstruct_chain(TENANT, rid)  # old-head chain now stale
    if verbose:
        _p("18-19 head invalidation",
           f"new_rev={rid_b[:12]} old_evidence_stale={stale} "
           f"old_chain={old_chain.state.value}")
    out["new_revision_differs"] = rid != rid_b
    out["old_evidence_stale"] = stale
    out["old_chain_state"] = old_chain.state.value

    if verbose:
        print("== shadow demonstration complete — execution remains DISABLED ==")
    return out


if __name__ == "__main__":
    run()
