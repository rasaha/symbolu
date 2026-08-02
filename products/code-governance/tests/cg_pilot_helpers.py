"""Shared builders for MVP 1D (read-only adapters + shadow pilot) tests."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from cg_clearance_helpers import EVAL, drive_to_action_evaluated, profile as make_profile
from ugence_action_clearance import SignalTrustLevel, SignalType
from ugence_code_governance import (
    AdapterRegistryEntry,
    AdapterRegistryProjection,
    AdapterRequest,
    ChangeWindowSnapshotAdapter,
    CodeGovernanceService,
    ControlStatusSnapshotAdapter,
    FakeReadOnlyTransport,
    GitHubReadOnlyAdapter,
    IdentitySnapshotAdapter,
    IncidentSnapshotAdapter,
    PersistenceMode,
    PilotThresholds,
    ShadowPilotConfig,
    ShadowPilotRunner,
    TargetHealthSnapshotAdapter,
    TransportPolicy,
)
from ugence_code_governance.adapters import RawResponse

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
GH_HOST = "api.github.com"
GH_POLICY = TransportPolicy(allowed_hosts=(GH_HOST,), allowed_path_prefixes=("/repos/",),
                            allow_head=False, allowed_content_types=("application/json",))


def durable_service():
    return CodeGovernanceService(persistence_mode=PersistenceMode.DURABLE_SHADOW)


def adapter_request(ctx, tenant="acme", signal_types=("ARTIFACT_IDENTITY",), at=EVAL):
    return AdapterRequest(
        tenant_id=tenant, workflow_id=ctx["workflow_id"], workflow_revision_id="rev",
        repository=ctx["repository"], pull_request_number=ctx["pull_request_number"],
        base_sha=ctx["base_sha"], head_sha=ctx["head_sha"], target_branch=ctx["target_branch"],
        prepared_action_fingerprint=ctx["prepared_action_fingerprint"],
        authorization_fingerprint=ctx["authorization_fingerprint"],
        requested_signal_types=signal_types, collection_time=at, source_config_ref="cfg")


def gh_pr_json(ctx, *, state="open", draft=False, head=None):
    return json.dumps({
        "number": ctx["pull_request_number"], "state": state, "draft": draft,
        "base": {"sha": ctx["base_sha"], "repo": {"full_name": ctx["repository"]}},
        "head": {"sha": head or ctx["head_sha"]}}).encode()


def gh_checks_json(*, conclusion="success", status="completed"):
    return json.dumps({"check_runs": [{"status": status, "conclusion": conclusion}]}).encode()


def gh_transport(ctx, *, pr_json=None, checks_json=None, policy=None):
    repo = ctx["repository"]
    num = ctx["pull_request_number"]
    head = ctx["head_sha"]
    responses = {
        ("GET", f"https://{GH_HOST}/repos/{repo}/pulls/{num}"):
            RawResponse(200, "application/json", pr_json if pr_json is not None else gh_pr_json(ctx)),
        ("GET", f"https://{GH_HOST}/repos/{repo}/commits/{head}/check-runs"):
            RawResponse(200, "application/json",
                        checks_json if checks_json is not None else gh_checks_json()),
    }
    return FakeReadOnlyTransport(policy or GH_POLICY, responses)


def github_adapter(ctx, *, transport=None, registry_version="reg-v1", retry=None, sleep=None):
    return GitHubReadOnlyAdapter(transport or gh_transport(ctx), registry_version=registry_version,
                                 retry=retry, sleep=sleep)


def supplied_snapshot(kind, facts, *, tenant="acme", subject="acme/widgets", source="src",
                      version="1.0.0", captured="2026-01-01T00:00:00Z",
                      valid="2026-12-31T00:00:00Z", action_fingerprint=None, with_digest=False):
    snap = {
        "schema_version": f"code_governance.{kind}_snapshot.v1", "tenant_id": tenant,
        "subject_ref": subject, "source_id": source, "source_kind": kind,
        "adapter_version": version, "captured_at": captured, "valid_until": valid,
        "facts": facts, "policy_ref": "policy-v1"}
    if action_fingerprint is not None:
        snap["action_fingerprint"] = action_fingerprint
    if with_digest:
        from ugence_code_governance.adapters import snapshot_digest
        snap["integrity_digest"] = snapshot_digest(snap)
    return snap


def registry_entry(adapter_id, kind, signal_type, *, version="1.0.0",
                   trust=SignalTrustLevel.LEVEL_2_AUTHENTICATED_ENVELOPE, enabled=True,
                   approved_versions=("1.0.0",)):
    return AdapterRegistryEntry(
        adapter_id=adapter_id, adapter_version=version, source_id=kind, source_kind=kind,
        approved_signal_types=(signal_type,), max_trust_level=trust,
        approved_adapter_versions=approved_versions, approved_hosts=(GH_HOST,),
        approved_path_prefixes=("/repos/",), enabled=enabled)


def full_registry(tenant="acme", version="reg-v1"):
    return AdapterRegistryProjection(
        registry_id="reg", registry_version=version, tenant_id=tenant, entries={
            "cg.github_readonly": registry_entry("cg.github_readonly", "github", "ARTIFACT_IDENTITY"),
            "cg.identity_snapshot": registry_entry("cg.identity_snapshot", "identity", "ACTOR_STATUS"),
            "cg.change_window_snapshot": registry_entry("cg.change_window_snapshot", "change_window", "CHANGE_FREEZE"),
            "cg.incident_snapshot": registry_entry("cg.incident_snapshot", "incident", "ACTIVE_INCIDENT"),
            "cg.target_health_snapshot": registry_entry("cg.target_health_snapshot", "target_health", "TARGET_AVAILABILITY"),
            "cg.control_status_snapshot": registry_entry("cg.control_status_snapshot", "control_status", "REQUIRED_CONTROL"),
        })


def pilot_config(repo, *, tenant="acme", adapters=None, required=("ARTIFACT_IDENTITY",),
                 max_evals=10, thresholds=None, reviewer_role_required=False, profile_ref=""):
    return ShadowPilotConfig(
        pilot_id="pilot-1", pilot_version="v1", tenant_id=tenant,
        allowed_repositories=(repo,),
        allowed_adapter_ids=tuple(adapters or (
            "cg.github_readonly", "cg.identity_snapshot", "cg.change_window_snapshot",
            "cg.incident_snapshot", "cg.target_health_snapshot", "cg.control_status_snapshot")),
        required_signal_types=required, evaluation_profile_ref=profile_ref,
        maximum_evaluations=max_evals, reviewer_role_required=reviewer_role_required,
        thresholds=thresholds or PilotThresholds(minimum_evaluations=1))


#: The pilot profile requires only the signals the read-only adapters supply.
PILOT_REQUIRED = (SignalType.ARTIFACT_IDENTITY, SignalType.ACTOR_STATUS)


def pilot_profile(**kw):
    return make_profile(required=PILOT_REQUIRED,
                        trust_required=(SignalType.ARTIFACT_IDENTITY,), **kw)


def build_pilot(*, head_sha="head-1", adapters=None,
                required=("ARTIFACT_IDENTITY", "ACTOR_STATUS"),
                max_evals=10, reviewer_role_required=False, profile=None):
    """Drive a workflow to ACTION_EVALUATED and return (svc, rid, ctx, runner, profile)."""
    svc = durable_service()
    change, rid, action, shadow = drive_to_action_evaluated(svc, head_sha=head_sha)
    ctx = svc.pilot_change_context("acme", rid)
    prof = profile or pilot_profile()
    reg = full_registry()
    cfg = pilot_config(ctx["repository"], adapters=adapters, required=required,
                       max_evals=max_evals, reviewer_role_required=reviewer_role_required,
                       profile_ref=prof.policy_ref)
    runner = ShadowPilotRunner(svc, cfg, registry=reg, profile=prof, routing=None)
    return svc, rid, ctx, runner, prof


def default_snapshot_adapters(active=True, incident=False):
    ida = IdentitySnapshotAdapter(supplied_snapshot("identity", {"account_active": active,
                                                                 "actor_ref": "user:approver"}))
    inc = IncidentSnapshotAdapter(supplied_snapshot("incident", {"incident_active": incident}))
    return [ida, inc]
