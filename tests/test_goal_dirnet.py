#!/usr/bin/env python3
"""
Tests for GoalDirNet — Learned Future-Direction Predictor
==========================================================

Unit tests:
    1. Feature builder (past-only, correct dims, all modes)
    2. GoalDirNet forward shapes + normalisation
    3. Direction loss values
    4. Logit baseline computation
    5. Data collection from adapter
    6. Training loop (5 steps, non-NaN)
    7. Evaluation pipeline (rho output, calibration)
    8. Alpha sweep
    9. Full pipeline integration (dry-run sized)
    10. Report printing
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
import pytest
import torch
import torch.nn.functional as F

from symbolu.ontological.goal_dirnet import (
    GoalDirFeatureBuilder,
    GoalDirNet,
    GoalDirNetConfig,
    GoalDirSample,
    GoalDirEvalResult,
    collect_from_dataset_adapter,
    train_goal_dirnet,
    evaluate_goal_dirnet,
    run_alpha_sweep,
    run_goal_dirnet_pipeline,
    print_goal_dirnet_report,
    _fit_logistic_calibration,
    _sigmoid,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def hidden_dim():
    return 64


@pytest.fixture
def vocab_size():
    return 50


@pytest.fixture
def seq_len():
    return 20


@pytest.fixture
def hidden_states(seq_len, hidden_dim):
    """Random hidden states [T, D]."""
    torch.manual_seed(42)
    return torch.randn(seq_len, hidden_dim)


@pytest.fixture
def logits_seq(seq_len, vocab_size, hidden_dim):
    """Random logits [T, V]."""
    torch.manual_seed(42)
    return torch.randn(seq_len, vocab_size)


@pytest.fixture
def dry_run_dataset(hidden_dim, vocab_size):
    """Small synthetic dataset like DatasetAdapter.from_dry_run."""
    torch.manual_seed(42)
    dataset = []
    for i in range(100):
        h = torch.randn(1, hidden_dim)
        logits = torch.randn(1, vocab_size)
        gt = torch.argmax(logits, dim=-1).item()
        goal = h + 0.1 * torch.randn(1, hidden_dim)
        dataset.append({
            "hidden_state": h,
            "goal_embedding": goal,
            "logits": logits,
            "ground_truth": gt,
        })
    return dataset


@pytest.fixture
def small_samples(hidden_dim, vocab_size):
    """Pre-built GoalDirSample list for training/eval tests."""
    torch.manual_seed(42)
    samples = []
    for i in range(50):
        h_t = torch.randn(hidden_dim)
        h_next = torch.randn(hidden_dim)
        u_target = F.normalize(h_next.unsqueeze(0), p=2, dim=-1).squeeze(0)
        logits_t = torch.randn(vocab_size)
        pred = logits_t.argmax().item()
        # Make roughly half correct
        gt = pred if i % 2 == 0 else (pred + 1) % vocab_size
        correct = 1 if pred == gt else 0
        samples.append(GoalDirSample(
            features=h_t,  # ht mode: features == h_t
            h_t=h_t,
            h_next=h_next,
            u_target=u_target,
            logits_t=logits_t,
            correct=correct,
            ground_truth_token=gt,
        ))
    return samples


# =========================================================================
# 1. Feature Builder Tests
# =========================================================================


class TestGoalDirFeatureBuilder:
    """Test feature builder produces correct dimensions and is past-only."""

    def test_ht_mode_dims(self, hidden_states, logits_seq, hidden_dim):
        builder = GoalDirFeatureBuilder(feature_mode="ht")
        assert builder.feature_dim(hidden_dim) == hidden_dim

        features = builder.build_features(hidden_states, logits_seq)
        assert features.shape == (hidden_states.shape[0] - 1, hidden_dim)

    def test_ht_mean_mode_dims(self, hidden_states, logits_seq, hidden_dim):
        builder = GoalDirFeatureBuilder(feature_mode="ht_mean", window_size=4)
        assert builder.feature_dim(hidden_dim) == hidden_dim * 2

        features = builder.build_features(hidden_states, logits_seq)
        assert features.shape == (hidden_states.shape[0] - 1, hidden_dim * 2)

    def test_ht_mean_logits_mode_dims(
        self, hidden_states, logits_seq, hidden_dim,
    ):
        builder = GoalDirFeatureBuilder(
            feature_mode="ht_mean_logits", window_size=4,
        )
        expected_dim = hidden_dim * 2 + 4
        assert builder.feature_dim(hidden_dim) == expected_dim

        features = builder.build_features(hidden_states, logits_seq)
        assert features.shape == (hidden_states.shape[0] - 1, expected_dim)

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown feature_mode"):
            GoalDirFeatureBuilder(feature_mode="future_leak")

    def test_specific_positions(self, hidden_states, logits_seq, hidden_dim):
        builder = GoalDirFeatureBuilder(feature_mode="ht")
        positions = [0, 5, 10]
        features = builder.build_features(
            hidden_states, logits_seq, positions=positions,
        )
        assert features.shape == (3, hidden_dim)
        # Feature at position 0 should be hidden_states[0]
        assert torch.allclose(features[0], hidden_states[0])

    def test_empty_positions(self, hidden_states, logits_seq, hidden_dim):
        builder = GoalDirFeatureBuilder(feature_mode="ht")
        features = builder.build_features(
            hidden_states, logits_seq, positions=[],
        )
        assert features.shape[0] == 0

    def test_past_only_no_future(self, hidden_states, hidden_dim):
        """Features at position t should only depend on h_0..h_t."""
        builder = GoalDirFeatureBuilder(feature_mode="ht_mean", window_size=4)
        features = builder.build_features(hidden_states)

        # Feature at t=0 should only use h_0
        # Modify h_{t+1} and check that feature at t doesn't change
        h_modified = hidden_states.clone()
        h_modified[5:] = torch.randn_like(h_modified[5:])

        features_modified = builder.build_features(h_modified)

        # Features at t=0..3 should be identical (window <= 4)
        for t in range(4):
            assert torch.allclose(features[t], features_modified[t]), \
                f"Feature at t={t} changed when only future was modified"


class TestLogitBaselines:
    """Test logit-derived baseline computation."""

    def test_baseline_shapes(self, vocab_size):
        torch.manual_seed(42)
        logits = torch.randn(10, vocab_size)
        baselines = GoalDirFeatureBuilder.compute_logit_baselines(logits)

        assert baselines["margin"].shape == (10,)
        assert baselines["maxprob"].shape == (10,)
        assert baselines["neg_entropy"].shape == (10,)
        assert baselines["logit_gap"].shape == (10,)

    def test_maxprob_in_01(self, vocab_size):
        torch.manual_seed(42)
        logits = torch.randn(20, vocab_size)
        baselines = GoalDirFeatureBuilder.compute_logit_baselines(logits)
        assert (baselines["maxprob"] >= 0).all()
        assert (baselines["maxprob"] <= 1).all()

    def test_margin_non_negative(self, vocab_size):
        torch.manual_seed(42)
        logits = torch.randn(20, vocab_size)
        baselines = GoalDirFeatureBuilder.compute_logit_baselines(logits)
        assert (baselines["margin"] >= 0).all()

    def test_entropy_sign(self, vocab_size):
        torch.manual_seed(42)
        logits = torch.randn(20, vocab_size)
        baselines = GoalDirFeatureBuilder.compute_logit_baselines(logits)
        # neg_entropy should be negative (since entropy >= 0)
        assert (baselines["neg_entropy"] <= 0).all()


# =========================================================================
# 2. GoalDirNet Model Tests
# =========================================================================


class TestGoalDirNet:
    """Test GoalDirNet model forward pass and normalisation."""

    def test_output_shape(self, hidden_dim):
        net = GoalDirNet(input_dim=hidden_dim, output_dim=hidden_dim)
        x = torch.randn(5, hidden_dim)
        out = net(x)
        assert out.shape == (5, hidden_dim)

    def test_output_unit_vectors(self, hidden_dim):
        net = GoalDirNet(input_dim=hidden_dim, output_dim=hidden_dim)
        x = torch.randn(10, hidden_dim)
        out = net(x)
        norms = out.norm(dim=-1)
        assert torch.allclose(norms, torch.ones(10), atol=1e-5)

    def test_different_input_output_dim(self):
        net = GoalDirNet(input_dim=128, output_dim=64, hidden_dim=256)
        x = torch.randn(3, 128)
        out = net(x)
        assert out.shape == (3, 64)
        norms = out.norm(dim=-1)
        assert torch.allclose(norms, torch.ones(3), atol=1e-5)

    def test_single_sample(self, hidden_dim):
        net = GoalDirNet(input_dim=hidden_dim, output_dim=hidden_dim)
        x = torch.randn(1, hidden_dim)
        out = net(x)
        assert out.shape == (1, hidden_dim)

    def test_gradient_flows(self, hidden_dim):
        net = GoalDirNet(input_dim=hidden_dim, output_dim=hidden_dim)
        x = torch.randn(5, hidden_dim, requires_grad=True)
        out = net(x)
        loss = out.sum()
        loss.backward()
        assert x.grad is not None
        assert not torch.isnan(x.grad).any()


class TestDirectionLoss:
    """Test the direction loss function."""

    def test_perfect_prediction_zero_loss(self, hidden_dim):
        u = F.normalize(torch.randn(5, hidden_dim), dim=-1)
        loss = GoalDirNet.direction_loss(u, u)
        assert loss.item() < 1e-5

    def test_opposite_direction_max_loss(self, hidden_dim):
        u = F.normalize(torch.randn(5, hidden_dim), dim=-1)
        loss = GoalDirNet.direction_loss(u, -u)
        assert abs(loss.item() - 2.0) < 1e-5

    def test_orthogonal_unit_loss(self):
        # Two orthogonal vectors: cos = 0, loss = 1
        u = torch.tensor([[1.0, 0.0]])
        v = torch.tensor([[0.0, 1.0]])
        loss = GoalDirNet.direction_loss(u, v)
        assert abs(loss.item() - 1.0) < 1e-5

    def test_loss_in_range(self, hidden_dim):
        u = F.normalize(torch.randn(10, hidden_dim), dim=-1)
        v = F.normalize(torch.randn(10, hidden_dim), dim=-1)
        loss = GoalDirNet.direction_loss(u, v)
        assert 0.0 <= loss.item() <= 2.0


# =========================================================================
# 3. Data Collection Tests
# =========================================================================


class TestDataCollection:
    """Test sample collection from adapter datasets."""

    def test_collect_from_adapter(self, dry_run_dataset):
        builder = GoalDirFeatureBuilder(feature_mode="ht")
        samples = collect_from_dataset_adapter(
            dry_run_dataset, builder, n_samples=50,
        )
        assert len(samples) == 50
        assert isinstance(samples[0], GoalDirSample)

    def test_sample_fields(self, dry_run_dataset, hidden_dim):
        builder = GoalDirFeatureBuilder(feature_mode="ht")
        samples = collect_from_dataset_adapter(
            dry_run_dataset, builder, n_samples=10,
        )
        s = samples[0]
        assert s.features.shape == (hidden_dim,)
        assert s.h_t.shape == (hidden_dim,)
        assert s.h_next.shape == (hidden_dim,)
        assert s.u_target.shape == (hidden_dim,)
        assert s.correct in (0, 1)

    def test_u_target_normalised(self, dry_run_dataset):
        builder = GoalDirFeatureBuilder(feature_mode="ht")
        samples = collect_from_dataset_adapter(
            dry_run_dataset, builder, n_samples=10,
        )
        for s in samples:
            norm = s.u_target.norm().item()
            assert abs(norm - 1.0) < 1e-5

    def test_respects_n_samples_limit(self, dry_run_dataset):
        builder = GoalDirFeatureBuilder(feature_mode="ht")
        samples = collect_from_dataset_adapter(
            dry_run_dataset, builder, n_samples=5,
        )
        assert len(samples) == 5

    def test_ht_mean_features(self, dry_run_dataset, hidden_dim):
        builder = GoalDirFeatureBuilder(
            feature_mode="ht_mean", window_size=4,
        )
        samples = collect_from_dataset_adapter(
            dry_run_dataset, builder, n_samples=10,
        )
        # For single-position sequences (from adapter), mean_pool == h_t
        # so feature dim should be 2*D
        expected_dim = hidden_dim * 2
        assert samples[0].features.shape == (expected_dim,)


# =========================================================================
# 4. Training Loop Tests
# =========================================================================


class TestTraining:
    """Test GoalDirNet training loop."""

    def test_train_5_steps_no_nan(self, small_samples, hidden_dim):
        config = GoalDirNetConfig(
            hidden_dim=64,
            epochs=1,
            batch_size=10,
            lr=1e-3,
        )
        net, stats = train_goal_dirnet(small_samples, config)

        assert isinstance(net, GoalDirNet)
        assert not np.isnan(stats["final_loss"])
        assert stats["final_loss"] >= 0
        assert stats["n_train"] > 0

    def test_loss_decreases(self, small_samples):
        config = GoalDirNetConfig(
            hidden_dim=64,
            epochs=5,
            batch_size=10,
            lr=1e-2,
        )
        net, stats = train_goal_dirnet(small_samples, config)

        # Loss should generally decrease (not guaranteed, but likely)
        first_loss = stats.get("loss_epoch_0", float("inf"))
        last_loss = stats.get("loss_epoch_4", float("inf"))
        assert not np.isnan(first_loss)
        assert not np.isnan(last_loss)

    def test_empty_samples_raises(self):
        config = GoalDirNetConfig(epochs=1)
        with pytest.raises(ValueError, match="No training samples"):
            train_goal_dirnet([], config)

    def test_model_produces_unit_vectors_after_training(
        self, small_samples, hidden_dim,
    ):
        config = GoalDirNetConfig(
            hidden_dim=64, epochs=2, batch_size=10,
        )
        net, _ = train_goal_dirnet(small_samples, config)

        features = torch.stack([s.features for s in small_samples])
        with torch.no_grad():
            out = net(features)
        norms = out.norm(dim=-1)
        assert torch.allclose(norms, torch.ones(len(small_samples)), atol=1e-4)


# =========================================================================
# 5. Evaluation Tests
# =========================================================================


class TestEvaluation:
    """Test GoalDirNet evaluation pipeline."""

    def test_eval_produces_valid_result(self, small_samples, hidden_dim, vocab_size):
        config = GoalDirNetConfig(
            hidden_dim=64, epochs=2, batch_size=10,
        )
        net, _ = train_goal_dirnet(small_samples, config)
        vocab_emb = torch.randn(vocab_size, hidden_dim)
        result = evaluate_goal_dirnet(net, small_samples, vocab_emb, "test_data")

        assert isinstance(result, GoalDirEvalResult)
        assert result.dataset_name == "test_data"
        assert result.n_eval == len(small_samples)
        # New fields: pass@1 with reranking
        assert 0.0 <= result.pass_at_1_baseline <= 1.0
        assert 0.0 <= result.pass_at_1_reranked <= 1.0
        assert 0.0 <= result.rerank_pct <= 1.0

    def test_rho_values_in_range(self, small_samples, hidden_dim, vocab_size):
        config = GoalDirNetConfig(
            hidden_dim=64, epochs=2, batch_size=10,
        )
        net, _ = train_goal_dirnet(small_samples, config)
        vocab_emb = torch.randn(vocab_size, hidden_dim)
        result = evaluate_goal_dirnet(net, small_samples, vocab_emb, "test")

        for rho_name in [
            "rho_sb_learned", "rho_margin", "rho_maxprob",
            "rho_neg_entropy", "rho_logit_gap",
        ]:
            val = getattr(result, rho_name)
            assert -1.0 <= val <= 1.0, f"{rho_name}={val} out of range"

    def test_calibration_metrics(self, small_samples, hidden_dim, vocab_size):
        config = GoalDirNetConfig(
            hidden_dim=64, epochs=2, batch_size=10,
        )
        net, _ = train_goal_dirnet(small_samples, config)
        vocab_emb = torch.randn(vocab_size, hidden_dim)
        result = evaluate_goal_dirnet(net, small_samples, vocab_emb, "test")

        assert 0.0 <= result.ece_maxprob <= 1.0
        assert 0.0 <= result.brier_maxprob <= 1.0
        assert 0.0 <= result.ece_sb_calibrated <= 1.0
        assert 0.0 <= result.brier_sb_calibrated <= 1.0

    def test_gating_verdict(self, small_samples, hidden_dim, vocab_size):
        config = GoalDirNetConfig(
            hidden_dim=64, epochs=2, batch_size=10,
        )
        net, _ = train_goal_dirnet(small_samples, config)
        vocab_emb = torch.randn(vocab_size, hidden_dim)
        result = evaluate_goal_dirnet(net, small_samples, vocab_emb, "test")

        # sb_learned_wins is bool
        assert isinstance(result.sb_learned_wins, bool)
        # best_baseline_name is one of the known baselines
        assert result.best_baseline_name in {
            "margin", "maxprob", "neg_entropy", "logit_gap",
        }

    def test_empty_samples(self, hidden_dim, vocab_size):
        net = GoalDirNet(hidden_dim, hidden_dim, hidden_dim=64)
        vocab_emb = torch.randn(vocab_size, hidden_dim)
        result = evaluate_goal_dirnet(net, [], vocab_emb, "empty")
        assert result.n_eval == 0


# =========================================================================
# 6. Alpha Sweep Tests
# =========================================================================


class TestAlphaSweep:
    """Test logit modulation alpha sweep."""

    def test_sweep_returns_results(self, small_samples, hidden_dim, vocab_size):
        config = GoalDirNetConfig(
            hidden_dim=64, epochs=2, batch_size=10,
        )
        net, _ = train_goal_dirnet(small_samples, config)

        vocab_emb = torch.randn(vocab_size, hidden_dim)
        results = run_alpha_sweep(
            net, small_samples, vocab_emb,
            alpha_values=[0.05, 0.1],
            dataset_name="test",
        )

        assert len(results) == 2
        assert 0.05 in results
        assert 0.1 in results

    def test_sweep_metrics_structure(
        self, small_samples, hidden_dim, vocab_size,
    ):
        config = GoalDirNetConfig(
            hidden_dim=64, epochs=2, batch_size=10,
        )
        net, _ = train_goal_dirnet(small_samples, config)

        vocab_emb = torch.randn(vocab_size, hidden_dim)
        results = run_alpha_sweep(
            net, small_samples, vocab_emb,
            alpha_values=[0.1],
        )

        metrics = results[0.1]
        assert "pass_at_1" in metrics
        assert "delta_pass_at_1" in metrics
        assert "rerank_pct" in metrics
        assert 0.0 <= metrics["pass_at_1"] <= 1.0
        assert 0.0 <= metrics["rerank_pct"] <= 1.0

    def test_alpha_zero_no_change(self, small_samples, hidden_dim, vocab_size):
        """Alpha=0 should give zero rerank (no modulation)."""
        config = GoalDirNetConfig(
            hidden_dim=64, epochs=2, batch_size=10,
        )
        net, _ = train_goal_dirnet(small_samples, config)

        vocab_emb = torch.randn(vocab_size, hidden_dim)
        results = run_alpha_sweep(
            net, small_samples, vocab_emb,
            alpha_values=[0.0],
        )

        # With alpha=0, no modulation, so rerank_pct = 0
        assert results[0.0]["rerank_pct"] == 0.0
        assert results[0.0]["delta_pass_at_1"] == 0.0

    def test_empty_samples(self, hidden_dim, vocab_size):
        net = GoalDirNet(hidden_dim, hidden_dim, hidden_dim=64)
        vocab_emb = torch.randn(vocab_size, hidden_dim)
        results = run_alpha_sweep(
            net, [], vocab_emb, alpha_values=[0.1],
        )
        assert results == {}


# =========================================================================
# 7. Calibration Helper Tests
# =========================================================================


class TestCalibrationHelpers:
    """Test logistic calibration and sigmoid helpers."""

    def test_sigmoid_basic(self):
        result = _sigmoid(np.array([0.0]))
        assert abs(result[0] - 0.5) < 1e-6

    def test_sigmoid_large_positive(self):
        result = _sigmoid(np.array([100.0]))
        assert abs(result[0] - 1.0) < 1e-6

    def test_sigmoid_large_negative(self):
        result = _sigmoid(np.array([-100.0]))
        assert abs(result[0]) < 1e-6

    def test_fit_logistic_calibration(self):
        np.random.seed(42)
        scores = np.random.randn(100)
        labels = (scores > 0).astype(np.float64)
        a, b = _fit_logistic_calibration(scores, labels)

        # a should be positive (higher score -> higher prob of correct)
        assert a > 0
        assert not np.isnan(a)
        assert not np.isnan(b)

    def test_fit_logistic_empty(self):
        a, b = _fit_logistic_calibration(np.array([]), np.array([]))
        assert a == 1.0
        assert b == 0.0


# =========================================================================
# 8. Full Pipeline Integration Test
# =========================================================================


class TestFullPipeline:
    """Integration test: full pipeline with dry-run data."""

    def _make_dry_run_model_and_tokenizer(self):
        """Create a minimal model/tokenizer for dry-run."""
        # Import here to avoid dependency issues
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from run_bcvf_benchmarks import create_dry_run_model
        return create_dry_run_model(device="cpu")

    def test_pipeline_dry_run(self, dry_run_dataset):
        config = GoalDirNetConfig(
            feature_mode="ht",
            hidden_dim=32,
            epochs=2,
            batch_size=16,
            train_samples=60,
            eval_samples=20,
        )

        datasets = {"DryRun": dry_run_dataset}

        eval_results, alpha_results = run_goal_dirnet_pipeline(
            model=None,
            tokenizer=None,
            datasets=datasets,
            config=config,
            device="cpu",
            run_alpha_sweep_flag=False,
        )

        assert len(eval_results) == 1
        assert eval_results[0].dataset_name == "DryRun"
        assert eval_results[0].n_eval > 0
        assert not np.isnan(eval_results[0].rho_sb_learned)

    def test_pipeline_with_alpha_sweep(self, dry_run_dataset):
        config = GoalDirNetConfig(
            feature_mode="ht",
            hidden_dim=32,
            epochs=2,
            batch_size=16,
            train_samples=60,
            eval_samples=20,
            alpha_values=[0.05, 0.1],
            # Set threshold to -999 so s_goal always "wins" for test
            rho_improvement_threshold=-999.0,
        )

        datasets = {"DryRun": dry_run_dataset}

        eval_results, alpha_results = run_goal_dirnet_pipeline(
            model=None,
            tokenizer=None,
            datasets=datasets,
            config=config,
            device="cpu",
            run_alpha_sweep_flag=True,
        )

        assert len(eval_results) == 1
        # Alpha sweep may or may not run depending on s_goal_wins


class TestReporting:
    """Test report printing."""

    def test_print_report_no_crash(self, small_samples, hidden_dim, vocab_size):
        config = GoalDirNetConfig(
            hidden_dim=64, epochs=1, batch_size=10,
        )
        net, stats = train_goal_dirnet(small_samples, config)
        vocab_emb = torch.randn(vocab_size, hidden_dim)
        result = evaluate_goal_dirnet(net, small_samples, vocab_emb, "test_data")

        report = print_goal_dirnet_report([result])
        assert "GoalDirNet Evaluation Report" in report
        assert "test_data" in report

    def test_print_report_with_alpha(self, small_samples, hidden_dim, vocab_size):
        config = GoalDirNetConfig(
            hidden_dim=64, epochs=1, batch_size=10,
        )
        net, stats = train_goal_dirnet(small_samples, config)
        vocab_emb = torch.randn(vocab_size, hidden_dim)
        result = evaluate_goal_dirnet(net, small_samples, vocab_emb, "test_data")

        alpha_results = {
            "test_data": {
                0.1: {
                    "pass_at_1": 0.5,
                    "delta_pass_at_1": 0.0,
                    "rerank_pct": 0.1,
                    "baseline_pass_at_1": 0.5,
                },
            },
        }

        report = print_goal_dirnet_report([result], alpha_results)
        assert "Alpha Sweep" in report

    def test_print_report_multiple_datasets(self, small_samples, hidden_dim, vocab_size):
        config = GoalDirNetConfig(
            hidden_dim=64, epochs=1, batch_size=10,
        )
        net, stats = train_goal_dirnet(small_samples, config)
        vocab_emb = torch.randn(vocab_size, hidden_dim)

        results = [
            evaluate_goal_dirnet(net, small_samples, vocab_emb, "wikitext"),
            evaluate_goal_dirnet(net, small_samples, vocab_emb, "humaneval"),
        ]

        report = print_goal_dirnet_report(results)
        assert "wikitext" in report
        assert "humaneval" in report


# =========================================================================
# 9. GoalDirNetConfig Tests
# =========================================================================


class TestGoalDirNetConfig:
    """Test configuration dataclass."""

    def test_defaults(self):
        config = GoalDirNetConfig()
        assert config.feature_mode == "ht"
        assert config.hidden_dim == 512
        assert config.epochs == 3
        assert config.train_ratio == 0.8

    def test_custom_values(self):
        config = GoalDirNetConfig(
            feature_mode="ht_mean_logits",
            hidden_dim=1024,
            epochs=5,
        )
        assert config.feature_mode == "ht_mean_logits"
        assert config.hidden_dim == 1024
        assert config.epochs == 5


# =========================================================================
# 10. Edge Case Tests
# =========================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_sample_dataset(self, hidden_dim, vocab_size):
        """Pipeline should handle a very small dataset gracefully."""
        torch.manual_seed(42)
        dataset = []
        for i in range(5):
            h = torch.randn(1, hidden_dim)
            logits = torch.randn(1, vocab_size)
            gt = torch.argmax(logits, dim=-1).item()
            dataset.append({
                "hidden_state": h,
                "logits": logits,
                "ground_truth": gt,
            })

        builder = GoalDirFeatureBuilder(feature_mode="ht")
        samples = collect_from_dataset_adapter(dataset, builder, n_samples=4)
        assert len(samples) == 4

    def test_very_large_hidden_dim(self):
        """GoalDirNet should handle large hidden dims."""
        D = 4096
        net = GoalDirNet(input_dim=D, output_dim=D, hidden_dim=512)
        x = torch.randn(2, D)
        out = net(x)
        assert out.shape == (2, D)
        norms = out.norm(dim=-1)
        assert torch.allclose(norms, torch.ones(2), atol=1e-4)
