"""Contract construction, serialization, and validation (incl. negative tests)."""

from __future__ import annotations

import pytest

from ugence_llm_steering_controller import (
    ContractError,
    ModelCandidate,
    PolicyViolation,
    ProviderCandidate,
    QualityPreference,
    RoutingPolicy,
    SteeringRequest,
    TaskRequirements,
)
from ugence_llm_steering_controller.contracts import PrivacyClass


def test_model_candidate_roundtrip():
    m = ModelCandidate.from_dict({
        "model_id": "m", "provider_id": "p", "context_limit": 8000,
        "modalities_in": ["text"], "capabilities": ["chat"], "cost_class": "low",
    })
    d = m.to_dict()
    m2 = ModelCandidate.from_dict(d)
    assert m2 == m
    assert m.modalities_in == ("text",)


def test_model_candidate_defaults_fail_closed():
    m = ModelCandidate(model_id="m", provider_id="p")
    # Unknown/unset metadata must default to unsupported / empty.
    assert m.structured_output is False
    assert m.tool_use is False
    assert m.modalities_in == ()
    assert m.capabilities == ()


@pytest.mark.parametrize("bad", [
    {"model_id": "m", "provider_id": "p", "cost_class": "bogus"},
    {"model_id": "m", "provider_id": "p", "quality_tier": "bogus"},
    {"model_id": "m", "provider_id": "p", "privacy_tier": "bogus"},
    {"model_id": "m", "provider_id": "p", "deprecation_state": "bogus"},
    {"model_id": "m", "provider_id": "p", "context_limit": -1},
])
def test_model_candidate_invalid(bad):
    with pytest.raises(ContractError):
        ModelCandidate.from_dict(bad)


def test_request_roundtrip_and_enum_coercion():
    r = SteeringRequest.from_dict({
        "task_category": "chat", "quality_preference": "cost_first",
        "privacy_classification": "confidential",
        "requirements": {"estimated_input_tokens": 100},
    })
    assert r.quality_preference is QualityPreference.COST_FIRST
    assert r.privacy_classification is PrivacyClass.CONFIDENTIAL
    r2 = SteeringRequest.from_dict(r.to_dict())
    assert r2.to_dict() == r.to_dict()


def test_negative_cost_budget_rejected():
    with pytest.raises(ContractError):
        SteeringRequest.from_dict({"cost_budget": -1.0})


def test_negative_latency_budget_rejected():
    with pytest.raises(ContractError):
        SteeringRequest(latency_budget_ms=-5)


def test_invalid_quality_preference_rejected():
    with pytest.raises(ValueError):
        SteeringRequest.from_dict({"quality_preference": "nonsense"})


def test_task_requirements_negative_context_rejected():
    with pytest.raises(ContractError):
        TaskRequirements(min_context_window=-1)


def test_policy_invalid_weight_dimension():
    with pytest.raises(PolicyViolation):
        RoutingPolicy(weight_overrides={"not_a_dim": 1.0})


def test_policy_negative_weight_rejected():
    with pytest.raises(PolicyViolation):
        RoutingPolicy(weight_overrides={"cost_score": -1.0})


def test_policy_zero_weights_rejected():
    pol = RoutingPolicy(weight_overrides={
        k: 0.0 for k in __import__("ugence_llm_steering_controller.policy",
                                   fromlist=["ALL_DIMENSIONS"]).ALL_DIMENSIONS})
    with pytest.raises(PolicyViolation):
        pol.weights()


def test_provider_candidate_no_secret_fields_in_shape():
    p = ProviderCandidate(provider_id="p")
    assert "provider_id" in p.to_dict()
    # No credential-bearing attribute exists on the dataclass.
    assert not any("key" in f or "secret" in f or "token" in f for f in p.to_dict())
