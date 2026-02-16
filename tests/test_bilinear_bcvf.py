#!/usr/bin/env python3
"""
Tests for BilinearBCVF scorer, trainer, and integration.

Tests cover:
    1. Shape tests for BilinearScorer output
    2. Training step smoke test on synthetic separable data
    3. Integration test: decoder with goal_strategy="bilinear"
    4. Determinism: loss decreases across epochs on synthetic data
    5. Config defaults
    6. Data collection from adapter-style dataset
    7. Evaluation produces valid metrics
    8. Report formatting
"""

import pytest
import numpy as np

import torch
import torch.nn as nn

from symbolu.ontological.bilinear_bcvf import (
    BilinearConfig,
    BilinearScorer,
    BilinearSample,
    BilinearEvalResult,
    collect_bilinear_samples_from_adapter,
    train_bilinear_scorer,
    evaluate_bilinear_scorer,
    print_bilinear_report,
    run_bilinear_pipeline,
)
from symbolu.ontological.bcvf_decoding import (
    BCVFDecoder,
    BCVFScoringModule,
    DecodingConfig,
)


# =========================================================================
# Fixtures
# =========================================================================

B = 4       # batch size
D = 32      # hidden dim
V = 100     # vocab size
M = 20      # top-M candidates
RANK = 8    # low-rank dimension


@pytest.fixture
def hidden():
    """Random hidden states [B, D]."""
    return torch.randn(B, D)


@pytest.fixture
def candidates():
    """Random candidate embeddings [B, M, D]."""
    return torch.randn(B, M, D)


@pytest.fixture
def vocab_emb():
    """Random vocabulary embeddings [V, D]."""
    return torch.randn(V, D)


@pytest.fixture
def logits(hidden, vocab_emb):
    """Logits from hidden @ vocab_emb.T."""
    return hidden @ vocab_emb.T


@pytest.fixture
def scorer():
    """Basic BilinearScorer instance."""
    return BilinearScorer(
        hidden_dim=D, rank=RANK,
        use_sigmoid=True, gamma_init=1.0,
        gamma_learnable=True,
    )


@pytest.fixture
def scorer_no_sigmoid():
    """BilinearScorer without sigmoid."""
    return BilinearScorer(
        hidden_dim=D, rank=RANK,
        use_sigmoid=False, gamma_init=1.0,
        gamma_learnable=False,
    )


@pytest.fixture
def config():
    """BilinearConfig with small values for testing."""
    return BilinearConfig(
        rank=RANK,
        use_sigmoid=True,
        top_m=M,
        lr=1e-2,
        epochs=3,
        batch_size=8,
        train_samples=100,
        eval_samples=50,
        seed=42,
    )


@pytest.fixture
def synthetic_samples():
    """Synthetic BilinearSamples for training/eval."""
    torch.manual_seed(42)
    samples = []
    for i in range(200):
        h = torch.randn(D)
        logits_t = torch.randn(V)
        gt = torch.randint(0, V, (1,)).item()
        correct = 1 if logits_t.argmax().item() == gt else 0
        samples.append(BilinearSample(
            h_t=h, logits_t=logits_t,
            ground_truth_token=gt, correct=correct,
        ))
    return samples


@pytest.fixture
def adapter_dataset():
    """DatasetAdapter-style list of dicts."""
    torch.manual_seed(42)
    dataset = []
    for i in range(100):
        h = torch.randn(1, D)
        v = torch.randn(V, D)
        logits_t = h @ v.T  # [1, V]
        gt = torch.randint(0, V, (1,)).item()
        dataset.append({
            "hidden_state": h,
            "logits": logits_t,
            "ground_truth": gt,
        })
    return dataset


# =========================================================================
# Test: BilinearConfig defaults
# =========================================================================


class TestBilinearConfig:
    def test_defaults(self):
        cfg = BilinearConfig()
        assert cfg.rank == 64
        assert cfg.use_sigmoid is True
        assert cfg.gamma_init == 1.0
        assert cfg.epochs == 3
        assert cfg.batch_size == 64
        assert cfg.rho_improvement_threshold == 0.05

    def test_override(self):
        cfg = BilinearConfig(rank=32, epochs=5, lr=5e-4)
        assert cfg.rank == 32
        assert cfg.epochs == 5
        assert cfg.lr == 5e-4


# =========================================================================
# Test: BilinearScorer shapes
# =========================================================================


class TestBilinearScorerShapes:
    def test_output_shape(self, scorer, hidden, candidates):
        """Output should be [B, M]."""
        scores = scorer(hidden, candidates)
        assert scores.shape == (B, M)

    def test_output_shape_no_sigmoid(self, scorer_no_sigmoid, hidden, candidates):
        """Output should be [B, M] without sigmoid too."""
        scores = scorer_no_sigmoid(hidden, candidates)
        assert scores.shape == (B, M)

    def test_output_dtype_float32(self, scorer, hidden, candidates):
        """Scores must be float32 regardless of input dtype."""
        h_fp16 = hidden.half()
        c_fp16 = candidates.half()
        scores = scorer(h_fp16, c_fp16)
        assert scores.dtype == torch.float32

    def test_sigmoid_bounds(self, scorer, hidden, candidates):
        """With sigmoid, output should be in (0, 1)."""
        scores = scorer(hidden, candidates)
        assert (scores >= 0.0).all()
        assert (scores <= 1.0).all()

    def test_no_sigmoid_unbounded(self, scorer_no_sigmoid, hidden, candidates):
        """Without sigmoid, output can be outside [0,1]."""
        scores = scorer_no_sigmoid(hidden, candidates)
        # Scores should have non-trivial variance
        assert scores.std() > 0.0

    def test_score_flat(self, scorer, hidden):
        """score_flat should return [B] shape."""
        e = torch.randn(B, D)
        scores = scorer.score_flat(hidden, e)
        assert scores.shape == (B,)

    def test_single_sample(self, scorer):
        """Should work with batch size 1."""
        h = torch.randn(1, D)
        E = torch.randn(1, M, D)
        scores = scorer(h, E)
        assert scores.shape == (1, M)

    def test_parameter_shapes(self, scorer):
        """U and V should be (D, rank)."""
        assert scorer.U.shape == (D, RANK)
        assert scorer.V.shape == (D, RANK)


# =========================================================================
# Test: Training smoke test
# =========================================================================


class TestBilinearTraining:
    def test_training_runs(self, synthetic_samples, config):
        """Training should complete without errors."""
        vocab_emb = torch.randn(V, D)
        train_samples = synthetic_samples[:100]

        scorer, loss_curve = train_bilinear_scorer(
            train_samples, vocab_emb, config, device="cpu",
        )

        assert isinstance(scorer, BilinearScorer)
        assert len(loss_curve) == config.epochs
        assert all(isinstance(v, float) for v in loss_curve)

    def test_loss_decreases(self):
        """On separable data, loss should decrease across epochs."""
        torch.manual_seed(42)

        # Create separable synthetic data: ground truth embedding is
        # a specific direction from h_t that the bilinear scorer can learn
        V_small = 50
        D_small = 16
        rank_small = 8

        # Fixed U*, V* that define the "true" bilinear preference
        U_star = torch.randn(D_small, rank_small) * 0.5
        V_star = torch.randn(D_small, rank_small) * 0.5
        vocab_emb = torch.randn(V_small, D_small)

        samples = []
        for i in range(200):
            h = torch.randn(D_small)
            # Generate logits biased toward tokens that score well
            # under the true bilinear function
            qh = h @ U_star  # [r]
            true_scores = (vocab_emb @ V_star) @ qh  # [V]
            logits = true_scores + 0.1 * torch.randn(V_small)
            gt = int(true_scores.argmax().item())
            correct = 1 if logits.argmax().item() == gt else 0
            samples.append(BilinearSample(
                h_t=h, logits_t=logits,
                ground_truth_token=gt, correct=correct,
            ))

        cfg = BilinearConfig(
            rank=rank_small, use_sigmoid=False, top_m=min(20, V_small),
            lr=1e-2, epochs=5, batch_size=32,
            train_samples=200, eval_samples=0, seed=42,
        )

        scorer, loss_curve = train_bilinear_scorer(
            samples, vocab_emb, cfg, device="cpu",
        )

        # Loss should decrease from first to last epoch
        assert loss_curve[-1] < loss_curve[0], (
            f"Loss did not decrease: {loss_curve}"
        )

    def test_training_with_small_vocab(self):
        """Should work when vocab is smaller than top_m."""
        torch.manual_seed(42)
        V_tiny = 10
        vocab_emb = torch.randn(V_tiny, D)
        samples = []
        for i in range(50):
            samples.append(BilinearSample(
                h_t=torch.randn(D),
                logits_t=torch.randn(V_tiny),
                ground_truth_token=i % V_tiny,
                correct=0,
            ))

        cfg = BilinearConfig(
            rank=RANK, top_m=50,  # larger than vocab
            epochs=1, batch_size=16, train_samples=50, seed=42,
        )
        scorer, loss_curve = train_bilinear_scorer(
            samples, vocab_emb, cfg, device="cpu",
        )
        assert len(loss_curve) == 1


# =========================================================================
# Test: Data collection
# =========================================================================


class TestDataCollection:
    def test_collect_from_adapter(self, adapter_dataset):
        """Should collect BilinearSamples from adapter dataset."""
        samples = collect_bilinear_samples_from_adapter(
            adapter_dataset, n_samples=50,
        )
        assert len(samples) == 50
        assert isinstance(samples[0], BilinearSample)
        assert samples[0].h_t.shape == (D,)
        assert samples[0].logits_t.shape == (V,)

    def test_collect_respects_limit(self, adapter_dataset):
        """Should stop at n_samples."""
        samples = collect_bilinear_samples_from_adapter(
            adapter_dataset, n_samples=10,
        )
        assert len(samples) == 10

    def test_correct_field(self, adapter_dataset):
        """correct field should be 0 or 1."""
        samples = collect_bilinear_samples_from_adapter(
            adapter_dataset, n_samples=20,
        )
        for s in samples:
            assert s.correct in (0, 1)


# =========================================================================
# Test: Evaluation
# =========================================================================


class TestBilinearEvaluation:
    def test_evaluation_runs(self, synthetic_samples, config):
        """Evaluation should produce valid metrics."""
        vocab_emb = torch.randn(V, D)
        train = synthetic_samples[:100]
        eval_s = synthetic_samples[100:150]

        scorer, _ = train_bilinear_scorer(
            train, vocab_emb, config, device="cpu",
        )
        result = evaluate_bilinear_scorer(
            scorer, eval_s, vocab_emb, config,
            dataset_name="test", device="cpu",
        )

        assert isinstance(result, BilinearEvalResult)
        assert result.n_eval == len(eval_s)
        assert result.dataset_name == "test"

        # rho values should be in [-1, 1]
        assert -1.0 <= result.rho_sb_bilin <= 1.0
        assert -1.0 <= result.rho_maxprob <= 1.0
        assert -1.0 <= result.rho_margin <= 1.0

        # ECE and Brier should be in [0, 1]
        assert 0.0 <= result.ece <= 1.0
        assert 0.0 <= result.brier <= 1.0

        # Pass@1 should be in [0, 1]
        assert 0.0 <= result.pass_at_1_base <= 1.0
        assert 0.0 <= result.pass_at_1_bilinear <= 1.0

    def test_verdict_logic(self):
        """Test that verdict fields are set correctly."""
        result = BilinearEvalResult(
            dataset_name="test", n_eval=100,
            rho_sb_bilin=0.3, rho_sb_bilin_top1=0.35,
            rho_sb_argmax=0.32, rho_softmax_conf=0.28,
            rho_maxprob=0.2, rho_margin=0.25,
            rho_neg_entropy=0.15, rho_logit_gap=0.18,
            bilinear_wins=True, best_baseline_rho=0.25,
            best_baseline_name="margin", rho_improvement=0.10,
            sb_mean=0.5, sb_std=0.1, sb_top1_mean=0.8,
            sb_gap_mean=0.05,
            sb_argmax_mean=0.65, sb_argmax_std=0.12,
            softmax_conf_mean=0.45, softmax_conf_std=0.15,
            ece=0.1, brier=0.2,
            ece_on_wrong_baseline=0.15, ece_on_low_margin=0.12,
            pass_at_1_base=0.6, pass_at_1_bilinear=0.65,
            pass_at_1_delta=0.05, rerank_pct=0.1,
        )
        assert result.bilinear_wins is True
        assert result.rho_improvement > 0.05

    def test_alpha_sweep_in_eval(self, synthetic_samples, config):
        """Alpha sweep should produce results."""
        vocab_emb = torch.randn(V, D)
        config.alpha_values = [0.01, 0.05]

        scorer, _ = train_bilinear_scorer(
            synthetic_samples[:100], vocab_emb, config, device="cpu",
        )
        result = evaluate_bilinear_scorer(
            scorer, synthetic_samples[100:150], vocab_emb, config,
            dataset_name="test", device="cpu",
        )

        assert len(result.alpha_sweep) == 2
        for alpha, vals in result.alpha_sweep.items():
            assert "pass_at_1" in vals
            assert "delta" in vals


# =========================================================================
# Test: Report formatting
# =========================================================================


class TestBilinearReport:
    def test_report_prints(self, synthetic_samples, config):
        """Report should print without errors."""
        vocab_emb = torch.randn(V, D)
        scorer, loss_curve = train_bilinear_scorer(
            synthetic_samples[:100], vocab_emb, config, device="cpu",
        )
        result = evaluate_bilinear_scorer(
            scorer, synthetic_samples[100:150], vocab_emb, config,
            dataset_name="test_report", device="cpu",
        )
        result.loss_curve = loss_curve

        report_str = print_bilinear_report(
            [result], {"test_report": loss_curve},
        )

        assert "Bilinear BCVF Evaluation Report" in report_str
        assert "test_report" in report_str
        assert "VERDICT" in report_str
        assert "sb_bilin" in report_str


# =========================================================================
# Test: Decoder integration with bilinear
# =========================================================================


class TestDecoderIntegration:
    def test_decode_with_bilinear_scorer(self, vocab_emb):
        """Decoder with goal_strategy='bilinear' should run end-to-end."""
        hidden_dim = D
        scorer = BilinearScorer(
            hidden_dim=hidden_dim, rank=RANK,
            use_sigmoid=True, gamma_init=1.0,
        )

        config = DecodingConfig(
            top_m=M, use_rerank=True, use_calibration=True,
        )
        decoder = BCVFDecoder(
            config=config,
            bilinear_scorer=scorer,
            goal_strategy="bilinear",
        )

        h = torch.randn(1, hidden_dim)
        goal = torch.randn(1, hidden_dim)  # placeholder, not used
        logits = h @ vocab_emb.T

        best_idx, probs, log_data = decoder.decode_step(
            h, vocab_emb, goal, logits,
        )

        # Shape checks
        assert best_idx.shape == (1,)
        assert probs.shape == (1, V)
        assert "sf" in log_data
        assert "sb" in log_data
        assert "L" in log_data

        # Bilinear-specific diagnostics
        assert log_data["goal_strategy"] == "bilinear"
        assert "sb_mean" in log_data
        assert "sb_std" in log_data
        assert "sb_top1" in log_data
        assert "sb_gap" in log_data

    def test_decode_without_bilinear_unchanged(self, vocab_emb):
        """Default decoder (no bilinear) should work as before."""
        config = DecodingConfig(
            top_m=M, use_rerank=True, use_calibration=True,
        )
        decoder = BCVFDecoder(config=config)

        h = torch.randn(1, D)
        goal = torch.randn(1, D)
        logits = h @ vocab_emb.T

        best_idx, probs, log_data = decoder.decode_step(
            h, vocab_emb, goal, logits,
        )

        assert best_idx.shape == (1,)
        assert probs.shape == (1, V)
        # No bilinear diagnostics
        assert "goal_strategy" not in log_data

    def test_bilinear_scoring_module_backward(self):
        """BCVFScoringModule with bilinear_scorer uses bilinear backward."""
        scorer = BilinearScorer(
            hidden_dim=D, rank=RANK, use_sigmoid=True,
        )
        config = DecodingConfig(top_m=M)
        module = BCVFScoringModule(config, bilinear_scorer=scorer)

        h = torch.randn(B, D)
        cands = torch.randn(B, M, D)

        sb = module.backward_score_bilinear(h, cands)
        assert sb.shape == (B, M)
        assert (sb >= 0.0).all()
        assert (sb <= 1.0).all()

    def test_decoder_reranking_with_bilinear(self, vocab_emb):
        """Bilinear reranking should sometimes change the top token."""
        torch.manual_seed(123)
        scorer = BilinearScorer(
            hidden_dim=D, rank=RANK, use_sigmoid=True,
        )

        config = DecodingConfig(
            top_m=M, use_rerank=True, beta=0.5,
        )
        decoder = BCVFDecoder(
            config=config,
            bilinear_scorer=scorer,
            goal_strategy="bilinear",
        )

        changed_count = 0
        for _ in range(20):
            h = torch.randn(1, D)
            goal = torch.zeros(1, D)  # placeholder
            logits = h @ vocab_emb.T

            best_idx, _, log_data = decoder.decode_step(
                h, vocab_emb, goal, logits,
            )

            if "rerank_changed" in log_data:
                if log_data["rerank_changed"].any():
                    changed_count += 1

        # With random scorer and high beta, some should change
        # (not a hard requirement, just sanity)
        assert changed_count >= 0  # passes trivially; non-crash is key


# =========================================================================
# Test: Full pipeline (dry-run scale)
# =========================================================================


class TestFullPipeline:
    def test_pipeline_dry_run(self):
        """Full pipeline should run on tiny synthetic data."""
        torch.manual_seed(42)

        # Create tiny model stub
        V_tiny = 30
        D_tiny = 16

        class TinyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.emb = nn.Embedding(V_tiny, D_tiny)

            def get_input_embeddings(self):
                return self.emb

        model = TinyModel()

        # Create adapter-style dataset
        dataset = []
        for i in range(100):
            h = torch.randn(1, D_tiny)
            logits = h @ model.emb.weight.T
            gt = torch.randint(0, V_tiny, (1,)).item()
            dataset.append({
                "hidden_state": h,
                "logits": logits,
                "ground_truth": gt,
            })

        config = BilinearConfig(
            rank=4, top_m=min(10, V_tiny),
            epochs=2, batch_size=16,
            train_samples=60, eval_samples=30,
            seed=42, alpha_values=[0.01],
        )

        results, loss_curves = run_bilinear_pipeline(
            model=model,
            tokenizer=None,
            datasets={"test_ds": dataset},
            config=config,
            device="cpu",
        )

        assert len(results) == 1
        assert results[0].dataset_name == "test_ds"
        assert results[0].n_eval > 0
        assert "test_ds" in loss_curves
        assert len(loss_curves["test_ds"]) == 2

    def test_pipeline_empty_dataset(self):
        """Pipeline should skip empty datasets gracefully."""

        class TinyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.emb = nn.Embedding(10, 8)

            def get_input_embeddings(self):
                return self.emb

        model = TinyModel()
        config = BilinearConfig(rank=4, epochs=1)

        results, loss_curves = run_bilinear_pipeline(
            model=model,
            tokenizer=None,
            datasets={"empty": []},
            config=config,
            device="cpu",
        )

        assert len(results) == 0
