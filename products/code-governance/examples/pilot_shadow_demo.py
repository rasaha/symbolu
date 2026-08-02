"""Deterministic offline MVP 1D demonstration: read-only enterprise signal pilot.

Uses fake GET-only transports and supplied snapshots — no network, no execution,
no reservation, no GitHub writes, no external database. Shows signal collection,
clearance evaluation, human-intervention routing, durable pilot persistence,
reviewer feedback, metrics, an offline-verifiable pilot report, source timeout,
stale GitHub head, conflicting signals, and that credentials are never persisted.

Run:

    PYTHONPATH=products/code-governance/src:packages/capabilities/action-clearance/src:... \
        python products/code-governance/examples/pilot_shadow_demo.py
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from ugence_action_clearance import ClearanceStatus, SignalTrustLevel, SignalType
from ugence_code_governance import (
    AdapterRegistryEntry, AdapterRegistryProjection, AuthorizedActor, ChangeWindowSnapshotAdapter,
    ClaimInput, ClaimStatus, ClaimType, CodeGovernanceClearanceProfile,
    CodeGovernanceService, ControlStatusSnapshotAdapter, DecisionInput, EvidenceRecord,
    FeedbackAgreement, GitHubReadOnlyAdapter, IdentitySnapshotAdapter, IncidentSnapshotAdapter,
    MergeMethod, ObservedResolution, PersistenceMode, PilotReviewerFeedback, PilotThresholds,
    RepositoryClassification, RetryPolicy, RiskTier, ShadowPilotConfig,
    ShadowPilotRunner, TargetHealthSnapshotAdapter, TransportPolicy, ValidatorTrustLevel,
    verify_shadow_pilot_report,
)
from ugence_code_governance.adapters import FakeReadOnlyTransport, RawResponse
from ugence_code_governance.workflow.records import revision_id_for, workflow_id_for

T0 = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
EVAL = T0 + timedelta(minutes=10)
TENANT = "tenant-acme"
REPO = "acme/billing"
NUM = 77
HOST = "api.github.com"
LOW = (ClaimType.BUILD, ClaimType.UNIT_TEST, ClaimType.STATIC_ANALYSIS)
ACTOR = AuthorizedActor(actor_id="user:sre", authority_id="role:merge-approver",
                        decision_scope="merge_pull_request")
REQUIRED = (SignalType.ARTIFACT_IDENTITY, SignalType.ACTOR_STATUS)


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


def _profile(classification=RepositoryClassification.MEDIUM, incident_escalate=False):
    return CodeGovernanceClearanceProfile(profile_id="prof", profile_version="v1", tenant_id=TENANT,
        repository_classification=classification, required_signal_types=REQUIRED,
        trust_required_signal_types=(SignalType.ARTIFACT_IDENTITY,),
        minimum_trust_levels={SignalType.ARTIFACT_IDENTITY: SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION},
        maximum_shadow_clearance_lifetime_s=3600,
        incident_response=ClearanceStatus.ESCALATE if incident_escalate else ClearanceStatus.HOLD)


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
    return c, rid


def _registry():
    def e(aid, kind, st):
        return AdapterRegistryEntry(adapter_id=aid, adapter_version="1.0.0", source_id=kind,
            source_kind=kind, approved_signal_types=(st,),
            max_trust_level=SignalTrustLevel.LEVEL_2_AUTHENTICATED_ENVELOPE,
            approved_adapter_versions=("1.0.0",), approved_hosts=(HOST,),
            approved_path_prefixes=("/repos/",))
    return AdapterRegistryProjection(registry_id="reg", registry_version="reg-v1", tenant_id=TENANT,
        entries={"cg.github_readonly": e("cg.github_readonly", "github", "ARTIFACT_IDENTITY"),
                 "cg.identity_snapshot": e("cg.identity_snapshot", "identity", "ACTOR_STATUS"),
                 "cg.change_window_snapshot": e("cg.change_window_snapshot", "change_window", "CHANGE_FREEZE"),
                 "cg.incident_snapshot": e("cg.incident_snapshot", "incident", "ACTIVE_INCIDENT")})


def _gh_transport(ctx, *, head=None, pr_status="open", resolver=None):
    repo, num = ctx["repository"], ctx["pull_request_number"]
    h = head or ctx["head_sha"]
    pr = json.dumps({"number": num, "state": pr_status, "draft": False,
                     "base": {"sha": ctx["base_sha"], "repo": {"full_name": repo}},
                     "head": {"sha": h}}).encode()
    checks = json.dumps({"check_runs": [{"status": "completed", "conclusion": "success"}]}).encode()
    pol = TransportPolicy(allowed_hosts=(HOST,), allowed_path_prefixes=("/repos/",))
    return FakeReadOnlyTransport(pol, {
        ("GET", f"https://{HOST}/repos/{repo}/pulls/{num}"): RawResponse(200, "application/json", pr),
        ("GET", f"https://{HOST}/repos/{repo}/commits/{ctx['head_sha']}/check-runs"):
            RawResponse(200, "application/json", checks)}, credential_resolver=resolver)


def _snap(kind, facts, sid):
    return {"schema_version": f"code_governance.{kind}_snapshot.v1", "tenant_id": TENANT,
            "subject_ref": REPO, "source_id": sid, "source_kind": kind, "adapter_version": "1.0.0",
            "captured_at": "2026-08-02T00:00:00Z", "valid_until": "2026-12-31T00:00:00Z",
            "facts": facts, "policy_ref": "policy-v1"}


def run(verbose=True):
    out = {}

    def say(m):
        if verbose:
            print(m)

    say("== Code Governance MVP 1D — read-only enterprise signal pilot demonstration ==")
    reg = _registry()
    prof = _profile()
    cfg = ShadowPilotConfig(pilot_id="pilot-1", pilot_version="v1", tenant_id=TENANT,
        allowed_repositories=(REPO,),
        allowed_adapter_ids=("cg.github_readonly", "cg.identity_snapshot",
                             "cg.change_window_snapshot", "cg.incident_snapshot"),
        required_signal_types=("ARTIFACT_IDENTITY", "ACTOR_STATUS"),
        evaluation_profile_ref=prof.policy_ref, maximum_evaluations=50,
        thresholds=PilotThresholds(minimum_evaluations=1))

    svc = CodeGovernanceService(persistence_mode=PersistenceMode.DURABLE_SHADOW)
    runner = ShadowPilotRunner(svc, cfg, registry=reg, profile=prof, routing=None)

    # 1-10. CLEAR: read-only GitHub facts + supplied identity snapshot, human not required.
    _, rid = _drive(svc, "head-AAA")
    ctx = svc.pilot_change_context(TENANT, rid)
    resolver = lambda s: {"Authorization": "Bearer SECRET-TOKEN-XYZ"}  # noqa: E731
    gh = GitHubReadOnlyAdapter(_gh_transport(ctx, resolver=resolver), registry_version="reg-v1")
    idad = IdentitySnapshotAdapter(_snap("identity", {"account_active": True}, "okta"))
    rec = runner.run_evaluation(rid, [gh, idad], collection_time=EVAL, evaluation_time=EVAL,
                                actor_ref="user:sre")
    say(f"  [1 CLEAR   ] status={rec.clearance_status} human={rec.human_intervention_required} "
        f"stale={rec.stale} exec={rec.execution_status}")
    out["clear"] = rec.clearance_status

    # 11. source timeout -> structured failure, never a positive signal.
    _, rid2 = _drive(svc, "head-BBB")
    ctx2 = svc.pilot_change_context(TENANT, rid2)
    tp = _gh_transport(ctx2)
    tp.set_response("GET", f"https://{HOST}/repos/{REPO}/pulls/{NUM}",
                    RawResponse(503, "application/json", b"{}"))
    gh2 = GitHubReadOnlyAdapter(tp)
    rec2 = runner.run_evaluation(rid2, [gh2, IdentitySnapshotAdapter(_snap("identity", {"account_active": True}, "okta"))],
                                 collection_time=EVAL, evaluation_time=EVAL, actor_ref="user:sre")
    say(f"  [11 timeout] status={rec2.clearance_status} failures={list(rec2.source_failures)}")
    out["timeout_failures"] = list(rec2.source_failures)

    # 12. stale GitHub head -> evaluation flagged stale (a new revision is required).
    _, rid3 = _drive(svc, "head-CCC")
    ctx3 = svc.pilot_change_context(TENANT, rid3)
    gh3 = GitHubReadOnlyAdapter(_gh_transport(ctx3, head="head-SUPERSEDED"))
    rec3 = runner.run_evaluation(rid3, [gh3, IdentitySnapshotAdapter(_snap("identity", {"account_active": True}, "okta"))],
                                 collection_time=EVAL, evaluation_time=EVAL, actor_ref="user:sre")
    say(f"  [12 stale  ] stale={rec3.stale} status={rec3.clearance_status}")
    out["stale"] = rec3.stale

    # 13. conflicting incident signals (two sources disagree) -> conflict, fail closed.
    _, rid4 = _drive(svc, "head-DDD")
    ctx4 = svc.pilot_change_context(TENANT, rid4)
    gh4 = GitHubReadOnlyAdapter(_gh_transport(ctx4))
    inc_yes = IncidentSnapshotAdapter(_snap("incident", {"incident_active": True}, "pagerduty"))
    inc_no = IncidentSnapshotAdapter(_snap("incident", {"incident_active": False}, "opsgenie"))
    rec4 = runner.run_evaluation(rid4, [gh4, IdentitySnapshotAdapter(_snap("identity", {"account_active": True}, "okta")),
                                        inc_yes, inc_no], collection_time=EVAL, evaluation_time=EVAL,
                                 actor_ref="user:sre")
    say(f"  [13 conflict] conflicts={list(rec4.conflicts)} status={rec4.clearance_status}")
    out["conflicts"] = list(rec4.conflicts)

    # 8. reviewer feedback (audit only). 9. metrics. 10. report + offline verify.
    runner.record_feedback(PilotReviewerFeedback(
        feedback_id="fb1", pilot_id="pilot-1", tenant_id=TENANT, workflow_id=ctx["workflow_id"],
        workflow_revision_id=rid, reviewer_ref="user:reviewer", reviewer_role="approver",
        reviewed_clearance_status=rec.clearance_status, reviewed_intervention_required=False,
        agreement=FeedbackAgreement.AGREE, observed_resolution=ObservedResolution.PROCEEDED_WITHOUT_CHANGE,
        submitted_at=EVAL))
    metrics = runner.snapshot_metrics(occurred_at=EVAL)
    say(f"  [9 metrics ] evals={metrics.evaluation_count} dist={metrics.clearance_distribution} "
        f"coverage={metrics.reviewer_feedback_coverage} failure_rate={metrics.adapter_failure_rate}")
    report = runner.export_report(occurred_at=EVAL)
    verification = verify_shadow_pilot_report(report)
    say(f"  [10 report ] status={report['pilot_status']} offline_verify_ok={verification.ok} "
        f"exec={report['execution_status']}")
    out["report_ok"] = verification.ok
    out["pilot_status"] = report["pilot_status"]

    # 14. credentials never persisted anywhere in the durable store.
    leaked = False
    for env in svc.durable_store.list_for_workflow(TENANT, "pilot:pilot-1"):
        if "SECRET-TOKEN-XYZ" in json.dumps(env.canonical_payload):
            leaked = True
    say(f"  [14 creds  ] credential value present in durable store: {leaked}")
    out["credential_leaked"] = leaked

    # 15. execution disabled.
    say("  [15 bounds ] no execution · no reservation · no consumption ledger · "
        "no GitHub write · read-only only")
    say("== demonstration complete — execution remains DISABLED ==")
    out["exec"] = svc.execution_status()
    svc.close()
    return out


if __name__ == "__main__":
    run()
