"""
Test Suite: Fusion Renderer Mapper Profile Integration
========================================================

Tests the mapper profile integration in FusionRenderer.

Test Cases:
1. HRM adds granularity markers
2. LCM collapses symbolic layer
3. LAM injects temporal framing phrase markers
"""

import pytest
from symbolu.mechanical.renderer.fusion_renderer import (
    FusionRenderer, FusionOutput, RenderMode, Domain,
    RenderedOutput
)
from symbolu.mechanical.pipeline.models import MapperProfile


@pytest.fixture
def base_fusion_output():
    """Create a base fusion output for testing."""
    return FusionOutput(
        query="Test query",
        merged_response="Test response with multiple points. First point here. Second point there.",
        hrm_content={
            "reasoning": "This is a test reasoning. Because of X, therefore Y."
        },
        lcm_content={
            "content": "Key fact one. Key fact two. Key fact three. Key fact four. Key fact five."
        },
        moe_content={
            "content": "Domain expertise here. Must consider constraints. Cannot ignore limitations.",
            "domain": "test"
        },
        channel_weights={"hrm": 0.4, "lcm": 0.3, "moe": 0.3},
        conflict_resolution=[],
        metadata={}
    )


@pytest.fixture
def renderer():
    """Create a fusion renderer instance."""
    return FusionRenderer(mode=RenderMode.STANDARD, domain=Domain.GENERAL)


def test_hrm_adds_granularity_markers(base_fusion_output, renderer):
    """Test that HRM profile adds granularity markers to symbolic layer."""
    # Render base output
    rendered = renderer.render(base_fusion_output)

    # Create HRM profile
    hrm_profile = MapperProfile(
        resolution_level="high",
        arc_mode="none",
        detail_bias=0.8,
        practical_bias=0.3,
        reflective_bias=0.6
    )

    # Apply mapper profile
    modulated = renderer.apply_mapper_profile(rendered, hrm_profile)

    # Assertions
    assert modulated is not None
    assert modulated.symbolic_layer is not None

    # Check for HRM granularity markers
    theme = modulated.symbolic_layer.theme
    archetype = modulated.symbolic_layer.archetype

    assert any([
        "[Examined in detail]" in theme,
        "specifically" in theme.lower(),
        "precisely" in theme.lower()
    ]), f"Expected granularity markers in theme, got: {theme}"

    assert "high-resolution" in archetype.lower(), \
        f"Expected 'high-resolution' in archetype, got: {archetype}"

    # Check for enhanced causal patterns
    patterns = modulated.symbolic_layer.causal_patterns
    assert any("Fine-grained" in p or "nuance" in p for p in patterns), \
        f"Expected fine-grained causal patterns, got: {patterns}"

    # Check reasoning depth increased
    assert modulated.symbolic_layer.reasoning_depth > rendered.symbolic_layer.reasoning_depth, \
        "Expected reasoning depth to increase with HRM"


def test_lcm_collapses_symbolic_layer(base_fusion_output, renderer):
    """Test that LCM profile collapses symbolic layer to minimal."""
    # Render base output
    rendered = renderer.render(base_fusion_output)

    # Create LCM profile
    lcm_profile = MapperProfile(
        resolution_level="low",
        arc_mode="none",
        detail_bias=0.2,
        practical_bias=0.9,
        reflective_bias=0.2
    )

    # Apply mapper profile
    modulated = renderer.apply_mapper_profile(rendered, lcm_profile)

    # Assertions
    assert modulated is not None
    assert modulated.symbolic_layer is not None

    # Check symbolic layer is collapsed
    assert "Pragmatic" in modulated.symbolic_layer.archetype, \
        f"Expected 'Pragmatic' archetype for LCM, got: {modulated.symbolic_layer.archetype}"

    # Check causal patterns reduced (max 1)
    assert len(modulated.symbolic_layer.causal_patterns) <= 1, \
        f"Expected max 1 causal pattern for LCM, got: {len(modulated.symbolic_layer.causal_patterns)}"

    # Check reasoning depth decreased
    assert modulated.symbolic_layer.reasoning_depth < rendered.symbolic_layer.reasoning_depth, \
        "Expected reasoning depth to decrease with LCM"

    # Check practical layer prioritized
    assert modulated.practical_layer is not None
    assert len(modulated.practical_layer.key_facts) <= 3, \
        f"Expected max 3 key facts for LCM, got: {len(modulated.practical_layer.key_facts)}"

    # Check mirror layer minimized
    assert modulated.mirror_truth_layer is not None
    assert "Minimal reflection" in str(modulated.mirror_truth_layer.tensions) or \
           "Practical focus" in modulated.mirror_truth_layer.reflection, \
        "Expected minimal reflection in mirror layer for LCM"


def test_lam_injects_temporal_framing(base_fusion_output, renderer):
    """Test that LAM profile injects temporal framing phrase markers."""
    # Render base output
    rendered = renderer.render(base_fusion_output)

    # Create LAM profile with temporal arc
    lam_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="temporal",
        detail_bias=0.5,
        practical_bias=0.3,
        reflective_bias=0.8
    )

    # Apply mapper profile
    modulated = renderer.apply_mapper_profile(rendered, lam_profile)

    # Assertions
    assert modulated is not None
    assert modulated.symbolic_layer is not None

    # Check for temporal framing in theme
    theme = modulated.symbolic_layer.theme
    assert "Across time" in theme or "temporal" in theme.lower(), \
        f"Expected temporal framing in theme, got: {theme}"

    # Check for long-arc pattern text
    patterns = modulated.symbolic_layer.causal_patterns
    assert any("temporal pattern" in p.lower() or "broader pattern" in p.lower() for p in patterns), \
        f"Expected temporal pattern text, got: {patterns}"

    # Check mirror layer has arc markers
    assert modulated.mirror_truth_layer is not None
    tensions = modulated.mirror_truth_layer.tensions
    assert any("Pattern continuity" in t or "Temporal coherence" in t for t in tensions), \
        f"Expected arc markers in tensions, got: {tensions}"

    # Check for arc reflection
    reflection = modulated.mirror_truth_layer.reflection
    assert "temporal" in reflection.lower() or "pattern" in reflection.lower(), \
        f"Expected temporal reflection, got: {reflection}"


def test_lam_identity_arc_mode(base_fusion_output, renderer):
    """Test that LAM profile with identity arc mode injects identity framing."""
    # Render base output
    rendered = renderer.render(base_fusion_output)

    # Create LAM profile with identity arc
    lam_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="identity",
        detail_bias=0.5,
        practical_bias=0.3,
        reflective_bias=0.8
    )

    # Apply mapper profile
    modulated = renderer.apply_mapper_profile(rendered, lam_profile)

    # Check for identity framing
    theme = modulated.symbolic_layer.theme
    assert "identity evolution" in theme.lower(), \
        f"Expected identity framing in theme, got: {theme}"

    # Check for identity markers in mirror layer
    tensions = modulated.mirror_truth_layer.tensions
    assert any("Identity tension" in t or "Self-concept" in t for t in tensions), \
        f"Expected identity markers, got: {tensions}"


def test_no_profile_returns_unchanged(base_fusion_output, renderer):
    """Test that None profile returns output unchanged."""
    # Render base output
    rendered = renderer.render(base_fusion_output)

    # Apply None profile
    modulated = renderer.apply_mapper_profile(rendered, None)

    # Should be the same object
    assert modulated is rendered


def test_neutral_profile_returns_unchanged(base_fusion_output, renderer):
    """Test that neutral profile (all defaults) returns minimal changes."""
    # Render base output
    rendered = renderer.render(base_fusion_output)

    # Create neutral profile
    neutral_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5
    )

    # Apply mapper profile
    modulated = renderer.apply_mapper_profile(rendered, neutral_profile)

    # Should have same basic structure
    assert modulated.symbolic_layer.theme == rendered.symbolic_layer.theme
    assert modulated.symbolic_layer.archetype == rendered.symbolic_layer.archetype


def test_mapper_profile_metadata_added(base_fusion_output, renderer):
    """Test that mapper profile is recorded in metadata."""
    # Render base output
    rendered = renderer.render(base_fusion_output)

    # Create profile
    profile = MapperProfile(
        resolution_level="high",
        arc_mode="temporal",
        detail_bias=0.8,
        practical_bias=0.3,
        reflective_bias=0.8
    )

    # Apply mapper profile
    modulated = renderer.apply_mapper_profile(rendered, profile)

    # Check metadata
    assert "mapper_profile_applied" in modulated.metadata
    profile_dict = modulated.metadata["mapper_profile_applied"]
    assert profile_dict["resolution_level"] == "high"
    assert profile_dict["arc_mode"] == "temporal"
    assert profile_dict["detail_bias"] == 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
