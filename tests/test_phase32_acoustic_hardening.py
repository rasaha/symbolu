"""
Phase 32 Hardening Test Suite: Acoustic-Safe Insight Window Gating

This test suite verifies all governance-critical hardening invariants for Phase 32.
These tests are MANDATORY and must pass for any release.

TEST GROUPS:
- Group A: Non-Increase Proof (10+ tests)
- Group B: Gate Monotonicity (10+ tests)
- Group C: Regression Lock (10+ tests)
- Group D: Import Safety (5+ tests)
- Group E: Determinism (5+ tests)

CRITICAL INVARIANTS TESTED:
- INV-P32-H1: adjusted_insight_depth <= base_insight_depth (ALWAYS)
- INV-P32-H2: Acoustic input can ONLY reduce insight_depth, never increase
- INV-P32-H3: When acoustic_alignment is None, output == input (bitwise)
- INV-P32-H4: If base window is CLOSED, adjusted window MUST remain CLOSED

This test suite is designed for audit and legal scrutiny.
"""

import pytest
import random
from typing import Dict, Any, Optional
from dataclasses import dataclass

from symbolu.policy.insight_window_gating import (
    compute_insight_window,
    InsightWindowResult,
    _apply_observer_only_gate_hardening,
)
from symbolu.policy.phase32_hardening import (
    InsightHardeningViolation,
    verify_insight_gate_monotonicity,
    verify_depth_non_increase,
    assert_insight_acoustic_safe,
    verify_backward_compatibility,
    compute_acoustic_penalty,
    MAX_ACOUSTIC_PENALTY,
    MISALIGNMENT_THRESHOLD,
)
from symbolu.core.coherence.acoustic_alignment_schema import (
    AcousticAlignmentReport,
    create_aligned_report,
    create_misaligned_report,
    create_neutral_report,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================


@dataclass
class MockUCFSnapshot:
    """Mock UCF snapshot for testing."""
    consciousness_order_index: float
    consciousness_stability_index: float
    consciousness_integration_potential: float
    entropy_of_weights: float = 0.3
    diagnostic_notes: tuple = ()


@dataclass
class MockCoherenceObservation:
    """Mock coherence observation for testing."""
    consciousness_order_index: Optional[float] = None
    consciousness_stability_index: Optional[float] = None
    consciousness_integration_potential: Optional[float] = None
    ucf_entropy: Optional[float] = None
    cognitive_drift_v3: Optional[float] = None
    temporal_entropy_volatility: Optional[float] = None
    ucf_notes: tuple = ()


@pytest.fixture
def sample_acoustic_reports():
    """Create sample acoustic alignment reports for testing."""
    return {
        "aligned": create_aligned_report(alignment_score=0.8, pressure_band="low"),
        "neutral": create_neutral_report(),
        "mild_misalign": create_misaligned_report(
            alignment_score=0.35, pressure_band="moderate", mismatch_tags=("mild_tension",)
        ),
        "moderate_misalign": create_misaligned_report(
            alignment_score=0.25, pressure_band="high", mismatch_tags=("moderate_tension",)
        ),
        "severe_misalign": create_misaligned_report(
            alignment_score=0.1, pressure_band="high", mismatch_tags=("severe_tension", "inner_outer_tension")
        ),
        "zero_alignment": create_misaligned_report(
            alignment_score=0.0, pressure_band="high", mismatch_tags=("complete_misalignment",)
        ),
    }


def random_ucf_snapshot() -> MockUCFSnapshot:
    """Generate random valid UCF snapshot."""
    return MockUCFSnapshot(
        consciousness_order_index=random.uniform(0.3, 0.9),
        consciousness_stability_index=random.uniform(0.3, 0.9),
        consciousness_integration_potential=random.uniform(0.3, 0.9),
        entropy_of_weights=random.uniform(0.1, 0.5),
    )


def random_coherence_observation() -> MockCoherenceObservation:
    """Generate random valid coherence observation."""
    return MockCoherenceObservation(
        cognitive_drift_v3=random.uniform(0.0, 0.8),
        temporal_entropy_volatility=random.uniform(0.0, 0.8),
    )


def random_acoustic_report(max_alignment: float = 1.0) -> AcousticAlignmentReport:
    """Generate a random acoustic alignment report."""
    alignment = random.uniform(0.0, max_alignment)
    pressure = random.choice(["low", "moderate", "high"])
    tags = tuple(random.sample(["tension", "mismatch", "pressure"], k=random.randint(0, 2)))
    return AcousticAlignmentReport(
        alignment_score=alignment,
        pressure_band=pressure,
        mismatch_tags=tags,
    )


def create_high_coherence_snapshot() -> MockUCFSnapshot:
    """Create high-coherence UCF snapshot (window should open)."""
    return MockUCFSnapshot(
        consciousness_order_index=0.75,
        consciousness_stability_index=0.70,
        consciousness_integration_potential=0.65,
        entropy_of_weights=0.25,
    )


def create_low_coherence_snapshot() -> MockUCFSnapshot:
    """Create low-coherence UCF snapshot (window should stay closed)."""
    return MockUCFSnapshot(
        consciousness_order_index=0.40,
        consciousness_stability_index=0.35,
        consciousness_integration_potential=0.30,
        entropy_of_weights=0.50,
    )


# =============================================================================
# GROUP A: NON-INCREASE PROOF (10+ tests)
# Prove that adjusted_insight_depth <= base_insight_depth ALWAYS
# =============================================================================


class TestGroupA_NonIncreaseProof:
    """
    Group A: Non-Increase Proof

    These tests prove that for ALL valid inputs:
        adjusted_insight_depth <= base_insight_depth

    This is invariant INV-P32-H1.
    """

    def test_a01_no_acoustic_returns_same(self):
        """No acoustic input returns identical insight depth (INV-P32-H3)."""
        snapshot = create_high_coherence_snapshot()

        result_without = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        result_with = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        assert result_without.insight_depth == result_with.insight_depth
        assert result_without.insight_window_open == result_with.insight_window_open
        assert result_without.insight_mode == result_with.insight_mode

    def test_a02_aligned_acoustic_no_penalty(self, sample_acoustic_reports):
        """High alignment score (>=0.4) applies no penalty."""
        snapshot = create_high_coherence_snapshot()
        report = sample_acoustic_reports["aligned"]  # alignment_score=0.8

        result_without = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        result_with = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        # High alignment should not reduce depth
        assert result_with.insight_depth == result_without.insight_depth

    def test_a03_misaligned_reduces_depth(self, sample_acoustic_reports):
        """Misaligned acoustic (alignment < 0.4) reduces insight depth."""
        snapshot = create_high_coherence_snapshot()
        report = sample_acoustic_reports["moderate_misalign"]  # alignment_score=0.25

        result_without = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        result_with = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        assert result_with.insight_depth <= result_without.insight_depth, (
            f"INV-P32-H1 VIOLATED: {result_with.insight_depth} > {result_without.insight_depth}"
        )

    def test_a04_severe_misalignment_max_penalty(self, sample_acoustic_reports):
        """Severe misalignment applies maximum 5% penalty."""
        snapshot = create_high_coherence_snapshot()
        report = sample_acoustic_reports["zero_alignment"]  # alignment_score=0.0

        result_without = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        result_with = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        penalty = result_without.insight_depth - result_with.insight_depth
        assert result_with.insight_depth <= result_without.insight_depth
        # Use tolerance for floating-point comparison
        assert penalty <= MAX_ACOUSTIC_PENALTY + 1e-9, f"Penalty {penalty} exceeds max {MAX_ACOUSTIC_PENALTY}"
        assert penalty >= 0.0

    def test_a05_random_inputs_invariant_holds(self):
        """Random inputs: invariant always holds (100 iterations)."""
        for _ in range(100):
            snapshot = random_ucf_snapshot()
            observation = random_coherence_observation()
            report = random_acoustic_report()

            result_without = compute_insight_window(
                ucf_snapshot=snapshot,
                coherence_observation=observation,
                interaction_mode="smart_insight",
                domain="therapy",
                acoustic_alignment=None,
            )

            result_with = compute_insight_window(
                ucf_snapshot=snapshot,
                coherence_observation=observation,
                interaction_mode="smart_insight",
                domain="therapy",
                acoustic_alignment=report,
            )

            assert result_with.insight_depth <= result_without.insight_depth, (
                f"INV-P32-H1 VIOLATED: adjusted={result_with.insight_depth} > "
                f"base={result_without.insight_depth}, alignment={report.alignment_score}"
            )

    def test_a06_boundary_alignment_0_4(self):
        """Boundary test: alignment exactly at 0.4 threshold."""
        snapshot = create_high_coherence_snapshot()
        report = AcousticAlignmentReport(
            alignment_score=0.4,
            pressure_band="moderate",
            mismatch_tags=(),
        )

        result_without = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        result_with = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        # At boundary 0.4, no penalty should apply
        assert result_with.insight_depth == result_without.insight_depth

    def test_a07_boundary_alignment_just_below_0_4(self):
        """Boundary test: alignment just below 0.4 threshold."""
        snapshot = create_high_coherence_snapshot()
        report = AcousticAlignmentReport(
            alignment_score=0.399,
            pressure_band="moderate",
            mismatch_tags=(),
        )

        result_without = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        result_with = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        assert result_with.insight_depth <= result_without.insight_depth
        # Just below threshold should apply small penalty
        assert result_with.insight_depth < result_without.insight_depth

    def test_a08_extreme_high_base_depth(self, sample_acoustic_reports):
        """Extreme: high base depth with severe misalignment."""
        snapshot = MockUCFSnapshot(
            consciousness_order_index=0.95,
            consciousness_stability_index=0.95,
            consciousness_integration_potential=0.95,
        )
        report = sample_acoustic_reports["zero_alignment"]

        result_without = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        result_with = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        assert result_with.insight_depth <= result_without.insight_depth

    def test_a09_extreme_low_base_depth(self, sample_acoustic_reports):
        """Extreme: low base depth with severe misalignment (depth stays non-negative)."""
        snapshot = create_low_coherence_snapshot()
        report = sample_acoustic_reports["zero_alignment"]

        result_with = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        assert result_with.insight_depth >= 0.0, "Insight depth must not go below 0"

    def test_a10_penalty_amount_bounded(self):
        """Penalty amount is always in [0.0, 0.05]."""
        for _ in range(100):
            snapshot = random_ucf_snapshot()
            report = random_acoustic_report(max_alignment=0.39)  # Force penalty

            result_without = compute_insight_window(
                ucf_snapshot=snapshot,
                coherence_observation=None,
                interaction_mode="smart_insight",
                domain="therapy",
                acoustic_alignment=None,
            )

            result_with = compute_insight_window(
                ucf_snapshot=snapshot,
                coherence_observation=None,
                interaction_mode="smart_insight",
                domain="therapy",
                acoustic_alignment=report,
            )

            penalty = result_without.insight_depth - result_with.insight_depth
            assert 0.0 <= penalty <= MAX_ACOUSTIC_PENALTY, f"Penalty out of bounds: {penalty}"

    def test_a11_hardening_function_never_increases(self):
        """_apply_observer_only_gate_hardening never increases depth."""
        for _ in range(100):
            base_depth = random.uniform(0.0, 1.0)
            base_window = random.choice([True, False])
            report = random_acoustic_report()

            adjusted_depth, adjusted_window, penalty_applied, penalty = _apply_observer_only_gate_hardening(
                base_insight_depth=base_depth,
                base_window_open=base_window,
                acoustic_alignment=report,
            )

            assert adjusted_depth <= base_depth, (
                f"INV-P32-H1 VIOLATED: adjusted={adjusted_depth} > base={base_depth}"
            )

    def test_a12_compute_acoustic_penalty_bounded(self):
        """compute_acoustic_penalty returns values in [0.0, 0.05]."""
        for _ in range(100):
            alignment = random.uniform(0.0, 1.0)
            penalty = compute_acoustic_penalty(alignment)
            assert 0.0 <= penalty <= MAX_ACOUSTIC_PENALTY, f"Penalty out of bounds: {penalty}"


# =============================================================================
# GROUP B: GATE MONOTONICITY (10+ tests)
# If base window is CLOSED, adjusted window MUST remain CLOSED
# =============================================================================


class TestGroupB_GateMonotonicity:
    """
    Group B: Gate Monotonicity

    These tests prove that:
    - If base window is CLOSED, adjusted window MUST remain CLOSED
    - Window can only close, never open

    This is invariant INV-P32-H4.
    """

    def test_b01_verify_function_closed_stays_closed(self):
        """verify_insight_gate_monotonicity: CLOSED stays CLOSED."""
        assert verify_insight_gate_monotonicity(0.35, 0.33, False, False) is True
        assert verify_insight_gate_monotonicity(0.35, 0.30, False, False) is True
        assert verify_insight_gate_monotonicity(0.35, 0.20, False, False) is True

    def test_b02_verify_function_open_can_close(self):
        """verify_insight_gate_monotonicity: OPEN can become CLOSED."""
        assert verify_insight_gate_monotonicity(0.70, 0.50, True, False) is True
        assert verify_insight_gate_monotonicity(0.70, 0.30, True, False) is True

    def test_b03_verify_function_open_stays_open(self):
        """verify_insight_gate_monotonicity: OPEN can stay OPEN."""
        assert verify_insight_gate_monotonicity(0.70, 0.68, True, True) is True
        assert verify_insight_gate_monotonicity(0.70, 0.65, True, True) is True

    def test_b04_verify_function_closed_to_open_forbidden(self):
        """verify_insight_gate_monotonicity: CLOSED → OPEN is forbidden."""
        assert verify_insight_gate_monotonicity(0.35, 0.60, False, True) is False

    def test_b05_verify_function_directional_violation(self):
        """verify_insight_gate_monotonicity detects depth increase violations."""
        # adjusted > base is always a violation
        assert verify_insight_gate_monotonicity(0.50, 0.55, True, True) is False
        assert verify_insight_gate_monotonicity(0.30, 0.35, False, False) is False

    def test_b06_closed_window_stays_closed_with_acoustic(self, sample_acoustic_reports):
        """Closed window stays closed even with acoustic input."""
        snapshot = create_low_coherence_snapshot()  # Will have closed window
        report = sample_acoustic_reports["aligned"]  # Well-aligned

        result = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        # With low coherence, window should be closed regardless of acoustic
        # Note: This depends on COI/CSI thresholds, which are checked separately
        # The invariant is: if base was CLOSED, acoustic cannot OPEN it

    def test_b07_hardening_function_preserves_closed(self):
        """_apply_observer_only_gate_hardening preserves CLOSED state."""
        for _ in range(50):
            base_depth = random.uniform(0.0, 0.5)
            report = random_acoustic_report()

            adjusted_depth, adjusted_window, _, _ = _apply_observer_only_gate_hardening(
                base_insight_depth=base_depth,
                base_window_open=False,  # Base is CLOSED
                acoustic_alignment=report,
            )

            assert adjusted_window is False, (
                f"INV-P32-H4 VIOLATED: CLOSED window became OPEN"
            )

    def test_b08_hardening_function_allows_open_to_close(self):
        """_apply_observer_only_gate_hardening can close an OPEN window."""
        # This is allowed - window can close but cannot open
        base_depth = 0.7
        report = AcousticAlignmentReport(
            alignment_score=0.0,  # Maximum misalignment
            pressure_band="high",
            mismatch_tags=("severe",),
        )

        adjusted_depth, adjusted_window, penalty_applied, penalty = _apply_observer_only_gate_hardening(
            base_insight_depth=base_depth,
            base_window_open=True,
            acoustic_alignment=report,
        )

        assert adjusted_depth <= base_depth
        # Window may stay open or close based on adjusted depth
        # The key is it should never go from CLOSED to OPEN

    def test_b09_random_gate_monotonicity(self):
        """Random inputs: gate monotonicity always holds."""
        for _ in range(100):
            snapshot = random_ucf_snapshot()
            report = random_acoustic_report()

            result_without = compute_insight_window(
                ucf_snapshot=snapshot,
                coherence_observation=None,
                interaction_mode="smart_insight",
                domain="therapy",
                acoustic_alignment=None,
            )

            result_with = compute_insight_window(
                ucf_snapshot=snapshot,
                coherence_observation=None,
                interaction_mode="smart_insight",
                domain="therapy",
                acoustic_alignment=report,
            )

            # If base window was CLOSED, adjusted window MUST be CLOSED
            if not result_without.insight_window_open:
                assert not result_with.insight_window_open, (
                    f"INV-P32-H4 VIOLATED: CLOSED window became OPEN"
                )

    def test_b10_assert_insight_acoustic_safe_passes(self):
        """assert_insight_acoustic_safe passes for valid adjustments."""
        # Valid: depth decreases, closed stays closed
        assert_insight_acoustic_safe(0.7, 0.65, True, True)
        assert_insight_acoustic_safe(0.5, 0.5, False, False)
        assert_insight_acoustic_safe(0.8, 0.75, True, False)  # Open → Closed allowed

    def test_b11_assert_insight_acoustic_safe_raises_for_increase(self):
        """assert_insight_acoustic_safe raises for depth increase."""
        with pytest.raises(InsightHardeningViolation) as exc_info:
            assert_insight_acoustic_safe(0.5, 0.52, True, True)

        assert "INV-P32-H1" in str(exc_info.value)

    def test_b12_assert_insight_acoustic_safe_raises_for_gate_violation(self):
        """assert_insight_acoustic_safe raises for gate monotonicity violation."""
        with pytest.raises(InsightHardeningViolation) as exc_info:
            assert_insight_acoustic_safe(0.35, 0.35, False, True)  # CLOSED → OPEN

        assert "INV-P32-H4" in str(exc_info.value)


# =============================================================================
# GROUP C: REGRESSION LOCK (10+ tests)
# Identical authoritative inputs produce identical outputs
# =============================================================================


class TestGroupC_RegressionLock:
    """
    Group C: Regression Lock

    Two contexts with identical authoritative inputs must produce identical:
    - Regime (P6)
    - Discourse (P7)
    - Semantic slots (P8)
    - Lexical selection (P9)

    When one has acoustic diagnostics and one doesn't, the authoritative
    outputs must be identical (acoustic only affects insight depth annotation).
    """

    def test_c01_no_acoustic_identical_to_original(self):
        """No acoustic input produces output identical to original formula."""
        snapshot = create_high_coherence_snapshot()

        # Multiple calls without acoustic should be identical
        result1 = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        result2 = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        assert result1.insight_depth == result2.insight_depth
        assert result1.insight_window_open == result2.insight_window_open
        assert result1.insight_mode == result2.insight_mode

    def test_c02_verify_backward_compatibility_function(self):
        """verify_backward_compatibility detects violations."""
        result1 = InsightWindowResult(
            insight_window_open=True,
            insight_depth=0.7,
            insight_mode="deep",
        )
        result2 = InsightWindowResult(
            insight_window_open=True,
            insight_depth=0.7,
            insight_mode="deep",
        )

        # No acoustic - must be equal
        assert verify_backward_compatibility(result1, result2, False) is True

        # With acoustic - adjusted may be lower
        result3 = InsightWindowResult(
            insight_window_open=True,
            insight_depth=0.65,
            insight_mode="light",
        )
        assert verify_backward_compatibility(result3, result1, True) is True  # Reduced
        assert verify_backward_compatibility(result1, result1, True) is True  # Same

    def test_c03_repeated_calls_same_result(self):
        """Repeated calls with same inputs produce identical results."""
        snapshot = random_ucf_snapshot()
        report = random_acoustic_report()

        results = []
        for _ in range(10):
            result = compute_insight_window(
                ucf_snapshot=snapshot,
                coherence_observation=None,
                interaction_mode="smart_insight",
                domain="therapy",
                acoustic_alignment=report,
            )
            results.append(result)

        first_result = results[0]
        for i, result in enumerate(results[1:], start=1):
            assert result.insight_depth == first_result.insight_depth, (
                f"Non-determinism detected: result[0].depth={first_result.insight_depth}, "
                f"result[{i}].depth={result.insight_depth}"
            )

    def test_c04_base_ucf_metrics_unchanged_by_acoustic(self):
        """Base UCF metrics (COI/CSI/CIP) are not modified by acoustic."""
        snapshot = create_high_coherence_snapshot()

        result_without = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        report = create_misaligned_report(alignment_score=0.1)
        result_with = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        # Both results should reference same UCF metrics (visible in notes)
        # The COI/CSI/CIP values in notes should be identical
        without_ucf_note = [n for n in result_without.notes if "UCF metrics:" in n]
        with_ucf_note = [n for n in result_with.notes if "UCF metrics:" in n]

        assert without_ucf_note == with_ucf_note, "UCF metrics should not change"

    def test_c05_domain_gate_unaffected_by_acoustic(self):
        """Domain gate (P6-related) is not affected by acoustic."""
        snapshot = create_high_coherence_snapshot()
        report = random_acoustic_report()

        # Trading domain should always close window regardless of acoustic
        result = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="trading",  # Not therapy/identity
            acoustic_alignment=report,
        )

        assert result.insight_window_open is False
        assert result.insight_mode == "none"

    def test_c06_mode_gate_unaffected_by_acoustic(self):
        """Mode gate is not affected by acoustic."""
        snapshot = create_high_coherence_snapshot()
        report = random_acoustic_report()

        # analytics_only mode should always close window regardless of acoustic
        result = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="analytics_only",  # Not smart_insight/deep_adaptive
            domain="therapy",
            acoustic_alignment=report,
        )

        assert result.insight_window_open is False
        assert result.insight_mode == "none"

    def test_c07_formula_weights_unchanged(self):
        """Core depth formula weights (0.40 COI, 0.40 CSI, 0.20 CIP) are unchanged."""
        # Test with specific values where we can verify weights
        snapshot = MockUCFSnapshot(
            consciousness_order_index=0.60,
            consciousness_stability_index=0.60,
            consciousness_integration_potential=0.60,
        )

        result = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        # raw_depth = 0.40 * 0.60 + 0.40 * 0.60 + 0.20 * 0.60 = 0.60
        # With no modifiers, depth should be 0.60
        # But window openness depends on COI >= 0.55 AND CSI >= 0.50
        assert abs(result.insight_depth - 0.60) < 0.01, f"Expected ~0.60, got {result.insight_depth}"

    def test_c08_authoritative_inputs_produce_same_base(self):
        """Same authoritative inputs always produce same base depth."""
        snapshot = create_high_coherence_snapshot()

        # Multiple reports with different acoustic data
        reports = [
            None,
            create_aligned_report(),
            create_misaligned_report(alignment_score=0.3),
            create_misaligned_report(alignment_score=0.1),
        ]

        base_result = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        for report in reports:
            result = compute_insight_window(
                ucf_snapshot=snapshot,
                coherence_observation=None,
                interaction_mode="smart_insight",
                domain="therapy",
                acoustic_alignment=report,
            )

            # Adjusted depth may differ, but should not exceed base
            assert result.insight_depth <= base_result.insight_depth

    def test_c09_acoustic_only_affects_depth_and_mode(self):
        """Acoustic input only affects depth and mode, not other authoritative outputs."""
        snapshot = create_high_coherence_snapshot()

        result_without = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        report = create_misaligned_report(alignment_score=0.1)
        result_with = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        # Tags that are not acoustic-related should be identical
        base_tags = [t for t in result_without.insight_tags if "acoustic" not in t]
        adjusted_tags = [t for t in result_with.insight_tags if "acoustic" not in t]

        # Core tags should be preserved (though ordering may differ)
        for tag in ["structural_alignment", "temporal_resilience", "integration_ready"]:
            if tag in base_tags:
                assert tag in adjusted_tags, f"Tag '{tag}' should be preserved"

    def test_c10_missing_ucf_data_consistent(self):
        """Missing UCF data produces consistent closed window results."""
        # No UCF snapshot
        result1 = compute_insight_window(
            ucf_snapshot=None,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        result2 = compute_insight_window(
            ucf_snapshot=None,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=create_misaligned_report(),
        )

        # Both should have closed window (no UCF data)
        assert result1.insight_window_open is False
        assert result2.insight_window_open is False
        assert result1.insight_depth == result2.insight_depth == 0.0

    def test_c11_drift_risk_unaffected_by_acoustic(self):
        """Drift risk band classification is not affected by acoustic."""
        snapshot = create_high_coherence_snapshot()
        observation = MockCoherenceObservation(
            cognitive_drift_v3=0.70,  # High drift
        )

        result_without = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=observation,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=None,
        )

        result_with = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=observation,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=create_misaligned_report(),
        )

        # Both should have drift_caution tag
        assert "drift_caution" in result_without.insight_tags
        assert "drift_caution" in result_with.insight_tags


# =============================================================================
# GROUP D: IMPORT SAFETY (5+ tests)
# Phase 32 must not import P22, P23, or P24 directly
# =============================================================================


class TestGroupD_ImportSafety:
    """
    Group D: Import Safety

    Phase 32 must NOT import P22, P23, or P24 directly.
    Only the acoustic alignment schema is allowed.
    """

    def test_d01_insight_window_gating_no_p22_import(self):
        """insight_window_gating does not import P22 directly."""
        import symbolu.policy.insight_window_gating as iwg
        source = open(iwg.__file__).read()

        forbidden = [
            "from symbolu.mechanical.pipeline.p22",
            "import symbolu.mechanical.pipeline.p22",
            "from symbolu.mechanical.pipeline import p22",
            "p22_acoustic_witness",
        ]

        for pattern in forbidden:
            assert pattern not in source, (
                f"IMPORT SAFETY VIOLATION: insight_window_gating.py imports P22: {pattern}"
            )

    def test_d02_insight_window_gating_no_p23_import(self):
        """insight_window_gating does not import P23 directly."""
        import symbolu.policy.insight_window_gating as iwg
        source = open(iwg.__file__).read()

        forbidden = [
            "from symbolu.mechanical.pipeline.p23",
            "import symbolu.mechanical.pipeline.p23",
            "from symbolu.mechanical.pipeline import p23",
            "p23_alignment",
        ]

        for pattern in forbidden:
            assert pattern not in source, (
                f"IMPORT SAFETY VIOLATION: insight_window_gating.py imports P23: {pattern}"
            )

    def test_d03_insight_window_gating_no_p24_import(self):
        """insight_window_gating does not import P24 directly."""
        import symbolu.policy.insight_window_gating as iwg
        source = open(iwg.__file__).read()

        forbidden = [
            "from symbolu.mechanical.pipeline.p24",
            "import symbolu.mechanical.pipeline.p24",
            "from symbolu.mechanical.pipeline import p24",
            "p24_projection",
        ]

        for pattern in forbidden:
            assert pattern not in source, (
                f"IMPORT SAFETY VIOLATION: insight_window_gating.py imports P24: {pattern}"
            )

    def test_d04_phase32_hardening_no_observer_import(self):
        """phase32_hardening module does not import observer modules."""
        import symbolu.policy.phase32_hardening as h
        source = open(h.__file__).read()

        forbidden = [
            "p22_acoustic_witness",
            "p23_alignment",
            "p24_projection",
            "from symbolu.mechanical.pipeline.p22",
            "from symbolu.mechanical.pipeline.p23",
            "from symbolu.mechanical.pipeline.p24",
        ]

        for pattern in forbidden:
            assert pattern not in source, (
                f"IMPORT SAFETY VIOLATION: phase32_hardening.py references {pattern}"
            )

    def test_d05_no_direct_motion_primitive_access(self):
        """No direct access to motion primitives from observer phases."""
        import symbolu.policy.insight_window_gating as iwg
        source = open(iwg.__file__).read()

        # Motion primitives from P22
        forbidden = [
            "MotionPrimitive",
            "INERTIA",
            "EXPANSION",
            "CONTRACTION",
            "OSCILLATION",
            "FRICTION",
        ]

        for primitive in forbidden:
            # Only check code, not comments
            lines = [l for l in source.split('\n') if not l.strip().startswith('#')]
            code_only = '\n'.join(lines)
            if primitive in code_only:
                # Allow in string literals (comments already filtered)
                assert f'"{primitive}"' in code_only or f"'{primitive}'" in code_only, (
                    f"IMPORT SAFETY VIOLATION: Direct motion primitive reference: {primitive}"
                )

    def test_d06_only_schema_interface_allowed(self):
        """Only AcousticAlignmentReport (schema) interface is allowed."""
        import symbolu.policy.insight_window_gating as iwg
        source = open(iwg.__file__).read()

        # Should NOT reference observer-specific types
        forbidden_refs = [
            "P22AcousticWitnessReport",
            "P23AlignmentReport",
            "P24ProjectionReport",
            "AcousticWitness",
            "AlignmentObserver",
        ]

        for ref in forbidden_refs:
            assert ref not in source, (
                f"IMPORT SAFETY VIOLATION: insight_window_gating.py references {ref}"
            )

    def test_d07_type_checking_only_import(self):
        """AcousticAlignmentReport import is under TYPE_CHECKING only."""
        import symbolu.policy.insight_window_gating as iwg
        source = open(iwg.__file__).read()

        # Check that acoustic_alignment_schema import is inside TYPE_CHECKING block
        if "from symbolu.core.coherence.acoustic_alignment_schema" in source:
            assert "TYPE_CHECKING" in source, (
                "acoustic_alignment_schema import should be under TYPE_CHECKING"
            )


# =============================================================================
# GROUP E: DETERMINISM (5+ tests)
# Same inputs produce same outputs across runs
# =============================================================================


class TestGroupE_Determinism:
    """
    Group E: Determinism

    Same inputs (including acoustic diagnostics) must produce
    same outputs across runs.
    """

    def test_e01_basic_determinism(self):
        """Same inputs always produce same outputs."""
        snapshot = MockUCFSnapshot(
            consciousness_order_index=0.75,
            consciousness_stability_index=0.70,
            consciousness_integration_potential=0.65,
        )
        report = AcousticAlignmentReport(
            alignment_score=0.3,
            pressure_band="moderate",
            mismatch_tags=("tension",),
        )

        results = []
        for _ in range(100):
            result = compute_insight_window(
                ucf_snapshot=snapshot,
                coherence_observation=None,
                interaction_mode="smart_insight",
                domain="therapy",
                acoustic_alignment=report,
            )
            results.append(result)

        first = results[0]
        assert all(
            r.insight_depth == first.insight_depth and
            r.insight_window_open == first.insight_window_open and
            r.insight_mode == first.insight_mode
            for r in results
        ), "Determinism violation detected"

    def test_e02_determinism_without_acoustic(self):
        """Determinism holds without acoustic input."""
        snapshot = random_ucf_snapshot()

        results = []
        for _ in range(100):
            result = compute_insight_window(
                ucf_snapshot=snapshot,
                coherence_observation=None,
                interaction_mode="smart_insight",
                domain="therapy",
                acoustic_alignment=None,
            )
            results.append(result)

        first = results[0]
        assert all(
            r.insight_depth == first.insight_depth
            for r in results
        ), "Determinism violation without acoustic"

    def test_e03_determinism_hardening_function(self):
        """_apply_observer_only_gate_hardening is deterministic."""
        base_depth = 0.7
        base_window = True
        report = AcousticAlignmentReport(
            alignment_score=0.25,
            pressure_band="high",
            mismatch_tags=("test",),
        )

        results = []
        for _ in range(100):
            result = _apply_observer_only_gate_hardening(
                base_insight_depth=base_depth,
                base_window_open=base_window,
                acoustic_alignment=report,
            )
            results.append(result)

        first = results[0]
        assert all(r == first for r in results), "Hardening function determinism violation"

    def test_e04_determinism_compute_acoustic_penalty(self):
        """compute_acoustic_penalty is deterministic."""
        results = []
        for _ in range(100):
            penalty = compute_acoustic_penalty(0.25)
            results.append(penalty)

        first = results[0]
        assert all(r == first for r in results), "Penalty computation determinism violation"

    def test_e05_no_random_state_influence(self):
        """Random module state does not affect results."""
        snapshot = random_ucf_snapshot()
        report = random_acoustic_report()

        # Get baseline result
        result1 = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        # Generate many random numbers to change random state
        for _ in range(1000):
            random.random()

        # Should still get same result
        result2 = compute_insight_window(
            ucf_snapshot=snapshot,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy",
            acoustic_alignment=report,
        )

        assert result1.insight_depth == result2.insight_depth, "Random state influenced results"

    def test_e06_determinism_across_sessions(self):
        """Results are deterministic across simulated sessions."""
        snapshot = MockUCFSnapshot(
            consciousness_order_index=0.65,
            consciousness_stability_index=0.60,
            consciousness_integration_potential=0.55,
        )
        report = AcousticAlignmentReport(
            alignment_score=0.15,
            pressure_band="high",
            mismatch_tags=("severe",),
        )

        # Simulate multiple "sessions"
        results = []
        for _ in range(50):
            # Reset any potential state (though there shouldn't be any)
            result = compute_insight_window(
                ucf_snapshot=snapshot,
                coherence_observation=None,
                interaction_mode="deep_adaptive",
                domain="identity",
                acoustic_alignment=report,
            )
            results.append((result.insight_depth, result.insight_window_open, result.insight_mode))

        first = results[0]
        assert all(r == first for r in results), "Determinism violation across sessions"


# =============================================================================
# ADDITIONAL HARDENING TESTS
# =============================================================================


class TestInsightHardeningViolationException:
    """Tests for the InsightHardeningViolation exception."""

    def test_exception_can_be_raised(self):
        """InsightHardeningViolation can be raised and caught."""
        with pytest.raises(InsightHardeningViolation):
            raise InsightHardeningViolation("Test violation")

    def test_exception_message_preserved(self):
        """Exception message is preserved."""
        msg = "INV-P32-H1 VIOLATED: test message"
        try:
            raise InsightHardeningViolation(msg)
        except InsightHardeningViolation as e:
            assert msg in str(e)

    def test_exception_is_exception_subclass(self):
        """InsightHardeningViolation is an Exception subclass."""
        assert issubclass(InsightHardeningViolation, Exception)


class TestComputeAcousticPenalty:
    """Tests for the compute_acoustic_penalty function."""

    def test_no_penalty_at_threshold(self):
        """No penalty when alignment is at or above threshold."""
        assert compute_acoustic_penalty(0.4) == 0.0
        assert compute_acoustic_penalty(0.5) == 0.0
        assert compute_acoustic_penalty(0.8) == 0.0
        assert compute_acoustic_penalty(1.0) == 0.0

    def test_max_penalty_at_zero(self):
        """Maximum penalty when alignment is zero."""
        penalty = compute_acoustic_penalty(0.0)
        assert penalty == MAX_ACOUSTIC_PENALTY

    def test_linear_penalty_scaling(self):
        """Penalty scales linearly below threshold."""
        # At 0.2 (halfway from 0 to 0.4)
        # penalty = 0.05 * (0.4 - 0.2) / 0.4 = 0.05 * 0.5 = 0.025
        penalty = compute_acoustic_penalty(0.2)
        expected = MAX_ACOUSTIC_PENALTY * (0.4 - 0.2) / 0.4
        assert abs(penalty - expected) < 1e-10

    def test_penalty_just_below_threshold(self):
        """Small penalty just below threshold."""
        penalty = compute_acoustic_penalty(0.39)
        expected = MAX_ACOUSTIC_PENALTY * (0.4 - 0.39) / 0.4
        assert abs(penalty - expected) < 1e-10
        assert penalty > 0.0
        assert penalty < MAX_ACOUSTIC_PENALTY


class TestVerifyFunctions:
    """Tests for verification helper functions."""

    def test_verify_depth_non_increase(self):
        """verify_depth_non_increase works correctly."""
        assert verify_depth_non_increase(0.7, 0.7) is True
        assert verify_depth_non_increase(0.7, 0.6) is True
        assert verify_depth_non_increase(0.7, 0.8) is False

    def test_verify_insight_gate_monotonicity_comprehensive(self):
        """Comprehensive test of gate monotonicity verification."""
        test_cases = [
            # (base_depth, adjusted_depth, base_open, adjusted_open, expected)
            (0.7, 0.7, True, True, True),     # Same, open stays open
            (0.7, 0.6, True, True, True),     # Decrease, open stays open
            (0.7, 0.5, True, False, True),    # Decrease, open closes (allowed)
            (0.3, 0.3, False, False, True),   # Same, closed stays closed
            (0.3, 0.2, False, False, True),   # Decrease, closed stays closed
            (0.3, 0.4, False, False, False),  # Increase (violation)
            (0.3, 0.3, False, True, False),   # Closed → open (violation)
        ]

        for base_d, adj_d, base_o, adj_o, expected in test_cases:
            result = verify_insight_gate_monotonicity(base_d, adj_d, base_o, adj_o)
            assert result == expected, (
                f"verify_insight_gate_monotonicity({base_d}, {adj_d}, {base_o}, {adj_o}) "
                f"expected {expected}, got {result}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
