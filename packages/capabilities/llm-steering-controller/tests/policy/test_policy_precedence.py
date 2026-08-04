"""Policy precedence: hard constraints beat any score; deterministic tie-break."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from support import base_registry, tie_registry  # noqa: E402

from ugence_llm_steering_controller import (  # noqa: E402
    CandidateRegistry, LLMSteeringController, RoutingPolicy, SteeringRequest,
)
from ugence_llm_steering_controller.policy import TIE_BREAK_RULE  # noqa: E402


def _ctrl(reg):
    return LLMSteeringController(CandidateRegistry.from_dict(reg))


def test_high_score_cannot_restore_prohibited_model():
    # claude-premium would score highest under quality_first, but prohibiting it must
    # remove it regardless of score.
    ctrl = _ctrl(base_registry())
    res = ctrl.recommend(SteeringRequest.from_dict({
        "quality_preference": "quality_first", "prohibited_models": ["claude-premium"],
        "requirements": {"estimated_input_tokens": 4000}}))
    assert res.is_recommended
    assert res.recommendation.recommended_model != "claude-premium"
    assert "claude-premium" not in res.recommendation.ranked_alternatives


def test_prohibited_provider_never_appears_in_ranking():
    ctrl = _ctrl(base_registry())
    res = ctrl.recommend(SteeringRequest.from_dict({
        "prohibited_providers": ["anthropic"], "requirements": {"estimated_input_tokens": 100}}))
    ranked = [res.recommendation.recommended_model, *res.recommendation.ranked_alternatives]
    reg = CandidateRegistry.from_dict(base_registry())
    for mid in ranked:
        assert reg.model(mid).provider_id != "anthropic"


def test_tie_break_is_deterministic_lexicographic():
    ctrl = _ctrl(tie_registry())
    res = ctrl.recommend(SteeringRequest.from_dict({"requirements": {"estimated_input_tokens": 2000}}))
    assert res.recommendation.recommended_model == "m-a"  # a < b at equal score
    assert res.recommendation.explanation.tie_break_rule == TIE_BREAK_RULE


def test_scores_are_only_over_eligible_set():
    ctrl = _ctrl(base_registry())
    res = ctrl.recommend(SteeringRequest.from_dict({
        "approved_models": ["gpt-fast"], "requirements": {"estimated_input_tokens": 100}}))
    # Only one model scored; evidence eligible_count == 1.
    assert res.evidence.eligible_count == 1
    assert len(res.recommendation.ranked_scores) == 1


def test_policy_version_present_in_every_result():
    ctrl = _ctrl(base_registry())
    res = ctrl.recommend(SteeringRequest.from_dict({
        "policy_version": "steering-policy-XYZ", "requirements": {"estimated_input_tokens": 100}}))
    assert res.policy_version == "steering-policy-XYZ"
    assert res.recommendation.policy_version == "steering-policy-XYZ"
    # No-eligible outcome also carries policy version.
    res2 = ctrl.recommend(SteeringRequest.from_dict({
        "policy_version": "steering-policy-XYZ", "requirements": {"min_context_window": 10**9}}))
    assert res2.policy_version == "steering-policy-XYZ"


def test_weight_override_changes_ranking_but_not_eligibility():
    reg = base_registry()
    base = _ctrl(reg).recommend(SteeringRequest.from_dict({
        "quality_preference": "balanced", "requirements": {"estimated_input_tokens": 4000}}))
    # Crank cost weight massively -> the cheapest eligible candidate must win, while the
    # eligible set is unchanged (a soft weight never alters eligibility).
    pol = RoutingPolicy(preference="balanced", weight_overrides={"cost_score": 50.0})
    cheap = _ctrl(reg).recommend(
        SteeringRequest.from_dict({"requirements": {"estimated_input_tokens": 4000}}), pol)
    assert base.evidence.eligible_count == cheap.evidence.eligible_count
    # Cheapest eligible model has cost_score == 1.0; the override must select it.
    assert cheap.recommendation.score.components["cost_score"] == 1.0
