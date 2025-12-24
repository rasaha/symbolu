"""
Test Suite for Session-Level Coherence Influencers v1.0

This module contains comprehensive tests for the session policy layer,
covering all deterministic rules and integration points.

Test Groups:
    - Group A: Stability Classification (6 tests)
    - Group B: Influencer Flags (6 tests)
    - Group C: Integration Tests (6 tests)

Total: 18 tests
"""

import pytest
from datetime import datetime

from symbolu.policy.session_policy import (
    SessionPolicyFlags,
    compute_session_policy_flags,
)
from symbolu.service.sessions.session_models import SessionSummary


# ============================================================================
# GROUP A: Stability Classification Tests (6 tests)
# ============================================================================


def test_high_coherence_yields_stable():
    """Test that high coherence score (>= 0.70) yields stable classification."""
    summary = SessionSummary(
        session_id="test-001",
        total_turns=5,
        coherence_trend=0.75,  # High coherence
        persona_drift_avg=0.30,
        temporal_arc_avg=0.60,
        semantic_stability_score=0.70,
        mapper_volatility_score=0.30,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_stable is True
    assert flags.session_is_recovering is False
    assert flags.session_is_fragmented is False


def test_mid_coherence_yields_recovering():
    """Test that mid coherence score (0.45-0.69) yields recovering classification."""
    summary = SessionSummary(
        session_id="test-002",
        total_turns=5,
        coherence_trend=0.55,  # Mid coherence
        persona_drift_avg=0.40,
        temporal_arc_avg=0.50,
        semantic_stability_score=0.60,
        mapper_volatility_score=0.35,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_stable is False
    assert flags.session_is_recovering is True
    assert flags.session_is_fragmented is False


def test_low_coherence_yields_fragmented():
    """Test that low coherence score (< 0.45) yields fragmented classification."""
    summary = SessionSummary(
        session_id="test-003",
        total_turns=5,
        coherence_trend=0.35,  # Low coherence
        persona_drift_avg=0.60,
        temporal_arc_avg=0.40,
        semantic_stability_score=0.35,
        mapper_volatility_score=0.50,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_stable is False
    assert flags.session_is_recovering is False
    assert flags.session_is_fragmented is True


def test_low_semantic_stability_overrides_stable():
    """Test that low semantic stability (< 0.45) triggers grounding even if coherence is high."""
    summary = SessionSummary(
        session_id="test-004",
        total_turns=5,
        coherence_trend=0.75,  # High coherence
        persona_drift_avg=0.30,
        temporal_arc_avg=0.60,
        semantic_stability_score=0.40,  # Low semantic stability
        mapper_volatility_score=0.30,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_stable is True  # Still stable due to high coherence
    assert flags.session_needs_grounding is True  # But needs grounding due to low semantic stability


def test_high_drift_always_triggers_grounding():
    """Test that high persona drift (> 0.55) always triggers grounding."""
    summary = SessionSummary(
        session_id="test-005",
        total_turns=5,
        coherence_trend=0.70,  # Stable coherence
        persona_drift_avg=0.60,  # High drift
        temporal_arc_avg=0.60,
        semantic_stability_score=0.70,
        mapper_volatility_score=0.30,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_stable is True
    assert flags.session_needs_grounding is True  # High drift triggers grounding


def test_volatility_does_not_affect_classification():
    """Test that mapper volatility does not affect stability classification."""
    summary = SessionSummary(
        session_id="test-006",
        total_turns=5,
        coherence_trend=0.75,  # High coherence
        persona_drift_avg=0.30,
        temporal_arc_avg=0.60,
        semantic_stability_score=0.70,
        mapper_volatility_score=0.90,  # Very high volatility
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_stable is True  # Volatility doesn't affect stability classification
    assert flags.session_allow_deep_reflection is False  # But prevents deep reflection


# ============================================================================
# GROUP B: Influencer Flags Tests (6 tests)
# ============================================================================


def test_fragmented_triggers_grounding():
    """Test that fragmented classification triggers grounding."""
    summary = SessionSummary(
        session_id="test-007",
        total_turns=5,
        coherence_trend=0.30,  # Fragmented
        persona_drift_avg=0.40,
        temporal_arc_avg=0.40,
        semantic_stability_score=0.50,
        mapper_volatility_score=0.40,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_fragmented is True
    assert flags.session_needs_grounding is True


def test_stable_with_temporal_arc_allows_deep_reflection():
    """Test that stable + good temporal arc + low volatility allows deep reflection."""
    summary = SessionSummary(
        session_id="test-008",
        total_turns=5,
        coherence_trend=0.75,  # Stable
        persona_drift_avg=0.30,
        temporal_arc_avg=0.60,  # Good temporal arc
        semantic_stability_score=0.70,
        mapper_volatility_score=0.30,  # Low volatility
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_stable is True
    assert flags.session_allow_deep_reflection is True


def test_recovering_with_good_arc_yields_exploratory_style():
    """Test that recovering + good temporal arc yields exploratory style."""
    summary = SessionSummary(
        session_id="test-009",
        total_turns=5,
        coherence_trend=0.55,  # Recovering
        persona_drift_avg=0.40,
        temporal_arc_avg=0.50,  # Good enough arc
        semantic_stability_score=0.60,
        mapper_volatility_score=0.35,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_recovering is True
    assert flags.session_recommended_style == "exploratory"


def test_stable_but_high_volatility_prevents_reflection():
    """Test that high volatility prevents deep reflection even if stable."""
    summary = SessionSummary(
        session_id="test-010",
        total_turns=5,
        coherence_trend=0.75,  # Stable
        persona_drift_avg=0.30,
        temporal_arc_avg=0.60,  # Good temporal arc
        semantic_stability_score=0.70,
        mapper_volatility_score=0.50,  # High volatility
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_stable is True
    assert flags.session_allow_deep_reflection is False  # Volatility prevents reflection


def test_fragmented_with_good_arc_still_grounded():
    """Test that fragmented classification yields grounded style even with good arc."""
    summary = SessionSummary(
        session_id="test-011",
        total_turns=5,
        coherence_trend=0.35,  # Fragmented
        persona_drift_avg=0.50,
        temporal_arc_avg=0.60,  # Good temporal arc
        semantic_stability_score=0.40,
        mapper_volatility_score=0.45,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_fragmented is True
    assert flags.session_needs_grounding is True
    assert flags.session_recommended_style == "grounded"  # Grounding overrides arc


def test_neutral_style_default():
    """Test that neutral style is default when no specific conditions are met."""
    summary = SessionSummary(
        session_id="test-012",
        total_turns=5,
        coherence_trend=0.55,  # Recovering
        persona_drift_avg=0.40,
        temporal_arc_avg=0.40,  # Low temporal arc
        semantic_stability_score=0.60,
        mapper_volatility_score=0.35,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_recovering is True
    assert flags.session_recommended_style == "neutral"


# ============================================================================
# GROUP C: Integration Tests (6 tests)
# ============================================================================


def test_none_session_summary_returns_none():
    """Test that None session summary returns None flags (sessionless request)."""
    flags = compute_session_policy_flags(None)
    assert flags is None


def test_policy_flags_serialization():
    """Test that SessionPolicyFlags can be serialized to dict."""
    summary = SessionSummary(
        session_id="test-013",
        total_turns=5,
        coherence_trend=0.75,
        persona_drift_avg=0.30,
        temporal_arc_avg=0.60,
        semantic_stability_score=0.70,
        mapper_volatility_score=0.30,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)
    assert flags is not None

    # Test serialization
    flags_dict = flags.to_dict()

    assert isinstance(flags_dict, dict)
    assert "session_needs_grounding" in flags_dict
    assert "session_allow_deep_reflection" in flags_dict
    assert "session_is_stable" in flags_dict
    assert "session_is_recovering" in flags_dict
    assert "session_is_fragmented" in flags_dict
    assert "session_recommended_style" in flags_dict

    # Verify values
    assert flags_dict["session_is_stable"] is True
    assert flags_dict["session_allow_deep_reflection"] is True
    assert flags_dict["session_recommended_style"] == "reflective"


def test_deterministic_output_same_input():
    """Test that same input produces same output (deterministic)."""
    summary = SessionSummary(
        session_id="test-014",
        total_turns=5,
        coherence_trend=0.65,
        persona_drift_avg=0.35,
        temporal_arc_avg=0.55,
        semantic_stability_score=0.65,
        mapper_volatility_score=0.35,
        created_at=datetime.utcnow(),
    )

    # Run computation twice
    flags1 = compute_session_policy_flags(summary)
    flags2 = compute_session_policy_flags(summary)

    # Verify identical output
    assert flags1 is not None
    assert flags2 is not None
    assert flags1.session_is_stable == flags2.session_is_stable
    assert flags1.session_needs_grounding == flags2.session_needs_grounding
    assert flags1.session_allow_deep_reflection == flags2.session_allow_deep_reflection
    assert flags1.session_recommended_style == flags2.session_recommended_style


def test_boundary_conditions_coherence_070():
    """Test boundary condition: coherence_score exactly 0.70 should be stable."""
    summary = SessionSummary(
        session_id="test-015",
        total_turns=5,
        coherence_trend=0.70,  # Exact boundary
        persona_drift_avg=0.30,
        temporal_arc_avg=0.60,
        semantic_stability_score=0.70,
        mapper_volatility_score=0.30,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_stable is True
    assert flags.session_is_recovering is False


def test_boundary_conditions_coherence_045():
    """Test boundary condition: coherence_score exactly 0.45 should be recovering."""
    summary = SessionSummary(
        session_id="test-016",
        total_turns=5,
        coherence_trend=0.45,  # Exact boundary
        persona_drift_avg=0.40,
        temporal_arc_avg=0.50,
        semantic_stability_score=0.60,
        mapper_volatility_score=0.35,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_stable is False
    assert flags.session_is_recovering is True
    assert flags.session_is_fragmented is False


def test_all_style_modes_coverage():
    """Test coverage of all 4 style modes: grounded, reflective, exploratory, neutral."""
    # Test 1: Grounded style
    summary_grounded = SessionSummary(
        session_id="test-017a",
        total_turns=5,
        coherence_trend=0.30,  # Fragmented
        persona_drift_avg=0.60,
        temporal_arc_avg=0.40,
        semantic_stability_score=0.35,
        mapper_volatility_score=0.50,
        created_at=datetime.utcnow(),
    )
    flags_grounded = compute_session_policy_flags(summary_grounded)
    assert flags_grounded.session_recommended_style == "grounded"

    # Test 2: Reflective style
    summary_reflective = SessionSummary(
        session_id="test-017b",
        total_turns=5,
        coherence_trend=0.75,  # Stable
        persona_drift_avg=0.30,
        temporal_arc_avg=0.60,  # Good arc
        semantic_stability_score=0.70,
        mapper_volatility_score=0.30,  # Low volatility
        created_at=datetime.utcnow(),
    )
    flags_reflective = compute_session_policy_flags(summary_reflective)
    assert flags_reflective.session_recommended_style == "reflective"

    # Test 3: Exploratory style
    summary_exploratory = SessionSummary(
        session_id="test-017c",
        total_turns=5,
        coherence_trend=0.55,  # Recovering
        persona_drift_avg=0.40,
        temporal_arc_avg=0.50,  # Good enough arc
        semantic_stability_score=0.60,
        mapper_volatility_score=0.35,
        created_at=datetime.utcnow(),
    )
    flags_exploratory = compute_session_policy_flags(summary_exploratory)
    assert flags_exploratory.session_recommended_style == "exploratory"

    # Test 4: Neutral style
    summary_neutral = SessionSummary(
        session_id="test-017d",
        total_turns=5,
        coherence_trend=0.55,  # Recovering
        persona_drift_avg=0.40,
        temporal_arc_avg=0.40,  # Low arc
        semantic_stability_score=0.60,
        mapper_volatility_score=0.35,
        created_at=datetime.utcnow(),
    )
    flags_neutral = compute_session_policy_flags(summary_neutral)
    assert flags_neutral.session_recommended_style == "neutral"


# ============================================================================
# Additional Edge Case Tests
# ============================================================================


def test_extreme_values_all_zeros():
    """Test behavior with all zero values."""
    summary = SessionSummary(
        session_id="test-018",
        total_turns=5,
        coherence_trend=0.0,
        persona_drift_avg=0.0,
        temporal_arc_avg=0.0,
        semantic_stability_score=0.0,
        mapper_volatility_score=0.0,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_fragmented is True  # Zero coherence is fragmented
    assert flags.session_needs_grounding is True  # Zero semantic stability triggers grounding
    assert flags.session_recommended_style == "grounded"


def test_extreme_values_all_ones():
    """Test behavior with all maximum values."""
    summary = SessionSummary(
        session_id="test-019",
        total_turns=5,
        coherence_trend=1.0,
        persona_drift_avg=1.0,
        temporal_arc_avg=1.0,
        semantic_stability_score=1.0,
        mapper_volatility_score=1.0,
        created_at=datetime.utcnow(),
    )

    flags = compute_session_policy_flags(summary)

    assert flags is not None
    assert flags.session_is_stable is True  # High coherence
    assert flags.session_needs_grounding is True  # High drift triggers grounding
    assert flags.session_allow_deep_reflection is False  # High volatility prevents reflection


# ============================================================================
# Test Summary
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
