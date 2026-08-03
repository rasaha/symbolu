"""H4 — compensation (separately governed; never auto-compensate irreversible)."""

from __future__ import annotations

from ugence_ai_hiring.actions.records import CompensationStatus
from ugence_ai_hiring.actions.status import ActionProposalStatus
from .h3_helpers import ai_ctx
from .h4_helpers import build_h4_env, decided_recommendation, exec_adapter, propose_and_authorize


def _compensation_required(env):
    prop, auth = propose_and_authorize(env, decided_recommendation(env))
    env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id,
                                  adapter=exec_adapter(observed_params_override=(("stage", "different"),)),
                                  satisfied_obligations=auth.obligations)
    env.reconciliation_service.reconcile(ai_ctx(), proposal_id=prop.action_proposal_id)
    return prop


def test_reversible_compensation_is_proposed_separately():
    env = build_h4_env()
    prop = _compensation_required(env)
    comp = env.compensation_service.propose_compensation(
        ai_ctx(), proposal_id=prop.action_proposal_id, reversible=True, reason="wrong stage")
    assert comp.status is CompensationStatus.PROPOSED and not comp.requires_human_remediation
    kinds = [e.event_type.value for e in env.h3.h2.audit_repo.events_for("action", prop.action_proposal_id)]
    assert "COMPENSATION_PROPOSED" in kinds


def test_irreversible_action_requires_human_remediation():
    env = build_h4_env()
    prop = _compensation_required(env)
    comp = env.compensation_service.propose_compensation(
        ai_ctx(), proposal_id=prop.action_proposal_id, reversible=False, reason="irreversible send")
    assert comp.requires_human_remediation
    assert comp.status is CompensationStatus.HUMAN_REMEDIATION_REQUIRED
    kinds = [e.event_type.value for e in env.h3.h2.audit_repo.events_for("action", prop.action_proposal_id)]
    assert "REMEDIATION_REQUESTED" in kinds


def test_resolve_compensation_closes_action():
    env = build_h4_env()
    prop = _compensation_required(env)
    comp = env.compensation_service.propose_compensation(
        ai_ctx(), proposal_id=prop.action_proposal_id, reversible=True, reason="fixable")
    env.compensation_service.resolve_compensation(
        ai_ctx(), compensation_id=comp.compensation_id, proposal_id=prop.action_proposal_id)
    assert env.proposals.get(prop.action_proposal_id).status == ActionProposalStatus.COMPENSATED


def test_compensation_requires_compensation_required_state():
    import pytest
    from ugence_ai_hiring.errors import CompensationError
    env = build_h4_env()
    prop, _ = propose_and_authorize(env, decided_recommendation(env))  # AUTHORIZED, not compensation-required
    with pytest.raises(CompensationError):
        env.compensation_service.propose_compensation(
            ai_ctx(), proposal_id=prop.action_proposal_id, reversible=True, reason="n/a")
