"""Deterministic offline MVP 1B demonstration: Action Clearance shadow integration.

No execution, no reservation, no production persistence, no external calls. Run:

    PYTHONPATH=products/code-governance/src:packages/capabilities/action-clearance/src:... \
        python products/code-governance/examples/clearance_shadow_demo.py
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ugence_code_governance import (
    AuthorizedActor, ClaimInput, ClaimStatus, ClaimType, CodeGovernanceClearanceProfile,
    CodeGovernanceOperationalSnapshot, CodeGovernanceService, DecisionInput, EvidenceRecord,
    InterventionRoutingPolicy, MergeMethod, RepositoryClassification, RiskTier,
    SignalSourceEntry, TrustedSignalSourceProjection, ValidatorTrustLevel,
)
from ugence_code_governance.clearance.adapter import ActionClearanceShadowAdapter
from ugence_code_governance.clearance.signal_adapter import build_trusted_signals
from ugence_code_governance.workflow.records import revision_id_for, workflow_id_for
from ugence_action_clearance import (
    ClearanceStatus, SignalTrustLevel, SignalType, evaluate_clearance,
)

T0 = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
EVAL = T0 + timedelta(minutes=10)
TENANT = "tenant-acme"
LOW = (ClaimType.BUILD, ClaimType.UNIT_TEST, ClaimType.STATIC_ANALYSIS)
REQUIRED = (SignalType.AUTHORIZATION_VALIDITY, SignalType.ACTOR_STATUS, SignalType.ARTIFACT_IDENTITY)
ACTOR = AuthorizedActor(actor_id="user:sre", authority_id="role:merge-approver",
                        decision_scope="merge_pull_request")


def _payload(head):
    return {"action": "opened", "repository": {"name": "billing", "owner": {"login": "acme"}},
            "pull_request": {"number": 77, "base": {"ref": "main", "sha": "base-0"},
                             "head": {"ref": "feat", "sha": head}}, "installation": {"id": "i"}}


def _ev(c, ct):
    return EvidenceRecord.create(tenant_id=c.tenant_id, repository=c.repository,
        pull_request_number=c.pull_request_number, base_sha=c.base_sha, head_sha=c.head_sha,
        evidence_type=ct.value, source_id=ct.value, source_kind="ci", validator_id="ci",
        validator_version="1.0", captured_at=T0, normalized_payload={"r": "pass", "t": ct.value},
        validator_trust_level=ValidatorTrustLevel.TRUSTED)


def _proj():
    return TrustedSignalSourceProjection(projection_id="proj", projection_version="v1", tenant_id=TENANT,
        entries={st: SignalSourceEntry(source_id=f"s-{st.value}", source_kind="approved", adapter_id="ad",
            adapter_version="1.0.0", ingestion_boundary="b", provenance_ref="p",
            max_trust_level=SignalTrustLevel.LEVEL_2_AUTHENTICATED_ENVELOPE,
            approved_adapter_versions=("1.0.0",)) for st in SignalType})


def _profile(classification=RepositoryClassification.MEDIUM, incident_escalate=False):
    return CodeGovernanceClearanceProfile(profile_id="prof", profile_version="v1", tenant_id=TENANT,
        repository_classification=classification, required_signal_types=REQUIRED,
        trust_required_signal_types=(SignalType.ARTIFACT_IDENTITY,),
        minimum_trust_levels={SignalType.ARTIFACT_IDENTITY: SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION},
        maximum_shadow_clearance_lifetime_s=3600,
        incident_response=ClearanceStatus.ESCALATE if incident_escalate else ClearanceStatus.HOLD)


def _snap(action, **ov):
    b = dict(authorization_validity="VALID", actor_state="ACTIVE",
             artifact_action_fingerprint=action.fingerprint, artifact_target_ref=action.repository)
    b.update(ov)
    return CodeGovernanceOperationalSnapshot(captured_at=T0, valid_until=T0 + timedelta(hours=2), **b)


def _drive(svc, head):
    c = svc.ingest_change_event(_payload(head), tenant_id=TENANT, captured_at=T0, delivery_id=head)
    rid = revision_id_for(workflow_id_for(TENANT, c.repository, 77), c.base_sha, c.head_sha)
    for ct in LOW:
        svc.record_evidence(TENANT, rid, _ev(c, ct))
    svc.build_claim_manifest(TENANT, rid, risk_tier=RiskTier.LOW,
        claim_inputs=tuple(ClaimInput(claim_type=ct, status=ClaimStatus.SATISFIED, evidence=(_ev(c, ct),)) for ct in LOW),
        captured_at=T0)
    svc.evaluate_claim_requirements(TENANT, rid, at=T0)
    svc.evaluate_assertions(TENANT, rid, at=T0)
    svc.create_recommendation(TENANT, rid, created_at=T0)
    svc.record_authorized_decision(TENANT, rid, actor=ACTOR, decision=DecisionInput(outcome="APPROVE"), at=T0)
    action = svc.prepare_exact_action(TENANT, rid, merge_method=MergeMethod.SQUASH, at=T0)
    shadow = svc.evaluate_action_shadow(TENANT, rid, at=T0, finalize=False)
    return c, rid, action, shadow


def _clear(svc, rid, action, *, snap=None, profile=None, sensitive=False):
    svc.record_operational_snapshot(TENANT, rid, snap or _snap(action), projection=_proj(),
                                    profile=profile or _profile(), at=EVAL)
    rec = svc.evaluate_action_clearance_shadow(TENANT, rid, evaluation_time=EVAL)
    hia = svc.assess_human_intervention(TENANT, rid, at=EVAL, routing=InterventionRoutingPolicy(),
                                        sensitive=sensitive)
    return rec, hia


def run(verbose=True):
    out = {}
    if verbose:
        print("== Code Governance MVP 1B — Action Clearance shadow demonstration ==")

    def show(step, rec, hia):
        if verbose:
            print(f"  [{step}] clearance={rec.clearance_status or rec.stage_state.value:>10} "
                  f"human={hia.required!s:>5} route={list(hia.intervention_types)} "
                  f"authorities={list(hia.required_authorities)}")

    # 1-6. CLEAR + no human intervention + execution disabled
    svc = CodeGovernanceService()
    c, rid, action, shadow = _drive(svc, "head-AAA")
    rec, hia = _clear(svc, rid, action)
    show("1-6 CLEAR", rec, hia)
    out["clear"] = rec.clearance_status
    out["clear_human"] = hia.required
    out["exec"] = svc.execution_status()

    # 7-9. temporary change freeze -> HOLD, wait/refresh, no automatic human
    svc = CodeGovernanceService(); c, rid, action, shadow = _drive(svc, "head-AAA")
    rec, hia = _clear(svc, rid, action, snap=_snap(action, change_freeze_active=True))
    show("7-9 HOLD/freeze", rec, hia)
    out["hold"] = rec.clearance_status; out["hold_human"] = hia.required

    # 10-12. exact-action mismatch -> BLOCK, reauthorize/change, not generic human review
    svc = CodeGovernanceService(); c, rid, action, shadow = _drive(svc, "head-AAA")
    rec, hia = _clear(svc, rid, action, snap=_snap(action, artifact_action_fingerprint="WRONG-FP"))
    show("10-12 BLOCK/mismatch", rec, hia)
    out["block"] = rec.clearance_status; out["block_human"] = hia.required

    # 13-15. active incident on a CRITICAL service -> ESCALATE, route to human authority
    svc = CodeGovernanceService(); c, rid, action, shadow = _drive(svc, "head-AAA")
    rec, hia = _clear(svc, rid, action, snap=_snap(action, incident_active=True),
                      profile=_profile(RepositoryClassification.CRITICAL, incident_escalate=True))
    show("13-15 ESCALATE/incident", rec, hia)
    out["escalate"] = rec.clearance_status; out["escalate_human"] = hia.required
    out["escalate_authorities"] = list(hia.required_authorities)

    # 16-17. change head_sha -> previous clearance + assessment become stale
    svc = CodeGovernanceService()
    c_a, rid_a, action_a, shadow_a = _drive(svc, "head-AAA")
    rec_a, hia_a = _clear(svc, rid_a, action_a)
    _drive(svc, "head-BBB")  # new head supersedes the lineage
    stale = svc.reconstruct_chain(TENANT, rid_a)
    if verbose:
        print(f"  [16-17 head change] old chain reconstructs: {stale.state.value} (historical, stale)")
    out["old_chain_stale"] = stale.state.value

    # 18-19. replay identical clearance inputs -> identical fingerprints
    svc = CodeGovernanceService(); c, rid, action, shadow = _drive(svc, "head-AAA")
    adapter = ActionClearanceShadowAdapter()
    def build_request():
        bundle = build_trusted_signals(_snap(action), _proj(), tenant_id=TENANT,
            subject_ref=action.repository, authorization_ref=shadow.result_fingerprint,
            action_fingerprint=action.fingerprint, required_signal_types=REQUIRED)
        authz = adapter.authorization_context(shadow, action, actor_ref="user:sre",
                                              authorization_issued_at=action.expiry)
        ident = adapter.action_identity(action, actor_ref="user:sre")
        ctx = adapter.policy_context(_profile())
        return adapter.build_request(request_id="replay", tenant_id=TENANT, evaluation_time=EVAL,
                                     authorization=authz, action=ident, signals=bundle, policy=ctx)
    r1 = evaluate_clearance(build_request(), _profile().to_clearance_policy())
    r2 = evaluate_clearance(build_request(), _profile().to_clearance_policy())
    out["replay_identical"] = r1.result_fingerprint == r2.result_fingerprint
    if verbose:
        print(f"  [18-19 replay] identical result_fingerprint={out['replay_identical']} "
              f"({r1.result_id[:20]}…)")

    # 20. report boundaries
    if verbose:
        print("  [20] no execution · no reservation · no production persistence · no external calls")
        print("== demonstration complete — execution remains DISABLED ==")
    out["reservation"] = "NONE"; out["persistence"] = "SHADOW_REFERENCE_ONLY"
    return out


if __name__ == "__main__":
    run()
