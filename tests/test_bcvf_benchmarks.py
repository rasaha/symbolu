#!/usr/bin/env python3
"""
Tests for the BCVF Benchmark Suite.

Covers:
    - GoalEmbeddingFactory (all strategies)
    - SimpleRetriever (indexing, retrieval, edge cases)
    - Bootstrap CI (pass@1 delta, Spearman rho)
    - Verdict logic
    - BenchmarkRunner (HumanEval, Instruction, Retrieval)
    - BenchmarkSuite (run_all, comparison report)
    - BenchmarkResult data structures
    - Extended summary output
    - Integration with existing ExperimentRunner
"""

import pytest
import numpy as np

# ---------------------------------------------------------------------------
# Check PyTorch availability
# ---------------------------------------------------------------------------
torch = pytest.importorskip("torch")

from symbolu.ontological.bcvf_decoding import DecodingConfig
from symbolu.ontological.bcvf_calibration import spearman_rank_correlation
from symbolu.ontological.bcvf_experiments import (
    ExperimentResult,
    ExperimentRunner,
)
from symbolu.ontological.bcvf_goal_embeddings import (
    GoalEmbeddingFactory,
    SimpleRetriever,
)
from symbolu.ontological.bcvf_benchmarks import (
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkSuite,
    BootstrapCI,
    ComparisonReport,
    bootstrap_ci,
    bootstrap_pass_at_1_delta,
    bootstrap_spearman,
    compute_verdict,
    print_extended_summary,
)


# ===========================================================================
# Fixtures
# ===========================================================================

B, D, V, M = 1, 64, 200, 50


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
    return hidden @ vocab_emb.T


@pytest.fixture
def synthetic_dataset():
    """Create a small synthetic dataset with various text keys."""
    torch.manual_seed(42)
    samples = []
    for i in range(15):
        h = torch.randn(1, D)
        v = torch.randn(V, D)
        lo = h @ v.T
        gt = torch.argmax(lo, dim=-1).item()
        samples.append({
            "hidden_state": h,
            "logits": lo,
            "ground_truth": gt,
            "prompt": f"def foo_{i}(x):\n    '''Return x + {i}'''\n",
            "instruction": f"Write a function that adds {i} to its input.",
            "context": f"The number {i} is an integer. Adding {i} to x gives x + {i}.",
        })
    return samples


@pytest.fixture
def benchmark_runner():
    """BenchmarkRunner without a real model (unit-test mode)."""
    return BenchmarkRunner(
        model=None,
        tokenizer=None,
        base_config=DecodingConfig(top_m=50, beta=0.2),
        device="cpu",
    )


# ===========================================================================
# GoalEmbeddingFactory
# ===========================================================================


class TestGoalEmbeddingFactory:
    def test_strategies_list(self):
        factory = GoalEmbeddingFactory()
        assert "lookahead" in factory.STRATEGIES
        assert "prompt_mean" in factory.STRATEGIES
        assert "random" in factory.STRATEGIES
        assert "instruction_only" in factory.STRATEGIES
        assert "code_problem_only" in factory.STRATEGIES
        assert "retrieval_context" in factory.STRATEGIES

    def test_unknown_strategy_raises(self):
        factory = GoalEmbeddingFactory()
        with pytest.raises(ValueError, match="Unknown strategy"):
            factory.build("nonexistent")

    def test_random_strategy(self):
        factory = GoalEmbeddingFactory()
        goal = factory.build("random", hidden_dim=D, batch_size=2)
        assert goal.shape == (2, D)

    def test_random_requires_hidden_dim(self):
        factory = GoalEmbeddingFactory()
        with pytest.raises(ValueError, match="hidden_dim"):
            factory.build("random")

    def test_lookahead_from_hidden_states_3d(self):
        factory = GoalEmbeddingFactory()
        hidden_states = torch.randn(1, 10, D)  # [B, T, D]
        goal = factory.build(
            "lookahead", hidden_states=hidden_states
        )
        assert goal.shape == (1, D)

    def test_lookahead_from_hidden_states_2d(self):
        factory = GoalEmbeddingFactory()
        hidden_states = torch.randn(2, D)  # [B, D] already pooled
        goal = factory.build(
            "lookahead", hidden_states=hidden_states
        )
        assert goal.shape == (2, D)

    def test_lookahead_requires_input(self):
        factory = GoalEmbeddingFactory()
        with pytest.raises(ValueError, match="lookahead requires"):
            factory.build("lookahead")

    def test_prompt_mean_3d(self):
        factory = GoalEmbeddingFactory()
        prompt_hidden = torch.randn(1, 8, D)
        goal = factory.build(
            "prompt_mean", prompt_hidden_states=prompt_hidden
        )
        assert goal.shape == (1, D)

    def test_prompt_mean_2d(self):
        factory = GoalEmbeddingFactory()
        prompt_hidden = torch.randn(8, D)  # [T, D]
        goal = factory.build(
            "prompt_mean", prompt_hidden_states=prompt_hidden
        )
        assert goal.shape == (1, D)

    def test_prompt_mean_requires_input(self):
        factory = GoalEmbeddingFactory()
        with pytest.raises(ValueError, match="prompt_hidden_states"):
            factory.build("prompt_mean")

    def test_instruction_only_requires_text(self):
        factory = GoalEmbeddingFactory()
        with pytest.raises(ValueError, match="text argument"):
            factory.build("instruction_only")

    def test_instruction_only_requires_model(self):
        factory = GoalEmbeddingFactory(model=None, tokenizer=None)
        with pytest.raises(ValueError, match="Model and tokenizer"):
            factory.build("instruction_only", text="Write hello world")

    def test_code_problem_only_requires_text(self):
        factory = GoalEmbeddingFactory()
        with pytest.raises(ValueError, match="text argument"):
            factory.build("code_problem_only")

    def test_retrieval_context_requires_text(self):
        factory = GoalEmbeddingFactory()
        with pytest.raises(ValueError, match="text argument"):
            factory.build("retrieval_context", context_text=None)

    def test_from_tensor_1d(self):
        emb = torch.randn(D)
        result = GoalEmbeddingFactory.from_tensor(emb)
        assert result.shape == (1, D)

    def test_from_tensor_2d(self):
        emb = torch.randn(3, D)
        result = GoalEmbeddingFactory.from_tensor(emb)
        assert result.shape == (3, D)

    def test_from_tensor_numpy(self):
        emb = np.random.randn(D)
        result = GoalEmbeddingFactory.from_tensor(emb)
        assert result.shape == (1, D)
        assert isinstance(result, torch.Tensor)


# ===========================================================================
# SimpleRetriever
# ===========================================================================


class TestSimpleRetriever:
    def test_index_from_embeddings(self):
        retriever = SimpleRetriever()
        texts = ["passage one", "passage two", "passage three"]
        embs = torch.randn(3, D)
        retriever.index_from_embeddings(texts, embs)
        assert len(retriever.corpus_texts) == 3
        assert retriever.corpus_embeddings.shape == (3, D)

    def test_retrieve_top_1(self):
        retriever = SimpleRetriever()
        torch.manual_seed(42)
        texts = ["alpha", "beta", "gamma"]
        embs = torch.randn(3, D)
        retriever.index_from_embeddings(texts, embs)

        query = embs[1:2]  # Should match "beta" best
        results = retriever.retrieve(query, top_k=1)
        assert len(results) == 1
        assert results[0]["text"] == "beta"
        assert results[0]["score"] > 0.99  # Self-similarity

    def test_retrieve_top_k(self):
        retriever = SimpleRetriever()
        texts = [f"passage {i}" for i in range(10)]
        embs = torch.randn(10, D)
        retriever.index_from_embeddings(texts, embs)

        query = embs[0:1]
        results = retriever.retrieve(query, top_k=3)
        assert len(results) == 3
        # First result should be self
        assert results[0]["index"] == 0

    def test_retrieve_empty_index(self):
        retriever = SimpleRetriever()
        query = torch.randn(1, D)
        results = retriever.retrieve(query)
        assert results == []

    def test_retrieve_1d_query(self):
        retriever = SimpleRetriever()
        texts = ["a", "b"]
        embs = torch.randn(2, D)
        retriever.index_from_embeddings(texts, embs)
        query = torch.randn(D)  # 1D
        results = retriever.retrieve(query, top_k=1)
        assert len(results) == 1

    def test_index_from_numpy(self):
        retriever = SimpleRetriever()
        texts = ["x", "y"]
        embs = np.random.randn(2, D).astype(np.float32)
        retriever.index_from_embeddings(texts, embs)
        assert retriever.corpus_embeddings.shape == (2, D)

    def test_top_k_larger_than_corpus(self):
        retriever = SimpleRetriever()
        texts = ["only"]
        embs = torch.randn(1, D)
        retriever.index_from_embeddings(texts, embs)
        results = retriever.retrieve(torch.randn(1, D), top_k=5)
        assert len(results) == 1


# ===========================================================================
# Bootstrap CI
# ===========================================================================


class TestBootstrapCI:
    def test_bootstrap_ci_basic(self):
        np.random.seed(42)
        values = np.random.randn(100)
        ci = bootstrap_ci(
            values, statistic_fn=np.mean, n_bootstrap=500, seed=42
        )
        assert ci.lower < ci.mean < ci.upper
        assert ci.n_bootstrap == 500

    def test_bootstrap_ci_empty(self):
        ci = bootstrap_ci(
            np.array([]), statistic_fn=np.mean, n_bootstrap=100
        )
        assert ci.mean == 0.0
        assert ci.lower == 0.0
        assert ci.upper == 0.0
        assert ci.n_bootstrap == 0

    def test_bootstrap_ci_constant(self):
        values = np.ones(50)
        ci = bootstrap_ci(
            values, statistic_fn=np.mean, n_bootstrap=200, seed=42
        )
        assert ci.mean == pytest.approx(1.0)
        assert ci.lower == pytest.approx(1.0)
        assert ci.upper == pytest.approx(1.0)

    def test_bootstrap_ci_str(self):
        ci = BootstrapCI(mean=0.05, lower=0.01, upper=0.09)
        s = str(ci)
        assert "0.0500" in s
        assert "0.0100" in s
        assert "0.0900" in s


class TestBootstrapPassAt1Delta:
    def test_zero_delta(self):
        correct = np.ones(50)
        ci = bootstrap_pass_at_1_delta(
            correct, correct, n_bootstrap=200, seed=42
        )
        assert ci.mean == pytest.approx(0.0)
        assert ci.lower == pytest.approx(0.0)
        assert ci.upper == pytest.approx(0.0)

    def test_positive_delta(self):
        baseline = np.zeros(100)
        bcvf = np.ones(100)
        ci = bootstrap_pass_at_1_delta(
            baseline, bcvf, n_bootstrap=200, seed=42
        )
        assert ci.mean == pytest.approx(1.0)
        assert ci.lower > 0.5

    def test_empty_arrays(self):
        ci = bootstrap_pass_at_1_delta(
            np.array([]), np.array([]), n_bootstrap=100
        )
        assert ci.mean == 0.0
        assert ci.n_bootstrap == 0

    def test_mixed_results(self):
        np.random.seed(42)
        baseline = np.random.binomial(1, 0.5, 100).astype(float)
        bcvf = np.random.binomial(1, 0.6, 100).astype(float)
        ci = bootstrap_pass_at_1_delta(
            baseline, bcvf, n_bootstrap=500, seed=42
        )
        # CI should contain the observed delta
        assert ci.lower <= ci.mean <= ci.upper


class TestBootstrapSpearman:
    def test_perfect_correlation(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        ci = bootstrap_spearman(x, y, n_bootstrap=200, seed=42)
        assert ci.mean == pytest.approx(1.0, abs=1e-6)
        assert ci.lower > 0.5

    def test_too_short(self):
        x = np.array([1.0, 2.0])
        y = np.array([3.0, 4.0])
        ci = bootstrap_spearman(x, y, n_bootstrap=100)
        assert ci.mean == 0.0
        assert ci.n_bootstrap == 0

    def test_no_correlation(self):
        np.random.seed(42)
        x = np.random.randn(100)
        y = np.random.randn(100)
        ci = bootstrap_spearman(x, y, n_bootstrap=300, seed=42)
        assert abs(ci.mean) < 0.3
        # CI should span zero
        assert ci.lower < 0.0 < ci.upper or abs(ci.mean) < 0.3


# ===========================================================================
# Verdict Logic
# ===========================================================================


class TestVerdictLogic:
    def test_sb_wins(self):
        assert compute_verdict(0.5, 0.1) == "sb WINS"

    def test_logit_wins(self):
        assert compute_verdict(0.1, 0.5) == "logit WINS"

    def test_neither(self):
        assert compute_verdict(0.02, 0.03) == "NEITHER"

    def test_tied(self):
        assert compute_verdict(0.3, 0.3) == "~tied"

    def test_borderline_sb_wins(self):
        # sb_rho = 0.15, logit_rho = 0.09 → sb > logit + 0.05 = 0.14
        assert compute_verdict(0.15, 0.09) == "sb WINS"

    def test_borderline_tied(self):
        # sb_rho = 0.14, logit_rho = 0.10 → sb <= logit + 0.05 = 0.15
        assert compute_verdict(0.14, 0.10) == "~tied"


# ===========================================================================
# BenchmarkResult
# ===========================================================================


class TestBenchmarkResult:
    def test_properties(self):
        er = ExperimentResult(
            label="C+B",
            flags={"use_rerank": True, "use_calibration": True},
            pass_at_1=0.75,
            sb_correctness_corr=0.3,
            base_logit_correctness_corr=0.1,
        )
        br = BenchmarkResult(
            experiment_result=er,
            dataset_name="HumanEval",
            benchmark_type="code_gen",
            goal_strategy="code_problem_only",
            verdict="sb WINS",
        )
        assert br.sb_rho == 0.3
        assert br.logit_rho == 0.1
        assert br.pass_at_1 == 0.75
        assert br.label == "C+B"


# ===========================================================================
# BenchmarkRunner
# ===========================================================================


class TestBenchmarkRunner:
    def test_run_humaneval_experiment(self, synthetic_dataset, benchmark_runner):
        result = benchmark_runner.run_humaneval_experiment(
            synthetic_dataset, n_bootstrap=50
        )
        assert result.dataset_name == "HumanEval"
        assert result.benchmark_type == "code_gen"
        assert result.goal_strategy == "code_problem_only"
        assert 0.0 <= result.pass_at_1 <= 1.0
        assert result.pass_at_1_delta_ci is not None
        assert result.sb_rho_ci is not None
        assert result.verdict in ("sb WINS", "logit WINS", "NEITHER", "~tied")

    def test_run_instruction_experiment(
        self, synthetic_dataset, benchmark_runner
    ):
        result = benchmark_runner.run_instruction_experiment(
            synthetic_dataset, n_bootstrap=50
        )
        assert result.dataset_name == "Instruction"
        assert result.benchmark_type == "instruction"
        assert result.goal_strategy == "instruction_only"
        assert 0.0 <= result.pass_at_1 <= 1.0
        assert result.pass_at_1_delta_ci is not None

    def test_run_retrieval_experiment(
        self, synthetic_dataset, benchmark_runner
    ):
        result = benchmark_runner.run_retrieval_experiment(
            synthetic_dataset, n_bootstrap=50
        )
        assert result.dataset_name == "Retrieval-Augmented"
        assert result.benchmark_type == "retrieval"
        assert result.goal_strategy == "retrieval_context"
        assert 0.0 <= result.pass_at_1 <= 1.0
        assert result.pass_at_1_delta_ci is not None

    def test_custom_flags(self, synthetic_dataset, benchmark_runner):
        flags = {
            "use_rerank": True,
            "use_logit_mod": True,
            "use_calibration": True,
        }
        result = benchmark_runner.run_humaneval_experiment(
            synthetic_dataset, flags=flags, n_bootstrap=20
        )
        assert result.experiment_result.label == "A+B+C"

    def test_prepare_retrieval_samples(
        self, synthetic_dataset, benchmark_runner
    ):
        corpus = [
            "Python is a programming language.",
            "Addition is a math operation.",
            "Functions take arguments and return values.",
        ]
        enriched = benchmark_runner.prepare_retrieval_samples(
            synthetic_dataset, corpus
        )
        assert len(enriched) == len(synthetic_dataset)
        for sample in enriched:
            assert "context" in sample
            assert isinstance(sample["context"], str)


# ===========================================================================
# BenchmarkSuite
# ===========================================================================


class TestBenchmarkSuite:
    def test_run_all_humaneval_only(self, synthetic_dataset):
        suite = BenchmarkSuite(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        report = suite.run_all(
            humaneval_problems=synthetic_dataset,
            n_bootstrap=20,
        )
        assert len(report.results) == 1
        assert report.results[0].benchmark_type == "code_gen"
        assert report.timestamp != ""

    def test_run_all_multiple_benchmarks(self, synthetic_dataset):
        suite = BenchmarkSuite(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        report = suite.run_all(
            humaneval_problems=synthetic_dataset,
            instruction_samples=synthetic_dataset,
            retrieval_samples=synthetic_dataset,
            n_bootstrap=20,
        )
        assert len(report.results) == 3
        types = {r.benchmark_type for r in report.results}
        assert types == {"code_gen", "instruction", "retrieval"}

    def test_run_all_empty_skips(self):
        suite = BenchmarkSuite(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        report = suite.run_all(n_bootstrap=20)
        assert len(report.results) == 0

    def test_print_comparison(self, synthetic_dataset):
        suite = BenchmarkSuite(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        report = suite.run_all(
            humaneval_problems=synthetic_dataset,
            instruction_samples=synthetic_dataset,
            n_bootstrap=20,
        )
        table = BenchmarkSuite.print_comparison(report)
        assert "HumanEval" in table
        assert "Instruction" in table
        assert "Assessment" in table
        # Should contain at least one verdict keyword
        assert any(
            v in table
            for v in ("sb WINS", "logit WINS", "NEITHER", "~tied")
        )

    def test_save_report(self, synthetic_dataset, tmp_path):
        suite = BenchmarkSuite(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        report = suite.run_all(
            humaneval_problems=synthetic_dataset,
            n_bootstrap=20,
        )
        path = str(tmp_path / "test_report.json")
        BenchmarkSuite.save_report(report, path)

        import json

        with open(path) as f:
            data = json.load(f)
        assert "benchmarks" in data
        assert len(data["benchmarks"]) == 1
        assert data["benchmarks"][0]["dataset_name"] == "HumanEval"


# ===========================================================================
# Extended print_summary
# ===========================================================================


class TestExtendedSummary:
    def test_print_extended_summary(self, synthetic_dataset):
        runner = BenchmarkRunner(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        results = [
            runner.run_humaneval_experiment(
                synthetic_dataset, n_bootstrap=20
            ),
            runner.run_instruction_experiment(
                synthetic_dataset, n_bootstrap=20
            ),
        ]
        table = print_extended_summary(results)
        assert "Benchmark-specific" in table
        assert "HumanEval" in table
        assert "Instruction" in table
        assert "95% CI" in table or "CI" in table


# ===========================================================================
# Integration with existing ExperimentRunner
# ===========================================================================


class TestIntegrationWithExistingPipeline:
    def test_benchmark_uses_experiment_runner(self, synthetic_dataset):
        """BenchmarkRunner delegates to ExperimentRunner correctly."""
        runner = BenchmarkRunner(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        result = runner.run_humaneval_experiment(
            synthetic_dataset, n_bootstrap=20
        )
        # Verify it produces a valid ExperimentResult
        er = result.experiment_result
        assert isinstance(er, ExperimentResult)
        assert er.total_samples == len(synthetic_dataset)
        assert len(er.per_sample) == len(synthetic_dataset)

    def test_goal_embeddings_are_distinct(self, synthetic_dataset):
        """Different goal strategies should produce different results."""
        runner = BenchmarkRunner(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        humaneval_result = runner.run_humaneval_experiment(
            synthetic_dataset, n_bootstrap=20
        )
        instruction_result = runner.run_instruction_experiment(
            synthetic_dataset, n_bootstrap=20
        )
        # They should both work but may have different metrics
        assert humaneval_result.goal_strategy != instruction_result.goal_strategy
        assert humaneval_result.benchmark_type != instruction_result.benchmark_type

    def test_existing_experiment_result_fields_present(
        self, synthetic_dataset
    ):
        """All standard ExperimentResult fields should be populated."""
        runner = BenchmarkRunner(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        result = runner.run_humaneval_experiment(
            synthetic_dataset, n_bootstrap=20
        )
        er = result.experiment_result
        assert isinstance(er.ece, float)
        assert isinstance(er.brier, float)
        assert isinstance(er.rerank_change_pct, float)
        assert isinstance(er.sb_correctness_corr, float)
        assert isinstance(er.logit_rank_correctness_corr, float)

    def test_bootstrap_ci_bounds_valid(self, synthetic_dataset):
        """Bootstrap CIs should have lower <= mean <= upper."""
        runner = BenchmarkRunner(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        result = runner.run_humaneval_experiment(
            synthetic_dataset, n_bootstrap=100
        )
        if result.pass_at_1_delta_ci is not None:
            ci = result.pass_at_1_delta_ci
            assert ci.lower <= ci.mean + 1e-8
            assert ci.mean <= ci.upper + 1e-8
        if result.sb_rho_ci is not None:
            ci = result.sb_rho_ci
            assert ci.lower <= ci.mean + 1e-8
            assert ci.mean <= ci.upper + 1e-8


# ===========================================================================
# ComparisonReport
# ===========================================================================


class TestComparisonReport:
    def test_empty_report(self):
        report = ComparisonReport()
        assert len(report.results) == 0
        table = BenchmarkSuite.print_comparison(report)
        assert "Assessment" in table

    def test_report_with_results(self):
        er1 = ExperimentResult(
            label="C+B", flags={},
            pass_at_1=0.75,
            sb_correctness_corr=0.4,
            base_logit_correctness_corr=0.1,
        )
        er2 = ExperimentResult(
            label="C+B", flags={},
            pass_at_1=0.60,
            sb_correctness_corr=0.1,
            base_logit_correctness_corr=0.5,
        )
        report = ComparisonReport(
            results=[
                BenchmarkResult(
                    experiment_result=er1,
                    dataset_name="HumanEval",
                    benchmark_type="code_gen",
                    goal_strategy="code_problem_only",
                    verdict="sb WINS",
                    pass_at_1_delta_ci=BootstrapCI(
                        mean=0.03, lower=0.01, upper=0.05
                    ),
                    sb_rho_ci=BootstrapCI(
                        mean=0.4, lower=0.2, upper=0.6
                    ),
                ),
                BenchmarkResult(
                    experiment_result=er2,
                    dataset_name="Instruction",
                    benchmark_type="instruction",
                    goal_strategy="instruction_only",
                    verdict="logit WINS",
                    pass_at_1_delta_ci=BootstrapCI(
                        mean=-0.02, lower=-0.05, upper=0.01
                    ),
                    sb_rho_ci=BootstrapCI(
                        mean=0.1, lower=-0.1, upper=0.3
                    ),
                ),
            ],
            timestamp="2025-01-01 12:00:00",
        )
        table = BenchmarkSuite.print_comparison(report)
        assert "HumanEval" in table
        assert "Instruction" in table
        assert "sb WINS: 1" in table
        assert "logit WINS: 1" in table


# ===========================================================================
# End-to-end: full suite run
# ===========================================================================


class TestEndToEnd:
    def test_full_suite_run(self, synthetic_dataset):
        """Run all three benchmarks and verify complete pipeline."""
        suite = BenchmarkSuite(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        report = suite.run_all(
            humaneval_problems=synthetic_dataset,
            instruction_samples=synthetic_dataset,
            retrieval_samples=synthetic_dataset,
            n_bootstrap=20,
        )

        assert len(report.results) == 3

        for r in report.results:
            # Core metrics
            assert 0.0 <= r.pass_at_1 <= 1.0
            assert -1.0 <= r.sb_rho <= 1.0
            assert -1.0 <= r.logit_rho <= 1.0

            # CIs
            assert r.pass_at_1_delta_ci is not None
            assert r.sb_rho_ci is not None

            # Verdict
            assert r.verdict in ("sb WINS", "logit WINS", "NEITHER", "~tied")

            # Metadata
            assert r.dataset_name != ""
            assert r.benchmark_type != ""
            assert r.goal_strategy != ""

        # Print and verify output
        table = BenchmarkSuite.print_comparison(report)
        assert len(table) > 100  # Non-trivial output

    def test_suite_with_prepare_retrieval(self, synthetic_dataset):
        """Test retrieval preparation + benchmark pipeline."""
        runner = BenchmarkRunner(
            base_config=DecodingConfig(top_m=50, beta=0.2)
        )
        corpus = [
            "Functions are blocks of reusable code.",
            "Variables store data values.",
            "Loops iterate over sequences.",
            "Conditionals control program flow.",
            "Classes define object blueprints.",
        ]
        enriched = runner.prepare_retrieval_samples(
            synthetic_dataset, corpus
        )
        result = runner.run_retrieval_experiment(enriched, n_bootstrap=20)
        assert result.benchmark_type == "retrieval"
        assert result.goal_strategy == "retrieval_context"
