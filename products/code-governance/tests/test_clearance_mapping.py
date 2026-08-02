"""MVP 1B acceptance tests 1-8: ActionGate -> Action Clearance integration mapping."""
from __future__ import annotations

import pytest

from cg_clearance_helpers import (
    ACTOR, EVAL, drive_to_action_evaluated, full_1b, projection, profile, snapshot,
)
from ugence_code_governance import CodeGovernanceService
from ugence_code_governance.clearance.adapter import ActionClearanceShadowAdapter, is_eligible
from ugence_code_governance.models.enums import ActionClearanceStatus
from ugence_action_clearance import ClearanceStatus


def _adapter_ctx():
    svc = CodeGovernanceService()
    change, rid, action, shadow = drive_to_action_evaluated(svc)
    return svc, rid, action, shadow


# 1. eligible ActionGate result maps to canonical AuthorizationContext
def test_eligible_maps_to_authorization_context():
    svc, rid, action, shadow = _adapter_ctx()
    adapter = ActionClearanceShadowAdapter()
    authz = adapter.authorization_context(shadow, action, actor_ref="user:approver",
                                          authorization_issued_at=action.expiry)
    assert authz.authorization_outcome == shadow.outcome
    assert authz.authorization_result_fingerprint == shadow.result_fingerprint
    assert authz.tenant_id == "acme"


# 2. prepared action maps to exact AuthorizedActionIdentity
def test_prepared_action_maps_to_action_identity():
    svc, rid, action, shadow = _adapter_ctx()
    adapter = ActionClearanceShadowAdapter()
    ident = adapter.action_identity(action, actor_ref="user:approver")
    assert ident.authorized_action_fingerprint == action.fingerprint
    assert ident.target_ref == action.repository
    assert ident.operation == action.merge_method.value


# 3. exact parameters preserved
def test_exact_parameters_preserved():
    svc, rid, action, shadow = _adapter_ctx()
    adapter = ActionClearanceShadowAdapter()
    ident = adapter.action_identity(action, actor_ref="x")
    assert ident.parameters["head_sha"] == action.head_sha
    assert ident.parameters["base_sha"] == action.base_sha
    assert ident.parameters["merge_method"] == action.merge_method.value


# 4-6. obligations, constraints, and expiry preserved
def test_obligations_constraints_expiry_preserved():
    svc, rid, action, shadow = _adapter_ctx()
    adapter = ActionClearanceShadowAdapter()
    authz = adapter.authorization_context(shadow, action, actor_ref="x",
                                          authorization_issued_at=action.expiry)
    assert tuple(authz.authorization_obligations) == tuple(shadow.obligations)
    assert tuple(authz.authorization_constraints) == tuple(shadow.constraints)
    assert authz.authorization_expires_at == action.expiry


# 7. ineligible ActionGate result is not evaluated
def test_ineligible_not_evaluated():
    from ugence_code_governance.governance.actiongate_adapter import ActionGateShadowAdapter
    from actiongate_provider.api import ActionGateEngine, build_actiongate_provider
    prov = build_actiongate_provider(engine=ActionGateEngine(denied=frozenset({"merge_pull_request"})))
    prov.initialize()
    svc, rid, action, shadow, record, assessment, result = full_1b(
        actiongate=ActionGateShadowAdapter(provider=prov))
    assert not is_eligible(shadow)
    assert record.stage_state is ActionClearanceStatus.NOT_EVALUATED_UPSTREAM_NOT_AUTHORIZED
    assert record.clearance_status == ""  # no fabricated clearance result


# 8. ActionGate denial cannot become CLEAR
def test_denial_cannot_become_clear():
    from ugence_code_governance.governance.actiongate_adapter import ActionGateShadowAdapter
    from actiongate_provider.api import ActionGateEngine, build_actiongate_provider
    prov = build_actiongate_provider(engine=ActionGateEngine(denied=frozenset({"merge_pull_request"})))
    prov.initialize()
    svc, rid, action, shadow, record, assessment, result = full_1b(
        actiongate=ActionGateShadowAdapter(provider=prov))
    assert record.clearance_status != ClearanceStatus.CLEAR.value
    assert svc.execution_status() == "DISABLED"
    # the chain still reconstructs (not-evaluated is legitimate)
    assert result.state.value in ("COMPLETE", "STALE")
