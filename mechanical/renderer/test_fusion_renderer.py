"""
Test Suite for SOULPI Fusion Renderer v3.0
==========================================

Comprehensive testing following the specification requirements:
- Unit tests for each layer builder
- Integration tests for full pipeline
- Mode-specific behavior validation
- Determinism verification
- Edge case handling

Run with: pytest test_fusion_renderer.py -v
"""

import pytest
import json
import numpy as np
from datetime import datetime
from fusion_renderer import (
    FusionRenderer,
    FusionOutput,
    SymbolicLayer,
    PracticalLayer,
    MirrorTruthLayer,
    RenderedOutput,
    RenderMode,
    Domain,
    render_fusion_output
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_fusion_output():
    """Create sample FusionOutput for testing"""
    return FusionOutput(
        query="What is the meaning of consciousness?",
        merged_response="Consciousness is the state of awareness. It involves perception, thought, and self-reflection. Different theories propose various mechanisms.",
        hrm_content={
            "reasoning": "Consciousness emerges from symbolic integration. Therefore, awareness requires recursive self-reference. This suggests a hierarchical structure.",
            "depth": 0.8
        },
        lcm_content={
            "content": "Consciousness is awareness. It includes perception. It involves cognition. Self-reflection is key.",
            "clarity": 0.9
        },
        moe_content={
            "content": "Neuroscience studies neural correlates. Must consider brain activity. Step 1: Measure signals. Step 2: Analyze patterns.",
            "domain": "neuroscience",
            "constraints": ["Limited by current technology", "Cannot measure subjective experience directly"],
            "procedures": ["Measure neural activity", "Correlate with reports", "Build models"]
        },
        channel_weights={
            "hrm": 0.5,
            "lcm": 0.3,
            "moe": 0.2
        },
        conflict_resolution=[
            {
                "source1": "hrm",
                "source2": "moe",
                "type": "abstraction_level",
                "resolution": "Hierarchical integration"
            }
        ],
        metadata={
            "query_type": "philosophical",
            "complexity": "high"
        }
    )


@pytest.fixture
def minimal_fusion_output():
    """Create minimal FusionOutput for edge case testing"""
    return FusionOutput(
        query="Test query",
        merged_response="Test response",
        hrm_content={},
        lcm_content={},
        moe_content={},
        channel_weights={
            "hrm": 0.33,
            "lcm": 0.33,
            "moe": 0.34
        },
        conflict_resolution=[],
        metadata={}
    )


# ============================================================================
# UNIT TESTS - LAYER BUILDERS
# ============================================================================

class TestSymbolicLayer:
    """Test Symbolic Layer builder"""
    
    def test_build_symbolic_layer(self, sample_fusion_output):
        """Test symbolic layer construction"""
        renderer = FusionRenderer()
        layer = renderer._build_symbolic_layer(sample_fusion_output)
        
        assert isinstance(layer, SymbolicLayer)
        assert layer.theme != ""
        assert layer.archetype != ""
        assert len(layer.causal_patterns) > 0
        assert len(layer.meaning_vectors) > 0
        assert layer.dominant_channel == "hrm"  # Highest weight
        assert 0.0 <= layer.reasoning_depth <= 1.0
    
    def test_extract_theme(self, sample_fusion_output):
        """Test theme extraction"""
        renderer = FusionRenderer()
        theme = renderer._extract_theme(sample_fusion_output.hrm_content)
        
        assert theme != ""
        assert isinstance(theme, str)
    
    def test_identify_archetype(self, sample_fusion_output):
        """Test archetype identification"""
        renderer = FusionRenderer()
        archetype = renderer._identify_archetype(sample_fusion_output.channel_weights)
        
        assert "Philosopher" in archetype  # HRM dominant
    
    def test_extract_causal_patterns(self, sample_fusion_output):
        """Test causal pattern extraction"""
        renderer = FusionRenderer()
        patterns = renderer._extract_causal_patterns(sample_fusion_output.hrm_content)
        
        assert len(patterns) > 0
        assert any("therefore" in p.lower() for p in patterns)
    
    def test_compute_meaning_vectors(self, sample_fusion_output):
        """Test meaning vector computation"""
        renderer = FusionRenderer()
        vectors = renderer._compute_meaning_vectors(sample_fusion_output)
        
        assert "abstractness" in vectors
        assert "clarity" in vectors
        assert "practicality" in vectors
        assert "complexity" in vectors
        assert all(0.0 <= v <= 1.0 for v in [vectors["abstractness"], 
                                               vectors["clarity"], 
                                               vectors["practicality"]])


class TestPracticalLayer:
    """Test Practical Layer builder"""
    
    def test_build_practical_layer(self, sample_fusion_output):
        """Test practical layer construction"""
        renderer = FusionRenderer()
        layer = renderer._build_practical_layer(sample_fusion_output)
        
        assert isinstance(layer, PracticalLayer)
        assert len(layer.key_facts) > 0
        assert len(layer.constraints) > 0
        assert len(layer.procedures) > 0
        assert 0.0 <= layer.coherence_score <= 1.0
        assert layer.domain != ""
        assert len(layer.actionable_items) > 0
    
    def test_extract_key_facts(self, sample_fusion_output):
        """Test key fact extraction"""
        renderer = FusionRenderer()
        facts = renderer._extract_key_facts(sample_fusion_output.lcm_content)
        
        assert len(facts) > 0
        assert all(isinstance(f, str) for f in facts)
    
    def test_extract_constraints(self, sample_fusion_output):
        """Test constraint extraction"""
        renderer = FusionRenderer()
        constraints = renderer._extract_constraints(sample_fusion_output.moe_content)
        
        assert len(constraints) > 0
        assert all(isinstance(c, str) for c in constraints)
    
    def test_extract_procedures(self, sample_fusion_output):
        """Test procedure extraction"""
        renderer = FusionRenderer()
        procedures = renderer._extract_procedures(sample_fusion_output.moe_content)
        
        assert len(procedures) > 0
        assert all(isinstance(p, str) for p in procedures)
    
    def test_extract_actionable_items(self, sample_fusion_output):
        """Test actionable item extraction"""
        renderer = FusionRenderer()
        items = renderer._extract_actionable_items(sample_fusion_output)
        
        assert len(items) > 0
        assert all(isinstance(i, str) for i in items)


class TestMirrorTruthLayer:
    """Test Mirror-Truth Layer builder"""
    
    def test_build_mirror_truth_layer(self, sample_fusion_output):
        """Test mirror-truth layer construction"""
        renderer = FusionRenderer()
        layer = renderer._build_mirror_truth_layer(sample_fusion_output)
        
        assert isinstance(layer, MirrorTruthLayer)
        assert isinstance(layer.contradictions, list)
        assert len(layer.entropy_measures) > 0
        assert len(layer.tensions) > 0
        assert 0.0 <= layer.alignment_score <= 1.0
        assert layer.stability_indicator != ""
        assert layer.reflection != ""
    
    def test_compute_entropy_measures(self, sample_fusion_output):
        """Test entropy measure computation"""
        renderer = FusionRenderer()
        measures = renderer._compute_entropy_measures(sample_fusion_output)
        
        assert "channel_entropy" in measures
        assert "conflict_entropy" in measures
        assert "response_entropy" in measures
        assert all(0.0 <= v <= 10.0 for v in measures.values())
    
    def test_identify_tensions(self, sample_fusion_output):
        """Test tension identification"""
        renderer = FusionRenderer()
        tensions = renderer._identify_tensions(sample_fusion_output)
        
        assert len(tensions) > 0
        assert all(isinstance(t, str) for t in tensions)
    
    def test_compute_alignment(self, sample_fusion_output):
        """Test alignment computation"""
        renderer = FusionRenderer()
        alignment = renderer._compute_alignment(sample_fusion_output.channel_weights)
        
        assert 0.0 <= alignment <= 1.0
    
    def test_assess_stability(self, sample_fusion_output):
        """Test stability assessment"""
        renderer = FusionRenderer()
        entropy_measures = {"test": 0.5}
        stability = renderer._assess_stability(entropy_measures, 0.7)
        
        assert stability in ["STABLE - Low entropy, high alignment",
                           "UNSTABLE - High entropy or low alignment",
                           "MODERATE - Balanced state"]
    
    def test_generate_reflection(self, sample_fusion_output):
        """Test reflection generation"""
        renderer = FusionRenderer()
        reflection = renderer._generate_reflection(
            sample_fusion_output.conflict_resolution,
            ["test tension"],
            0.7
        )
        
        assert reflection != ""
        assert isinstance(reflection, str)


# ============================================================================
# INTEGRATION TESTS - FULL PIPELINE
# ============================================================================

class TestFullPipeline:
    """Test complete rendering pipeline"""
    
    def test_render_standard_mode(self, sample_fusion_output):
        """Test standard mode rendering"""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(sample_fusion_output)
        
        assert isinstance(output, RenderedOutput)
        assert output.symbolic_layer is not None
        assert output.practical_layer is not None
        assert output.mirror_truth_layer is not None
        assert output.mode == "standard"
    
    def test_render_minimal_mode(self, sample_fusion_output):
        """Test minimal mode rendering"""
        renderer = FusionRenderer(mode=RenderMode.MINIMAL)
        output = renderer.render(sample_fusion_output)
        
        assert isinstance(output, RenderedOutput)
        assert output.symbolic_layer is None
        assert output.practical_layer is not None
        assert output.mirror_truth_layer is None
        assert output.mode == "minimal"
    
    def test_render_symbolic_mode(self, sample_fusion_output):
        """Test symbolic mode rendering"""
        renderer = FusionRenderer(mode=RenderMode.SYMBOLIC)
        output = renderer.render(sample_fusion_output)
        
        assert isinstance(output, RenderedOutput)
        assert output.symbolic_layer is not None
        assert output.practical_layer is not None
        assert output.mirror_truth_layer is not None
        assert output.mode == "symbolic"
        # Practical layer should be condensed
        assert len(output.practical_layer.key_facts) <= 2
    
    def test_render_regulated_mode(self, sample_fusion_output):
        """Test regulated mode rendering"""
        renderer = FusionRenderer(mode=RenderMode.REGULATED, domain=Domain.FINANCE)
        output = renderer.render(sample_fusion_output)
        
        assert isinstance(output, RenderedOutput)
        assert output.mode == "regulated"
        assert output.metadata["is_regulated"] is True
    
    def test_metadata_propagation(self, sample_fusion_output):
        """Test exact metadata propagation"""
        renderer = FusionRenderer()
        output = renderer.render(sample_fusion_output)
        
        assert "query_type" in output.metadata
        assert output.metadata["query_type"] == "philosophical"
        assert "render_mode" in output.metadata
        assert "render_domain" in output.metadata
    
    def test_json_serialization(self, sample_fusion_output):
        """Test JSON output serialization"""
        renderer = FusionRenderer()
        output = renderer.render(sample_fusion_output)
        
        json_str = output.to_json()
        assert isinstance(json_str, str)
        
        # Verify valid JSON
        parsed = json.loads(json_str)
        assert parsed["query"] == sample_fusion_output.query
        assert parsed["mode"] == "standard"


# ============================================================================
# MODE-SPECIFIC TESTS
# ============================================================================

class TestRenderModes:
    """Test mode-specific behavior"""
    
    def test_minimal_mode_layers(self, sample_fusion_output):
        """Verify minimal mode shows only practical layer"""
        renderer = FusionRenderer(mode=RenderMode.MINIMAL)
        output = renderer.render(sample_fusion_output)
        
        assert output.symbolic_layer is None
        assert output.practical_layer is not None
        assert output.mirror_truth_layer is None
    
    def test_standard_mode_layers(self, sample_fusion_output):
        """Verify standard mode shows all layers"""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(sample_fusion_output)
        
        assert output.symbolic_layer is not None
        assert output.practical_layer is not None
        assert output.mirror_truth_layer is not None
    
    def test_symbolic_mode_emphasis(self, sample_fusion_output):
        """Verify symbolic mode emphasizes symbolic layer"""
        renderer = FusionRenderer(mode=RenderMode.SYMBOLIC)
        output = renderer.render(sample_fusion_output)
        
        # Symbolic layer should be present
        assert output.symbolic_layer is not None
        # Practical layer should be condensed
        assert len(output.practical_layer.key_facts) <= 2
        assert len(output.practical_layer.actionable_items) <= 1
    
    def test_regulated_mode_restrictions(self, sample_fusion_output):
        """Verify regulated mode applies restrictions"""
        renderer = FusionRenderer(mode=RenderMode.REGULATED, domain=Domain.LEGAL)
        output = renderer.render(sample_fusion_output)
        
        # Check metaphor reduction in symbolic layer
        if output.symbolic_layer:
            assert "like" not in output.symbolic_layer.theme.lower()
            assert "as" not in output.symbolic_layer.theme.lower()
        
        assert output.metadata["is_regulated"] is True


# ============================================================================
# DETERMINISM TESTS
# ============================================================================

class TestDeterminism:
    """Verify deterministic behavior (no LLM randomness)"""
    
    def test_same_input_same_output(self, sample_fusion_output):
        """Test that same input produces same output"""
        renderer = FusionRenderer()
        
        output1 = renderer.render(sample_fusion_output)
        output2 = renderer.render(sample_fusion_output)
        
        # Should produce identical results
        assert output1.query == output2.query
        assert output1.mode == output2.mode
        
        # Symbolic layer determinism
        if output1.symbolic_layer and output2.symbolic_layer:
            assert output1.symbolic_layer.theme == output2.symbolic_layer.theme
            assert output1.symbolic_layer.archetype == output2.symbolic_layer.archetype
        
        # Practical layer determinism
        if output1.practical_layer and output2.practical_layer:
            assert output1.practical_layer.coherence_score == output2.practical_layer.coherence_score
        
        # Mirror-truth layer determinism
        if output1.mirror_truth_layer and output2.mirror_truth_layer:
            assert output1.mirror_truth_layer.alignment_score == output2.mirror_truth_layer.alignment_score
    
    def test_no_random_components(self, sample_fusion_output):
        """Verify no random number generation in output"""
        renderer = FusionRenderer()
        
        # Run multiple times
        outputs = [renderer.render(sample_fusion_output) for _ in range(5)]
        
        # All outputs should be identical
        for i in range(1, len(outputs)):
            assert outputs[0].to_json() == outputs[i].to_json()


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_minimal_content(self, minimal_fusion_output):
        """Test rendering with minimal content"""
        renderer = FusionRenderer()
        output = renderer.render(minimal_fusion_output)
        
        assert isinstance(output, RenderedOutput)
        # Should handle gracefully with defaults
        assert output.symbolic_layer is not None
        assert output.practical_layer is not None
    
    def test_empty_conflict_resolution(self, minimal_fusion_output):
        """Test with no conflicts"""
        renderer = FusionRenderer()
        output = renderer.render(minimal_fusion_output)
        
        assert len(output.mirror_truth_layer.contradictions) == 0
    
    def test_balanced_channel_weights(self):
        """Test with perfectly balanced weights"""
        fusion_output = FusionOutput(
            query="Test",
            merged_response="Test response",
            hrm_content={"reasoning": "Test"},
            lcm_content={"content": "Test"},
            moe_content={"content": "Test"},
            channel_weights={"hrm": 0.333, "lcm": 0.333, "moe": 0.334},
            conflict_resolution=[],
            metadata={}
        )
        
        renderer = FusionRenderer()
        output = renderer.render(fusion_output)
        
        # Should handle balanced weights
        assert output.mirror_truth_layer.alignment_score > 0.8
    
    def test_extreme_weight_imbalance(self):
        """Test with extreme weight imbalance"""
        fusion_output = FusionOutput(
            query="Test",
            merged_response="Test response",
            hrm_content={"reasoning": "Test"},
            lcm_content={"content": "Test"},
            moe_content={"content": "Test"},
            channel_weights={"hrm": 0.9, "lcm": 0.05, "moe": 0.05},
            conflict_resolution=[],
            metadata={}
        )
        
        renderer = FusionRenderer()
        output = renderer.render(fusion_output)
        
        # Should detect imbalance
        assert output.mirror_truth_layer.alignment_score < 0.5
        assert any("imbalance" in t.lower() for t in output.mirror_truth_layer.tensions)
    
    def test_invalid_input(self):
        """Test with invalid input"""
        invalid_output = FusionOutput(
            query="Test",
            merged_response="Test",
            hrm_content={},
            lcm_content={},
            moe_content={},
            channel_weights={"hrm": 0.5, "lcm": 0.3, "moe": 0.3},  # Sums to 1.1
            conflict_resolution=[],
            metadata={}
        )
        
        renderer = FusionRenderer()
        with pytest.raises(ValueError):
            renderer.render(invalid_output)


# ============================================================================
# STATISTICS TESTS
# ============================================================================

class TestStatistics:
    """Test statistics tracking"""
    
    def test_stats_initialization(self):
        """Test initial statistics state"""
        renderer = FusionRenderer()
        stats = renderer.get_stats()
        
        assert stats["total_renders"] == 0
        assert stats["avg_render_time_ms"] == 0.0
        assert all(count == 0 for count in stats["mode_counts"].values())
    
    def test_stats_update(self, sample_fusion_output):
        """Test statistics update after rendering"""
        renderer = FusionRenderer()
        
        renderer.render(sample_fusion_output)
        stats = renderer.get_stats()
        
        assert stats["total_renders"] == 1
        assert stats["avg_render_time_ms"] > 0.0
        assert stats["mode_counts"]["standard"] == 1
    
    def test_multiple_renders_stats(self, sample_fusion_output):
        """Test statistics after multiple renders"""
        renderer = FusionRenderer()
        
        for _ in range(5):
            renderer.render(sample_fusion_output)
        
        stats = renderer.get_stats()
        assert stats["total_renders"] == 5
        assert stats["mode_counts"]["standard"] == 5


# ============================================================================
# CONVENIENCE FUNCTION TESTS
# ============================================================================

class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_render_fusion_output_function(self, sample_fusion_output):
        """Test convenience render function"""
        output = render_fusion_output(sample_fusion_output)
        
        assert isinstance(output, RenderedOutput)
        assert output.mode == "standard"
    
    def test_render_with_custom_mode(self, sample_fusion_output):
        """Test convenience function with custom mode"""
        output = render_fusion_output(
            sample_fusion_output,
            mode=RenderMode.MINIMAL,
            domain=Domain.FINANCE
        )
        
        assert output.mode == "minimal"
        assert output.metadata["render_domain"] == "finance"


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
