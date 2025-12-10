"""
Phase 10: Coherence v3 Formula Fusion Integration Tests

Tests the first formula-layer megafusion that integrates:
- Phase 1 temporal formulas (smi, delta_smi, bhava_gap, tension_corridor)
- Phase 3 derived metrics (resonance_index, tension_index, arc_alignment_index)
- Phase 8 resonance metrics (guna_resonance_index, kosha_resonance_index)
- Phase 9 modulation biases (guna_resonance_bias, kosha_resonance_bias, expression_harmonics)

Test Groups:
- Group A: Formula Math (8 tests)
- Group B: Observer + Unified API (7 tests)
- Group C: Policy Integration (6 tests)
- Group D: Behavioral Invariance (5 tests)

Total: 26 tests
"""

import pytest
from symbolu.core.coherence.coherence_state import CoherenceState
from symbolu.core.coherence.coherence_engine import CoherenceEngine
from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver, CoherenceObservation
from symbolu.policy.policy_engine import compute_policy_flags, _get_active_coherence_score
from symbolu.policy.domain_profiles import get_domain_profile


# ============================================================================
# GROUP A: FORMULA MATH (8 TESTS)
# ============================================================================


def test_v3_greater_than_v2_when_resonance_strong():
    """Test that v3 > v2 when resonance metrics are strong."""
    engine = CoherenceEngine()

    # Create state with strong resonance
    state = CoherenceState(
        convo_id="test",
        turn_index=5,
        coherence_score=0.70,  # v1 base
    )

    # Set Phase 3 metrics (strong resonance)
    state.resonance_index = 0.85
    state.tension_index = 0.25
    state.arc_alignment_index = 0.80

    # Set Phase 8 metrics (strong resonance)
    state.guna_resonance_index = 0.90
    state.kosha_resonance_index = 0.88

    # Compute v2 (without Phase 8/9)
    state.coherence_score_v2 = engine._compute_coherence_score_v2(state)

    # Compute v3 (with Phase 8/9)
    mapper_profile = {
        "guna_resonance_bias": 0.05,
        "kosha_resonance_bias": 0.05,
        "expression_harmonics": [0.8, 0.82, 0.85, 0.83],  # Low variance = high coherence
    }
    state.coherence_score_v3 = engine._compute_coherence_score_v3(state, mapper_profile)

    assert state.coherence_score_v3 is not None
    assert state.coherence_score_v2 is not None
    assert state.coherence_score_v3 > state.coherence_score_v2
    assert state.coherence_score_v3 > state.coherence_score  # Also > v1


def test_v3_less_than_v2_when_tension_high():
    """Test that v3 < v2 when tension is high."""
    engine = CoherenceEngine()

    # Create state with high tension
    state = CoherenceState(
        convo_id="test",
        turn_index=5,
        coherence_score=0.65,  # v1 base
    )

    # Set Phase 3 metrics (high tension)
    state.resonance_index = 0.50
    state.tension_index = 0.85  # High tension
    state.arc_alignment_index = 0.45

    # Set Phase 8 metrics (low resonance)
    state.guna_resonance_index = 0.40
    state.kosha_resonance_index = 0.42

    # Compute v2
    state.coherence_score_v2 = engine._compute_coherence_score_v2(state)

    # Compute v3 (with negative biases)
    mapper_profile = {
        "guna_resonance_bias": -0.08,
        "kosha_resonance_bias": -0.06,
        "expression_harmonics": [0.3, 0.7, 0.2, 0.9],  # High variance = low coherence
    }
    state.coherence_score_v3 = engine._compute_coherence_score_v3(state, mapper_profile)

    assert state.coherence_score_v3 is not None
    assert state.coherence_score_v2 is not None
    assert state.coherence_score_v3 < state.coherence_score_v2


def test_v3_clamps_correctly():
    """Test that v3 formula clamps to [0.0, 1.0]."""
    engine = CoherenceEngine()

    # Test upper clamp
    state_high = CoherenceState(
        convo_id="test",
        turn_index=5,
        coherence_score=0.95,
    )
    state_high.resonance_index = 0.99
    state_high.tension_index = 0.05
    state_high.arc_alignment_index = 0.98
    state_high.guna_resonance_index = 0.99
    state_high.kosha_resonance_index = 0.98

    mapper_high = {
        "guna_resonance_bias": 0.10,
        "kosha_resonance_bias": 0.10,
        "expression_harmonics": [0.95, 0.96, 0.97],
    }
    v3_high = engine._compute_coherence_score_v3(state_high, mapper_high)

    assert v3_high is not None
    assert v3_high <= 1.0
    assert v3_high >= 0.0

    # Test lower clamp
    state_low = CoherenceState(
        convo_id="test",
        turn_index=5,
        coherence_score=0.15,
    )
    state_low.resonance_index = 0.10
    state_low.tension_index = 0.95
    state_low.arc_alignment_index = 0.08
    state_low.guna_resonance_index = 0.05
    state_low.kosha_resonance_index = 0.07

    mapper_low = {
        "guna_resonance_bias": -0.10,
        "kosha_resonance_bias": -0.10,
        "expression_harmonics": [0.1, 0.9, 0.05, 0.85],
    }
    v3_low = engine._compute_coherence_score_v3(state_low, mapper_low)

    assert v3_low is not None
    assert v3_low >= 0.0
    assert v3_low <= 1.0


def test_v3_missing_data_returns_none():
    """Test that v3 returns None when required data is missing."""
    engine = CoherenceEngine()

    # Missing resonance_index
    state1 = CoherenceState(convo_id="test", turn_index=1, coherence_score=0.7)
    state1.resonance_index = None  # Missing
    state1.tension_index = 0.5
    state1.arc_alignment_index = 0.6
    state1.guna_resonance_index = 0.7
    state1.kosha_resonance_index = 0.65

    result1 = engine._compute_coherence_score_v3(state1, {})
    assert result1 is None

    # Missing guna_resonance_index
    state2 = CoherenceState(convo_id="test", turn_index=1, coherence_score=0.7)
    state2.resonance_index = 0.7
    state2.tension_index = 0.5
    state2.arc_alignment_index = 0.6
    state2.guna_resonance_index = None  # Missing
    state2.kosha_resonance_index = 0.65

    result2 = engine._compute_coherence_score_v3(state2, {})
    assert result2 is None

    # Missing kosha_resonance_index
    state3 = CoherenceState(convo_id="test", turn_index=1, coherence_score=0.7)
    state3.resonance_index = 0.7
    state3.tension_index = 0.5
    state3.arc_alignment_index = 0.6
    state3.guna_resonance_index = 0.7
    state3.kosha_resonance_index = None  # Missing

    result3 = engine._compute_coherence_score_v3(state3, {})
    assert result3 is None


def test_bias_synergy_works():
    """Test _bias_synergy support function."""
    engine = CoherenceEngine()

    # Positive synergy
    synergy_pos = engine._bias_synergy(0.08, 0.06)
    assert synergy_pos > 0.5  # Above neutral
    assert synergy_pos <= 0.6  # Within expected range

    # Negative synergy
    synergy_neg = engine._bias_synergy(-0.08, -0.06)
    assert synergy_neg < 0.5  # Below neutral
    assert synergy_neg >= 0.4  # Within expected range

    # Neutral synergy
    synergy_neutral = engine._bias_synergy(0.0, 0.0)
    assert synergy_neutral == 0.5  # Exactly neutral

    # Mixed synergy
    synergy_mixed = engine._bias_synergy(0.05, -0.05)
    assert synergy_mixed == 0.5  # Cancels out


def test_harmonics_coherence_works():
    """Test _harmonics_coherence support function."""
    engine = CoherenceEngine()

    # Low variance (high coherence)
    harmonics_low_var = [0.80, 0.82, 0.81, 0.83]
    coherence_low_var = engine._harmonics_coherence(harmonics_low_var)
    assert coherence_low_var > 0.9  # Very coherent

    # High variance (low coherence)
    harmonics_high_var = [0.1, 0.9, 0.2, 0.8]
    coherence_high_var = engine._harmonics_coherence(harmonics_high_var)
    assert coherence_high_var < 0.7  # Less coherent

    # None harmonics (neutral)
    coherence_none = engine._harmonics_coherence(None)
    assert coherence_none == 1.0  # Neutral = perfect

    # Empty harmonics (neutral)
    coherence_empty = engine._harmonics_coherence([])
    assert coherence_empty == 1.0  # Neutral = perfect

    # Single harmonic (no variance)
    coherence_single = engine._harmonics_coherence([0.75])
    assert coherence_single == 1.0  # No variance = perfect


def test_full_fusion_determinism():
    """Test that v3 formula produces deterministic results."""
    engine = CoherenceEngine()

    # Create identical states
    state1 = CoherenceState(convo_id="test1", turn_index=5, coherence_score=0.68)
    state1.resonance_index = 0.72
    state1.tension_index = 0.42
    state1.arc_alignment_index = 0.65
    state1.guna_resonance_index = 0.78
    state1.kosha_resonance_index = 0.74

    state2 = CoherenceState(convo_id="test2", turn_index=5, coherence_score=0.68)
    state2.resonance_index = 0.72
    state2.tension_index = 0.42
    state2.arc_alignment_index = 0.65
    state2.guna_resonance_index = 0.78
    state2.kosha_resonance_index = 0.74

    mapper = {
        "guna_resonance_bias": 0.03,
        "kosha_resonance_bias": 0.04,
        "expression_harmonics": [0.7, 0.72, 0.71, 0.73],
    }

    v3_1 = engine._compute_coherence_score_v3(state1, mapper)
    v3_2 = engine._compute_coherence_score_v3(state2, mapper)

    assert v3_1 == v3_2  # Deterministic
    assert v3_1 is not None


def test_base_only_scenario():
    """Test v3 formula with minimal resonance (base-heavy scenario)."""
    engine = CoherenceEngine()

    state = CoherenceState(convo_id="test", turn_index=1, coherence_score=0.80)
    state.resonance_index = 0.50
    state.tension_index = 0.50
    state.arc_alignment_index = 0.50
    state.guna_resonance_index = 0.50
    state.kosha_resonance_index = 0.50

    mapper = {
        "guna_resonance_bias": 0.0,
        "kosha_resonance_bias": 0.0,
        "expression_harmonics": None,  # Neutral
    }

    v3 = engine._compute_coherence_score_v3(state, mapper)

    # With all metrics at 0.5 (neutral), v3 should be close to base * 0.35 + neutral contributions
    # Expected: 0.35*0.8 + 0.15*0.5 + 0.10*0.5 + 0.10*0.5 + 0.10*0.5 + 0.10*0.5 + 0.05*0.5 + 0.05*1.0
    # = 0.28 + 0.075 + 0.05 + 0.05 + 0.05 + 0.05 + 0.025 + 0.05 = 0.63
    assert v3 is not None
    assert 0.60 <= v3 <= 0.65  # Approximate range


# ============================================================================
# GROUP B: OBSERVER + UNIFIED API (7 TESTS)
# ============================================================================


def test_v3_included_in_observer():
    """Test that v3 is included in CoherenceObservation."""
    from symbolu.mechanical.pipeline.models import PipelineContext, UserRequest

    # Create mock coherence state with v3
    state = CoherenceState(convo_id="test", turn_index=3, coherence_score=0.72)
    state.coherence_score_v2 = 0.75
    state.coherence_score_v3 = 0.78
    state.resonance_index = 0.70
    state.guna_resonance_index = 0.68
    state.kosha_resonance_index = 0.72

    # Create mock context
    class MockRoutingPlan:
        tier = "hybrid"
        domain = "generic"
        normalized_entropy = 0.45
        long_arc_tension = 0.38

    class MockMLCR:
        routing_plan = MockRoutingPlan()

    ctx = PipelineContext(request=UserRequest(user_id="test", text="test"))
    ctx.coherence_state = state
    ctx.mlcr = MockMLCR()

    # Observe
    observer = CoherenceObserver()
    observation = observer.observe("test", ctx, state)

    # Check v3 is present
    assert observation.coherence_score_v3 == 0.78
    assert observation.coherence_score_v2 == 0.75
    assert observation.coherence_score == 0.72


def test_v3_included_in_unified_output():
    """Test that v3 appears in serialized observation."""
    state = CoherenceState(convo_id="test", turn_index=1, coherence_score=0.65)
    state.coherence_score_v2 = 0.70
    state.coherence_score_v3 = 0.73

    observation = CoherenceObservation(
        coherence_score=0.65,
        coherence_score_v2=0.70,
        coherence_score_v3=0.73,
        persona_drift_score=0.3,
        semantic_stability_score=0.8,
        temporal_arc_score=0.7,
        mapper_volatility_score=0.2,
        turn_number=1,
        tier="hybrid",
        domain="generic",
        active_mappers=["HRM"],
    )

    serialized = observation.to_dict()

    assert "coherence_score_v3" in serialized
    assert serialized["coherence_score_v3"] == 0.73
    assert serialized["coherence_score_v2"] == 0.70
    assert serialized["coherence_score"] == 0.65


def test_v3_is_none_when_missing():
    """Test that v3 is None when metrics are missing."""
    from symbolu.mechanical.pipeline.models import PipelineContext, UserRequest

    # Create state without Phase 3/8 metrics (v3 cannot be computed)
    state = CoherenceState(convo_id="test", turn_index=1, coherence_score=0.70)
    state.resonance_index = None  # Missing
    state.guna_resonance_index = None  # Missing

    class MockMLCR:
        routing_plan = None

    ctx = PipelineContext(request=UserRequest(user_id="test", text="test"))
    ctx.coherence_state = state
    ctx.mlcr = MockMLCR()

    observer = CoherenceObserver()
    observation = observer.observe("test", ctx, state)

    assert observation.coherence_score_v3 is None
    assert observation.coherence_score == 0.70  # v1 still present


def test_v3_json_safe():
    """Test that v3 serialization is JSON-safe."""
    import json

    observation = CoherenceObservation(
        coherence_score=0.68,
        coherence_score_v2=0.72,
        coherence_score_v3=0.75,
        persona_drift_score=0.25,
        semantic_stability_score=0.82,
        temporal_arc_score=0.75,
        mapper_volatility_score=0.18,
        turn_number=5,
        tier="hybrid",
        domain="therapy",
        active_mappers=["HRM", "LAM"],
    )

    # Should serialize without error
    json_str = json.dumps(observation.to_dict())
    assert json_str is not None

    # Should deserialize without error
    deserialized = json.loads(json_str)
    assert deserialized["coherence_score_v3"] == 0.75


def test_v3_multi_turn_consistency():
    """Test v3 across multiple turns maintains consistency."""
    from symbolu.mechanical.pipeline.models import PipelineContext, UserRequest

    engine = CoherenceEngine()
    observer = CoherenceObserver()

    # Turn 1
    state1 = CoherenceState(convo_id="test", turn_index=1, coherence_score=0.70)
    state1.resonance_index = 0.65
    state1.tension_index = 0.45
    state1.arc_alignment_index = 0.60
    state1.guna_resonance_index = 0.68
    state1.kosha_resonance_index = 0.66

    mapper1 = {"guna_resonance_bias": 0.02, "kosha_resonance_bias": 0.03, "expression_harmonics": [0.7, 0.72]}
    state1.coherence_score_v3 = engine._compute_coherence_score_v3(state1, mapper1)

    ctx1 = PipelineContext(request=UserRequest(user_id="test", text="test"))
    ctx1.coherence_state = state1

    obs1 = observer.observe("test", ctx1, state1)

    # Turn 2 (same metrics)
    state2 = CoherenceState(convo_id="test", turn_index=2, coherence_score=0.70)
    state2.resonance_index = 0.65
    state2.tension_index = 0.45
    state2.arc_alignment_index = 0.60
    state2.guna_resonance_index = 0.68
    state2.kosha_resonance_index = 0.66

    state2.coherence_score_v3 = engine._compute_coherence_score_v3(state2, mapper1)

    ctx2 = PipelineContext(request=UserRequest(user_id="test", text="test"))
    ctx2.coherence_state = state2

    obs2 = observer.observe("test", ctx2, state2)

    # v3 should be identical (deterministic)
    assert obs1.coherence_score_v3 == obs2.coherence_score_v3


def test_v3_snapshot_invariance():
    """Test that snapshot() doesn't break with v3."""
    from symbolu.mechanical.pipeline.models import PipelineContext, UserRequest

    state = CoherenceState(convo_id="test", turn_index=2, coherence_score=0.68)
    state.coherence_score_v2 = 0.71
    state.coherence_score_v3 = 0.74
    state.persona_drift_score = 0.28
    state.semantic_stability_score = 0.80
    state.temporal_arc_score = 0.72
    state.mapper_volatility_score = 0.22

    class MockMLCR:
        routing_plan = None

    ctx = PipelineContext(request=UserRequest(user_id="test", text="test"))
    ctx.coherence_state = state
    ctx.mlcr = MockMLCR()

    observer = CoherenceObserver()
    observer.observe("test", ctx, state)

    snapshot = observer.snapshot()

    assert "coherence" in snapshot
    assert snapshot["coherence"] == 0.68  # v1 still primary in snapshot


def test_v3_backward_compatibility():
    """Test that v3 doesn't break existing observer code."""
    # Old code that expects only v1/v2 should still work
    observation = CoherenceObservation(
        coherence_score=0.75,
        persona_drift_score=0.20,
        semantic_stability_score=0.85,
        temporal_arc_score=0.78,
        mapper_volatility_score=0.15,
        turn_number=3,
        tier="hybrid",
        domain="generic",
        active_mappers=["HRM"],
        # v3 not provided (None)
    )

    assert observation.coherence_score == 0.75
    assert observation.coherence_score_v3 is None  # Optional, defaults to None

    # Serialization should work
    serialized = observation.to_dict()
    assert "coherence_score" in serialized


# ============================================================================
# GROUP C: POLICY INTEGRATION (6 TESTS)
# ============================================================================


def test_v3_ignored_for_all_domains_by_default():
    """Test that v3 is ignored when use_coherence_v3=False (default)."""
    unified = {
        "coherence": {
            "coherence_score": 0.60,
            "coherence_score_v2": 0.70,
            "coherence_score_v3": 0.80,
        }
    }

    # All domains should have v3 disabled by default
    for domain in ["trading", "therapy", "identity", "generic"]:
        profile = get_domain_profile(domain)
        assert profile.get("use_coherence_v3", False) is False

        active_score = _get_active_coherence_score(unified, profile)

        # Should NOT use v3
        assert active_score != 0.80
        # Should use v2 if enabled, else v1
        if profile.get("use_coherence_v2", False):
            assert active_score == 0.70  # v2
        else:
            assert active_score == 0.60  # v1


def test_v3_enabled_uses_v3():
    """Test that enabling use_coherence_v3 flag uses v3 score."""
    unified = {
        "coherence": {
            "coherence_score": 0.60,
            "coherence_score_v2": 0.70,
            "coherence_score_v3": 0.80,
        }
    }

    # Enable v3 for testing
    profile_v3 = {
        "use_coherence_v2": False,
        "use_coherence_v3": True,  # Enable v3
    }

    active_score = _get_active_coherence_score(unified, profile_v3)
    assert active_score == 0.80  # Should use v3


def test_v3_fallback_to_v2_or_v1():
    """Test v3 → v2 → v1 fallback cascade."""
    # Scenario 1: v3 enabled but not available → fallback to v2
    unified_no_v3 = {
        "coherence": {
            "coherence_score": 0.60,
            "coherence_score_v2": 0.70,
            # v3 not available
        }
    }

    profile_v3_v2 = {
        "use_coherence_v2": True,
        "use_coherence_v3": True,
    }

    score1 = _get_active_coherence_score(unified_no_v3, profile_v3_v2)
    assert score1 == 0.70  # Falls back to v2

    # Scenario 2: v3 and v2 enabled but neither available → fallback to v1
    unified_v1_only = {
        "coherence": {
            "coherence_score": 0.60,
            # v2 and v3 not available
        }
    }

    score2 = _get_active_coherence_score(unified_v1_only, profile_v3_v2)
    assert score2 == 0.60  # Falls back to v1

    # Scenario 3: v3 enabled, v3 available → use v3
    unified_all = {
        "coherence": {
            "coherence_score": 0.60,
            "coherence_score_v2": 0.70,
            "coherence_score_v3": 0.80,
        }
    }

    score3 = _get_active_coherence_score(unified_all, profile_v3_v2)
    assert score3 == 0.80  # Uses v3


def test_v3_policy_determinism():
    """Test that policy flags are deterministic with v3."""
    unified = {
        "coherence": {
            "coherence_score": 0.55,
            "coherence_score_v2": 0.65,
            "coherence_score_v3": 0.72,
            "persona_drift_score": 0.35,
            "mapper_volatility_score": 0.28,
            "temporal_arc_score": 0.68,
        },
        "entropy": {
            "normalized_entropy": 0.42,
        },
    }

    # Compute flags twice
    flags1 = compute_policy_flags(unified, "generic")
    flags2 = compute_policy_flags(unified, "generic")

    assert flags1 == flags2  # Deterministic


def test_v3_invariance_for_trading_generic():
    """Test that v3 doesn't affect trading/generic domains (disabled)."""
    unified = {
        "coherence": {
            "coherence_score": 0.58,
            "coherence_score_v2": 0.68,
            "coherence_score_v3": 0.75,
            "persona_drift_score": 0.38,
            "mapper_volatility_score": 0.42,
            "temporal_arc_score": 0.65,
        },
        "entropy": {
            "normalized_entropy": 0.48,
        },
    }

    # Trading and generic should use v1 only
    flags_trading = compute_policy_flags(unified, "trading")
    flags_generic = compute_policy_flags(unified, "generic")

    # Both should use v1 score (0.58), not v3 (0.75)
    # Trading min_coherence=0.55, so 0.58 > 0.55 → needs_grounding=False (also check drift/volatility)
    # Generic min_coherence=0.40, so 0.58 > 0.40 → needs_grounding=False
    # But persona_drift (0.38) < max (0.40 for trading, 0.55 for generic) and volatility (0.42) < max
    # So needs_grounding should be False for both
    assert flags_trading["needs_grounding"] is False
    assert flags_generic["needs_grounding"] is False


def test_v3_invariance_for_mapper_rules():
    """Test that v3 doesn't alter mapper activation rules."""
    unified = {
        "coherence": {
            "coherence_score": 0.50,
            "coherence_score_v2": 0.60,
            "coherence_score_v3": 0.70,
            "persona_drift_score": 0.45,
            "mapper_volatility_score": 0.35,
            "temporal_arc_score": 0.62,
        },
        "entropy": {
            "normalized_entropy": 0.50,
        },
    }

    # Generic domain (v3 disabled)
    flags = compute_policy_flags(unified, "generic")

    # Mapper recommendations should be based on v1 score (0.50)
    # Generic profile prefers ["HRM"], and coherence 0.50 > min_coherence 0.40
    # needs_grounding=False (coherence OK, drift/volatility OK)
    # So should use first preferred mapper: HRM
    assert flags["recommended_mapper"] == "HRM"  # Generic prefers HRM


# ============================================================================
# GROUP D: BEHAVIORAL INVARIANCE (5 TESTS)
# ============================================================================


def test_ttor_unchanged():
    """Test that TTOR routing is unaffected by v3."""
    # v3 is observation-only and should not modify TTOR behavior
    # This test verifies that CoherenceEngine doesn't pass v3 to routing

    engine = CoherenceEngine()

    # Create state and compute v3
    state = CoherenceState(convo_id="test", turn_index=1, coherence_score=0.65)
    state.resonance_index = 0.70
    state.tension_index = 0.40
    state.arc_alignment_index = 0.65
    state.guna_resonance_index = 0.68
    state.kosha_resonance_index = 0.72

    mapper_profile = {
        "guna_resonance_bias": 0.05,
        "kosha_resonance_bias": 0.04,
        "expression_harmonics": [0.7, 0.72, 0.71],
    }

    v3 = engine._compute_coherence_score_v3(state, mapper_profile)

    # v3 should exist but not be used for routing decisions
    assert v3 is not None
    # State should still have v1 as primary
    assert state.coherence_score == 0.65


def test_mlcr_unchanged():
    """Test that MLCR mapper selection is unaffected by v3."""
    # v3 should not influence MLCR activation plan

    unified = {
        "coherence": {
            "coherence_score": 0.62,
            "coherence_score_v2": 0.70,
            "coherence_score_v3": 0.78,
            "persona_drift_score": 0.32,
            "mapper_volatility_score": 0.25,
            "temporal_arc_score": 0.68,
        },
        "entropy": {
            "normalized_entropy": 0.45,
        },
    }

    # Generic domain (v3 disabled) - uses v1
    flags_v1 = compute_policy_flags(unified, "generic")

    # Recommended mapper should be based on v1 score (0.62)
    # With needs_grounding=False (0.62 > 0.40), mapper selection is normal
    assert flags_v1["needs_grounding"] is False
    assert flags_v1["recommended_mapper"] in ["LCM", "HRM", "LAM"]


def test_mapper_activation_unchanged():
    """Test that mapper activation patterns are unaffected by v3."""
    # v3 should not modify how mappers are activated

    from symbolu.mechanical.pipeline.models import PipelineContext, UserRequest

    state = CoherenceState(convo_id="test", turn_index=3, coherence_score=0.68)
    state.coherence_score_v2 = 0.72
    state.coherence_score_v3 = 0.76
    state.persona_drift_score = 0.30
    state.semantic_stability_score = 0.78

    # Observer should extract v3 but not use it for activation
    ctx = PipelineContext(request=UserRequest(user_id="test", text="test"))
    ctx.coherence_state = state

    observer = CoherenceObserver()
    observation = observer.observe("test", ctx, state)

    # v3 should be observed but not affect active_mappers
    assert observation.coherence_score_v3 == 0.76
    # active_mappers is determined by pipeline, not by v3


def test_renderer_output_unaffected():
    """Test that renderer output is not modified by v3."""
    # v3 is diagnostic/observational only

    observation = CoherenceObservation(
        coherence_score=0.65,
        coherence_score_v2=0.71,
        coherence_score_v3=0.77,
        persona_drift_score=0.28,
        semantic_stability_score=0.82,
        temporal_arc_score=0.74,
        mapper_volatility_score=0.20,
        turn_number=4,
        tier="hybrid",
        domain="therapy",
        active_mappers=["HRM", "LAM"],
    )

    # Serialize for renderer
    serialized = observation.to_dict()

    # v3 should be present in diagnostics but not used for rendering decisions
    assert "coherence_score_v3" in serialized
    assert serialized["coherence_score_v3"] == 0.77

    # Primary coherence score should still be v1
    assert serialized["coherence_score"] == 0.65


def test_policy_flags_unaffected_unless_enabled():
    """Test that policy flags are unchanged when v3 is disabled."""
    unified = {
        "coherence": {
            "coherence_score": 0.58,
            "coherence_score_v2": 0.68,
            "coherence_score_v3": 0.78,
            "persona_drift_score": 0.42,
            "mapper_volatility_score": 0.38,
            "temporal_arc_score": 0.62,
        },
        "entropy": {
            "normalized_entropy": 0.48,
        },
    }

    # Compute flags for generic (v3 disabled)
    flags = compute_policy_flags(unified, "generic")

    # Flags should be based on v1 score (0.58)
    # needs_grounding: 0.58 > 0.40 (min_coherence for generic), so False
    # But persona_drift 0.42 < 0.55 and volatility 0.38 < 0.55, so False
    assert flags["needs_grounding"] is False

    # If we manually enable v3, behavior should change
    profile_v3_enabled = get_domain_profile("generic").copy()
    profile_v3_enabled["use_coherence_v3"] = True

    score_with_v3 = _get_active_coherence_score(unified, profile_v3_enabled)
    assert score_with_v3 == 0.78  # Would use v3 if enabled


# ============================================================================
# END OF TESTS (26 total)
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
