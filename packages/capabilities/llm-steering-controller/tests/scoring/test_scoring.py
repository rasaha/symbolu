"""Scoring decomposition, normalization, confidence."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from support import base_registry  # noqa: E402

from ugence_llm_steering_controller import CandidateRegistry, LLMSteeringController, SteeringRequest  # noqa: E402
from ugence_llm_steering_controller.policy import ALL_DIMENSIONS  # noqa: E402


def _res(req):
    ctrl = LLMSteeringController(CandidateRegistry.from_dict(base_registry()))
    return ctrl.recommend(SteeringRequest.from_dict(req))


def test_all_score_components_present_and_in_range():
    res = _res({"requirements": {"estimated_input_tokens": 4000}})
    for s in res.recommendation.ranked_scores:
        comps = s["components"]
        assert set(comps) == set(ALL_DIMENSIONS)
        for k, v in comps.items():
            assert 0.0 <= v <= 1.0, (k, v)
        assert 0.0 <= s["total"] <= 1.0


def test_measurement_basis_is_estimated():
    res = _res({"requirements": {"estimated_input_tokens": 4000}})
    assert res.recommendation.score.measurement_basis == "estimated_from_declared_metadata"


def test_relative_cost_score_min_is_one_max_is_zero():
    res = _res({"requirements": {"estimated_input_tokens": 4000}})
    costs = [s["components"]["cost_score"] for s in res.recommendation.ranked_scores]
    assert max(costs) == 1.0  # cheapest eligible
    assert min(costs) == 0.0  # most expensive eligible


def test_confidence_single_candidate_is_fixed_moderate():
    res = _res({"approved_models": ["gpt-fast"], "requirements": {"estimated_input_tokens": 100}})
    assert res.recommendation.confidence == 0.6
    assert "single eligible candidate" in res.recommendation.confidence_basis


def test_confidence_reflects_score_gap():
    res = _res({"quality_preference": "quality_first", "requirements": {"estimated_input_tokens": 4000}})
    assert 0.5 <= res.recommendation.confidence <= 1.0
    assert "gap" in res.recommendation.confidence_basis


def test_weighted_dimension_sum_matches_total():
    res = _res({"requirements": {"estimated_input_tokens": 4000}})
    s = res.recommendation.score
    # total is the weight-normalized average; recompute the normalization from weighted sum.
    assert 0.0 <= s.total <= 1.0
    assert abs(sum(s.weighted.values()) / sum(
        __import__("ugence_llm_steering_controller.policy", fromlist=["RoutingPolicy"])
        .RoutingPolicy(preference="balanced").weights().values()) - s.total) < 1e-6
