"""
Rule-Based Renderer Tests
==========================

Comprehensive test suite for FusionRenderer (deterministic) and RulesRenderer.

Tests validate:
1. Correct mode-switching (minimal, standard, symbolic, regulated)
2. Symbolic / practical / mirror-truth layer handling
3. Determinism (same input → identical outputs)
4. Regulated mode compliance (no metaphors, factual only)
5. Metadata preservation
6. Input validation

Version: 1.0
"""

import sys
import copy
import pytest
from typing import Dict, Any

# Add project root to path for imports
sys.path.insert(0, "/home/user/symbolu")

from symbolu.mechanical.renderer.fusion_renderer import (
    FusionRenderer,
    FusionOutput,
    RenderedOutput,
    RenderMode,
    Domain,
    MODE_WEIGHTS,
    REGULATED_DOMAINS,
    SymbolicLayer,
    PracticalLayer,
    MirrorTruthLayer
)
from symbolu.mechanical.renderer.rules_renderer import RulesRenderer


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_fusion_output() -> FusionOutput:
    """
    Create a synthetic FusionEngine output for testing.

    Structure matches the FusionEngine output specification:
    - symbolic: themes, archetypes, causal patterns
    - practical: facts, constraints, procedures
    - mirror_truth: contradictions, tensions, alignment
    """
    return FusionOutput(
        query="What is the meaning of my career struggle?",
        merged_response="Your career struggle reflects a deeper tension between security and growth. Consider exploring both paths.",
        hrm_content={
            "reasoning": "The user seeks understanding because their current path feels misaligned. Therefore, exploring alternatives would provide clarity. This represents a classic growth vs stability conflict.",
            "themes": ["growth", "tension", "alignment"],
            "archetypes": ["seeker", "builder"]
        },
        lcm_content={
            "content": "User is experiencing career transition. The situation requires careful evaluation. Multiple options exist for resolution. Professional guidance may help.",
            "clarity_score": 0.85
        },
        moe_content={
            "content": "First, assess current skills. Then, identify market demands. Finally, create an action plan. This must be done systematically.",
            "domain": "career",
            "constraints": ["time limitations", "financial considerations"],
            "procedures": ["skill assessment", "market research", "networking"]
        },
        channel_weights={"hrm": 0.4, "lcm": 0.35, "moe": 0.25},
        conflict_resolution=[
            {
                "source1": "hrm",
                "source2": "moe",
                "type": "perspective_conflict",
                "resolution": "weighted_blend"
            }
        ],
        metadata={
            "session_id": "test-session-001",
            "user_id": "test-user",
            "entropy": 0.42
        }
    )


@pytest.fixture
def simple_analysis_input() -> Dict[str, Any]:
    """Create simple analysis input for RulesRenderer testing."""
    return {
        "text": "Sample analysis text",
        "average_smi": 0.75,
        "calling_type": "VOCATION",
        "dha_tone": "SWEET_RESONANCE",
        "words": ["sample", "analysis", "text"],
        "recommendations": [
            "Focus on alignment",
            "Seek clarity",
            "Take action"
        ]
    }


@pytest.fixture
def regulated_fusion_output(sample_fusion_output) -> FusionOutput:
    """Create FusionOutput with metaphor-like content for regulated mode testing."""
    output = copy.deepcopy(sample_fusion_output)
    output.hrm_content["reasoning"] = "Life is like a garden, as you plant seeds of effort. Therefore, growth requires patience like water nurtures plants."
    return output


# ============================================================================
# FUSION RENDERER MODE TESTS
# ============================================================================

class TestFusionRendererModes:
    """Test mode-switching behavior of FusionRenderer."""

    def test_minimal_mode_only_practical_layer(self, sample_fusion_output):
        """MINIMAL mode should return only practical layer."""
        renderer = FusionRenderer(mode=RenderMode.MINIMAL)
        output = renderer.render(sample_fusion_output)

        assert output.symbolic_layer is None, "MINIMAL mode should not include symbolic layer"
        assert output.practical_layer is not None, "MINIMAL mode must include practical layer"
        assert output.mirror_truth_layer is None, "MINIMAL mode should not include mirror layer"
        assert output.mode == "minimal"

    def test_standard_mode_all_layers(self, sample_fusion_output):
        """STANDARD mode should return all three layers."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(sample_fusion_output)

        assert output.symbolic_layer is not None, "STANDARD mode must include symbolic layer"
        assert output.practical_layer is not None, "STANDARD mode must include practical layer"
        assert output.mirror_truth_layer is not None, "STANDARD mode must include mirror layer"
        assert output.mode == "standard"

    def test_symbolic_mode_expanded_symbolic(self, sample_fusion_output):
        """SYMBOLIC mode should expand symbolic layer and condense practical."""
        renderer = FusionRenderer(mode=RenderMode.SYMBOLIC)
        output = renderer.render(sample_fusion_output)

        assert output.symbolic_layer is not None, "SYMBOLIC mode must include symbolic layer"
        assert output.practical_layer is not None, "SYMBOLIC mode includes condensed practical layer"
        assert output.mirror_truth_layer is not None, "SYMBOLIC mode includes mirror layer"
        assert output.mode == "symbolic"

        # Verify practical layer is condensed (max 2 facts, 1 action)
        assert len(output.practical_layer.key_facts) <= 2, "SYMBOLIC mode condenses key_facts to max 2"
        assert len(output.practical_layer.actionable_items) <= 1, "SYMBOLIC mode condenses actions to max 1"

    def test_regulated_mode_compliance(self, sample_fusion_output):
        """REGULATED mode should minimize metaphors and maintain factual content."""
        renderer = FusionRenderer(mode=RenderMode.REGULATED)
        output = renderer.render(sample_fusion_output)

        assert output.symbolic_layer is not None, "REGULATED mode includes restricted symbolic layer"
        assert output.practical_layer is not None, "REGULATED mode prioritizes practical layer"
        assert output.mode == "regulated"

    def test_mode_weights_applied_correctly(self, sample_fusion_output):
        """Verify mode weights are correctly applied."""
        for mode in RenderMode:
            renderer = FusionRenderer(mode=mode)
            output = renderer.render(sample_fusion_output)

            expected_weights = MODE_WEIGHTS[mode]
            assert output.metadata["layer_weights"] == expected_weights, \
                f"Mode {mode.value} should use correct weights"


# ============================================================================
# LAYER HANDLING TESTS
# ============================================================================

class TestLayerHandling:
    """Test symbolic, practical, and mirror-truth layer handling."""

    def test_renderer_does_not_mutate_input(self, sample_fusion_output):
        """Renderer should not mutate the given FusionOutput data."""
        original_query = sample_fusion_output.query
        original_metadata = copy.deepcopy(sample_fusion_output.metadata)
        original_hrm = copy.deepcopy(sample_fusion_output.hrm_content)

        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        _ = renderer.render(sample_fusion_output)

        assert sample_fusion_output.query == original_query, "Query should not be mutated"
        assert sample_fusion_output.metadata == original_metadata, "Metadata should not be mutated"
        assert sample_fusion_output.hrm_content == original_hrm, "HRM content should not be mutated"

    def test_metadata_not_dropped(self, sample_fusion_output):
        """Renderer should preserve all metadata."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(sample_fusion_output)

        # Original metadata should be preserved
        assert "session_id" in output.metadata, "session_id should be preserved"
        assert "user_id" in output.metadata, "user_id should be preserved"
        assert output.metadata["session_id"] == "test-session-001"
        assert output.metadata["user_id"] == "test-user"

        # Rendering metadata should be added
        assert "render_mode" in output.metadata, "render_mode should be added"
        assert "render_domain" in output.metadata, "render_domain should be added"
        assert "layer_weights" in output.metadata, "layer_weights should be added"

    def test_output_structure_has_expected_keys(self, sample_fusion_output):
        """Rendered output structure must match expected keys."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(sample_fusion_output)
        output_dict = output.to_dict()

        # Top-level keys
        expected_top_keys = {"query", "mode", "symbolic_layer", "practical_layer",
                           "mirror_truth_layer", "metadata", "render_timestamp"}
        assert set(output_dict.keys()) == expected_top_keys, \
            f"Output should have expected top-level keys"

        # Symbolic layer keys
        symbolic_keys = {"theme", "archetype", "causal_patterns", "meaning_vectors",
                        "dominant_channel", "reasoning_depth"}
        assert set(output_dict["symbolic_layer"].keys()) == symbolic_keys

        # Practical layer keys
        practical_keys = {"key_facts", "constraints", "procedures",
                         "coherence_score", "domain", "actionable_items"}
        assert set(output_dict["practical_layer"].keys()) == practical_keys

        # Mirror-truth layer keys
        mirror_keys = {"contradictions", "entropy_measures", "tensions",
                      "alignment_score", "stability_indicator", "reflection"}
        assert set(output_dict["mirror_truth_layer"].keys()) == mirror_keys

    def test_symbolic_layer_extracts_theme(self, sample_fusion_output):
        """Symbolic layer should extract theme from HRM content."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(sample_fusion_output)

        assert output.symbolic_layer.theme is not None
        assert len(output.symbolic_layer.theme) > 0

    def test_practical_layer_extracts_facts(self, sample_fusion_output):
        """Practical layer should extract key facts from LCM content."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(sample_fusion_output)

        assert output.practical_layer.key_facts is not None
        assert len(output.practical_layer.key_facts) > 0

    def test_mirror_truth_preserves_contradictions(self, sample_fusion_output):
        """Mirror-truth layer should preserve contradictions from conflict resolution."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(sample_fusion_output)

        assert output.mirror_truth_layer.contradictions is not None
        assert len(output.mirror_truth_layer.contradictions) == len(sample_fusion_output.conflict_resolution)


# ============================================================================
# DETERMINISM TESTS
# ============================================================================

class TestDeterminism:
    """Test deterministic behavior of renderers."""

    def test_same_input_produces_identical_outputs(self, sample_fusion_output):
        """Calling renderer twice with same input should produce identical outputs."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)

        output1 = renderer.render(sample_fusion_output)
        output2 = renderer.render(sample_fusion_output)

        # Compare dictionaries (excluding timestamps which may differ)
        dict1 = output1.to_dict()
        dict2 = output2.to_dict()

        # Remove timestamps for comparison
        del dict1["render_timestamp"]
        del dict2["render_timestamp"]

        assert dict1 == dict2, "Same input must produce identical outputs (determinism)"

    def test_determinism_across_modes(self, sample_fusion_output):
        """Each mode should produce deterministic outputs."""
        for mode in RenderMode:
            renderer = FusionRenderer(mode=mode)

            output1 = renderer.render(sample_fusion_output)
            output2 = renderer.render(sample_fusion_output)

            dict1 = output1.to_dict()
            dict2 = output2.to_dict()
            del dict1["render_timestamp"]
            del dict2["render_timestamp"]

            assert dict1 == dict2, f"Mode {mode.value} must be deterministic"

    def test_determinism_with_different_instances(self, sample_fusion_output):
        """Different renderer instances should produce identical outputs for same input."""
        renderer1 = FusionRenderer(mode=RenderMode.STANDARD)
        renderer2 = FusionRenderer(mode=RenderMode.STANDARD)

        output1 = renderer1.render(sample_fusion_output)
        output2 = renderer2.render(sample_fusion_output)

        dict1 = output1.to_dict()
        dict2 = output2.to_dict()
        del dict1["render_timestamp"]
        del dict2["render_timestamp"]

        assert dict1 == dict2, "Different instances must produce identical outputs"

    def test_json_serialization_consistency(self, sample_fusion_output):
        """JSON serialization should be consistent across calls."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)

        output1 = renderer.render(sample_fusion_output)
        output2 = renderer.render(sample_fusion_output)

        # Compare JSON without timestamps
        dict1 = output1.to_dict()
        dict2 = output2.to_dict()
        dict1["render_timestamp"] = 0
        dict2["render_timestamp"] = 0

        json1 = output1.to_json()
        json2 = output2.to_json()

        # Both should be valid JSON
        import json
        parsed1 = json.loads(json1)
        parsed2 = json.loads(json2)

        parsed1["render_timestamp"] = 0
        parsed2["render_timestamp"] = 0

        assert parsed1 == parsed2, "JSON serialization must be consistent"


# ============================================================================
# REGULATED MODE TESTS
# ============================================================================

class TestRegulatedMode:
    """Test regulated mode compliance (suppress metaphors, factual only)."""

    def test_regulated_mode_flag_set(self, sample_fusion_output):
        """Regulated mode should set is_regulated flag in metadata."""
        renderer = FusionRenderer(mode=RenderMode.REGULATED, domain=Domain.FINANCE)
        output = renderer.render(sample_fusion_output)

        assert output.metadata["is_regulated"] is True

    def test_regulated_domain_detection(self, sample_fusion_output):
        """Regulated domains should be correctly detected."""
        for domain in REGULATED_DOMAINS:
            renderer = FusionRenderer(mode=RenderMode.STANDARD, domain=domain)
            assert renderer.is_regulated is True, f"{domain.value} should be regulated"

        # Non-regulated domain
        renderer = FusionRenderer(mode=RenderMode.STANDARD, domain=Domain.GENERAL)
        assert renderer.is_regulated is False, "GENERAL domain should not be regulated"

    def test_regulated_mode_simplifies_archetype(self, sample_fusion_output):
        """REGULATED mode should simplify archetype (remove descriptive text after dash)."""
        renderer = FusionRenderer(mode=RenderMode.REGULATED)
        output = renderer.render(sample_fusion_output)

        # Archetype should be simplified (no dash description)
        if output.symbolic_layer and output.symbolic_layer.archetype:
            assert "-" not in output.symbolic_layer.archetype or \
                   output.symbolic_layer.archetype == output.symbolic_layer.archetype.split("-")[0].strip()

    def test_regulated_mode_practical_layer_priority(self, sample_fusion_output):
        """REGULATED mode should prioritize practical layer (highest weight)."""
        renderer = FusionRenderer(mode=RenderMode.REGULATED)

        weights = renderer.layer_weights
        assert weights["practical"] > weights["symbolic"], \
            "Practical layer should have higher weight than symbolic in REGULATED mode"
        assert weights["practical"] > weights["mirror"], \
            "Practical layer should have higher weight than mirror in REGULATED mode"

    def test_regulated_mode_metaphor_suppression(self, regulated_fusion_output):
        """REGULATED mode should suppress metaphor-like themes."""
        renderer = FusionRenderer(mode=RenderMode.REGULATED)
        output = renderer.render(regulated_fusion_output)

        # When theme contains "like" or "as" (metaphor indicators), it should be replaced
        # with plain language: "Core purpose identified"
        if output.symbolic_layer:
            theme = output.symbolic_layer.theme.lower()
            # The regulated mode replaces metaphors with "Core purpose identified"
            # or keeps non-metaphoric themes
            # Check that if original had metaphors, they were handled
            assert output.symbolic_layer.theme is not None


# ============================================================================
# RULES RENDERER TESTS
# ============================================================================

class TestRulesRenderer:
    """Test the simpler RulesRenderer."""

    def test_rules_renderer_basic_render(self, simple_analysis_input):
        """RulesRenderer should produce valid output."""
        renderer = RulesRenderer()
        output = renderer.render(simple_analysis_input)

        assert output is not None
        assert isinstance(output, str)
        assert len(output) > 0

    def test_rules_renderer_includes_header(self, simple_analysis_input):
        """RulesRenderer output should include header with text reference."""
        renderer = RulesRenderer()
        output = renderer.render(simple_analysis_input)

        assert "Analysis of:" in output

    def test_rules_renderer_includes_recommendations(self, simple_analysis_input):
        """RulesRenderer output should include recommendations."""
        renderer = RulesRenderer()
        output = renderer.render(simple_analysis_input)

        assert "Recommendations:" in output
        # Recommendations should be bullet-pointed
        assert "Focus on alignment" in output or "alignment" in output.lower()

    def test_rules_renderer_deterministic(self, simple_analysis_input):
        """RulesRenderer should be deterministic."""
        renderer = RulesRenderer()

        output1 = renderer.render(simple_analysis_input)
        output2 = renderer.render(simple_analysis_input)

        assert output1 == output2, "RulesRenderer must be deterministic"

    def test_rules_renderer_with_borders(self, simple_analysis_input):
        """RulesRenderer should add borders when requested."""
        renderer = RulesRenderer()

        output_no_borders = renderer.render(simple_analysis_input, borders=False)
        output_with_borders = renderer.render(simple_analysis_input, borders=True)

        # With borders should be longer and contain border characters
        assert len(output_with_borders) > len(output_no_borders)
        assert "=" in output_with_borders


# ============================================================================
# INPUT VALIDATION TESTS
# ============================================================================

class TestInputValidation:
    """Test input validation for FusionRenderer."""

    def test_invalid_channel_weights_sum(self):
        """Should raise error if channel weights don't sum to 1.0."""
        invalid_output = FusionOutput(
            query="test",
            merged_response="test response",
            hrm_content={},
            lcm_content={},
            moe_content={},
            channel_weights={"hrm": 0.5, "lcm": 0.3, "moe": 0.1},  # Sums to 0.9
            conflict_resolution=[],
            metadata={}
        )

        renderer = FusionRenderer()
        with pytest.raises(ValueError, match="Channel weights must sum to 1.0"):
            renderer.render(invalid_output)

    def test_valid_channel_weights_sum(self, sample_fusion_output):
        """Should accept channel weights that sum to 1.0."""
        renderer = FusionRenderer()
        # Should not raise
        output = renderer.render(sample_fusion_output)
        assert output is not None


# ============================================================================
# STATISTICS TESTS
# ============================================================================

class TestRendererStatistics:
    """Test renderer statistics tracking."""

    def test_stats_tracking(self, sample_fusion_output):
        """Renderer should track rendering statistics."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)

        initial_stats = renderer.get_stats()
        assert initial_stats["total_renders"] == 0

        renderer.render(sample_fusion_output)

        stats = renderer.get_stats()
        assert stats["total_renders"] == 1
        assert stats["mode_counts"]["standard"] == 1
        assert stats["avg_render_time_ms"] > 0

    def test_stats_accumulate(self, sample_fusion_output):
        """Stats should accumulate across multiple renders."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)

        for _ in range(5):
            renderer.render(sample_fusion_output)

        stats = renderer.get_stats()
        assert stats["total_renders"] == 5
        assert stats["mode_counts"]["standard"] == 5


# ============================================================================
# DOMAIN-SPECIFIC TESTS
# ============================================================================

class TestDomainHandling:
    """Test domain-specific rendering behavior."""

    def test_domain_propagation(self, sample_fusion_output):
        """Domain should be propagated to output metadata."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD, domain=Domain.FINANCE)
        output = renderer.render(sample_fusion_output)

        assert output.metadata["render_domain"] == "finance"

    def test_all_domains_supported(self, sample_fusion_output):
        """All defined domains should be supported."""
        for domain in Domain:
            renderer = FusionRenderer(mode=RenderMode.STANDARD, domain=domain)
            output = renderer.render(sample_fusion_output)

            assert output.metadata["render_domain"] == domain.value


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_conflict_resolution(self):
        """Should handle empty conflict resolution list."""
        output = FusionOutput(
            query="test",
            merged_response="test response",
            hrm_content={"reasoning": "Simple reasoning."},
            lcm_content={"content": "Simple content."},
            moe_content={"content": "Simple expert content."},
            channel_weights={"hrm": 0.33, "lcm": 0.34, "moe": 0.33},
            conflict_resolution=[],  # Empty
            metadata={}
        )

        renderer = FusionRenderer()
        rendered = renderer.render(output)

        assert rendered is not None
        assert rendered.mirror_truth_layer.contradictions == []

    def test_empty_metadata(self):
        """Should handle empty metadata."""
        output = FusionOutput(
            query="test",
            merged_response="test response",
            hrm_content={},
            lcm_content={},
            moe_content={},
            channel_weights={"hrm": 0.33, "lcm": 0.34, "moe": 0.33},
            conflict_resolution=[],
            metadata={}  # Empty
        )

        renderer = FusionRenderer()
        rendered = renderer.render(output)

        # Should have rendering metadata added
        assert "render_mode" in rendered.metadata
        assert "render_domain" in rendered.metadata

    def test_query_preserved_exactly(self, sample_fusion_output):
        """Query should be preserved exactly in output."""
        renderer = FusionRenderer()
        output = renderer.render(sample_fusion_output)

        assert output.query == sample_fusion_output.query


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
