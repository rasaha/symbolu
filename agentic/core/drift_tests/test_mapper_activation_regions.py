"""
Mapper Activation Region Tests
===============================

Grid-based validation of HRM/LCM/LAM activation zones across:
- Tier: LOWER / HYBRID / UPPER
- Domain: generic / task / therapy / identity / spiritual
- Normalized Entropy: [0.0, 0.39, 0.41, 0.49, 0.51, 0.59, 0.61, 1.0]
- Long-Arc Tension: [0.0, 0.49, 0.51, 1.0]

Canonical Mapper Rules v2.0:
----------------------------
HRM: (tier != LOWER) and (normalized_entropy > 0.40)
LCM: (tier == LOWER) and (normalized_entropy > 0.50)
LAM: (long_arc_tension > 0.50) or temporal_patterns_detected
     or (domain in ["therapy", "identity", "spiritual"] and normalized_entropy > 0.60)

This test suite ensures zero drift from these formulas.
"""

import math
import pytest
from typing import Dict

from symbolu_core.mechanical.pipeline.ttor.router import TTORRouter
from symbolu_core.mechanical.pipeline.ttor.models import RouterContext, Tier


# Canonical rules reference (must match TTOR implementation exactly)
def expected_mappers(
    tier: Tier,
    domain: str,
    normalized_entropy: float,
    long_arc_tension: float,
) -> Dict[str, bool]:
    """
    Compute expected mapper flags using canonical formulas v2.0.

    This function is the drift reference - it must never change unless
    the canonical rules themselves are updated (which requires approval).
    """
    # Canonical thresholds (frozen in v2.0)
    HRM_ENTROPY_THRESHOLD = 0.40
    LCM_ENTROPY_THRESHOLD = 0.50
    LAM_TENSION_THRESHOLD = 0.50
    LAM_DOMAIN_ENTROPY_THRESHOLD = 0.60
    LAM_DOMAINS = ["therapy", "identity", "spiritual"]

    # Temporal patterns detection (not yet implemented)
    temporal_patterns_detected = False

    # Apply canonical formulas exactly
    use_hrm = (tier != Tier.LOWER) and (normalized_entropy > HRM_ENTROPY_THRESHOLD)
    use_lcm = (tier == Tier.LOWER) and (normalized_entropy > LCM_ENTROPY_THRESHOLD)
    use_lam = (
        long_arc_tension > LAM_TENSION_THRESHOLD
        or temporal_patterns_detected
        or (domain in LAM_DOMAINS and normalized_entropy > LAM_DOMAIN_ENTROPY_THRESHOLD)
    )

    return {
        "use_hrm": use_hrm,
        "use_lcm": use_lcm,
        "use_lam": use_lam,
    }


def create_router_context_for_entropy(
    target_entropy: float,
    domain: str = "generic",
    long_arc_tension: float = 0.0,
) -> RouterContext:
    """
    Create a RouterContext that produces approximately the target normalized_entropy.

    TTOR computes normalized_entropy as:
        normalized_entropy = 0.6 * (H_D / ln(10)) + 0.4 * (H_G / ln(3))

    To achieve target_entropy e ∈ [0, 1], we directly set:
        H_D = e * ln(10)
        H_G = e * ln(3)

    This gives: normalized_entropy = 0.6*e + 0.4*e = 1.0*e = e

    So we can directly use the target_entropy as the scaling factor.
    """
    # Direct calculation: to get normalized_entropy ≈ target_entropy,
    # we need H_D and H_G such that 0.6*(H_D/ln(10)) + 0.4*(H_G/ln(3)) = target_entropy
    # Setting H_D = k*ln(10) and H_G = k*ln(3) gives: 0.6*k + 0.4*k = 1.0*k = target_entropy
    # So k = target_entropy

    k = target_entropy
    k = min(1.0, max(0.0, k))  # Clamp to [0, 1]

    H_D = k * math.log(10)
    H_G = k * math.log(3)

    # Balanced aspect probabilities (neutral tier bias)
    aspect_probs = {
        "Execution": 0.15,
        "Identity": 0.15,
        "Form": 0.10,
        "Cognition": 0.10,
        "Agency": 0.15,
        "Reasoning": 0.15,
        "Purpose": 0.10,
        "Observation": 0.05,
        "Core": 0.03,
        "Universal": 0.02,
    }

    # Balanced anchor scores (neutral tier bias)
    anchor_scores = {
        "Needs": 0.2,
        "Exchange": 0.2,
        "Challenge": 0.1,
        "Belonging": 0.15,
        "Relation": 0.15,
        "Change": 0.1,
        "Meaning": 0.05,
        "Role": 0.03,
        "Collective": 0.02,
    }

    return RouterContext(
        aspect_probs=aspect_probs,
        H_D=H_D,
        H_G=H_G,
        H_K=0.0,
        anchor_scores=anchor_scores,
        domain=domain,
        risk_level="low",
        long_arc_tension=long_arc_tension,
    )


def override_tier_in_context(
    ctx: RouterContext,
    target_tier: Tier,
) -> RouterContext:
    """
    Modify aspect_probs to force a specific tier outcome.

    LOWER: Boost lower aspects (Execution, Identity, Form, Cognition)
    UPPER: Boost upper aspects (Agency, Reasoning, Purpose, etc.)
    HYBRID: Balance both tiers
    """
    if target_tier == Tier.LOWER:
        aspect_probs = {
            "Execution": 0.50,
            "Identity": 0.25,
            "Form": 0.15,
            "Cognition": 0.08,
            "Agency": 0.01,
            "Reasoning": 0.005,
            "Purpose": 0.003,
            "Observation": 0.001,
            "Core": 0.0005,
            "Universal": 0.0005,
        }
    elif target_tier == Tier.UPPER:
        aspect_probs = {
            "Execution": 0.005,
            "Identity": 0.003,
            "Form": 0.001,
            "Cognition": 0.001,
            "Agency": 0.35,
            "Reasoning": 0.35,
            "Purpose": 0.20,
            "Observation": 0.075,
            "Core": 0.01,
            "Universal": 0.005,
        }
    else:  # HYBRID
        aspect_probs = {
            "Execution": 0.15,
            "Identity": 0.15,
            "Form": 0.10,
            "Cognition": 0.10,
            "Agency": 0.15,
            "Reasoning": 0.15,
            "Purpose": 0.10,
            "Observation": 0.05,
            "Core": 0.03,
            "Universal": 0.02,
        }

    # Also adjust anchor scores to reinforce tier bias
    if target_tier == Tier.LOWER:
        anchor_scores = {
            "Needs": 0.40,
            "Exchange": 0.35,
            "Challenge": 0.20,
            "Belonging": 0.02,
            "Relation": 0.01,
            "Change": 0.01,
            "Meaning": 0.005,
            "Role": 0.003,
            "Collective": 0.002,
        }
    elif target_tier == Tier.UPPER:
        anchor_scores = {
            "Needs": 0.01,
            "Exchange": 0.005,
            "Challenge": 0.005,
            "Belonging": 0.30,
            "Relation": 0.35,
            "Change": 0.20,
            "Meaning": 0.10,
            "Role": 0.02,
            "Collective": 0.015,
        }
    else:  # HYBRID
        anchor_scores = {
            "Needs": 0.15,
            "Exchange": 0.15,
            "Challenge": 0.10,
            "Belonging": 0.15,
            "Relation": 0.15,
            "Change": 0.10,
            "Meaning": 0.10,
            "Role": 0.05,
            "Collective": 0.05,
        }

    # Create new context with modified aspect_probs and anchor_scores
    return RouterContext(
        aspect_probs=aspect_probs,
        H_D=ctx.H_D,
        H_G=ctx.H_G,
        H_K=ctx.H_K,
        anchor_scores=anchor_scores,
        domain=ctx.domain,
        risk_level=ctx.risk_level,
        long_arc_tension=ctx.long_arc_tension,
    )


# =============================================================================
# PARAMETRIZED GRID TESTS
# =============================================================================

@pytest.mark.parametrize("domain", ["generic", "task", "therapy", "identity", "spiritual"])
@pytest.mark.parametrize("entropy", [0.0, 0.39, 0.41, 0.49, 0.51, 0.59, 0.61, 1.0])
@pytest.mark.parametrize("tension", [0.0, 0.49, 0.51, 1.0])
@pytest.mark.parametrize("bias", ["lower", "upper", "neutral"])
def test_mapper_activation_grid(
    domain: str,
    entropy: float,
    tension: float,
    bias: str,
):
    """
    Grid test: Verify mapper activation across all parameter combinations.

    This test ensures that TTOR routing behavior matches the canonical formulas
    for every combination of domain, entropy, tension, and tier bias.

    Instead of forcing a specific tier (which may be contradictory with entropy),
    we bias the inputs towards a tier and then verify the canonical rules
    for whatever tier TTOR actually chooses.
    """
    # Create router context with the given bias
    ctx = create_router_context_for_entropy(
        target_entropy=entropy,
        domain=domain,
        long_arc_tension=tension,
    )

    # Apply tier bias (but don't force tier - let TTOR decide)
    if bias == "lower":
        # Bias towards LOWER tier (but high entropy might still result in HYBRID/UPPER)
        ctx = override_tier_in_context(ctx, Tier.LOWER)
    elif bias == "upper":
        # Bias towards UPPER tier (but low entropy might still result in HYBRID/LOWER)
        ctx = override_tier_in_context(ctx, Tier.UPPER)
    # else neutral: use balanced probabilities (likely HYBRID)

    # Route using TTOR - let it choose the actual tier
    router = TTORRouter()
    plan = router.route(ctx)

    # Compute expected flags using canonical formulas based on ACTUAL tier
    expected = expected_mappers(
        tier=plan.tier,  # Use the tier that TTOR actually chose
        domain=domain,
        normalized_entropy=plan.normalized_entropy,
        long_arc_tension=tension,
    )

    # Assert exact match
    assert plan.use_hrm == expected["use_hrm"], (
        f"HRM mismatch: tier={plan.tier.value}, domain={domain}, "
        f"entropy={plan.normalized_entropy:.3f}, tension={tension:.3f} | "
        f"Expected: {expected['use_hrm']}, Got: {plan.use_hrm}"
    )

    assert plan.use_lcm == expected["use_lcm"], (
        f"LCM mismatch: tier={plan.tier.value}, domain={domain}, "
        f"entropy={plan.normalized_entropy:.3f}, tension={tension:.3f} | "
        f"Expected: {expected['use_lcm']}, Got: {plan.use_lcm}"
    )

    assert plan.use_lam == expected["use_lam"], (
        f"LAM mismatch: tier={plan.tier.value}, domain={domain}, "
        f"entropy={plan.normalized_entropy:.3f}, tension={tension:.3f} | "
        f"Expected: {expected['use_lam']}, Got: {plan.use_lam}"
    )


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

def test_edge_case_lower_tier_entropy_threshold():
    """
    LOWER tier with entropy exactly at LCM threshold boundary.

    Expected:
    - entropy 0.49 → no LCM
    - entropy 0.51 → use_lcm = True
    """
    router = TTORRouter()

    # Test entropy = 0.49 (below threshold)
    ctx_below = create_router_context_for_entropy(0.49, domain="generic", long_arc_tension=0.0)
    ctx_below = override_tier_in_context(ctx_below, Tier.LOWER)
    plan_below = router.route(ctx_below)

    assert plan_below.tier == Tier.LOWER
    assert not plan_below.use_lcm, f"LCM should be False at entropy={plan_below.normalized_entropy:.3f} (below 0.50)"
    assert not plan_below.use_hrm, "HRM should be False for LOWER tier"

    # Test entropy = 0.51 (above threshold)
    ctx_above = create_router_context_for_entropy(0.51, domain="generic", long_arc_tension=0.0)
    ctx_above = override_tier_in_context(ctx_above, Tier.LOWER)
    plan_above = router.route(ctx_above)

    assert plan_above.tier == Tier.LOWER
    assert plan_above.use_lcm, f"LCM should be True at entropy={plan_above.normalized_entropy:.3f} (above 0.50)"
    assert not plan_above.use_hrm, "HRM should be False for LOWER tier"


def test_edge_case_upper_tier_entropy_threshold():
    """
    Non-LOWER tier with entropy exactly at HRM threshold boundary.

    Expected:
    - tier != LOWER, entropy 0.39 → no HRM
    - tier != LOWER, entropy 0.41 → use_hrm = True
    """
    router = TTORRouter()

    # Test entropy = 0.39 (below threshold)
    ctx_below = create_router_context_for_entropy(0.39, domain="generic", long_arc_tension=0.0)
    ctx_below = override_tier_in_context(ctx_below, Tier.UPPER)
    plan_below = router.route(ctx_below)

    # Tier might be UPPER or HYBRID, both are acceptable for this test
    assert plan_below.tier in [Tier.UPPER, Tier.HYBRID], f"Expected UPPER or HYBRID, got {plan_below.tier.value}"
    assert not plan_below.use_hrm, f"HRM should be False at entropy={plan_below.normalized_entropy:.3f} (below 0.40)"

    # Test entropy = 0.41 (above threshold)
    ctx_above = create_router_context_for_entropy(0.41, domain="generic", long_arc_tension=0.0)
    ctx_above = override_tier_in_context(ctx_above, Tier.UPPER)
    plan_above = router.route(ctx_above)

    # Tier might be UPPER or HYBRID, both are acceptable for this test
    assert plan_above.tier in [Tier.UPPER, Tier.HYBRID], f"Expected UPPER or HYBRID, got {plan_above.tier.value}"
    assert plan_above.use_hrm, f"HRM should be True at entropy={plan_above.normalized_entropy:.3f} (above 0.40)"


def test_edge_case_therapy_domain_entropy_threshold():
    """
    Therapy domain with entropy at LAM domain threshold.

    Expected:
    - therapy domain, entropy 0.61, tension=0.0 → use_lam = True
    - generic domain, entropy 0.61, tension=0.0 → use_lam = False
    """
    router = TTORRouter()

    # Test therapy domain (should activate LAM via domain rule)
    ctx_therapy = create_router_context_for_entropy(0.61, domain="therapy", long_arc_tension=0.0)
    ctx_therapy = override_tier_in_context(ctx_therapy, Tier.UPPER)
    plan_therapy = router.route(ctx_therapy)

    assert plan_therapy.use_lam, (
        f"LAM should be True for therapy domain at entropy={plan_therapy.normalized_entropy:.3f} "
        f"(above 0.60, tension={plan_therapy.long_arc_tension:.3f})"
    )

    # Test generic domain (should NOT activate LAM)
    ctx_generic = create_router_context_for_entropy(0.61, domain="generic", long_arc_tension=0.0)
    ctx_generic = override_tier_in_context(ctx_generic, Tier.UPPER)
    plan_generic = router.route(ctx_generic)

    assert not plan_generic.use_lam, (
        f"LAM should be False for generic domain at entropy={plan_generic.normalized_entropy:.3f}, "
        f"tension={plan_generic.long_arc_tension:.3f} (no trigger)"
    )


def test_edge_case_tension_threshold():
    """
    Long-arc tension at LAM threshold boundary.

    Expected:
    - any domain, tension 0.51 → use_lam = True
    - any domain, tension 0.49 → use_lam = False (unless domain rule applies)
    """
    router = TTORRouter()

    # Test tension = 0.51 (above threshold)
    ctx_high = create_router_context_for_entropy(0.3, domain="generic", long_arc_tension=0.51)
    ctx_high = override_tier_in_context(ctx_high, Tier.UPPER)
    plan_high = router.route(ctx_high)

    assert plan_high.use_lam, (
        f"LAM should be True at tension={plan_high.long_arc_tension:.3f} (above 0.50)"
    )

    # Test tension = 0.49 (below threshold)
    ctx_low = create_router_context_for_entropy(0.3, domain="generic", long_arc_tension=0.49)
    ctx_low = override_tier_in_context(ctx_low, Tier.UPPER)
    plan_low = router.route(ctx_low)

    assert not plan_low.use_lam, (
        f"LAM should be False at tension={plan_low.long_arc_tension:.3f} (below 0.50), "
        f"entropy={plan_low.normalized_entropy:.3f} (below 0.60), domain=generic"
    )


def test_edge_case_no_mapper_activation():
    """
    Test scenario where NO mapper should be active.

    Expected:
    - LOWER tier, low entropy, no tension → all mappers False
    """
    router = TTORRouter()

    ctx = create_router_context_for_entropy(0.3, domain="generic", long_arc_tension=0.0)
    ctx = override_tier_in_context(ctx, Tier.LOWER)
    plan = router.route(ctx)

    assert plan.tier == Tier.LOWER
    assert not plan.use_hrm, "HRM should be False (LOWER tier)"
    assert not plan.use_lcm, f"LCM should be False (entropy={plan.normalized_entropy:.3f} < 0.50)"
    assert not plan.use_lam, f"LAM should be False (tension={plan.long_arc_tension:.3f} < 0.50, no domain trigger)"


def test_edge_case_all_mappers_active():
    """
    Test scenario where multiple mappers could be active.

    Expected:
    - UPPER tier, high entropy, high tension, deep domain → HRM + LAM
    """
    router = TTORRouter()

    ctx = create_router_context_for_entropy(0.9, domain="therapy", long_arc_tension=0.9)
    ctx = override_tier_in_context(ctx, Tier.UPPER)
    plan = router.route(ctx)

    assert plan.tier == Tier.UPPER
    assert plan.use_hrm, f"HRM should be True (UPPER tier, entropy={plan.normalized_entropy:.3f} > 0.40)"
    assert not plan.use_lcm, "LCM should be False (not LOWER tier)"
    assert plan.use_lam, (
        f"LAM should be True (tension={plan.long_arc_tension:.3f} > 0.50 OR "
        f"domain=therapy with entropy={plan.normalized_entropy:.3f} > 0.60)"
    )


# =============================================================================
# DRIFT DETECTION SUMMARY
# =============================================================================

def test_generate_drift_report(tmp_path):
    """
    Generate a JSON drift report for dashboard consumption.

    This test runs a subset of critical cases and outputs a report file
    that the drift dashboard can analyze.
    """
    import json

    router = TTORRouter()
    test_cases = []

    # Define critical test cases
    cases = [
        (Tier.LOWER, "generic", 0.49, 0.0),
        (Tier.LOWER, "generic", 0.51, 0.0),
        (Tier.UPPER, "generic", 0.39, 0.0),
        (Tier.UPPER, "generic", 0.41, 0.0),
        (Tier.UPPER, "therapy", 0.61, 0.0),
        (Tier.UPPER, "generic", 0.61, 0.0),
        (Tier.UPPER, "generic", 0.3, 0.51),
        (Tier.UPPER, "generic", 0.3, 0.49),
        (Tier.LOWER, "task", 0.55, 0.0),
        (Tier.UPPER, "therapy", 0.9, 0.9),
    ]

    for tier, domain, target_entropy, tension in cases:
        ctx = create_router_context_for_entropy(target_entropy, domain, tension)
        ctx = override_tier_in_context(ctx, tier)
        plan = router.route(ctx)

        expected = expected_mappers(tier, domain, plan.normalized_entropy, tension)

        drift_detected = (
            plan.use_hrm != expected["use_hrm"]
            or plan.use_lcm != expected["use_lcm"]
            or plan.use_lam != expected["use_lam"]
        )

        test_cases.append({
            "tier": tier.value,
            "domain": domain,
            "target_entropy": target_entropy,
            "actual_entropy": round(plan.normalized_entropy, 3),
            "tension": tension,
            "expected_hrm": expected["use_hrm"],
            "actual_hrm": plan.use_hrm,
            "expected_lcm": expected["use_lcm"],
            "actual_lcm": plan.use_lcm,
            "expected_lam": expected["use_lam"],
            "actual_lam": plan.use_lam,
            "drift_detected": drift_detected,
        })

    report = {
        "test_suite": "mapper_activation_regions",
        "version": "v2.0",
        "total_cases": len(test_cases),
        "drift_cases": sum(1 for tc in test_cases if tc["drift_detected"]),
        "test_cases": test_cases,
    }

    # Write to core/drift_tests directory (sibling to this test file)
    output_path = tmp_path.parent / "mapper_activation_report.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    # Also write to fixed location for dashboard
    fixed_path = "/home/user/symbolu/symbolu/core/drift_tests/mapper_activation_report.json"
    with open(fixed_path, "w") as f:
        json.dump(report, f, indent=2)

    # Assert no drift
    assert report["drift_cases"] == 0, f"Drift detected in {report['drift_cases']} cases!"
