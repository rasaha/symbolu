"""
Test Suite: DHA Engine Mapper Modulation
==========================================

Tests the mapper profile integration in DHA Engine.

Test Cases:
1. LCM produces shallow insight
2. HRM produces rich framing
3. LAM produces long-arc identity-level framing
"""

import pytest
from symbolu.mechanical.dha.dha_engine import DHAEngine
from symbolu.mechanical.pipeline.models import MapperProfile


@pytest.fixture
def dha_engine():
    """Create a DHA engine instance."""
    return DHAEngine()


@pytest.fixture
def base_insight():
    """Create a base insight dictionary for testing."""
    return {
        "readiness_score": 0.7,
        "resistance_score": 0.3,
        "emotional_entropy": 0.4,
        "ego_state": "open",
        "long_arc_tension": 0.5
    }


def test_lcm_shallow_insight(dha_engine, base_insight):
    """Test that LCM profile produces shallow insight."""
    # Create LCM profile
    lcm_profile = MapperProfile(
        resolution_level="low",
        arc_mode="none",
        detail_bias=0.2,
        practical_bias=0.9,
        reflective_bias=0.2
    )

    # Modulate insight
    modulated = dha_engine.modulate_dha_depth(base_insight, lcm_profile)

    # Assertions
    assert modulated is not None
    assert modulated["introspection_level"] == "minimal"
    assert modulated["metaphor_allowed"] is False
    assert modulated["reflection_depth"] == "surface"
    assert modulated["long_range_implications"] is False
    assert "practical" in modulated["framing_note"].lower()


def test_hrm_rich_framing(dha_engine, base_insight):
    """Test that HRM profile produces rich framing."""
    # Create HRM profile
    hrm_profile = MapperProfile(
        resolution_level="high",
        arc_mode="none",
        detail_bias=0.8,
        practical_bias=0.3,
        reflective_bias=0.6
    )

    # Modulate insight
    modulated = dha_engine.modulate_dha_depth(base_insight, hrm_profile)

    # Assertions
    assert modulated is not None
    assert modulated["introspection_level"] == "deep"
    assert modulated["metaphor_allowed"] is True
    assert modulated["reflection_depth"] == "detailed"
    assert modulated["contrastive_phrasing"] is True
    assert modulated["symbolic_mirrors"] == "emphasized"
    assert "high-resolution" in modulated["framing_note"].lower()


def test_lam_temporal_arc_framing(dha_engine, base_insight):
    """Test that LAM profile with temporal arc produces appropriate framing."""
    # Create LAM profile with temporal arc
    lam_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="temporal",
        detail_bias=0.5,
        practical_bias=0.3,
        reflective_bias=0.8
    )

    # Modulate insight
    modulated = dha_engine.modulate_dha_depth(base_insight, lam_profile)

    # Assertions
    assert modulated is not None
    assert modulated["introspection_level"] == "arc-aware"
    assert modulated["metaphor_allowed"] is True
    assert modulated["reflection_depth"] == "identity"
    assert modulated["emphasize_coherence"] is True

    # Check arc keywords
    arc_keywords = modulated["arc_keywords"]
    assert "trajectory" in arc_keywords
    assert "momentum" in arc_keywords
    assert "directionality" in arc_keywords
    assert "coherence" in arc_keywords

    # Check arc framing
    assert "arc_framing" in modulated
    assert "broader movement" in modulated["arc_framing"].lower() or \
           "sessions" in modulated["arc_framing"].lower()


def test_lam_identity_arc_framing(dha_engine, base_insight):
    """Test that LAM profile with identity arc produces identity framing."""
    # Create LAM profile with identity arc
    lam_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="identity",
        detail_bias=0.5,
        practical_bias=0.3,
        reflective_bias=0.8
    )

    # Modulate insight
    modulated = dha_engine.modulate_dha_depth(base_insight, lam_profile)

    # Assertions
    assert modulated is not None
    assert modulated["introspection_level"] == "arc-aware"

    # Check identity-specific framing
    assert "arc_framing" in modulated
    assert "identity" in modulated["arc_framing"].lower() or \
           "self-concept" in modulated["arc_framing"].lower()


def test_lam_deep_context_arc_framing(dha_engine, base_insight):
    """Test that LAM profile with deep_context arc produces contextual framing."""
    # Create LAM profile with deep_context arc
    lam_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="deep_context",
        detail_bias=0.5,
        practical_bias=0.3,
        reflective_bias=0.8
    )

    # Modulate insight
    modulated = dha_engine.modulate_dha_depth(base_insight, lam_profile)

    # Assertions
    assert modulated is not None
    assert "arc_framing" in modulated
    assert "deep contextual" in modulated["arc_framing"].lower() or \
           "trajectory" in modulated["arc_framing"].lower()


def test_lam_high_tension_stabilization(dha_engine):
    """Test that LAM with high tension adds stabilization framing."""
    # Create insight with high tension
    high_tension_insight = {
        "readiness_score": 0.7,
        "resistance_score": 0.3,
        "emotional_entropy": 0.4,
        "ego_state": "open",
        "long_arc_tension": 0.8  # High tension
    }

    # Create LAM profile
    lam_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="temporal",
        detail_bias=0.5,
        practical_bias=0.3,
        reflective_bias=0.8
    )

    # Modulate insight
    modulated = dha_engine.modulate_dha_depth(high_tension_insight, lam_profile)

    # Assertions
    assert modulated is not None
    assert "stabilization_framing" in modulated
    assert "integration" in modulated["stabilization_framing"].lower() or \
           "stabilization" in modulated["stabilization_framing"].lower()


def test_no_profile_returns_unchanged(dha_engine, base_insight):
    """Test that None profile returns insight unchanged."""
    modulated = dha_engine.modulate_dha_depth(base_insight, None)

    # Should be the same dict
    assert modulated is base_insight


def test_neutral_profile_returns_unchanged(dha_engine, base_insight):
    """Test that neutral profile returns insight unchanged."""
    # Create neutral profile (doesn't match any conditions)
    neutral_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5
    )

    # Modulate insight
    modulated = dha_engine.modulate_dha_depth(base_insight, neutral_profile)

    # Should be a copy with no modulation
    assert modulated == base_insight


def test_combined_hrm_lam_uses_hrm(dha_engine, base_insight):
    """Test that when both HRM and LAM conditions are met, HRM takes precedence (elif structure)."""
    # Create profile that matches both HRM and LAM
    combined_profile = MapperProfile(
        resolution_level="high",
        arc_mode="temporal",
        detail_bias=0.8,  # HRM condition
        practical_bias=0.3,
        reflective_bias=0.8  # LAM condition
    )

    # Modulate insight
    modulated = dha_engine.modulate_dha_depth(base_insight, combined_profile)

    # HRM should take precedence (elif structure - HRM is checked first)
    assert modulated["introspection_level"] == "deep"
    assert modulated["metaphor_allowed"] is True
    assert modulated["reflection_depth"] == "detailed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
