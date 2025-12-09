"""
Phase 1 Resonance Formulas - Drift Test Suite
==============================================

Comprehensive deterministic tests for Phase 1 temporal formulas:
- SMI (Symbolic Mental Index)
- ΔSMI (delta SMI)
- Bhava Gap
- Tension Corridor

Test Categories:
1. Range tests: Verify all outputs stay within valid bounds
2. Monotonicity tests: Verify expected behavior under input changes
3. Determinism tests: Verify same input produces same output
4. Drift fixture tests: Verify canonical outputs match saved fixtures

Version: 1.0
Date: 2025-12-09
"""

import pytest
from symbolu.formulas.resonance_formulas import (
    compute_smi,
    compute_delta_smi,
    compute_bhava_gap,
    compute_tension_corridor,
)


# =============================================================================
# 1. RANGE TESTS
# =============================================================================


class TestSMIRange:
    """Test that SMI always stays in [0.0, 1.0] range."""

    def test_smi_range_min_inputs(self):
        """Test SMI with minimum inputs."""
        smi = compute_smi(0.0, 0.0, 0.0)
        assert 0.0 <= smi <= 1.0, f"SMI out of range: {smi}"

    def test_smi_range_max_inputs(self):
        """Test SMI with maximum inputs."""
        smi = compute_smi(1.0, 1.0, 1.0)
        assert 0.0 <= smi <= 1.0, f"SMI out of range: {smi}"

    def test_smi_range_mixed_inputs(self):
        """Test SMI with various mixed inputs."""
        test_cases = [
            (0.5, 0.5, 0.5),
            (0.0, 0.5, 1.0),
            (1.0, 0.5, 0.0),
            (0.3, 0.7, 0.2),
            (0.8, 0.1, 0.9),
        ]
        for dim_res, vrtti_int, bhava_pos in test_cases:
            smi = compute_smi(dim_res, vrtti_int, bhava_pos)
            assert 0.0 <= smi <= 1.0, f"SMI out of range for inputs ({dim_res}, {vrtti_int}, {bhava_pos}): {smi}"

    def test_smi_invalid_inputs_raise_error(self):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            compute_smi(-0.1, 0.5, 0.5)  # negative dimensional_resonance

        with pytest.raises(ValueError):
            compute_smi(0.5, 1.1, 0.5)  # vrtti_intensity > 1.0

        with pytest.raises(ValueError):
            compute_smi(0.5, 0.5, -0.1)  # negative bhava_position


class TestDeltaSMIRange:
    """Test that ΔSMI always stays in [-1.0, 1.0] range."""

    def test_delta_smi_range_max_increase(self):
        """Test ΔSMI with maximum increase."""
        delta = compute_delta_smi(1.0, 0.0)
        assert -1.0 <= delta <= 1.0, f"ΔSMI out of range: {delta}"

    def test_delta_smi_range_max_decrease(self):
        """Test ΔSMI with maximum decrease."""
        delta = compute_delta_smi(0.0, 1.0)
        assert -1.0 <= delta <= 1.0, f"ΔSMI out of range: {delta}"

    def test_delta_smi_range_no_change(self):
        """Test ΔSMI with no change."""
        delta = compute_delta_smi(0.5, 0.5)
        assert -1.0 <= delta <= 1.0, f"ΔSMI out of range: {delta}"

    def test_delta_smi_range_first_turn(self):
        """Test ΔSMI with no previous value (first turn)."""
        delta = compute_delta_smi(0.7, None)
        assert -1.0 <= delta <= 1.0, f"ΔSMI out of range: {delta}"
        assert delta == 0.0, f"ΔSMI should be 0.0 on first turn, got {delta}"

    def test_delta_smi_invalid_inputs_raise_error(self):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            compute_delta_smi(1.5, 0.5)  # smi > 1.0

        with pytest.raises(ValueError):
            compute_delta_smi(0.5, -0.1)  # previous_smi < 0.0


class TestBhavaGapRange:
    """Test that Bhava Gap always stays in [0.0, 1.0] range."""

    def test_bhava_gap_range_same_bhava(self):
        """Test Bhava Gap with same bhava."""
        gap = compute_bhava_gap(5, 5)
        assert 0.0 <= gap <= 1.0, f"Bhava Gap out of range: {gap}"
        assert gap == 0.0, f"Bhava Gap should be 0.0 for same bhava, got {gap}"

    def test_bhava_gap_range_adjacent_bhava(self):
        """Test Bhava Gap with adjacent bhava."""
        gap = compute_bhava_gap(5, 6)
        assert 0.0 <= gap <= 1.0, f"Bhava Gap out of range: {gap}"

    def test_bhava_gap_range_opposite_bhava(self):
        """Test Bhava Gap with opposite bhava (max distance)."""
        gap = compute_bhava_gap(0, 6)
        assert 0.0 <= gap <= 1.0, f"Bhava Gap out of range: {gap}"

    def test_bhava_gap_range_first_turn(self):
        """Test Bhava Gap with no previous bhava (first turn)."""
        gap = compute_bhava_gap(5, None)
        assert 0.0 <= gap <= 1.0, f"Bhava Gap out of range: {gap}"
        assert gap == 0.0, f"Bhava Gap should be 0.0 on first turn, got {gap}"

    def test_bhava_gap_invalid_inputs_raise_error(self):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            compute_bhava_gap(12, 5)  # current_bhava > 11

        with pytest.raises(ValueError):
            compute_bhava_gap(5, -1)  # previous_bhava < 0


class TestTensionCorridorRange:
    """Test that Tension Corridor always stays in [0.0, 1.0] range."""

    def test_tension_corridor_range_zero_inputs(self):
        """Test Tension Corridor with zero inputs."""
        tc = compute_tension_corridor(0.0, 0.0)
        assert 0.0 <= tc <= 1.0, f"Tension Corridor out of range: {tc}"

    def test_tension_corridor_range_max_inputs(self):
        """Test Tension Corridor with maximum inputs."""
        tc = compute_tension_corridor(1.0, 1.0)
        assert 0.0 <= tc <= 1.0, f"Tension Corridor out of range: {tc}"

    def test_tension_corridor_range_negative_delta(self):
        """Test Tension Corridor with negative delta_smi."""
        tc = compute_tension_corridor(-1.0, 0.5)
        assert 0.0 <= tc <= 1.0, f"Tension Corridor out of range: {tc}"

    def test_tension_corridor_range_mixed_inputs(self):
        """Test Tension Corridor with various mixed inputs."""
        test_cases = [
            (0.5, 0.5),
            (-0.5, 0.5),
            (0.3, 0.7),
            (-0.8, 0.2),
        ]
        for delta, gap in test_cases:
            tc = compute_tension_corridor(delta, gap)
            assert 0.0 <= tc <= 1.0, f"Tension Corridor out of range for inputs ({delta}, {gap}): {tc}"

    def test_tension_corridor_invalid_inputs_raise_error(self):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            compute_tension_corridor(1.5, 0.5)  # delta_smi > 1.0

        with pytest.raises(ValueError):
            compute_tension_corridor(0.5, 1.5)  # bhava_gap > 1.0


# =============================================================================
# 2. MONOTONICITY TESTS
# =============================================================================


class TestSMIMonotonicity:
    """Test that SMI increases/decreases monotonically with inputs."""

    def test_smi_increases_with_dimensional_resonance(self):
        """Test that SMI increases as dimensional_resonance increases."""
        smi1 = compute_smi(0.3, 0.5, 0.5)
        smi2 = compute_smi(0.7, 0.5, 0.5)
        assert smi2 > smi1, f"SMI should increase with dimensional_resonance: {smi1} -> {smi2}"

    def test_smi_increases_with_vrtti_intensity(self):
        """Test that SMI increases as vrtti_intensity increases."""
        smi1 = compute_smi(0.5, 0.3, 0.5)
        smi2 = compute_smi(0.5, 0.7, 0.5)
        assert smi2 > smi1, f"SMI should increase with vrtti_intensity: {smi1} -> {smi2}"

    def test_smi_increases_with_bhava_position(self):
        """Test that SMI increases as bhava_position increases."""
        smi1 = compute_smi(0.5, 0.5, 0.3)
        smi2 = compute_smi(0.5, 0.5, 0.7)
        assert smi2 > smi1, f"SMI should increase with bhava_position: {smi1} -> {smi2}"


class TestDeltaSMIMonotonicity:
    """Test that ΔSMI reflects SMI changes correctly."""

    def test_delta_smi_positive_when_increasing(self):
        """Test that ΔSMI is positive when SMI increases."""
        delta = compute_delta_smi(0.7, 0.3)
        assert delta > 0, f"ΔSMI should be positive when SMI increases: {delta}"

    def test_delta_smi_negative_when_decreasing(self):
        """Test that ΔSMI is negative when SMI decreases."""
        delta = compute_delta_smi(0.3, 0.7)
        assert delta < 0, f"ΔSMI should be negative when SMI decreases: {delta}"

    def test_delta_smi_zero_when_stable(self):
        """Test that ΔSMI is zero when SMI is stable."""
        delta = compute_delta_smi(0.5, 0.5)
        assert delta == 0.0, f"ΔSMI should be zero when SMI is stable: {delta}"


class TestTensionCorridorMonotonicity:
    """Test that Tension Corridor increases with inputs."""

    def test_tension_corridor_increases_with_delta_smi_magnitude(self):
        """Test that Tension Corridor increases as |ΔSMI| increases."""
        tc1 = compute_tension_corridor(0.2, 0.5)
        tc2 = compute_tension_corridor(0.8, 0.5)
        assert tc2 > tc1, f"Tension Corridor should increase with |ΔSMI|: {tc1} -> {tc2}"

        # Test with negative delta_smi
        tc3 = compute_tension_corridor(-0.2, 0.5)
        tc4 = compute_tension_corridor(-0.8, 0.5)
        assert tc4 > tc3, f"Tension Corridor should increase with |ΔSMI| (negative): {tc3} -> {tc4}"

    def test_tension_corridor_increases_with_bhava_gap(self):
        """Test that Tension Corridor increases as bhava_gap increases."""
        tc1 = compute_tension_corridor(0.5, 0.2)
        tc2 = compute_tension_corridor(0.5, 0.8)
        assert tc2 > tc1, f"Tension Corridor should increase with bhava_gap: {tc1} -> {tc2}"


# =============================================================================
# 3. DETERMINISM TESTS
# =============================================================================


class TestFormulasDeterminism:
    """Test that formulas are deterministic (same input -> same output)."""

    def test_smi_determinism(self):
        """Test that SMI produces same output for same input."""
        smi1 = compute_smi(0.5, 0.6, 0.7)
        smi2 = compute_smi(0.5, 0.6, 0.7)
        assert smi1 == smi2, f"SMI should be deterministic: {smi1} != {smi2}"

    def test_delta_smi_determinism(self):
        """Test that ΔSMI produces same output for same input."""
        delta1 = compute_delta_smi(0.7, 0.3)
        delta2 = compute_delta_smi(0.7, 0.3)
        assert delta1 == delta2, f"ΔSMI should be deterministic: {delta1} != {delta2}"

    def test_bhava_gap_determinism(self):
        """Test that Bhava Gap produces same output for same input."""
        gap1 = compute_bhava_gap(5, 8)
        gap2 = compute_bhava_gap(5, 8)
        assert gap1 == gap2, f"Bhava Gap should be deterministic: {gap1} != {gap2}"

    def test_tension_corridor_determinism(self):
        """Test that Tension Corridor produces same output for same input."""
        tc1 = compute_tension_corridor(0.5, 0.6)
        tc2 = compute_tension_corridor(0.5, 0.6)
        assert tc1 == tc2, f"Tension Corridor should be deterministic: {tc1} != {tc2}"


# =============================================================================
# 4. DRIFT FIXTURE TESTS
# =============================================================================


class TestDriftFixtures:
    """
    Test canonical outputs against saved fixtures.

    These tests use a 12-sample test grid to verify that formula
    outputs remain stable across code changes. If these tests fail,
    it indicates unintended drift in formula computations.
    """

    # Canonical test grid: 12 samples covering edge cases and typical values
    TEST_GRID = [
        # (dimensional_resonance, vrtti_intensity, bhava_position, current_bhava, previous_smi, previous_bhava)
        (0.0, 0.0, 0.0, 0, None, None),  # Sample 1: All zeros, first turn
        (1.0, 1.0, 1.0, 11, 0.5, 5),  # Sample 2: All ones
        (0.5, 0.5, 0.5, 5, 0.4, 4),  # Sample 3: All mid-values
        (0.3, 0.7, 0.2, 3, 0.6, 9),  # Sample 4: Mixed values
        (0.8, 0.2, 0.6, 8, 0.3, 2),  # Sample 5: Mixed values
        (0.1, 0.9, 0.4, 1, 0.8, 10),  # Sample 6: Mixed values
        (0.6, 0.4, 0.8, 6, 0.2, 0),  # Sample 7: Mixed values
        (0.9, 0.1, 0.3, 9, 0.7, 3),  # Sample 8: Mixed values
        (0.2, 0.6, 0.9, 2, 0.1, 11),  # Sample 9: Mixed values
        (0.7, 0.3, 0.1, 7, 0.9, 1),  # Sample 10: Mixed values
        (0.4, 0.8, 0.5, 4, 0.5, 6),  # Sample 11: Mixed values
        (0.5, 0.5, 0.7, 10, 0.4, 7),  # Sample 12: Mixed values
    ]

    # Canonical outputs (computed with v1.0 implementation)
    CANONICAL_OUTPUTS = [
        # (smi, delta_smi, bhava_gap, tension_corridor)
        (0.0, 0.0, 0.0, 0.0),  # Sample 1
        (1.0, 0.5, 1.0, 0.7),  # Sample 2
        (0.5, 0.09999999999999998, 0.16666666666666666, 0.12666666666666665),  # Sample 3
        (0.4, -0.19999999999999996, 1.0, 0.52),  # Sample 4
        (0.5800000000000001, 0.2800000000000001, 1.0, 0.5680000000000001),  # Sample 5
        (0.4, -0.4, 0.5, 0.44),  # Sample 6
        (0.5800000000000001, 0.38000000000000006, 1.0, 0.6280000000000001),  # Sample 7
        (0.54, -0.15999999999999992, 1.0, 0.496),  # Sample 8
        (0.4600000000000001, 0.3600000000000001, 0.5, 0.41600000000000004),  # Sample 9
        (0.45999999999999996, -0.44000000000000006, 1.0, 0.664),  # Sample 10
        (0.54, 0.040000000000000036, 0.3333333333333333, 0.15733333333333335),  # Sample 11
        (0.54, 0.14, 0.5, 0.28400000000000003),  # Sample 12
    ]

    def test_drift_fixtures_all_samples(self):
        """Test all samples in the canonical grid for drift."""
        for i, (test_input, expected_output) in enumerate(zip(self.TEST_GRID, self.CANONICAL_OUTPUTS)):
            dim_res, vrtti_int, bhava_pos, curr_bhava, prev_smi, prev_bhava = test_input
            expected_smi, expected_delta, expected_gap, expected_tc = expected_output

            # Compute formulas
            smi = compute_smi(dim_res, vrtti_int, bhava_pos)
            delta_smi = compute_delta_smi(smi, prev_smi)
            bhava_gap = compute_bhava_gap(curr_bhava, prev_bhava)
            tension_corridor = compute_tension_corridor(delta_smi, bhava_gap)

            # Assert approximate match (allow for floating-point precision)
            assert smi == pytest.approx(expected_smi, abs=1e-10), (
                f"Sample {i+1}: SMI drifted! Expected {expected_smi}, got {smi}\n"
                f"Inputs: dim_res={dim_res}, vrtti_int={vrtti_int}, bhava_pos={bhava_pos}"
            )

            assert delta_smi == pytest.approx(expected_delta, abs=1e-10), (
                f"Sample {i+1}: ΔSMI drifted! Expected {expected_delta}, got {delta_smi}\n"
                f"Inputs: smi={smi}, prev_smi={prev_smi}"
            )

            assert bhava_gap == pytest.approx(expected_gap, abs=1e-10), (
                f"Sample {i+1}: Bhava Gap drifted! Expected {expected_gap}, got {bhava_gap}\n"
                f"Inputs: curr_bhava={curr_bhava}, prev_bhava={prev_bhava}"
            )

            assert tension_corridor == pytest.approx(expected_tc, abs=1e-10), (
                f"Sample {i+1}: Tension Corridor drifted! Expected {expected_tc}, got {tension_corridor}\n"
                f"Inputs: delta_smi={delta_smi}, bhava_gap={bhava_gap}"
            )

    def test_drift_sample_1_detailed(self):
        """Detailed test for Sample 1 (all zeros, first turn)."""
        smi = compute_smi(0.0, 0.0, 0.0)
        delta_smi = compute_delta_smi(smi, None)
        bhava_gap = compute_bhava_gap(0, None)
        tension_corridor = compute_tension_corridor(delta_smi, bhava_gap)

        assert smi == 0.0
        assert delta_smi == 0.0
        assert bhava_gap == 0.0
        assert tension_corridor == 0.0

    def test_drift_sample_2_detailed(self):
        """Detailed test for Sample 2 (all ones)."""
        smi = compute_smi(1.0, 1.0, 1.0)
        delta_smi = compute_delta_smi(smi, 0.5)
        bhava_gap = compute_bhava_gap(11, 5)
        tension_corridor = compute_tension_corridor(delta_smi, bhava_gap)

        assert smi == 1.0
        assert delta_smi == 0.5
        assert bhava_gap == 1.0
        assert tension_corridor == 0.7


# =============================================================================
# 5. INTEGRATION TESTS
# =============================================================================


class TestFormulasIntegration:
    """Test formulas working together in realistic scenarios."""

    def test_complete_turn_sequence(self):
        """Test computing all formulas for a complete turn sequence."""
        # Turn 1
        smi1 = compute_smi(0.3, 0.5, 0.4)
        delta1 = compute_delta_smi(smi1, None)
        gap1 = compute_bhava_gap(3, None)
        tc1 = compute_tension_corridor(delta1, gap1)

        assert 0.0 <= smi1 <= 1.0
        assert delta1 == 0.0  # First turn
        assert gap1 == 0.0  # First turn
        assert tc1 == 0.0  # First turn

        # Turn 2
        smi2 = compute_smi(0.6, 0.7, 0.5)
        delta2 = compute_delta_smi(smi2, smi1)
        gap2 = compute_bhava_gap(5, 3)
        tc2 = compute_tension_corridor(delta2, gap2)

        assert 0.0 <= smi2 <= 1.0
        assert delta2 > 0  # SMI increased
        assert gap2 > 0  # Bhava changed
        assert tc2 > 0  # Tension present

        # Turn 3
        smi3 = compute_smi(0.4, 0.3, 0.3)
        delta3 = compute_delta_smi(smi3, smi2)
        gap3 = compute_bhava_gap(2, 5)
        tc3 = compute_tension_corridor(delta3, gap3)

        assert 0.0 <= smi3 <= 1.0
        assert delta3 < 0  # SMI decreased
        assert gap3 > 0  # Bhava changed
        assert tc3 > 0  # Tension present


# =============================================================================
# 6. EDGE CASE TESTS
# =============================================================================


class TestFormulasEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_bhava_gap_circular_distance(self):
        """Test that Bhava Gap uses shortest circular distance."""
        # Distance 11 -> 0 should be 1 (not 11)
        gap1 = compute_bhava_gap(0, 11)
        assert gap1 == pytest.approx(1.0 / 6.0), f"Expected {1.0/6.0}, got {gap1}"

        # Distance 0 -> 6 should be 6 (max distance)
        gap2 = compute_bhava_gap(6, 0)
        assert gap2 == 1.0, f"Expected 1.0, got {gap2}"

        # Distance 2 -> 10 should be 4 (not 8)
        gap3 = compute_bhava_gap(10, 2)
        assert gap3 == pytest.approx(4.0 / 6.0), f"Expected {4.0/6.0}, got {gap3}"

    def test_tension_corridor_symmetry_with_delta_sign(self):
        """Test that Tension Corridor is symmetric w.r.t. delta_smi sign."""
        tc_pos = compute_tension_corridor(0.5, 0.3)
        tc_neg = compute_tension_corridor(-0.5, 0.3)
        assert tc_pos == tc_neg, f"Tension Corridor should be symmetric: {tc_pos} != {tc_neg}"
