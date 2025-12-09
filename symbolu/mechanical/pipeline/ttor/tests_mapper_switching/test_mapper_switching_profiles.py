"""
TTOR Mapper Switching Profile Tests

Verifies that TTOR activates HRM/LCM/LAM in expected, deterministic scenarios.
This test suite serves as a guardrail against routing drift when TTOR formulas change.

Test Profiles:
1. simple_task_low_entropy - Task-oriented, low complexity
2. deep_therapy_high_entropy - Reflective, high uncertainty
3. long_arc_high_tension - Identity arc with sustained tension
4. generic_low_complexity_chat - Balanced, low-stakes conversation

Each profile has a fixed expected routing outcome that must not change
without explicit review and baseline update.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict

import pytest

from symbolu.mechanical.pipeline.ttor.router import TTORRouter
from symbolu.mechanical.pipeline.ttor.models import RouterContext
from symbolu.mechanical.pipeline.ttor.constants import H_D_MAX, H_G_MAX

# Path configuration
BASE_DIR = Path(__file__).parent.parent
BASELINE_PATH = BASE_DIR / "snapshots" / "mapper_switching_baseline.json"
REPORT_PATH = Path(__file__).parent / "mapper_switching_report.json"


def build_router_context(profile: str) -> RouterContext:
    """
    Build deterministic RouterContext instances for canonical routing profiles.

    Each profile is designed to trigger specific routing behavior:
    - simple_task_low_entropy: Lower tier, OUTER_ONLY flow, all mappers off
    - deep_therapy_high_entropy: Upper tier, INNER_PRIORITY flow, all mappers on
    - long_arc_high_tension: Upper tier with high tension, LAM active
    - generic_low_complexity_chat: Lower tier, OUTER_ONLY flow, all mappers off

    Args:
        profile: Profile identifier string

    Returns:
        RouterContext configured for the specified profile

    Raises:
        ValueError: If profile is not recognized
    """
    if profile == "simple_task_low_entropy":
        # Heavy lower-tier aspects (Execution, Cognition), low entropy, task domain
        # Expected: tier=lower, flow=outer_only, all mappers off
        aspect_probs = {
            "Execution": 0.7,
            "Cognition": 0.5,
            "Identity": 0.3,
            "Form": 0.2,
            # Minimal upper-tier presence
            "Agency": 0.05,
            "Reasoning": 0.05,
            "Purpose": 0.05,
            "Observation": 0.05,
        }
        # Strong lower anchors, weak upper anchors (low conflict)
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
        # Low entropy values
        H_D = H_D_MAX * 0.15  # ~15% of max
        H_G = H_G_MAX * 0.10  # ~10% of max
        domain = "task"
        risk_level = "low"
        long_arc_tension = 0.1

    elif profile == "deep_therapy_high_entropy":
        # Heavy upper-tier aspects (Purpose, Observation, Universal), high entropy
        # Expected: tier=upper, flow=inner_priority, HRM/LCM/LAM all on
        aspect_probs = {
            "Purpose": 0.7,
            "Observation": 0.6,
            "Universal": 0.5,
            "Core": 0.4,
            "Agency": 0.3,
            "Reasoning": 0.3,
            # Minimal lower-tier presence
            "Execution": 0.05,
            "Cognition": 0.05,
            "Identity": 0.1,
            "Form": 0.05,
        }
        # Strong upper anchors
        anchor_scores = {
            "Meaning": 0.9,
            "Role": 0.8,
            "Collective": 0.7,
            "Belonging": 0.6,
            "Relation": 0.5,
            "Change": 0.5,
            # Weak lower anchors
            "Needs": 0.1,
            "Exchange": 0.1,
            "Challenge": 0.1,
        }
        # High entropy values (normalized_entropy > 0.6)
        H_D = H_D_MAX * 0.85  # ~85% of max
        H_G = H_G_MAX * 0.80  # ~80% of max
        domain = "therapy"
        risk_level = "medium"
        long_arc_tension = 0.4

    elif profile == "long_arc_high_tension":
        # Identity arc with high tension, triggering LAM
        # Mixed aspects but upper-tier dominant due to reflective domain
        # Expected: tier=upper, LAM=True, potentially HRM/LCM based on flow
        aspect_probs = {
            "Identity": 0.4,
            "Purpose": 0.5,
            "Observation": 0.4,
            "Agency": 0.3,
            "Core": 0.3,
            # Some lower-tier presence
            "Execution": 0.1,
            "Cognition": 0.2,
            "Form": 0.1,
        }
        # Moderate anchor scores with upper-tier bias
        anchor_scores = {
            "Meaning": 0.7,
            "Role": 0.6,
            "Belonging": 0.5,
            "Relation": 0.4,
            "Change": 0.4,
            "Collective": 0.3,
            # Some lower anchors
            "Needs": 0.2,
            "Exchange": 0.2,
            "Challenge": 0.2,
        }
        # Moderate-to-high entropy
        H_D = H_D_MAX * 0.70  # ~70% of max
        H_G = H_G_MAX * 0.65  # ~65% of max
        domain = "identity"
        risk_level = "medium"
        # High tension - key signal for LAM
        long_arc_tension = 0.9

    elif profile == "generic_low_complexity_chat":
        # Balanced aspects with clear lower-tier bias, low entropy
        # Expected: tier=lower, flow=outer_only, all mappers off
        # Key: upper anchor scores must be low enough to keep conflict < 0.5
        aspect_probs = {
            "Execution": 0.5,
            "Cognition": 0.4,
            "Identity": 0.3,
            "Form": 0.3,
            # Minimal upper-tier presence
            "Agency": 0.1,
            "Reasoning": 0.1,
            "Purpose": 0.1,
            "Observation": 0.1,
        }
        # Strong lower-tier anchor bias with very low upper anchors (conflict < 0.5)
        # conflict = 2 * min(lower, upper) / (lower + upper)
        # With lower=0.4, upper=0.05: conflict = 2*0.05/0.45 = 0.22 < 0.5
        anchor_scores = {
            "Needs": 0.5,
            "Exchange": 0.4,
            "Challenge": 0.3,
            # Very low upper anchors to minimize conflict
            "Belonging": 0.05,
            "Relation": 0.05,
            "Change": 0.05,
            "Meaning": 0.05,
            "Role": 0.05,
            "Collective": 0.05,
        }
        # Low entropy
        H_D = H_D_MAX * 0.20  # ~20% of max
        H_G = H_G_MAX * 0.20  # ~20% of max
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


# Expected routing outcomes for each profile
# These are the protected expectations - any change requires explicit review
EXPECTED_ROUTING: Dict[str, Dict[str, Any]] = {
    "simple_task_low_entropy": {
        "tier": "lower",
        "use_hrm": False,
        "use_lcm": False,
        "use_lam": False,
    },
    "deep_therapy_high_entropy": {
        "tier": "upper",
        "use_hrm": True,
        "use_lcm": True,
        "use_lam": True,
    },
    "long_arc_high_tension": {
        "tier": "upper",
        "use_hrm": True,
        "use_lcm": True,
        "use_lam": True,
    },
    "generic_low_complexity_chat": {
        "tier": "lower",
        "use_hrm": False,
        "use_lcm": False,
        "use_lam": False,
    },
}


def collect_routing_decisions() -> Dict[str, Dict[str, Any]]:
    """
    Execute TTOR routing for all canonical profiles and collect results.

    Returns:
        Dictionary mapping profile names to their routing decision dictionaries,
        including tier, flow_mode, engine_family, and mapper flags.
    """
    router = TTORRouter()
    results: Dict[str, Dict[str, Any]] = {}

    for profile in EXPECTED_ROUTING.keys():
        ctx = build_router_context(profile)
        plan = router.route(ctx)

        results[profile] = {
            "tier": plan.tier.value if hasattr(plan.tier, "value") else str(plan.tier),
            "flow_mode": plan.flow_mode.value if hasattr(plan.flow_mode, "value") else str(plan.flow_mode),
            "preferred_engine_family": plan.preferred_engine_family,
            "use_hrm": bool(plan.use_hrm),
            "use_lcm": bool(plan.use_lcm),
            "use_lam": bool(plan.use_lam),
            "regulated_mode": bool(plan.regulated_mode),
            "allow_metaphor": bool(plan.allow_metaphor),
        }

    return results


def test_mapper_switching_profiles_against_expectations() -> None:
    """
    Test that TTOR mapper switching matches expected outcomes for canonical profiles.

    This test verifies that:
    1. HRM/LCM/LAM flags match exactly for each profile
    2. Tier classification is correct
    3. Results are written to a human-readable report

    Failures indicate routing drift that requires explicit review.
    """
    routing_results = collect_routing_decisions()

    # Always write a human-readable report for CI artifact collection
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(routing_results, indent=2, sort_keys=True),
        encoding="utf-8"
    )

    # Compare against EXPECTED_ROUTING
    for profile, expected in EXPECTED_ROUTING.items():
        actual = routing_results[profile]

        # Assert mapper flags match exactly
        assert actual["use_hrm"] == expected["use_hrm"], (
            f"Profile '{profile}': use_hrm changed from "
            f"{expected['use_hrm']} to {actual['use_hrm']}"
        )
        assert actual["use_lcm"] == expected["use_lcm"], (
            f"Profile '{profile}': use_lcm changed from "
            f"{expected['use_lcm']} to {actual['use_lcm']}"
        )
        assert actual["use_lam"] == expected["use_lam"], (
            f"Profile '{profile}': use_lam changed from "
            f"{expected['use_lam']} to {actual['use_lam']}"
        )

        # Assert tier classification
        assert actual["tier"] == expected["tier"], (
            f"Profile '{profile}': tier changed from "
            f"{expected['tier']} to {actual['tier']}"
        )


def test_mapper_switching_against_baseline() -> None:
    """
    Test that TTOR mapper switching matches the stored baseline snapshot.

    This test provides additional regression protection:
    - If baseline doesn't exist, creates it and skips (first run)
    - If baseline exists, compares current results against it
    - Any deviation in mapper flags fails the test

    To update baseline after intentional changes:
    1. Delete the baseline file
    2. Run tests to regenerate
    3. Review changes and commit new baseline
    """
    routing_results = collect_routing_decisions()

    # Ensure snapshots directory exists
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not BASELINE_PATH.exists():
        # First run: create baseline and skip
        BASELINE_PATH.write_text(
            json.dumps(routing_results, indent=2, sort_keys=True),
            encoding="utf-8"
        )
        pytest.skip(
            "Baseline created at "
            f"{BASELINE_PATH}; rerun tests to enforce mapper switching stability."
        )

    # Load and compare against baseline
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    for profile in baseline.keys():
        if profile not in routing_results:
            pytest.fail(
                f"Profile '{profile}' exists in baseline but not in current results"
            )

        baseline_result = baseline[profile]
        actual_result = routing_results[profile]

        # Assert mapper flags match baseline
        assert actual_result["use_hrm"] == baseline_result["use_hrm"], (
            f"Profile '{profile}': use_hrm differs from baseline "
            f"(expected {baseline_result['use_hrm']}, got {actual_result['use_hrm']})"
        )
        assert actual_result["use_lcm"] == baseline_result["use_lcm"], (
            f"Profile '{profile}': use_lcm differs from baseline "
            f"(expected {baseline_result['use_lcm']}, got {actual_result['use_lcm']})"
        )
        assert actual_result["use_lam"] == baseline_result["use_lam"], (
            f"Profile '{profile}': use_lam differs from baseline "
            f"(expected {baseline_result['use_lam']}, got {actual_result['use_lam']})"
        )

    # Check for new profiles not in baseline
    for profile in routing_results.keys():
        if profile not in baseline:
            pytest.fail(
                f"Profile '{profile}' exists in current results but not in baseline. "
                "Delete baseline and regenerate to include new profiles."
            )


def test_profile_builder_coverage() -> None:
    """
    Verify that all expected profiles can be built without errors.

    This is a sanity check to ensure profile definitions are valid.
    """
    for profile in EXPECTED_ROUTING.keys():
        ctx = build_router_context(profile)
        assert ctx is not None, f"Failed to build context for profile: {profile}"
        assert ctx.domain is not None
        assert ctx.aspect_probs is not None
        assert len(ctx.aspect_probs) > 0


def test_unknown_profile_raises_error() -> None:
    """Verify that unknown profile names raise ValueError."""
    with pytest.raises(ValueError, match="Unknown profile"):
        build_router_context("nonexistent_profile")


class TestMapperFlagLogic:
    """
    Detailed tests for individual mapper flag activation logic.

    These tests verify the specific conditions under which each mapper
    is activated or deactivated.
    """

    def test_hrm_off_for_lower_tier_low_entropy(self) -> None:
        """HRM should be off for lower tier with low entropy and low conflict."""
        ctx = build_router_context("simple_task_low_entropy")
        router = TTORRouter()
        plan = router.route(ctx)

        assert plan.tier.value == "lower"
        assert plan.use_hrm is False, (
            "HRM should be off for lower tier with low entropy"
        )

    def test_hrm_on_for_high_entropy(self) -> None:
        """HRM should be on when entropy exceeds threshold."""
        ctx = build_router_context("deep_therapy_high_entropy")
        router = TTORRouter()
        plan = router.route(ctx)

        assert plan.use_hrm is True, (
            "HRM should be on when entropy is high"
        )

    def test_lcm_on_for_inner_priority_flow(self) -> None:
        """LCM should be on when flow mode is INNER_PRIORITY."""
        ctx = build_router_context("deep_therapy_high_entropy")
        router = TTORRouter()
        plan = router.route(ctx)

        assert plan.flow_mode.value == "inner_priority"
        assert plan.use_lcm is True, (
            "LCM should be on for INNER_PRIORITY flow mode"
        )

    def test_lcm_off_for_outer_only_flow(self) -> None:
        """LCM should be off when flow mode is OUTER_ONLY."""
        ctx = build_router_context("simple_task_low_entropy")
        router = TTORRouter()
        plan = router.route(ctx)

        assert plan.flow_mode.value == "outer_only"
        assert plan.use_lcm is False, (
            "LCM should be off for OUTER_ONLY flow mode"
        )

    def test_lam_on_for_high_tension(self) -> None:
        """LAM should be on when long_arc_tension exceeds threshold."""
        ctx = build_router_context("long_arc_high_tension")
        router = TTORRouter()
        plan = router.route(ctx)

        assert plan.use_lam is True, (
            "LAM should be on when long_arc_tension is high (> 0.5)"
        )

    def test_lam_off_for_low_tension_outer_only(self) -> None:
        """LAM should be off when tension is low and flow is OUTER_ONLY."""
        ctx = build_router_context("simple_task_low_entropy")
        router = TTORRouter()
        plan = router.route(ctx)

        assert plan.use_lam is False, (
            "LAM should be off when tension is low and flow is not INNER_PRIORITY"
        )


class TestRoutingStability:
    """
    Tests to verify routing stability and determinism.
    """

    def test_routing_is_deterministic(self) -> None:
        """Verify that routing produces identical results on repeated calls."""
        router = TTORRouter()

        for profile in EXPECTED_ROUTING.keys():
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

        for profile in EXPECTED_ROUTING.keys():
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
