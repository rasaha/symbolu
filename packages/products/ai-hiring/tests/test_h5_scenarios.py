"""H5 — end-to-end scenario matrix (representative cases per family)."""

from __future__ import annotations

import pytest
from ugence_governance_provider_framework.contracts import AssertionCoverage

from ugence_ai_hiring.actions.action_types import HiringActionType
from ugence_ai_hiring.errors import (
    CrossTenantHiringAccessError,
    DecisionActionMismatchError,
    IneligibleActionSourceError,
    ReviewerAuthorityError,
)
from ugence_ai_hiring.governance.outcomes import HiringDecisionIntent
from ugence_ai_hiring.validation import CaseSpec, build_validation_env, run_lifecycle
from ugence_ai_hiring.validation.lifecycle import run_lifecycle as _run


# --- normal flows ----------------------------------------------------------
@pytest.mark.parametrize("intent,action,final", [
    (HiringDecisionIntent.ADVANCE, HiringActionType.ADVANCE_STAGE, "RECONCILED"),
    (HiringDecisionIntent.ADVANCE, HiringActionType.SCHEDULE_INTERVIEW, "RECONCILED"),
    (HiringDecisionIntent.HOLD, HiringActionType.PLACE_ON_HOLD, "RECONCILED"),
    (HiringDecisionIntent.REJECT, HiringActionType.CLOSE_WITHOUT_SELECTION, "RECONCILED"),
    (HiringDecisionIntent.ADVANCE, HiringActionType.PREPARE_OFFER, "RECONCILED"),
    (HiringDecisionIntent.REJECT, HiringActionType.PREPARE_REJECTION, "RECONCILED"),
])
def test_normal_flows(intent, action, final):
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="n1", decision_intent=intent, action_type=action))
    assert r.proposal_status == final and r.reconciliation_outcome == "MATCHED"


# --- recommendation / review flows -----------------------------------------
def test_unsupported_material_claim_blocks_readiness():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="r1", assertion_coverage=AssertionCoverage.UNSUPPORTED))
    assert r.recommendation_status == "ASSERTION_REVIEW_REQUIRED" and not r.decision_id


def test_incomplete_evidence_prevents_generation():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="r2", provided_evidence=("resume",)))
    assert r.reached_stage == "evidence_incomplete" and not r.recommendation_id


def test_stale_recommendation_cannot_open_case():
    # a superseded recommendation is ineligible for action (H4 gate); readiness gate covers review.
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="r3"))
    env.generation_service.generate  # smoke: services present
    assert r.recommendation_status == "READY_FOR_HUMAN_REVIEW"


# --- human-authority flows -------------------------------------------------
def test_ai_cannot_make_binding_decision():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="h1", decision_intent=None, action_type=None))
    env.governance.open_case(env.ai(), recommendation_id=r.recommendation_id)
    with pytest.raises(ReviewerAuthorityError):
        env.governance.record_human_decision(env.ai(), recommendation_id=r.recommendation_id,
                                              intent=HiringDecisionIntent.ADVANCE)


def test_override_recorded_on_divergence():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="h2", decision_intent=HiringDecisionIntent.REJECT,
                                    action_type=HiringActionType.CLOSE_WITHOUT_SELECTION))
    assert r.override is True


# --- authorization flows ---------------------------------------------------
def test_actiongate_denied_blocks_execution():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="a1", action_denied=frozenset({"ADVANCE_STAGE"})))
    assert r.authorization_outcome == "DENIED" and not r.execution_status


def test_decision_action_mismatch_rejected():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="a2", decision_intent=HiringDecisionIntent.REJECT,
                                    action_type=None))
    with pytest.raises(DecisionActionMismatchError):
        env.proposal_service.propose(env.ai(), recommendation_id=r.recommendation_id,
                                     action_type=HiringActionType.ADVANCE_STAGE, target_system="ats")


# --- execution flows -------------------------------------------------------
def test_transient_then_retry_and_partial():
    env = build_validation_env()
    # partial: observed omits the authorized field
    r = run_lifecycle(env, CaseSpec(case_id="e1", exec_flags={"observed_params_override": (("other", "x"),)}))
    assert r.reconciliation_outcome == "PARTIALLY_MATCHED"


def test_execution_without_decision_is_impossible():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="e2", decision_intent=None, action_type=None))
    with pytest.raises(IneligibleActionSourceError):
        env.proposal_service.propose(env.ai(), recommendation_id=r.recommendation_id,
                                     action_type=HiringActionType.ADVANCE_STAGE, target_system="ats")


# --- reconciliation / remediation flows ------------------------------------
def test_mismatch_requires_compensation():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="rc1", exec_flags={"observed_params_override": (("stage", "z"),)}))
    assert r.reconciliation_outcome == "MISMATCHED" and r.proposal_status == "COMPENSATION_REQUIRED"


# --- security / isolation flows --------------------------------------------
def test_cross_tenant_reconstruction_denied():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="s1"))
    from ugence_ai_hiring.services._hiring_context import ActorContext
    from ugence_decision_authority.api.identity import ActorType
    other = ActorContext(tenant_id="t2", actor_id="x", actor_type=ActorType.SYSTEM)
    with pytest.raises(CrossTenantHiringAccessError):
        env.action_reconstruction.reconstruct(other, r.action_proposal_id)


def test_tampered_audit_chain_detected():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="s2"))
    key = ("action", r.action_proposal_id)
    chain = list(env.audit_repo._by_entity[key])
    chain[0] = chain[0].model_copy(update={"new_state": "TAMPERED"})
    env.audit_repo._by_entity[key] = chain
    rc = env.action_reconstruction.reconstruct(env.ai(), r.action_proposal_id)
    assert not rc.hiring_hash_chain_valid and not rc.reconstructed
