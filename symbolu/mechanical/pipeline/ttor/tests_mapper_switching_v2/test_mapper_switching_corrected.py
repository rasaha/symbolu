"""
TTOR Mapper Switching Corrected Test Suite v2.0

Enforces CANONICAL MAPPER ACTIVATION RULES for TTOR → Mappers routing.
These rules are frozen in CI to prevent routing drift.

CANONICAL RULES:
================

HRM (High-Resolution Mapper):
    use_hrm = (tier != LOWER) and (entropy_mix > 0.40)

LCM (Low-Context Mapper):
    use_lcm = (tier == LOWER) and (entropy_mix > 0.50)

LAM (Long-Arc Mapper):
    use_lam = (
        long_arc_tension > 0.50
        or temporal_patterns_detected
        or (domain in ["therapy", "identity", "spiritual"] and entropy_mix > 0.60)
    )

TEST PROFILES:
==============
1. simple_task_low_entropy     - tier=LOWER, low entropy → LCM=True expected
2. deep_therapy_high_entropy   - tier=UPPER, therapy domain, high entropy → HRM=True, LAM=True
3. long_arc_high_tension       - high tension → LAM=True
4. generic_low_complexity_chat - generic domain, low entropy → no mappers

NOTE: This test suite computes EXPECTED values using the canonical formulas
and compares them against ACTUAL router output. If they differ, the test
fails - indicating routing drift that requires review.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

from symbolu.mechanical.pipeline.ttor.router import TTORRouter
from symbolu.mechanical.pipeline.ttor.models import RouterContext, Tier
from symbolu.mechanical.pipeline.ttor.constants import H_D_MAX, H_G_MAX
from symbolu.mechanical.pipeline.ttor.formulas import entropy_mix as compute_entropy_mix

# =============================================================================
# PATH CONFIGURATION
# =============================================================================
BASE_DIR = Path(__file__).parent.parent
BASELINE_PATH = BASE_DIR / "snapshots" / "mapper_switching_baseline_v2.json"
REPORT_PATH = Path(__file__).parent / "mapper_switching_report_v2.json"

# =============================================================================
# CANONICAL THRESHOLDS
# =============================================================================
HRM_ENTROPY_THRESHOLD = 0.40  # entropy_mix threshold for HRM activation
LCM_ENTROPY_THRESHOLD = 0.50  # entropy_mix threshold for LCM activation
LAM_TENSION_THRESHOLD = 0.50  # long_arc_tension threshold for LAM activation
LAM_DOMAIN_ENTROPY_THRESHOLD = 0.60  # entropy_mix threshold for domain-based LAM
LAM_DOMAINS = frozenset(["therapy", "identity", "spiritual"])

# Profile definitions
PROFILES = [
    "simple_task_low_entropy",
    "deep_therapy_high_entropy",
    "long_arc_high_tension",
    "generic_low_complexity_chat",
]


def compute_expected_mappers(
    tier: Tier,
    entropy_mix: float,
    domain: str,
    long_arc_tension: float,
    temporal_patterns_detected: bool = False,
) -> Dict[str, bool]:
    """
    Compute expected mapper activation flags using CANONICAL FORMULAS.

    CANONICAL RULES:
    ----------------
    HRM: use_hrm = (tier != LOWER) and (entropy_mix > 0.40)
    LCM: use_lcm = (tier == LOWER) and (entropy_mix > 0.50)
    LAM: use_lam = (
        long_arc_tension > 0.50
        or temporal_patterns_detected
        or (domain in ["therapy", "identity", "spiritual"] and entropy_mix > 0.60)
    )

    Args:
        tier: Computed routing tier (LOWER, UPPER, or HYBRID)
        entropy_mix: Normalized entropy mix value [0, 1]
        domain: Domain classification string
        long_arc_tension: Long-arc tension value [0, 1]
        temporal_patterns_detected: Whether temporal patterns were detected

    Returns:
        Dictionary with use_hrm, use_lcm, use_lam boolean values
    """
    # HRM: (tier != LOWER) and (entropy_mix > 0.40)
    use_hrm = (tier != Tier.LOWER) and (entropy_mix > HRM_ENTROPY_THRESHOLD)

    # LCM: (tier == LOWER) and (entropy_mix > 0.50)
    use_lcm = (tier == Tier.LOWER) and (entropy_mix > LCM_ENTROPY_THRESHOLD)

    # LAM: (long_arc_tension > 0.50) or temporal_patterns_detected or
    #      (domain in LAM_DOMAINS and entropy_mix > 0.60)
    use_lam = (
        long_arc_tension > LAM_TENSION_THRESHOLD
        or temporal_patterns_detected
        or (domain in LAM_DOMAINS and entropy_mix > LAM_DOMAIN_ENTROPY_THRESHOLD)
    )

    return {
        "use_hrm": use_hrm,
        "use_lcm": use_lcm,
        "use_lam": use_lam,
    }


def build_router_context(profile: str) -> RouterContext:
    """
    Build deterministic RouterContext instances for canonical routing profiles.

    Each profile is designed to test specific canonical rule conditions:
    - simple_task_low_entropy: LOWER tier, low entropy
    - deep_therapy_high_entropy: UPPER tier, therapy domain, high entropy
    - long_arc_high_tension: High long_arc_tension (> 0.50)
    - generic_low_complexity_chat: Generic domain, moderate entropy

    Args:
        profile: Profile identifier string

    Returns:
        RouterContext configured for the specified profile

    Raises:
        ValueError: If profile is not recognized
    """
    if profile == "simple_task_low_entropy":
        # Designed for: tier=LOWER, low entropy
        # Expected by canonical rules:
        #   - use_hrm = False (tier is LOWER)
        #   - use_lcm = True if entropy > 0.50, but we use low entropy
        #   - use_lam = False (no high tension, no temporal, not LAM domain)
        aspect_probs = {
            "Execution": 0.7,
            "Cognition": 0.5,
            "Identity": 0.3,
            "Form": 0.2,
            "Agency": 0.05,
            "Reasoning": 0.05,
            "Purpose": 0.05,
            "Observation": 0.05,
        }
        anchor_scores = {
            "Needs": 0.8,
            "Exchange": 0.7,
            "Challenge": 0.6,
            "Belonging": 0.1,
            "Relation": 0.1,
            "Change": 0.1,
            "Meaning": 0.1,
            "Role": 0.1,
            "Collective": 0.1,
        }
        # Low entropy: ~15% of max for H_D, ~10% for H_G
        # entropy_mix = 0.6 * 0.15 + 0.4 * 0.10 = 0.09 + 0.04 = 0.13
        H_D = H_D_MAX * 0.15
        H_G = H_G_MAX * 0.10
        domain = "task"
        risk_level = "low"
        long_arc_tension = 0.1

    elif profile == "deep_therapy_high_entropy":
        # Designed for: tier=UPPER, therapy domain, high entropy (> 0.60)
        # Expected by canonical rules:
        #   - use_hrm = True (tier != LOWER and entropy > 0.40)
        #   - use_lcm = False (tier != LOWER)
        #   - use_lam = True (therapy domain + entropy > 0.60)
        aspect_probs = {
            "Purpose": 0.7,
            "Observation": 0.6,
            "Universal": 0.5,
            "Core": 0.4,
            "Agency": 0.3,
            "Reasoning": 0.3,
            "Execution": 0.05,
            "Cognition": 0.05,
            "Identity": 0.1,
            "Form": 0.05,
        }
        anchor_scores = {
            "Meaning": 0.9,
            "Role": 0.8,
            "Collective": 0.7,
            "Belonging": 0.6,
            "Relation": 0.5,
            "Change": 0.5,
            "Needs": 0.1,
            "Exchange": 0.1,
            "Challenge": 0.1,
        }
        # High entropy: ~85% of max for H_D, ~80% for H_G
        # entropy_mix = 0.6 * 0.85 + 0.4 * 0.80 = 0.51 + 0.32 = 0.83
        H_D = H_D_MAX * 0.85
        H_G = H_G_MAX * 0.80
        domain = "therapy"
        risk_level = "medium"
        long_arc_tension = 0.4

    elif profile == "long_arc_high_tension":
        # Designed for: High long_arc_tension (> 0.50)
        # Expected by canonical rules:
        #   - use_hrm = depends on tier and entropy
        #   - use_lcm = depends on tier and entropy
        #   - use_lam = True (long_arc_tension > 0.50)
        aspect_probs = {
            "Identity": 0.4,
            "Purpose": 0.5,
            "Observation": 0.4,
            "Agency": 0.3,
            "Core": 0.3,
            "Execution": 0.1,
            "Cognition": 0.2,
            "Form": 0.1,
        }
        anchor_scores = {
            "Meaning": 0.7,
            "Role": 0.6,
            "Belonging": 0.5,
            "Relation": 0.4,
            "Change": 0.4,
            "Collective": 0.3,
            "Needs": 0.2,
            "Exchange": 0.2,
            "Challenge": 0.2,
        }
        # Moderate-high entropy: ~70% of max for H_D, ~65% for H_G
        # entropy_mix = 0.6 * 0.70 + 0.4 * 0.65 = 0.42 + 0.26 = 0.68
        H_D = H_D_MAX * 0.70
        H_G = H_G_MAX * 0.65
        domain = "identity"
        risk_level = "medium"
        # High tension - key signal for LAM
        long_arc_tension = 0.9

    elif profile == "generic_low_complexity_chat":
        # Designed for: Generic domain, moderate entropy, no mapper activation
        # Expected by canonical rules (for LOWER tier):
        #   - use_hrm = False (tier is LOWER)
        #   - use_lcm = False (entropy < 0.50)
        #   - use_lam = False (no high tension, not LAM domain)
        aspect_probs = {
            "Execution": 0.5,
            "Cognition": 0.4,
            "Identity": 0.3,
            "Form": 0.3,
            "Agency": 0.1,
            "Reasoning": 0.1,
            "Purpose": 0.1,
            "Observation": 0.1,
        }
        anchor_scores = {
            "Needs": 0.5,
            "Exchange": 0.4,
            "Challenge": 0.3,
            "Belonging": 0.05,
            "Relation": 0.05,
            "Change": 0.05,
            "Meaning": 0.05,
            "Role": 0.05,
            "Collective": 0.05,
        }
        # Low entropy: ~20% of max
        # entropy_mix = 0.6 * 0.20 + 0.4 * 0.20 = 0.12 + 0.08 = 0.20
        H_D = H_D_MAX * 0.20
        H_G = H_G_MAX * 0.20
        domain = "generic"
        risk_level = "low"
        long_arc_tension = 0.1

    else:
        raise ValueError(f"Unknown profile: {profile}")

    return RouterContext(
        aspect_probs=aspect_probs,
        H_D=H_D,
        H_G=H_G,
        H_K=0.0,
        vritti_probs=None,
        anchor_scores=anchor_scores,
        domain=domain,
        risk_level=risk_level,
        long_arc_tension=long_arc_tension,
    )


def get_profile_metadata(profile: str) -> Dict[str, Any]:
    """
    Get metadata for a profile including expected tier and other inputs.

    This is used for computing expected mapper values without running the router.

    Args:
        profile: Profile identifier string

    Returns:
        Dictionary with domain, long_arc_tension, temporal_patterns_detected,
        and expected_tier based on profile design.
    """
    ctx = build_router_context(profile)
    normalized_entropy, _ = compute_entropy_mix(ctx.H_D, ctx.H_G)

    # Temporal patterns are not detected for any test profiles (deterministic)
    temporal_patterns_detected = False

    return {
        "domain": ctx.domain,
        "long_arc_tension": ctx.long_arc_tension,
        "temporal_patterns_detected": temporal_patterns_detected,
        "entropy_mix": normalized_entropy,
        "H_D": ctx.H_D,
        "H_G": ctx.H_G,
    }


def collect_routing_decisions() -> Dict[str, Dict[str, Any]]:
    """
    Execute TTOR routing for all canonical profiles and collect results.

    Collects both:
    - Actual routing results from TTORRouter.route()
    - Expected results computed from canonical formulas

    Returns:
        Dictionary mapping profile names to their routing decisions,
        including actual and expected mapper flags.
    """
    router = TTORRouter()
    results: Dict[str, Dict[str, Any]] = {}

    for profile in PROFILES:
        ctx = build_router_context(profile)
        plan = router.route(ctx)

        # Get actual tier from router
        actual_tier = plan.tier

        # Compute entropy_mix for canonical formula
        normalized_entropy, _ = compute_entropy_mix(ctx.H_D, ctx.H_G)

        # Compute expected mappers using canonical formulas
        expected = compute_expected_mappers(
            tier=actual_tier,
            entropy_mix=normalized_entropy,
            domain=ctx.domain,
            long_arc_tension=ctx.long_arc_tension,
            temporal_patterns_detected=False,  # No temporal patterns in test profiles
        )

        # Collect actual mapper flags
        actual = {
            "use_hrm": bool(plan.use_hrm),
            "use_lcm": bool(plan.use_lcm),
            "use_lam": bool(plan.use_lam),
        }

        results[profile] = {
            "actual": {
                "tier": plan.tier.value,
                "flow_mode": plan.flow_mode.value,
                "preferred_engine_family": plan.preferred_engine_family,
                "use_hrm": actual["use_hrm"],
                "use_lcm": actual["use_lcm"],
                "use_lam": actual["use_lam"],
                "regulated_mode": bool(plan.regulated_mode),
                "allow_metaphor": bool(plan.allow_metaphor),
            },
            "expected": expected,
            "inputs": {
                "domain": ctx.domain,
                "long_arc_tension": ctx.long_arc_tension,
                "entropy_mix": normalized_entropy,
                "H_D": ctx.H_D,
                "H_G": ctx.H_G,
            },
        }

    return results


# =============================================================================
# TEST 1: COMPARE ACTUAL TO EXPECTED (CANONICAL RULES)
# =============================================================================
def test_mapper_switching_against_canonical_rules() -> None:
    """
    Test that TTOR mapper switching matches expected outcomes per CANONICAL RULES.

    This test verifies that:
    1. HRM/LCM/LAM flags match canonical formula expectations
    2. Any deviation indicates routing drift from canonical specification

    CANONICAL RULES ENFORCED:
    - HRM: (tier != LOWER) and (entropy_mix > 0.40)
    - LCM: (tier == LOWER) and (entropy_mix > 0.50)
    - LAM: (long_arc_tension > 0.50) or temporal_patterns_detected or
           (domain in ["therapy", "identity", "spiritual"] and entropy_mix > 0.60)
    """
    routing_results = collect_routing_decisions()

    # Always write a human-readable report for CI artifact collection
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(routing_results, indent=2, sort_keys=True),
        encoding="utf-8"
    )

    # Compare against canonical expectations
    failures = []
    for profile in PROFILES:
        result = routing_results[profile]
        actual = result["actual"]
        expected = result["expected"]
        inputs = result["inputs"]

        # Check each mapper flag
        for mapper in ["use_hrm", "use_lcm", "use_lam"]:
            if actual[mapper] != expected[mapper]:
                failures.append(
                    f"Profile '{profile}': {mapper} differs from canonical expectation\n"
                    f"  Actual: {actual[mapper]}\n"
                    f"  Expected (canonical): {expected[mapper]}\n"
                    f"  Inputs: tier={actual['tier']}, entropy_mix={inputs['entropy_mix']:.4f}, "
                    f"domain={inputs['domain']}, tension={inputs['long_arc_tension']}"
                )

    if failures:
        pytest.fail(
            "Routing drift detected - mapper flags do not match canonical rules:\n\n"
            + "\n\n".join(failures)
        )


# =============================================================================
# TEST 2: BASELINE STABILITY ENFORCEMENT
# =============================================================================
def test_mapper_switching_baseline_stability() -> None:
    """
    Test that TTOR mapper switching matches the stored baseline snapshot.

    Provides regression protection against unintentional changes:
    - If baseline doesn't exist, creates it and skips enforcement
    - If baseline exists, compares current actual results against it
    - Any deviation in mapper flags fails the test

    To update baseline after intentional changes:
    1. Delete mapper_switching_baseline_v2.json
    2. Run tests to regenerate
    3. Review changes and commit new baseline
    """
    routing_results = collect_routing_decisions()

    # Ensure snapshots directory exists
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Extract actual results for baseline comparison
    actual_for_baseline: Dict[str, Dict[str, Any]] = {}
    for profile in PROFILES:
        actual_for_baseline[profile] = routing_results[profile]["actual"]

    if not BASELINE_PATH.exists():
        # First run: create baseline and skip enforcement
        BASELINE_PATH.write_text(
            json.dumps(actual_for_baseline, indent=2, sort_keys=True),
            encoding="utf-8"
        )
        pytest.skip(
            f"Baseline v2 created at {BASELINE_PATH}; "
            "rerun tests to enforce mapper switching stability."
        )

    # Load and compare against baseline
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    failures = []
    for profile in baseline.keys():
        if profile not in actual_for_baseline:
            failures.append(
                f"Profile '{profile}' exists in baseline but not in current results"
            )
            continue

        baseline_result = baseline[profile]
        actual_result = actual_for_baseline[profile]

        # Compare mapper flags
        for mapper in ["use_hrm", "use_lcm", "use_lam"]:
            if actual_result.get(mapper) != baseline_result.get(mapper):
                failures.append(
                    f"Profile '{profile}': {mapper} differs from baseline\n"
                    f"  Actual: {actual_result.get(mapper)}\n"
                    f"  Baseline: {baseline_result.get(mapper)}"
                )

    # Check for new profiles not in baseline
    for profile in actual_for_baseline.keys():
        if profile not in baseline:
            failures.append(
                f"Profile '{profile}' exists in current results but not in baseline. "
                "Delete baseline and regenerate to include new profiles."
            )

    if failures:
        pytest.fail(
            "Baseline stability check failed:\n\n" + "\n\n".join(failures)
        )


# =============================================================================
# TEST 3: REPORT GENERATION
# =============================================================================
def test_report_generation() -> None:
    """
    Test that the mapper switching report is generated with correct structure.

    This test ensures:
    1. Report JSON file is created
    2. Report contains all canonical profiles
    3. Report includes both actual and expected values
    """
    routing_results = collect_routing_decisions()

    # Write report
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(routing_results, indent=2, sort_keys=True),
        encoding="utf-8"
    )

    # Verify report exists and is valid JSON
    assert REPORT_PATH.exists(), f"Report not created at {REPORT_PATH}"

    report_content = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    # Verify all profiles are present
    for profile in PROFILES:
        assert profile in report_content, f"Profile '{profile}' missing from report"

        profile_data = report_content[profile]

        # Verify structure
        assert "actual" in profile_data, f"Profile '{profile}' missing 'actual' key"
        assert "expected" in profile_data, f"Profile '{profile}' missing 'expected' key"

        # Verify mapper keys in actual
        for mapper in ["use_hrm", "use_lcm", "use_lam"]:
            assert mapper in profile_data["actual"], (
                f"Profile '{profile}' actual missing '{mapper}'"
            )
            assert mapper in profile_data["expected"], (
                f"Profile '{profile}' expected missing '{mapper}'"
            )


# =============================================================================
# TEST CLASS: CANONICAL FORMULA VALIDATION
# =============================================================================
class TestCanonicalFormulaLogic:
    """
    Direct tests for compute_expected_mappers() canonical formulas.

    These tests verify the formula implementation itself is correct.
    """

    def test_hrm_canonical_formula_lower_tier(self) -> None:
        """HRM should be False for LOWER tier regardless of entropy."""
        result = compute_expected_mappers(
            tier=Tier.LOWER,
            entropy_mix=0.80,  # High entropy, but tier is LOWER
            domain="generic",
            long_arc_tension=0.0,
        )
        assert result["use_hrm"] is False, (
            "HRM should be False for LOWER tier (canonical rule)"
        )

    def test_hrm_canonical_formula_upper_tier_high_entropy(self) -> None:
        """HRM should be True for UPPER tier with entropy > 0.40."""
        result = compute_expected_mappers(
            tier=Tier.UPPER,
            entropy_mix=0.50,  # > 0.40 threshold
            domain="generic",
            long_arc_tension=0.0,
        )
        assert result["use_hrm"] is True, (
            "HRM should be True for UPPER tier with entropy > 0.40"
        )

    def test_hrm_canonical_formula_upper_tier_low_entropy(self) -> None:
        """HRM should be False for UPPER tier with entropy <= 0.40."""
        result = compute_expected_mappers(
            tier=Tier.UPPER,
            entropy_mix=0.35,  # <= 0.40 threshold
            domain="generic",
            long_arc_tension=0.0,
        )
        assert result["use_hrm"] is False, (
            "HRM should be False for UPPER tier with entropy <= 0.40"
        )

    def test_hrm_canonical_formula_hybrid_tier(self) -> None:
        """HRM should be True for HYBRID tier with entropy > 0.40."""
        result = compute_expected_mappers(
            tier=Tier.HYBRID,
            entropy_mix=0.50,  # > 0.40 threshold
            domain="generic",
            long_arc_tension=0.0,
        )
        assert result["use_hrm"] is True, (
            "HRM should be True for HYBRID tier (tier != LOWER) with entropy > 0.40"
        )

    def test_lcm_canonical_formula_lower_tier_high_entropy(self) -> None:
        """LCM should be True for LOWER tier with entropy > 0.50."""
        result = compute_expected_mappers(
            tier=Tier.LOWER,
            entropy_mix=0.60,  # > 0.50 threshold
            domain="generic",
            long_arc_tension=0.0,
        )
        assert result["use_lcm"] is True, (
            "LCM should be True for LOWER tier with entropy > 0.50"
        )

    def test_lcm_canonical_formula_lower_tier_low_entropy(self) -> None:
        """LCM should be False for LOWER tier with entropy <= 0.50."""
        result = compute_expected_mappers(
            tier=Tier.LOWER,
            entropy_mix=0.40,  # <= 0.50 threshold
            domain="generic",
            long_arc_tension=0.0,
        )
        assert result["use_lcm"] is False, (
            "LCM should be False for LOWER tier with entropy <= 0.50"
        )

    def test_lcm_canonical_formula_upper_tier(self) -> None:
        """LCM should be False for non-LOWER tier."""
        result = compute_expected_mappers(
            tier=Tier.UPPER,
            entropy_mix=0.80,  # High entropy, but tier is not LOWER
            domain="generic",
            long_arc_tension=0.0,
        )
        assert result["use_lcm"] is False, (
            "LCM should be False for non-LOWER tier"
        )

    def test_lam_canonical_formula_high_tension(self) -> None:
        """LAM should be True when long_arc_tension > 0.50."""
        result = compute_expected_mappers(
            tier=Tier.LOWER,
            entropy_mix=0.20,  # Low entropy
            domain="generic",  # Not a LAM domain
            long_arc_tension=0.60,  # > 0.50 threshold
        )
        assert result["use_lam"] is True, (
            "LAM should be True when long_arc_tension > 0.50"
        )

    def test_lam_canonical_formula_temporal_patterns(self) -> None:
        """LAM should be True when temporal_patterns_detected."""
        result = compute_expected_mappers(
            tier=Tier.LOWER,
            entropy_mix=0.20,
            domain="generic",
            long_arc_tension=0.10,  # Low tension
            temporal_patterns_detected=True,
        )
        assert result["use_lam"] is True, (
            "LAM should be True when temporal_patterns_detected"
        )

    def test_lam_canonical_formula_therapy_domain_high_entropy(self) -> None:
        """LAM should be True for therapy domain with entropy > 0.60."""
        result = compute_expected_mappers(
            tier=Tier.UPPER,
            entropy_mix=0.70,  # > 0.60 threshold
            domain="therapy",  # LAM domain
            long_arc_tension=0.10,  # Low tension
        )
        assert result["use_lam"] is True, (
            "LAM should be True for therapy domain with entropy > 0.60"
        )

    def test_lam_canonical_formula_identity_domain_high_entropy(self) -> None:
        """LAM should be True for identity domain with entropy > 0.60."""
        result = compute_expected_mappers(
            tier=Tier.UPPER,
            entropy_mix=0.65,  # > 0.60 threshold
            domain="identity",  # LAM domain
            long_arc_tension=0.10,
        )
        assert result["use_lam"] is True, (
            "LAM should be True for identity domain with entropy > 0.60"
        )

    def test_lam_canonical_formula_spiritual_domain_high_entropy(self) -> None:
        """LAM should be True for spiritual domain with entropy > 0.60."""
        result = compute_expected_mappers(
            tier=Tier.UPPER,
            entropy_mix=0.65,  # > 0.60 threshold
            domain="spiritual",  # LAM domain
            long_arc_tension=0.10,
        )
        assert result["use_lam"] is True, (
            "LAM should be True for spiritual domain with entropy > 0.60"
        )

    def test_lam_canonical_formula_no_activation(self) -> None:
        """LAM should be False when no activation conditions met."""
        result = compute_expected_mappers(
            tier=Tier.LOWER,
            entropy_mix=0.30,  # Low entropy
            domain="generic",  # Not a LAM domain
            long_arc_tension=0.20,  # Low tension
            temporal_patterns_detected=False,
        )
        assert result["use_lam"] is False, (
            "LAM should be False when no activation conditions are met"
        )


# =============================================================================
# TEST CLASS: PROFILE VALIDATION
# =============================================================================
class TestProfileValidation:
    """Tests to verify profile definitions are valid and complete."""

    def test_all_profiles_buildable(self) -> None:
        """Verify all profiles can be built without errors."""
        for profile in PROFILES:
            ctx = build_router_context(profile)
            assert ctx is not None, f"Failed to build context for profile: {profile}"
            assert ctx.domain is not None
            assert ctx.aspect_probs is not None
            assert len(ctx.aspect_probs) > 0

    def test_unknown_profile_raises_error(self) -> None:
        """Verify unknown profile names raise ValueError."""
        with pytest.raises(ValueError, match="Unknown profile"):
            build_router_context("nonexistent_profile")

    def test_profile_entropy_values(self) -> None:
        """Verify entropy values are in expected ranges for each profile."""
        for profile in PROFILES:
            ctx = build_router_context(profile)
            normalized_entropy, _ = compute_entropy_mix(ctx.H_D, ctx.H_G)

            # All entropy values should be in [0, 1]
            assert 0.0 <= normalized_entropy <= 1.0, (
                f"Profile '{profile}': entropy_mix {normalized_entropy} out of range"
            )


# =============================================================================
# TEST CLASS: ROUTING STABILITY
# =============================================================================
class TestRoutingStability:
    """Tests to verify routing stability and determinism."""

    def test_routing_is_deterministic(self) -> None:
        """Verify that routing produces identical results on repeated calls."""
        router = TTORRouter()

        for profile in PROFILES:
            ctx = build_router_context(profile)

            # Run routing multiple times
            results = [router.route(ctx) for _ in range(3)]

            # All results should be identical
            for i, result in enumerate(results[1:], start=2):
                assert result.tier == results[0].tier, (
                    f"Profile '{profile}': tier differed on run {i}"
                )
                assert result.use_hrm == results[0].use_hrm, (
                    f"Profile '{profile}': use_hrm differed on run {i}"
                )
                assert result.use_lcm == results[0].use_lcm, (
                    f"Profile '{profile}': use_lcm differed on run {i}"
                )
                assert result.use_lam == results[0].use_lam, (
                    f"Profile '{profile}': use_lam differed on run {i}"
                )

    def test_all_profiles_produce_valid_plans(self) -> None:
        """Verify all profiles produce complete RoutingPlan objects."""
        router = TTORRouter()

        for profile in PROFILES:
            ctx = build_router_context(profile)
            plan = router.route(ctx)

            # Verify plan has all required fields
            assert plan.tier is not None
            assert plan.flow_mode is not None
            assert plan.preferred_engine_family is not None
            assert isinstance(plan.use_hrm, bool)
            assert isinstance(plan.use_lcm, bool)
            assert isinstance(plan.use_lam, bool)
            assert plan.explanation is not None
            assert len(plan.explanation) > 0
