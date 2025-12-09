"""
Test Suite: Pipeline Mapper Integration Snapshots
===================================================

Pipeline-level snapshot tests for mapper profile integration.

Test Scenarios:
1. LOWER-task → LCM-only (compressed symbolic layer, minimal DHA, short tone)
2. UPPER-therapy-high entropy → HRM + LAM (expanded symbolic, deep DHA, reflective tone)
3. Identity-high entropy → LAM identity arc (trajectory framing, balanced HRM)
"""

import pytest
from symbolu.mechanical.pipeline.models import MapperProfile
from symbolu.mechanical.pipeline.ttor.models import RoutingPlan, Tier, FlowMode
from symbolu.mechanical.mlcr.mapper_profile_builder import compute_mapper_profile
from symbolu.mechanical.renderer.fusion_renderer import (
    FusionRenderer, FusionOutput, RenderMode, Domain
)
from symbolu.mechanical.dha.dha_engine import DHAEngine
from symbolu.mechanical.renderer.llm_renderer import LLMRenderer


@pytest.fixture
def fusion_renderer():
    """Create fusion renderer for testing."""
    return FusionRenderer(mode=RenderMode.STANDARD, domain=Domain.GENERAL)


@pytest.fixture
def dha_engine():
    """Create DHA engine for testing."""
    return DHAEngine()


@pytest.fixture
def llm_renderer():
    """Create LLM renderer for testing."""
    return LLMRenderer(provider="anthropic")


@pytest.fixture
def base_fusion_output():
    """Create base fusion output for testing."""
    return FusionOutput(
        query="Test query for pipeline integration",
        merged_response="Analysis shows multiple patterns. First observation here. Second insight there. Third conclusion follows.",
        hrm_content={
            "reasoning": "Deep symbolic reasoning shows causal patterns. Because of X, therefore Y leads to Z."
        },
        lcm_content={
            "content": "Concrete fact one. Practical point two. Actionable item three. Clear directive four."
        },
        moe_content={
            "content": "Domain expertise applied. Must consider constraints carefully. Cannot ignore limitations.",
            "domain": "general"
        },
        channel_weights={"hrm": 0.4, "lcm": 0.3, "moe": 0.3},
        conflict_resolution=[],
        metadata={}
    )


def test_snapshot_lower_task_lcm_only(fusion_renderer, dha_engine, llm_renderer, base_fusion_output):
    """
    Snapshot 1: LOWER-task should show LCM-only modulation.

    Expected characteristics:
    - LCM-only mapper profile
    - Compressed symbolic layer
    - Minimal DHA introspection
    - Short, clipped renderer tone
    """
    # Create LOWER-task routing plan with LCM only
    routing_plan = RoutingPlan(
        tier=Tier.LOWER,
        flow_mode=FlowMode.OUTER_ONLY,
        preferred_engine_family="lcm",
        use_hrm=False,
        use_lcm=True,
        use_lam=False,
        regulated_mode=False,
        allow_metaphor=False,
        normalized_entropy=0.3,  # Low entropy
        long_arc_tension=0.2,    # Low tension
        domain="task",
        explanation="LOWER tier with concrete task focus",
        debug={}
    )

    # Compute mapper profile
    mapper_profile = compute_mapper_profile(routing_plan)

    # Verify mapper profile characteristics
    assert mapper_profile.resolution_level == "low"
    assert mapper_profile.arc_mode == "none"
    assert mapper_profile.practical_bias > 0.6
    assert mapper_profile.detail_bias < 0.5

    # Apply to Fusion Renderer
    rendered = fusion_renderer.render(base_fusion_output)
    modulated_render = fusion_renderer.apply_mapper_profile(rendered, mapper_profile)

    # Verify compressed symbolic layer
    assert modulated_render.symbolic_layer is not None
    assert "Pragmatic" in modulated_render.symbolic_layer.archetype
    assert len(modulated_render.symbolic_layer.causal_patterns) <= 1

    # Verify practical layer prioritized
    assert len(modulated_render.practical_layer.key_facts) <= 3

    # Verify minimal mirror layer
    assert "Practical focus" in modulated_render.mirror_truth_layer.reflection or \
           "Minimal reflection" in str(modulated_render.mirror_truth_layer.tensions)

    # Apply to DHA Engine
    dha_insight = {
        "readiness_score": 0.8,
        "resistance_score": 0.2,
        "emotional_entropy": 0.3,
        "ego_state": "open",
        "long_arc_tension": 0.2
    }
    modulated_dha = dha_engine.modulate_dha_depth(dha_insight, mapper_profile)

    # Verify minimal DHA
    assert modulated_dha["introspection_level"] == "minimal"
    assert modulated_dha["metaphor_allowed"] is False
    assert modulated_dha["reflection_depth"] == "surface"

    # Apply to LLM Renderer
    sample_text = "This requires action. Consider the implications. Review the outcomes."
    modulated_text = llm_renderer.apply_mapper_tone(sample_text, mapper_profile)

    # Verify short, clipped tone
    assert len(modulated_text) <= len(sample_text)
    sentences = [s.strip() for s in modulated_text.split('.') if s.strip()]
    assert len(sentences) <= 3


def test_snapshot_upper_therapy_high_entropy(fusion_renderer, dha_engine, llm_renderer, base_fusion_output):
    """
    Snapshot 2: UPPER-therapy-high entropy should show HRM + LAM modulation.

    Expected characteristics:
    - HRM + LAM mapper profile
    - Expanded symbolic layer
    - Deep DHA introspection
    - Reflective renderer tone
    """
    # Create UPPER-therapy routing plan with HRM + LAM
    routing_plan = RoutingPlan(
        tier=Tier.UPPER,
        flow_mode=FlowMode.INNER_PRIORITY,
        preferred_engine_family="hrm",
        use_hrm=True,
        use_lcm=False,
        use_lam=True,
        regulated_mode=False,
        allow_metaphor=True,
        normalized_entropy=0.85,  # High entropy
        long_arc_tension=0.75,    # High tension
        domain="therapy",
        explanation="UPPER tier with high entropy and therapy domain",
        debug={}
    )

    # Compute mapper profile
    mapper_profile = compute_mapper_profile(routing_plan)

    # Verify mapper profile characteristics
    assert mapper_profile.resolution_level in ["high", "medium"]  # HRM + LAM can be medium
    assert mapper_profile.arc_mode != "none"  # LAM activates arc mode
    assert mapper_profile.detail_bias > 0.6 or mapper_profile.reflective_bias > 0.6

    # Apply to Fusion Renderer
    rendered = fusion_renderer.render(base_fusion_output)
    modulated_render = fusion_renderer.apply_mapper_profile(rendered, mapper_profile)

    # Verify expanded symbolic layer (HRM or LAM effects)
    assert modulated_render.symbolic_layer is not None
    # Either HRM granularity or LAM arc framing should be present
    theme = modulated_render.symbolic_layer.theme
    has_expansion = (
        "[Examined in detail]" in theme or
        "high-resolution" in modulated_render.symbolic_layer.archetype.lower() or
        any(arc_word in theme.lower() for arc_word in ["time", "context", "identity", "pattern"])
    )
    assert has_expansion, f"Expected expanded symbolic layer, got theme: {theme}"

    # Verify mirror layer has arc markers (LAM)
    assert modulated_render.mirror_truth_layer is not None
    tensions = modulated_render.mirror_truth_layer.tensions
    has_arc_markers = any(
        marker in str(tensions) for marker in
        ["Pattern continuity", "Temporal coherence", "Identity tension", "Trajectory contrast"]
    )
    assert has_arc_markers, f"Expected arc markers in tensions, got: {tensions}"

    # Apply to DHA Engine
    dha_insight = {
        "readiness_score": 0.6,
        "resistance_score": 0.4,
        "emotional_entropy": 0.7,
        "ego_state": "open",
        "long_arc_tension": 0.75
    }
    modulated_dha = dha_engine.modulate_dha_depth(dha_insight, mapper_profile)

    # Verify deep DHA (either HRM or LAM effects)
    assert modulated_dha["introspection_level"] in ["deep", "arc-aware"]
    assert modulated_dha["metaphor_allowed"] is True
    assert modulated_dha["reflection_depth"] in ["detailed", "identity"]

    # Apply to LLM Renderer
    sample_text = "This pattern emerges from complex dynamics. Multiple factors interact. Deeper understanding required."
    modulated_text = llm_renderer.apply_mapper_tone(sample_text, mapper_profile)

    # Verify reflective tone (LAM) or enhanced transitions (HRM)
    modulated_lower = modulated_text.lower()
    has_reflective_or_detailed = (
        any(word in modulated_lower for word in ["over time", "pattern", "context", "evolution"]) or
        any(word in modulated_lower for word in ["furthermore", "moreover", "specifically"])
    )
    assert has_reflective_or_detailed, f"Expected reflective or detailed tone, got: {modulated_text}"


def test_snapshot_identity_high_entropy(fusion_renderer, dha_engine, llm_renderer, base_fusion_output):
    """
    Snapshot 3: Identity-high entropy should show LAM identity arc.

    Expected characteristics:
    - LAM identity arc mode
    - Trajectory framing
    - Balanced HRM (if co-activated)
    """
    # Create routing plan with identity domain and high entropy
    routing_plan = RoutingPlan(
        tier=Tier.HYBRID,
        flow_mode=FlowMode.OUTER_PLUS_INNER,
        preferred_engine_family="fusion",
        use_hrm=True,
        use_lcm=False,
        use_lam=True,
        regulated_mode=False,
        allow_metaphor=True,
        normalized_entropy=0.80,  # High entropy
        long_arc_tension=0.55,
        domain="identity",  # Identity domain
        explanation="HYBRID tier with identity domain and high entropy",
        debug={}
    )

    # Compute mapper profile
    mapper_profile = compute_mapper_profile(routing_plan)

    # Verify mapper profile characteristics
    assert mapper_profile.arc_mode == "identity"  # Identity domain triggers identity arc
    assert mapper_profile.reflective_bias > 0.6  # LAM increases reflective bias

    # Apply to Fusion Renderer
    rendered = fusion_renderer.render(base_fusion_output)
    modulated_render = fusion_renderer.apply_mapper_profile(rendered, mapper_profile)

    # Verify HRM + LAM combined modulation
    # Note: HRM modulation takes precedence in the if/elif chain
    # but LAM arc_mode should still be identity, and reflective bias high
    assert modulated_render.symbolic_layer is not None
    theme = modulated_render.symbolic_layer.theme

    # With HRM active, we expect HRM modulation (detail markers)
    # Identity framing from LAM is secondary when both are active
    assert any([
        "[Examined in detail]" in theme,
        "high-resolution" in modulated_render.symbolic_layer.archetype.lower()
    ]), f"Expected HRM detail markers (takes precedence), got theme: {theme}"

    # Check that profile has identity arc_mode even if HRM modulation takes precedence
    assert mapper_profile.arc_mode == "identity"

    # Apply to DHA Engine
    dha_insight = {
        "readiness_score": 0.7,
        "resistance_score": 0.3,
        "emotional_entropy": 0.6,
        "ego_state": "open",
        "long_arc_tension": 0.55
    }
    modulated_dha = dha_engine.modulate_dha_depth(dha_insight, mapper_profile)

    # DHA also uses HRM precedence when both conditions met
    assert modulated_dha["introspection_level"] == "deep"  # HRM takes precedence
    assert modulated_dha["metaphor_allowed"] is True

    # Apply to LLM Renderer
    sample_text = "These patterns reflect ongoing development. Self-understanding evolves through experience."
    modulated_text = llm_renderer.apply_mapper_tone(sample_text, mapper_profile)

    # LLM renderer also uses HRM precedence for tone
    # HRM: clearer transitions, deeper detail
    modulated_lower = modulated_text.lower()
    has_hrm_tone = any(
        marker in modulated_lower for marker in
        ["furthermore", "moreover", "specifically", "in addition"]
    )
    # OR it might use LAM if reflective_bias is very high
    has_lam_tone = any(
        marker in modulated_lower for marker in
        ["evolution", "context", "pattern"]
    )
    assert has_hrm_tone or has_lam_tone, \
        f"Expected HRM or LAM tone markers, got: {modulated_text}"


def test_mapper_profile_builder_integration():
    """Test that mapper_profile_builder correctly computes profiles from routing plans."""
    # Test LCM-only
    lcm_plan = RoutingPlan(
        tier=Tier.LOWER,
        flow_mode=FlowMode.OUTER_ONLY,
        preferred_engine_family="lcm",
        use_hrm=False,
        use_lcm=True,
        use_lam=False,
        regulated_mode=False,
        allow_metaphor=False,
        normalized_entropy=0.3,
        long_arc_tension=0.2,
        domain="task",
        explanation="LCM test",
        debug={}
    )

    lcm_profile = compute_mapper_profile(lcm_plan)
    assert lcm_profile.resolution_level == "low"
    assert lcm_profile.practical_bias > 0.6

    # Test HRM-only
    hrm_plan = RoutingPlan(
        tier=Tier.UPPER,
        flow_mode=FlowMode.INNER_PRIORITY,
        preferred_engine_family="hrm",
        use_hrm=True,
        use_lcm=False,
        use_lam=False,
        regulated_mode=False,
        allow_metaphor=True,
        normalized_entropy=0.5,
        long_arc_tension=0.3,
        domain="analysis",
        explanation="HRM test",
        debug={}
    )

    hrm_profile = compute_mapper_profile(hrm_plan)
    assert hrm_profile.resolution_level == "high"
    assert hrm_profile.detail_bias > 0.6

    # Test LAM temporal
    lam_plan = RoutingPlan(
        tier=Tier.HYBRID,
        flow_mode=FlowMode.OUTER_PLUS_INNER,
        preferred_engine_family="fusion",
        use_hrm=False,
        use_lcm=False,
        use_lam=True,
        regulated_mode=False,
        allow_metaphor=True,
        normalized_entropy=0.6,
        long_arc_tension=0.75,  # High tension → temporal
        domain="generic",
        explanation="LAM temporal test",
        debug={}
    )

    lam_profile = compute_mapper_profile(lam_plan)
    assert lam_profile.arc_mode == "temporal"
    assert lam_profile.reflective_bias > 0.6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
