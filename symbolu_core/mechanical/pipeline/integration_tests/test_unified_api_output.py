"""
Integration tests for Unified API Output Schema (USU-API v1.0).

Tests verify:
1. Structure completeness - all top-level keys present
2. JSON serialization - output is JSON-safe
3. Stability snapshot - deterministic output for fixed input
4. Non-invasiveness - does not modify pipeline behavior
5. Coherence propagation - exposes all coherence metrics
6. Entropy propagation - exposes all entropy metrics
"""

import json
import pytest
from agentic.api.unified_api import (
    build_unified_output,
    get_unified_json,
    get_public_response,
    get_internal_diagnostics,
)
from symbolu_core.mechanical.pipeline.orchestrator import SymbolUPipeline
from symbolu_core.mechanical.pipeline.models import (
    UserRequest,
    PipelineContext,
    PersonaContext,
    MlcrResult,
    FusionResult,
    DhaDecision,
    RenderedOutput,
    MapperProfile,
)
from agentic.core.coherence.coherence_state import CoherenceState


def create_mock_context(text: str = "test query") -> PipelineContext:
    """
    Create a mock PipelineContext with all components populated.

    This simulates a complete pipeline execution for testing.
    """
    request = UserRequest(text=text, user_id="test_user")
    ctx = PipelineContext(request=request)

    # Add persona
    ctx.persona = PersonaContext(
        active_persona_id="analyst",
        persona_config={
            "id": "analyst",
            "formality": 0.7,
            "warmth": 0.5,
            "directness": 0.8,
        },
    )

    # Add MLCR result
    ctx.mlcr = MlcrResult(
        entries={
            "explain_log": {
                "meta": {
                    "tier": "hybrid",
                    "intent": "WHAT",
                    "domain": "general",
                },
                "entropy": {
                    "H_D": 0.5,
                    "H_G": 0.4,
                    "H_K": 0.3,
                    "normalized_entropy": 0.45,
                },
            },
            "activation_plan": {
                "use_hrm": True,
                "use_lcm": False,
                "use_lam": False,
            },
        }
    )

    # Add mapper profile
    ctx.mapper_profile = MapperProfile(
        resolution_level="high",
        arc_mode="none",
        detail_bias=0.7,
        practical_bias=0.3,
        reflective_bias=0.4,
    )

    # Add DHA decision
    ctx.dha = DhaDecision(
        guarded_text="This is the adapted response.",
        tone_profile="sweet_resonance",
        readiness_level="HIGH",
        resistance_flags={},
        safety_flags={"is_safe": True},
        adaptation_notes={"process_time_ms": 15.2},
    )

    # Add rendered output
    ctx.rendered = RenderedOutput(
        raw_text="This is the adapted response.",
        mode="standard",
        meta={"persona_id": "analyst"},
    )

    # Add coherence state
    ctx.coherence_state = CoherenceState(
        convo_id="test_convo",
        turn_index=3,
        tier_history=["hybrid"] * 4,
        domain_history=["general"] * 4,
        mapper_profile_history=[{}] * 4,
        smi_history=[0.5] * 4,
        bhava_id_history=[1] * 4,
        bhava_direction_history=["stable"] * 4,
        tension_history=[0.3] * 4,
        temporal_flags_history=[{}] * 4,
        coherence_score=0.85,
        persona_drift_score=0.15,
        semantic_stability_score=0.9,
        temporal_arc_score=0.8,
        mapper_volatility_score=0.1,
    )

    # Add coherence report
    ctx.coherence_report = {
        "coherence_score": 0.85,
        "persona_drift_score": 0.15,
        "semantic_stability_score": 0.9,
        "temporal_arc_score": 0.8,
        "mapper_volatility_score": 0.1,
        "turn_number": 3,
        "tier": "hybrid",
        "domain": "general",
        "active_mappers": ["HRM"],
    }

    return ctx


def test_structure_completeness():
    """
    Test that all top-level keys exist in unified output.

    Verifies the API contract is complete.
    """
    ctx = create_mock_context()
    unified = get_unified_json(ctx)

    # Check all required top-level keys
    required_keys = [
        "text",
        "symbolic",
        "practical",
        "mirror",
        "dha",
        "routing",
        "mappers",
        "entropy",
        "coherence",
        "metadata",
    ]

    for key in required_keys:
        assert key in unified, f"Missing required key: {key}"

    # Verify each section has content
    assert isinstance(unified["text"], str)
    assert isinstance(unified["symbolic"], dict)
    assert isinstance(unified["practical"], dict)
    assert isinstance(unified["mirror"], dict)
    assert isinstance(unified["dha"], dict)
    assert isinstance(unified["routing"], dict)
    assert isinstance(unified["mappers"], dict)
    assert isinstance(unified["entropy"], dict)
    assert isinstance(unified["coherence"], dict)
    assert isinstance(unified["metadata"], dict)


def test_json_serialization():
    """
    Test that unified output is JSON-serializable.

    Verifies no circular references or non-serializable objects.
    """
    ctx = create_mock_context()
    unified = get_unified_json(ctx)

    # Should not raise exception
    json_str = json.dumps(unified)
    assert len(json_str) > 0

    # Should be able to parse back
    parsed = json.loads(json_str)
    assert parsed == unified


def test_stability_snapshot():
    """
    Test that unified output is deterministic for fixed input.

    Same input should always produce same output (except timestamp).
    """
    ctx1 = create_mock_context("deterministic query")
    ctx2 = create_mock_context("deterministic query")

    unified1 = get_unified_json(ctx1)
    unified2 = get_unified_json(ctx2)

    # Remove timestamps before comparison
    unified1_no_ts = {k: v for k, v in unified1.items() if k != "metadata"}
    unified2_no_ts = {k: v for k, v in unified2.items() if k != "metadata"}

    # Metadata without timestamp
    meta1 = {k: v for k, v in unified1["metadata"].items() if k != "timestamp"}
    meta2 = {k: v for k, v in unified2["metadata"].items() if k != "timestamp"}

    # Should be identical (except timestamp)
    assert unified1_no_ts == unified2_no_ts
    assert meta1 == meta2


def test_non_invasiveness():
    """
    Test that enabling unified API does not modify pipeline behavior.

    Compare pipeline execution with and without unified API calls.
    """
    ctx = create_mock_context()

    # Capture original state
    original_text = ctx.rendered.raw_text if ctx.rendered else ""
    original_routing_tier = (
        ctx.mlcr.entries.get("explain_log", {}).get("meta", {}).get("tier")
        if ctx.mlcr
        else None
    )
    original_mapper_profile = ctx.mapper_profile.to_dict() if ctx.mapper_profile else {}
    original_coherence = ctx.coherence_report.copy() if ctx.coherence_report else {}

    # Call unified API
    unified = get_unified_json(ctx)

    # Verify nothing changed
    assert ctx.rendered.raw_text == original_text
    assert (
        ctx.mlcr.entries.get("explain_log", {}).get("meta", {}).get("tier")
        == original_routing_tier
    )
    assert ctx.mapper_profile.to_dict() == original_mapper_profile
    assert ctx.coherence_report == original_coherence

    # Verify unified output contains expected data
    assert unified["text"] == original_text


def test_coherence_propagation():
    """
    Test that all coherence metrics are exposed in unified output.

    Verifies:
    - coherence_score
    - persona_drift_score
    - semantic_stability_score
    - temporal_arc_score
    - mapper_volatility_score
    """
    ctx = create_mock_context()
    unified = get_unified_json(ctx)

    coherence = unified["coherence"]

    # Check all coherence metrics present
    assert "coherence_score" in coherence
    assert "persona_drift_score" in coherence
    assert "semantic_stability_score" in coherence
    assert "temporal_arc_score" in coherence
    assert "mapper_volatility_score" in coherence

    # Verify values match context
    assert coherence["coherence_score"] == 0.85
    assert coherence["persona_drift_score"] == 0.15
    assert coherence["semantic_stability_score"] == 0.9
    assert coherence["temporal_arc_score"] == 0.8
    assert coherence["mapper_volatility_score"] == 0.1


def test_entropy_propagation():
    """
    Test that all entropy metrics are exposed in unified output.

    Verifies:
    - H_D (dimensional entropy)
    - H_G (guna entropy)
    - H_K (kosha entropy)
    - normalized_entropy
    """
    ctx = create_mock_context()
    unified = get_unified_json(ctx)

    entropy = unified["entropy"]

    # Check all entropy metrics present
    assert "H_D" in entropy
    assert "H_G" in entropy
    assert "H_K" in entropy
    assert "normalized_entropy" in entropy

    # Verify values match context
    assert entropy["H_D"] == 0.5
    assert entropy["H_G"] == 0.4
    assert entropy["H_K"] == 0.3
    assert entropy["normalized_entropy"] == 0.45


def test_routing_plan_propagation():
    """
    Test that routing plan fields are exposed correctly.
    """
    ctx = create_mock_context()
    unified = get_unified_json(ctx)

    routing = unified["routing"]

    # Check routing plan fields
    assert "tier" in routing
    assert "intent" in routing
    assert "domain" in routing
    assert "use_hrm" in routing
    assert "use_lcm" in routing
    assert "use_lam" in routing

    # Verify values
    assert routing["tier"] == "hybrid"
    assert routing["intent"] == "WHAT"
    assert routing["domain"] == "general"
    assert routing["use_hrm"] is True
    assert routing["use_lcm"] is False
    assert routing["use_lam"] is False


def test_mapper_profile_propagation():
    """
    Test that mapper profile is exposed correctly.
    """
    ctx = create_mock_context()
    unified = get_unified_json(ctx)

    mappers = unified["mappers"]

    # Check mapper profile fields
    assert "resolution_level" in mappers
    assert "arc_mode" in mappers
    assert "detail_bias" in mappers
    assert "practical_bias" in mappers
    assert "reflective_bias" in mappers

    # Verify values
    assert mappers["resolution_level"] == "high"
    assert mappers["arc_mode"] == "none"
    assert mappers["detail_bias"] == 0.7
    assert mappers["practical_bias"] == 0.3
    assert mappers["reflective_bias"] == 0.4


def test_dha_insights_propagation():
    """
    Test that DHA insights are exposed correctly.
    """
    ctx = create_mock_context()
    unified = get_unified_json(ctx)

    dha = unified["dha"]

    # Check DHA fields
    assert "delivery_profile" in dha
    assert "readiness_level" in dha
    assert "adapted_message" in dha

    # Verify values
    assert dha["delivery_profile"] == "sweet_resonance"
    assert dha["readiness_level"] == "HIGH"
    assert dha["adapted_message"] == "This is the adapted response."


def test_public_response_trimming():
    """
    Test that public response is properly trimmed for UI consumption.
    """
    ctx = create_mock_context()
    public = get_public_response(ctx)

    # Should have subset of keys
    expected_keys = [
        "text",
        "symbolic",
        "practical",
        "mirror",
        "dha",
        "coherence",
        "mappers",
        "domain",
        "timestamp",
    ]

    for key in expected_keys:
        assert key in public, f"Missing key in public response: {key}"

    # DHA should be simplified
    assert "delivery_profile" in public["dha"]
    assert "readiness_level" in public["dha"]
    assert len(public["dha"]) == 2  # Only these two fields

    # Coherence should be simplified
    assert "coherence_score" in public["coherence"]
    assert "state" in public["coherence"]
    assert public["coherence"]["state"] in ["Excellent", "Good", "Fair", "Poor"]


def test_internal_diagnostics_completeness():
    """
    Test that internal diagnostics include all debug information.
    """
    ctx = create_mock_context()
    diagnostics = get_internal_diagnostics(ctx)

    # Should have all unified output keys
    assert "text" in diagnostics
    assert "coherence" in diagnostics
    assert "entropy" in diagnostics

    # Should have internal debug section
    assert "_internal" in diagnostics

    internal = diagnostics["_internal"]
    assert "has_fusion" in internal
    assert "has_dha" in internal
    assert "has_mlcr" in internal
    assert "has_coherence" in internal
    assert "has_rendered" in internal
    assert "router_mode" in internal


def test_empty_context_handling():
    """
    Test that unified API handles empty/minimal contexts gracefully.
    """
    # Create minimal context
    request = UserRequest(text="minimal query")
    ctx = PipelineContext(request=request)

    # Should not crash
    unified = get_unified_json(ctx)

    # Should have all keys with defaults
    assert "text" in unified
    assert "coherence" in unified
    assert "entropy" in unified
    assert "routing" in unified

    # Should be JSON-serializable
    json_str = json.dumps(unified)
    assert len(json_str) > 0


def test_metadata_fields():
    """
    Test that metadata contains expected fields.
    """
    ctx = create_mock_context()
    unified = get_unified_json(ctx)

    metadata = unified["metadata"]

    # Check required metadata fields
    assert "timestamp" in metadata
    assert "turn_index" in metadata
    assert "domain" in metadata
    assert "api_version" in metadata
    assert "pipeline_version" in metadata

    # Verify values
    assert metadata["api_version"] == "USU-API-v1.0"
    assert metadata["pipeline_version"] == "3.0"
    assert metadata["turn_index"] == 3
    assert metadata["domain"] == "general"

    # Timestamp should be ISO format
    assert "T" in metadata["timestamp"]
    assert metadata["timestamp"].endswith("Z")


def test_no_none_values_in_output():
    """
    Test that None values are removed from output.
    """
    ctx = create_mock_context()
    unified = get_unified_json(ctx)

    # Recursively check for None values
    def has_none(obj):
        if obj is None:
            return True
        if isinstance(obj, dict):
            return any(has_none(v) for v in obj.values())
        if isinstance(obj, list):
            return any(has_none(item) for item in obj)
        return False

    assert not has_none(unified), "Output contains None values"


def test_end_to_end_pipeline_integration():
    """
    Test unified API with actual pipeline execution.

    This test runs a real pipeline and verifies unified output.
    """
    # Run actual pipeline
    pipeline = SymbolUPipeline()
    request = UserRequest(text="What is the meaning of life?")

    # Execute pipeline
    result = pipeline.run(request)

    # Build context from result (this would normally be available in the orchestrator)
    # For this test, we simulate what the orchestrator would do
    ctx = PipelineContext(request=request)
    ctx.rendered = result

    # Get unified output
    unified = get_unified_json(ctx)

    # Verify structure
    assert "text" in unified
    assert "metadata" in unified

    # Should be JSON-serializable
    json_str = json.dumps(unified)
    assert len(json_str) > 0


def test_unified_output_to_dict_method():
    """
    Test UnifiedOutput.to_dict() method.
    """
    ctx = create_mock_context()
    text = ctx.rendered.raw_text if ctx.rendered else ""

    unified_obj = build_unified_output(text, ctx)

    # Should have to_dict method
    assert hasattr(unified_obj, 'to_dict')

    # Should return dict
    unified_dict = unified_obj.to_dict()
    assert isinstance(unified_dict, dict)

    # Should match get_unified_json output (except timestamp)
    unified_direct = get_unified_json(ctx)

    # Remove timestamps before comparison
    unified_dict_no_ts = {k: v for k, v in unified_dict.items() if k != "metadata"}
    unified_direct_no_ts = {k: v for k, v in unified_direct.items() if k != "metadata"}

    assert unified_dict_no_ts == unified_direct_no_ts

    # Metadata should match except timestamp
    meta1 = {k: v for k, v in unified_dict["metadata"].items() if k != "timestamp"}
    meta2 = {k: v for k, v in unified_direct["metadata"].items() if k != "timestamp"}
    assert meta1 == meta2


def test_unified_output_to_json_string_method():
    """
    Test UnifiedOutput.to_json_string() method.
    """
    ctx = create_mock_context()
    text = ctx.rendered.raw_text if ctx.rendered else ""

    unified_obj = build_unified_output(text, ctx)

    # Should have to_json_string method
    assert hasattr(unified_obj, 'to_json_string')

    # Should return JSON string
    json_str = unified_obj.to_json_string()
    assert isinstance(json_str, str)
    assert len(json_str) > 0

    # Should be parseable
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
