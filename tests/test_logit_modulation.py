#!/usr/bin/env python3
"""
Tests for Logit Modulation Decoding Pipeline
==============================================

Covers:
    - LogitModulationConfig defaults and custom values
    - LogitModulator.modulate() correctness
    - LogitModulator.modulate_and_sample() end-to-end
    - ModulationMode configuration factory
    - RetrievalScorer (dot_product, cosine, external)
    - PenaltyScorer (repetition, blacklist, safety, constraint)
    - LogitModulationBenchmark (ablation, sweep, report)
    - Numeric stability (clamping, edge cases)
    - Shape validation and error handling
"""

import pytest
import numpy as np

# ---------------------------------------------------------------------------
# Check PyTorch availability
# ---------------------------------------------------------------------------
torch = pytest.importorskip("torch")
import torch.nn.functional as F

from symbolu.inference.logit_modulation import (
    LogitModulationConfig,
    LogitModulator,
    ModulationMode,
)
from symbolu.inference.retrieval_scorer import (
    RetrievalScorer,
    RetrievalScorerConfig,
    RetrievalStrategy,
)
from symbolu.inference.penalty_scorer import (
    PenaltyScorer,
    PenaltyScorerConfig,
)
from symbolu.inference.logit_modulation_benchmark import (
    BenchmarkMetrics,
    LogitModulationBenchmark,
    SweepResult,
    compute_brier_score,
    compute_ece,
    compute_pass_at_1,
    compute_spearman,
)


# ===========================================================================
# Fixtures
# ===========================================================================

B, D, V = 2, 64, 200


@pytest.fixture
def base_logits():
    torch.manual_seed(42)
    return torch.randn(B, V)


@pytest.fixture
def retrieval_scores():
    torch.manual_seed(43)
    return torch.randn(B, V)


@pytest.fixture
def penalty_scores():
    torch.manual_seed(44)
    return torch.rand(B, V) * 2.0  # Non-negative penalties


@pytest.fixture
def vocab_embeddings():
    torch.manual_seed(45)
    emb = torch.randn(V, D)
    return F.normalize(emb, dim=-1)


@pytest.fixture
def context_embedding():
    torch.manual_seed(46)
    emb = torch.randn(B, D)
    return F.normalize(emb, dim=-1)


@pytest.fixture
def target_ids():
    torch.manual_seed(47)
    return torch.randint(0, V, (B,))


# ===========================================================================
# LogitModulationConfig Tests
# ===========================================================================


class TestLogitModulationConfig:
    def test_defaults(self):
        cfg = LogitModulationConfig()
        assert cfg.alpha == 1.0
        assert cfg.beta == 1.0
        assert cfg.clamp_min == -50.0
        assert cfg.clamp_max == 50.0
        assert cfg.enable_retrieval is True
        assert cfg.enable_penalty is True

    def test_custom_values(self):
        cfg = LogitModulationConfig(alpha=0.5, beta=2.0)
        assert cfg.alpha == 0.5
        assert cfg.beta == 2.0


# ===========================================================================
# LogitModulator Tests
# ===========================================================================


class TestLogitModulator:
    def test_no_modification_when_disabled(self, base_logits):
        """When both retrieval and penalty are disabled, output equals clamped input."""
        cfg = LogitModulationConfig(enable_retrieval=False, enable_penalty=False)
        mod = LogitModulator(cfg)
        result = mod.modulate(base_logits)
        expected = torch.clamp(base_logits, min=-50, max=50)
        assert torch.allclose(result, expected)

    def test_retrieval_only(self, base_logits, retrieval_scores):
        """Retrieval-only mode adds α·R to base logits."""
        alpha = 0.5
        cfg = LogitModulationConfig(
            alpha=alpha, beta=0.0,
            enable_retrieval=True, enable_penalty=False,
        )
        mod = LogitModulator(cfg)
        result = mod.modulate(base_logits, retrieval_scores=retrieval_scores)
        expected = torch.clamp(base_logits + alpha * retrieval_scores, min=-50, max=50)
        assert torch.allclose(result, expected)

    def test_penalty_only(self, base_logits, penalty_scores):
        """Penalty-only mode subtracts β·C from base logits."""
        beta = 2.0
        cfg = LogitModulationConfig(
            alpha=0.0, beta=beta,
            enable_retrieval=False, enable_penalty=True,
        )
        mod = LogitModulator(cfg)
        result = mod.modulate(base_logits, penalty_scores=penalty_scores)
        expected = torch.clamp(base_logits - beta * penalty_scores, min=-50, max=50)
        assert torch.allclose(result, expected)

    def test_combined(self, base_logits, retrieval_scores, penalty_scores):
        """Combined mode: z + α·R − β·C."""
        alpha, beta = 1.0, 1.0
        cfg = LogitModulationConfig(alpha=alpha, beta=beta)
        mod = LogitModulator(cfg)
        result = mod.modulate(
            base_logits,
            retrieval_scores=retrieval_scores,
            penalty_scores=penalty_scores,
        )
        expected = torch.clamp(
            base_logits + alpha * retrieval_scores - beta * penalty_scores,
            min=-50, max=50,
        )
        assert torch.allclose(result, expected)

    def test_clamping(self):
        """Extreme logits are clamped to [-50, 50]."""
        cfg = LogitModulationConfig(alpha=100.0, clamp_min=-50.0, clamp_max=50.0)
        mod = LogitModulator(cfg)
        base = torch.zeros(1, 10)
        retrieval = torch.ones(1, 10)
        result = mod.modulate(base, retrieval_scores=retrieval)
        assert result.max().item() <= 50.0
        assert result.min().item() >= -50.0

    def test_shape_mismatch_retrieval(self, base_logits):
        """Shape mismatch in retrieval_scores raises ValueError."""
        cfg = LogitModulationConfig()
        mod = LogitModulator(cfg)
        bad_shape = torch.randn(1, V + 10)
        with pytest.raises(ValueError, match="retrieval_scores shape"):
            mod.modulate(base_logits, retrieval_scores=bad_shape)

    def test_shape_mismatch_penalty(self, base_logits):
        """Shape mismatch in penalty_scores raises ValueError."""
        cfg = LogitModulationConfig()
        mod = LogitModulator(cfg)
        bad_shape = torch.randn(1, V + 10)
        with pytest.raises(ValueError, match="penalty_scores shape"):
            mod.modulate(base_logits, penalty_scores=bad_shape)

    def test_modulate_and_sample(self, base_logits, retrieval_scores, penalty_scores):
        """modulate_and_sample returns valid token, probs, and meta."""
        cfg = LogitModulationConfig(alpha=0.5, beta=0.5)
        mod = LogitModulator(cfg)
        token, probs, meta = mod.modulate_and_sample(
            base_logits,
            retrieval_scores=retrieval_scores,
            penalty_scores=penalty_scores,
            temperature=0.8,
        )
        assert token.shape == (B, 1)
        assert probs.shape == (B, V)
        # Probabilities should sum to ~1
        assert torch.allclose(probs.sum(dim=-1), torch.ones(B), atol=1e-5)
        assert "alpha" in meta
        assert "beta" in meta
        assert "max_prob" in meta

    def test_modulate_and_sample_with_topk(self, base_logits):
        """Top-k filtering zeros out low-probability tokens."""
        cfg = LogitModulationConfig(enable_retrieval=False, enable_penalty=False)
        mod = LogitModulator(cfg)
        token, probs, meta = mod.modulate_and_sample(
            base_logits, top_k=10, temperature=1.0,
        )
        # At most top_k tokens should have non-zero probability
        nonzero = (probs > 0).sum(dim=-1)
        assert (nonzero <= 10).all()

    def test_modulate_and_sample_with_topp(self, base_logits):
        """Top-p filtering gives valid probabilities."""
        cfg = LogitModulationConfig(enable_retrieval=False, enable_penalty=False)
        mod = LogitModulator(cfg)
        token, probs, meta = mod.modulate_and_sample(
            base_logits, top_p=0.9, temperature=1.0,
        )
        assert torch.allclose(probs.sum(dim=-1), torch.ones(B), atol=1e-5)


# ===========================================================================
# ModulationMode Tests
# ===========================================================================


class TestModulationMode:
    def test_all_modes(self):
        modes = ModulationMode.all_modes()
        assert len(modes) == 4
        assert "baseline" in modes
        assert "retrieval_only" in modes
        assert "penalty_only" in modes
        assert "retrieval_penalty" in modes

    def test_baseline_config(self):
        cfg = ModulationMode.get_config("baseline")
        assert cfg.alpha == 0.0
        assert cfg.beta == 0.0
        assert cfg.enable_retrieval is False
        assert cfg.enable_penalty is False

    def test_retrieval_only_config(self):
        cfg = ModulationMode.get_config("retrieval_only", alpha=2.0)
        assert cfg.alpha == 2.0
        assert cfg.beta == 0.0
        assert cfg.enable_retrieval is True
        assert cfg.enable_penalty is False

    def test_penalty_only_config(self):
        cfg = ModulationMode.get_config("penalty_only", beta=3.0)
        assert cfg.alpha == 0.0
        assert cfg.beta == 3.0
        assert cfg.enable_retrieval is False
        assert cfg.enable_penalty is True

    def test_combined_config(self):
        cfg = ModulationMode.get_config("retrieval_penalty", alpha=1.5, beta=0.5)
        assert cfg.alpha == 1.5
        assert cfg.beta == 0.5
        assert cfg.enable_retrieval is True
        assert cfg.enable_penalty is True

    def test_unknown_mode(self):
        with pytest.raises(ValueError, match="Unknown modulation mode"):
            ModulationMode.get_config("nonexistent")


# ===========================================================================
# RetrievalScorer Tests
# ===========================================================================


class TestRetrievalScorer:
    def test_cosine_shape(self, context_embedding, vocab_embeddings):
        scorer = RetrievalScorer(
            RetrievalScorerConfig(strategy=RetrievalStrategy.COSINE)
        )
        scores = scorer.score(context_embedding, vocab_embeddings)
        assert scores.shape == (B, V)

    def test_dot_product_shape(self, context_embedding, vocab_embeddings):
        scorer = RetrievalScorer(
            RetrievalScorerConfig(
                strategy=RetrievalStrategy.DOT_PRODUCT,
                normalize_scores=False,
            )
        )
        scores = scorer.score(context_embedding, vocab_embeddings)
        assert scores.shape == (B, V)

    def test_external_shape(self):
        external = torch.randn(B, V)
        scorer = RetrievalScorer(
            RetrievalScorerConfig(strategy=RetrievalStrategy.EXTERNAL)
        )
        scores = scorer.score(
            torch.zeros(B, D),  # unused for external
            torch.zeros(V, D),  # unused for external
            external_scores=external,
        )
        assert scores.shape == (B, V)

    def test_external_requires_scores(self):
        scorer = RetrievalScorer(
            RetrievalScorerConfig(strategy=RetrievalStrategy.EXTERNAL)
        )
        with pytest.raises(ValueError, match="external_scores must be provided"):
            scorer.score(torch.zeros(B, D), torch.zeros(V, D))

    def test_cosine_normalized(self, context_embedding, vocab_embeddings):
        """When normalize_scores=True, output should have ~zero mean."""
        scorer = RetrievalScorer(
            RetrievalScorerConfig(
                strategy=RetrievalStrategy.COSINE,
                normalize_scores=True,
            )
        )
        scores = scorer.score(context_embedding, vocab_embeddings)
        # Mean should be approximately 0
        assert abs(scores.mean().item()) < 0.1

    def test_score_from_hidden(self, context_embedding, vocab_embeddings):
        scorer = RetrievalScorer()
        scores = scorer.score_from_hidden(context_embedding, vocab_embeddings)
        assert scores.shape == (B, V)

    def test_score_from_hidden_with_chunks(self, vocab_embeddings):
        torch.manual_seed(50)
        hidden = torch.randn(B, D)
        chunks = torch.randn(B, 3, D)  # 3 retrieved chunks
        scorer = RetrievalScorer()
        scores = scorer.score_from_hidden(hidden, vocab_embeddings, retrieved_chunks=chunks)
        assert scores.shape == (B, V)

    def test_temperature_scaling(self, context_embedding, vocab_embeddings):
        """Temperature != 1.0 should change score magnitudes."""
        scorer_t1 = RetrievalScorer(
            RetrievalScorerConfig(
                strategy=RetrievalStrategy.COSINE,
                normalize_scores=False,
                temperature=1.0,
            )
        )
        scorer_t2 = RetrievalScorer(
            RetrievalScorerConfig(
                strategy=RetrievalStrategy.COSINE,
                normalize_scores=False,
                temperature=2.0,
            )
        )
        s1 = scorer_t1.score(context_embedding, vocab_embeddings)
        s2 = scorer_t2.score(context_embedding, vocab_embeddings)
        # s2 should be half of s1 (within tolerance due to clamping)
        assert torch.allclose(s2, s1 / 2.0, atol=1e-5)


# ===========================================================================
# PenaltyScorer Tests
# ===========================================================================


class TestPenaltyScorer:
    def test_no_penalty_when_disabled(self, base_logits):
        cfg = PenaltyScorerConfig(
            enable_repetition=False,
            enable_blacklist=False,
            enable_safety=False,
            enable_constraint=False,
        )
        scorer = PenaltyScorer(cfg)
        penalties = scorer.score(base_logits)
        assert (penalties == 0).all()

    def test_repetition_penalty_shape(self, base_logits):
        cfg = PenaltyScorerConfig(enable_repetition=True)
        scorer = PenaltyScorer(cfg)
        gen_ids = torch.randint(0, V, (B, 20))
        penalties = scorer.score(base_logits, generated_ids=gen_ids)
        assert penalties.shape == (B, V)

    def test_repetition_penalty_nonzero(self, base_logits):
        """Tokens that appear in generated_ids should get nonzero penalty."""
        cfg = PenaltyScorerConfig(
            enable_repetition=True,
            repetition_penalty_value=5.0,
        )
        scorer = PenaltyScorer(cfg)
        # Generate a sequence with token 10 appearing
        gen_ids = torch.tensor([[10, 20, 10, 30]])
        penalties = scorer.score(
            torch.randn(1, V), generated_ids=gen_ids,
        )
        assert penalties[0, 10].item() > 0
        assert penalties[0, 20].item() > 0
        # Token 0 (never generated) should have 0 penalty
        assert penalties[0, 0].item() == 0

    def test_repetition_decay(self, base_logits):
        """More recent repetitions should have higher penalty."""
        cfg = PenaltyScorerConfig(
            enable_repetition=True,
            repetition_penalty_value=1.0,
            repetition_decay=0.5,  # Strong decay
        )
        scorer = PenaltyScorer(cfg)
        # Token 10 at position 0 (old) and token 20 at position 1 (recent)
        gen_ids = torch.tensor([[10, 20]])
        penalties = scorer.score(
            torch.randn(1, V), generated_ids=gen_ids,
        )
        # Token 20 (more recent) should have higher penalty than token 10
        assert penalties[0, 20].item() > penalties[0, 10].item()

    def test_blacklist_penalty(self, base_logits):
        cfg = PenaltyScorerConfig(
            enable_repetition=False,
            enable_blacklist=True,
            blacklist_token_ids={5, 10, 15},
            blacklist_penalty_value=8.0,
        )
        scorer = PenaltyScorer(cfg)
        penalties = scorer.score(base_logits)
        assert penalties[0, 5].item() == 8.0
        assert penalties[0, 10].item() == 8.0
        assert penalties[0, 15].item() == 8.0
        assert penalties[0, 0].item() == 0.0

    def test_safety_penalty(self, base_logits):
        cfg = PenaltyScorerConfig(
            enable_repetition=False,
            enable_safety=True,
        )
        scorer = PenaltyScorer(cfg)
        safety = torch.rand(B, V) * 3.0
        penalties = scorer.score(base_logits, safety_scores=safety)
        assert torch.allclose(penalties, safety.clamp(min=0.0))

    def test_constraint_penalty(self, base_logits):
        cfg = PenaltyScorerConfig(
            enable_repetition=False,
            enable_constraint=True,
        )
        scorer = PenaltyScorer(cfg)
        constraint = torch.rand(B, V) * 2.0
        penalties = scorer.score(base_logits, constraint_scores=constraint)
        assert torch.allclose(penalties, constraint.clamp(min=0.0))

    def test_combined_penalties(self, base_logits):
        """Multiple penalty sources are summed."""
        cfg = PenaltyScorerConfig(
            enable_repetition=True,
            enable_blacklist=True,
            blacklist_token_ids={5},
            blacklist_penalty_value=10.0,
            enable_safety=True,
        )
        scorer = PenaltyScorer(cfg)
        gen_ids = torch.tensor([[5, 5]])  # Token 5 repeated
        safety = torch.zeros(1, V)
        safety[0, 5] = 2.0

        penalties = scorer.score(
            torch.randn(1, V),
            generated_ids=gen_ids,
            safety_scores=safety,
        )
        # Token 5 gets repetition + blacklist + safety penalties
        assert penalties[0, 5].item() > 10.0  # At least blacklist


# ===========================================================================
# Metric Function Tests
# ===========================================================================


class TestMetrics:
    def test_pass_at_1_perfect(self):
        pred = np.array([1, 2, 3, 4])
        targ = np.array([1, 2, 3, 4])
        assert compute_pass_at_1(pred, targ) == 1.0

    def test_pass_at_1_zero(self):
        pred = np.array([0, 0, 0, 0])
        targ = np.array([1, 2, 3, 4])
        assert compute_pass_at_1(pred, targ) == 0.0

    def test_pass_at_1_half(self):
        pred = np.array([1, 2, 0, 0])
        targ = np.array([1, 2, 3, 4])
        assert compute_pass_at_1(pred, targ) == 0.5

    def test_ece_perfect_calibration(self):
        """Perfectly calibrated: confidence matches accuracy."""
        conf = np.array([0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.1])
        correct = np.array([1, 1, 1, 1, 1, 1, 1, 1, 1, 0])
        ece = compute_ece(conf, correct.astype(float))
        assert ece < 0.15  # Should be low

    def test_ece_empty(self):
        assert compute_ece(np.array([]), np.array([])) == 0.0

    def test_brier_perfect(self):
        conf = np.array([1.0, 0.0])
        correct = np.array([1.0, 0.0])
        assert compute_brier_score(conf, correct) == 0.0

    def test_brier_worst(self):
        conf = np.array([0.0, 1.0])
        correct = np.array([1.0, 0.0])
        assert compute_brier_score(conf, correct) == 1.0

    def test_spearman_perfect(self):
        conf = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        correct = np.array([0.0, 0.0, 0.0, 1.0, 1.0])
        rho = compute_spearman(conf, correct)
        assert rho > 0.7  # Strong positive correlation

    def test_spearman_single(self):
        assert compute_spearman(np.array([1.0]), np.array([1.0])) == 0.0


# ===========================================================================
# Benchmark Tests
# ===========================================================================


class TestLogitModulationBenchmark:
    def test_evaluate_condition(self, base_logits, target_ids):
        benchmark = LogitModulationBenchmark()
        cfg = LogitModulationConfig(enable_retrieval=False, enable_penalty=False)
        metrics = benchmark.evaluate_condition(
            base_logits, target_ids, cfg, condition_name="test",
        )
        assert isinstance(metrics, BenchmarkMetrics)
        assert 0 <= metrics.pass_at_1 <= 1
        assert 0 <= metrics.ece <= 1
        assert 0 <= metrics.brier <= 1
        assert metrics.n_samples == B

    def test_ablation_four_conditions(self, base_logits, target_ids, retrieval_scores, penalty_scores):
        benchmark = LogitModulationBenchmark()
        results = benchmark.run_ablation(
            base_logits, target_ids,
            retrieval_scores=retrieval_scores,
            penalty_scores=penalty_scores,
        )
        assert len(results) == 4
        assert "baseline" in results
        assert "retrieval_only" in results
        assert "penalty_only" in results
        assert "retrieval_penalty" in results

    def test_sweep(self, base_logits, target_ids, retrieval_scores, penalty_scores):
        benchmark = LogitModulationBenchmark()
        sweep = benchmark.run_alpha_beta_sweep(
            base_logits, target_ids,
            retrieval_scores=retrieval_scores,
            penalty_scores=penalty_scores,
            alpha_values=[0.0, 1.0],
            beta_values=[0.0, 1.0],
        )
        assert isinstance(sweep, SweepResult)
        assert len(sweep.results) == 4  # 2x2 grid
        assert sweep.best_by_pass_at_1() is not None

    def test_report_generation(self, base_logits, target_ids, retrieval_scores, penalty_scores):
        benchmark = LogitModulationBenchmark()
        results = benchmark.run_ablation(
            base_logits, target_ids,
            retrieval_scores=retrieval_scores,
            penalty_scores=penalty_scores,
        )
        report = benchmark.generate_report(results)
        assert "LOGIT MODULATION BENCHMARK REPORT" in report
        assert "VERDICT" in report

    def test_sweep_report(self, base_logits, target_ids, retrieval_scores, penalty_scores):
        benchmark = LogitModulationBenchmark()
        sweep = benchmark.run_alpha_beta_sweep(
            base_logits, target_ids,
            retrieval_scores=retrieval_scores,
            penalty_scores=penalty_scores,
            alpha_values=[0.0, 1.0],
            beta_values=[0.0, 1.0],
        )
        report = benchmark.generate_sweep_report(sweep)
        assert "ALPHA/BETA SWEEP RESULTS" in report

    def test_save_results(self, base_logits, target_ids, tmp_path):
        benchmark = LogitModulationBenchmark()
        cfg = LogitModulationConfig(enable_retrieval=False, enable_penalty=False)
        results = {"test": benchmark.evaluate_condition(
            base_logits, target_ids, cfg, condition_name="test",
        )}
        path = str(tmp_path / "results.json")
        benchmark.save_results(results, path)
        import json
        data = json.loads((tmp_path / "results.json").read_text())
        assert "ablation" in data
        assert "test" in data["ablation"]


# ===========================================================================
# End-to-End Integration Tests
# ===========================================================================


class TestEndToEnd:
    def test_full_pipeline(self, vocab_embeddings, context_embedding, target_ids):
        """Full pipeline: retrieval scoring -> penalty scoring -> modulation -> benchmark."""
        torch.manual_seed(99)

        # Step 1: Get base logits
        base_logits = context_embedding @ vocab_embeddings.T  # [B, V]

        # Step 2: Compute retrieval scores
        ret_scorer = RetrievalScorer(
            RetrievalScorerConfig(strategy=RetrievalStrategy.COSINE)
        )
        ret_scores = ret_scorer.score(context_embedding, vocab_embeddings)
        assert ret_scores.shape == base_logits.shape

        # Step 3: Compute penalty scores
        pen_cfg = PenaltyScorerConfig(
            enable_repetition=True,
            enable_blacklist=True,
            blacklist_token_ids={0, 1},
            blacklist_penalty_value=5.0,
        )
        pen_scorer = PenaltyScorer(pen_cfg)
        gen_ids = torch.randint(0, V, (B, 10))
        pen_scores = pen_scorer.score(base_logits, generated_ids=gen_ids)
        assert pen_scores.shape == base_logits.shape

        # Step 4: Modulate
        mod_cfg = LogitModulationConfig(alpha=0.5, beta=0.3)
        mod = LogitModulator(mod_cfg)
        modified = mod.modulate(base_logits, ret_scores, pen_scores)
        assert modified.shape == base_logits.shape
        assert modified.max() <= 50.0
        assert modified.min() >= -50.0

        # Step 5: Benchmark
        benchmark = LogitModulationBenchmark()
        results = benchmark.run_ablation(
            base_logits, target_ids,
            retrieval_scores=ret_scores,
            penalty_scores=pen_scores,
            alpha=0.5, beta=0.3,
        )
        assert len(results) == 4

        # Step 6: Verify report
        report = benchmark.generate_report(results)
        assert len(report) > 0

    def test_zero_alpha_beta_matches_baseline(self, base_logits, retrieval_scores, penalty_scores):
        """α=0, β=0 should produce identical results to baseline softmax."""
        mod = LogitModulator(LogitModulationConfig(alpha=0.0, beta=0.0))
        modified = mod.modulate(base_logits, retrieval_scores, penalty_scores)
        expected = torch.clamp(base_logits, min=-50, max=50)
        assert torch.allclose(modified, expected)

    def test_numeric_stability_extreme_logits(self):
        """Extreme input logits are safely clamped."""
        extreme = torch.tensor([[1e6, -1e6, 0.0, 1e4, -1e4]])
        mod = LogitModulator(LogitModulationConfig())
        result = mod.modulate(extreme)
        assert not torch.isnan(result).any()
        assert not torch.isinf(result).any()
        assert result.max() <= 50.0
        assert result.min() >= -50.0

    def test_softmax_after_modulation_valid(self, base_logits, retrieval_scores, penalty_scores):
        """Softmax on modified logits produces valid distribution."""
        mod = LogitModulator(LogitModulationConfig(alpha=1.0, beta=1.0))
        modified = mod.modulate(base_logits, retrieval_scores, penalty_scores)
        probs = F.softmax(modified, dim=-1)
        assert torch.allclose(probs.sum(dim=-1), torch.ones(B), atol=1e-5)
        assert (probs >= 0).all()
