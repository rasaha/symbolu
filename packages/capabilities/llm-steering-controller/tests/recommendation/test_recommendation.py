"""Recommendation shape, fallback/escalation, determinism, evidence, no-eligible outcome."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from support import base_registry, single_model_registry  # noqa: E402

import pytest  # noqa: E402

from ugence_llm_steering_controller import (  # noqa: E402
    CandidateRegistry, LLMSteeringController, NoEligibleCandidate, SteeringRequest,
)


def _ctrl(reg=None):
    return LLMSteeringController(CandidateRegistry.from_dict(reg or base_registry()))


def test_recommendation_is_advisory_not_executed():
    res = _ctrl().recommend(SteeringRequest.from_dict({"requirements": {"estimated_input_tokens": 100}}))
    rec = res.recommendation
    assert rec.execution_status == "NOT_EXECUTED"
    assert rec.recommendation_only is True
    assert res.execution_status == "NOT_EXECUTED"


def test_ranked_alternatives_exclude_winner():
    res = _ctrl().recommend(SteeringRequest.from_dict({"requirements": {"estimated_input_tokens": 100}}))
    rec = res.recommendation
    assert rec.recommended_model not in rec.ranked_alternatives
    assert len(rec.ranked_scores) == 1 + len(rec.ranked_alternatives)


def test_fallback_ordered_and_advisory():
    res = _ctrl().recommend(SteeringRequest.from_dict({
        "fallback_permitted": True, "requirements": {"estimated_input_tokens": 100}}))
    fb = res.recommendation.fallback
    assert fb.permitted is True
    assert list(fb.ordered_candidates) == list(res.recommendation.ranked_alternatives)
    assert fb.conditions  # non-empty guidance


def test_fallback_prohibited_yields_no_ordered_candidates():
    res = _ctrl().recommend(SteeringRequest.from_dict({
        "fallback_permitted": False, "requirements": {"estimated_input_tokens": 100}}))
    assert res.recommendation.fallback.ordered_candidates == ()


def test_escalation_recommended_on_low_confidence_single_candidate():
    res = _ctrl(single_model_registry()).recommend(SteeringRequest.from_dict({
        "fallback_permitted": False, "escalation_permitted": True,
        "requirements": {"estimated_input_tokens": 100}}))
    fb = res.recommendation.fallback
    assert fb.escalation_recommended is True
    assert fb.escalation_conditions


def test_decision_id_is_deterministic():
    req = {"quality_preference": "balanced", "requirements": {"estimated_input_tokens": 4000}}
    a = _ctrl().recommend(SteeringRequest.from_dict(req))
    b = _ctrl().recommend(SteeringRequest.from_dict(req))
    assert a.decision_id == b.decision_id
    assert a.to_dict() == b.to_dict()


def test_decision_id_changes_with_inputs():
    a = _ctrl().recommend(SteeringRequest.from_dict({"requirements": {"estimated_input_tokens": 4000}}))
    b = _ctrl().recommend(SteeringRequest.from_dict({"requirements": {"estimated_input_tokens": 8000}}))
    assert a.decision_id != b.decision_id


def test_evidence_reproduces_filtering():
    res = _ctrl().recommend(SteeringRequest.from_dict({
        "prohibited_providers": ["trainy"], "requirements": {"estimated_input_tokens": 100}}))
    ev = res.evidence
    assert ev.candidates_considered == 5
    assert ev.eligible_count == len(res.recommendation.ranked_scores)
    # Every rejected record lists its failing constraints.
    for r in ev.rejected:
        assert r["failed"]
    # Fingerprints present for reproduction.
    assert ev.registry_fingerprint.startswith("reg-")
    assert ev.request_fingerprint.startswith("req-")
    assert ev.policy_fingerprint.startswith("pol-")


def test_no_eligible_returns_typed_outcome_not_exception():
    res = _ctrl().recommend(SteeringRequest.from_dict({"requirements": {"min_context_window": 10**9}}))
    assert res.status == "NO_ELIGIBLE_CANDIDATE"
    assert res.recommendation is None
    assert res.reason
    # Evidence still explains rejections.
    assert res.evidence.eligible_count == 0
    assert len(res.evidence.rejected) == 5


def test_recommend_or_raise_raises_on_no_candidate():
    with pytest.raises(NoEligibleCandidate):
        _ctrl().recommend_or_raise(SteeringRequest.from_dict(
            {"requirements": {"min_context_window": 10**9}}))


def test_trace_stage_order():
    res = _ctrl().recommend(SteeringRequest.from_dict({"requirements": {"estimated_input_tokens": 100}}))
    assert res.trace.stages[0] == "discover_candidates"
    assert res.trace.stages[1] == "apply_hard_constraints"
    assert "build_recommendation" in res.trace.stages
