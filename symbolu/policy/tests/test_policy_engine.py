"""
Test Suite for Symbol-U Policy Engine v1.0

Comprehensive tests covering:
- Domain profile selection
- Policy flag computation rules
- Stability status transitions
- Mapper recommendations
- Deterministic behavior
- Edge cases and error handling

Design:
- Zero-LLM: All tests use deterministic assertions
- CI-safe: Fast, isolated, no external dependencies
- Comprehensive: 14+ test cases covering all rules
"""

import pytest
from typing import Dict, Any

from symbolu.policy.domain_profiles import (
    get_domain_profile,
    get_all_domain_names,
    is_domain_supported,
)
from symbolu.policy.policy_engine import (
    compute_policy_flags,
    explain_policy_flags,
)


# ============================================================================
# DOMAIN PROFILE TESTS
# ============================================================================


def test_trading_profile():
    """Test trading domain profile has correct configuration."""
    profile = get_domain_profile("trading")

    assert profile["min_coherence"] == 0.55
    assert profile["max_persona_drift"] == 0.40
    assert profile["max_mapper_volatility"] == 0.45
    assert profile["prefer_mappers"] == ["LCM", "HRM"]
    assert profile["allow_lam"] is False
    assert profile["style"] == "precise"


def test_therapy_profile():
    """Test therapy domain profile has correct configuration."""
    profile = get_domain_profile("therapy")

    assert profile["min_coherence"] == 0.45
    assert profile["max_persona_drift"] == 0.60
    assert profile["max_mapper_volatility"] == 0.60
    assert profile["prefer_mappers"] == ["HRM", "LAM"]
    assert profile["allow_lam"] is True
    assert profile["style"] == "reflective"


def test_identity_profile():
    """Test identity domain profile has correct configuration."""
    profile = get_domain_profile("identity")

    assert profile["min_coherence"] == 0.50
    assert profile["max_persona_drift"] == 0.50
    assert profile["max_mapper_volatility"] == 0.55
    assert profile["prefer_mappers"] == ["LAM", "HRM"]
    assert profile["allow_lam"] is True
    assert profile["style"] == "exploratory"


def test_generic_fallback():
    """Test unknown domains fall back to generic profile."""
    profile = get_domain_profile("unknown_domain_xyz")

    assert profile["min_coherence"] == 0.40
    assert profile["max_persona_drift"] == 0.55
    assert profile["max_mapper_volatility"] == 0.55
    assert profile["prefer_mappers"] == ["HRM"]
    assert profile["allow_lam"] is False
    assert profile["style"] == "neutral"


def test_domain_profile_case_insensitive():
    """Test domain profile lookup is case-insensitive."""
    profile_lower = get_domain_profile("trading")
    profile_upper = get_domain_profile("TRADING")
    profile_mixed = get_domain_profile("TrAdInG")

    assert profile_lower == profile_upper == profile_mixed


def test_get_all_domain_names():
    """Test retrieval of all supported domain names."""
    domains = get_all_domain_names()

    assert "trading" in domains
    assert "therapy" in domains
    assert "identity" in domains
    assert "generic" not in domains  # Generic is fallback, not a "supported" domain


def test_is_domain_supported():
    """Test domain support checking."""
    assert is_domain_supported("trading") is True
    assert is_domain_supported("therapy") is True
    assert is_domain_supported("identity") is True
    assert is_domain_supported("unknown") is False
    assert is_domain_supported("generic") is False


# ============================================================================
# POLICY FLAG COMPUTATION TESTS - NEEDS_GROUNDING
# ============================================================================


def test_trading_low_coherence_needs_grounding():
    """Test trading domain: low coherence triggers needs_grounding."""
    unified = {
        "coherence": {
            "coherence_score": 0.46,  # Below trading min (0.55)
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.40},
    }

    flags = compute_policy_flags(unified, "trading")

    assert flags["needs_grounding"] is True
    assert flags["coherence_warning"] is False  # Not below 0.45 (0.55 - 0.1)
    assert flags["recommended_mapper"] == "LCM"  # Override due to needs_grounding


def test_trading_high_drift_needs_grounding():
    """Test trading domain: high persona drift triggers needs_grounding."""
    unified = {
        "coherence": {
            "coherence_score": 0.70,  # Good coherence
            "persona_drift_score": 0.50,  # Above trading max (0.40)
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.40},
    }

    flags = compute_policy_flags(unified, "trading")

    assert flags["needs_grounding"] is True
    assert flags["recommended_mapper"] == "LCM"


def test_trading_high_volatility_needs_grounding():
    """Test trading domain: high mapper volatility triggers needs_grounding."""
    unified = {
        "coherence": {
            "coherence_score": 0.70,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.50,  # Above trading max (0.45)
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.40},
    }

    flags = compute_policy_flags(unified, "trading")

    assert flags["needs_grounding"] is True
    assert flags["recommended_mapper"] == "LCM"


# ============================================================================
# POLICY FLAG COMPUTATION TESTS - DEEP REFLECTION
# ============================================================================


def test_therapy_allows_deep_reflection():
    """Test therapy domain: allows deep reflection when LAM + coherent."""
    unified = {
        "coherence": {
            "coherence_score": 0.60,  # Above therapy min (0.45)
            "persona_drift_score": 0.50,  # Below 0.65
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.50},
    }

    flags = compute_policy_flags(unified, "therapy")

    assert flags["allow_deep_reflection"] is True  # LAM allowed + coherent + drift OK
    assert flags["needs_grounding"] is False


def test_trading_disallows_deep_reflection():
    """Test trading domain: disallows deep reflection (LAM not allowed)."""
    unified = {
        "coherence": {
            "coherence_score": 0.70,  # Good coherence
            "persona_drift_score": 0.30,  # Low drift
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.40},
    }

    flags = compute_policy_flags(unified, "trading")

    assert flags["allow_deep_reflection"] is False  # LAM not allowed in trading


def test_therapy_disallows_deep_reflection_when_high_drift():
    """Test therapy domain: disallows deep reflection when drift > 0.65."""
    unified = {
        "coherence": {
            "coherence_score": 0.60,
            "persona_drift_score": 0.70,  # Above 0.65 threshold
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.50},
    }

    flags = compute_policy_flags(unified, "therapy")

    assert flags["allow_deep_reflection"] is False  # Drift too high


# ============================================================================
# POLICY FLAG COMPUTATION TESTS - PREFER_CONCRETE & PREFER_ARC_MODE
# ============================================================================


def test_prefer_concrete_when_entropy_low():
    """Test prefer_concrete when LCM preferred + entropy low."""
    unified = {
        "coherence": {
            "coherence_score": 0.60,  # Below 0.65
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.50},  # Below 0.60
    }

    flags = compute_policy_flags(unified, "trading")  # LCM in prefer_mappers

    assert flags["prefer_concrete"] is True


def test_identity_prefer_arc_mode():
    """Test identity domain: prefer_arc_mode when LAM allowed + stable."""
    unified = {
        "coherence": {
            "coherence_score": 0.65,  # Above identity min (0.50)
            "persona_drift_score": 0.40,  # Below 0.55
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.75,
        },
        "entropy": {"normalized_entropy": 0.50},
    }

    flags = compute_policy_flags(unified, "identity")  # LAM in prefer_mappers

    assert flags["prefer_arc_mode"] is True
    assert flags["recommended_mapper"] == "LAM"  # Override due to prefer_arc_mode


def test_prefer_arc_mode_blocked_when_high_drift():
    """Test prefer_arc_mode blocked when drift >= 0.55."""
    unified = {
        "coherence": {
            "coherence_score": 0.65,
            "persona_drift_score": 0.60,  # Above 0.55
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.75,
        },
        "entropy": {"normalized_entropy": 0.50},
    }

    flags = compute_policy_flags(unified, "identity")

    assert flags["prefer_arc_mode"] is False


# ============================================================================
# POLICY FLAG COMPUTATION TESTS - COHERENCE_WARNING
# ============================================================================


def test_coherence_warning_triggered():
    """Test coherence_warning when score < (min_coherence - 0.1)."""
    unified = {
        "coherence": {
            "coherence_score": 0.35,  # Below trading min (0.55) - 0.1 = 0.45
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.50,
        },
        "entropy": {"normalized_entropy": 0.60},
    }

    flags = compute_policy_flags(unified, "trading")

    assert flags["coherence_warning"] is True
    assert flags["needs_grounding"] is True


def test_coherence_warning_not_triggered():
    """Test coherence_warning not triggered when score >= (min - 0.1)."""
    unified = {
        "coherence": {
            "coherence_score": 0.48,  # Above 0.45 (0.55 - 0.1)
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.40},
    }

    flags = compute_policy_flags(unified, "trading")

    assert flags["coherence_warning"] is False
    assert flags["needs_grounding"] is True  # Still needs grounding (below 0.55)


# ============================================================================
# POLICY FLAG COMPUTATION TESTS - STABILITY_STATUS
# ============================================================================


def test_stability_status_stable():
    """Test stability_status = stable when coherence >= 0.65 and drift <= 0.40."""
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.35,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40},
    }

    flags = compute_policy_flags(unified, "trading")

    assert flags["stability_status"] == "stable"


def test_stability_status_recovering():
    """Test stability_status = recovering when arc >= 0.60 and drift <= 0.55."""
    unified = {
        "coherence": {
            "coherence_score": 0.55,  # Not high enough for stable
            "persona_drift_score": 0.50,
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.70,  # Good arc
        },
        "entropy": {"normalized_entropy": 0.50},
    }

    flags = compute_policy_flags(unified, "trading")

    assert flags["stability_status"] == "recovering"


def test_stability_status_fragmented():
    """Test stability_status = fragmented when neither stable nor recovering."""
    unified = {
        "coherence": {
            "coherence_score": 0.45,  # Low coherence
            "persona_drift_score": 0.60,  # High drift
            "mapper_volatility_score": 0.50,
            "temporal_arc_score": 0.50,  # Low arc
        },
        "entropy": {"normalized_entropy": 0.70},
    }

    flags = compute_policy_flags(unified, "therapy")

    assert flags["stability_status"] == "fragmented"


# ============================================================================
# POLICY FLAG COMPUTATION TESTS - RECOMMENDED_MAPPER
# ============================================================================


def test_recommended_mapper_override_lcm_when_grounding():
    """Test recommended_mapper = LCM when needs_grounding = True."""
    unified = {
        "coherence": {
            "coherence_score": 0.35,  # Low - needs grounding
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.60,
        },
        "entropy": {"normalized_entropy": 0.40},
    }

    flags = compute_policy_flags(unified, "therapy")  # therapy prefers HRM/LAM

    assert flags["needs_grounding"] is True
    assert flags["recommended_mapper"] == "LCM"  # Override


def test_recommended_mapper_override_lam_when_arc_mode():
    """Test recommended_mapper = LAM when prefer_arc_mode = True."""
    unified = {
        "coherence": {
            "coherence_score": 0.70,
            "persona_drift_score": 0.40,
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.50},
    }

    flags = compute_policy_flags(unified, "identity")  # LAM in prefer_mappers

    assert flags["prefer_arc_mode"] is True
    assert flags["recommended_mapper"] == "LAM"


def test_recommended_mapper_from_profile():
    """Test recommended_mapper uses profile preference when no overrides."""
    unified = {
        "coherence": {
            "coherence_score": 0.70,  # Good - no grounding needed
            "persona_drift_score": 0.30,  # Low - no arc mode issue
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.40},
    }

    flags = compute_policy_flags(unified, "trading")  # prefer_mappers = [LCM, HRM]

    assert flags["needs_grounding"] is False
    assert flags["prefer_arc_mode"] is False
    assert flags["recommended_mapper"] == "LCM"  # First in profile


def test_recommended_mapper_fallback_hrm():
    """Test recommended_mapper falls back to HRM when profile empty."""
    unified = {
        "coherence": {
            "coherence_score": 0.70,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.40},
    }

    # Simulate empty prefer_mappers (modify generic profile temporarily)
    from symbolu.policy.domain_profiles import DOMAIN_PROFILES
    original = DOMAIN_PROFILES["generic"]["prefer_mappers"]
    DOMAIN_PROFILES["generic"]["prefer_mappers"] = []

    try:
        flags = compute_policy_flags(unified, "unknown_domain")
        assert flags["recommended_mapper"] == "HRM"  # Fallback
    finally:
        # Restore original
        DOMAIN_PROFILES["generic"]["prefer_mappers"] = original


# ============================================================================
# POLICY FLAG COMPUTATION TESTS - RECOMMENDED_STYLE
# ============================================================================


def test_recommended_style_from_profile():
    """Test recommended_style comes from domain profile."""
    unified = {
        "coherence": {
            "coherence_score": 0.60,
            "persona_drift_score": 0.40,
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.50},
    }

    flags_trading = compute_policy_flags(unified, "trading")
    flags_therapy = compute_policy_flags(unified, "therapy")
    flags_identity = compute_policy_flags(unified, "identity")

    assert flags_trading["recommended_style"] == "precise"
    assert flags_therapy["recommended_style"] == "reflective"
    assert flags_identity["recommended_style"] == "exploratory"


# ============================================================================
# DETERMINISTIC BEHAVIOR TEST
# ============================================================================


def test_deterministic_behavior():
    """Test compute_policy_flags produces identical output for identical input."""
    unified = {
        "coherence": {
            "coherence_score": 0.55,
            "persona_drift_score": 0.45,
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.65,
        },
        "entropy": {"normalized_entropy": 0.55},
    }

    # Run 5 times with same input
    results = [compute_policy_flags(unified, "trading") for _ in range(5)]

    # All results should be identical
    first = results[0]
    for result in results[1:]:
        assert result == first, "Non-deterministic behavior detected!"


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================


def test_missing_coherence_data_uses_safe_defaults():
    """Test policy engine handles missing coherence data gracefully."""
    unified = {}  # Empty unified output

    # Should not crash, should use safe defaults
    flags = compute_policy_flags(unified, "trading")

    # With defaults (coherence=1.0, drift=0.0), trading should be OK
    assert flags["needs_grounding"] is False
    assert flags["stability_status"] == "stable"


def test_invalid_unified_raises_error():
    """Test invalid unified input raises ValueError."""
    with pytest.raises(ValueError, match="unified output must be a non-empty dictionary"):
        compute_policy_flags(None, "trading")

    with pytest.raises(ValueError, match="unified output must be a non-empty dictionary"):
        compute_policy_flags("not a dict", "trading")


def test_explain_policy_flags():
    """Test explain_policy_flags generates human-readable summary."""
    flags = {
        "needs_grounding": True,
        "allow_deep_reflection": False,
        "prefer_concrete": True,
        "prefer_arc_mode": False,
        "coherence_warning": True,
        "stability_status": "fragmented",
        "recommended_style": "precise",
        "recommended_mapper": "LCM",
    }

    explanation = explain_policy_flags(flags)

    assert "FRAGMENTED" in explanation
    assert "COHERENCE WARNING" in explanation
    assert "GROUNDING NEEDED" in explanation
    assert "precise" in explanation
    assert "LCM" in explanation


# ============================================================================
# INTEGRATION TEST
# ============================================================================


def test_full_policy_workflow():
    """Integration test: full policy workflow from unified output to flags."""
    # Simulate realistic unified output from USU-API
    unified = {
        "text": "User response text",
        "coherence": {
            "coherence_score": 0.48,
            "persona_drift_score": 0.52,
            "semantic_stability_score": 0.60,
            "temporal_arc_score": 0.68,
            "mapper_volatility_score": 0.38,
            "turn_number": 5,
            "tier": "HYBRID",
            "domain": "therapy",
            "active_mappers": ["HRM"],
        },
        "entropy": {
            "H_D": 0.45,
            "H_G": 0.50,
            "H_K": 0.48,
            "normalized_entropy": 0.48,
        },
        "metadata": {
            "timestamp": "2025-12-09T10:30:00Z",
            "turn_index": 5,
            "domain": "therapy",
            "api_version": "USU-API-v1.0",
        },
    }

    # Compute policy flags
    flags = compute_policy_flags(unified, domain="therapy")

    # Therapy profile: min_coherence=0.45, max_drift=0.60
    # coherence_score=0.48 >= 0.45 (OK)
    # drift=0.52 <= 0.60 (OK)
    # volatility=0.38 <= 0.60 (OK)
    assert flags["needs_grounding"] is False

    # allow_lam=True, coherence OK, drift <= 0.65
    assert flags["allow_deep_reflection"] is True

    # arc_score=0.68 >= 0.60, drift=0.52 <= 0.55
    assert flags["stability_status"] == "recovering"

    # coherence=0.48 >= (0.45 - 0.1) = 0.35
    assert flags["coherence_warning"] is False

    assert flags["recommended_style"] == "reflective"

    # Verify explanation works
    explanation = explain_policy_flags(flags)
    assert "recovering" in explanation.lower()


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
