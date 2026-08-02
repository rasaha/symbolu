"""Shared builders for MVP 1E (pilot operator) tests."""
from __future__ import annotations

from cg_clearance_helpers import EVAL
from cg_pilot_helpers import (
    build_pilot,
    default_snapshot_adapters,
    full_registry,
    github_adapter,
    pilot_profile,
    supplied_snapshot,
)
from ugence_code_governance import IdentitySnapshotAdapter
from ugence_code_governance.pilot_operator import (
    CredentialReference,
    PilotDeploymentConfig,
    PilotStopThresholds,
    ResolverKind,
    open_pilot_operator,
    validate_pilot_config,
)

FAKE_CREDENTIAL = "SECRET-TOKEN-DO-NOT-PERSIST"


def fake_resolver(ref_id):
    return {"Authorization": f"Bearer {FAKE_CREDENTIAL}"}


def deployment_config(repo, *, tenant="acme", store_path=":memory:", max_evals=10,
                      branches=("feature/x", "main"), reviewer_roles=(),
                      concurrency=1, pilot_end="2026-12-31T00:00:00Z", **overrides):
    base = dict(
        config_id="c1", config_version="v1", pilot_id="pilot-1", tenant_id=tenant,
        allowed_repositories=(repo,), allowed_branches=branches, durable_store_path=store_path,
        github_adapter_registry_ref="reg-v1",
        credential_references=(CredentialReference(
            "gh", ResolverKind.ENVIRONMENT, "api.github.com",
            environment_variable_name="GH_TOKEN", required_scopes=("metadata:read",)),),
        approved_snapshot_adapters=("cg.identity_snapshot",),
        reviewer_role_allowlist=reviewer_roles,
        maximum_evaluations=max_evals, maximum_concurrent_collections=concurrency,
        maximum_concurrent_evaluations=concurrency, pilot_end_at=pilot_end,
        stop_thresholds=PilotStopThresholds())
    base.update(overrides)
    return validate_pilot_config(PilotDeploymentConfig(**base))


def identity_adapter(active=True):
    return IdentitySnapshotAdapter(supplied_snapshot("identity", {"account_active": active}))


def build_operator(*, max_evals=10, reviewer_roles=(), started=True,
                   approved_adapters=("cg.identity_snapshot",)):
    """Build a durable service at ACTION_EVALUATED + an opened operator."""
    svc, rid, ctx, _runner, prof = build_pilot()
    cfg = deployment_config(ctx["repository"], max_evals=max_evals, reviewer_roles=reviewer_roles,
                            approved_snapshot_adapters=approved_adapters)
    op = open_pilot_operator(cfg, service=svc, registry=full_registry(), profile=prof,
                             routing=None, credential_resolver=fake_resolver)
    if started:
        op.preflight()
        op.start(EVAL)
    return svc, rid, ctx, op, cfg


def adapters_for(ctx, *, active=True):
    return [github_adapter(ctx), identity_adapter(active)]
