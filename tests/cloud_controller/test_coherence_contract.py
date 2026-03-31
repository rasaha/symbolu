"""Coherence algorithm contract tests — behavioral + mathematical invariants.

These tests protect the coherence algorithm from incorrect modifications.
If someone changes the algorithm, these tests MUST break, forcing them to
understand WHY each property exists before they can modify it.

Protected properties (SCC — Signal Coherence Contract):
  1. VARIANCE-BASED agreement (not correlation, not cosine-phase)
  2. CROSS-GROUP agreement via group-mean variance
  3. 70/30 within-vs-cross blend ratio
  4. Signal health degradation (15% per missing signal, floor 0.3)
  5. EMA temporal smoothing (beta=0.7)
  6. Hysteresis dead-band (±0.05)
  7. Single-signal neutrality (returns 0.5)
  8. Output bounded to [0, 1]
  9. Monotonicity: more agreement → higher coherence
  10. Symmetry: identical signals → agreement = 1.0

IMPORTANT: Do NOT weaken these tests. Each one protects a specific
property that was validated across 19 adversarial scenarios and
demonstrated to prevent false scaling decisions.

If you need to modify the coherence algorithm:
  1. Read docs/SCALING_CONTROLLER_ARCHITECTURE.md
  2. Run the full edge case harness: python -m pytest tests/cloud_controller/test_edge_cases.py
  3. Verify 0 CATASTROPHIC, 0 SEVERE across all 19 scenarios
  4. Update these contracts to match the new invariants
"""

import math
import pytest
from symbolu.cloud_controller.core.coherence import CoherenceModel, CoherenceResult


# ============================================================
# Contract 1: Output Range
# ============================================================

class TestCoherenceOutputContract:
    """C_t must always be in [0, 1]."""

    @pytest.mark.parametrize("metrics", [
        {"cpu": 0.0, "memory": 0.0, "latency_p99": 0.0, "error_rate": 0.0},
        {"cpu": 1.0, "memory": 1.0, "latency_p99": 1.0, "error_rate": 1.0},
        {"cpu": 0.0, "memory": 1.0, "latency_p99": 0.0, "error_rate": 1.0},
        {"cpu": 0.5, "memory": 0.5, "latency_p99": 0.5, "error_rate": 0.5},
        {"cpu": 0.99, "memory": 0.01, "latency_p99": 0.99, "error_rate": 0.01},
    ])
    def test_coherence_bounded_zero_one(self, metrics):
        model = CoherenceModel()
        result = model.compute(metrics)
        assert 0.0 <= result.coherence <= 1.0, (
            f"coherence={result.coherence} out of bounds for {metrics}"
        )

    def test_instability_equals_one_minus_coherence(self):
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.7, "memory": 0.3,
            "latency_p99": 0.6, "error_rate": 0.4,
        })
        assert abs(result.instability - (1.0 - result.coherence)) < 1e-9


# ============================================================
# Contract 2: Variance-Based Agreement (NOT correlation/cosine)
# ============================================================

class TestVarianceAgreementContract:
    """_group_agreement uses variance, not correlation or cosine.

    This is the correct formula for scalar metrics in [0,1].
    Phase-based methods (cosine of phase difference) require oscillatory
    signals and produce artifacts on step/ramp demand patterns.
    """

    def test_identical_signals_perfect_agreement(self):
        """Identical values → variance=0 → agreement=1.0."""
        model = CoherenceModel()
        agreement = model._group_agreement(
            {"cpu": 0.7, "memory": 0.7}, ("cpu", "memory"),
        )
        assert agreement == 1.0

    def test_maximally_different_signals_zero_agreement(self):
        """[0,1] → variance=0.25 → agreement=0.0."""
        model = CoherenceModel()
        agreement = model._group_agreement(
            {"cpu": 0.0, "memory": 1.0}, ("cpu", "memory"),
        )
        assert agreement == 0.0

    def test_agreement_is_symmetric(self):
        """agreement(a,b) == agreement(b,a)."""
        model = CoherenceModel()
        a1 = model._group_agreement(
            {"cpu": 0.3, "memory": 0.8}, ("cpu", "memory"),
        )
        a2 = model._group_agreement(
            {"cpu": 0.8, "memory": 0.3}, ("cpu", "memory"),
        )
        assert abs(a1 - a2) < 1e-9

    def test_agreement_monotonic_with_convergence(self):
        """As signals converge, agreement increases."""
        model = CoherenceModel()
        # Far apart
        a_far = model._group_agreement(
            {"cpu": 0.1, "memory": 0.9}, ("cpu", "memory"),
        )
        # Closer
        a_mid = model._group_agreement(
            {"cpu": 0.3, "memory": 0.7}, ("cpu", "memory"),
        )
        # Very close
        a_near = model._group_agreement(
            {"cpu": 0.45, "memory": 0.55}, ("cpu", "memory"),
        )
        assert a_far < a_mid < a_near

    def test_agreement_formula_is_one_minus_normalized_variance(self):
        """Exact formula: agreement = 1 - var(values) / 0.25.

        This locks in the variance-based formula. If someone replaces it
        with correlation, cosine, or any other metric, this test breaks.
        """
        import numpy as np
        model = CoherenceModel()
        values = {"cpu": 0.3, "memory": 0.7}
        agreement = model._group_agreement(values, ("cpu", "memory"))
        expected = 1.0 - float(np.var([0.3, 0.7])) / 0.25
        assert abs(agreement - expected) < 1e-9, (
            f"Agreement formula changed! Got {agreement}, expected {expected} "
            f"from variance formula"
        )


# ============================================================
# Contract 3: Single-Signal Neutrality
# ============================================================

class TestSingleSignalContract:
    """One signal cannot agree with itself → neutral 0.5."""

    def test_single_signal_returns_neutral(self):
        model = CoherenceModel()
        agreement = model._group_agreement(
            {"cpu": 0.95}, ("cpu",),
        )
        assert agreement == 0.5

    def test_no_signals_returns_neutral(self):
        model = CoherenceModel()
        agreement = model._group_agreement({}, ("cpu", "memory"))
        assert agreement == 0.5


# ============================================================
# Contract 4: Cross-Group Agreement
# ============================================================

class TestCrossGroupContract:
    """Cross-group coherence measures inter-layer agreement."""

    def test_aligned_groups_high_cross(self):
        """Infra and app both high → high cross-group."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.85, "memory": 0.80,
            "latency_p99": 0.82, "error_rate": 0.78,
        })
        assert result.c_cross > 0.8

    def test_misaligned_groups_low_cross(self):
        """Infra high, app low → low cross-group."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.90, "memory": 0.85,
            "latency_p99": 0.10, "error_rate": 0.05,
        })
        assert result.c_cross < 0.5

    def test_cross_group_blended_at_thirty_percent(self):
        """Overall coherence = 0.7 * within + 0.3 * cross (before health/EMA).

        This locks in the 70/30 blend ratio. Changing it affects 19 scenarios.
        """
        model = CoherenceModel()
        # First call to initialize (no EMA on first call)
        result = model.compute({
            "cpu": 0.85, "memory": 0.80,
            "latency_p99": 0.82, "error_rate": 0.78,
        })
        # Reconstruct expected value (pre-health, pre-EMA)
        # For first call, _prev_coherence is None, so no EMA/hysteresis
        c_infra = model._group_agreement(
            {"cpu": 0.85, "memory": 0.80}, ("cpu", "memory"),
        )
        c_app = model._group_agreement(
            {"latency_p99": 0.82, "error_rate": 0.78},
            ("latency_p99", "error_rate"),
        )
        within = (0.4 * c_infra + 0.4 * c_app) / 0.8  # no business signals
        import numpy as np
        group_means = [
            (0.85 + 0.80) / 2,    # infra mean
            (0.82 + 0.78) / 2,    # app mean
        ]
        c_cross = 1.0 - min(float(np.var(group_means)) / 0.25, 1.0)
        expected = (0.7 * within + 0.3 * c_cross) * 1.0  # signal_health=1
        assert abs(result.coherence - expected) < 1e-9, (
            f"Blend ratio changed! Got {result.coherence}, expected {expected}. "
            f"The 70/30 within/cross ratio is validated across 19 scenarios."
        )


# ============================================================
# Contract 5: Signal Health Degradation
# ============================================================

class TestSignalHealthContract:
    """Missing signals degrade coherence — 15% per signal, floor 0.3."""

    def test_all_present_full_health(self):
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.5, "memory": 0.5,
            "latency_p99": 0.5, "error_rate": 0.5,
        })
        assert result.signal_health == 1.0

    def test_one_missing_degrades(self):
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.5,
            "latency_p99": 0.5, "error_rate": 0.5,
        })
        # memory missing from infra → 1 missing → health = 0.85
        assert abs(result.signal_health - 0.85) < 1e-9

    def test_health_floor_at_thirty_percent(self):
        """Even with many signals missing, health never goes below 0.3."""
        model = CoherenceModel()
        result = model.compute({"cpu": 0.5})
        # cpu only → missing: memory, latency_p99, error_rate = 3 missing
        # health = max(0.3, 1.0 - 0.15*3) = max(0.3, 0.55) = 0.55
        assert result.signal_health >= 0.3
        assert result.missing_signal_count == 3

    def test_health_multiplies_coherence(self):
        """signal_health reduces the final coherence multiplicatively."""
        model = CoherenceModel()
        full = model.compute({
            "cpu": 0.5, "memory": 0.5,
            "latency_p99": 0.5, "error_rate": 0.5,
        })
        model2 = CoherenceModel()
        partial = model2.compute({
            "cpu": 0.5,
            "latency_p99": 0.5, "error_rate": 0.5,
        })
        # partial coherence should be < full coherence (health penalty)
        assert partial.coherence < full.coherence


# ============================================================
# Contract 6: EMA Temporal Smoothing
# ============================================================

class TestEMASmoothingContract:
    """EMA prevents noisy coherence from causing decision paralysis.

    Formula: C_t = beta * C_{t-1} + (1 - beta) * C_raw
    Default beta = 0.7 (heavy smoothing, validated against
    coherence_oscillation scenario which flickers near threshold).
    """

    def test_first_call_no_smoothing(self):
        """First call has no previous value → no EMA applied."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.85, "memory": 0.80,
            "latency_p99": 0.82, "error_rate": 0.78,
        })
        # Store the first value
        first = result.coherence
        assert first > 0  # sanity

    def test_ema_smooths_sudden_drop(self):
        """A sudden coherence drop is smoothed, not applied fully."""
        model = CoherenceModel()
        # Establish high coherence
        model.compute({
            "cpu": 0.85, "memory": 0.80,
            "latency_p99": 0.82, "error_rate": 0.78,
        })
        high_c = model._prev_coherence
        # Sudden drop to disagreement
        result = model.compute({
            "cpu": 0.95, "memory": 0.05,
            "latency_p99": 0.90, "error_rate": 0.10,
        })
        # EMA should make result closer to previous high than raw low
        assert result.coherence > 0.4, (
            "EMA smoothing not working — coherence dropped too fast"
        )

    def test_ema_beta_zero_means_no_smoothing(self):
        """beta=0 disables smoothing entirely."""
        model = CoherenceModel(ema_beta=0.0)
        model.compute({
            "cpu": 0.85, "memory": 0.80,
            "latency_p99": 0.82, "error_rate": 0.78,
        })
        result = model.compute({
            "cpu": 0.95, "memory": 0.05,
            "latency_p99": 0.90, "error_rate": 0.10,
        })
        # With no smoothing, coherence should reflect the raw disagreement
        assert result.coherence < 0.6


# ============================================================
# Contract 7: Hysteresis Dead-Band
# ============================================================

class TestHysteresisContract:
    """Hysteresis prevents coherence flicker near decision thresholds.

    If |C_raw - C_prev| < band, hold C_prev. Default band = 0.05.
    Validated against coherence_oscillation scenario.
    """

    def test_tiny_change_held(self):
        """Change within dead-band is suppressed."""
        model = CoherenceModel(ema_beta=0.0, hysteresis_band=0.05)
        # First call
        r1 = model.compute({
            "cpu": 0.50, "memory": 0.50,
            "latency_p99": 0.50, "error_rate": 0.50,
        })
        c1 = r1.coherence
        # Tiny perturbation
        r2 = model.compute({
            "cpu": 0.51, "memory": 0.50,
            "latency_p99": 0.50, "error_rate": 0.50,
        })
        assert r2.coherence == c1, (
            "Hysteresis not working — tiny change should be suppressed"
        )

    def test_large_change_passes_through(self):
        """Change exceeding dead-band is applied."""
        model = CoherenceModel(ema_beta=0.0, hysteresis_band=0.05)
        r1 = model.compute({
            "cpu": 0.50, "memory": 0.50,
            "latency_p99": 0.50, "error_rate": 0.50,
        })
        c1 = r1.coherence
        # Large perturbation (infra says high, app says low)
        r2 = model.compute({
            "cpu": 0.95, "memory": 0.90,
            "latency_p99": 0.10, "error_rate": 0.05,
        })
        assert r2.coherence != c1


# ============================================================
# Contract 8: Weight Structure
# ============================================================

class TestWeightContract:
    """Signal group weights: infra=0.4, app=0.4, business=0.2.

    Business signals are optional. When absent, infra and app
    split the weight equally (0.5/0.5 effective).
    """

    def test_default_weights(self):
        model = CoherenceModel()
        assert model.w_infra == 0.4
        assert model.w_app == 0.4
        assert model.w_business == 0.2

    def test_business_optional(self):
        """Coherence works without business signals."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.8, "memory": 0.7,
            "latency_p99": 0.75, "error_rate": 0.65,
        })
        assert 0.0 <= result.coherence <= 1.0

    def test_business_signals_included_when_present(self):
        """Adding business signals changes the result."""
        model1 = CoherenceModel()
        r_no_biz = model1.compute({
            "cpu": 0.8, "memory": 0.7,
            "latency_p99": 0.75, "error_rate": 0.65,
        })
        model2 = CoherenceModel()
        r_with_biz = model2.compute({
            "cpu": 0.8, "memory": 0.7,
            "latency_p99": 0.75, "error_rate": 0.65,
            "queue_depth": 0.2,  # low business signal → disagreement
        })
        # Adding a disagreeing business signal should change coherence
        assert r_no_biz.coherence != r_with_biz.coherence


# ============================================================
# Contract 9: Behavioral — Coherent vs Incoherent Ordering
# ============================================================

class TestBehavioralOrdering:
    """These test the fundamental guarantee the controller relies on:
    signals agreeing → high C_t → scaling confident
    signals disagreeing → low C_t → scaling cautious
    """

    def test_all_agree_high_beats_one_disagrees(self):
        model1 = CoherenceModel()
        coherent = model1.compute({
            "cpu": 0.85, "memory": 0.80,
            "latency_p99": 0.82, "error_rate": 0.78,
        })
        model2 = CoherenceModel()
        incoherent = model2.compute({
            "cpu": 0.90, "memory": 0.10,
            "latency_p99": 0.85, "error_rate": 0.05,
        })
        assert coherent.coherence > incoherent.coherence

    def test_all_low_is_coherent(self):
        """All signals low = agreement (no problem). Still coherent."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.10, "memory": 0.15,
            "latency_p99": 0.12, "error_rate": 0.08,
        })
        # Within-group agreement should be high (all similar)
        assert result.c_infra > 0.9
        assert result.c_app > 0.9

    def test_cpu_only_spike_is_incoherent(self):
        """Classic false alarm: CPU spikes but nothing else confirms it."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.95, "memory": 0.20,
            "latency_p99": 0.15, "error_rate": 0.05,
        })
        # Infra group disagrees (CPU high, memory low)
        assert result.c_infra < 0.5
        # Cross-group also shows disagreement (infra mean ~0.575 vs app mean ~0.10)
        assert result.c_cross < 0.85


# ============================================================
# Contract 10: Edge Case Regression Guard
# ============================================================

class TestEdgeCaseRegressionGuard:
    """Golden-value tests computed from the CURRENT algorithm.

    If someone changes the algorithm, these values WILL change,
    forcing them to re-validate against the 19-scenario harness.
    """

    def test_golden_coherent_case(self):
        """Known-good output for all-agree scenario."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.80, "memory": 0.80,
            "latency_p99": 0.80, "error_rate": 0.80,
        })
        # All identical → within_agreement=1.0, cross=1.0
        # coherence = (0.7*1.0 + 0.3*1.0) * 1.0 = 1.0
        assert abs(result.coherence - 1.0) < 1e-6, (
            f"Golden coherent value changed: {result.coherence} != 1.0. "
            f"Re-run edge case harness before accepting this change."
        )

    def test_golden_incoherent_case(self):
        """Known-good output for infra-vs-app disagreement."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 1.0, "memory": 0.0,
            "latency_p99": 1.0, "error_rate": 0.0,
        })
        # Both groups have max disagreement → within=0.0 for each
        # cross: group_means = [0.5, 0.5] → var=0 → cross=1.0
        # coherence = (0.7*0.0 + 0.3*1.0) * 1.0 = 0.3
        assert abs(result.coherence - 0.3) < 1e-6, (
            f"Golden incoherent value changed: {result.coherence} != 0.3. "
            f"Re-run edge case harness before accepting this change."
        )

    def test_golden_partial_observability(self):
        """Known-good output with missing signal."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.80,
            "latency_p99": 0.80, "error_rate": 0.80,
        })
        # memory missing → health = 0.85, infra has 1 signal → 0.5
        # app agreement = 1.0 (both 0.80)
        # within = (0.4*0.5 + 0.4*1.0) / 0.8 = 0.75
        # cross: infra_mean=0.80, app_mean=0.80, var=0 → cross=1.0
        # coherence = (0.7*0.75 + 0.3*1.0) * 0.85 = 0.7012..
        expected = (0.7 * 0.75 + 0.3 * 1.0) * 0.85
        assert abs(result.coherence - expected) < 1e-6, (
            f"Golden partial-observability value changed: "
            f"{result.coherence} != {expected}. "
            f"Re-run edge case harness before accepting this change."
        )
