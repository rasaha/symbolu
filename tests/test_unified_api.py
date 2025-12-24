"""
Tests for Unified API (symbolu/api/unified_api.py)

These tests validate the Unified Symbol-U API Output Schema (USU-API v1.0):
- UnifiedOutput structure and serialization
- build_unified_output from pipeline context
- get_unified_json and get_public_response helpers
- Helper functions for data processing
- Edge cases and error handling
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from datetime import datetime

from symbolu.api.unified_api import (
    UnifiedOutput,
    build_unified_output,
    get_unified_json,
    get_public_response,
    get_internal_diagnostics,
    _remove_none_values,
    _get_coherence_state_label,
    _trim_session_memory_for_public,
    _trim_session_recap_for_public,
    _trim_identity_signature_for_public,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def minimal_unified_output():
    """Create a minimal UnifiedOutput for testing."""
    return UnifiedOutput(
        text="Test output text",
        symbolic={"fusion_score": 0.85},
        practical={"text": "Practical response"},
        mirror={"routing": {}},
        dha={"delivery_profile": "neutral"},
        routing={"tier": "tier_1", "domain": "generic"},
        mappers={"resolution_level": "medium"},
        entropy={"H_D": 0.5, "H_G": 0.3},
        coherence={"coherence_score": 0.9},
        metadata={"timestamp": "2025-12-20T00:00:00Z", "api_version": "USU-API-v1.0"},
    )


@pytest.fixture
def mock_pipeline_context():
    """Create a mock PipelineContext for testing."""
    ctx = MagicMock()

    # Mock fusion result
    ctx.fusion = MagicMock()
    ctx.fusion.fused_candidates = MagicMock()
    ctx.fusion.fused_candidates.to_dict.return_value = {
        "fusion_score": 0.85,
        "ranked_candidates": [{"text": "candidate1"}, {"text": "candidate2"}],
        "selected_candidate": {
            "text": "Selected response",
            "source": "rule_based",
            "confidence": 0.9,
            "relevance_score": 0.8,
        },
        "explain": {"reasoning": "High confidence rule match"},
        "routing": {},
        "metadata": {},
    }

    # Mock DHA result
    ctx.dha = MagicMock()
    ctx.dha.tone_profile = "neutral"
    ctx.dha.readiness_level = "high"
    ctx.dha.resistance_flags = []
    ctx.dha.safety_flags = []
    ctx.dha.adaptation_notes = "No adaptation needed"
    ctx.dha.guarded_text = "Guarded output text"

    # Mock MLCR result
    ctx.mlcr = MagicMock()
    ctx.mlcr.entries = {
        "explain_log": {
            "meta": {"tier": "tier_1", "intent": "query", "domain": "generic"},
            "entropy": {"H_D": 0.5, "H_G": 0.3, "H_K": 0.2, "normalized_entropy": 0.4},
        },
        "activation_plan": {"use_hrm": True, "use_lcm": False, "use_lam": False},
    }

    # Mock mapper profile
    ctx.mapper_profile = MagicMock()
    ctx.mapper_profile.to_dict.return_value = {
        "resolution_level": "medium",
        "arc_mode": "none",
        "detail_bias": 0.5,
    }

    # Mock coherence report
    ctx.coherence_report = {
        "coherence_score": 0.9,
        "persona_drift_score": 0.1,
        "turn_number": 3,
    }

    # Mock coherence state
    ctx.coherence_state = MagicMock()
    ctx.coherence_state.coherence_score_v2 = 0.88
    ctx.coherence_state.coherence_score_v3 = 0.92
    ctx.coherence_state.coherence_v3_quality = "high"
    ctx.coherence_state.coherence_fused = 0.90
    ctx.coherence_state.fusion_stability_weight = 0.5
    ctx.coherence_state.fusion_inertia_factor = 0.3
    ctx.coherence_state.fusion_quality_factor = 0.7
    ctx.coherence_state.semantic_integrity_score = 0.85
    ctx.coherence_state.cognitive_drift_v3 = 0.15
    ctx.coherence_state.temporal_entropy_volatility = 0.25

    # Mock request
    ctx.request = MagicMock()
    ctx.request.user_id = "test_user_123"

    # Mock rendered output
    ctx.rendered = MagicMock()
    ctx.rendered.raw_text = "Final rendered text"

    return ctx


@pytest.fixture
def mock_minimal_context():
    """Create a minimal mock context with no optional fields."""
    ctx = MagicMock()
    ctx.fusion = None
    ctx.dha = None
    ctx.mlcr = None
    ctx.mapper_profile = None
    ctx.coherence_report = None
    ctx.coherence_state = None
    ctx.request = None
    ctx.rendered = None
    return ctx


# =============================================================================
# Tests for UnifiedOutput
# =============================================================================


class TestUnifiedOutput:
    """Tests for UnifiedOutput dataclass."""

    def test_basic_creation(self, minimal_unified_output):
        """Should create UnifiedOutput with required fields."""
        output = minimal_unified_output
        assert output.text == "Test output text"
        assert output.symbolic == {"fusion_score": 0.85}
        assert output.metadata["api_version"] == "USU-API-v1.0"

    def test_optional_fields_default_to_dict(self):
        """Optional dict fields should default to empty dict."""
        output = UnifiedOutput(
            text="test",
            symbolic={},
            practical={},
            mirror={},
            dha={},
            routing={},
            mappers={},
            entropy={},
            coherence={},
            metadata={},
        )
        assert output.session_memory == {}
        assert output.session_recap == {}
        assert output.intent_arc == {}

    def test_optional_fields_none_allowed(self):
        """Optional None fields should be None by default."""
        output = UnifiedOutput(
            text="test",
            symbolic={},
            practical={},
            mirror={},
            dha={},
            routing={},
            mappers={},
            entropy={},
            coherence={},
            metadata={},
        )
        assert output.formulas is None
        assert output.trading_guardrails is None
        assert output.interaction_mode is None

    def test_to_dict(self, minimal_unified_output):
        """to_dict should convert to JSON-serializable dictionary."""
        result = minimal_unified_output.to_dict()
        assert isinstance(result, dict)
        assert result["text"] == "Test output text"
        assert result["symbolic"]["fusion_score"] == 0.85

    def test_to_dict_removes_none_values(self):
        """to_dict should remove None values from output."""
        output = UnifiedOutput(
            text="test",
            symbolic={},
            practical={},
            mirror={},
            dha={},
            routing={},
            mappers={},
            entropy={},
            coherence={},
            metadata={},
            formulas=None,  # This should be removed
        )
        result = output.to_dict()
        assert "formulas" not in result

    def test_to_json_string(self, minimal_unified_output):
        """to_json_string should return valid JSON string."""
        import json

        result = minimal_unified_output.to_json_string()
        assert isinstance(result, str)
        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["text"] == "Test output text"


# =============================================================================
# Tests for build_unified_output
# =============================================================================


class TestBuildUnifiedOutput:
    """Tests for build_unified_output function."""

    def test_with_full_context(self, mock_pipeline_context):
        """Should build complete output from full context."""
        output = build_unified_output("Final text", mock_pipeline_context)

        assert output.text == "Final text"
        assert output.symbolic["fusion_score"] == 0.85
        assert output.dha["delivery_profile"] == "neutral"
        assert output.routing["tier"] == "tier_1"
        assert output.entropy["H_D"] == 0.5

    def test_with_minimal_context(self, mock_minimal_context):
        """Should handle minimal context gracefully."""
        output = build_unified_output("Minimal text", mock_minimal_context)

        assert output.text == "Minimal text"
        assert output.symbolic == {}
        assert output.practical == {}
        assert output.dha == {}

    def test_extracts_coherence_v2_v3(self, mock_pipeline_context):
        """Should extract coherence v2 and v3 scores."""
        output = build_unified_output("test", mock_pipeline_context)

        assert output.coherence.get("coherence_score_v2") == 0.88
        assert output.coherence.get("coherence_score_v3") == 0.92
        assert output.coherence.get("coherence_v3_quality") == "high"

    def test_extracts_formula_fusion_metrics(self, mock_pipeline_context):
        """Should extract Formula Fusion Stabilizer metrics."""
        output = build_unified_output("test", mock_pipeline_context)

        assert output.coherence.get("coherence_fused") == 0.90
        stabilizer = output.coherence.get("stabilizer", {})
        assert stabilizer.get("stability_weight") == 0.5
        assert stabilizer.get("inertia_factor") == 0.3

    def test_computes_dashboard_bands(self, mock_pipeline_context):
        """Should compute dashboard bands when metrics available."""
        output = build_unified_output("test", mock_pipeline_context)

        bands = output.metadata.get("bands", {})
        # With coherence_fused=0.90 and entropy_volatility=0.25 → stable
        assert bands.get("stability_band") == "stable"
        # With cognitive_drift_v3=0.15 → low
        assert bands.get("drift_band") == "low"

    def test_adds_user_id_to_metadata(self, mock_pipeline_context):
        """Should add user_id to metadata when available."""
        output = build_unified_output("test", mock_pipeline_context)
        assert output.metadata.get("user_id") == "test_user_123"

    def test_handles_missing_fusion(self, mock_pipeline_context):
        """Should handle missing fusion result."""
        mock_pipeline_context.fusion = None
        output = build_unified_output("test", mock_pipeline_context)

        assert output.symbolic == {}
        assert output.practical == {}

    def test_handles_missing_dha(self, mock_pipeline_context):
        """Should handle missing DHA result."""
        mock_pipeline_context.dha = None
        output = build_unified_output("test", mock_pipeline_context)

        assert output.dha == {}


# =============================================================================
# Tests for get_unified_json
# =============================================================================


class TestGetUnifiedJson:
    """Tests for get_unified_json function."""

    def test_returns_dict(self, mock_pipeline_context):
        """Should return dictionary."""
        result = get_unified_json(mock_pipeline_context)
        assert isinstance(result, dict)

    def test_extracts_rendered_text(self, mock_pipeline_context):
        """Should extract text from rendered output."""
        result = get_unified_json(mock_pipeline_context)
        assert result["text"] == "Final rendered text"

    def test_falls_back_to_dha_text(self, mock_pipeline_context):
        """Should fall back to DHA text if no rendered."""
        mock_pipeline_context.rendered = None
        result = get_unified_json(mock_pipeline_context)
        assert result["text"] == "Guarded output text"

    def test_handles_no_text_sources(self, mock_minimal_context):
        """Should handle when no text sources available."""
        result = get_unified_json(mock_minimal_context)
        assert result["text"] == ""


# =============================================================================
# Tests for get_public_response
# =============================================================================


class TestGetPublicResponse:
    """Tests for get_public_response function."""

    def test_returns_simplified_response(self, mock_pipeline_context):
        """Should return simplified public response."""
        result = get_public_response(mock_pipeline_context)

        assert "text" in result
        assert "symbolic" in result
        assert "practical" in result
        assert "mirror" in result
        assert "dha" in result
        assert "coherence" in result
        assert "domain" in result

    def test_coherence_has_state_label(self, mock_pipeline_context):
        """Coherence should include state label."""
        result = get_public_response(mock_pipeline_context)

        coherence = result.get("coherence", {})
        assert "coherence_score" in coherence
        assert "state" in coherence
        assert coherence["state"] in ["Excellent", "Good", "Fair", "Poor"]

    def test_dha_trimmed_to_essentials(self, mock_pipeline_context):
        """DHA should only include essential fields."""
        result = get_public_response(mock_pipeline_context)

        dha = result.get("dha", {})
        assert "delivery_profile" in dha
        assert "readiness_level" in dha
        # Should not include internal fields
        assert "resistance_flags" not in dha
        assert "adaptation_notes" not in dha


# =============================================================================
# Tests for get_internal_diagnostics
# =============================================================================


class TestGetInternalDiagnostics:
    """Tests for get_internal_diagnostics function."""

    def test_includes_internal_metadata(self, mock_pipeline_context):
        """Should include _internal diagnostics."""
        result = get_internal_diagnostics(mock_pipeline_context)

        assert "_internal" in result
        internal = result["_internal"]
        assert "has_fusion" in internal
        assert "has_dha" in internal
        assert "has_mlcr" in internal

    def test_reports_component_presence(self, mock_pipeline_context):
        """Should correctly report component presence."""
        result = get_internal_diagnostics(mock_pipeline_context)

        internal = result["_internal"]
        assert internal["has_fusion"] is True
        assert internal["has_dha"] is True

    def test_handles_missing_components(self, mock_minimal_context):
        """Should report missing components."""
        result = get_internal_diagnostics(mock_minimal_context)

        internal = result["_internal"]
        assert internal["has_fusion"] is False
        assert internal["has_dha"] is False


# =============================================================================
# Tests for _remove_none_values
# =============================================================================


class TestRemoveNoneValues:
    """Tests for _remove_none_values helper."""

    def test_removes_none_at_top_level(self):
        """Should remove None values at top level."""
        d = {"a": 1, "b": None, "c": 3}
        result = _remove_none_values(d)
        assert result == {"a": 1, "c": 3}

    def test_removes_none_nested(self):
        """Should remove None values in nested dicts."""
        d = {"outer": {"a": 1, "b": None}}
        result = _remove_none_values(d)
        assert result == {"outer": {"a": 1}}

    def test_handles_empty_dict(self):
        """Should handle empty dict."""
        result = _remove_none_values({})
        assert result == {}

    def test_handles_lists(self):
        """Should handle lists in dict."""
        d = {"items": [1, None, 3]}
        result = _remove_none_values(d)
        # None in lists is preserved
        assert result == {"items": [1, None, 3]}

    def test_handles_deeply_nested(self):
        """Should handle deeply nested structures."""
        d = {"a": {"b": {"c": {"d": None, "e": 1}}}}
        result = _remove_none_values(d)
        assert result == {"a": {"b": {"c": {"e": 1}}}}

    def test_preserves_non_dict_values(self):
        """Should preserve non-dict values."""
        assert _remove_none_values(42) == 42
        assert _remove_none_values("hello") == "hello"
        assert _remove_none_values([1, 2, 3]) == [1, 2, 3]


# =============================================================================
# Tests for _get_coherence_state_label
# =============================================================================


class TestGetCoherenceStateLabel:
    """Tests for _get_coherence_state_label helper."""

    @pytest.mark.parametrize("score,expected", [
        (0.95, "Excellent"),
        (0.90, "Excellent"),
        (0.85, "Excellent"),
        (0.80, "Good"),
        (0.75, "Good"),
        (0.70, "Good"),
        (0.65, "Fair"),
        (0.60, "Fair"),
        (0.55, "Fair"),
        (0.50, "Fair"),
        (0.45, "Poor"),
        (0.30, "Poor"),
        (0.10, "Poor"),
        (0.0, "Poor"),
    ])
    def test_score_to_label(self, score, expected):
        """Should map score to correct label."""
        assert _get_coherence_state_label(score) == expected

    def test_boundary_conditions(self):
        """Should handle boundary conditions correctly."""
        assert _get_coherence_state_label(0.85) == "Excellent"
        assert _get_coherence_state_label(0.849) == "Good"
        assert _get_coherence_state_label(0.70) == "Good"
        assert _get_coherence_state_label(0.699) == "Fair"
        assert _get_coherence_state_label(0.50) == "Fair"
        assert _get_coherence_state_label(0.499) == "Poor"


# =============================================================================
# Tests for _trim_session_memory_for_public
# =============================================================================


class TestTrimSessionMemoryForPublic:
    """Tests for _trim_session_memory_for_public helper."""

    def test_empty_memory(self):
        """Should handle empty session memory."""
        result = _trim_session_memory_for_public({})
        assert result == {}

    def test_no_events(self):
        """Should handle memory with no events key."""
        result = _trim_session_memory_for_public({"other_key": "value"})
        assert result == {}

    def test_filters_to_significant_events(self):
        """Should filter to significant event types."""
        memory = {
            "events": [
                {"event_type": "turn_start", "turn_index": 0},
                {"event_type": "breakthrough", "turn_index": 1, "description": "Major insight"},
                {"event_type": "turn_end", "turn_index": 1},
                {"event_type": "stabilization", "turn_index": 2, "description": "Session stabilized"},
            ]
        }
        result = _trim_session_memory_for_public(memory)

        assert len(result["events"]) == 2
        assert result["events"][0]["event_type"] == "breakthrough"
        assert result["events"][1]["event_type"] == "stabilization"

    def test_limits_to_two_events(self):
        """Should limit to last 2 significant events."""
        memory = {
            "events": [
                {"event_type": "breakthrough", "turn_index": 1, "description": "First"},
                {"event_type": "stabilization", "turn_index": 2, "description": "Second"},
                {"event_type": "mapper_flip", "turn_index": 3, "description": "Third"},
            ]
        }
        result = _trim_session_memory_for_public(memory)

        assert len(result["events"]) == 2
        # Should be the last 2
        assert result["events"][0]["event_type"] == "stabilization"
        assert result["events"][1]["event_type"] == "mapper_flip"

    def test_removes_raw_metrics(self):
        """Should remove raw metrics from events."""
        memory = {
            "events": [
                {
                    "event_type": "breakthrough",
                    "turn_index": 1,
                    "description": "Insight",
                    "raw_metrics": {"some": "data"},
                    "internal_score": 0.95,
                }
            ]
        }
        result = _trim_session_memory_for_public(memory)

        event = result["events"][0]
        assert "turn_index" in event
        assert "event_type" in event
        assert "description" in event
        assert "raw_metrics" not in event
        assert "internal_score" not in event


# =============================================================================
# Tests for _trim_session_recap_for_public
# =============================================================================


class TestTrimSessionRecapForPublic:
    """Tests for _trim_session_recap_for_public helper."""

    def test_empty_recap(self):
        """Should handle empty recap."""
        result = _trim_session_recap_for_public({})
        assert result == {}

    def test_extracts_public_fields(self):
        """Should extract public-safe fields."""
        recap = {
            "overall_state": "stable",
            "net_trajectory": "improving",
            "recommended_style": "supportive",
            "turning_points": [],
            "internal_metrics": {"should_not": "appear"},
        }
        result = _trim_session_recap_for_public(recap)

        assert result["overall_state"] == "stable"
        assert result["net_trajectory"] == "improving"
        assert result["recommended_style"] == "supportive"
        assert "internal_metrics" not in result

    def test_filters_turning_points(self):
        """Should filter turning points to significant types."""
        recap = {
            "overall_state": "stable",
            "turning_points": [
                {"event_type": "minor_change", "turn_index": 1},
                {"event_type": "breakthrough", "turn_index": 2, "description": "Major"},
                {"event_type": "fragmentation", "turn_index": 3, "description": "Issue"},
            ],
        }
        result = _trim_session_recap_for_public(recap)

        assert len(result["recent_turning_points"]) == 2
        assert result["recent_turning_points"][0]["event_type"] == "breakthrough"
        assert result["recent_turning_points"][1]["event_type"] == "fragmentation"


# =============================================================================
# Tests for _trim_identity_signature_for_public
# =============================================================================


class TestTrimIdentitySignatureForPublic:
    """Tests for _trim_identity_signature_for_public helper."""

    def test_empty_signature(self):
        """Should handle empty signature."""
        result = _trim_identity_signature_for_public({})
        assert result == {}

    def test_extracts_public_fields(self):
        """Should extract public-safe fields."""
        signature = {
            "signature_type": "explorer",
            "confidence": 0.85,
            "markers": ["curious", "open"],
            "drivers": ["growth", "understanding", "connection"],
            "internal_data": {"should_not": "appear"},
        }
        result = _trim_identity_signature_for_public(signature)

        assert result["signature_type"] == "explorer"
        assert result["confidence"] == 0.85
        assert "internal_data" not in result

    def test_limits_markers(self):
        """Should limit to last 2 markers."""
        signature = {
            "signature_type": "explorer",
            "confidence": 0.85,
            "markers": ["first", "second", "third", "fourth"],
            "drivers": [],
        }
        result = _trim_identity_signature_for_public(signature)

        assert len(result["recent_markers"]) == 2
        assert result["recent_markers"] == ["third", "fourth"]

    def test_driver_summary(self):
        """Should provide driver summary with count."""
        signature = {
            "signature_type": "explorer",
            "confidence": 0.85,
            "markers": [],
            "drivers": ["growth", "understanding", "connection"],
        }
        result = _trim_identity_signature_for_public(signature)

        driver_summary = result["driver_summary"]
        assert driver_summary["count"] == 3
        assert driver_summary["primary"] == "growth"

    def test_empty_drivers(self):
        """Should handle empty drivers."""
        signature = {
            "signature_type": "neutral",
            "confidence": 0.5,
            "markers": [],
            "drivers": [],
        }
        result = _trim_identity_signature_for_public(signature)

        driver_summary = result["driver_summary"]
        assert driver_summary["count"] == 0
        assert driver_summary["primary"] is None


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for unified API flow."""

    def test_full_pipeline_flow(self, mock_pipeline_context):
        """Test complete flow from context to public response."""
        # Get unified JSON
        unified = get_unified_json(mock_pipeline_context)
        assert isinstance(unified, dict)
        assert "text" in unified
        assert "coherence" in unified

        # Get public response
        public = get_public_response(mock_pipeline_context)
        assert isinstance(public, dict)
        assert "text" in public
        assert "coherence" in public

        # Get diagnostics
        diagnostics = get_internal_diagnostics(mock_pipeline_context)
        assert "_internal" in diagnostics

    def test_handles_real_world_edge_cases(self, mock_minimal_context):
        """Test handling of minimal real-world context."""
        # Should not raise
        unified = get_unified_json(mock_minimal_context)
        public = get_public_response(mock_minimal_context)
        diagnostics = get_internal_diagnostics(mock_minimal_context)

        assert unified is not None
        assert public is not None
        assert diagnostics is not None
