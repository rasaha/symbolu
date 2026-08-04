"""Public API stability + manifest agreement + candidate-metadata immutability."""

from __future__ import annotations

import dataclasses
import json
import os

import pytest

import ugence_llm_steering_controller as u

_MANIFEST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "module_manifest.json"))

EXPECTED_API = {
    "LLMSteeringController", "CandidateRegistry", "validate_registry", "RoutingPolicy",
    "SteeringRequest", "TaskRequirements", "ModelCandidate", "ProviderCandidate",
    "RoutingRecommendation", "SteeringResult", "FallbackRecommendation", "RoutingConstraint",
    "CandidateScore", "RoutingExplanation", "RoutingEvidence", "RoutingDecisionTrace",
    "QualityPreference", "PrivacyClass", "ExecutionStatus", "SteeringStatus",
    "DeprecationState", "SteeringError", "ContractError", "RegistryError", "PolicyViolation",
    "NoEligibleCandidate", "recommend", "build_controller", "__version__", "VERSION",
    "POLICY_VERSION", "SCHEMA_VERSION",
}


def test_public_api_is_importable_and_complete():
    for name in EXPECTED_API:
        assert hasattr(u, name), f"missing public symbol: {name}"


def test_all_matches_expected():
    assert set(u.__all__) == EXPECTED_API


def test_manifest_public_api_matches_package():
    manifest = json.load(open(_MANIFEST, encoding="utf-8"))
    manifest_api = set(manifest["public_api"])
    # Every manifest-listed symbol is a real public export.
    assert manifest_api <= set(u.__all__)


def test_manifest_version_matches_package():
    manifest = json.load(open(_MANIFEST, encoding="utf-8"))
    assert manifest["version"] == u.__version__
    assert manifest["policy_version"] == u.POLICY_VERSION
    assert manifest["schema_version"] == u.SCHEMA_VERSION


def test_candidate_metadata_is_immutable():
    m = u.ModelCandidate(model_id="m", provider_id="p")
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.model_id = "other"  # type: ignore[misc]


def test_recommendation_is_frozen():
    res = u.recommend({"providers": [{"provider_id": "p"}],
                       "models": [{"model_id": "m", "provider_id": "p", "context_limit": 9000}]},
                      {"task_category": "chat"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.recommendation.recommended_model = "x"  # type: ignore[misc]
