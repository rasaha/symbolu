"""Deterministic offline MVP 1E demonstration: the deployable pilot operator.

Uses fake read-only transports + supplied snapshots. No network, no execution, no
GitHub writes, no reservation, no consumption ledger, no external database. Shows
config validation, security preflight, lifecycle, evaluation, reviewer queue,
feedback, metrics, pause-blocks-collection, restart + recovery (no external call),
explicit resume, kill switch, closeout, offline-verified report, and that a unique
fake credential is persisted nowhere.

Run:
    PYTHONPATH=products/code-governance/src:packages/capabilities/action-clearance/src:... \
        python products/code-governance/examples/pilot_operator_demo.py
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

from ugence_action_clearance import ClearanceStatus, SignalTrustLevel, SignalType
from ugence_code_governance import (
    AdapterRegistryEntry, AdapterRegistryProjection, AuthorizedActor, ClaimInput, ClaimStatus,
    ClaimType, CodeGovernanceClearanceProfile, CodeGovernanceService, DecisionInput, EvidenceRecord,
    GitHubReadOnlyAdapter, IdentitySnapshotAdapter, MergeMethod, PersistenceMode,
    RepositoryClassification, RiskTier, ValidatorTrustLevel,
)
from ugence_code_governance.adapters import FakeReadOnlyTransport, RawResponse, TransportPolicy
from ugence_code_governance.pilot_operator import (
    CredentialReference, PilotDeploymentConfig, PilotLifecycleStatus, PilotStopThresholds,
    ResolverKind, open_pilot_operator, recover_pilot, scan_for_credential,
)
from ugence_code_governance.workflow.records import revision_id_for, workflow_id_for

T0 = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
EVAL = T0 + timedelta(minutes=10)
TENANT = "tenant-acme"
REPO = "acme/billing"
NUM = 77
HOST = "api.github.com"
LOW = (ClaimType.BUILD, ClaimType.UNIT_TEST, ClaimType.STATIC_ANALYSIS)
REQUIRED = (SignalType.ARTIFACT_IDENTITY, SignalType.ACTOR_STATUS)
ACTOR = AuthorizedActor(actor_id="user:sre", authority_id="role:merge-approver",
                        decision_scope="merge_pull_request")
FAKE_CREDENTIAL = "SECRET-OPERATOR-TOKEN-9Z"


def _payload(head):
    return {"action": "opened", "repository": {"name": "billing", "owner": {"login": "acme"}},
            "pull_request": {"number": NUM, "base": {"ref": "main", "sha": "base-0"},
                             "head": {"ref": "feat", "sha": head}}, "installation": {"id": "i"}}


def _ev(c, ct):
    return EvidenceRecord.create(tenant_id=c.tenant_id, repository=c.repository,
        pull_request_number=c.pull_request_number, base_sha=c.base_sha, head_sha=c.head_sha,
        evidence_type=ct.value, source_id=ct.value, source_kind="ci", validator_id="ci",
        validator_version="1.0", captured_at=T0, normalized_payload={"r": "pass", "t": ct.value},
        validator_trust_level=ValidatorTrustLevel.TRUSTED)


def _profile():
    return CodeGovernanceClearanceProfile(profile_id="prof", profile_version="v1", tenant_id=TENANT,
        repository_classification=RepositoryClassification.MEDIUM, required_signal_types=REQUIRED,
        trust_required_signal_types=(SignalType.ARTIFACT_IDENTITY,),
        minimum_trust_levels={SignalType.ARTIFACT_IDENTITY: SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION},
        maximum_shadow_clearance_lifetime_s=3600, incident_response=ClearanceStatus.HOLD)


def _drive(svc, head):
    c = svc.ingest_change_event(_payload(head), tenant_id=TENANT, captured_at=T0, delivery_id=head)
    rid = revision_id_for(workflow_id_for(TENANT, c.repository, NUM), c.base_sha, c.head_sha)
    for ct in LOW:
        svc.record_evidence(TENANT, rid, _ev(c, ct))
    svc.build_claim_manifest(TENANT, rid, risk_tier=RiskTier.LOW,
        claim_inputs=tuple(ClaimInput(claim_type=ct, status=ClaimStatus.SATISFIED, evidence=(_ev(c, ct),)) for ct in LOW),
        captured_at=T0)
    svc.evaluate_claim_requirements(TENANT, rid, at=T0)
    svc.evaluate_assertions(TENANT, rid, at=T0)
    svc.create_recommendation(TENANT, rid, created_at=T0)
    svc.record_authorized_decision(TENANT, rid, actor=ACTOR, decision=DecisionInput(outcome="APPROVE"), at=T0)
    svc.prepare_exact_action(TENANT, rid, merge_method=MergeMethod.SQUASH, at=T0)
    svc.evaluate_action_shadow(TENANT, rid, at=T0, finalize=False)
    return rid


def _registry():
    def e(aid, kind, st):
        return AdapterRegistryEntry(adapter_id=aid, adapter_version="1.0.0", source_id=kind,
            source_kind=kind, approved_signal_types=(st,),
            max_trust_level=SignalTrustLevel.LEVEL_2_AUTHENTICATED_ENVELOPE,
            approved_adapter_versions=("1.0.0",), approved_hosts=(HOST,), approved_path_prefixes=("/repos/",))
    return AdapterRegistryProjection("reg", "reg-v1", TENANT,
        {"cg.github_readonly": e("cg.github_readonly", "github", "ARTIFACT_IDENTITY"),
         "cg.identity_snapshot": e("cg.identity_snapshot", "identity", "ACTOR_STATUS")})


def _gh(ctx, resolver=None):
    repo, num, head = ctx["repository"], ctx["pull_request_number"], ctx["head_sha"]
    pr = json.dumps({"number": num, "state": "open", "draft": False,
                     "base": {"sha": ctx["base_sha"], "repo": {"full_name": repo}},
                     "head": {"sha": head}}).encode()
    checks = json.dumps({"check_runs": [{"status": "completed", "conclusion": "success"}]}).encode()
    pol = TransportPolicy(allowed_hosts=(HOST,), allowed_path_prefixes=("/repos/",))
    tp = FakeReadOnlyTransport(pol, {
        ("GET", f"https://{HOST}/repos/{repo}/pulls/{num}"): RawResponse(200, "application/json", pr),
        ("GET", f"https://{HOST}/repos/{repo}/commits/{head}/check-runs"): RawResponse(200, "application/json", checks)},
        credential_resolver=resolver)
    return GitHubReadOnlyAdapter(tp, registry_version="reg-v1")


def _identity():
    snap = {"schema_version": "code_governance.identity_snapshot.v1", "tenant_id": TENANT,
            "subject_ref": REPO, "source_id": "okta", "source_kind": "identity", "adapter_version": "1.0.0",
            "captured_at": "2026-08-02T00:00:00Z", "valid_until": "2026-12-31T00:00:00Z",
            "facts": {"account_active": True}, "policy_ref": "p"}
    return IdentitySnapshotAdapter(snap)


def _config(store_path):
    return PilotDeploymentConfig(
        config_id="c1", config_version="v1", pilot_id="pilot-1", tenant_id=TENANT,
        allowed_repositories=(REPO,), allowed_branches=("feat", "main"), durable_store_path=store_path,
        github_adapter_registry_ref="reg-v1",
        credential_references=(CredentialReference("gh", ResolverKind.ENVIRONMENT, HOST,
                                                   environment_variable_name="GH_TOKEN",
                                                   required_scopes=("metadata:read",)),),
        approved_snapshot_adapters=("cg.identity_snapshot",), maximum_evaluations=25,
        pilot_end_at="2026-12-31T00:00:00Z", stop_thresholds=PilotStopThresholds())


def run(verbose=True):
    out = {}
    path = os.path.join(tempfile.mkdtemp(prefix="cg-operator-demo-"), "gov.db")

    def say(m):
        if verbose:
            print(m)

    say("== Code Governance MVP 1E — deployable pilot operator demonstration ==")
    resolver = lambda ref: {"Authorization": f"Bearer {FAKE_CREDENTIAL}"}  # noqa: E731

    # 1-5. config, preflight, operator, lifecycle.
    svc = CodeGovernanceService(store_path=path)
    rid1 = _drive(svc, "head-AAA")
    ctx1 = svc.pilot_change_context(TENANT, rid1)
    cfg = svc.durable_store and _config(path)
    from ugence_code_governance.pilot_operator import validate_pilot_config
    validate_pilot_config(cfg)
    op = open_pilot_operator(cfg, service=svc, registry=_registry(), profile=_profile(),
                             credential_resolver=resolver)
    pf = op.preflight()
    say(f"  [1-3 config+preflight] outcome={pf.outcome.value} perm={pf.permission_verification.value}")
    op.start(EVAL)
    say(f"  [4-5 lifecycle] status={op.status.value}")

    # 6-11. evaluate + reviewer queue + feedback + metrics.
    rec = op.run_once(rid1, [_gh(ctx1, resolver), _identity()], collection_time=EVAL,
                      evaluation_time=EVAL, actor_ref="user:sre")
    say(f"  [6-8 evaluate] status={rec.clearance_status} human={rec.human_intervention_required} "
        f"exec={rec.execution_status}")
    say(f"  [9-11 metrics] queue={len(op.review_queue())} evals={op.metrics().evaluations_completed}")
    out["clear"] = rec.clearance_status

    # 12-13. pause blocks collection.
    op.pause(EVAL)
    blocked = False
    try:
        op.run_once(rid1, [_gh(ctx1), _identity()], collection_time=EVAL, evaluation_time=EVAL)
    except Exception:
        blocked = True
    say(f"  [12-13 pause] collection blocked while paused: {blocked}")
    out["paused_blocked"] = blocked
    svc.close()  # 14. process shutdown

    # 14-17. restart, recover (no external call), explicit resume, evaluate again.
    svc2 = CodeGovernanceService(store_path=path)
    recovery = recover_pilot(svc2.durable_store, cfg)
    say(f"  [14-15 restart+recover] status={recovery.status.value} "
        f"requires_action={recovery.requires_explicit_action}")
    op2 = open_pilot_operator(cfg, service=svc2, registry=_registry(), profile=_profile(),
                              credential_resolver=resolver)
    op2.confirm_recovery(recovery, EVAL)  # 16. explicit resume
    rid2 = _drive(svc2, "head-BBB")
    ctx2 = svc2.pilot_change_context(TENANT, rid2)
    # recovered status was PAUSED; resume to ACTIVE before evaluating.
    if op2.status is PilotLifecycleStatus.PAUSED:
        op2.resume(EVAL)
    rec2 = op2.run_once(rid2, [_gh(ctx2, resolver), _identity()], collection_time=EVAL,
                        evaluation_time=EVAL, actor_ref="user:sre")
    say(f"  [16-17 resume+evaluate] status={rec2.clearance_status}")
    out["recovery"] = recovery.status.value

    # 18-19. kill switch blocks new collection.
    op2.activate_kill_switch(EVAL)
    killed_blocked = False
    try:
        op2.run_once(rid2, [_gh(ctx2), _identity()], collection_time=EVAL, evaluation_time=EVAL)
    except Exception:
        killed_blocked = True
    say(f"  [18-19 kill switch] new collection blocked: {killed_blocked}")
    out["kill_blocked"] = killed_blocked
    op2.clear_kill_switch(EVAL)

    # 20-21. closeout + offline-verified report.
    summary = op2.closeout(EVAL)
    say(f"  [20-21 closeout] status={summary['final_lifecycle_status']} "
        f"report_verified={summary['report_verified']} exec={summary['execution_status']}")
    out["report_verified"] = summary["report_verified"]

    # 22-23. credential scan across every persisted artifact.
    leaked = []
    for wf in (f"op:pilot-1", f"pilot:pilot-1"):
        for env in svc2.durable_store.list_for_workflow(TENANT, wf):
            leaked += scan_for_credential(FAKE_CREDENTIAL, env.canonical_payload)
    leaked += scan_for_credential(FAKE_CREDENTIAL, summary)
    for e in op2.logger.events:
        leaked += scan_for_credential(FAKE_CREDENTIAL, e)
    say(f"  [22-23 credentials] fake credential found anywhere: {bool(leaked)}")
    out["credential_leaked"] = bool(leaked)

    # 24. boundaries.
    say("  [24 bounds] no execution · no GitHub writes · no reservation · "
        "no consumption ledger · no external database")
    say("== demonstration complete — execution remains DISABLED ==")
    out["exec"] = svc2.execution_status()
    svc2.close()
    return out


if __name__ == "__main__":
    run()
