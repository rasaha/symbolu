"""Hard-constraint enforcement, fail-closed behavior, and precedence."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from support import base_registry  # noqa: E402

from ugence_llm_steering_controller import CandidateRegistry, LLMSteeringController, SteeringRequest  # noqa: E402
from ugence_llm_steering_controller.constraints import evaluate_candidate  # noqa: E402


def _ctrl():
    return LLMSteeringController(CandidateRegistry.from_dict(base_registry()))


def _rec(request_dict):
    return _ctrl().recommend(SteeringRequest.from_dict(request_dict))


def test_prohibited_provider_disqualified():
    res = _rec({"prohibited_providers": ["anthropic"],
               "requirements": {"required_modalities": ["image"], "estimated_input_tokens": 100}})
    # claude-premium was the only image model; prohibiting anthropic removes it.
    assert res.status == "NO_ELIGIBLE_CANDIDATE"


def test_approved_provider_allowlist():
    res = _rec({"approved_providers": ["openai"], "requirements": {"estimated_input_tokens": 100}})
    assert res.is_recommended
    assert res.recommendation.recommended_provider == "openai"


def test_deprecated_candidate_excluded():
    res = _rec({"approved_models": ["legacy-deprecated"],
               "requirements": {"estimated_input_tokens": 100}})
    assert res.status == "NO_ELIGIBLE_CANDIDATE"


def test_unknown_capability_treated_as_unsupported():
    res = _rec({"requirements": {"required_capabilities": ["telepathy"], "estimated_input_tokens": 100}})
    assert res.status == "NO_ELIGIBLE_CANDIDATE"


def test_missing_modality_disqualifies():
    res = _rec({"requirements": {"required_modalities": ["audio"], "estimated_input_tokens": 100}})
    assert res.status == "NO_ELIGIBLE_CANDIDATE"


def test_structured_output_required_filters():
    # onprem-small / trainy-cheap lack structured_output; require it and confine to them.
    res = _rec({"approved_models": ["onprem-small", "trainy-cheap"],
               "requirements": {"structured_output_required": True, "estimated_input_tokens": 100}})
    assert res.status == "NO_ELIGIBLE_CANDIDATE"


def test_privacy_confidential_fail_closed():
    # trainy trains_on_data and standard tier -> excluded; only high-tier non-training survive.
    res = _rec({"privacy_classification": "confidential", "requirements": {"estimated_input_tokens": 100}})
    assert res.is_recommended
    picked = res.recommendation.recommended_model
    assert picked in ("claude-premium", "onprem-small")  # both privacy_tier=high, no training


def test_data_residency_fail_closed():
    res = _rec({"data_residency": ["apac"], "requirements": {"estimated_input_tokens": 100}})
    assert res.status == "NO_ELIGIBLE_CANDIDATE"  # nothing serves apac


def test_context_window_enforced():
    res = _rec({"requirements": {"min_context_window": 250000, "estimated_input_tokens": 250000}})
    assert res.status == "NO_ELIGIBLE_CANDIDATE"  # largest is 200000


def test_cost_ceiling_enforced():
    reg = CandidateRegistry.from_dict(base_registry())
    model = reg.model("claude-premium")
    provider = reg.provider("anthropic")
    req = SteeringRequest.from_dict({"cost_budget": 0.001,
                                     "requirements": {"estimated_input_tokens": 100000}})
    eligible, constraints = evaluate_candidate(model, provider, req)
    assert eligible is False
    assert any(c.name == "cost_within_budget" and not c.satisfied for c in constraints)


def test_every_recorded_constraint_has_provenance():
    reg = CandidateRegistry.from_dict(base_registry())
    model = reg.model("gpt-fast")
    provider = reg.provider("openai")
    req = SteeringRequest.from_dict({
        "cost_budget": 100, "latency_budget_ms": 100000,
        "data_residency": ["us"], "privacy_classification": "confidential",
        "requirements": {"required_modalities": ["text"], "structured_output_required": True,
                         "tool_use_required": True, "required_capabilities": ["chat"],
                         "min_context_window": 1000, "estimated_input_tokens": 1000}})
    _, constraints = evaluate_candidate(model, provider, req)
    assert all(c.provenance for c in constraints)
    # Hard constraints span policy-hard, verified-provider-fact and request-budget provenances.
    provs = {c.provenance for c in constraints}
    assert {"policy-hard", "verified-provider-fact", "request-budget"} <= provs
