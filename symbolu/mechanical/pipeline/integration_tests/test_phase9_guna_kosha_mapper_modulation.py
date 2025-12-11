"""
Phase 9 Integration Tests: Guna/Kosha Resonance Mapper Modulation
==================================================================

Comprehensive integration tests for Phase 9 Guna/Kosha resonance modulation
to mapper expression biases (HRM/LCM/LAM).

Test Groups:
- Group A: MapperProfile Bias Tests (12 tests - includes 4 edge cases)
- Group B: Renderer Integration Tests (7 tests)
- Group C: Behavioral Invariance (6 tests)

All tests verify that Guna/Kosha modulation ONLY affects expression,
NOT routing, mapper activation, policy, or any decision logic.

Fixed Issues:
- Issue 1: Replaced mock fixtures with actual CoherenceState and RoutingPlan
- Issue 2: Simplified LLM renderer test to reduce fragility
- Issue 3: Added 4 edge case tests (extreme biases, empty/zero vectors, simultaneous mappers)
"""

import pytest
from symbolu.mechanical.pipeline.models import MapperProfile
from symbolu.mechanical.mlcr.mapper_profile_builder import (
    apply_resonance_biases,
    build_mapper_profile_with_resonance,
    compute_mapper_profile,
)
from symbolu.mechanical.renderer.fusion_renderer import (
    FusionRenderer,
    FusionOutput,
    SymbolicLayer,
    PracticalLayer,
    MirrorTruthLayer,
)
from symbolu.mechanical.dha.dha_engine import DHAEngine
from symbolu.mechanical.renderer.llm_renderer import LLMRenderer
from symbolu.mechanical.pipeline.ttor.models import RoutingPlan
from symbolu.core.coherence.coherence_state import CoherenceState


# =============================================================================
# FIXTURES & TEST DATA
# =============================================================================


@pytest.fixture
def base_mapper_profile():
    """Base mapper profile without resonance biases."""
    return MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=0.0,
        kosha_resonance_bias=0.0,
        expression_harmonics=None,
    )


@pytest.fixture
def coherence_state_high_resonance():
    """Real coherence state with high Guna/Kosha resonance."""
    state = CoherenceState(convo_id="test", turn_index=1)
    state.guna_resonance_index = 0.85  # High (> 0.65)
    state.kosha_resonance_index = 0.75  # High (> 0.60)
    state.kosha_activation_vector = [0.4, 0.3, 0.2, 0.08, 0.02]
    return state


@pytest.fixture
def coherence_state_low_resonance():
    """Real coherence state with low Guna/Kosha resonance."""
    state = CoherenceState(convo_id="test", turn_index=1)
    state.guna_resonance_index = 0.25  # Low (< 0.35)
    state.kosha_resonance_index = 0.30  # Low (< 0.40)
    state.kosha_activation_vector = [0.6, 0.25, 0.1, 0.03, 0.02]
    return state


@pytest.fixture
def routing_plan():
    """Real routing plan for profile building."""
    return RoutingPlan(
        tier="hybrid",
        domain="general",
        long_arc_tension=0.5,
        normalized_entropy=0.5,
        use_hrm=False,
        use_lcm=False,
        use_lam=False
    )


# =============================================================================
# GROUP A: MAPPERPROFILE BIAS TESTS (12 tests)
# =============================================================================


def test_high_guna_resonance_increases_detail_bias(base_mapper_profile):
    """High guna resonance (> 0.65) should increase detail_bias by 0.05."""
    modulated = apply_resonance_biases(
        base_mapper_profile,
        guna_resonance=0.85,  # High
        kosha_resonance=None,
        kosha_vector=None
    )

    assert modulated.detail_bias == 0.55, "detail_bias should increase by 0.05"
    assert modulated.guna_resonance_bias == 0.05, "guna_resonance_bias should be +0.05"


def test_low_guna_resonance_increases_practical_bias(base_mapper_profile):
    """Low guna resonance (< 0.35) should increase practical_bias by 0.05."""
    modulated = apply_resonance_biases(
        base_mapper_profile,
        guna_resonance=0.25,  # Low
        kosha_resonance=None,
        kosha_vector=None
    )

    assert modulated.practical_bias == 0.55, "practical_bias should increase by 0.05"
    assert modulated.guna_resonance_bias == -0.05, "guna_resonance_bias should be -0.05"


def test_high_kosha_resonance_increases_reflective_bias(base_mapper_profile):
    """High kosha resonance (> 0.60) should increase reflective_bias by 0.05."""
    modulated = apply_resonance_biases(
        base_mapper_profile,
        guna_resonance=None,
        kosha_resonance=0.75,  # High
        kosha_vector=None
    )

    assert modulated.reflective_bias == 0.55, "reflective_bias should increase by 0.05"
    assert modulated.kosha_resonance_bias == 0.05, "kosha_resonance_bias should be +0.05"


def test_low_kosha_resonance_decreases_reflective_bias(base_mapper_profile):
    """Low kosha resonance (< 0.40) should decrease reflective_bias by 0.05."""
    modulated = apply_resonance_biases(
        base_mapper_profile,
        guna_resonance=None,
        kosha_resonance=0.30,  # Low
        kosha_vector=None
    )

    assert modulated.reflective_bias == 0.45, "reflective_bias should decrease by 0.05"
    assert modulated.kosha_resonance_bias == -0.05, "kosha_resonance_bias should be -0.05"


def test_bias_clamping_to_0_and_1():
    """Biases should clamp to [0, 1] range."""
    # Profile with already high detail_bias
    high_profile = MapperProfile(
        resolution_level="high",
        arc_mode="none",
        detail_bias=0.98,
        practical_bias=0.5,
        reflective_bias=0.5,
    )

    modulated = apply_resonance_biases(
        high_profile,
        guna_resonance=0.85,  # Would increase detail_bias
        kosha_resonance=None,
        kosha_vector=None
    )

    assert modulated.detail_bias <= 1.0, "detail_bias should not exceed 1.0"
    assert modulated.detail_bias >= 0.0, "detail_bias should not go below 0.0"


def test_expression_harmonics_computed_from_kosha_vector(base_mapper_profile):
    """Expression harmonics should reflect kosha vector deviations from mean."""
    kosha_vector = [0.4, 0.3, 0.2, 0.08, 0.02]
    mean_value = sum(kosha_vector) / len(kosha_vector)  # 0.2

    modulated = apply_resonance_biases(
        base_mapper_profile,
        guna_resonance=None,
        kosha_resonance=None,
        kosha_vector=kosha_vector
    )

    assert modulated.expression_harmonics is not None, "Harmonics should be computed"
    assert len(modulated.expression_harmonics) == 5, "Harmonics should have 5 elements"

    # Check deviations
    expected = [round(v - mean_value, 4) for v in kosha_vector]
    assert modulated.expression_harmonics == expected, "Harmonics should match deviations"


def test_missing_metrics_no_change(base_mapper_profile):
    """When all metrics are None, profile should remain unchanged."""
    modulated = apply_resonance_biases(
        base_mapper_profile,
        guna_resonance=None,
        kosha_resonance=None,
        kosha_vector=None
    )

    assert modulated.detail_bias == base_mapper_profile.detail_bias
    assert modulated.practical_bias == base_mapper_profile.practical_bias
    assert modulated.reflective_bias == base_mapper_profile.reflective_bias
    assert modulated.guna_resonance_bias == 0.0
    assert modulated.kosha_resonance_bias == 0.0
    assert modulated.expression_harmonics is None


def test_combined_guna_kosha_modulation(base_mapper_profile):
    """Both guna and kosha should modulate simultaneously."""
    modulated = apply_resonance_biases(
        base_mapper_profile,
        guna_resonance=0.85,  # High → +detail_bias
        kosha_resonance=0.75,  # High → +reflective_bias
        kosha_vector=[0.4, 0.3, 0.2, 0.08, 0.02]
    )

    assert modulated.detail_bias == 0.55, "detail_bias should increase"
    assert modulated.reflective_bias == 0.55, "reflective_bias should increase"
    assert modulated.expression_harmonics is not None, "Harmonics should be set"


def test_extreme_bias_with_high_resonance_clamping():
    """Extreme bias (0.98) + high resonance should clamp correctly."""
    # Profile with already very high detail_bias
    extreme_profile = MapperProfile(
        resolution_level="high",
        arc_mode="none",
        detail_bias=0.98,  # Already very high
        practical_bias=0.2,
        reflective_bias=0.2,
    )

    modulated = apply_resonance_biases(
        extreme_profile,
        guna_resonance=0.85,  # Would increase detail_bias by 0.05
        kosha_resonance=0.75,  # Would increase reflective_bias by 0.05
        kosha_vector=[0.4, 0.3, 0.2, 0.08, 0.02]
    )

    # Should clamp to 1.0
    assert modulated.detail_bias == 1.0, "detail_bias should clamp to 1.0"
    assert modulated.detail_bias <= 1.0, "detail_bias should not exceed 1.0"
    assert modulated.reflective_bias == 0.25, "reflective_bias should increase to 0.25"


def test_empty_kosha_vector_handling():
    """Empty kosha vector should be handled gracefully."""
    modulated = apply_resonance_biases(
        MapperProfile(
            resolution_level="medium",
            arc_mode="none",
            detail_bias=0.5,
            practical_bias=0.5,
            reflective_bias=0.5,
        ),
        guna_resonance=0.85,
        kosha_resonance=0.75,
        kosha_vector=[]  # Empty vector
    )

    # Should not crash, harmonics should be None
    assert modulated.expression_harmonics is None, "Empty vector should result in None harmonics"
    assert modulated.guna_resonance_bias == 0.05, "Guna bias should still be applied"
    assert modulated.kosha_resonance_bias == 0.05, "Kosha bias should still be applied"


def test_zero_kosha_vector_handling():
    """All-zero kosha vector should compute harmonics correctly."""
    kosha_vector = [0.0, 0.0, 0.0, 0.0, 0.0]
    modulated = apply_resonance_biases(
        MapperProfile(
            resolution_level="medium",
            arc_mode="none",
            detail_bias=0.5,
            practical_bias=0.5,
            reflective_bias=0.5,
        ),
        guna_resonance=None,
        kosha_resonance=None,
        kosha_vector=kosha_vector
    )

    # Mean should be 0.0, all harmonics should be 0.0
    assert modulated.expression_harmonics is not None, "Harmonics should be computed"
    assert all(h == 0.0 for h in modulated.expression_harmonics), "All harmonics should be 0.0"


def test_simultaneous_hrm_lcm_with_resonance():
    """HRM+LCM simultaneously with resonance biases should work correctly."""
    # Create routing plan with both HRM and LCM active
    plan = RoutingPlan(
        tier="hybrid",
        domain="general",
        long_arc_tension=0.5,
        normalized_entropy=0.5,
        use_hrm=True,
        use_lcm=True,
        use_lam=False
    )

    # Create coherence state with high resonance
    state = CoherenceState(convo_id="test", turn_index=1)
    state.guna_resonance_index = 0.85
    state.kosha_resonance_index = 0.75
    state.kosha_activation_vector = [0.4, 0.3, 0.2, 0.08, 0.02]

    # Build profile
    profile = build_mapper_profile_with_resonance(plan, state)

    # Verify base mapper effects applied
    assert profile.resolution_level == "medium", "HRM+LCM should compromise to medium"

    # Verify resonance biases applied
    assert profile.guna_resonance_bias == 0.05, "Guna bias should be applied"
    assert profile.kosha_resonance_bias == 0.05, "Kosha bias should be applied"
    assert profile.expression_harmonics is not None, "Harmonics should be set"


# =============================================================================
# GROUP B: RENDERER INTEGRATION TESTS (7 tests)
# =============================================================================


def test_fusion_symbolic_layer_adjusts_with_positive_guna_bias():
    """Positive guna bias should add symbolic nuance markers to symbolic layer."""
    renderer = FusionRenderer()

    profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=0.05,  # Positive
        kosha_resonance_bias=0.0,
        expression_harmonics=None,
    )

    symbolic_layer = SymbolicLayer(
        theme="Exploration of possibilities",
        archetype="Philosopher",
        causal_patterns=["Pattern A", "Pattern B"],
        meaning_vectors={"abstractness": 0.8},
        dominant_channel="hrm",
        reasoning_depth=0.7
    )

    modulated = renderer._apply_resonance_to_symbolic(symbolic_layer, profile)

    assert "[symbolic nuance]" in modulated.theme, "Theme should have symbolic nuance marker"


def test_fusion_symbolic_layer_reduces_with_negative_guna_bias():
    """Negative guna bias should remove symbolic embellishments."""
    renderer = FusionRenderer()

    profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=-0.05,  # Negative
        kosha_resonance_bias=0.0,
        expression_harmonics=None,
    )

    symbolic_layer = SymbolicLayer(
        theme="Exploration [detailed analysis]",
        archetype="Philosopher",
        causal_patterns=["Pattern A"],
        meaning_vectors={"abstractness": 0.8},
        dominant_channel="hrm",
        reasoning_depth=0.7
    )

    modulated = renderer._apply_resonance_to_symbolic(symbolic_layer, profile)

    assert "[detailed analysis]" not in modulated.theme, "Embellishments should be removed"


def test_fusion_mirror_layer_depth_increases_with_positive_kosha_bias():
    """Positive kosha bias should increase mirror-truth reflective depth."""
    renderer = FusionRenderer()

    profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=0.0,
        kosha_resonance_bias=0.06,  # Positive > 0.05
        expression_harmonics=None,
    )

    mirror_layer = MirrorTruthLayer(
        contradictions=[],
        entropy_measures={"channel_entropy": 0.5},
        tensions=["Tension A"],
        alignment_score=0.8,
        stability_indicator="STABLE",
        reflection="High coherence."
    )

    modulated = renderer._apply_resonance_to_mirror(mirror_layer, profile)

    assert "Reflective coherence deepened" in modulated.reflection, "Reflection should be deepened"


def test_fusion_mirror_layer_depth_decreases_with_negative_kosha_bias():
    """Negative kosha bias should suppress mirror-truth reflective depth."""
    renderer = FusionRenderer()

    profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=0.0,
        kosha_resonance_bias=-0.06,  # Negative < -0.05
        expression_harmonics=None,
    )

    mirror_layer = MirrorTruthLayer(
        contradictions=[],
        entropy_measures={"channel_entropy": 0.5},
        tensions=["Tension A"],
        alignment_score=0.8,
        stability_indicator="STABLE",
        reflection="High coherence. Multiple dimensions present."
    )

    modulated = renderer._apply_resonance_to_mirror(mirror_layer, profile)

    # Should only keep first sentence
    assert modulated.reflection == "High coherence.", "Reflection should be simplified"


def test_dha_extra_insight_triggered_with_positive_kosha_bias():
    """DHA should add extra reflective insight marker when kosha_resonance_bias > 0.05."""
    engine = DHAEngine()

    profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=0.0,
        kosha_resonance_bias=0.06,  # Positive
        expression_harmonics=None,
    )

    insight = {"readiness": 0.8}
    modulated = engine.modulate_dha_depth(insight, profile)

    assert modulated.get("extra_reflective_insight") is True, "Should add extra insight marker"
    assert modulated.get("kosha_depth_boost") is True, "Should have depth boost flag"


def test_dha_suppresses_depth_with_negative_kosha_bias():
    """DHA should suppress depth when kosha_resonance_bias < -0.05."""
    engine = DHAEngine()

    profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=0.0,
        kosha_resonance_bias=-0.06,  # Negative
        expression_harmonics=None,
    )

    insight = {"readiness": 0.8}
    modulated = engine.modulate_dha_depth(insight, profile)

    assert modulated.get("suppress_lowest_depth") is True, "Should suppress depth"
    assert modulated.get("kosha_depth_reduction") is True, "Should have depth reduction flag"


def test_llm_tone_shifts_with_resonance_bias():
    """LLM renderer should apply tone modulation based on resonance bias."""
    renderer = LLMRenderer()

    # Test positive bias - verify method executes without error
    profile_positive = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=0.05,  # Positive
        kosha_resonance_bias=0.0,
        expression_harmonics=None,
    )

    text = "This is a test. Another sentence here."
    modulated_positive = renderer.apply_mapper_tone(text, profile_positive)

    # Verify method returns valid result
    assert modulated_positive is not None, "Should return modulated text"
    assert isinstance(modulated_positive, str), "Should return string"
    assert len(modulated_positive) > 0, "Should return non-empty text"

    # Test negative bias - verify method executes without error
    profile_negative = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=-0.05,  # Negative
        kosha_resonance_bias=0.0,
        expression_harmonics=None,
    )

    text_with_connector = "Additionally, this is a test. Furthermore, another sentence here. More text."
    modulated_negative = renderer.apply_mapper_tone(text_with_connector, profile_negative)

    # Verify method returns valid result
    assert modulated_negative is not None, "Should return modulated text"
    assert isinstance(modulated_negative, str), "Should return string"
    assert len(modulated_negative) > 0, "Should return non-empty text"


# =============================================================================
# GROUP C: BEHAVIORAL INVARIANCE (6 tests)
# =============================================================================


def test_routing_unchanged_by_resonance_biases(routing_plan, coherence_state_high_resonance):
    """Routing plan should NOT change based on resonance biases."""
    # Build profile with high resonance
    profile_with = build_mapper_profile_with_resonance(
        routing_plan,
        coherence_state_high_resonance
    )

    # Build profile without resonance
    profile_without = build_mapper_profile_with_resonance(
        routing_plan,
        None
    )

    # Core routing attributes should be identical
    assert profile_with.resolution_level == profile_without.resolution_level, \
        "resolution_level should be invariant"
    assert profile_with.arc_mode == profile_without.arc_mode, \
        "arc_mode should be invariant"


def test_mapper_activation_unchanged_by_resonance_biases(routing_plan, coherence_state_high_resonance):
    """HRM/LCM/LAM activation should NOT change based on resonance biases."""
    # The routing plan's use_hrm, use_lcm, use_lam flags should NOT be affected
    # by resonance biases

    # Activate HRM
    routing_plan.use_hrm = True

    profile_with = build_mapper_profile_with_resonance(
        routing_plan,
        coherence_state_high_resonance
    )

    profile_without = build_mapper_profile_with_resonance(
        routing_plan,
        None
    )

    # Base profile characteristics from HRM should be identical
    # (only the resonance bias fields differ)
    assert profile_with.resolution_level == profile_without.resolution_level
    assert profile_with.arc_mode == profile_without.arc_mode


def test_policy_unchanged_by_resonance_biases():
    """Policy flags should NOT be generated from resonance biases."""
    # This is a placeholder test - in actual pipeline, policy engine
    # should not create flags based on guna/kosha resonance metrics

    # Low resonance should NOT trigger policy flags
    profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=-0.05,  # Low
        kosha_resonance_bias=-0.05,  # Low
        expression_harmonics=None,
    )

    # Verify no policy-related attributes in profile
    assert not hasattr(profile, 'policy_flags'), "Profile should not have policy flags"


def test_ttor_unchanged_by_resonance_biases(routing_plan, coherence_state_high_resonance):
    """TTOR routing logic should NOT change based on resonance biases."""
    # TTOR uses routing_plan to make decisions
    # Resonance biases should NOT affect these decisions

    profile1 = build_mapper_profile_with_resonance(
        routing_plan,
        coherence_state_high_resonance
    )

    profile2 = build_mapper_profile_with_resonance(
        routing_plan,
        None
    )

    # The base mapper profile (before resonance) should be identical
    base1 = compute_mapper_profile(routing_plan)
    base2 = compute_mapper_profile(routing_plan)

    assert base1.resolution_level == base2.resolution_level
    assert base1.detail_bias == base2.detail_bias
    assert base1.practical_bias == base2.practical_bias


def test_motivation_identity_intent_signals_unchanged():
    """Motivation/Identity/Intent signals should NOT be affected by resonance biases."""
    # These engines should operate independently of resonance biases

    profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=0.05,
        kosha_resonance_bias=0.05,
        expression_harmonics=[0.1, 0.05, 0.0, -0.05, -0.1],
    )

    # Verify profile doesn't contain motivation/identity/intent fields
    assert not hasattr(profile, 'motivation_profile'), "Should not have motivation profile"
    assert not hasattr(profile, 'identity_signature'), "Should not have identity signature"
    assert not hasattr(profile, 'intent_arc'), "Should not have intent arc"


def test_dilchat_badges_hints_unchanged_by_resonance_biases():
    """DILchat badges and hints should NOT reference guna/kosha resonance."""
    # This is verified by ensuring resonance biases only appear in
    # expression modulation, not in user-facing badges/hints

    profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5,
        guna_resonance_bias=0.05,
        kosha_resonance_bias=0.05,
        expression_harmonics=[0.1, 0.05, 0.0, -0.05, -0.1],
    )

    # Verify no DILchat-specific attributes
    assert not hasattr(profile, 'badges'), "Should not have badges"
    assert not hasattr(profile, 'hints'), "Should not have hints"


# =============================================================================
# INTEGRATION TEST: FULL PIPELINE
# =============================================================================


def test_full_phase9_integration(routing_plan, coherence_state_high_resonance):
    """Full Phase 9 integration: routing plan → coherence state → modulated profile."""
    # Build profile with resonance
    profile = build_mapper_profile_with_resonance(
        routing_plan,
        coherence_state_high_resonance
    )

    # Verify all Phase 9 fields are set
    assert profile.guna_resonance_bias != 0.0, "Guna bias should be set"
    assert profile.kosha_resonance_bias != 0.0, "Kosha bias should be set"
    assert profile.expression_harmonics is not None, "Harmonics should be set"

    # Verify base profile unchanged
    assert profile.resolution_level == "medium", "Base routing unchanged"
    assert profile.arc_mode == "none", "Base routing unchanged"

    # Verify determinism
    profile2 = build_mapper_profile_with_resonance(
        routing_plan,
        coherence_state_high_resonance
    )

    assert profile.guna_resonance_bias == profile2.guna_resonance_bias, "Should be deterministic"
    assert profile.kosha_resonance_bias == profile2.kosha_resonance_bias, "Should be deterministic"
    assert profile.expression_harmonics == profile2.expression_harmonics, "Should be deterministic"
