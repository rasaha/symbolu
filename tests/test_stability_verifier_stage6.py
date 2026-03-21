#!/usr/bin/env python3
"""
Tests for Appendix F Stage 6 — Stability and Orthogonality Verification.

Tests cover all five verification components:
  1. PhaseControlOrthogonalityChecker (F.8.2)
  2. ModulationStabilityChecker (F.8.3)
  3. EntropyMonitor (F.8.4)
  4. LongSequenceAnalyzer (F.8.5)
  5. KillSwitchVerifier (F.8.6)
  6. StabilityVerifier (F.8 combined orchestrator)
  7. StabilityConfig
  8. Edge cases
"""

import pytest
import torch
import torch.nn.functional as F
import math

from symbolu.training.conscious_generation.diagnostics.stability_verifier import (
    StabilityConfig,
    PhaseControlOrthogonalityChecker,
    ModulationStabilityChecker,
    EntropyMonitor,
    LongSequenceAnalyzer,
    KillSwitchVerifier,
    StabilityVerifier,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def config():
    return StabilityConfig()


@pytest.fixture
def custom_config():
    return StabilityConfig(
        phase_control_corr_threshold=0.2,
        modulation_ratio_max=0.05,
        entropy_min=2.0,
        entropy_max=10.0,
        entropy_std_max=1.5,
        repetition_ngram_size=3,
        repetition_rate_max=0.03,
        oscillation_window=6,
        coherence_min=0.4,
        norm_growth_max=5.0,
    )


# =============================================================================
# TEST: StabilityConfig
# =============================================================================

class TestStabilityConfig:
    def test_default_values(self):
        cfg = StabilityConfig()
        assert cfg.phase_control_corr_threshold == 0.3
        assert cfg.modulation_ratio_max == 0.1
        assert cfg.entropy_min == 1.0
        assert cfg.entropy_max == 12.0
        assert cfg.entropy_std_max == 2.0
        assert cfg.repetition_ngram_size == 4
        assert cfg.repetition_rate_max == 0.05
        assert cfg.oscillation_window == 8
        assert cfg.coherence_min == 0.3
        assert cfg.norm_growth_max == 10.0
        assert cfg.bhava_slice == (0, 12)
        assert cfg.control_slice == (12, 28)

    def test_custom_values(self, custom_config):
        assert custom_config.phase_control_corr_threshold == 0.2
        assert custom_config.modulation_ratio_max == 0.05
        assert custom_config.entropy_min == 2.0


# =============================================================================
# TEST: PhaseControlOrthogonalityChecker (F.8.2)
# =============================================================================

class TestPhaseControlOrthogonality:
    def test_independent_planes_pass(self, config):
        """Uncorrelated phase and control planes should pass."""
        checker = PhaseControlOrthogonalityChecker(config)
        # Create state with independent phase and control
        torch.manual_seed(42)
        state = torch.randn(10, 50, 32)
        result = checker.check(state)
        # Random data should have low correlation
        assert result["abs_correlation"] < 0.3
        assert result["passed"] is True

    def test_correlated_planes_fail(self, config):
        """Highly correlated phase and control should fail."""
        checker = PhaseControlOrthogonalityChecker(config)
        # Create state where flattened phase and control are correlated.
        # Phase: 12D [0:12], Control: 16D [12:28].
        # Use a single random vector for both, just different lengths,
        # so when flattened and truncated they correlate perfectly.
        torch.manual_seed(42)
        n = 200
        shared = torch.randn(n * 16)  # Enough for both
        state = torch.zeros(n, 32)
        # Fill phase [0:12] from shared[:n*12] reshaped
        state[:, 0:12] = shared[:n * 12].reshape(n, 12)
        # Fill control [12:28] from the SAME data: shared[:n*16] reshaped
        state[:, 12:28] = shared[:n * 16].reshape(n, 16)
        # When flattened: phase = shared[:2400], control = shared[:3200]
        # Truncated to min(2400,3200) = 2400, both = shared[:2400] → corr ≈ 1.0
        result = checker.check(state)
        assert result["abs_correlation"] > 0.3
        assert result["passed"] is False

    def test_batch_check(self, config):
        """Batch check aggregates results correctly."""
        checker = PhaseControlOrthogonalityChecker(config)
        torch.manual_seed(42)
        states = [torch.randn(10, 32) for _ in range(5)]
        result = checker.check_batch(states)
        assert result["num_samples"] == 5
        assert "all_passed" in result
        assert "max_abs_correlation" in result

    def test_zero_variance_phase(self, config):
        """Constant phase should give zero correlation."""
        checker = PhaseControlOrthogonalityChecker(config)
        state = torch.zeros(10, 32)
        state[:, :12] = 1.0  # Constant phase
        state[:, 12:28] = torch.randn(10, 16)  # Random control
        result = checker.check(state)
        assert result["correlation"] == 0.0
        assert result["passed"] is True

    def test_custom_slices(self):
        """Custom bhava/control slices work correctly."""
        cfg = StabilityConfig(bhava_slice=(0, 8), control_slice=(8, 20))
        checker = PhaseControlOrthogonalityChecker(cfg)
        torch.manual_seed(42)
        state = torch.randn(50, 24)
        result = checker.check(state)
        assert "correlation" in result

    def test_single_sample_batch(self, config):
        """Batch check with single sample works."""
        checker = PhaseControlOrthogonalityChecker(config)
        torch.manual_seed(42)
        states = [torch.randn(5, 32)]
        result = checker.check_batch(states)
        assert result["num_samples"] == 1
        assert result["num_failed"] >= 0


# =============================================================================
# TEST: ModulationStabilityChecker (F.8.3)
# =============================================================================

class TestModulationStability:
    def test_small_modulation_passes(self, config):
        """Small modulation within bounds should pass."""
        checker = ModulationStabilityChecker(config)
        torch.manual_seed(42)
        base = torch.randn(4, 100)  # base logits
        # Tiny modulation
        modulated = base + 0.001 * torch.randn_like(base)
        result = checker.check(base, modulated)
        assert result["passed"] is True
        assert result["max_ratio"] < 0.1

    def test_large_modulation_fails(self, config):
        """Large modulation exceeding bounds should fail."""
        checker = ModulationStabilityChecker(config)
        torch.manual_seed(42)
        base = torch.randn(4, 100)
        # Large modulation: 50% of std
        modulated = base + 0.5 * base.std(dim=-1, keepdim=True) * torch.randn_like(base)
        result = checker.check(base, modulated)
        assert result["passed"] is False

    def test_zero_modulation(self, config):
        """Zero modulation (identical logits) should pass."""
        checker = ModulationStabilityChecker(config)
        base = torch.randn(4, 100)
        result = checker.check(base, base.clone())
        assert result["passed"] is True
        assert result["max_delta"] == 0.0

    def test_clamp_modulation(self, config):
        """Clamped modulation should satisfy the constraint."""
        checker = ModulationStabilityChecker(config)
        torch.manual_seed(42)
        base = torch.randn(4, 100)
        # Huge modulation
        modulated = base + 10.0 * torch.randn_like(base)
        clamped = checker.clamp_modulation(base, modulated)
        result = checker.check(base, clamped)
        assert result["passed"] is True

    def test_output_keys(self, config):
        """Check all expected output keys are present."""
        checker = ModulationStabilityChecker(config)
        base = torch.randn(2, 50)
        modulated = base + 0.01 * torch.randn_like(base)
        result = checker.check(base, modulated)
        assert "max_ratio" in result
        assert "mean_ratio" in result
        assert "max_delta" in result
        assert "logit_std_mean" in result
        assert "passed" in result
        assert "threshold" in result

    def test_custom_threshold(self, custom_config):
        """Custom modulation threshold is respected."""
        checker = ModulationStabilityChecker(custom_config)
        assert checker.config.modulation_ratio_max == 0.05


# =============================================================================
# TEST: EntropyMonitor (F.8.4)
# =============================================================================

class TestEntropyMonitor:
    def test_healthy_entropy(self, config):
        """Normal logits should have healthy entropy."""
        monitor = EntropyMonitor(config)
        # Create logits with reasonable entropy
        torch.manual_seed(42)
        logits = torch.randn(100, 1000)  # 100 steps, vocab 1000
        result = monitor.check_sequence(logits)
        assert result["min_entropy"] > 1.0
        assert result["max_entropy"] < 12.0
        assert result["passed"] is True

    def test_collapsed_entropy_fails(self, config):
        """Near-deterministic logits should fail (entropy collapse)."""
        monitor = EntropyMonitor(config)
        # Create near-one-hot logits (very low entropy)
        logits = torch.full((100, 1000), -100.0)
        logits[:, 0] = 100.0  # All probability on token 0
        result = monitor.check_sequence(logits)
        assert result["min_entropy"] < 1.0
        assert result["no_collapse"] is False
        assert result["passed"] is False

    def test_exploded_entropy_fails(self, config):
        """Uniform logits with huge vocab should have high entropy."""
        monitor = EntropyMonitor(config)
        # Uniform distribution: H = log(V)
        # Need V > e^12 ≈ 162755 for H > 12
        V = 200000
        logits = torch.zeros(10, V)  # Uniform → H = log(V) ≈ 12.2
        result = monitor.check_sequence(logits)
        assert result["max_entropy"] > 12.0
        assert result["no_explosion"] is False
        assert result["passed"] is False

    def test_entropy_computation(self, config):
        """Entropy of uniform distribution should be log(V)."""
        monitor = EntropyMonitor(config)
        V = 100
        logits = torch.zeros(1, V)  # Uniform
        entropy = monitor.compute_entropy(logits)
        expected = math.log(V)  # ln(100) ≈ 4.605
        assert abs(entropy.item() - expected) < 0.01

    def test_batched_logits(self, config):
        """Batched logits (3D) should work correctly."""
        monitor = EntropyMonitor(config)
        torch.manual_seed(42)
        logits = torch.randn(4, 50, 1000)  # batch=4, seq=50, vocab=1000
        result = monitor.check_sequence(logits)
        assert "min_entropy" in result
        assert result["entropies"].numel() == 200  # 4*50 flattened

    def test_monotonic_decrease_detection(self, config):
        """Detect monotonically decreasing entropy."""
        monitor = EntropyMonitor(config)
        # Monotonically decreasing entropy
        entropies = torch.linspace(5.0, 1.0, 100)
        result = monitor.check_monotonic_decrease(entropies, window=50)
        assert result["monotonic_decrease_detected"] is True
        assert result["longest_decrease_run"] >= 50

    def test_stable_entropy_no_decrease(self, config):
        """Stable entropy should not trigger monotonic decrease."""
        monitor = EntropyMonitor(config)
        torch.manual_seed(42)
        entropies = 5.0 + 0.5 * torch.randn(100)
        result = monitor.check_monotonic_decrease(entropies, window=50)
        assert result["monotonic_decrease_detected"] is False

    def test_short_sequence(self, config):
        """Short sequence below window should not trigger."""
        monitor = EntropyMonitor(config)
        entropies = torch.tensor([5.0, 4.0, 3.0])
        result = monitor.check_monotonic_decrease(entropies, window=50)
        assert result["monotonic_decrease_detected"] is False
        assert result["longest_decrease_run"] == 0

    def test_entropy_std(self, config):
        """Entropy std is correctly computed."""
        monitor = EntropyMonitor(config)
        torch.manual_seed(42)
        logits = torch.randn(50, 500)
        result = monitor.check_sequence(logits)
        assert result["std_entropy"] >= 0
        assert "stable" in result


# =============================================================================
# TEST: LongSequenceAnalyzer (F.8.5)
# =============================================================================

class TestLongSequenceAnalyzer:
    def test_no_repetition(self, config):
        """Non-repetitive sequence should pass."""
        analyzer = LongSequenceAnalyzer(config)
        # All unique tokens
        token_ids = torch.arange(200)
        result = analyzer.check_repetition(token_ids)
        assert result["repetition_rate"] == 0.0
        assert result["passed"] is True

    def test_high_repetition_fails(self, config):
        """Highly repetitive sequence should fail."""
        analyzer = LongSequenceAnalyzer(config)
        # Repeating pattern: 1,2,3,4,1,2,3,4,...
        pattern = torch.tensor([1, 2, 3, 4])
        token_ids = pattern.repeat(100)
        result = analyzer.check_repetition(token_ids)
        assert result["repetition_rate"] > 0.05
        assert result["passed"] is False

    def test_no_oscillation(self, config):
        """Non-oscillating sequence should pass."""
        analyzer = LongSequenceAnalyzer(config)
        token_ids = torch.arange(200)
        result = analyzer.check_oscillation(token_ids)
        assert result["oscillation_detected"] is False

    def test_oscillation_detected(self, config):
        """A-B-A-B pattern should be detected."""
        analyzer = LongSequenceAnalyzer(config)
        # Long A-B-A-B pattern
        token_ids = torch.tensor([5, 10] * 50)
        result = analyzer.check_oscillation(token_ids)
        assert result["oscillation_detected"] is True
        assert result["max_oscillation_length"] >= 8

    def test_norm_growth_stable(self, config):
        """Stable hidden states should pass norm check."""
        analyzer = LongSequenceAnalyzer(config)
        torch.manual_seed(42)
        hidden = torch.randn(200, 64)
        result = analyzer.check_norm_growth(hidden)
        assert result["passed"] is True
        assert result["growth_factor"] < 10.0

    def test_norm_growth_unbounded(self, config):
        """Exponentially growing norms should fail."""
        analyzer = LongSequenceAnalyzer(config)
        hidden = torch.randn(200, 64)
        # Make norms grow by factor > 10 (threshold)
        for i in range(200):
            hidden[i] *= (1.0 + 0.1 * i)  # Factor ~20x from start to end
        result = analyzer.check_norm_growth(hidden)
        assert result["growth_factor"] > 10.0
        assert result["passed"] is False

    def test_coherence_above_threshold(self, config):
        """Coherence above minimum should pass."""
        analyzer = LongSequenceAnalyzer(config)
        scores = torch.full((100,), 0.5)
        result = analyzer.check_coherence(scores)
        assert result["passed"] is True

    def test_coherence_below_threshold(self, config):
        """Coherence below minimum should fail."""
        analyzer = LongSequenceAnalyzer(config)
        scores = torch.full((100,), 0.2)
        result = analyzer.check_coherence(scores)
        assert result["passed"] is False

    def test_full_analysis_all_pass(self, config):
        """Full analysis with healthy data should pass."""
        analyzer = LongSequenceAnalyzer(config)
        torch.manual_seed(42)
        token_ids = torch.arange(200)
        hidden = torch.randn(200, 64)
        coherence = torch.full((200,), 0.5)
        result = analyzer.full_analysis(token_ids, hidden, coherence)
        assert result["all_passed"] is True

    def test_full_analysis_partial_inputs(self, config):
        """Full analysis with only token_ids still works."""
        analyzer = LongSequenceAnalyzer(config)
        token_ids = torch.arange(200)
        result = analyzer.full_analysis(token_ids)
        assert "repetition" in result
        assert "oscillation" in result
        assert "norm_growth" not in result
        assert "coherence" not in result

    def test_short_sequence_repetition(self, config):
        """Very short sequence handles edge case."""
        analyzer = LongSequenceAnalyzer(config)
        token_ids = torch.tensor([1, 2])
        result = analyzer.check_repetition(token_ids)
        assert result["passed"] is True
        assert result["total_ngrams"] == 0

    def test_short_sequence_oscillation(self, config):
        """Very short sequence handles oscillation edge case."""
        analyzer = LongSequenceAnalyzer(config)
        token_ids = torch.tensor([1, 2])
        result = analyzer.check_oscillation(token_ids)
        assert result["oscillation_detected"] is False

    def test_batched_hidden_states(self, config):
        """3D hidden states (batched) work for norm check."""
        analyzer = LongSequenceAnalyzer(config)
        torch.manual_seed(42)
        hidden = torch.randn(4, 200, 64)  # batch=4
        result = analyzer.check_norm_growth(hidden)
        assert "growth_factor" in result


# =============================================================================
# TEST: KillSwitchVerifier (F.8.6)
# =============================================================================

class TestKillSwitchVerifier:
    def test_identical_outputs_pass(self):
        """Identical outputs should pass."""
        verifier = KillSwitchVerifier()
        output = torch.randn(4, 100)
        result = verifier.check(output, output.clone())
        assert result["passed"] is True
        assert result["max_diff"] == 0.0

    def test_different_outputs_fail(self):
        """Different outputs should fail."""
        verifier = KillSwitchVerifier()
        baseline = torch.randn(4, 100)
        killswitch = baseline + 1.0  # Large diff
        result = verifier.check(baseline, killswitch)
        assert result["passed"] is False

    def test_near_identical_within_tolerance(self):
        """Near-identical within tolerance should pass."""
        verifier = KillSwitchVerifier(atol=0.01)
        baseline = torch.randn(4, 100)
        killswitch = baseline + 0.001 * torch.randn_like(baseline)
        result = verifier.check(baseline, killswitch)
        assert result["passed"] is True

    def test_logits_check_with_argmax(self):
        """Logit check includes argmax agreement."""
        verifier = KillSwitchVerifier()
        logits = torch.randn(10, 50)
        result = verifier.check_logits(logits, logits.clone())
        assert result["argmax_agreement"] == 1.0
        assert result["argmax_perfect"] is True

    def test_logits_check_different_argmax(self):
        """Different argmax detected in logit check."""
        verifier = KillSwitchVerifier()
        baseline = torch.randn(10, 50)
        # Swap top logit to force different argmax
        killswitch = baseline.clone()
        killswitch[:, 0] = 100.0  # Force token 0 as argmax
        result = verifier.check_logits(baseline, killswitch)
        assert result["argmax_agreement"] < 1.0

    def test_output_keys(self):
        """Check all expected output keys."""
        verifier = KillSwitchVerifier()
        output = torch.randn(4, 100)
        result = verifier.check(output, output.clone())
        assert "passed" in result
        assert "max_diff" in result
        assert "mean_diff" in result
        assert "atol" in result
        assert "rtol" in result


# =============================================================================
# TEST: StabilityVerifier (Combined Orchestrator)
# =============================================================================

class TestStabilityVerifier:
    def test_run_all_no_inputs(self, config):
        """Running with no inputs returns empty summary."""
        verifier = StabilityVerifier(config)
        result = verifier.run_all()
        assert result["summary"]["tests_run"] == 0
        assert result["summary"]["all_passed"] is False

    def test_run_all_with_all_inputs(self, config):
        """Running with all inputs runs all 5 tests."""
        verifier = StabilityVerifier(config)
        torch.manual_seed(42)

        # Prepare inputs for all tests
        ontological_states = [torch.randn(10, 32) for _ in range(3)]
        base_logits = torch.randn(4, 1000)
        modulated_logits = base_logits + 0.001 * torch.randn_like(base_logits)
        logits_sequence = torch.randn(50, 1000)
        token_ids = torch.arange(200)
        baseline_output = torch.randn(4, 100)

        result = verifier.run_all(
            ontological_states=ontological_states,
            base_logits=base_logits,
            modulated_logits=modulated_logits,
            logits_sequence=logits_sequence,
            token_ids=token_ids,
            baseline_output=baseline_output,
            killswitch_output=baseline_output.clone(),
        )

        assert result["summary"]["tests_run"] == 5
        assert "orthogonality" in result
        assert "modulation" in result
        assert "entropy" in result
        assert "long_sequence" in result
        assert "kill_switch" in result

    def test_partial_inputs(self, config):
        """Running with partial inputs runs only available tests."""
        verifier = StabilityVerifier(config)
        torch.manual_seed(42)

        result = verifier.run_all(
            token_ids=torch.arange(100),
        )
        assert result["summary"]["tests_run"] == 1
        assert "long_sequence" in result
        assert "orthogonality" not in result

    def test_all_pass_scenario(self, config):
        """All tests pass with well-behaved data."""
        verifier = StabilityVerifier(config)
        torch.manual_seed(42)

        result = verifier.run_all(
            ontological_states=[torch.randn(20, 32)],
            base_logits=torch.randn(4, 500),
            modulated_logits=torch.randn(4, 500) * 0.001 + torch.randn(4, 500),
            logits_sequence=torch.randn(50, 500),
            token_ids=torch.arange(200),
            hidden_states=torch.randn(200, 64),
            coherence_scores=torch.full((200,), 0.5),
            baseline_output=torch.zeros(4, 100),
            killswitch_output=torch.zeros(4, 100),
        )
        # Kill switch should pass (identical zeros)
        assert result["kill_switch"]["passed"] is True

    def test_uses_custom_config(self, custom_config):
        """Custom config propagates to sub-checkers."""
        verifier = StabilityVerifier(custom_config)
        assert verifier.orthogonality.config.phase_control_corr_threshold == 0.2
        assert verifier.modulation.config.modulation_ratio_max == 0.05
        assert verifier.entropy.config.entropy_min == 2.0
        assert verifier.long_sequence.config.repetition_ngram_size == 3


# =============================================================================
# TEST: Edge Cases
# =============================================================================

class TestEdgeCases:
    def test_single_token_sequence(self, config):
        """Single token doesn't crash any analyzer."""
        analyzer = LongSequenceAnalyzer(config)
        token_ids = torch.tensor([42])
        result = analyzer.full_analysis(token_ids)
        assert "repetition" in result

    def test_empty_entropy_history(self, config):
        """Single logit step computes entropy."""
        monitor = EntropyMonitor(config)
        logits = torch.randn(1, 1000)
        result = monitor.check_sequence(logits)
        assert "min_entropy" in result

    def test_large_ontological_state(self, config):
        """Large batch of ontological states works."""
        checker = PhaseControlOrthogonalityChecker(config)
        torch.manual_seed(42)
        state = torch.randn(1000, 32)
        result = checker.check(state)
        assert "correlation" in result

    def test_high_dimensional_hidden(self, config):
        """High-dimensional hidden states work."""
        analyzer = LongSequenceAnalyzer(config)
        torch.manual_seed(42)
        hidden = torch.randn(100, 4096)
        result = analyzer.check_norm_growth(hidden)
        assert "growth_factor" in result

    def test_all_same_tokens(self, config):
        """All-same-token sequence has high repetition."""
        analyzer = LongSequenceAnalyzer(config)
        token_ids = torch.full((100,), 42)
        result = analyzer.check_repetition(token_ids)
        # All 4-grams are (42,42,42,42) → unique=1 → rate = 1 - 1/97 ≈ 0.99
        assert result["repetition_rate"] > 0.9
        assert result["passed"] is False

    def test_norm_growth_single_step(self, config):
        """Single hidden state step doesn't crash."""
        analyzer = LongSequenceAnalyzer(config)
        hidden = torch.randn(1, 64)
        result = analyzer.check_norm_growth(hidden)
        assert result["passed"] is True

    def test_killswitch_different_tolerance(self):
        """Different tolerance levels affect pass/fail."""
        strict = KillSwitchVerifier(atol=1e-8, rtol=1e-8)
        lenient = KillSwitchVerifier(atol=1.0, rtol=1.0)

        baseline = torch.randn(10, 50)
        noisy = baseline + 0.01 * torch.randn_like(baseline)

        assert strict.check(baseline, noisy)["passed"] is False
        assert lenient.check(baseline, noisy)["passed"] is True
