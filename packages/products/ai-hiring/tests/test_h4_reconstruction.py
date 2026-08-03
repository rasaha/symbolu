"""H4 — end-to-end decision→outcome reconstruction + cross-audit linkage."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.errors import ActionProposalNotFoundError, CrossTenantHiringAccessError
from .h3_helpers import ai_ctx, human_ctx
from .h4_helpers import build_h4_env, decided_recommendation, exec_adapter, propose_and_authorize


def _full_chain(env):
    prop, auth = propose_and_authorize(env, decided_recommendation(env))
    env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id, adapter=exec_adapter(),
                                  satisfied_obligations=auth.obligations)
    env.reconciliation_service.reconcile(ai_ctx(), proposal_id=prop.action_proposal_id)
    return prop


def test_reconstruct_full_decision_to_outcome_chain():
    env = build_h4_env()
    prop = _full_chain(env)
    r = env.reconstruction_service.reconstruct(ai_ctx(), prop.action_proposal_id)
    assert r.reconstructed
    assert r.recommendation is not None and r.claims and r.provider_claim_bindings
    assert r.human_decision is not None
    assert r.authorizations and r.attempts and r.reconciliations
    assert r.links_intact and r.tenant_scope_consistent and r.hiring_hash_chain_valid


def test_reconstruction_cross_links_hiring_and_governance_audit():
    env = build_h4_env()
    prop = _full_chain(env)
    r = env.reconstruction_service.reconstruct(ai_ctx(), prop.action_proposal_id)
    assert r.hiring_audit_events and r.governance_audit_events


def test_reconstruction_detects_tampered_action_audit():
    env = build_h4_env()
    prop = _full_chain(env)
    key = ("action", prop.action_proposal_id)
    chain = list(env.h3.h2.audit_repo._by_entity[key])
    chain[0] = chain[0].model_copy(update={"new_state": "TAMPERED"})
    env.h3.h2.audit_repo._by_entity[key] = chain
    r = env.reconstruction_service.reconstruct(ai_ctx(), prop.action_proposal_id)
    assert not r.hiring_hash_chain_valid and not r.reconstructed


def test_reconstruction_tenant_isolation():
    env = build_h4_env()
    prop = _full_chain(env)
    with pytest.raises(CrossTenantHiringAccessError):
        env.reconstruction_service.reconstruct(ai_ctx(tenant="t2", actor="ai-t2"), prop.action_proposal_id)


def test_reconstruct_unknown_proposal():
    env = build_h4_env()
    with pytest.raises(ActionProposalNotFoundError):
        env.reconstruction_service.reconstruct(ai_ctx(), "missing")


def test_read_models_expose_timeline_and_trace():
    env = build_h4_env()
    prop = _full_chain(env)
    tl = env.read_models.execution_timeline(ai_ctx(), prop.action_proposal_id)
    assert tl.entries and tl.entries[-1].execution_status == "SUCCEEDED"
    trace = env.read_models.decision_to_outcome_trace(ai_ctx(), prop.action_proposal_id)
    assert trace.human_decision_id and trace.authorized and trace.reconciliation_outcome == "MATCHED"
