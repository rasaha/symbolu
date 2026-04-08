"""
Phase 4 Coherence v2 Integration Tests
========================================

Tests for Phase 4 Symbol-U Formula Integration Plan v1.0.

These tests verify that Phase 4 coherence score v2 (formula-aware coherence) is:
- Correctly computed from Phase 1 + Phase 3 formula signals
- Properly propagated through the coherence state → observer → unified output → DILchat adapter
- Feature-flag gated (no change to live behavior unless explicitly enabled)
- Backward compatible (v1 behavior unchanged for domains with use_coherence_v2=False)

All changes must be:
- Zero-LLM (pure math + rules, deterministic)
- Non-invasive (v1 behavior fully intact by default)
- CI-safe (all tests pass with drift & invariance guards)
- Policy-layer only (no routing/TTOR/mapper changes)

Test Coverage:
Group A - Coherence v2 Math (~6 tests)
Group B - Policy Flag Selection (~4 tests)
Group C - Behavioral Invariance (~4 tests)
Group D - Unified API & DILchat (~4 tests)
Total: ~18 tests
"""

import pytest
from typing import Dict, Any, Optional

from agentic.core.coherence.coherence_engine import CoherenceEngine
from agentic.core.coherence.coherence_state import CoherenceState
from agentic.policy.domain_profiles import get_domain_profile
from agentic.policy.policy_engine import compute_policy_flags, _get_active_coherence_score
from symbolu_core.mechanical.pipeline.coherence_observer import CoherenceObserver


# ==============================================================================
# Group A: Coherence v2 Math
# ==============================================================================


def test_coherence_v2_formula_high_base_high_resonance():
    """
    Test v2 formula with high base + high resonance → v2 > base.

    Scenario: base=0.6, res=0.8, ten=0.3, arc=0.7
    Expected: v2 > base (resonance and arc boost the score)
    """
    engine = CoherenceEngine(window=10)

    state = CoherenceState(
        convo_id="test_convo",
        turn_index=0,
    )

    # Set v1 base score
    state.coherence_score = 0.6

    # Set Phase 3 derived metrics (inputs for v2 formula)
    state.resonance_index = 0.8  # High resonance
    state.tension_index = 0.3     # Low tension
    state.arc_alignment_index = 0.7  # Good alignment

    # Compute v2
    v2 = engine._compute_coherence_score_v2(state)

    # Assertions
    assert v2 is not None, "v2 should be computed when all inputs are present"
    assert 0.0 <= v2 <= 1.0, f"v2 must be in [0,1], got {v2}"
    assert v2 > state.coherence_score, f"Expected v2 > base (0.6), got v2={v2}"

    # Verify formula: 0.55*0.6 + 0.20*0.8 + 0.15*0.7 + 0.10*(1-0.3)
    expected = 0.55 * 0.6 + 0.20 * 0.8 + 0.15 * 0.7 + 0.10 * (1.0 - 0.3)
    assert abs(v2 - expected) < 0.01, f"Expected v2≈{expected}, got {v2}"


def test_coherence_v2_formula_high_base_low_resonance():
    """
    Test v2 formula with high base + low resonance → v2 < base.

    Scenario: base=0.7, res=0.2, ten=0.9, arc=0.1
    Expected: v2 < base (low resonance and high tension drag it down)
    """
    engine = CoherenceEngine(window=10)

    state = CoherenceState(
        convo_id="test_convo",
        turn_index=0,
    )

    state.coherence_score = 0.7
    state.resonance_index = 0.2
    state.tension_index = 0.9
    state.arc_alignment_index = 0.1

    v2 = engine._compute_coherence_score_v2(state)

    assert v2 is not None
    assert 0.0 <= v2 <= 1.0
    assert v2 < state.coherence_score, f"Expected v2 < base (0.7), got v2={v2}"

    # Verify formula
    expected = 0.55 * 0.7 + 0.20 * 0.2 + 0.15 * 0.1 + 0.10 * (1.0 - 0.9)
    assert abs(v2 - expected) < 0.01


def test_coherence_v2_clamped_to_range():
    """
    Test that v2 is always clamped to [0, 1].

    Even with extreme inputs, v2 should never exceed 1.0 or drop below 0.0.
    """
    engine = CoherenceEngine(window=10)

    state = CoherenceState(
        convo_id="test_convo",
        turn_index=0,
    )

    # Test upper bound clamping
    state.coherence_score = 1.0
    state.resonance_index = 1.0
    state.tension_index = 0.0
    state.arc_alignment_index = 1.0

    v2 = engine._compute_coherence_score_v2(state)
    assert v2 is not None
    assert v2 <= 1.0, f"v2 must not exceed 1.0, got {v2}"

    # Test lower bound clamping
    state.coherence_score = 0.0
    state.resonance_index = 0.0
    state.tension_index = 1.0
    state.arc_alignment_index = 0.0

    v2 = engine._compute_coherence_score_v2(state)
    assert v2 is not None
    assert v2 >= 0.0, f"v2 must not drop below 0.0, got {v2}"


def test_coherence_v2_returns_none_when_inputs_missing():
    """
    Test that v2 returns None when any required derived metric is missing.

    This ensures graceful degradation when Phase 3 metrics aren't available.
    """
    engine = CoherenceEngine(window=10)

    state = CoherenceState(
        convo_id="test_convo",
        turn_index=0,
    )

    state.coherence_score = 0.5

    # Case 1: All derived metrics None
    state.resonance_index = None
    state.tension_index = None
    state.arc_alignment_index = None

    v2 = engine._compute_coherence_score_v2(state)
    assert v2 is None, "v2 should be None when all derived metrics are missing"

    # Case 2: Partial inputs (resonance only)
    state.resonance_index = 0.5
    v2 = engine._compute_coherence_score_v2(state)
    assert v2 is None, "v2 should be None when some derived metrics are missing"

    # Case 3: All inputs present
    state.tension_index = 0.5
    state.arc_alignment_index = 0.5
    v2 = engine._compute_coherence_score_v2(state)
    assert v2 is not None, "v2 should be computed when all inputs are present"


def test_coherence_v2_integrated_into_state_update():
    """
    Test that v2 is automatically computed during state update.

    When CoherenceEngine.update_state() is called with Phase 3 formulas available,
    coherence_score_v2 should be populated automatically.
    """
    engine = CoherenceEngine(window=10)

    # Create mock temporal summary with formulas
    temporal_summary = {
        "smi": 0.7,
        "delta_smi": 0.1,
        "bhava_gap": 0.2,
        "tension_corridor": 0.3,
        "bhava_id": 3,
        "bhava_direction": "upward",
    }

    # Create mock routing plan
    class MockRoutingPlan:
        tier = "hybrid"
        domain = "therapy"
        long_arc_tension = 0.3

    routing_plan = MockRoutingPlan()

    # Update state
    state = engine.update_state(
        prev_state=None,
        convo_id="test_convo",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile={"resolution_level": "medium", "arc_mode": "none"},
        temporal_summary=temporal_summary,
        semantic_signature={},
    )

    # Assertions
    assert state.coherence_score is not None, "v1 score should always be computed"
    assert state.resonance_index is not None, "Phase 3 metrics should be computed"
    assert state.tension_index is not None
    assert state.arc_alignment_index is not None

    # Phase 4: v2 should be auto-computed
    assert state.coherence_score_v2 is not None, "v2 should be auto-computed when Phase 3 metrics are present"
    assert 0.0 <= state.coherence_score_v2 <= 1.0


def test_coherence_v2_deterministic():
    """
    Test that v2 computation is fully deterministic.

    Same inputs should always produce same v2 output.
    """
    engine = CoherenceEngine(window=10)

    state1 = CoherenceState(convo_id="test1", turn_index=0)
    state1.coherence_score = 0.65
    state1.resonance_index = 0.75
    state1.tension_index = 0.35
    state1.arc_alignment_index = 0.70

    state2 = CoherenceState(convo_id="test2", turn_index=0)
    state2.coherence_score = 0.65
    state2.resonance_index = 0.75
    state2.tension_index = 0.35
    state2.arc_alignment_index = 0.70

    v2_1 = engine._compute_coherence_score_v2(state1)
    v2_2 = engine._compute_coherence_score_v2(state2)

    assert v2_1 == v2_2, "v2 must be deterministic (same inputs → same output)"


# ==============================================================================
# Group B: Policy Flag Selection
# ==============================================================================


def test_get_active_coherence_score_v1_when_flag_disabled():
    """
    Test that _get_active_coherence_score returns v1 when use_coherence_v2=False.

    For trading and generic domains (use_coherence_v2=False), policy should
    always use v1 even when v2 is present.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.6,      # v1
            "coherence_score_v2": 0.75,  # v2 (should be ignored)
        }
    }

    # Trading profile (use_coherence_v2=False)
    profile = get_domain_profile("trading")
    assert profile["use_coherence_v2"] is False, "Trading should default to v1"

    active_score = _get_active_coherence_score(unified, profile)
    assert active_score == 0.6, f"Expected v1 (0.6), got {active_score}"

    # Generic profile (use_coherence_v2=False)
    profile_generic = get_domain_profile("generic")
    assert profile_generic["use_coherence_v2"] is False

    active_score_generic = _get_active_coherence_score(unified, profile_generic)
    assert active_score_generic == 0.6


def test_get_active_coherence_score_v2_when_flag_enabled():
    """
    Test that _get_active_coherence_score returns v2 when use_coherence_v2=True.

    For therapy and identity domains (use_coherence_v2=True), policy should
    use v2 when available.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.6,
            "coherence_score_v2": 0.75,
        }
    }

    # Therapy profile (use_coherence_v2=True)
    profile = get_domain_profile("therapy")
    assert profile["use_coherence_v2"] is True, "Therapy should enable v2"

    active_score = _get_active_coherence_score(unified, profile)
    assert active_score == 0.75, f"Expected v2 (0.75), got {active_score}"

    # Identity profile (use_coherence_v2=True)
    profile_identity = get_domain_profile("identity")
    assert profile_identity["use_coherence_v2"] is True

    active_score_identity = _get_active_coherence_score(unified, profile_identity)
    assert active_score_identity == 0.75


def test_get_active_coherence_score_fallback_to_v1_when_v2_missing():
    """
    Test that _get_active_coherence_score falls back to v1 when v2 is None.

    Even when use_coherence_v2=True, if v2 is not available (None), fall back to v1.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.6,
            "coherence_score_v2": None,  # v2 not available
        }
    }

    profile = get_domain_profile("therapy")  # use_coherence_v2=True

    active_score = _get_active_coherence_score(unified, profile)
    assert active_score == 0.6, f"Expected fallback to v1 (0.6), got {active_score}"


def test_policy_flags_use_v2_for_therapy():
    """
    Test that policy flags for therapy domain use v2 when present.

    Therapy has use_coherence_v2=True, so policy flags (needs_grounding, etc.)
    should be computed using v2, not v1.
    """
    # Scenario: v1=0.42 (below therapy min 0.45), v2=0.55 (above min 0.45)
    unified = {
        "coherence": {
            "coherence_score": 0.42,      # v1: would trigger needs_grounding
            "coherence_score_v2": 0.55,   # v2: above threshold, no grounding needed
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.70,
        },
        "entropy": {
            "normalized_entropy": 0.40,
        }
    }

    flags = compute_policy_flags(unified, domain="therapy")

    # With v2=0.55 (above therapy min 0.45), needs_grounding should be False
    assert flags["needs_grounding"] is False, "v2=0.55 is above threshold, should not need grounding"

    # Now test with trading (v1 only)
    flags_trading = compute_policy_flags(unified, domain="trading")

    # With v1=0.42 (below trading min 0.55), needs_grounding should be True
    assert flags_trading["needs_grounding"] is True, "v1=0.42 is below trading threshold, should need grounding"


# ==============================================================================
# Group C: Behavioral Invariance (Default Domains)
# ==============================================================================


def test_behavioral_invariance_trading_domain():
    """
    Test that trading domain behavior is unchanged (v1 only).

    Trading has use_coherence_v2=False, so all policy flags should be
    identical to pre-Phase-4 behavior.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.52,
            "coherence_score_v2": 0.68,  # Present but should be ignored
            "persona_drift_score": 0.38,
            "mapper_volatility_score": 0.42,
            "temporal_arc_score": 0.65,
        },
        "entropy": {
            "normalized_entropy": 0.35,
        }
    }

    flags = compute_policy_flags(unified, domain="trading")

    # Trading min_coherence=0.55, so 0.52 should trigger needs_grounding
    assert flags["needs_grounding"] is True

    # Verify that policy recommendations are based on v1, not v2
    assert flags["coherence_warning"] is False  # 0.52 is not < (0.55 - 0.1)


def test_behavioral_invariance_generic_domain():
    """
    Test that generic domain behavior is unchanged (v1 only).

    Generic has use_coherence_v2=False by default.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.45,
            "coherence_score_v2": 0.72,  # Present but ignored
            "persona_drift_score": 0.50,
            "mapper_volatility_score": 0.45,
            "temporal_arc_score": 0.60,
        },
        "entropy": {
            "normalized_entropy": 0.50,
        }
    }

    flags = compute_policy_flags(unified, domain="generic")

    # Generic min_coherence=0.40, so 0.45 should NOT trigger needs_grounding
    assert flags["needs_grounding"] is False

    # Verify allow_deep_reflection is False (generic doesn't allow LAM)
    assert flags["allow_deep_reflection"] is False


def test_v2_present_but_not_used_in_conservative_domains():
    """
    Test that v2 is present in output but not used in policy for conservative domains.

    Even when v2 is computed and available, domains with use_coherence_v2=False
    should ignore it for policy decisions.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.58,
            "coherence_score_v2": 0.48,  # Lower than v1
            "persona_drift_score": 0.35,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Trading (v1 only): coherence_score=0.58 is above min_coherence=0.55
    flags_trading = compute_policy_flags(unified, domain="trading")
    assert flags_trading["needs_grounding"] is False, "v1=0.58 is above trading threshold"

    # Therapy (v2 enabled): coherence_score_v2=0.48 is above min_coherence=0.45
    flags_therapy = compute_policy_flags(unified, domain="therapy")
    assert flags_therapy["needs_grounding"] is False, "v2=0.48 is above therapy threshold"


def test_phase4_does_not_affect_mapper_recommendations():
    """
    Test that Phase 4 v2 integration does not change mapper recommendations.

    Mapper recommendations (LCM/HRM/LAM) are based on policy flags, which
    in turn are based on active coherence score. Verify that v1-only domains
    get identical mapper recommendations pre- and post-Phase-4.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.48,  # Below trading threshold → needs grounding
            "coherence_score_v2": 0.62,
            "persona_drift_score": 0.45,
            "mapper_volatility_score": 0.50,
            "temporal_arc_score": 0.55,
        },
        "entropy": {"normalized_entropy": 0.45}
    }

    flags = compute_policy_flags(unified, domain="trading")

    # Trading: needs_grounding=True → recommended_mapper should be LCM
    assert flags["needs_grounding"] is True
    assert flags["recommended_mapper"] == "LCM", "Grounding needed → should recommend LCM"


# ==============================================================================
# Group D: Unified API & DILchat
# ==============================================================================


def test_unified_output_includes_coherence_v2():
    """
    Test that unified output JSON includes coherence_score_v2 when available.

    The coherence block should include both:
    - coherence_score (v1, always present)
    - coherence_score_v2 (Phase 4, optional)
    """
    # Create a mock coherence observation with v2
    observer = CoherenceObserver()

    # Mock pipeline context
    class MockContext:
        coherence_state = CoherenceState(convo_id="test", turn_index=0)

    ctx = MockContext()
    ctx.coherence_state.coherence_score = 0.65
    ctx.coherence_state.coherence_score_v2 = 0.72
    ctx.coherence_state.persona_drift_score = 0.30
    ctx.coherence_state.semantic_stability_score = 0.75
    ctx.coherence_state.temporal_arc_score = 0.70
    ctx.coherence_state.mapper_volatility_score = 0.25
    ctx.coherence_state.resonance_index = 0.80
    ctx.coherence_state.tension_index = 0.30
    ctx.coherence_state.arc_alignment_index = 0.70

    # Observe
    observation = observer.observe("test text", ctx)

    # Verify observation includes v2
    assert observation.coherence_score == 0.65
    assert observation.coherence_score_v2 == 0.72

    # Verify serialization includes v2
    serialized = observer.serialize()
    assert "coherence_score" in serialized
    assert "coherence_score_v2" in serialized
    assert serialized["coherence_score_v2"] == 0.72


def test_unified_output_v2_is_none_when_formulas_missing():
    """
    Test that coherence_score_v2 is None when Phase 3 metrics are missing.

    This ensures graceful degradation for turns without formula data.
    """
    observer = CoherenceObserver()

    class MockContext:
        coherence_state = CoherenceState(convo_id="test", turn_index=0)

    ctx = MockContext()
    ctx.coherence_state.coherence_score = 0.65
    ctx.coherence_state.coherence_score_v2 = None  # Not computed (formulas missing)
    ctx.coherence_state.persona_drift_score = 0.30
    ctx.coherence_state.semantic_stability_score = 0.75
    ctx.coherence_state.temporal_arc_score = 0.70
    ctx.coherence_state.mapper_volatility_score = 0.25

    observation = observer.observe("test text", ctx)

    # v2 should be None
    assert observation.coherence_score_v2 is None

    # Serialization should omit None values or include null
    serialized = observer.serialize()
    # Either key is absent, or value is None (both acceptable)
    v2_value = serialized.get("coherence_score_v2")
    assert v2_value is None or "coherence_score_v2" not in serialized


def test_dilchat_diagnostics_include_v2():
    """
    Test that DILchat diagnostics payload includes v2 in raw_unified.

    The raw_unified field should include the full coherence dict with v2.
    This enables observability without changing UI behavior.
    """
    # Create mock unified output
    unified_output = {
        "text": "Test response",
        "coherence": {
            "coherence_score": 0.65,
            "coherence_score_v2": 0.72,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.25,
            "temporal_arc_score": 0.70,
        },
        "symbolic": {},
        "practical": {},
        "mirror": {},
        "dha": {},
        "routing": {},
        "mappers": {},
        "entropy": {},
        "metadata": {"domain": "therapy"},
    }

    policy_flags = {
        "needs_grounding": False,
        "allow_deep_reflection": True,
        "prefer_concrete": False,
        "prefer_arc_mode": False,
        "coherence_warning": False,
        "stability_status": "stable",
        "recommended_style": "reflective",
        "recommended_mapper": "HRM",
    }

    # Import DILchat adapter
    from symbolu_core.adapter.dilchat_adapter import build_dilchat_response

    response = build_dilchat_response(unified_output, policy_flags, domain="therapy")

    # Verify raw_unified includes v2
    assert response.raw_unified is not None
    assert "coherence" in response.raw_unified
    assert response.raw_unified["coherence"]["coherence_score"] == 0.65
    assert response.raw_unified["coherence"]["coherence_score_v2"] == 0.72


def test_dilchat_badges_unchanged_by_v2():
    """
    Test that DILchat badges are NOT changed by v2 in Phase 4.

    Per spec: "Do not change badges/hints in Phase 4 based on v2"
    Badges should be based on policy flags, which use active_coherence_score,
    but the badges themselves should not have v2-specific logic.
    """
    from symbolu_core.adapter.dilchat_adapter import build_dilchat_response

    unified_v1_low = {
        "text": "Test",
        "coherence": {
            "coherence_score": 0.42,
            "coherence_score_v2": 0.58,  # v2 is higher
            "persona_drift_score": 0.50,
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.60,
        },
        "symbolic": {}, "practical": {}, "mirror": {}, "dha": {}, "routing": {},
        "mappers": {}, "entropy": {}, "metadata": {"domain": "trading"},
    }

    # Trading uses v1 only (use_coherence_v2=False)
    # v1=0.42 < trading min 0.55 → needs_grounding=True
    flags_trading = compute_policy_flags(unified_v1_low, domain="trading")
    assert flags_trading["needs_grounding"] is True

    response = build_dilchat_response(unified_v1_low, flags_trading, domain="trading")

    # Should have "Grounding Needed" badge
    badge_labels = [b.label for b in response.badges]
    assert "Grounding Needed" in badge_labels

    # Verify v2 is present in diagnostics but not affecting badges
    assert response.coherence_score == 0.42  # UI displays v1
    assert response.raw_unified["coherence"]["coherence_score_v2"] == 0.58  # v2 in diagnostics


# ==============================================================================
# CI Integration Smoke Test
# ==============================================================================


def test_phase4_ci_smoke():
    """
    Smoke test for CI integration.

    Verifies that Phase 4 integration doesn't break existing coherence pipeline.
    """
    engine = CoherenceEngine(window=10)
    observer = CoherenceObserver()

    # Create mock multi-turn scenario
    temporal_summary = {
        "smi": 0.7,
        "delta_smi": 0.1,
        "bhava_gap": 0.2,
        "tension_corridor": 0.3,
        "bhava_id": 3,
        "bhava_direction": "upward",
    }

    class MockRoutingPlan:
        tier = "hybrid"
        domain = "therapy"
        long_arc_tension = 0.3

    # Turn 1
    state1 = engine.update_state(
        prev_state=None,
        convo_id="smoke_test",
        turn_index=0,
        routing_plan=MockRoutingPlan(),
        mapper_profile={"resolution_level": "medium", "arc_mode": "none"},
        temporal_summary=temporal_summary,
        semantic_signature={},
    )

    assert state1.coherence_score is not None
    assert state1.coherence_score_v2 is not None

    # Turn 2
    state2 = engine.update_state(
        prev_state=state1,
        convo_id="smoke_test",
        turn_index=1,
        routing_plan=MockRoutingPlan(),
        mapper_profile={"resolution_level": "medium", "arc_mode": "none"},
        temporal_summary=temporal_summary,
        semantic_signature={},
    )

    assert state2.coherence_score is not None
    assert state2.coherence_score_v2 is not None

    # Verify determinism: same inputs → same outputs
    assert state1.coherence_score_v2 == state2.coherence_score_v2
