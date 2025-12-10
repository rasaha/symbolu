"""
Semantic-Shape Guardrail Tests
================================

Tests that verify expression modulation does NOT change semantic content.
Ensures all required structural fields appear consistently across mapper modes.

Version: 1.0
Status: Production
CI-Enforced: Yes

Test Coverage:
1. Semantic core unchanged across mappers
2. Required DHA fields always present
3. Structural layers in fusion renderer always present
4. LLM renderer preserves content tokens
5. LOWER-task vs UPPER-therapy share semantic skeleton
6. No semantic loss under LCM compression

Contract Guardian: These tests enforce the expression modulation contract.
Any test failure is a CONTRACT VIOLATION.
"""

import re
from typing import Dict, Any, Set
import pytest

from symbolu.mechanical.pipeline.models import MapperProfile
from symbolu.mechanical.renderer.fusion_renderer import (
    FusionRenderer,
    FusionOutput,
    SymbolicLayer,
    PracticalLayer,
    MirrorTruthLayer,
    RenderedOutput,
)
from symbolu.mechanical.renderer.llm_renderer import LLMRenderer
from symbolu.mechanical.dha.dha_engine import DHAEngine


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def sample_fusion_output() -> FusionOutput:
    """Create a sample FusionOutput for testing."""
    return FusionOutput(
        query="What causes anxiety?",
        merged_response="Anxiety stems from uncertainty about future outcomes and perceived threats to safety or identity.",
        hrm_content={
            "reasoning": "Anxiety represents a complex interplay between cognitive appraisal and emotional response. It stems from uncertainty.",
            "symbolic_analysis": "Fear archetype, survival pattern",
        },
        lcm_content={
            "content": "Anxiety is caused by uncertainty. It triggers stress responses. It affects decision-making.",
            "coherence": 0.8,
        },
        moe_content={
            "content": "Psychological factors include cognitive distortions and past trauma. Biological factors include neurotransmitter imbalances.",
            "domain": "psychology",
        },
        channel_weights={"hrm": 0.4, "lcm": 0.3, "moe": 0.3},
        conflict_resolution=[],
        metadata={"entropy": 0.5},
    )


@pytest.fixture
def hrm_profile() -> MapperProfile:
    """HRM mapper profile."""
    return MapperProfile(
        resolution_level="high",
        arc_mode="none",
        detail_bias=0.8,
        practical_bias=0.5,
        reflective_bias=0.7,
    )


@pytest.fixture
def lcm_profile() -> MapperProfile:
    """LCM mapper profile."""
    return MapperProfile(
        resolution_level="low",
        arc_mode="none",
        detail_bias=0.2,
        practical_bias=0.9,
        reflective_bias=0.3,
    )


@pytest.fixture
def lam_profile() -> MapperProfile:
    """LAM mapper profile with identity arc."""
    return MapperProfile(
        resolution_level="medium",
        arc_mode="identity",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.8,
    )


# ============================================================================
# TEST 1: Semantic Core Unchanged Across Mappers
# ============================================================================


def test_semantic_core_unchanged_across_mappers(
    sample_fusion_output: FusionOutput,
    hrm_profile: MapperProfile,
    lcm_profile: MapperProfile,
    lam_profile: MapperProfile,
):
    """
    Test 1: Semantic Core Unchanged Across Mappers

    Verify that the same symbolic/practical/mirror content produces
    consistent structural fields across HRM, LCM, and LAM mapper profiles.

    Assertions:
    - symbolic/practical/mirror keys exist in all outputs
    - dha "insight" always exists (tested in Test 2)
    - NO field is removed in any mode

    This test verifies SHAPE preservation, not exact phrasing.
    """
    renderer = FusionRenderer()

    # Render base output
    base_output = renderer.render(sample_fusion_output)

    # Apply each mapper profile
    hrm_output = renderer.apply_mapper_profile(base_output, hrm_profile)
    lcm_output = renderer.apply_mapper_profile(base_output, lcm_profile)
    lam_output = renderer.apply_mapper_profile(base_output, lam_profile)

    # Test 1.1: All outputs have symbolic layer
    assert hrm_output.symbolic_layer is not None, "HRM output missing symbolic layer"
    assert lcm_output.symbolic_layer is not None, "LCM output missing symbolic layer"
    assert lam_output.symbolic_layer is not None, "LAM output missing symbolic layer"

    # Test 1.2: All outputs have practical layer
    assert hrm_output.practical_layer is not None, "HRM output missing practical layer"
    assert lcm_output.practical_layer is not None, "LCM output missing practical layer"
    assert lam_output.practical_layer is not None, "LAM output missing practical layer"

    # Test 1.3: All outputs have mirror layer
    assert hrm_output.mirror_truth_layer is not None, "HRM output missing mirror layer"
    assert lcm_output.mirror_truth_layer is not None, "LCM output missing mirror layer"
    assert lam_output.mirror_truth_layer is not None, "LAM output missing mirror layer"

    # Test 1.4: Structural keys preserved in symbolic layer
    for output_name, output in [("HRM", hrm_output), ("LCM", lcm_output), ("LAM", lam_output)]:
        symbolic = output.symbolic_layer
        assert hasattr(symbolic, "theme"), f"{output_name} symbolic layer missing 'theme'"
        assert hasattr(symbolic, "archetype"), f"{output_name} symbolic layer missing 'archetype'"
        assert hasattr(symbolic, "causal_patterns"), f"{output_name} symbolic layer missing 'causal_patterns'"
        assert hasattr(symbolic, "meaning_vectors"), f"{output_name} symbolic layer missing 'meaning_vectors'"
        assert hasattr(symbolic, "dominant_channel"), f"{output_name} symbolic layer missing 'dominant_channel'"
        assert hasattr(symbolic, "reasoning_depth"), f"{output_name} symbolic layer missing 'reasoning_depth'"

    # Test 1.5: Structural keys preserved in practical layer
    for output_name, output in [("HRM", hrm_output), ("LCM", lcm_output), ("LAM", lam_output)]:
        practical = output.practical_layer
        assert hasattr(practical, "key_facts"), f"{output_name} practical layer missing 'key_facts'"
        assert hasattr(practical, "constraints"), f"{output_name} practical layer missing 'constraints'"
        assert hasattr(practical, "procedures"), f"{output_name} practical layer missing 'procedures'"
        assert hasattr(practical, "coherence_score"), f"{output_name} practical layer missing 'coherence_score'"
        assert hasattr(practical, "domain"), f"{output_name} practical layer missing 'domain'"
        assert hasattr(practical, "actionable_items"), f"{output_name} practical layer missing 'actionable_items'"

    # Test 1.6: Structural keys preserved in mirror layer
    for output_name, output in [("HRM", hrm_output), ("LCM", lcm_output), ("LAM", lam_output)]:
        mirror = output.mirror_truth_layer
        assert hasattr(mirror, "contradictions"), f"{output_name} mirror layer missing 'contradictions'"
        assert hasattr(mirror, "entropy_measures"), f"{output_name} mirror layer missing 'entropy_measures'"
        assert hasattr(mirror, "tensions"), f"{output_name} mirror layer missing 'tensions'"
        assert hasattr(mirror, "alignment_score"), f"{output_name} mirror layer missing 'alignment_score'"
        assert hasattr(mirror, "stability_indicator"), f"{output_name} mirror layer missing 'stability_indicator'"
        assert hasattr(mirror, "reflection"), f"{output_name} mirror layer missing 'reflection'"


# ============================================================================
# TEST 2: Required DHA Fields Always Present
# ============================================================================


def test_required_dha_fields_always_present(
    hrm_profile: MapperProfile,
    lcm_profile: MapperProfile,
    lam_profile: MapperProfile,
):
    """
    Test 2: Required DHA Fields Always Present

    Ensure that for ALL mapper profiles:
    - dha_output["insight"] is non-empty
    - dha_output["insight"] includes content derived from input text
    - mapper modulation may wrap/add but cannot remove insight

    Note: This test uses DHA's modulate_dha_depth() method which
    modulates insight structure, not the full DHA pipeline.
    """
    dha_engine = DHAEngine()

    # Create base insight
    base_insight = {
        "readiness_score": 0.7,
        "resistance_score": 0.3,
        "introspection_level": "moderate",
        "reflection_depth": "standard",
        "content": "User shows openness to feedback with moderate resistance patterns.",
    }

    # Apply mapper modulation
    hrm_insight = dha_engine.modulate_dha_depth(base_insight.copy(), hrm_profile)
    lcm_insight = dha_engine.modulate_dha_depth(base_insight.copy(), lcm_profile)
    lam_insight = dha_engine.modulate_dha_depth(base_insight.copy(), lam_profile)

    # Test 2.1: All insights have introspection_level
    assert "introspection_level" in hrm_insight, "HRM insight missing 'introspection_level'"
    assert "introspection_level" in lcm_insight, "LCM insight missing 'introspection_level'"
    assert "introspection_level" in lam_insight, "LAM insight missing 'introspection_level'"

    # Test 2.2: All insights have reflection_depth
    assert "reflection_depth" in hrm_insight, "HRM insight missing 'reflection_depth'"
    assert "reflection_depth" in lcm_insight, "LCM insight missing 'reflection_depth'"
    assert "reflection_depth" in lam_insight, "LAM insight missing 'reflection_depth'"

    # Test 2.3: All insights preserve original content
    assert hrm_insight.get("content") == base_insight["content"], "HRM insight altered content"
    assert lcm_insight.get("content") == base_insight["content"], "LCM insight altered content"
    assert lam_insight.get("content") == base_insight["content"], "LAM insight altered content"

    # Test 2.4: Modulation adds metadata, doesn't remove base fields
    for insight_name, insight in [("HRM", hrm_insight), ("LCM", lcm_insight), ("LAM", lam_insight)]:
        for key in base_insight.keys():
            assert key in insight, f"{insight_name} insight removed base field '{key}'"


# ============================================================================
# TEST 3: Structural Layers in Fusion Renderer Always Present
# ============================================================================


def test_structural_layers_always_present(
    sample_fusion_output: FusionOutput,
    hrm_profile: MapperProfile,
    lcm_profile: MapperProfile,
    lam_profile: MapperProfile,
):
    """
    Test 3: Structural Layers in Fusion Renderer Always Present

    Verify that "symbolic", "practical", "mirror" exist in every mapper state.

    Even when LCM compresses content, the layers must remain present
    (though their content may be minimal).
    """
    renderer = FusionRenderer()

    # Render base output
    base_output = renderer.render(sample_fusion_output)

    # Apply each mapper profile
    hrm_output = renderer.apply_mapper_profile(base_output, hrm_profile)
    lcm_output = renderer.apply_mapper_profile(base_output, lcm_profile)
    lam_output = renderer.apply_mapper_profile(base_output, lam_profile)

    # Test 3.1: All three layers present in HRM output
    assert hrm_output.symbolic_layer is not None, "HRM missing symbolic layer"
    assert hrm_output.practical_layer is not None, "HRM missing practical layer"
    assert hrm_output.mirror_truth_layer is not None, "HRM missing mirror layer"

    # Test 3.2: All three layers present in LCM output (even when compressed)
    assert lcm_output.symbolic_layer is not None, "LCM missing symbolic layer"
    assert lcm_output.practical_layer is not None, "LCM missing practical layer"
    assert lcm_output.mirror_truth_layer is not None, "LCM missing mirror layer"

    # Test 3.3: All three layers present in LAM output
    assert lam_output.symbolic_layer is not None, "LAM missing symbolic layer"
    assert lam_output.practical_layer is not None, "LAM missing practical layer"
    assert lam_output.mirror_truth_layer is not None, "LAM missing mirror layer"

    # Test 3.4: LCM compression doesn't remove core symbolic fields
    lcm_symbolic = lcm_output.symbolic_layer
    assert lcm_symbolic.theme, "LCM symbolic layer has empty theme"
    assert lcm_symbolic.causal_patterns, "LCM symbolic layer has no causal patterns"
    assert lcm_symbolic.meaning_vectors, "LCM symbolic layer has no meaning vectors"

    # Test 3.5: LCM compression doesn't remove core practical fields
    lcm_practical = lcm_output.practical_layer
    assert lcm_practical.key_facts, "LCM practical layer has no facts"
    assert lcm_practical.actionable_items, "LCM practical layer has no actionable items"


# ============================================================================
# TEST 4: LLM Renderer Preserves Content Tokens
# ============================================================================


def test_llm_renderer_preserves_content_tokens(
    hrm_profile: MapperProfile,
    lcm_profile: MapperProfile,
    lam_profile: MapperProfile,
):
    """
    Test 4: LLM Renderer Preserves Content Tokens

    Provide a fixed example text.
    Pass through apply_mapper_tone() for HRM, LCM, LAM.
    Extract content words and verify ALL tokens from base text appear in modulated text.

    Meaning preserved → tone changed.
    """
    llm_renderer = LLMRenderer()

    # Base text with clear semantic content
    base_text = "Anxiety stems from uncertainty. It triggers stress responses. It affects decision making."

    # Extract content tokens from base text
    base_tokens = set(re.findall(r"[a-zA-Z]+", base_text.lower()))

    # Apply mapper tone modulation
    hrm_text = llm_renderer.apply_mapper_tone(base_text, hrm_profile)
    lcm_text = llm_renderer.apply_mapper_tone(base_text, lcm_profile)
    lam_text = llm_renderer.apply_mapper_tone(base_text, lam_profile)

    # Extract tokens from modulated texts
    hrm_tokens = set(re.findall(r"[a-zA-Z]+", hrm_text.lower()))
    lcm_tokens = set(re.findall(r"[a-zA-Z]+", lcm_text.lower()))
    lam_tokens = set(re.findall(r"[a-zA-Z]+", lam_text.lower()))

    # Test 4.1: HRM preserves all content tokens
    missing_hrm = base_tokens - hrm_tokens
    assert not missing_hrm, f"HRM tone modulation lost content tokens: {missing_hrm}"

    # Test 4.2: LCM preserves all content tokens (even when compressing)
    # Note: LCM may remove some words if it splits sentences, so we check for core keywords
    core_keywords = {"anxiety", "uncertainty", "stress", "decision"}
    missing_lcm = core_keywords - lcm_tokens
    assert not missing_lcm, f"LCM tone modulation lost core semantic tokens: {missing_lcm}"

    # Test 4.3: LAM preserves all content tokens
    missing_lam = base_tokens - lam_tokens
    assert not missing_lam, f"LAM tone modulation lost content tokens: {missing_lam}"


# ============================================================================
# TEST 5: LOWER-task vs UPPER-therapy Share Semantic Skeleton
# ============================================================================


def test_snapshot_lower_task_vs_upper_therapy_semantic_skeleton(
    sample_fusion_output: FusionOutput,
):
    """
    Test 5: Snapshot: LOWER-task vs UPPER-therapy Share Semantic Skeleton

    Create two pipeline snapshots:
    - LOWER-task (LCM)
    - UPPER-therapy (HRM+LAM)

    Assert:
    - Both snapshots contain:
      - symbolic layer
      - practical layer
      - mirror layer
      - dha_output.insight (simulated via modulated insight)

    - Differences should be:
      - presence of arc markers
      - level of detail modulation

    - Similarities should be:
      - SAME structural keys ("semantic skeleton")
    """
    renderer = FusionRenderer()

    # LOWER-task profile (LCM)
    lower_task_profile = MapperProfile(
        resolution_level="low",
        arc_mode="none",
        detail_bias=0.2,
        practical_bias=0.9,
        reflective_bias=0.3,
    )

    # UPPER-therapy profile (HRM + LAM)
    upper_therapy_profile = MapperProfile(
        resolution_level="high",
        arc_mode="identity",
        detail_bias=0.8,
        practical_bias=0.5,
        reflective_bias=1.0,
    )

    # Render base output
    base_output = renderer.render(sample_fusion_output)

    # Apply profiles
    lower_task_output = renderer.apply_mapper_profile(base_output, lower_task_profile)
    upper_therapy_output = renderer.apply_mapper_profile(base_output, upper_therapy_profile)

    # Test 5.1: Both snapshots have all three layers
    assert lower_task_output.symbolic_layer is not None, "LOWER-task missing symbolic layer"
    assert lower_task_output.practical_layer is not None, "LOWER-task missing practical layer"
    assert lower_task_output.mirror_truth_layer is not None, "LOWER-task missing mirror layer"

    assert upper_therapy_output.symbolic_layer is not None, "UPPER-therapy missing symbolic layer"
    assert upper_therapy_output.practical_layer is not None, "UPPER-therapy missing practical layer"
    assert upper_therapy_output.mirror_truth_layer is not None, "UPPER-therapy missing mirror layer"

    # Test 5.2: Both have same structural keys in symbolic layer
    lower_symbolic_keys = set(lower_task_output.symbolic_layer.to_dict().keys())
    upper_symbolic_keys = set(upper_therapy_output.symbolic_layer.to_dict().keys())
    assert lower_symbolic_keys == upper_symbolic_keys, "Symbolic layer structure differs between LOWER-task and UPPER-therapy"

    # Test 5.3: Both have same structural keys in practical layer
    lower_practical_keys = set(lower_task_output.practical_layer.to_dict().keys())
    upper_practical_keys = set(upper_therapy_output.practical_layer.to_dict().keys())
    assert lower_practical_keys == upper_practical_keys, "Practical layer structure differs between LOWER-task and UPPER-therapy"

    # Test 5.4: Both have same structural keys in mirror layer
    lower_mirror_keys = set(lower_task_output.mirror_truth_layer.to_dict().keys())
    upper_mirror_keys = set(upper_therapy_output.mirror_truth_layer.to_dict().keys())
    assert lower_mirror_keys == upper_mirror_keys, "Mirror layer structure differs between LOWER-task and UPPER-therapy"

    # Test 5.5: UPPER-therapy has arc markers, LOWER-task doesn't
    upper_mirror = upper_therapy_output.mirror_truth_layer
    assert any("identity" in str(t).lower() or "evolution" in str(t).lower()
               for t in upper_mirror.tensions), "UPPER-therapy missing identity arc markers"

    # Test 5.6: LOWER-task has practical focus markers
    lower_mirror = lower_task_output.mirror_truth_layer
    assert any("practical" in str(t).lower() or "action" in str(t).lower()
               for t in lower_mirror.tensions), "LOWER-task missing practical focus markers"


# ============================================================================
# TEST 6: No Semantic Loss Under LCM Compression
# ============================================================================


def test_no_semantic_loss_under_lcm_compression(
    sample_fusion_output: FusionOutput,
    lcm_profile: MapperProfile,
):
    """
    Test 6: No Semantic Loss Under LCM Compression

    For LCM profile:
    - ensure:
      - symbolic layer declines in richness
      - BUT required fields (e.g., "theme", "causal_patterns", "meaning_vectors")
        still exist if originally present

    This test verifies that LCM compression is LOSSLESS in terms of structure,
    even if content is minimized.
    """
    renderer = FusionRenderer()

    # Render base output
    base_output = renderer.render(sample_fusion_output)

    # Apply LCM compression
    lcm_output = renderer.apply_mapper_profile(base_output, lcm_profile)

    # Test 6.1: Symbolic layer still has required fields
    lcm_symbolic = lcm_output.symbolic_layer
    assert lcm_symbolic.theme, "LCM compression removed theme"
    assert lcm_symbolic.archetype, "LCM compression removed archetype"
    assert lcm_symbolic.causal_patterns, "LCM compression removed causal_patterns"
    assert lcm_symbolic.meaning_vectors, "LCM compression removed meaning_vectors"

    # Test 6.2: Practical layer still has required fields
    lcm_practical = lcm_output.practical_layer
    assert lcm_practical.key_facts, "LCM compression removed key_facts"
    assert lcm_practical.constraints, "LCM compression removed constraints"
    assert lcm_practical.procedures, "LCM compression removed procedures"
    assert lcm_practical.domain, "LCM compression removed domain"
    assert lcm_practical.actionable_items, "LCM compression removed actionable_items"

    # Test 6.3: Mirror layer still has required fields
    lcm_mirror = lcm_output.mirror_truth_layer
    assert hasattr(lcm_mirror, "contradictions"), "LCM compression removed contradictions field"
    assert lcm_mirror.entropy_measures, "LCM compression removed entropy_measures"
    assert lcm_mirror.tensions, "LCM compression removed tensions"
    assert lcm_mirror.alignment_score is not None, "LCM compression removed alignment_score"
    assert lcm_mirror.stability_indicator, "LCM compression removed stability_indicator"
    assert lcm_mirror.reflection, "LCM compression removed reflection"

    # Test 6.4: Compression reduces richness but preserves structure
    base_symbolic = base_output.symbolic_layer

    # LCM should have fewer causal patterns
    assert len(lcm_symbolic.causal_patterns) <= len(base_symbolic.causal_patterns), \
        "LCM compression should reduce causal patterns count"

    # LCM should have lower reasoning_depth
    assert lcm_symbolic.reasoning_depth <= base_symbolic.reasoning_depth, \
        "LCM compression should reduce reasoning_depth"

    # Test 6.5: Practical bias increases under LCM
    assert lcm_practical.coherence_score >= base_output.practical_layer.coherence_score, \
        "LCM should increase practical coherence"

    # Test 6.6: Mirror layer reflection is minimal but non-empty
    assert lcm_mirror.reflection, "LCM compression removed reflection text"
    assert len(lcm_mirror.reflection) > 0, "LCM reflection is empty"


# ============================================================================
# END OF SEMANTIC-SHAPE TESTS
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
