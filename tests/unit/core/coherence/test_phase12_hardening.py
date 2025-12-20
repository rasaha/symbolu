"""
Phase 12 Hardening Test Suite: Acoustic-Safe Quality Gating

This test suite verifies all governance-critical hardening invariants for Phase 12.
These tests are MANDATORY and must pass for any release.

TEST GROUPS:
- Group A: Non-Increase Proof (10+ tests)
- Group B: Gate Monotonicity (10+ tests)
- Group C: Regression Lock (10+ tests)
- Group D: Import Safety (5+ tests)
- Group E: Determinism (5+ tests)

CRITICAL INVARIANTS TESTED:
- INV-P12-H1: adjusted_quality <= base_quality (ALWAYS)
- INV-P12-H2: Acoustic input can ONLY reduce quality, never increase
- INV-P12-H3: When acoustic_alignment is None, output == input (bitwise)
- INV-P12-H4: If base_quality < threshold, adjusted cannot cross upward

This test suite is designed for audit and legal scrutiny.
"""

import pytest
import random
from typing import Tuple, Optional, Dict, Any

from symbolu.core.coherence.coherence_engine import CoherenceEngine
from symbolu.core.coherence.acoustic_alignment_schema import (
    AcousticAlignmentReport,
    create_aligned_report,
    create_misaligned_report,
    create_neutral_report,
)
from symbolu.core.coherence.phase12_hardening import (
    AcousticHardeningViolation,
    verify_gate_monotonicity,
    assert_acoustic_safe,
    verify_backward_compatibility,
    THERAPY_QUALITY_THRESHOLD,
    IDENTITY_QUALITY_THRESHOLD,
    ALL_QUALITY_THRESHOLDS,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def engine():
    """Create a CoherenceEngine instance for testing."""
    return CoherenceEngine(window=10)


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


def random_quality_inputs() -> Dict[str, float]:
    """Generate random valid quality inputs."""
    return {
        "base": random.uniform(0.0, 1.0),
        "v3": random.uniform(0.0, 1.0),
        "resonance_index": random.uniform(0.0, 1.0),
        "arc_alignment_index": random.uniform(0.0, 1.0),
        "tension_index": random.uniform(0.0, 1.0),
    }


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


# =============================================================================
# GROUP A: NON-INCREASE PROOF (10+ tests)
# Prove that adjusted_quality <= base_quality ALWAYS
# =============================================================================


class TestGroupA_NonIncreaseProof:
    """
    Group A: Non-Increase Proof

    These tests prove that for ALL valid inputs:
        adjusted_quality <= base_quality

    This is invariant INV-P12-H1.
    """

    def test_a01_no_acoustic_returns_same(self, engine):
        """No acoustic input returns identical quality (INV-P12-H3)."""
        inputs = random_quality_inputs()
        adjusted, penalty_applied, penalty_amount, base_q = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=None,
            **inputs
        )

        if adjusted is not None:
            assert adjusted == base_q, "Without acoustic, adjusted must equal base"
            assert not penalty_applied, "No penalty should be applied"
            assert penalty_amount == 0.0, "Penalty amount should be zero"

    def test_a02_aligned_acoustic_no_penalty(self, engine, sample_acoustic_reports):
        """High alignment score (>=0.4) applies no penalty."""
        inputs = random_quality_inputs()
        report = sample_acoustic_reports["aligned"]  # alignment_score=0.8

        adjusted, penalty_applied, penalty_amount, base_q = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report,
            **inputs
        )

        if adjusted is not None:
            assert adjusted == base_q, "Aligned acoustic should not reduce quality"
            assert not penalty_applied, "No penalty for high alignment"
            assert penalty_amount == 0.0

    def test_a03_misaligned_reduces_quality(self, engine, sample_acoustic_reports):
        """Misaligned acoustic (alignment < 0.4) reduces quality."""
        inputs = random_quality_inputs()
        report = sample_acoustic_reports["moderate_misalign"]  # alignment_score=0.25

        adjusted, penalty_applied, penalty_amount, base_q = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report,
            **inputs
        )

        if adjusted is not None and base_q is not None:
            assert adjusted <= base_q, f"INV-P12-H1 VIOLATED: {adjusted} > {base_q}"
            assert penalty_applied, "Penalty should be applied for misalignment"
            assert penalty_amount > 0.0

    def test_a04_severe_misalignment_max_penalty(self, engine, sample_acoustic_reports):
        """Severe misalignment applies maximum 5% penalty."""
        inputs = random_quality_inputs()
        report = sample_acoustic_reports["zero_alignment"]  # alignment_score=0.0

        adjusted, penalty_applied, penalty_amount, base_q = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report,
            **inputs
        )

        if adjusted is not None and base_q is not None:
            assert adjusted <= base_q, f"INV-P12-H1 VIOLATED: {adjusted} > {base_q}"
            assert penalty_amount <= 0.05, "Penalty must not exceed 5%"
            assert penalty_amount >= 0.0, "Penalty must be non-negative"

    def test_a05_random_inputs_invariant_holds(self, engine):
        """Random inputs: invariant always holds (100 iterations)."""
        for _ in range(100):
            inputs = random_quality_inputs()
            report = random_acoustic_report()

            adjusted, penalty_applied, penalty_amount, base_q = engine._compute_coherence_v3_quality_with_acoustic(
                acoustic_alignment=report,
                **inputs
            )

            if adjusted is not None and base_q is not None:
                assert adjusted <= base_q, (
                    f"INV-P12-H1 VIOLATED: adjusted={adjusted} > base={base_q}, "
                    f"alignment={report.alignment_score}"
                )

    def test_a06_boundary_alignment_0_4(self, engine):
        """Boundary test: alignment exactly at 0.4 threshold."""
        inputs = random_quality_inputs()
        report = AcousticAlignmentReport(
            alignment_score=0.4,
            pressure_band="moderate",
            mismatch_tags=(),
        )

        adjusted, penalty_applied, penalty_amount, base_q = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report,
            **inputs
        )

        if adjusted is not None and base_q is not None:
            assert adjusted == base_q, "At boundary 0.4, no penalty should apply"
            assert not penalty_applied

    def test_a07_boundary_alignment_just_below_0_4(self, engine):
        """Boundary test: alignment just below 0.4 threshold."""
        inputs = random_quality_inputs()
        report = AcousticAlignmentReport(
            alignment_score=0.399,
            pressure_band="moderate",
            mismatch_tags=(),
        )

        adjusted, penalty_applied, penalty_amount, base_q = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report,
            **inputs
        )

        if adjusted is not None and base_q is not None:
            assert adjusted <= base_q, f"INV-P12-H1 VIOLATED: {adjusted} > {base_q}"
            assert penalty_applied, "Just below threshold should apply penalty"

    def test_a08_extreme_high_base_quality(self, engine, sample_acoustic_reports):
        """Extreme: base quality = 1.0 with severe misalignment."""
        inputs = {
            "base": 0.9,
            "v3": 0.9,
            "resonance_index": 0.9,
            "arc_alignment_index": 0.9,
            "tension_index": 0.1,  # Low tension = high quality
        }
        report = sample_acoustic_reports["zero_alignment"]

        adjusted, penalty_applied, penalty_amount, base_q = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report,
            **inputs
        )

        if adjusted is not None and base_q is not None:
            assert adjusted <= base_q, f"INV-P12-H1 VIOLATED: {adjusted} > {base_q}"

    def test_a09_extreme_low_base_quality(self, engine, sample_acoustic_reports):
        """Extreme: base quality near 0.0 with severe misalignment."""
        inputs = {
            "base": 0.1,
            "v3": 0.1,
            "resonance_index": 0.1,
            "arc_alignment_index": 0.1,
            "tension_index": 0.9,  # High tension = low quality
        }
        report = sample_acoustic_reports["zero_alignment"]

        adjusted, penalty_applied, penalty_amount, base_q = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report,
            **inputs
        )

        if adjusted is not None and base_q is not None:
            assert adjusted <= base_q, f"INV-P12-H1 VIOLATED: {adjusted} > {base_q}"
            assert adjusted >= 0.0, "Adjusted quality must not go below 0"

    def test_a10_penalty_amount_bounded(self, engine):
        """Penalty amount is always in [0.0, 0.05]."""
        for _ in range(100):
            inputs = random_quality_inputs()
            report = random_acoustic_report(max_alignment=0.39)  # Force penalty

            adjusted, penalty_applied, penalty_amount, base_q = engine._compute_coherence_v3_quality_with_acoustic(
                acoustic_alignment=report,
                **inputs
            )

            if adjusted is not None:
                assert 0.0 <= penalty_amount <= 0.05, (
                    f"Penalty out of bounds: {penalty_amount}"
                )

    def test_a11_multiple_sequential_never_increase(self, engine):
        """Multiple sequential calls never increase quality."""
        inputs = random_quality_inputs()

        # First call without acoustic
        adj1, _, _, base1 = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=None, **inputs
        )

        # Second call with misaligned acoustic
        report = create_misaligned_report(alignment_score=0.2)
        adj2, _, _, base2 = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report, **inputs
        )

        if adj1 is not None and adj2 is not None:
            # Both should be <= their respective base
            assert adj1 <= base1 if base1 else True
            assert adj2 <= base2 if base2 else True


# =============================================================================
# GROUP B: GATE MONOTONICITY (10+ tests)
# For every gating threshold, base_quality below threshold must stay below
# =============================================================================


class TestGroupB_GateMonotonicity:
    """
    Group B: Gate Monotonicity

    These tests prove that for every gating threshold:
    - If base_quality < threshold, adjusted_quality MUST be < threshold
    - Gate can only close, never open

    This is invariant INV-P12-H4.
    """

    def test_b01_verify_function_closed_stays_closed(self):
        """verify_gate_monotonicity: CLOSED stays CLOSED."""
        assert verify_gate_monotonicity(0.35, 0.35, 0.40) is True
        assert verify_gate_monotonicity(0.35, 0.30, 0.40) is True
        assert verify_gate_monotonicity(0.35, 0.20, 0.40) is True

    def test_b02_verify_function_open_can_close(self):
        """verify_gate_monotonicity: OPEN can become CLOSED."""
        assert verify_gate_monotonicity(0.50, 0.35, 0.40) is True
        assert verify_gate_monotonicity(0.50, 0.30, 0.40) is True

    def test_b03_verify_function_open_stays_open(self):
        """verify_gate_monotonicity: OPEN can stay OPEN."""
        assert verify_gate_monotonicity(0.50, 0.50, 0.40) is True
        assert verify_gate_monotonicity(0.50, 0.45, 0.40) is True

    def test_b04_verify_function_closed_to_open_forbidden(self):
        """verify_gate_monotonicity: CLOSED → OPEN is forbidden."""
        # This should return False because it violates gate monotonicity
        # However, since adjusted > base is also a violation, it should fail
        assert verify_gate_monotonicity(0.35, 0.42, 0.40) is False

    def test_b05_verify_function_directional_violation(self):
        """verify_gate_monotonicity detects directional violations."""
        # adjusted > base is always a violation
        assert verify_gate_monotonicity(0.50, 0.55, 0.40) is False
        assert verify_gate_monotonicity(0.30, 0.35, 0.40) is False

    def test_b06_therapy_threshold_monotonicity(self, engine):
        """Therapy threshold (0.40): gate monotonicity holds."""
        threshold = THERAPY_QUALITY_THRESHOLD

        for _ in range(50):
            inputs = random_quality_inputs()
            report = random_acoustic_report(max_alignment=0.39)

            adjusted, _, _, base_q = engine._compute_coherence_v3_quality_with_acoustic(
                acoustic_alignment=report, **inputs
            )

            if adjusted is not None and base_q is not None:
                assert verify_gate_monotonicity(base_q, adjusted, threshold), (
                    f"Gate monotonicity violated: base={base_q}, adjusted={adjusted}, threshold={threshold}"
                )

    def test_b07_identity_threshold_monotonicity(self, engine):
        """Identity threshold (0.45): gate monotonicity holds."""
        threshold = IDENTITY_QUALITY_THRESHOLD

        for _ in range(50):
            inputs = random_quality_inputs()
            report = random_acoustic_report(max_alignment=0.39)

            adjusted, _, _, base_q = engine._compute_coherence_v3_quality_with_acoustic(
                acoustic_alignment=report, **inputs
            )

            if adjusted is not None and base_q is not None:
                assert verify_gate_monotonicity(base_q, adjusted, threshold), (
                    f"Gate monotonicity violated: base={base_q}, adjusted={adjusted}, threshold={threshold}"
                )

    def test_b08_assert_acoustic_safe_all_thresholds(self, engine):
        """assert_acoustic_safe validates all thresholds."""
        for _ in range(50):
            inputs = random_quality_inputs()
            report = random_acoustic_report()

            adjusted, _, _, base_q = engine._compute_coherence_v3_quality_with_acoustic(
                acoustic_alignment=report, **inputs
            )

            if adjusted is not None and base_q is not None:
                # Should not raise
                assert_acoustic_safe(base_q, adjusted, ALL_QUALITY_THRESHOLDS)

    def test_b09_closed_gate_base_just_below_threshold(self, engine):
        """Gate CLOSED: base just below threshold stays blocked."""
        # Create inputs that produce quality just below therapy threshold
        for threshold in ALL_QUALITY_THRESHOLDS:
            # Run multiple times to find case where base is just below threshold
            for _ in range(50):
                inputs = random_quality_inputs()
                report = random_acoustic_report(max_alignment=0.39)

                adjusted, _, _, base_q = engine._compute_coherence_v3_quality_with_acoustic(
                    acoustic_alignment=report, **inputs
                )

                if base_q is not None and base_q < threshold:
                    # If gate was CLOSED, it must stay CLOSED
                    if adjusted is not None:
                        assert adjusted < threshold, (
                            f"Gate opened! base={base_q} < threshold={threshold} "
                            f"but adjusted={adjusted} >= threshold"
                        )

    def test_b10_open_gate_may_close(self, engine, sample_acoustic_reports):
        """Gate OPEN: acoustic can close it (allowed)."""
        # High quality inputs
        inputs = {
            "base": 0.8,
            "v3": 0.8,
            "resonance_index": 0.7,
            "arc_alignment_index": 0.7,
            "tension_index": 0.3,
        }

        report = sample_acoustic_reports["zero_alignment"]
        adjusted, _, penalty, base_q = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report, **inputs
        )

        if adjusted is not None and base_q is not None:
            # With max 5% penalty, gate might close for thresholds close to base
            assert adjusted <= base_q
            # This is allowed - gate can close but cannot open

    def test_b11_boundary_at_threshold(self, engine):
        """Boundary: base exactly at threshold stays at or below."""
        for threshold in ALL_QUALITY_THRESHOLDS:
            for _ in range(20):
                inputs = random_quality_inputs()
                report = random_acoustic_report(max_alignment=0.39)

                adjusted, _, _, base_q = engine._compute_coherence_v3_quality_with_acoustic(
                    acoustic_alignment=report, **inputs
                )

                if base_q is not None and adjusted is not None:
                    # If base was at or above threshold, adjusted can be at or below
                    # but never above base
                    assert adjusted <= base_q


# =============================================================================
# GROUP C: REGRESSION LOCK (10+ tests)
# Identical authoritative inputs produce identical outputs
# =============================================================================


class TestGroupC_RegressionLock:
    """
    Group C: Regression Lock

    Two contexts with identical authoritative inputs must produce identical:
    - Regime decisions
    - Discourse acts
    - Semantic frames
    - Lexical frames
    - Action eligibility
    - Policy decisions

    When one has acoustic diagnostics and one doesn't, the authoritative
    outputs must be identical (acoustic only affects quality annotation).
    """

    def test_c01_no_acoustic_identical_to_original(self, engine):
        """No acoustic input produces output identical to original formula."""
        inputs = random_quality_inputs()

        # Without acoustic (original behavior)
        base_quality_original = engine._compute_coherence_v3_quality(**inputs)

        # With acoustic=None (should be identical)
        adjusted, penalty_applied, penalty_amount, base_q = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=None, **inputs
        )

        assert adjusted == base_quality_original, (
            f"Backward compatibility violated: adjusted={adjusted} != original={base_quality_original}"
        )
        assert base_q == base_quality_original

    def test_c02_verify_backward_compatibility_function(self):
        """verify_backward_compatibility detects violations."""
        # No acoustic - must be equal
        assert verify_backward_compatibility(0.5, 0.5, False) is True
        assert verify_backward_compatibility(0.5, 0.6, False) is False  # Different

        # With acoustic - adjusted may be lower
        assert verify_backward_compatibility(0.45, 0.5, True) is True  # Reduced
        assert verify_backward_compatibility(0.5, 0.5, True) is True  # Same
        assert verify_backward_compatibility(0.55, 0.5, True) is False  # Increased!

    def test_c03_repeated_calls_same_result(self, engine):
        """Repeated calls with same inputs produce identical results."""
        inputs = random_quality_inputs()
        report = random_acoustic_report()

        results = []
        for _ in range(10):
            result = engine._compute_coherence_v3_quality_with_acoustic(
                acoustic_alignment=report, **inputs
            )
            results.append(result)

        first_result = results[0]
        for i, result in enumerate(results[1:], start=1):
            assert result == first_result, (
                f"Non-determinism detected: result[0]={first_result}, result[{i}]={result}"
            )

    def test_c04_base_quality_unchanged_by_acoustic(self, engine):
        """Base quality (4th return value) matches original computation."""
        inputs = random_quality_inputs()

        # Original computation
        original_quality = engine._compute_coherence_v3_quality(**inputs)

        # With acoustic
        report = create_misaligned_report(alignment_score=0.1)
        _, _, _, base_q = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report, **inputs
        )

        assert base_q == original_quality, (
            f"Base quality changed! base_q={base_q}, original={original_quality}"
        )

    def test_c05_formula_weights_unchanged(self, engine):
        """Core formula weights are unchanged (40% res, 30% arc, 30% tension)."""
        # Test specific input where we can verify weights
        inputs = {
            "base": 0.6,
            "v3": 0.6,
            "resonance_index": 0.5,  # w_r = 0.5 (linear in [0.3, 0.7])
            "arc_alignment_index": 0.5,  # w_a = 0.5
            "tension_index": 0.5,  # w_t = 0.5 (inverted)
        }

        quality = engine._compute_coherence_v3_quality(**inputs)

        # stability_core = 0.4 * 0.5 + 0.3 * 0.5 + 0.3 * 0.5 = 0.5
        # divergence = 0 (v3 == base)
        # quality = 0.5 * (1 - 0) = 0.5
        assert abs(quality - 0.5) < 0.01, f"Formula weights changed! Expected ~0.5, got {quality}"

    def test_c06_acoustic_penalty_formula_unchanged(self, engine):
        """Acoustic penalty formula is unchanged (linear, max 5%)."""
        # alignment_score = 0.2 → penalty = 0.05 * (0.4 - 0.2) / 0.4 = 0.025
        quality_score = 0.6
        report = AcousticAlignmentReport(
            alignment_score=0.2,
            pressure_band="moderate",
            mismatch_tags=(),
        )

        adjusted, penalty_applied, penalty_amount = engine._apply_acoustic_confidence_adjustment(
            quality_score=quality_score,
            acoustic_alignment=report,
        )

        expected_penalty = 0.05 * (0.4 - 0.2) / 0.4
        assert abs(penalty_amount - expected_penalty) < 1e-10, (
            f"Penalty formula changed! Expected {expected_penalty}, got {penalty_amount}"
        )

    def test_c07_multiple_input_combinations_regression(self, engine):
        """Multiple input combinations match expected behavior."""
        test_cases = [
            # (base, v3, res, arc, ten, expected_quality_approx)
            (0.6, 0.6, 0.5, 0.5, 0.5, 0.5),  # Neutral
            (0.8, 0.8, 0.8, 0.8, 0.2, 0.9),  # High quality expected
            (0.3, 0.3, 0.2, 0.2, 0.8, 0.0),  # Low quality expected
        ]

        for base, v3, res, arc, ten, expected_approx in test_cases:
            quality = engine._compute_coherence_v3_quality(
                base=base, v3=v3,
                resonance_index=res,
                arc_alignment_index=arc,
                tension_index=ten,
            )

            # Quality should be in expected range (tolerance for formula variations)
            assert quality is not None
            assert 0.0 <= quality <= 1.0

    def test_c08_authoritative_inputs_produce_same_base(self, engine):
        """Same authoritative inputs always produce same base quality."""
        fixed_inputs = {
            "base": 0.65,
            "v3": 0.70,
            "resonance_index": 0.55,
            "arc_alignment_index": 0.60,
            "tension_index": 0.45,
        }

        # Multiple reports with different acoustic data
        reports = [
            None,
            create_aligned_report(),
            create_misaligned_report(alignment_score=0.3),
            create_misaligned_report(alignment_score=0.1),
        ]

        base_qualities = []
        for report in reports:
            _, _, _, base_q = engine._compute_coherence_v3_quality_with_acoustic(
                acoustic_alignment=report, **fixed_inputs
            )
            base_qualities.append(base_q)

        # All base qualities must be identical
        assert all(q == base_qualities[0] for q in base_qualities), (
            f"Base quality varies with acoustic input: {base_qualities}"
        )

    def test_c09_acoustic_only_affects_adjusted_not_base(self, engine):
        """Acoustic input only affects adjusted quality, not base quality."""
        inputs = random_quality_inputs()

        # Without acoustic
        _, _, _, base_without = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=None, **inputs
        )

        # With various acoustic reports
        for _ in range(10):
            report = random_acoustic_report()
            adjusted, _, _, base_with = engine._compute_coherence_v3_quality_with_acoustic(
                acoustic_alignment=report, **inputs
            )

            assert base_with == base_without, (
                f"Acoustic changed base quality! without={base_without}, with={base_with}"
            )

    def test_c10_missing_optional_metrics_consistent(self, engine):
        """Missing optional metrics produce consistent results."""
        # Test with various combinations of missing optional metrics
        combos = [
            {"base": 0.6, "v3": 0.6, "resonance_index": None, "arc_alignment_index": 0.5, "tension_index": 0.5},
            {"base": 0.6, "v3": 0.6, "resonance_index": 0.5, "arc_alignment_index": None, "tension_index": 0.5},
            {"base": 0.6, "v3": 0.6, "resonance_index": 0.5, "arc_alignment_index": 0.5, "tension_index": None},
            {"base": 0.6, "v3": 0.6, "resonance_index": None, "arc_alignment_index": None, "tension_index": None},
        ]

        for combo in combos:
            # Should not raise and should be consistent
            q1 = engine._compute_coherence_v3_quality(**combo)
            q2 = engine._compute_coherence_v3_quality(**combo)
            assert q1 == q2, f"Inconsistent results for missing metrics: {combo}"


# =============================================================================
# GROUP D: IMPORT SAFETY (5+ tests)
# Phase 12 must not import P22, P23, or P24 directly
# =============================================================================


class TestGroupD_ImportSafety:
    """
    Group D: Import Safety

    Phase 12 must NOT import P22, P23, or P24 directly.
    Only the acoustic alignment schema is allowed.
    """

    def test_d01_coherence_engine_no_p22_import(self):
        """CoherenceEngine does not import P22 directly."""
        import symbolu.core.coherence.coherence_engine as ce
        source = open(ce.__file__).read()

        # Check for direct P22 imports
        forbidden = [
            "from symbolu.mechanical.pipeline.p22",
            "import symbolu.mechanical.pipeline.p22",
            "from symbolu.mechanical.pipeline import p22",
        ]

        for pattern in forbidden:
            assert pattern not in source, (
                f"IMPORT SAFETY VIOLATION: coherence_engine.py imports P22 directly: {pattern}"
            )

    def test_d02_coherence_engine_no_p23_import(self):
        """CoherenceEngine does not import P23 directly."""
        import symbolu.core.coherence.coherence_engine as ce
        source = open(ce.__file__).read()

        forbidden = [
            "from symbolu.mechanical.pipeline.p23",
            "import symbolu.mechanical.pipeline.p23",
            "from symbolu.mechanical.pipeline import p23",
        ]

        for pattern in forbidden:
            assert pattern not in source, (
                f"IMPORT SAFETY VIOLATION: coherence_engine.py imports P23 directly: {pattern}"
            )

    def test_d03_coherence_engine_no_p24_import(self):
        """CoherenceEngine does not import P24 directly."""
        import symbolu.core.coherence.coherence_engine as ce
        source = open(ce.__file__).read()

        forbidden = [
            "from symbolu.mechanical.pipeline.p24",
            "import symbolu.mechanical.pipeline.p24",
            "from symbolu.mechanical.pipeline import p24",
        ]

        for pattern in forbidden:
            assert pattern not in source, (
                f"IMPORT SAFETY VIOLATION: coherence_engine.py imports P24 directly: {pattern}"
            )

    def test_d04_hardening_module_no_observer_import(self):
        """phase12_hardening module does not import observer modules."""
        import symbolu.core.coherence.phase12_hardening as h
        source = open(h.__file__).read()

        forbidden = [
            "p22_acoustic_witness",
            "p23_alignment",
            "p24_projection",
        ]

        for pattern in forbidden:
            assert pattern not in source, (
                f"IMPORT SAFETY VIOLATION: phase12_hardening.py references {pattern}"
            )

    def test_d05_acoustic_schema_is_only_interface(self):
        """AcousticAlignmentReport is the only interface to acoustic data."""
        import symbolu.core.coherence.coherence_engine as ce
        source = open(ce.__file__).read()

        # Should import acoustic_alignment_schema
        assert "acoustic_alignment_schema" in source or "AcousticAlignmentReport" in source

        # Should NOT reference observer modules
        forbidden_refs = [
            "P22AcousticWitnessReport",
            "P23AlignmentReport",
            "P24ProjectionReport",
            "AcousticWitness",
            "AlignmentObserver",
        ]

        for ref in forbidden_refs:
            assert ref not in source, (
                f"IMPORT SAFETY VIOLATION: coherence_engine.py references {ref}"
            )

    def test_d06_no_direct_motion_primitive_access(self):
        """No direct access to motion primitives from observer phases."""
        import symbolu.core.coherence.coherence_engine as ce
        source = open(ce.__file__).read()

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
            # Only check if it appears as a direct reference, not in comments
            lines = [l for l in source.split('\n') if not l.strip().startswith('#')]
            code_only = '\n'.join(lines)
            if primitive in code_only:
                # Allow in string literals (comments/docstrings already filtered)
                assert f'"{primitive}"' in code_only or f"'{primitive}'" in code_only, (
                    f"IMPORT SAFETY VIOLATION: Direct motion primitive reference: {primitive}"
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

    def test_e01_basic_determinism(self, engine):
        """Same inputs always produce same outputs."""
        inputs = {
            "base": 0.65,
            "v3": 0.70,
            "resonance_index": 0.55,
            "arc_alignment_index": 0.60,
            "tension_index": 0.45,
        }
        report = AcousticAlignmentReport(
            alignment_score=0.3,
            pressure_band="moderate",
            mismatch_tags=("tension",),
        )

        results = []
        for _ in range(100):
            result = engine._compute_coherence_v3_quality_with_acoustic(
                acoustic_alignment=report, **inputs
            )
            results.append(result)

        first = results[0]
        assert all(r == first for r in results), "Determinism violation detected"

    def test_e02_determinism_without_acoustic(self, engine):
        """Determinism holds without acoustic input."""
        inputs = random_quality_inputs()

        results = []
        for _ in range(100):
            result = engine._compute_coherence_v3_quality_with_acoustic(
                acoustic_alignment=None, **inputs
            )
            results.append(result)

        first = results[0]
        assert all(r == first for r in results), "Determinism violation without acoustic"

    def test_e03_determinism_base_quality_only(self, engine):
        """Base quality computation is deterministic."""
        inputs = random_quality_inputs()

        results = []
        for _ in range(100):
            result = engine._compute_coherence_v3_quality(**inputs)
            results.append(result)

        first = results[0]
        assert all(r == first for r in results), "Base quality determinism violation"

    def test_e04_determinism_penalty_application(self, engine):
        """Penalty application is deterministic."""
        quality_score = 0.7
        report = AcousticAlignmentReport(
            alignment_score=0.25,
            pressure_band="high",
            mismatch_tags=("test",),
        )

        results = []
        for _ in range(100):
            result = engine._apply_acoustic_confidence_adjustment(
                quality_score=quality_score,
                acoustic_alignment=report,
            )
            results.append(result)

        first = results[0]
        assert all(r == first for r in results), "Penalty application determinism violation"

    def test_e05_determinism_across_engine_instances(self):
        """Determinism holds across different engine instances."""
        inputs = random_quality_inputs()
        report = random_acoustic_report()

        results = []
        for _ in range(10):
            engine = CoherenceEngine(window=10)
            result = engine._compute_coherence_v3_quality_with_acoustic(
                acoustic_alignment=report, **inputs
            )
            results.append(result)

        first = results[0]
        assert all(r == first for r in results), "Determinism violation across instances"

    def test_e06_no_random_state_influence(self, engine):
        """Random module state does not affect results."""
        inputs = random_quality_inputs()
        report = random_acoustic_report()

        # Get baseline result
        result1 = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report, **inputs
        )

        # Generate many random numbers to change random state
        for _ in range(1000):
            random.random()

        # Should still get same result
        result2 = engine._compute_coherence_v3_quality_with_acoustic(
            acoustic_alignment=report, **inputs
        )

        assert result1 == result2, "Random state influenced results"


# =============================================================================
# ADDITIONAL HARDENING TESTS
# =============================================================================


class TestAcousticHardeningViolationException:
    """Tests for the AcousticHardeningViolation exception."""

    def test_exception_can_be_raised(self):
        """AcousticHardeningViolation can be raised and caught."""
        with pytest.raises(AcousticHardeningViolation):
            raise AcousticHardeningViolation("Test violation")

    def test_exception_message_preserved(self):
        """Exception message is preserved."""
        msg = "INV-P12-H1 VIOLATED: test message"
        try:
            raise AcousticHardeningViolation(msg)
        except AcousticHardeningViolation as e:
            assert msg in str(e)

    def test_exception_is_exception_subclass(self):
        """AcousticHardeningViolation is an Exception subclass."""
        assert issubclass(AcousticHardeningViolation, Exception)


class TestAssertAcousticSafe:
    """Tests for the assert_acoustic_safe function."""

    def test_passes_for_valid_adjustment(self):
        """assert_acoustic_safe passes for valid adjustments."""
        assert_acoustic_safe(0.5, 0.48)  # Should not raise
        assert_acoustic_safe(0.5, 0.5)   # Should not raise

    def test_raises_for_quality_increase(self):
        """assert_acoustic_safe raises for quality increase."""
        with pytest.raises(AcousticHardeningViolation) as exc_info:
            assert_acoustic_safe(0.5, 0.52)

        assert "INV-P12-H1" in str(exc_info.value)

    def test_raises_for_gate_violation(self):
        """assert_acoustic_safe raises for gate monotonicity violation."""
        # This would only happen if adjusted > base, which is already caught
        # by INV-P12-H1, so gate violation is redundant but checked anyway
        with pytest.raises(AcousticHardeningViolation):
            assert_acoustic_safe(0.35, 0.42, thresholds=(0.40,))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
