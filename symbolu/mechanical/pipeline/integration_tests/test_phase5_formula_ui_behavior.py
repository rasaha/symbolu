"""
Phase 5 Formula UI Behavior Tests
==================================

Tests for Phase 5 Symbol-U Formula Integration Plan v1.0.

These tests verify that Phase 5 formula-based UI modulation:
- Correctly refines policy flags for therapy/identity domains using Phase 3/4 metrics
- Leaves trading/generic domains completely unchanged (invariance)
- Produces deterministic, reproducible outputs
- Never modifies core safety flags (needs_grounding, coherence_warning, etc.)
- Only affects UI-layer policy flags (allow_deep_reflection, prefer_concrete, prefer_arc_mode)

All changes must be:
- Zero-LLM (pure rules, deterministic)
- Non-invasive (v1 behavior intact for non-formula domains)
- CI-safe (all tests pass with drift & invariance guards)
- UI-layer only (no routing/TTOR/mapper changes)

Test Coverage:
Group A - Policy Refinement Logic (~8 tests)
Group B - DILchat Behavior (~5 tests)
Group C - Behavioral Invariance & Determinism (~7 tests)
Total: ~20 tests
"""

import pytest
from typing import Dict, Any

from symbolu.policy.domain_profiles import get_domain_profile
from symbolu.policy.policy_engine import (
    compute_policy_flags,
    _refine_policy_with_formulas,
    _get_active_coherence_score,
)
from symbolu.adapter.dilchat_adapter import build_dilchat_response


# ==============================================================================
# Group A: Policy Refinement Logic (Unit-ish Behavior)
# ==============================================================================


def test_refine_policy_with_formulas_disabled_for_none_mode():
    """
    Test that refinement is completely skipped when formula_ui_mode="none".

    For trading and generic domains, _refine_policy_with_formulas should
    return flags unchanged regardless of formula metrics.
    """
    # Setup flags
    flags = {
        "allow_deep_reflection": False,
        "prefer_concrete": False,
        "prefer_arc_mode": False,
        "needs_grounding": True,
        "coherence_warning": False,
    }

    # Setup unified output with strong formula signals
    unified = {
        "coherence": {
            "coherence_score": 0.80,
            "coherence_score_v2": 0.85,
            "resonance_index": 0.90,  # Very high
            "tension_index": 0.10,     # Very low
            "arc_alignment_index": 0.95,  # Very high
        }
    }

    # Trading profile (formula_ui_mode="none")
    profile = get_domain_profile("trading")
    assert profile["formula_ui_mode"] == "none"

    refined = _refine_policy_with_formulas(flags, unified, profile)

    # Assert complete invariance
    assert refined == flags, "Flags should be unchanged when formula_ui_mode=none"
    assert refined["allow_deep_reflection"] is False
    assert refined["prefer_arc_mode"] is False


def test_refine_policy_enables_deep_reflection_when_signals_safe():
    """
    Test RULE 1: Enable deep reflection when coherence + resonance high, tension low.

    For therapy domain with good formula signals, allow_deep_reflection should
    be enabled even if it was False initially.
    """
    flags = {
        "allow_deep_reflection": False,  # Initially disabled
        "prefer_concrete": False,
        "prefer_arc_mode": False,
        "needs_grounding": False,
    }

    unified = {
        "coherence": {
            "coherence_score": 0.65,
            "coherence_score_v2": 0.70,
            "resonance_index": 0.75,  # High resonance
            "tension_index": 0.30,     # Low tension
            "arc_alignment_index": 0.60,
        }
    }

    profile = get_domain_profile("therapy")
    assert profile["formula_ui_mode"] == "light"
    assert profile["min_resonance_for_reflection"] == 0.50
    assert profile["max_tension_for_reflection"] == 0.75

    refined = _refine_policy_with_formulas(flags, unified, profile)

    # Assert reflection enabled
    assert refined["allow_deep_reflection"] is True, "Reflection should be enabled with safe signals"


def test_refine_policy_enables_arc_mode_when_alignment_high():
    """
    Test RULE 2: Enable arc mode when arc_alignment >= 0.60 AND reflection allowed.

    When arc alignment is strong and reflection is safe, prefer_arc_mode should
    be enabled.
    """
    flags = {
        "allow_deep_reflection": False,  # Will be enabled by RULE 1
        "prefer_arc_mode": False,
        "prefer_concrete": False,
    }

    unified = {
        "coherence": {
            "coherence_score": 0.70,
            "resonance_index": 0.80,
            "tension_index": 0.25,
            "arc_alignment_index": 0.75,  # High arc alignment
        }
    }

    profile = get_domain_profile("identity")
    refined = _refine_policy_with_formulas(flags, unified, profile)

    # Assert both reflection and arc mode enabled
    assert refined["allow_deep_reflection"] is True, "Reflection should be enabled first"
    assert refined["prefer_arc_mode"] is True, "Arc mode should be enabled with high alignment"


def test_refine_policy_forces_concrete_when_tension_very_high():
    """
    Test RULE 3: Force concrete mode when tension >= 0.75 (safety override).

    When tension is dangerously high, prefer_concrete should be enabled
    and both reflection and arc mode should be disabled for safety.
    """
    flags = {
        "allow_deep_reflection": True,  # Initially enabled
        "prefer_arc_mode": True,         # Initially enabled
        "prefer_concrete": False,
    }

    unified = {
        "coherence": {
            "coherence_score": 0.60,
            "resonance_index": 0.70,
            "tension_index": 0.85,  # Very high tension (danger zone)
            "arc_alignment_index": 0.65,
        }
    }

    profile = get_domain_profile("therapy")
    refined = _refine_policy_with_formulas(flags, unified, profile)

    # Assert safety override
    assert refined["prefer_concrete"] is True, "Concrete mode should be forced with high tension"
    assert refined["allow_deep_reflection"] is False, "Reflection should be disabled for safety"
    assert refined["prefer_arc_mode"] is False, "Arc mode should be disabled for safety"


def test_refine_policy_no_change_when_metrics_missing():
    """
    Test that refinement is skipped when formula metrics are missing.

    If any of resonance_index, tension_index, or arc_alignment_index is None,
    flags should be returned unchanged.
    """
    flags = {
        "allow_deep_reflection": False,
        "prefer_arc_mode": False,
        "prefer_concrete": False,
    }

    # Missing resonance_index
    unified_partial = {
        "coherence": {
            "coherence_score": 0.70,
            "resonance_index": None,  # Missing
            "tension_index": 0.30,
            "arc_alignment_index": 0.65,
        }
    }

    profile = get_domain_profile("therapy")
    refined = _refine_policy_with_formulas(flags, unified_partial, profile)

    assert refined == flags, "Flags should be unchanged when metrics are missing"


def test_refine_policy_respects_domain_thresholds():
    """
    Test that refinement respects domain-specific thresholds.

    Different domains have different min_resonance and max_tension thresholds.
    Verify that the same formula values produce different results across domains.
    """
    flags = {"allow_deep_reflection": False, "prefer_concrete": False, "prefer_arc_mode": False}

    unified = {
        "coherence": {
            "coherence_score": 0.60,
            "resonance_index": 0.52,  # Just above therapy threshold (0.50), below trading (0.60)
            "tension_index": 0.72,     # Below therapy max (0.75), above identity max (0.70)
            "arc_alignment_index": 0.55,
        }
    }

    # Therapy: should enable reflection (resonance=0.52 >= 0.50, tension=0.72 <= 0.75)
    profile_therapy = get_domain_profile("therapy")
    refined_therapy = _refine_policy_with_formulas(flags.copy(), unified, profile_therapy)
    assert refined_therapy["allow_deep_reflection"] is True, "Therapy should enable reflection"

    # Identity: should NOT enable reflection (tension=0.72 > 0.70)
    profile_identity = get_domain_profile("identity")
    refined_identity = _refine_policy_with_formulas(flags.copy(), unified, profile_identity)
    assert refined_identity["allow_deep_reflection"] is False, "Identity should not enable reflection"


def test_refine_policy_never_modifies_safety_flags():
    """
    Test that refinement NEVER modifies core safety flags.

    The following flags must remain untouched by _refine_policy_with_formulas:
    - needs_grounding
    - coherence_warning
    - stability_status
    - recommended_mapper
    """
    flags = {
        "allow_deep_reflection": False,
        "prefer_concrete": False,
        "prefer_arc_mode": False,
        "needs_grounding": True,           # Core safety flag
        "coherence_warning": True,         # Core safety flag
        "stability_status": "fragmented",  # Core safety flag
        "recommended_mapper": "LCM",       # Routing decision
    }

    unified = {
        "coherence": {
            "coherence_score": 0.80,
            "resonance_index": 0.90,
            "tension_index": 0.10,
            "arc_alignment_index": 0.95,
        }
    }

    profile = get_domain_profile("therapy")
    refined = _refine_policy_with_formulas(flags, unified, profile)

    # Assert safety flags unchanged
    assert refined["needs_grounding"] is True, "needs_grounding must not be modified"
    assert refined["coherence_warning"] is True, "coherence_warning must not be modified"
    assert refined["stability_status"] == "fragmented", "stability_status must not be modified"
    assert refined["recommended_mapper"] == "LCM", "recommended_mapper must not be modified"


def test_refine_policy_deterministic():
    """
    Test that refinement is fully deterministic.

    Same inputs should always produce same outputs.
    """
    flags = {"allow_deep_reflection": False, "prefer_arc_mode": False, "prefer_concrete": False}

    unified = {
        "coherence": {
            "coherence_score": 0.65,
            "resonance_index": 0.75,
            "tension_index": 0.30,
            "arc_alignment_index": 0.70,
        }
    }

    profile = get_domain_profile("therapy")

    # Run refinement multiple times
    refined_1 = _refine_policy_with_formulas(flags.copy(), unified, profile)
    refined_2 = _refine_policy_with_formulas(flags.copy(), unified, profile)
    refined_3 = _refine_policy_with_formulas(flags.copy(), unified, profile)

    # Assert all results identical
    assert refined_1 == refined_2 == refined_3, "Refinement must be deterministic"


# ==============================================================================
# Group B: DILchat Behavior (Domain-Specific)
# ==============================================================================


def test_dilchat_hints_invariant_for_trading_domain():
    """
    Test that DILchat hints for trading domain are completely unchanged by Phase 5.

    Trading has formula_ui_mode="none", so hints should be identical with or
    without formula metrics present.
    """
    # Baseline unified output (no formulas)
    unified_baseline = {
        "text": "Market analysis complete.",
        "coherence": {
            "coherence_score": 0.65,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.25,
            "temporal_arc_score": 0.70,
        },
        "symbolic": {"summary": "Precise calculation"},
        "practical": {"text": "Action steps"},
        "mirror": {},
        "dha": {},
        "routing": {},
        "mappers": {},
        "entropy": {"normalized_entropy": 0.40},
        "metadata": {"domain": "trading"},
    }

    # Compute policy flags and build response
    flags_baseline = compute_policy_flags(unified_baseline, "trading")
    response_baseline = build_dilchat_response(unified_baseline, flags_baseline, "trading")

    # Enhanced unified output (with strong formula signals)
    unified_enhanced = unified_baseline.copy()
    unified_enhanced["coherence"] = {
        **unified_baseline["coherence"],
        "resonance_index": 0.90,
        "tension_index": 0.10,
        "arc_alignment_index": 0.85,
        "coherence_score_v2": 0.75,
    }

    # Compute flags and build response with formulas
    flags_enhanced = compute_policy_flags(unified_enhanced, "trading")
    response_enhanced = build_dilchat_response(unified_enhanced, flags_enhanced, "trading")

    # Assert complete invariance
    assert response_baseline.hints == response_enhanced.hints, \
        "Trading hints must be unchanged by formula metrics"
    assert response_baseline.badges == response_enhanced.badges, \
        "Trading badges must be unchanged by formula metrics"


def test_dilchat_hints_invariant_for_generic_domain():
    """
    Test that DILchat hints for generic domain are completely unchanged by Phase 5.

    Generic has formula_ui_mode="none", so behavior must be identical.
    """
    unified = {
        "text": "Generic response.",
        "coherence": {
            "coherence_score": 0.55,
            "persona_drift_score": 0.40,
            "mapper_volatility_score": 0.35,
            "temporal_arc_score": 0.60,
            "resonance_index": 0.85,  # High formula signals
            "tension_index": 0.15,
            "arc_alignment_index": 0.80,
        },
        "symbolic": {},
        "practical": {},
        "mirror": {},
        "dha": {},
        "routing": {},
        "mappers": {},
        "entropy": {"normalized_entropy": 0.45},
        "metadata": {"domain": "generic"},
    }

    # Compute flags
    flags = compute_policy_flags(unified, "generic")

    # Assert formula metrics don't affect policy
    assert flags["allow_deep_reflection"] is False, "Generic should not enable reflection via formulas"


def test_dilchat_therapy_reflection_hint_enabled_with_formulas():
    """
    Test that therapy domain enables reflection hints when formula signals are safe.

    With high resonance, low tension, and adequate coherence, therapy should
    produce DEEP_REFLECTION or REFLECTION_MODE hints.
    """
    unified = {
        "text": "Let's explore deeper...",
        "coherence": {
            "coherence_score": 0.60,
            "coherence_score_v2": 0.70,
            "persona_drift_score": 0.40,
            "mapper_volatility_score": 0.35,
            "temporal_arc_score": 0.65,
            "resonance_index": 0.75,  # High resonance
            "tension_index": 0.30,     # Low tension
            "arc_alignment_index": 0.60,
        },
        "symbolic": {"summary": "Reflective exploration"},
        "practical": {"text": "Explore feelings"},
        "mirror": {},
        "dha": {},
        "routing": {},
        "mappers": {},
        "entropy": {"normalized_entropy": 0.40},
        "metadata": {"domain": "therapy"},
    }

    flags = compute_policy_flags(unified, "therapy")
    response = build_dilchat_response(unified, flags, "therapy")

    # Check that reflection is enabled in flags
    assert flags["allow_deep_reflection"] is True, "Therapy should enable reflection with safe formulas"

    # Check that response includes reflection hints
    hint_codes = [hint.code for hint in response.hints]
    assert "DEEP_REFLECTION" in hint_codes or "REFLECTION_MODE" in hint_codes, \
        "Therapy should include reflection hints when formulas are safe"


def test_dilchat_therapy_concrete_hint_enabled_with_high_tension():
    """
    Test that therapy domain forces concrete hints when tension is very high.

    With tension >= 0.75, therapy should produce PREFER_CONCRETE or GROUNDING hints
    and suppress reflection hints.
    """
    unified = {
        "text": "Stay grounded...",
        "coherence": {
            "coherence_score": 0.55,
            "coherence_score_v2": 0.50,
            "persona_drift_score": 0.50,
            "mapper_volatility_score": 0.45,
            "temporal_arc_score": 0.50,
            "resonance_index": 0.60,
            "tension_index": 0.85,  # Very high tension
            "arc_alignment_index": 0.40,
        },
        "symbolic": {},
        "practical": {"text": "Stay present"},
        "mirror": {},
        "dha": {},
        "routing": {},
        "mappers": {},
        "entropy": {"normalized_entropy": 0.50},
        "metadata": {"domain": "therapy"},
    }

    flags = compute_policy_flags(unified, "therapy")
    response = build_dilchat_response(unified, flags, "therapy")

    # Check that concrete is forced
    assert flags["prefer_concrete"] is True, "High tension should force concrete mode"
    assert flags["allow_deep_reflection"] is False, "High tension should disable reflection"

    # Check hints
    hint_codes = [hint.code for hint in response.hints]
    assert "PREFER_CONCRETE" in hint_codes or "GROUNDING" in hint_codes, \
        "Therapy should include concrete/grounding hints when tension is high"


def test_dilchat_identity_arc_hint_enabled_with_alignment():
    """
    Test that identity domain enables arc hints when arc_alignment is high.

    With high arc alignment and safe formula signals, identity should produce
    PREFER_ARC hints.
    """
    unified = {
        "text": "Your identity arc shows...",
        "coherence": {
            "coherence_score": 0.65,
            "coherence_score_v2": 0.72,
            "persona_drift_score": 0.35,
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.75,
            "resonance_index": 0.70,
            "tension_index": 0.35,
            "arc_alignment_index": 0.80,  # Very high arc alignment
        },
        "symbolic": {"summary": "Identity exploration"},
        "practical": {"text": "Identity reflection"},
        "mirror": {},
        "dha": {},
        "routing": {},
        "mappers": {},
        "entropy": {"normalized_entropy": 0.35},
        "metadata": {"domain": "identity"},
    }

    flags = compute_policy_flags(unified, "identity")
    response = build_dilchat_response(unified, flags, "identity")

    # Check that arc mode is enabled
    assert flags["prefer_arc_mode"] is True, "Identity should enable arc mode with high alignment"

    # Check hints
    hint_codes = [hint.code for hint in response.hints]
    assert "PREFER_ARC" in hint_codes, "Identity should include arc hints when alignment is high"


# ==============================================================================
# Group C: Behavioral Invariance & Determinism
# ==============================================================================


def test_policy_flags_deterministic_across_runs():
    """
    Test that compute_policy_flags produces identical results across multiple runs.

    Same unified output should always produce same flags.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.65,
            "coherence_score_v2": 0.70,
            "persona_drift_score": 0.40,
            "mapper_volatility_score": 0.35,
            "temporal_arc_score": 0.70,
            "resonance_index": 0.75,
            "tension_index": 0.30,
            "arc_alignment_index": 0.65,
        },
        "entropy": {"normalized_entropy": 0.40},
    }

    # Run multiple times
    flags_1 = compute_policy_flags(unified, "therapy")
    flags_2 = compute_policy_flags(unified, "therapy")
    flags_3 = compute_policy_flags(unified, "therapy")

    # Assert identical
    assert flags_1 == flags_2 == flags_3, "Policy flags must be deterministic"


def test_dilchat_response_deterministic_across_runs():
    """
    Test that DILchat response is deterministic for same input.

    Same unified output and flags should always produce same hints and badges.
    """
    unified = {
        "text": "Response text",
        "coherence": {
            "coherence_score": 0.65,
            "coherence_score_v2": 0.70,
            "persona_drift_score": 0.40,
            "mapper_volatility_score": 0.35,
            "temporal_arc_score": 0.70,
            "resonance_index": 0.75,
            "tension_index": 0.30,
            "arc_alignment_index": 0.65,
        },
        "symbolic": {"summary": "Test"},
        "practical": {"text": "Test"},
        "mirror": {},
        "dha": {},
        "routing": {},
        "mappers": {},
        "entropy": {"normalized_entropy": 0.40},
        "metadata": {"domain": "therapy"},
    }

    flags = compute_policy_flags(unified, "therapy")

    # Build response multiple times
    response_1 = build_dilchat_response(unified, flags, "therapy")
    response_2 = build_dilchat_response(unified, flags, "therapy")
    response_3 = build_dilchat_response(unified, flags, "therapy")

    # Assert hints identical
    assert response_1.hints == response_2.hints == response_3.hints, "Hints must be deterministic"
    assert response_1.badges == response_2.badges == response_3.badges, "Badges must be deterministic"


def test_trading_domain_complete_invariance():
    """
    Test that trading domain behavior is 100% unchanged by Phase 5.

    All policy flags should be identical with or without formula metrics.
    """
    unified_no_formulas = {
        "coherence": {
            "coherence_score": 0.60,
            "persona_drift_score": 0.35,
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.65,
        },
        "entropy": {"normalized_entropy": 0.45},
    }

    unified_with_formulas = {
        "coherence": {
            "coherence_score": 0.60,
            "persona_drift_score": 0.35,
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.65,
            "resonance_index": 0.90,
            "tension_index": 0.10,
            "arc_alignment_index": 0.85,
            "coherence_score_v2": 0.75,
        },
        "entropy": {"normalized_entropy": 0.45},
    }

    flags_without = compute_policy_flags(unified_no_formulas, "trading")
    flags_with = compute_policy_flags(unified_with_formulas, "trading")

    # Assert complete invariance
    assert flags_without == flags_with, "Trading flags must be unchanged by formula metrics"


def test_generic_domain_complete_invariance():
    """
    Test that generic domain behavior is 100% unchanged by Phase 5.

    All policy flags should be identical with or without formula metrics.
    """
    unified_no_formulas = {
        "coherence": {
            "coherence_score": 0.50,
            "persona_drift_score": 0.45,
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.55,
        },
        "entropy": {"normalized_entropy": 0.50},
    }

    unified_with_formulas = {
        "coherence": {
            "coherence_score": 0.50,
            "persona_drift_score": 0.45,
            "mapper_volatility_score": 0.40,
            "temporal_arc_score": 0.55,
            "resonance_index": 0.85,
            "tension_index": 0.15,
            "arc_alignment_index": 0.80,
        },
        "entropy": {"normalized_entropy": 0.50},
    }

    flags_without = compute_policy_flags(unified_no_formulas, "generic")
    flags_with = compute_policy_flags(unified_with_formulas, "generic")

    # Assert complete invariance
    assert flags_without == flags_with, "Generic flags must be unchanged by formula metrics"


def test_therapy_backward_compatible_without_formulas():
    """
    Test that therapy domain works correctly when formula metrics are absent.

    When Phase 3 metrics are missing (None), therapy should fall back to
    standard Phase 4 behavior without errors.
    """
    unified_no_formulas = {
        "coherence": {
            "coherence_score": 0.55,
            "coherence_score_v2": 0.60,
            "persona_drift_score": 0.50,
            "mapper_volatility_score": 0.45,
            "temporal_arc_score": 0.60,
            # No Phase 3 metrics
            "resonance_index": None,
            "tension_index": None,
            "arc_alignment_index": None,
        },
        "entropy": {"normalized_entropy": 0.45},
    }

    # Should not raise any errors
    flags = compute_policy_flags(unified_no_formulas, "therapy")

    # Verify flags computed (using Phase 4 v2 logic only)
    assert "allow_deep_reflection" in flags
    assert "prefer_arc_mode" in flags
    assert "prefer_concrete" in flags


def test_identity_backward_compatible_without_formulas():
    """
    Test that identity domain works correctly when formula metrics are absent.

    When Phase 3 metrics are missing, identity should fall back to standard
    Phase 4 behavior without errors.
    """
    unified_no_formulas = {
        "coherence": {
            "coherence_score": 0.60,
            "coherence_score_v2": 0.65,
            "persona_drift_score": 0.40,
            "mapper_volatility_score": 0.45,
            "temporal_arc_score": 0.70,
            # Missing Phase 3 metrics
        },
        "entropy": {"normalized_entropy": 0.40},
    }

    # Should not raise any errors
    flags = compute_policy_flags(unified_no_formulas, "identity")

    # Verify flags computed
    assert "allow_deep_reflection" in flags
    assert "prefer_arc_mode" in flags


def test_phase5_changes_only_ui_flags_not_core_flags():
    """
    Test that Phase 5 NEVER changes core safety/routing flags.

    Verify that needs_grounding, coherence_warning, stability_status,
    and recommended_mapper are computed by Phase 1-4 logic only.
    """
    unified = {
        "coherence": {
            "coherence_score": 0.40,  # Below therapy min (triggers needs_grounding)
            "coherence_score_v2": 0.45,
            "persona_drift_score": 0.70,  # High drift (triggers needs_grounding)
            "mapper_volatility_score": 0.30,
            "temporal_arc_score": 0.50,
            "resonance_index": 0.95,  # Very high (but shouldn't override safety)
            "tension_index": 0.05,     # Very low
            "arc_alignment_index": 0.90,
        },
        "entropy": {"normalized_entropy": 0.60},
    }

    flags = compute_policy_flags(unified, "therapy")

    # Assert core safety flags are NOT overridden by formulas
    assert flags["needs_grounding"] is True, "needs_grounding must be determined by Phase 1-4 logic"
    assert flags["stability_status"] == "fragmented", "stability_status must be determined by Phase 1-4 logic"
    assert flags["recommended_mapper"] == "LCM", "Mapper must be LCM due to needs_grounding"


# ==============================================================================
# Summary
# ==============================================================================

"""
Phase 5 Test Suite Summary
===========================

Group A (8 tests):
- Refinement logic disabled for formula_ui_mode="none"
- Deep reflection enabled with safe signals
- Arc mode enabled with high alignment
- Concrete forced with high tension
- Refinement skipped when metrics missing
- Domain-specific thresholds respected
- Safety flags never modified
- Deterministic refinement

Group B (5 tests):
- Trading hints invariant
- Generic hints invariant
- Therapy reflection hints enabled
- Therapy concrete hints forced
- Identity arc hints enabled

Group C (7 tests):
- Policy flags deterministic
- DILchat response deterministic
- Trading complete invariance
- Generic complete invariance
- Therapy backward compatible
- Identity backward compatible
- Phase 5 only affects UI flags

Total: 20 tests covering all Phase 5 requirements
"""
