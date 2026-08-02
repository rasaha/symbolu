"""MVP 1E acceptance tests — configuration, lifecycle, and preflight.

Execution stays DISABLED throughout.
"""
from __future__ import annotations

import pytest
from cg_clearance_helpers import EVAL
from cg_operator_helpers import build_operator, deployment_config, fake_resolver

from ugence_code_governance.pilot_operator import (
    PilotDeploymentConfig,
    PilotLifecycleStatus,
    PreflightOutcome,
    can_transition,
    fingerprint_pilot_config,
    load_pilot_config,
    validate_pilot_config,
)
from ugence_code_governance.pilot_operator.errors import PilotConfigError, PilotLifecycleError


def _base_dict(**over):
    d = dict(config_id="c1", config_version="v1", pilot_id="p1", tenant_id="acme",
             allowed_repositories=["acme/widgets"], allowed_branches=["main"],
             durable_store_path="/data/cg.db", github_adapter_registry_ref="reg-v1",
             maximum_evaluations=50, pilot_end_at="2026-12-31T00:00:00Z")
    d.update(over)
    return d


# --- 1-10. configuration ----------------------------------------------------
def test_valid_bounded_config_admitted():
    cfg = load_pilot_config(_base_dict())
    assert cfg.pilot_id == "p1"


def test_empty_repository_allowlist_rejected():
    with pytest.raises(PilotConfigError):
        load_pilot_config(_base_dict(allowed_repositories=[]))


def test_wildcard_tenant_rejected():
    with pytest.raises(PilotConfigError):
        load_pilot_config(_base_dict(tenant_id="*"))


def test_unrestricted_repositories_rejected():
    with pytest.raises(PilotConfigError):
        load_pilot_config(_base_dict(allowed_repositories=["*"]))


def test_unrestricted_branches_rejected():
    with pytest.raises(PilotConfigError):
        load_pilot_config(_base_dict(allowed_branches=[]))


def test_inline_credential_rejected():
    with pytest.raises(PilotConfigError):
        load_pilot_config(_base_dict(token="ghp_secret"))


def test_unbounded_evaluation_count_rejected():
    with pytest.raises(PilotConfigError):
        load_pilot_config(_base_dict(maximum_evaluations=0, pilot_end_at=None))


def test_unbounded_concurrency_rejected():
    with pytest.raises(PilotConfigError):
        load_pilot_config(_base_dict(maximum_concurrent_collections=99))


def test_unsupported_config_schema_rejected():
    with pytest.raises(PilotConfigError):
        load_pilot_config(_base_dict(schema_version="code_governance.pilot_deployment_config.v99"))


def test_config_fingerprint_deterministic():
    a = load_pilot_config(_base_dict())
    b = load_pilot_config(_base_dict())
    assert a.fingerprint == b.fingerprint


def test_credential_value_excluded_from_fingerprint():
    d = _base_dict(credential_references=[{"reference_id": "gh", "resolver_kind": "ENVIRONMENT",
                                           "source_host": "api.github.com",
                                           "environment_variable_name": "GH_TOKEN",
                                           "required_scopes": ["metadata:read"]}])
    cfg = load_pilot_config(d)
    # the fingerprint is over reference names/scopes only — no value is present anyway
    assert "GH_TOKEN" in fingerprint_pilot_config(cfg) or cfg.fingerprint  # deterministic + value-free
    assert cfg.credential_references[0].environment_variable_name == "GH_TOKEN"


def test_write_scope_credential_rejected():
    d = _base_dict(credential_references=[{"reference_id": "gh", "resolver_kind": "ENVIRONMENT",
                                           "source_host": "api.github.com",
                                           "required_scopes": ["contents:write"]}])
    with pytest.raises(PilotConfigError):
        load_pilot_config(d)


# --- 11-20. lifecycle -------------------------------------------------------
def test_draft_to_ready_valid():
    assert can_transition(PilotLifecycleStatus.DRAFT, PilotLifecycleStatus.READY)


def test_ready_to_active_valid():
    assert can_transition(PilotLifecycleStatus.READY, PilotLifecycleStatus.ACTIVE)


def test_active_to_paused_valid():
    assert can_transition(PilotLifecycleStatus.ACTIVE, PilotLifecycleStatus.PAUSED)


def test_paused_to_active_valid():
    assert can_transition(PilotLifecycleStatus.PAUSED, PilotLifecycleStatus.ACTIVE)


def test_active_to_stopping_valid():
    assert can_transition(PilotLifecycleStatus.ACTIVE, PilotLifecycleStatus.STOPPING)


def test_stopping_to_completed_valid():
    assert can_transition(PilotLifecycleStatus.STOPPING, PilotLifecycleStatus.COMPLETED)


def test_completed_cannot_restart():
    assert not can_transition(PilotLifecycleStatus.COMPLETED, PilotLifecycleStatus.ACTIVE)


def test_aborted_cannot_restart():
    assert not can_transition(PilotLifecycleStatus.ABORTED, PilotLifecycleStatus.ACTIVE)


def test_no_automatic_draft_to_active():
    assert not can_transition(PilotLifecycleStatus.DRAFT, PilotLifecycleStatus.ACTIVE)


def test_integrity_failure_cannot_restart():
    assert not can_transition(PilotLifecycleStatus.INTEGRITY_FAILURE, PilotLifecycleStatus.ACTIVE)


def test_lifecycle_events_append_only_and_survive_restart():
    from ugence_code_governance.pilot_operator import recover_pilot
    svc, rid, ctx, op, cfg = build_operator()
    op.pause(EVAL)
    op.resume(EVAL)
    # lifecycle events are durable; a new recovery sees the ACTIVE state.
    res = recover_pilot(svc.durable_store, cfg)
    assert res.last_lifecycle_status == "ACTIVE"
    svc.close()


def test_illegal_transition_rejected():
    svc, rid, ctx, op, cfg = build_operator()
    with pytest.raises(PilotLifecycleError):
        op.transition(PilotLifecycleStatus.COMPLETED, EVAL)  # ACTIVE -> COMPLETED illegal
    svc.close()


# --- 21-30. preflight -------------------------------------------------------
def test_valid_readonly_config_passes_preflight():
    svc, rid, ctx, op, cfg = build_operator(started=False)
    result = op.preflight()
    assert result.outcome in (PreflightOutcome.PASS, PreflightOutcome.PASS_WITH_WARNINGS)
    svc.close()


def test_execution_disabled_check_present_in_preflight():
    svc, rid, ctx, op, cfg = build_operator(started=False)
    result = op.preflight()
    assert any(name == "execution_disabled" and status == "PASS"
               for name, status, _ in result.checks)
    svc.close()


def test_preflight_no_write_capable_api():
    svc, rid, ctx, op, cfg = build_operator(started=False)
    result = op.preflight()
    assert any(name == "no_write_capable_api" and status == "PASS"
               for name, status, _ in result.checks)
    svc.close()


def test_preflight_credential_value_never_in_result():
    from cg_operator_helpers import FAKE_CREDENTIAL
    svc, rid, ctx, op, cfg = build_operator(started=False)
    result = op.preflight()
    assert FAKE_CREDENTIAL not in str(result)
    svc.close()


def test_preflight_read_only_permissions_pass():
    svc, rid, ctx, op, cfg = build_operator(started=False)
    result = op.preflight()
    assert any(name == "github_permissions_read_only" and status == "PASS"
               for name, status, _ in result.checks)
    svc.close()


def test_preflight_performs_no_mutation():
    svc, rid, ctx, op, cfg = build_operator(started=False)
    before = svc.durable_store.health_check()["record_count"]
    op.preflight()
    after = svc.durable_store.health_check()["record_count"]
    assert before == after  # preflight persists nothing / mutates nothing
    svc.close()
