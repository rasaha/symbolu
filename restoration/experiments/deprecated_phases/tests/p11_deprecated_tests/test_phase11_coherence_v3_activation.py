"""
Phase 11 Coherence v3 Selective Domain Activation Tests
========================================================

Tests for Phase 11 Symbol-U Formula Fusion v1.0:
"Selective Domain Activation & v3 Stability Tests v1.0"

These tests verify that Phase 11 coherence score v3 (megafusion) is:
- ENABLED for therapy and identity domains only
- DISABLED (not used for policy) for trading and generic domains
- Properly propagated through coherence state → observer → unified output → policy
- Feature-flag gated with strict behavioral invariance for disabled domains
- Fully backward compatible (no routing/mapper/DHA changes)

All changes must be:
- Zero-LLM (pure math + rules, deterministic)
- Non-invasive (v1/v2 behavior fully intact for disabled domains)
- CI-safe (all tests pass with strict invariance guards)
- Policy-layer only (no routing/TTOR/mapper/Fusion changes)

Test Coverage:
Group A - Domain Activation Tests (~5 tests)
Group B - Policy Integration Tests (~5 tests)
Group C - Behavioral Invariance Tests (~6 tests)
Group D - API / Observer Tests (~5 tests)
Total: ~21 tests
"""

import pytest
from typing import Dict, Any, Optional

from symbolu.core.coherence.coherence_engine import CoherenceEngine
from symbolu.core.coherence.coherence_state import CoherenceState
from symbolu.policy.domain_profiles import get_domain_profile
from symbolu.policy.policy_engine import compute_policy_flags, _get_active_coherence_score
from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver


# ==============================================================================
# Group A: Domain Activation Tests
# ==============================================================================


def test_therapy_domain_v3_enabled():
    """
    Test that therapy domain has v3 ENABLED (use_coherence_v3=True).

    Therapy should use v3 for policy decisions when v3 is available.
    """
    profile = get_domain_profile("therapy")
    assert profile["use_coherence_v3"] is True, "Therapy should have v3 enabled in Phase 11"


def test_identity_domain_v3_enabled():
    """
    Test that identity domain has v3 ENABLED (use_coherence_v3=True).

    Identity should use v3 for policy decisions when v3 is available.
    """
    profile = get_domain_profile("identity")
    assert profile["use_coherence_v3"] is True, "Identity should have v3 enabled in Phase 11"


def test_trading_domain_v3_disabled():
    """
    Test that trading domain has v3 DISABLED (use_coherence_v3=False).

    Trading should NOT use v3 for policy decisions, even when v3 is present.
    """
    profile = get_domain_profile("trading")
    assert profile["use_coherence_v3"] is False, "Trading should keep v3 disabled for stability"


def test_generic_domain_v3_disabled():
    """
    Test that generic domain has v3 DISABLED (use_coherence_v3=False).

    Generic should NOT use v3 for policy decisions, even when v3 is present.
    """
    profile = get_domain_profile("generic")
    assert profile["use_coherence_v3"] is False, "Generic should keep v3 disabled by default"


def test_v3_priority_cascade_in_active_coherence_score():
    """
    Test the v3 → v2 → v1 priority cascade in _get_active_coherence_score.

    Priority order:
    1. v3 (if use_coherence_v3=True AND v3 available)
    2. v2 (if use_coherence_v2=True AND v2 available)
    3. v1 (always fallback)
    """
    # Test Case 1: v3 enabled, v3 available → use v3
    unified_all = {
        "coherence": {
            "coherence_score": 0.60,      # v1
            "coherence_score_v2": 0.72,   # v2
            "coherence_score_v3": 0.85,   # v3
            "coherence_v3_quality": 0.75, # Quality gate
        }
    }

    profile_v3 = get_domain_profile("therapy")  # use_coherence_v3=True
    active_score = _get_active_coherence_score(unified_all, profile_v3)
    assert active_score == unified_all["coherence"]["coherence_score_v3"], f"Expected v3, got {active_score}"

    # Test Case 2: v3 disabled, v2 enabled → use v2
    profile_v2_only = get_domain_profile("trading")
    # Override for test: simulate v2 enabled but v3 disabled
    profile_v2_only_modified = profile_v2_only.copy()
    profile_v2_only_modified["use_coherence_v2"] = True  # Enable v2 for this test
    profile_v2_only_modified["use_coherence_v3"] = False

    active_score_v2 = _get_active_coherence_score(unified_all, profile_v2_only_modified)
    assert active_score_v2 == 0.72, f"Expected v2 (0.72) when v3 disabled, got {active_score_v2}"

    # Test Case 3: Both v2 and v3 disabled → use v1
    profile_v1_only = get_domain_profile("trading")  # Both v2 and v3 disabled
    active_score_v1 = _get_active_coherence_score(unified_all, profile_v1_only)
    assert active_score_v1 == 0.60, f"Expected v1 (0.60) when v2/v3 disabled, got {active_score_v1}"


# ==============================================================================
# Group B: Policy Integration Tests
# ==============================================================================


def test_therapy_policy_uses_v3_when_available():
    """
    Test that therapy domain policy flags use v3 when v3 is available.

    Scenario: v1=0.40, v2=0.42, v3=0.55
    Therapy min_coherence=0.45
    - v1 would trigger needs_grounding (0.40 < 0.45)
    - v2 would trigger needs_grounding (0.42 < 0.45)
    - v3 should NOT trigger needs_grounding (0.55 >= 0.45)
    """
    unified = {
        "coherence": {
            "coherence_score": 0.40,      # v1: below threshold
            "coherence_score_v2": 0.42,   # v2: below threshold
            "coherence_score_v3": 0.55,   # v3: ABOVE threshold
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.25,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    flags = compute_policy_flags(unified, domain="therapy")

    # With v3=0.55 (above therapy min 0.45), needs_grounding should be False
    assert flags["needs_grounding"] is False, "v3=0.55 is above threshold, should not need grounding"
    assert flags["coherence_warning"] is False, "v3=0.55 should not trigger warning"


def test_identity_policy_uses_v3_when_available():
    """
    Test that identity domain policy flags use v3 when v3 is available.

    Scenario: v1=0.45, v2=0.48, v3=0.62
    Identity min_coherence=0.50
    - v1 would trigger needs_grounding (0.45 < 0.50)
    - v2 would trigger needs_grounding (0.48 < 0.50)
    - v3 should NOT trigger needs_grounding (0.62 >= 0.50)
    """
    unified = {
        "coherence": {
            "coherence_score": 0.45,      # v1: below threshold
            "coherence_score_v2": 0.48,   # v2: below threshold
            "coherence_score_v3": 0.62,   # v3: ABOVE threshold
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.35,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.75,
        },
        "entropy": {"normalized_entropy": 0.45}
    }

    flags = compute_policy_flags(unified, domain="identity")

    # With v3=0.62 (above identity min 0.50), needs_grounding should be False
    assert flags["needs_grounding"] is False, "v3=0.62 is above threshold, should not need grounding"


def test_trading_policy_ignores_v3_uses_v1():
    """
    Test that trading domain policy flags IGNORE v3 and use v1.

    Scenario: v1=0.52, v2=0.68, v3=0.72
    Trading min_coherence=0.55
    Trading has use_coherence_v2=False, use_coherence_v3=False
    - Should use v1=0.52 (below threshold) → needs_grounding=True
    - Should IGNORE v2 and v3
    """
    unified = {
        "coherence": {
            "coherence_score": 0.52,      # v1: below trading threshold 0.55
            "coherence_score_v2": 0.68,   # v2: above threshold (should be ignored)
            "coherence_score_v3": 0.72,   # v3: above threshold (should be ignored)
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.35,
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.65,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    flags = compute_policy_flags(unified, domain="trading")

    # Trading should use v1=0.52, which is below min_coherence=0.55
    assert flags["needs_grounding"] is True, "Trading should use v1=0.52 (below 0.55) and need grounding"


def test_generic_policy_ignores_v3_uses_v1():
    """
    Test that generic domain policy flags IGNORE v3 and use v1.

    Generic has use_coherence_v2=False, use_coherence_v3=False.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.38,      # v1: below generic min 0.40
            "coherence_score_v2": 0.65,   # v2: should be ignored
            "coherence_score_v3": 0.75,   # v3: should be ignored
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.50,
            "mapper_volatility_score": 0.45,
            "temporal_arc_score": 0.60,
        },
        "entropy": {"normalized_entropy": 0.50}
    }

    flags = compute_policy_flags(unified, domain="generic")

    # Generic should use v1=0.38, which is below min_coherence=0.40
    assert flags["needs_grounding"] is True, "Generic should use v1=0.38 (below 0.40) and need grounding"


def test_v3_policy_deterministic():
    """
    Test that v3-based policy decisions are fully deterministic.

    Same inputs should always produce same policy flags.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.42,
            "coherence_score_v2": 0.48,
            "coherence_score_v3": 0.58,
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.35,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Run policy computation twice
    flags1 = compute_policy_flags(unified, domain="therapy")
    flags2 = compute_policy_flags(unified, domain="therapy")

    # All flags should be identical
    assert flags1 == flags2, "Policy flags must be deterministic"


# ==============================================================================
# Group C: Behavioral Invariance Tests
# ==============================================================================


def test_v3_does_not_change_mapper_recommendations_for_disabled_domains():
    """
    Test that v3 presence does NOT change mapper recommendations for trading/generic.

    Mapper recommendations should be identical to pre-Phase-11 behavior.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.48,      # Below trading threshold → LCM
            "coherence_score_v2": 0.65,
            "coherence_score_v3": 0.72,
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.45,
            "mapper_volatility_score": 0.50,
            "temporal_arc_score": 0.55,
        },
        "entropy": {"normalized_entropy": 0.45}
    }

    flags = compute_policy_flags(unified, domain="trading")

    # Trading: v1=0.48 < 0.55 → needs_grounding=True → recommended_mapper=LCM
    assert flags["needs_grounding"] is True
    assert flags["recommended_mapper"] == "LCM", "Trading should recommend LCM when grounding needed"


def test_v3_does_not_change_stability_status_for_disabled_domains():
    """
    Test that v3 does NOT change stability_status for trading/generic.

    Stability status should be based on v1 only for these domains.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.58,      # v1: moderate
            "coherence_score_v2": 0.75,   # v2: high
            "coherence_score_v3": 0.82,   # v3: very high
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.38,
            "mapper_volatility_score": 0.35,
            "temporal_arc_score": 0.65,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    flags_trading = compute_policy_flags(unified, domain="trading")

    # Stability status should be based on v1 score (0.58)
    # With drift=0.38 and coherence=0.58, should NOT be "stable" (requires coherence >= 0.65)
    assert flags_trading["stability_status"] != "stable", "Trading stability should use v1, not v3"


def test_trading_domain_full_behavioral_invariance():
    """
    Test complete behavioral invariance for trading domain.

    All policy flags should be identical to pre-Phase-11 when v3 is present.
    """
    unified_with_v3 = {
        "coherence": {
            "coherence_score": 0.56,
            "coherence_score_v2": 0.70,
            "coherence_score_v3": 0.78,
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.38,
            "mapper_volatility_score": 0.42,
            "temporal_arc_score": 0.65,
        },
        "entropy": {"normalized_entropy": 0.35}
    }

    unified_without_v3 = {
        "coherence": {
            "coherence_score": 0.56,
            # No v2 or v3
            "persona_drift_score": 0.38,
            "mapper_volatility_score": 0.42,
            "temporal_arc_score": 0.65,
        },
        "entropy": {"normalized_entropy": 0.35}
    }

    flags_with_v3 = compute_policy_flags(unified_with_v3, domain="trading")
    flags_without_v3 = compute_policy_flags(unified_without_v3, domain="trading")

    # All core flags should be identical
    assert flags_with_v3["needs_grounding"] == flags_without_v3["needs_grounding"]
    assert flags_with_v3["allow_deep_reflection"] == flags_without_v3["allow_deep_reflection"]
    assert flags_with_v3["prefer_concrete"] == flags_without_v3["prefer_concrete"]
    assert flags_with_v3["prefer_arc_mode"] == flags_without_v3["prefer_arc_mode"]
    assert flags_with_v3["coherence_warning"] == flags_without_v3["coherence_warning"]
    assert flags_with_v3["stability_status"] == flags_without_v3["stability_status"]
    assert flags_with_v3["recommended_mapper"] == flags_without_v3["recommended_mapper"]


def test_generic_domain_full_behavioral_invariance():
    """
    Test complete behavioral invariance for generic domain.

    All policy flags should be identical to pre-Phase-11 when v3 is present.
    """
    unified_with_v3 = {
        "coherence": {
            "coherence_score": 0.45,
            "coherence_score_v2": 0.68,
            "coherence_score_v3": 0.75,
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.50,
            "mapper_volatility_score": 0.45,
            "temporal_arc_score": 0.60,
        },
        "entropy": {"normalized_entropy": 0.50}
    }

    unified_without_v3 = {
        "coherence": {
            "coherence_score": 0.45,
            "persona_drift_score": 0.50,
            "mapper_volatility_score": 0.45,
            "temporal_arc_score": 0.60,
        },
        "entropy": {"normalized_entropy": 0.50}
    }

    flags_with_v3 = compute_policy_flags(unified_with_v3, domain="generic")
    flags_without_v3 = compute_policy_flags(unified_without_v3, domain="generic")

    # All flags should be identical
    assert flags_with_v3 == flags_without_v3, "Generic domain behavior must be 100% invariant"


def test_v3_does_not_change_allow_deep_reflection():
    """
    Test that v3 does not change allow_deep_reflection flag logic.

    This flag is based on allow_lam + coherence + drift thresholds.
    The logic should be identical, only the coherence value changes for v3-enabled domains.
    """
    # Therapy (v3 enabled): v3 makes coherence adequate → allow_deep_reflection=True
    unified_therapy = {
        "coherence": {
            "coherence_score": 0.42,      # v1: below therapy min 0.45
            "coherence_score_v2": 0.44,   # v2: still below
            "coherence_score_v3": 0.52,   # v3: above threshold
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.50,  # acceptable drift
            "mapper_volatility_score": 0.35,
            "temporal_arc_score": 0.65,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    flags_therapy = compute_policy_flags(unified_therapy, domain="therapy")

    # Therapy allows LAM, and v3=0.52 >= 0.45, drift=0.50 <= 0.65 → allow_deep_reflection=True
    assert flags_therapy["allow_deep_reflection"] is True


def test_v3_stability_with_formula_ui_modulation():
    """
    Test that v3 integrates correctly with Phase 5 formula UI modulation.

    For therapy/identity, formula UI modulation uses active coherence score,
    which should be v3 when v3 is enabled and available.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.45,      # v1: moderate
            "coherence_score_v2": 0.50,   # v2: moderate
            "coherence_score_v3": 0.68,   # v3: good
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.35,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.70,
            # Phase 3 metrics for formula UI
            "resonance_index": 0.75,
            "tension_index": 0.35,
            "arc_alignment_index": 0.65,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    flags = compute_policy_flags(unified, domain="therapy")

    # With v3=0.68 (>= 0.50), resonance=0.75 (>= 0.50), tension=0.35 (<= 0.75)
    # → allow_deep_reflection should be True (refined by formula UI)
    assert flags["allow_deep_reflection"] is True


# ==============================================================================
# Group D: API / Observer Tests
# ==============================================================================


def test_observer_includes_v3_in_observation():
    """
    Test that CoherenceObserver includes v3 in observation when available.
    """
    observer = CoherenceObserver()

    class MockContext:
        coherence_state = CoherenceState(convo_id="test", turn_index=0)

    ctx = MockContext()
    ctx.coherence_state.coherence_score = 0.60
    ctx.coherence_state.coherence_score_v2 = 0.70
    ctx.coherence_state.coherence_score_v3 = 0.82
    ctx.coherence_state.persona_drift_score = 0.30
    ctx.coherence_state.semantic_stability_score = 0.75
    ctx.coherence_state.temporal_arc_score = 0.70
    ctx.coherence_state.mapper_volatility_score = 0.25

    observation = observer.observe("test text", ctx)

    # Verify all three coherence scores are in observation
    assert observation.coherence_score == 0.60
    assert observation.coherence_score_v2 == 0.70
    assert observation.coherence_score_v3 == 0.82


def test_unified_output_includes_v3_in_coherence_block():
    """
    Test that unified API includes v3 in coherence block when available.
    """
    from symbolu.api.unified_api import build_unified_output

    class MockContext:
        coherence_state = CoherenceState(convo_id="test", turn_index=0)
        coherence_report = {
            "coherence_score": 0.60,
            "coherence_score_v2": 0.70,
            "coherence_score_v3": 0.82,
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.30,
            "semantic_stability_score": 0.75,
            "temporal_arc_score": 0.70,
            "mapper_volatility_score": 0.25,
            "turn_number": 0,
            "tier": "hybrid",
            "domain": "therapy",
            "active_mappers": ["HRM"],
        }

    ctx = MockContext()
    ctx.coherence_state.coherence_score = 0.60
    ctx.coherence_state.coherence_score_v2 = 0.70
    ctx.coherence_state.coherence_score_v3 = 0.82
    ctx.fusion = None
    ctx.dha = None
    ctx.mlcr = None
    ctx.mapper_profile = None

    unified = build_unified_output("test response", ctx)

    # Verify v3 is in coherence block
    coherence = unified.coherence
    assert coherence["coherence_score"] == 0.60
    assert coherence["coherence_score_v2"] == 0.70
    assert coherence["coherence_score_v3"] == 0.82


def test_unified_output_v3_from_coherence_state():
    """
    Test that unified API extracts v3 from coherence_state even if not in coherence_report.
    """
    from symbolu.api.unified_api import build_unified_output

    class MockContext:
        coherence_state = CoherenceState(convo_id="test", turn_index=0)
        coherence_report = {
            "coherence_score": 0.60,
            "persona_drift_score": 0.30,
            "semantic_stability_score": 0.75,
            "temporal_arc_score": 0.70,
            "mapper_volatility_score": 0.25,
            "turn_number": 0,
            "tier": "hybrid",
            "domain": "therapy",
            "active_mappers": ["HRM"],
        }

    ctx = MockContext()
    ctx.coherence_state.coherence_score = 0.60
    ctx.coherence_state.coherence_score_v2 = 0.70
    ctx.coherence_state.coherence_score_v3 = 0.82
    ctx.fusion = None
    ctx.dha = None
    ctx.mlcr = None
    ctx.mapper_profile = None

    unified = build_unified_output("test response", ctx)

    # Phase 11: Ensure v2 and v3 are extracted from coherence_state
    coherence = unified.coherence
    assert coherence["coherence_score_v2"] == 0.70, "v2 should be extracted from coherence_state"
    assert coherence["coherence_score_v3"] == 0.82, "v3 should be extracted from coherence_state"


def test_v3_json_serialization():
    """
    Test that v3 is correctly serialized in JSON output.
    """
    observer = CoherenceObserver()

    class MockContext:
        coherence_state = CoherenceState(convo_id="test", turn_index=0)

    ctx = MockContext()
    ctx.coherence_state.coherence_score = 0.60
    ctx.coherence_state.coherence_score_v2 = 0.70
    ctx.coherence_state.coherence_score_v3 = 0.82
    ctx.coherence_state.persona_drift_score = 0.30
    ctx.coherence_state.semantic_stability_score = 0.75
    ctx.coherence_state.temporal_arc_score = 0.70
    ctx.coherence_state.mapper_volatility_score = 0.25

    observation = observer.observe("test text", ctx)
    serialized = observer.serialize()

    # Verify JSON serialization includes all three scores
    assert "coherence_score" in serialized
    assert "coherence_score_v2" in serialized
    assert "coherence_score_v3" in serialized
    assert serialized["coherence_score_v3"] == 0.82


def test_v3_graceful_degradation_when_missing():
    """
    Test graceful degradation when v3 is not computed.

    When v3 is None, policy should fall back to v2 or v1 without errors.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.60,
            "coherence_score_v2": 0.70,
            "coherence_score_v3": None,  # v3 not available
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.25,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Therapy should fall back to v2 when v3 is None
    flags = compute_policy_flags(unified, domain="therapy")
    assert flags is not None, "Policy should not fail when v3 is None"

    # Verify it's using v2 (0.70) not v1 (0.60)
    profile = get_domain_profile("therapy")
    active_score = _get_active_coherence_score(unified, profile)
    assert active_score == 0.70, f"Should fall back to v2 (0.70) when v3 is None, got {active_score}"


# ==============================================================================
# CI Integration Smoke Tests
# ==============================================================================


def test_phase11_ci_smoke_therapy():
    """
    Smoke test for Phase 11 therapy domain integration.

    Verifies end-to-end v3 flow for therapy domain.
    """
    engine = CoherenceEngine(window=10)
    observer = CoherenceObserver()

    # Create mock temporal summary with all formulas
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

    # Update state (v1 and v2 will be auto-computed)
    state = engine.update_state(
        prev_state=None,
        convo_id="smoke_test_therapy",
        turn_index=0,
        routing_plan=MockRoutingPlan(),
        mapper_profile={"resolution_level": "medium", "arc_mode": "none"},
        temporal_summary=temporal_summary,
        semantic_signature={},
    )

    # Verify v1 and v2 are computed
    assert state.coherence_score is not None, "v1 should always be computed"
    assert state.coherence_score_v2 is not None, "v2 should be computed when formulas present"

    # For Phase 11 smoke test: Manually add v3 (simulating full pipeline with Guna/Kosha)
    # In a real pipeline, v3 would be computed when Guna/Kosha metrics are available
    state.guna_resonance_index = 0.85
    state.kosha_resonance_index = 0.82

    # Compute v3 using Phase 10 formula
    mapper_profile_with_biases = {
        "resolution_level": "medium",
        "arc_mode": "none",
        "guna_resonance_bias": 0.05,
        "kosha_resonance_bias": 0.05,
        "expression_harmonics": [0.80, 0.82, 0.85, 0.83],
    }
    state.coherence_score_v3 = engine._compute_coherence_score_v3(state, mapper_profile_with_biases)

    # Verify v3 is computed
    assert state.coherence_score_v3 is not None, "v3 should be computed when Guna/Kosha present"
    assert 0.0 <= state.coherence_score_v3 <= 1.0, "v3 must be in valid range"

    # Verify observer captures v3
    # Create mock context for observer
    class MockContext:
        pass

    mock_ctx = MockContext()
    mock_ctx.coherence_state = state

    observation = observer.observe("test", mock_ctx)
    assert observation.coherence_score_v3 is not None

    # Verify policy uses v3 for therapy
    unified = {
        "coherence": {
            "coherence_score": state.coherence_score,
            "coherence_score_v2": state.coherence_score_v2,
            "coherence_score_v3": state.coherence_score_v3,
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": state.persona_drift_score,
            "mapper_volatility_score": state.mapper_volatility_score,
            "temporal_arc_score": state.temporal_arc_score,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    flags = compute_policy_flags(unified, domain="therapy")
    profile = get_domain_profile("therapy")
    active_score = _get_active_coherence_score(unified, profile)

    assert active_score == state.coherence_score_v3, "Therapy should use v3 for policy"


def test_phase11_ci_smoke_trading_invariance():
    """
    Smoke test for Phase 11 trading domain invariance.

    Verifies that trading domain behavior is 100% unchanged.
    """
    engine = CoherenceEngine(window=10)

    temporal_summary = {
        "smi": 0.7,
        "delta_smi": 0.1,
        "bhava_gap": 0.2,
        "tension_corridor": 0.3,
        "bhava_id": 3,
        "bhava_direction": "upward",
    }

    class MockRoutingPlan:
        tier = "concrete"
        domain = "trading"
        long_arc_tension = 0.3

    state = engine.update_state(
        prev_state=None,
        convo_id="smoke_test_trading",
        turn_index=0,
        routing_plan=MockRoutingPlan(),
        mapper_profile={"resolution_level": "high", "arc_mode": "none"},
        temporal_summary=temporal_summary,
        semantic_signature={},
    )

    # v1 always computed
    assert state.coherence_score is not None

    # v2 should be None (trading doesn't enable v2 formulas by default)
    # v3 may be computed but should NOT be used for policy

    # Build unified output
    unified = {
        "coherence": {
            "coherence_score": state.coherence_score,
            "coherence_score_v2": state.coherence_score_v2,
            "coherence_score_v3": state.coherence_score_v3,
            "coherence_v3_quality": 0.75,  # Quality gate for v3
            "persona_drift_score": state.persona_drift_score,
            "mapper_volatility_score": state.mapper_volatility_score,
            "temporal_arc_score": state.temporal_arc_score,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Verify policy uses v1 only
    profile = get_domain_profile("trading")
    active_score = _get_active_coherence_score(unified, profile)

    assert active_score == state.coherence_score, "Trading must use v1 only, ignoring v2 and v3"
