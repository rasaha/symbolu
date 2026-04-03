"""
Temporal-LAM Integration Tests
===============================

Tests that TemporalBhavaTracker properly triggers LAM activation
via the detect_activation_window() method.

Test Scenarios:
1. Rising momentum → expect LAM=True even if entropy low
2. Falling momentum downward → LAM=True
3. No trend → LAM only via entropy/tension rules
4. Extreme tension + rising momentum → LAM=True
5. Tension corridor (2+ high SMI entries) → LAM=True

These tests validate the integration between:
- TemporalBhavaTracker.detect_activation_window()
- TTOR router's temporal_patterns_detected flag
- MLCR expert_router's LAM activation logic
"""

import math
import pytest
from typing import Dict, Any

from agentic.temporal.temporal_bhava_tracker import TemporalBhavaTracker
from symbolu_core.mechanical.pipeline.ttor.router import TTORRouter
from symbolu_core.mechanical.pipeline.ttor.models import RouterContext, Tier
from symbolu_core.mechanical.mlcr.expert_router import ExpertRouter
from symbolu_core.mechanical.mlcr.activation_plan import TierType, IntentType


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_tracker_with_rising_momentum() -> TemporalBhavaTracker:
    """
    Create a tracker with rising SMI values (upward momentum).

    SMI pattern: 0.3 → 0.4 → 0.5 → 0.6 → 0.7
    This should trigger LAM due to upward momentum and significant slope.
    """
    tracker = TemporalBhavaTracker(window_size=10)

    # Add entries with rising SMI
    smi_values = [0.3, 0.4, 0.5, 0.6, 0.7]
    for i, smi in enumerate(smi_values):
        tracker.add_analysis(
            text=f"Test message {i}",
            smi=smi,
            bhava_id=1,
            bhava_direction="upward",
            kosha_id=3,
            ontology_id=5,
            timestamp=float(i),
        )

    return tracker


def create_tracker_with_falling_momentum() -> TemporalBhavaTracker:
    """
    Create a tracker with falling SMI values (downward momentum).

    SMI pattern: 0.8 → 0.65 → 0.5 → 0.35 → 0.2
    This should trigger LAM due to downward momentum and significant slope.
    """
    tracker = TemporalBhavaTracker(window_size=10)

    # Add entries with falling SMI
    smi_values = [0.8, 0.65, 0.5, 0.35, 0.2]
    for i, smi in enumerate(smi_values):
        tracker.add_analysis(
            text=f"Test message {i}",
            smi=smi,
            bhava_id=1,
            bhava_direction="downward",
            kosha_id=3,
            ontology_id=5,
            timestamp=float(i),
        )

    return tracker


def create_tracker_with_no_trend() -> TemporalBhavaTracker:
    """
    Create a tracker with stable SMI values (no clear trend).

    SMI pattern: 0.5 → 0.52 → 0.48 → 0.51 → 0.49
    This should NOT trigger LAM via temporal patterns (slope too small).
    """
    tracker = TemporalBhavaTracker(window_size=10)

    # Add entries with stable SMI
    smi_values = [0.5, 0.52, 0.48, 0.51, 0.49]
    for i, smi in enumerate(smi_values):
        tracker.add_analysis(
            text=f"Test message {i}",
            smi=smi,
            bhava_id=1,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
            timestamp=float(i),
        )

    return tracker


def create_tracker_with_tension_corridor() -> TemporalBhavaTracker:
    """
    Create a tracker with a tension corridor (sustained high SMI).

    SMI pattern: 0.4 → 0.5 → 0.65 → 0.7 → 0.72
    The last 3 entries are >= 0.6 (HIGH_SMI_THRESHOLD), forming a corridor.
    """
    tracker = TemporalBhavaTracker(window_size=10)

    # Add entries with tension corridor at end
    smi_values = [0.4, 0.5, 0.65, 0.7, 0.72]
    for i, smi in enumerate(smi_values):
        tracker.add_analysis(
            text=f"Test message {i}",
            smi=smi,
            bhava_id=1,
            bhava_direction="upward" if i > 1 else "neutral",
            kosha_id=3,
            ontology_id=5,
            timestamp=float(i),
        )

    return tracker


def create_router_context(
    entropy: float,
    domain: str = "generic",
    long_arc_tension: float = 0.0,
    temporal_patterns_detected: bool = False,
) -> RouterContext:
    """
    Create a RouterContext for testing with specified parameters.
    """
    # Calculate H_D and H_G to achieve target entropy
    # Formula: entropy = 0.6 * (H_D / ln(10)) + 0.4 * (H_G / ln(3))
    k = max(0.0, min(1.0, entropy))
    H_D = k * math.log(10)
    H_G = k * math.log(3)

    # Balanced aspect probabilities
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

    # Balanced anchor scores
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

    return RouterContext(
        aspect_probs=aspect_probs,
        H_D=H_D,
        H_G=H_G,
        H_K=0.0,
        anchor_scores=anchor_scores,
        domain=domain,
        risk_level="low",
        long_arc_tension=long_arc_tension,
        temporal_patterns_detected=temporal_patterns_detected,
    )


# =============================================================================
# TEMPORAL BHAVA TRACKER TESTS
# =============================================================================

class TestTemporalBhavaTrackerDetection:
    """Tests for TemporalBhavaTracker.detect_activation_window()."""

    def test_rising_momentum_triggers_activation(self):
        """Rising SMI momentum should trigger LAM activation."""
        tracker = create_tracker_with_rising_momentum()
        signals = tracker.get_lam_activation_signals()

        assert signals["temporal_patterns_detected"], (
            "Rising momentum should trigger temporal_patterns_detected"
        )
        # Check that at least one activation condition is met
        assert (
            signals["momentum_active"]
            or signals["trajectory_active"]
            or signals["tension_corridor_active"]
        ), "At least one activation condition should be met"

    def test_falling_momentum_triggers_activation(self):
        """Falling SMI momentum should trigger LAM activation."""
        tracker = create_tracker_with_falling_momentum()
        signals = tracker.get_lam_activation_signals()

        assert signals["temporal_patterns_detected"], (
            "Falling momentum should trigger temporal_patterns_detected"
        )
        # Expect downward momentum or negative trajectory slope
        assert signals["momentum_direction"] == "downward" or signals["trajectory_slope"] < 0, (
            "Expected downward momentum direction or negative slope"
        )

    def test_no_trend_does_not_trigger(self):
        """Stable SMI values should NOT trigger LAM activation."""
        tracker = create_tracker_with_no_trend()
        signals = tracker.get_lam_activation_signals()

        assert not signals["temporal_patterns_detected"], (
            f"No-trend tracker should not trigger activation. "
            f"Got: momentum_active={signals['momentum_active']}, "
            f"trajectory_active={signals['trajectory_active']}, "
            f"tension_corridor_active={signals['tension_corridor_active']}"
        )

    def test_tension_corridor_triggers_activation(self):
        """Tension corridor (sustained high SMI) should trigger LAM activation."""
        tracker = create_tracker_with_tension_corridor()
        signals = tracker.get_lam_activation_signals()

        # Either tension corridor or trajectory slope should activate
        assert signals["temporal_patterns_detected"], (
            f"Tension corridor should trigger temporal_patterns_detected. "
            f"Got: tension_corridor_length={signals['tension_corridor_length']}, "
            f"trajectory_slope={signals['trajectory_slope']}"
        )

    def test_empty_tracker_no_activation(self):
        """Empty tracker should not trigger activation."""
        tracker = TemporalBhavaTracker(window_size=10)
        signals = tracker.get_lam_activation_signals()

        assert not signals["temporal_patterns_detected"], (
            "Empty tracker should not trigger activation"
        )
        assert signals["entry_count"] == 0

    def test_single_entry_no_activation(self):
        """Single entry should not trigger activation (need at least 2)."""
        tracker = TemporalBhavaTracker(window_size=10)
        tracker.add_analysis(
            text="Single entry",
            smi=0.7,
            bhava_id=1,
            bhava_direction="upward",
            kosha_id=3,
            ontology_id=5,
        )
        signals = tracker.get_lam_activation_signals()

        assert not signals["temporal_patterns_detected"], (
            "Single entry should not trigger activation"
        )


# =============================================================================
# TTOR ROUTER INTEGRATION TESTS
# =============================================================================

class TestTTORTemporalIntegration:
    """Tests for TTOR router's handling of temporal_patterns_detected."""

    def test_temporal_signal_activates_lam_low_entropy(self):
        """
        Temporal signal should activate LAM even with low entropy.

        When temporal_patterns_detected=True, LAM should activate regardless
        of entropy level (canonical rule allows temporal override).
        """
        router = TTORRouter()

        # Low entropy, no tension, but temporal signal active
        ctx = create_router_context(
            entropy=0.3,  # Below all thresholds
            domain="generic",  # Not a LAM domain
            long_arc_tension=0.0,  # Below threshold
            temporal_patterns_detected=True,  # This should trigger LAM
        )

        plan = router.route(ctx)

        assert plan.use_lam, (
            f"LAM should be True when temporal_patterns_detected=True. "
            f"Got: use_lam={plan.use_lam}, entropy={plan.normalized_entropy:.3f}"
        )
        assert plan.debug.get("temporal_patterns_detected") == True

    def test_no_temporal_signal_no_lam_low_entropy(self):
        """
        Without temporal signal, LAM should NOT activate with low entropy.
        """
        router = TTORRouter()

        ctx = create_router_context(
            entropy=0.3,
            domain="generic",
            long_arc_tension=0.0,
            temporal_patterns_detected=False,
        )

        plan = router.route(ctx)

        assert not plan.use_lam, (
            f"LAM should be False without temporal signal at low entropy. "
            f"Got: use_lam={plan.use_lam}"
        )

    def test_temporal_signal_with_high_tension(self):
        """
        Both temporal signal and high tension should activate LAM.
        """
        router = TTORRouter()

        ctx = create_router_context(
            entropy=0.3,
            domain="generic",
            long_arc_tension=0.8,  # High tension
            temporal_patterns_detected=True,  # Also temporal
        )

        plan = router.route(ctx)

        assert plan.use_lam, "LAM should activate with temporal + high tension"

    def test_therapy_domain_with_temporal(self):
        """
        Therapy domain with temporal patterns should definitely activate LAM.
        """
        router = TTORRouter()

        ctx = create_router_context(
            entropy=0.7,  # High entropy for therapy rule
            domain="therapy",  # LAM domain
            long_arc_tension=0.3,
            temporal_patterns_detected=True,
        )

        plan = router.route(ctx)

        assert plan.use_lam, "LAM should activate for therapy domain with temporal signal"


# =============================================================================
# MLCR EXPERT ROUTER INTEGRATION TESTS
# =============================================================================

class TestMLCRTemporalIntegration:
    """Tests for MLCR expert router's handling of temporal_patterns_detected."""

    def test_mlcr_temporal_signal_activates_lam(self):
        """MLCR should activate LAM when temporal_patterns_detected=True."""
        router = ExpertRouter()

        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.ASK,
            domain="generic",
            H_D=0.5,  # Low-ish entropy
            H_G=0.3,
            long_arc_tension=0.0,
            temporal_patterns_detected=True,
        )

        assert activation["use_lam"], (
            "MLCR should activate LAM when temporal_patterns_detected=True"
        )
        assert activation["temporal_patterns_detected"] == True

    def test_mlcr_no_temporal_signal_respects_rules(self):
        """MLCR should follow canonical rules when temporal signal is False."""
        router = ExpertRouter()

        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.ASK,
            domain="generic",
            H_D=0.5,
            H_G=0.3,
            long_arc_tension=0.0,
            temporal_patterns_detected=False,
        )

        # Without temporal signal, LAM should only activate via tension or domain rules
        # Here: generic domain, low tension → LAM should be False
        assert not activation["use_lam"], (
            "MLCR should not activate LAM without temporal signal (generic domain, low tension)"
        )


# =============================================================================
# END-TO-END INTEGRATION TESTS
# =============================================================================

class TestEndToEndTemporalLAM:
    """End-to-end tests: TemporalBhavaTracker → TTOR router."""

    def test_e2e_rising_momentum_activates_lam(self):
        """
        End-to-end: Rising momentum tracker → TTOR → LAM activation.
        """
        # Step 1: Create tracker with rising momentum
        tracker = create_tracker_with_rising_momentum()
        temporal_signal = tracker.detect_activation_window()

        # Step 2: Create router context with the temporal signal
        ctx = create_router_context(
            entropy=0.3,  # Low entropy (wouldn't normally trigger LAM)
            domain="generic",
            long_arc_tension=0.0,
            temporal_patterns_detected=temporal_signal,
        )

        # Step 3: Route through TTOR
        router = TTORRouter()
        plan = router.route(ctx)

        assert plan.use_lam, (
            f"LAM should be True with rising momentum. "
            f"temporal_signal={temporal_signal}, entropy={plan.normalized_entropy:.3f}"
        )

    def test_e2e_falling_momentum_activates_lam(self):
        """
        End-to-end: Falling momentum tracker → TTOR → LAM activation.
        """
        tracker = create_tracker_with_falling_momentum()
        temporal_signal = tracker.detect_activation_window()

        ctx = create_router_context(
            entropy=0.3,
            domain="generic",
            long_arc_tension=0.0,
            temporal_patterns_detected=temporal_signal,
        )

        router = TTORRouter()
        plan = router.route(ctx)

        assert plan.use_lam, (
            f"LAM should be True with falling momentum. "
            f"temporal_signal={temporal_signal}"
        )

    def test_e2e_no_trend_falls_back_to_rules(self):
        """
        End-to-end: No-trend tracker → TTOR → LAM via standard rules only.
        """
        tracker = create_tracker_with_no_trend()
        temporal_signal = tracker.detect_activation_window()

        # This should be False (no significant trend)
        assert not temporal_signal, "No-trend tracker should not trigger temporal signal"

        ctx = create_router_context(
            entropy=0.3,
            domain="generic",
            long_arc_tension=0.0,
            temporal_patterns_detected=temporal_signal,
        )

        router = TTORRouter()
        plan = router.route(ctx)

        # LAM should be False (no temporal, low entropy, low tension, generic domain)
        assert not plan.use_lam, (
            "LAM should be False with no temporal signal and no other triggers"
        )

    def test_e2e_extreme_tension_with_temporal(self):
        """
        End-to-end: Rising momentum + extreme tension → LAM definitely active.
        """
        tracker = create_tracker_with_rising_momentum()
        temporal_signal = tracker.detect_activation_window()

        ctx = create_router_context(
            entropy=0.8,
            domain="therapy",  # LAM domain
            long_arc_tension=0.9,  # Extreme tension
            temporal_patterns_detected=temporal_signal,
        )

        router = TTORRouter()
        plan = router.route(ctx)

        # All three triggers: temporal, tension, and domain+entropy
        assert plan.use_lam, "LAM must be True with all triggers active"


# =============================================================================
# REPORT GENERATION
# =============================================================================

def test_generate_temporal_lam_report(tmp_path):
    """
    Generate a JSON report for temporal-LAM integration testing.
    """
    import json

    test_cases = []
    router = TTORRouter()

    # Test scenarios
    scenarios = [
        ("rising_momentum", create_tracker_with_rising_momentum()),
        ("falling_momentum", create_tracker_with_falling_momentum()),
        ("no_trend", create_tracker_with_no_trend()),
        ("tension_corridor", create_tracker_with_tension_corridor()),
    ]

    for scenario_name, tracker in scenarios:
        signals = tracker.get_lam_activation_signals()
        temporal_signal = tracker.detect_activation_window()

        # Test with low entropy (only temporal should trigger LAM)
        ctx = create_router_context(
            entropy=0.3,
            domain="generic",
            long_arc_tension=0.0,
            temporal_patterns_detected=temporal_signal,
        )
        plan = router.route(ctx)

        test_cases.append({
            "scenario": scenario_name,
            "temporal_patterns_detected": temporal_signal,
            "momentum_active": signals["momentum_active"],
            "trajectory_active": signals["trajectory_active"],
            "tension_corridor_active": signals["tension_corridor_active"],
            "momentum_direction": signals["momentum_direction"],
            "momentum_strength": signals["momentum_strength"],
            "trajectory_slope": signals["trajectory_slope"],
            "use_lam": plan.use_lam,
            "normalized_entropy": plan.normalized_entropy,
            "expected_lam": (
                scenario_name in ["rising_momentum", "falling_momentum", "tension_corridor"]
            ),
        })

    report = {
        "test_suite": "temporal_lam_activation",
        "version": "v2.0",
        "total_scenarios": len(test_cases),
        "test_cases": test_cases,
        "status": (
            "OK" if all(tc["use_lam"] == tc["expected_lam"] for tc in test_cases)
            else "DRIFT"
        ),
    }

    # Write to fixed location
    output_path = "/home/user/symbolu/symbolu/core/drift_tests/temporal_lam_report.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    # Assert all expectations are met
    for tc in test_cases:
        assert tc["use_lam"] == tc["expected_lam"], (
            f"Scenario '{tc['scenario']}': expected LAM={tc['expected_lam']}, "
            f"got LAM={tc['use_lam']}"
        )
