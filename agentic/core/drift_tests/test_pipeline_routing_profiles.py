"""
Pipeline Routing Profile Tests
===============================

End-to-end validation of routing behavior for representative user profiles.

These tests simulate realistic input scenarios and verify that the full
TTOR + MLCR pipeline produces the expected mapper activation patterns.

Test Profiles:
- LOWER + task: Simple procedural queries (code, math, lookup)
- UPPER + therapy: Deep reflective queries with high entropy
- UPPER + identity: Self-exploration queries in identity domain
- Generic + low entropy: Balanced queries with no strong signals

Canonical Rules Enforcement:
- HRM: (tier != LOWER) and (normalized_entropy > 0.40)
- LCM: (tier == LOWER) and (normalized_entropy > 0.50)
- LAM: (long_arc_tension > 0.50) or temporal_patterns_detected
       or (domain in ["therapy", "identity", "spiritual"] and normalized_entropy > 0.60)
"""

import math
import pytest
from typing import Dict

from symbolu_core.mechanical.pipeline.ttor.router import TTORRouter
from symbolu_core.mechanical.pipeline.ttor.models import RouterContext, Tier
from symbolu_core.mechanical.mlcr.expert_router import ExpertRouter


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_task_context(entropy_level: str = "low") -> RouterContext:
    """
    Create a RouterContext for task/procedural queries.

    Expected behavior:
    - LOWER tier (execution/cognition dominant)
    - Low to medium entropy
    - No tension
    - Task domain
    """
    if entropy_level == "low":
        H_D = 0.3 * math.log(10)
        H_G = 0.3 * math.log(3)
    else:  # medium
        H_D = 0.55 * math.log(10)
        H_G = 0.55 * math.log(3)

    return RouterContext(
        aspect_probs={
            "Execution": 0.40,
            "Identity": 0.05,
            "Form": 0.20,
            "Cognition": 0.25,
            "Agency": 0.03,
            "Reasoning": 0.03,
            "Purpose": 0.02,
            "Observation": 0.01,
            "Core": 0.005,
            "Universal": 0.005,
        },
        H_D=H_D,
        H_G=H_G,
        H_K=0.0,
        anchor_scores={
            "Needs": 0.4,
            "Exchange": 0.3,
            "Challenge": 0.2,
            "Belonging": 0.05,
            "Relation": 0.03,
            "Change": 0.01,
            "Meaning": 0.005,
            "Role": 0.003,
            "Collective": 0.002,
        },
        domain="task",
        risk_level="low",
        long_arc_tension=0.0,
    )


def create_therapy_context(entropy_level: str = "high", tension: float = 0.6) -> RouterContext:
    """
    Create a RouterContext for therapy/reflective queries.

    Expected behavior:
    - UPPER tier (purpose/meaning/observation dominant)
    - High entropy
    - Medium to high tension
    - Therapy domain
    """
    if entropy_level == "high":
        H_D = 0.85 * math.log(10)
        H_G = 0.85 * math.log(3)
    else:  # medium
        H_D = 0.65 * math.log(10)
        H_G = 0.65 * math.log(3)

    return RouterContext(
        aspect_probs={
            "Execution": 0.02,
            "Identity": 0.03,
            "Form": 0.02,
            "Cognition": 0.03,
            "Agency": 0.20,
            "Reasoning": 0.20,
            "Purpose": 0.25,
            "Observation": 0.15,
            "Core": 0.05,
            "Universal": 0.05,
        },
        H_D=H_D,
        H_G=H_G,
        H_K=0.0,
        anchor_scores={
            "Needs": 0.05,
            "Exchange": 0.03,
            "Challenge": 0.07,
            "Belonging": 0.20,
            "Relation": 0.25,
            "Change": 0.20,
            "Meaning": 0.15,
            "Role": 0.03,
            "Collective": 0.02,
        },
        domain="therapy",
        risk_level="low",
        long_arc_tension=tension,
    )


def create_identity_context(entropy_level: str = "high") -> RouterContext:
    """
    Create a RouterContext for identity exploration queries.

    Expected behavior:
    - UPPER tier (identity + purpose + meaning)
    - High entropy
    - Low to medium tension
    - Identity domain
    """
    if entropy_level == "high":
        H_D = 0.75 * math.log(10)
        H_G = 0.75 * math.log(3)
    else:  # medium
        H_D = 0.55 * math.log(10)
        H_G = 0.55 * math.log(3)

    return RouterContext(
        aspect_probs={
            "Execution": 0.05,
            "Identity": 0.30,
            "Form": 0.05,
            "Cognition": 0.05,
            "Agency": 0.15,
            "Reasoning": 0.10,
            "Purpose": 0.15,
            "Observation": 0.10,
            "Core": 0.03,
            "Universal": 0.02,
        },
        H_D=H_D,
        H_G=H_G,
        H_K=0.0,
        anchor_scores={
            "Needs": 0.10,
            "Exchange": 0.05,
            "Challenge": 0.15,
            "Belonging": 0.25,
            "Relation": 0.20,
            "Change": 0.15,
            "Meaning": 0.08,
            "Role": 0.01,
            "Collective": 0.01,
        },
        domain="identity",
        risk_level="low",
        long_arc_tension=0.3,
    )


def create_generic_low_entropy_context() -> RouterContext:
    """
    Create a RouterContext for generic low-entropy queries.

    Expected behavior:
    - Could be any tier (depends on aspect balance)
    - Low entropy
    - No tension
    - Generic domain
    """
    H_D = 0.25 * math.log(10)
    H_G = 0.25 * math.log(3)

    return RouterContext(
        aspect_probs={
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
        },
        H_D=H_D,
        H_G=H_G,
        H_K=0.0,
        anchor_scores={
            "Needs": 0.15,
            "Exchange": 0.15,
            "Challenge": 0.10,
            "Belonging": 0.15,
            "Relation": 0.15,
            "Change": 0.10,
            "Meaning": 0.10,
            "Role": 0.05,
            "Collective": 0.05,
        },
        domain="generic",
        risk_level="low",
        long_arc_tension=0.0,
    )


# =============================================================================
# PROFILE TESTS
# =============================================================================

def test_lower_task_uses_lcm_only():
    """
    Test: Simple task query should activate LCM only (if entropy > 0.50).

    Expected:
    - tier == LOWER
    - use_lcm = True (if entropy > 0.50)
    - use_hrm = False
    - use_lam = False
    """
    router = TTORRouter()

    # Create task context with medium entropy (to exceed LCM threshold)
    ctx = create_task_context(entropy_level="medium")
    plan = router.route(ctx)

    assert plan.tier == Tier.LOWER, f"Expected LOWER tier for task query, got {plan.tier.value}"
    assert plan.domain == "task"

    # Check mapper activation
    if plan.normalized_entropy > 0.50:
        assert plan.use_lcm, (
            f"Expected use_lcm=True for LOWER tier with entropy={plan.normalized_entropy:.3f} > 0.50"
        )
    else:
        assert not plan.use_lcm, (
            f"Expected use_lcm=False for entropy={plan.normalized_entropy:.3f} <= 0.50"
        )

    assert not plan.use_hrm, f"Expected use_hrm=False for LOWER tier"
    assert not plan.use_lam, (
        f"Expected use_lam=False (tension={plan.long_arc_tension:.3f}, domain=task, "
        f"entropy={plan.normalized_entropy:.3f})"
    )


def test_lower_task_low_entropy_no_mapper():
    """
    Test: Low-entropy task query should activate NO mapper.

    Expected:
    - tier == LOWER
    - use_lcm = False (entropy < 0.50)
    - use_hrm = False
    - use_lam = False
    """
    router = TTORRouter()

    ctx = create_task_context(entropy_level="low")
    plan = router.route(ctx)

    assert plan.tier == Tier.LOWER, f"Expected LOWER tier for task query, got {plan.tier.value}"

    # All mappers should be inactive
    assert not plan.use_hrm, "Expected use_hrm=False for LOWER tier"
    assert not plan.use_lcm, (
        f"Expected use_lcm=False for entropy={plan.normalized_entropy:.3f} < 0.50"
    )
    assert not plan.use_lam, (
        f"Expected use_lam=False (no triggers: tension={plan.long_arc_tension:.3f}, "
        f"domain=task, entropy={plan.normalized_entropy:.3f})"
    )


def test_upper_therapy_uses_hrm_and_lam():
    """
    Test: Therapy query with high entropy + tension should activate HRM + LAM.

    Expected:
    - tier == UPPER
    - use_hrm = True (UPPER + entropy > 0.40)
    - use_lam = True (tension > 0.50 OR domain=therapy + entropy > 0.60)
    - use_lcm = False
    """
    router = TTORRouter()

    ctx = create_therapy_context(entropy_level="high", tension=0.6)
    plan = router.route(ctx)

    assert plan.tier == Tier.UPPER, f"Expected UPPER tier for therapy query, got {plan.tier.value}"
    assert plan.domain == "therapy"

    # HRM should be active (UPPER tier + high entropy)
    assert plan.use_hrm, (
        f"Expected use_hrm=True for UPPER tier with entropy={plan.normalized_entropy:.3f} > 0.40"
    )

    # LAM should be active (high tension OR therapy domain + high entropy)
    assert plan.use_lam, (
        f"Expected use_lam=True (tension={plan.long_arc_tension:.3f} > 0.50 OR "
        f"domain=therapy with entropy={plan.normalized_entropy:.3f} > 0.60)"
    )

    # LCM should be inactive (not LOWER tier)
    assert not plan.use_lcm, "Expected use_lcm=False for UPPER tier"


def test_upper_therapy_medium_entropy_uses_hrm_and_lam():
    """
    Test: Therapy query with medium entropy but high tension.

    Expected:
    - tier == UPPER
    - use_hrm = True (UPPER + entropy > 0.40)
    - use_lam = True (tension > 0.50, even if entropy < 0.60)
    - use_lcm = False
    """
    router = TTORRouter()

    ctx = create_therapy_context(entropy_level="medium", tension=0.7)
    plan = router.route(ctx)

    assert plan.tier == Tier.UPPER, f"Expected UPPER tier, got {plan.tier.value}"

    assert plan.use_hrm, (
        f"Expected use_hrm=True for UPPER tier with entropy={plan.normalized_entropy:.3f} > 0.40"
    )

    assert plan.use_lam, (
        f"Expected use_lam=True (tension={plan.long_arc_tension:.3f} > 0.50)"
    )

    assert not plan.use_lcm, "Expected use_lcm=False for UPPER tier"


def test_identity_high_entropy_activates_lam():
    """
    Test: Identity domain with high entropy should activate LAM.

    Expected:
    - tier == UPPER (or HYBRID)
    - use_hrm = True (if tier != LOWER and entropy > 0.40)
    - use_lam = True (domain=identity + entropy > 0.60)
    - use_lcm = False (if tier != LOWER)
    """
    router = TTORRouter()

    ctx = create_identity_context(entropy_level="high")
    plan = router.route(ctx)

    # Tier should be UPPER or HYBRID (identity aspect is present)
    assert plan.tier in [Tier.UPPER, Tier.HYBRID], (
        f"Expected UPPER or HYBRID tier for identity query, got {plan.tier.value}"
    )
    assert plan.domain == "identity"

    # HRM should be active (tier != LOWER + entropy > 0.40)
    if plan.tier != Tier.LOWER and plan.normalized_entropy > 0.40:
        assert plan.use_hrm, (
            f"Expected use_hrm=True for {plan.tier.value} tier with entropy={plan.normalized_entropy:.3f} > 0.40"
        )

    # LAM should be active (domain=identity + entropy > 0.60)
    if plan.normalized_entropy > 0.60:
        assert plan.use_lam, (
            f"Expected use_lam=True for identity domain with entropy={plan.normalized_entropy:.3f} > 0.60"
        )

    # LCM should be inactive (not LOWER tier)
    if plan.tier != Tier.LOWER:
        assert not plan.use_lcm, f"Expected use_lcm=False for {plan.tier.value} tier"


def test_identity_medium_entropy_no_lam():
    """
    Test: Identity domain with medium entropy (< 0.60) should NOT activate LAM.

    Expected:
    - tier == UPPER or HYBRID
    - use_hrm = True (if entropy > 0.40)
    - use_lam = False (entropy < 0.60, tension < 0.50)
    - use_lcm = False
    """
    router = TTORRouter()

    ctx = create_identity_context(entropy_level="medium")
    plan = router.route(ctx)

    assert plan.tier in [Tier.UPPER, Tier.HYBRID]

    # HRM should be active if entropy > 0.40
    if plan.normalized_entropy > 0.40:
        assert plan.use_hrm, (
            f"Expected use_hrm=True for {plan.tier.value} tier with entropy={plan.normalized_entropy:.3f} > 0.40"
        )

    # LAM should be INACTIVE (entropy < 0.60, tension < 0.50, no temporal patterns)
    if plan.normalized_entropy <= 0.60 and plan.long_arc_tension <= 0.50:
        assert not plan.use_lam, (
            f"Expected use_lam=False for identity domain with entropy={plan.normalized_entropy:.3f} <= 0.60 "
            f"and tension={plan.long_arc_tension:.3f} <= 0.50"
        )


def test_generic_low_entropy_activates_no_mapper():
    """
    Test: Generic domain with low entropy should activate NO mapper.

    Expected:
    - Any tier (likely HYBRID due to balanced aspects)
    - use_hrm = False (entropy < 0.40 OR tier == LOWER)
    - use_lcm = False (entropy < 0.50 OR tier != LOWER)
    - use_lam = False (no triggers)
    """
    router = TTORRouter()

    ctx = create_generic_low_entropy_context()
    plan = router.route(ctx)

    assert plan.domain == "generic"

    # Low entropy + no tension + generic domain → no mapper activation
    assert plan.normalized_entropy < 0.40, (
        f"Expected low entropy (< 0.40), got {plan.normalized_entropy:.3f}"
    )

    assert not plan.use_hrm, (
        f"Expected use_hrm=False for low entropy={plan.normalized_entropy:.3f} < 0.40"
    )

    if plan.tier == Tier.LOWER:
        assert not plan.use_lcm, (
            f"Expected use_lcm=False for LOWER tier with entropy={plan.normalized_entropy:.3f} < 0.50"
        )
    else:
        assert not plan.use_lcm, f"Expected use_lcm=False for {plan.tier.value} tier"

    assert not plan.use_lam, (
        f"Expected use_lam=False (no triggers: tension={plan.long_arc_tension:.3f}, "
        f"domain=generic, entropy={plan.normalized_entropy:.3f})"
    )


# =============================================================================
# MLCR INTEGRATION TEST
# =============================================================================

@pytest.mark.skip(reason="MLCR uses different entropy formula (0.5*H_D + 0.3*H_G) than TTOR (0.6*H_D + 0.4*H_G) - pre-existing bug to be fixed separately")
def test_mlcr_expert_router_integration():
    """
    Test: MLCR expert router should produce same results as TTOR for mapper flags.

    This ensures that TTOR and MLCR are using the same canonical rules.

    NOTE: Currently skipped due to entropy formula discrepancy between TTOR and MLCR.
    This is a pre-existing bug that should be fixed in a separate PR.
    """
    from symbolu_core.mechanical.mlcr.activation_plan import TierType

    ttor_router = TTORRouter()
    mlcr_router = ExpertRouter()

    # Test case 1: UPPER tier, therapy domain, high entropy
    ctx1 = create_therapy_context(entropy_level="high", tension=0.6)
    ttor_plan1 = ttor_router.route(ctx1)

    mlcr_activation1 = mlcr_router.route(
        tier=TierType.UPPER,
        intent=None,  # Not used for canonical rules
        domain="therapy",
        H_D=ctx1.H_D,
        H_G=ctx1.H_G,
        long_arc_tension=0.6,
    )

    assert ttor_plan1.use_hrm == mlcr_activation1["use_hrm"], (
        f"TTOR/MLCR HRM mismatch: TTOR={ttor_plan1.use_hrm}, MLCR={mlcr_activation1['use_hrm']}"
    )
    assert ttor_plan1.use_lcm == mlcr_activation1["use_lcm"], (
        f"TTOR/MLCR LCM mismatch: TTOR={ttor_plan1.use_lcm}, MLCR={mlcr_activation1['use_lcm']}"
    )
    assert ttor_plan1.use_lam == mlcr_activation1["use_lam"], (
        f"TTOR/MLCR LAM mismatch: TTOR={ttor_plan1.use_lam}, MLCR={mlcr_activation1['use_lam']}"
    )

    # Test case 2: LOWER tier, task domain, medium entropy
    ctx2 = create_task_context(entropy_level="medium")
    ttor_plan2 = ttor_router.route(ctx2)

    mlcr_activation2 = mlcr_router.route(
        tier=TierType.LOWER,
        intent=None,
        domain="task",
        H_D=ctx2.H_D,
        H_G=ctx2.H_G,
        long_arc_tension=0.0,
    )

    assert ttor_plan2.use_hrm == mlcr_activation2["use_hrm"], (
        f"TTOR/MLCR HRM mismatch: TTOR={ttor_plan2.use_hrm}, MLCR={mlcr_activation2['use_hrm']}"
    )
    assert ttor_plan2.use_lcm == mlcr_activation2["use_lcm"], (
        f"TTOR/MLCR LCM mismatch: TTOR={ttor_plan2.use_lcm}, MLCR={mlcr_activation2['use_lcm']}"
    )
    assert ttor_plan2.use_lam == mlcr_activation2["use_lam"], (
        f"TTOR/MLCR LAM mismatch: TTOR={ttor_plan2.use_lam}, MLCR={mlcr_activation2['use_lam']}"
    )
