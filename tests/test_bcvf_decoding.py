#!/usr/bin/env python3
"""
Tests for the BCVF Controlled Decoding Pipeline.

Covers:
    - DecodingConfig defaults and overrides
    - BCVFScoringModule (forward_score, backward_score, lagrangian, rerank)
    - CalibrationLayer confidence tiers
    - BCVFDecoder decode_step with all option combinations
    - Calibration metrics (ECE, Brier, reliability bins)
    - CalibrationTracker stateful accumulation
    - StepLogger and StepRecord construction
    - ExperimentRunner ablation matrix
    - Stop-condition evaluator
"""

import pytest
import numpy as np

# ---------------------------------------------------------------------------
# Check PyTorch availability
# ---------------------------------------------------------------------------
torch = pytest.importorskip("torch")

from symbolu.ontological.bcvf_decoding import (
    BCVFDecoder,
    BCVFScoringModule,
    CalibrationLayer,
    DecodingConfig,
    decode_step,
)
from symbolu.ontological.bcvf_calibration import (
    CalibrationTracker,
    compute_brier,
    compute_ece,
    reliability_bins,
)
from symbolu.ontological.bcvf_experiments import (
    EXPERIMENT_MATRIX,
    ExperimentResult,
    ExperimentRunner,
    GoNoGoVerdict,
    StepLogger,
    StepRecord,
    config_label,
    evaluate_stop_conditions,
)


# ===========================================================================
# Fixtures
# ===========================================================================

B, D, V, M = 2, 64, 1000, 100


@pytest.fixture
def hidden():
    torch.manual_seed(42)
    return torch.randn(B, D)


@pytest.fixture
def goal():
    torch.manual_seed(43)
    return torch.randn(B, D)


@pytest.fixture
def vocab_emb():
    torch.manual_seed(44)
    return torch.randn(V, D)


@pytest.fixture
def logits(hidden, vocab_emb):
    return hidden @ vocab_emb.T  # [B, V]


@pytest.fixture
def default_config():
    return DecodingConfig()


# ===========================================================================
# DecodingConfig
# ===========================================================================


class TestDecodingConfig:
    def test_defaults(self):
        cfg = DecodingConfig()
        assert cfg.top_m == 500
        assert cfg.beta == pytest.approx(0.2)
        assert cfg.use_rerank is True
        assert cfg.use_logit_mod is False
        assert cfg.use_calibration is True

    def test_override(self):
        cfg = DecodingConfig(top_m=100, beta=0.5, use_rerank=False)
        assert cfg.top_m == 100
        assert cfg.beta == 0.5
        assert cfg.use_rerank is False


# ===========================================================================
# BCVFScoringModule
# ===========================================================================


class TestBCVFScoringModule:
    def test_forward_score_shape(self, hidden, vocab_emb, default_config):
        scorer = BCVFScoringModule(default_config)
        candidates = vocab_emb[:M].unsqueeze(0).expand(B, -1, -1)
        sf = scorer.forward_score(hidden, candidates)
        assert sf.shape == (B, M)

    def test_forward_score_range(self, hidden, vocab_emb, default_config):
        scorer = BCVFScoringModule(default_config)
        candidates = vocab_emb[:M].unsqueeze(0).expand(B, -1, -1)
        sf = scorer.forward_score(hidden, candidates)
        assert (sf >= 0).all() and (sf <= 1).all()

    def test_backward_score_shape(self, goal, vocab_emb, default_config):
        scorer = BCVFScoringModule(default_config)
        candidates = vocab_emb[:M].unsqueeze(0).expand(B, -1, -1)
        sb = scorer.backward_score(candidates, goal)
        assert sb.shape == (B, M)

    def test_backward_score_range(self, goal, vocab_emb, default_config):
        scorer = BCVFScoringModule(default_config)
        candidates = vocab_emb[:M].unsqueeze(0).expand(B, -1, -1)
        sb = scorer.backward_score(candidates, goal)
        assert (sb >= 0).all() and (sb <= 1).all()

    def test_lagrangian_zero_for_perfect_scores(self, default_config):
        scorer = BCVFScoringModule(default_config)
        sf = torch.ones(B, M)
        sb = torch.ones(B, M)
        L = scorer.lagrangian(sf, sb)
        assert torch.allclose(L, torch.zeros_like(L), atol=1e-6)

    def test_lagrangian_nonzero_for_imperfect(self, default_config):
        scorer = BCVFScoringModule(default_config)
        sf = torch.full((B, M), 0.5)
        sb = torch.full((B, M), 0.3)
        L = scorer.lagrangian(sf, sb)
        assert (L > 0).all()

    def test_lagrangian_consistency_penalty(self, default_config):
        scorer = BCVFScoringModule(default_config)
        # Same sf/sb should have lower L than mismatched
        sf_same = torch.full((1, 1), 0.8)
        sb_same = torch.full((1, 1), 0.8)
        sf_diff = torch.full((1, 1), 0.8)
        sb_diff = torch.full((1, 1), 0.3)
        L_same = scorer.lagrangian(sf_same, sb_same)
        L_diff = scorer.lagrangian(sf_diff, sb_diff)
        assert L_same.item() < L_diff.item()

    def test_rerank_returns_valid_indices(
        self, hidden, goal, vocab_emb, logits, default_config
    ):
        scorer = BCVFScoringModule(default_config)
        topM_scores, topM_indices = torch.topk(logits, M, dim=-1)
        best_idx, sf, sb, L = scorer.rerank(
            logits, topM_indices, vocab_emb, hidden, goal
        )
        assert best_idx.shape == (B,)
        assert (best_idx >= 0).all() and (best_idx < V).all()


# ===========================================================================
# CalibrationLayer
# ===========================================================================


class TestCalibrationLayer:
    def test_high_confidence(self):
        cfg = DecodingConfig()
        cal = CalibrationLayer(cfg)
        # Create probs where max is very high
        probs = torch.zeros(1, 100)
        probs[0, 0] = 0.95
        probs[0, 1] = 0.03
        probs[0, 2:] = 0.02 / 98
        result = cal(probs)
        assert result["confidence_level"] == ["HIGH"]

    def test_medium_confidence(self):
        cfg = DecodingConfig()
        cal = CalibrationLayer(cfg)
        probs = torch.zeros(1, 100)
        probs[0, 0] = 0.60
        probs[0, 1] = 0.55
        probs[0, 2:] = (1.0 - 0.60 - 0.55) / 98
        # Normalize
        probs = probs / probs.sum(dim=-1, keepdim=True)
        result = cal(probs)
        assert result["confidence_level"][0] in ("MEDIUM", "LOW")

    def test_low_confidence(self):
        cfg = DecodingConfig()
        cal = CalibrationLayer(cfg)
        # Uniform-ish distribution
        probs = torch.ones(1, 100) / 100
        result = cal(probs)
        assert result["confidence_level"] == ["LOW"]

    def test_batch_handling(self):
        cfg = DecodingConfig()
        cal = CalibrationLayer(cfg)
        probs = torch.zeros(3, 50)
        probs[0, 0] = 0.95  # HIGH
        probs[1] = 1.0 / 50  # LOW
        probs[2, 0] = 0.60  # MEDIUM
        probs = probs / probs.sum(dim=-1, keepdim=True)
        result = cal(probs)
        assert len(result["confidence_level"]) == 3
        assert result["confidence"].shape == (3,)
        assert result["margin"].shape == (3,)


# ===========================================================================
# BCVFDecoder
# ===========================================================================


class TestBCVFDecoder:
    def test_baseline_decode(self, hidden, vocab_emb, goal, logits):
        """Baseline (all options off) should return argmax of logits."""
        cfg = DecodingConfig(
            use_rerank=False, use_logit_mod=False, use_calibration=False
        )
        decoder = BCVFDecoder(cfg)
        best, probs, log_data = decoder.decode_step(
            hidden, vocab_emb, goal, logits
        )
        expected = torch.argmax(logits, dim=-1)
        assert torch.equal(best, expected)
        assert probs.shape == logits.shape
        assert "base_logits" in log_data

    def test_rerank_only(self, hidden, vocab_emb, goal, logits):
        cfg = DecodingConfig(
            use_rerank=True, use_logit_mod=False, use_calibration=False
        )
        decoder = BCVFDecoder(cfg)
        best, probs, log_data = decoder.decode_step(
            hidden, vocab_emb, goal, logits
        )
        assert best.shape == (B,)
        assert "rerank_selected" in log_data
        assert "rerank_changed" in log_data

    def test_calibration_only(self, hidden, vocab_emb, goal, logits):
        cfg = DecodingConfig(
            use_rerank=False, use_logit_mod=False, use_calibration=True
        )
        decoder = BCVFDecoder(cfg)
        best, probs, log_data = decoder.decode_step(
            hidden, vocab_emb, goal, logits
        )
        assert "confidence" in log_data
        assert "margin" in log_data
        assert "confidence_level" in log_data

    def test_logit_modulation(self, hidden, vocab_emb, goal, logits):
        cfg = DecodingConfig(
            use_rerank=False, use_logit_mod=True, use_calibration=False
        )
        decoder = BCVFDecoder(cfg)
        best, probs, log_data = decoder.decode_step(
            hidden, vocab_emb, goal, logits
        )
        # Probs should sum to 1
        assert torch.allclose(
            probs.sum(dim=-1), torch.ones(B), atol=1e-4
        )

    def test_full_pipeline(self, hidden, vocab_emb, goal, logits):
        cfg = DecodingConfig(
            use_rerank=True, use_logit_mod=True, use_calibration=True
        )
        decoder = BCVFDecoder(cfg)
        best, probs, log_data = decoder.decode_step(
            hidden, vocab_emb, goal, logits
        )
        assert best.shape == (B,)
        assert "rerank_selected" in log_data
        assert "confidence" in log_data
        assert "sf" in log_data
        assert "sb" in log_data
        assert "L" in log_data

    def test_no_logits_provided(self, hidden, vocab_emb, goal):
        """When no logits are provided, compute from hidden @ vocab.T."""
        cfg = DecodingConfig(
            use_rerank=False, use_logit_mod=False, use_calibration=False
        )
        decoder = BCVFDecoder(cfg)
        best, probs, log_data = decoder.decode_step(
            hidden, vocab_emb, goal
        )
        expected_logits = hidden @ vocab_emb.T
        expected = torch.argmax(expected_logits, dim=-1)
        assert torch.equal(best, expected)

    def test_convenience_wrapper(self, hidden, vocab_emb, goal, logits):
        cfg = DecodingConfig(use_rerank=False)
        best, probs, log_data = decode_step(
            hidden, vocab_emb, goal, logits, config=cfg
        )
        assert best.shape == (B,)

    def test_small_vocab(self):
        """Pipeline works with V < top_m."""
        small_V = 50
        h = torch.randn(1, D)
        g = torch.randn(1, D)
        v = torch.randn(small_V, D)
        cfg = DecodingConfig(top_m=500, use_rerank=True, use_calibration=True)
        decoder = BCVFDecoder(cfg)
        best, probs, _ = decoder.decode_step(h, v, g)
        assert best.shape == (1,)
        assert probs.shape == (1, small_V)


# ===========================================================================
# Calibration Metrics
# ===========================================================================


class TestCalibrationMetrics:
    def test_perfect_calibration(self):
        # Perfectly calibrated: confidence 0.8 on items that are 80% correct
        np.random.seed(42)
        N = 1000
        confs = np.full(N, 0.8)
        correct = np.random.binomial(1, 0.8, N)
        ece = compute_ece(confs, correct)
        assert ece < 0.1  # Should be close to 0

    def test_worst_calibration(self):
        # Always confident but always wrong
        confs = np.ones(100)
        correct = np.zeros(100)
        ece = compute_ece(confs, correct)
        assert ece > 0.5

    def test_brier_perfect(self):
        confs = np.ones(100)
        correct = np.ones(100)
        assert compute_brier(confs, correct) == pytest.approx(0.0)

    def test_brier_worst(self):
        confs = np.ones(100)
        correct = np.zeros(100)
        assert compute_brier(confs, correct) == pytest.approx(1.0)

    def test_reliability_bins(self):
        confs = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
        correct = np.array([0, 0, 1, 1, 1])
        bins = reliability_bins(confs, correct, n_bins=5)
        assert len(bins) >= 1
        for conf, acc, count in bins:
            assert 0.0 <= conf <= 1.0
            assert 0.0 <= acc <= 1.0
            assert count > 0

    def test_empty_input(self):
        assert compute_ece(np.array([]), np.array([])) == 0.0
        assert compute_brier(np.array([]), np.array([])) == 0.0


class TestCalibrationTracker:
    def test_accumulation(self):
        tracker = CalibrationTracker()
        tracker.update(confidence=0.9, correct=True, confidence_level="HIGH")
        tracker.update(confidence=0.4, correct=False, confidence_level="LOW")
        tracker.update(confidence=0.6, correct=True, confidence_level="MEDIUM")

        assert tracker.accuracy() == pytest.approx(2 / 3)
        assert tracker.tier_counts["HIGH"] == 1
        assert tracker.tier_counts["MEDIUM"] == 1
        assert tracker.tier_counts["LOW"] == 1

    def test_report(self):
        tracker = CalibrationTracker()
        for i in range(50):
            tracker.update(
                confidence=0.8,
                correct=i < 40,  # 80% accuracy
                confidence_level="HIGH",
            )
        report = tracker.report()
        assert report["n"] == 50
        assert report["accuracy"] == pytest.approx(0.8)
        assert "ece" in report
        assert "brier" in report
        assert "tier_accuracy" in report

    def test_reset(self):
        tracker = CalibrationTracker()
        tracker.update(confidence=0.9, correct=True)
        tracker.reset()
        assert len(tracker.confidences) == 0
        assert len(tracker.correctness) == 0


# ===========================================================================
# StepLogger
# ===========================================================================


class TestStepLogger:
    def test_basic_logging(self):
        logger = StepLogger()
        record = StepRecord(
            step_index=0,
            predicted_token=42,
            correct=True,
            rerank_changed=True,
            confidence=0.9,
            confidence_level="HIGH",
        )
        logger.log(record)
        assert logger.accuracy() == 1.0
        assert logger.rerank_change_rate() == 1.0

    def test_summary(self):
        logger = StepLogger()
        for i in range(10):
            logger.log(
                StepRecord(
                    step_index=i,
                    predicted_token=i,
                    correct=i < 7,
                    rerank_changed=i < 3,
                    sf_selected=0.8,
                    sb_selected=0.7,
                )
            )
        summary = logger.summary()
        assert summary["n_steps"] == 10
        assert summary["accuracy"] == pytest.approx(0.7)
        assert summary["rerank_change_rate"] == pytest.approx(0.3)
        assert summary["mean_sf"] == pytest.approx(0.8)
        assert summary["mean_sb"] == pytest.approx(0.7)


# ===========================================================================
# Experiment Runner
# ===========================================================================


class TestExperimentRunner:
    @pytest.fixture
    def synthetic_dataset(self):
        """Create a small synthetic dataset for testing."""
        torch.manual_seed(42)
        samples = []
        for i in range(20):
            h = torch.randn(1, D)
            v = torch.randn(V, D)
            logits = h @ v.T
            gt = torch.argmax(logits, dim=-1).item()
            samples.append({
                "hidden_state": h,
                "goal_embedding": torch.randn(1, D),
                "logits": logits,
                "ground_truth": gt,
            })
        return samples

    def test_config_label(self):
        assert config_label(EXPERIMENT_MATRIX[0]) == "baseline"
        assert config_label(EXPERIMENT_MATRIX[1]) == "B"
        assert config_label(EXPERIMENT_MATRIX[2]) == "C"
        assert "A" in config_label(EXPERIMENT_MATRIX[-1])
        assert "B" in config_label(EXPERIMENT_MATRIX[-1])
        assert "C" in config_label(EXPERIMENT_MATRIX[-1])

    def test_run_single_experiment(self, synthetic_dataset):
        runner = ExperimentRunner()
        flags = {"use_rerank": False, "use_logit_mod": False, "use_calibration": False}
        result = runner.run_single_experiment(flags, synthetic_dataset)
        assert result.label == "baseline"
        assert result.total_samples == 20
        assert 0.0 <= result.pass_at_1 <= 1.0

    def test_run_ablation_small(self, synthetic_dataset):
        runner = ExperimentRunner()
        # Run just 2 configs for speed
        small_matrix = EXPERIMENT_MATRIX[:2]
        results = runner.run_ablation(synthetic_dataset, matrix=small_matrix)
        assert len(results) == 2
        assert results[0].label == "baseline"
        assert results[1].label == "B"

    def test_print_summary(self, synthetic_dataset):
        runner = ExperimentRunner()
        small_matrix = EXPERIMENT_MATRIX[:2]
        results = runner.run_ablation(synthetic_dataset, matrix=small_matrix)
        table = ExperimentRunner.print_summary(results)
        assert "baseline" in table
        assert "pass@1" in table


# ===========================================================================
# Stop-Condition Evaluator
# ===========================================================================


class TestStopConditions:
    def test_pass_at_1_regression_stops(self):
        baseline = ExperimentResult(
            label="baseline",
            flags={},
            pass_at_1=0.7,
            total_samples=100,
            tier_accuracy={"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3},
        )
        bcvf = ExperimentResult(
            label="C",
            flags={"use_rerank": True},
            pass_at_1=0.65,  # Regression
            total_samples=100,
            rerank_change_pct=0.1,
            tier_accuracy={"HIGH": 0.85, "MEDIUM": 0.55, "LOW": 0.25},
        )
        verdict = evaluate_stop_conditions(baseline, bcvf, beta=0.2)
        assert not verdict.should_continue
        assert any("STOP" in r and "pass@1" in r for r in verdict.reasons)

    def test_low_rerank_signal_stops(self):
        baseline = ExperimentResult(
            label="baseline", flags={}, pass_at_1=0.7, total_samples=100,
            tier_accuracy={"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3},
        )
        bcvf = ExperimentResult(
            label="C", flags={}, pass_at_1=0.71, total_samples=100,
            rerank_change_pct=0.01,  # Only 1%
            tier_accuracy={"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3},
        )
        verdict = evaluate_stop_conditions(baseline, bcvf)
        assert not verdict.should_continue

    def test_good_results_continue(self):
        baseline = ExperimentResult(
            label="baseline", flags={}, pass_at_1=0.7, total_samples=100,
            ece=0.15,
            tier_accuracy={"HIGH": 0.8, "MEDIUM": 0.6, "LOW": 0.4},
        )
        bcvf = ExperimentResult(
            label="A+B+C", flags={}, pass_at_1=0.73, total_samples=100,
            ece=0.08,
            rerank_change_pct=0.15,
            tier_accuracy={"HIGH": 0.92, "MEDIUM": 0.65, "LOW": 0.35},
        )
        verdict = evaluate_stop_conditions(baseline, bcvf)
        assert verdict.should_continue
        assert any("GO" in r for r in verdict.reasons)


# ===========================================================================
# Integration: End-to-End
# ===========================================================================


class TestEndToEnd:
    def test_full_ablation_produces_comparable_results(self):
        """
        Run the full 8-config matrix on a tiny synthetic dataset and
        verify all configs produce valid results.
        """
        torch.manual_seed(0)
        samples = []
        for _ in range(10):
            h = torch.randn(1, D)
            v = torch.randn(200, D)
            logits = h @ v.T
            gt = torch.argmax(logits, dim=-1).item()
            samples.append({
                "hidden_state": h,
                "goal_embedding": torch.randn(1, D),
                "logits": logits,
                "ground_truth": gt,
            })

        runner = ExperimentRunner(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        results = runner.run_ablation(samples)

        assert len(results) == 8
        for r in results:
            assert 0.0 <= r.pass_at_1 <= 1.0
            assert r.total_samples == 10
            assert 0.0 <= r.ece <= 1.0
            assert 0.0 <= r.brier <= 1.0
