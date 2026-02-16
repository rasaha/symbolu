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
    ParameterSweepRunner,
    StepLogger,
    StepRecord,
    check_topM_recall,
    config_label,
    evaluate_stop_conditions,
    run_unit_tests,
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


# ===========================================================================
# Risk A: Baseline sf/sb delta diagnostics
# ===========================================================================


class TestRiskADiagnostics:
    def test_decode_emits_baseline_sf_sb(self, hidden, vocab_emb, goal, logits):
        """Decode step should always log baseline_sf and baseline_sb."""
        cfg = DecodingConfig(use_rerank=True, use_calibration=False)
        decoder = BCVFDecoder(cfg)
        _, _, log_data = decoder.decode_step(hidden, vocab_emb, goal, logits)
        assert "baseline_sf" in log_data
        assert "baseline_sb" in log_data
        assert log_data["baseline_sf"].shape == (B,)
        assert log_data["baseline_sb"].shape == (B,)

    def test_decode_emits_delta_sf_sb_when_reranking(
        self, hidden, vocab_emb, goal, logits
    ):
        """When reranking, delta_sf and delta_sb are logged."""
        cfg = DecodingConfig(use_rerank=True, use_calibration=False)
        decoder = BCVFDecoder(cfg)
        _, _, log_data = decoder.decode_step(hidden, vocab_emb, goal, logits)
        assert "delta_sf" in log_data
        assert "delta_sb" in log_data
        assert "selected_sf" in log_data
        assert "selected_sb" in log_data

    def test_step_record_captures_deltas(self, hidden, vocab_emb, goal, logits):
        """StepRecord should populate delta_sf/sb from log_data."""
        cfg = DecodingConfig(use_rerank=True, use_calibration=True)
        decoder = BCVFDecoder(cfg)
        best, _, log_data = decoder.decode_step(hidden, vocab_emb, goal, logits)
        record = StepLogger.from_decode_log(
            step_index=0,
            log_data=log_data,
            predicted_token=int(best[0].item()),
            ground_truth_token=0,
        )
        # These fields should be populated (may be 0.0 if token wasn't changed)
        assert isinstance(record.sf_baseline, float)
        assert isinstance(record.sb_baseline, float)
        assert isinstance(record.delta_sf, float)
        assert isinstance(record.delta_sb, float)


# ===========================================================================
# Logit Modulation Sanity (KL, entropy)
# ===========================================================================


class TestLogitModSanity:
    def test_kl_and_entropy_logged_when_logit_mod_on(
        self, hidden, vocab_emb, goal, logits
    ):
        cfg = DecodingConfig(
            use_rerank=False, use_logit_mod=True, use_calibration=False
        )
        decoder = BCVFDecoder(cfg)
        _, _, log_data = decoder.decode_step(hidden, vocab_emb, goal, logits)
        assert "kl_base_mod" in log_data
        assert "entropy_base" in log_data
        assert "entropy_mod" in log_data
        assert "entropy_delta" in log_data
        # KL should be non-negative
        assert (log_data["kl_base_mod"] >= -1e-6).all()

    def test_kl_not_logged_when_logit_mod_off(
        self, hidden, vocab_emb, goal, logits
    ):
        cfg = DecodingConfig(
            use_rerank=False, use_logit_mod=False, use_calibration=False
        )
        decoder = BCVFDecoder(cfg)
        _, _, log_data = decoder.decode_step(hidden, vocab_emb, goal, logits)
        assert "kl_base_mod" not in log_data

    def test_base_probs_always_logged(self, hidden, vocab_emb, goal, logits):
        """base_probs should always be present for comparison."""
        cfg = DecodingConfig(
            use_rerank=False, use_logit_mod=False, use_calibration=False
        )
        decoder = BCVFDecoder(cfg)
        _, _, log_data = decoder.decode_step(hidden, vocab_emb, goal, logits)
        assert "base_probs" in log_data


# ===========================================================================
# Top-M Recall Check (Risk B)
# ===========================================================================


class TestTopMRecall:
    def test_recall_check_returns_valid_structure(self):
        torch.manual_seed(42)
        h = torch.randn(1, D)
        v = torch.randn(500, D)
        g = torch.randn(1, D)
        result = check_topM_recall(h, v, g, M_values=[50, 100, 200, 500])
        assert "bcvf_best_rank" in result
        assert "recall_at_M" in result
        assert "min_required_M" in result
        assert isinstance(result["bcvf_best_rank"], int)
        assert result["bcvf_best_rank"] >= 0
        # recall_at_500 must be True since pool is 500
        assert result["recall_at_M"][500] is True

    def test_recall_monotone(self):
        """Recall at larger M must be >= recall at smaller M."""
        torch.manual_seed(99)
        h = torch.randn(1, D)
        v = torch.randn(1000, D)
        g = torch.randn(1, D)
        result = check_topM_recall(h, v, g, M_values=[100, 200, 500, 1000])
        ms = sorted(result["recall_at_M"].keys())
        for i in range(len(ms) - 1):
            if result["recall_at_M"][ms[i]]:
                assert result["recall_at_M"][ms[i + 1]]


# ===========================================================================
# Conditional ECE & Tier Confusion
# ===========================================================================


class TestConditionalECE:
    @pytest.fixture
    def experiment_with_rerank(self):
        """Run a single experiment with reranking to get conditional metrics."""
        torch.manual_seed(42)
        samples = []
        for i in range(30):
            h = torch.randn(1, D)
            v = torch.randn(200, D)
            logits = h @ v.T
            # Alternate correct/incorrect ground truths
            gt = torch.argmax(logits, dim=-1).item() if i % 2 == 0 else 0
            samples.append({
                "hidden_state": h,
                "goal_embedding": torch.randn(1, D),
                "logits": logits,
                "ground_truth": gt,
            })
        runner = ExperimentRunner(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        flags = {"use_rerank": True, "use_logit_mod": False, "use_calibration": True}
        return runner.run_single_experiment(flags, samples)

    def test_tier_confusion_structure(self, experiment_with_rerank):
        r = experiment_with_rerank
        assert "HIGH" in r.tier_confusion
        assert "MEDIUM" in r.tier_confusion
        assert "LOW" in r.tier_confusion
        for tier in ("HIGH", "MEDIUM", "LOW"):
            assert "correct" in r.tier_confusion[tier]
            assert "wrong" in r.tier_confusion[tier]

    def test_conditional_ece_fields_exist(self, experiment_with_rerank):
        r = experiment_with_rerank
        assert isinstance(r.ece_on_wrong_baseline, float)
        assert isinstance(r.ece_on_low_margin, float)
        assert 0.0 <= r.ece_on_wrong_baseline <= 1.0
        assert 0.0 <= r.ece_on_low_margin <= 1.0

    def test_rerank_effectiveness_fields(self, experiment_with_rerank):
        r = experiment_with_rerank
        assert isinstance(r.rerank_worsened_pct, float)
        assert isinstance(r.rerank_net_benefit, float)
        assert isinstance(r.mean_delta_sf, float)
        assert isinstance(r.mean_delta_sb, float)


# ===========================================================================
# Enhanced print_summary
# ===========================================================================


class TestEnhancedPrintSummary:
    def test_summary_includes_rerank_breakdown(self):
        torch.manual_seed(42)
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
        results = runner.run_ablation(samples, matrix=EXPERIMENT_MATRIX[:3])
        table = ExperimentRunner.print_summary(results)
        assert "Impr%" in table
        assert "Wrsd%" in table
        assert "Net" in table


# ===========================================================================
# Sandbox: run_unit_tests
# ===========================================================================


class TestRunUnitTests:
    def test_passing_code(self):
        code = "def add(a, b): return a + b\n"
        test = "def check(fn): assert fn(1, 2) == 3\n"
        assert run_unit_tests(code, test, "add", use_subprocess=False) is True

    def test_failing_code(self):
        code = "def add(a, b): return a - b\n"
        test = "def check(fn): assert fn(1, 2) == 3\n"
        assert run_unit_tests(code, test, "add", use_subprocess=False) is False

    def test_timeout_with_subprocess(self):
        code = "import time\ndef slow(): time.sleep(100)\n"
        test = "def check(fn): fn()\n"
        result = run_unit_tests(
            code, test, "slow", timeout_seconds=1.0, use_subprocess=True
        )
        assert result is False


# ===========================================================================
# Parameter Sweeps
# ===========================================================================


class TestParameterSweeps:
    @pytest.fixture
    def sweep_dataset(self):
        torch.manual_seed(42)
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
        return samples

    def test_beta_sweep(self, sweep_dataset):
        runner = ExperimentRunner(
            base_config=DecodingConfig(top_m=50)
        )
        sweeper = ParameterSweepRunner(runner)
        result = sweeper.sweep_beta(
            sweep_dataset, values=[0.0, 0.1, 0.3]
        )
        assert result.parameter_name == "beta"
        assert len(result.results) == 3
        assert result.results[0].label == "β=0.0"
        assert result.results[2].label == "β=0.3"

    def test_top_m_sweep(self, sweep_dataset):
        runner = ExperimentRunner(
            base_config=DecodingConfig(beta=0.2)
        )
        sweeper = ParameterSweepRunner(runner)
        result = sweeper.sweep_top_m(
            sweep_dataset, values=[50, 100]
        )
        assert result.parameter_name == "top_m"
        assert len(result.results) == 2

    def test_lambda_c_sweep(self, sweep_dataset):
        runner = ExperimentRunner(
            base_config=DecodingConfig(top_m=50)
        )
        sweeper = ParameterSweepRunner(runner)
        result = sweeper.sweep_lambda_c(
            sweep_dataset, values=[0.0, 0.25]
        )
        assert result.parameter_name == "lambda_c"
        assert len(result.results) == 2

    def test_sweep_base_config_not_mutated(self, sweep_dataset):
        """Sweeps should not permanently modify the runner's base_config."""
        runner = ExperimentRunner(
            base_config=DecodingConfig(top_m=50, beta=0.2, lambda_c=0.25)
        )
        sweeper = ParameterSweepRunner(runner)
        sweeper.sweep_beta(sweep_dataset, values=[0.5, 1.0])
        assert runner.base_config.beta == pytest.approx(0.2)
        sweeper.sweep_top_m(sweep_dataset, values=[999])
        assert runner.base_config.top_m == 50
        sweeper.sweep_lambda_c(sweep_dataset, values=[0.99])
        assert runner.base_config.lambda_c == pytest.approx(0.25)


# ===========================================================================
# StepLogger enhanced summary
# ===========================================================================


class TestStepLoggerEnhanced:
    def test_summary_includes_new_fields(self):
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
                    sf_baseline=0.75,
                    sb_baseline=0.65,
                    delta_sf=0.05,
                    delta_sb=0.05,
                    kl_base_mod=0.1 if i < 5 else 0.0,
                    entropy_delta=-0.05 if i < 5 else 0.0,
                )
            )
        summary = logger.summary()
        assert "rerank_worsened_rate" in summary
        assert "rerank_net_benefit" in summary
        assert "mean_delta_sf" in summary
        assert "mean_delta_sb" in summary
        assert "mean_kl_base_mod" in summary
        assert "mean_entropy_delta" in summary

    def test_rerank_net_benefit_correct(self):
        logger = StepLogger()
        # 3 changed: 2 correct, 1 wrong
        logger.log(StepRecord(step_index=0, predicted_token=0, correct=True, rerank_changed=True))
        logger.log(StepRecord(step_index=1, predicted_token=1, correct=True, rerank_changed=True))
        logger.log(StepRecord(step_index=2, predicted_token=2, correct=False, rerank_changed=True))
        logger.log(StepRecord(step_index=3, predicted_token=3, correct=True, rerank_changed=False))

        assert logger.rerank_improvement_rate() == pytest.approx(2 / 3)
        assert logger.rerank_worsened_rate() == pytest.approx(1 / 3)
        assert logger.rerank_net_benefit() == pytest.approx(1 / 3)
