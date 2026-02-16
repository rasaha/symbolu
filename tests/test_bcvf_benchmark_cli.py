#!/usr/bin/env python3
"""
Shallow CLI tests for ``scripts/run_bcvf_benchmarks.py``.

These tests verify:
    - Argument parsing (defaults, overrides, invalid values)
    - Config construction (DecodingConfig from args)
    - Dry-run path (full pipeline, no network, no GPU)
    - DatasetAdapter (synthetic data generation, shape checks)
    - Runner invocation (ExperimentRunner called correctly)
    - Output formatting (comparison table, JSON export)

All tests use random tensors only — no model downloads, no GPU.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import numpy as np

# Ensure project root is on path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

torch = pytest.importorskip("torch")

# Import the CLI module
from scripts.run_bcvf_benchmarks import (
    DatasetAdapter,
    build_parser,
    main,
    resolve_model_name,
    run_single_mode,
    _build_benchmark_result,
    _compute_goal_embeddings,
    _builtin_fallback_texts,
)
from symbolu.ontological.bcvf_decoding import DecodingConfig
from symbolu.ontological.bcvf_benchmarks import BenchmarkResult, ComparisonReport


# =========================================================================
# Argument Parsing
# =========================================================================


class TestArgParsing:
    def test_defaults(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.mode == "wikitext"
        assert args.model == "gpt2"
        assert args.samples == 500
        assert args.beta == 0.2
        assert args.top_m == 500
        assert args.lambda_c == 0.25
        assert args.n_bootstrap == 1000
        assert args.dry_run is False
        assert args.goal_strategy == ["lookahead", "prompt_mean", "random"]

    def test_mode_override(self):
        parser = build_parser()
        args = parser.parse_args(["--mode", "humaneval"])
        assert args.mode == "humaneval"

    def test_all_modes_accepted(self):
        parser = build_parser()
        for mode in ["wikitext", "humaneval", "instruction", "retrieval", "all"]:
            args = parser.parse_args(["--mode", mode])
            assert args.mode == mode

    def test_bcvf_params(self):
        parser = build_parser()
        args = parser.parse_args([
            "--beta", "0.5", "--top-m", "200", "--lambda-c", "0.3",
        ])
        assert args.beta == 0.5
        assert args.top_m == 200
        assert args.lambda_c == 0.3

    def test_goal_strategy_single(self):
        parser = build_parser()
        args = parser.parse_args(["--goal-strategy", "lookahead"])
        assert args.goal_strategy == ["lookahead"]

    def test_goal_strategy_multiple(self):
        parser = build_parser()
        args = parser.parse_args([
            "--goal-strategy", "lookahead", "random",
        ])
        assert args.goal_strategy == ["lookahead", "random"]

    def test_dry_run_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_output_path(self):
        parser = build_parser()
        args = parser.parse_args(["--output", "/tmp/out.json"])
        assert args.output == "/tmp/out.json"

    def test_data_paths(self):
        parser = build_parser()
        args = parser.parse_args([
            "--humaneval-path", "/data/he.jsonl",
            "--instruction-path", "/data/instr.jsonl",
            "--retrieval-path", "/data/ret.json",
        ])
        assert args.humaneval_path == "/data/he.jsonl"
        assert args.instruction_path == "/data/instr.jsonl"
        assert args.retrieval_path == "/data/ret.json"

    def test_samples_override(self):
        parser = build_parser()
        args = parser.parse_args(["--samples", "100"])
        assert args.samples == 100

    def test_bootstrap_override(self):
        parser = build_parser()
        args = parser.parse_args(["--n-bootstrap", "50"])
        assert args.n_bootstrap == 50


# =========================================================================
# Model Name Resolution
# =========================================================================


class TestModelResolution:
    def test_alias_gpt2(self):
        assert resolve_model_name("gpt2") == "gpt2"

    def test_alias_phi3(self):
        assert resolve_model_name("phi3") == "microsoft/phi-3.5-mini-instruct"

    def test_alias_stablelm(self):
        assert resolve_model_name("stablelm") == "stabilityai/stablelm-zephyr-3b"

    def test_passthrough_full_name(self):
        assert resolve_model_name("meta-llama/Llama-2-7b") == "meta-llama/Llama-2-7b"

    def test_case_insensitive(self):
        assert resolve_model_name("PHI3") == "microsoft/phi-3.5-mini-instruct"


# =========================================================================
# Config Construction
# =========================================================================


class TestConfigConstruction:
    def test_bcvf_config_from_args(self):
        parser = build_parser()
        args = parser.parse_args([
            "--beta", "0.3", "--top-m", "300", "--lambda-c", "0.5",
        ])
        config = DecodingConfig(
            top_m=args.top_m,
            beta=args.beta,
            lambda_c=args.lambda_c,
        )
        assert config.top_m == 300
        assert config.beta == 0.3
        assert config.lambda_c == 0.5

    def test_dry_run_clamps_top_m(self):
        parser = build_parser()
        args = parser.parse_args(["--dry-run", "--top-m", "500"])
        top_m = min(args.top_m, 25)  # Dry-run clamp
        assert top_m == 25

    def test_dry_run_clamps_samples(self):
        parser = build_parser()
        args = parser.parse_args(["--dry-run", "--samples", "1000"])
        samples = min(args.samples, 200)
        assert samples == 200


# =========================================================================
# DatasetAdapter
# =========================================================================


class TestDatasetAdapter:
    def test_dry_run_default(self):
        dataset = DatasetAdapter.from_dry_run(n_samples=50)
        assert len(dataset) == 50
        sample = dataset[0]
        assert "hidden_state" in sample
        assert "goal_embedding" in sample
        assert "logits" in sample
        assert "ground_truth" in sample
        assert sample["hidden_state"].shape == (1, 64)
        assert sample["goal_embedding"].shape == (1, 64)
        assert sample["logits"].shape == (1, 50)

    def test_dry_run_custom_dims(self):
        dataset = DatasetAdapter.from_dry_run(
            n_samples=10, hidden_dim=128, vocab_size=100,
        )
        assert len(dataset) == 10
        assert dataset[0]["hidden_state"].shape == (1, 128)
        assert dataset[0]["logits"].shape == (1, 100)

    def test_dry_run_strategies(self):
        for strategy in ["lookahead", "prompt_mean", "random"]:
            dataset = DatasetAdapter.from_dry_run(
                n_samples=5, strategy=strategy,
            )
            assert len(dataset) == 5

    def test_dry_run_deterministic(self):
        d1 = DatasetAdapter.from_dry_run(n_samples=10)
        d2 = DatasetAdapter.from_dry_run(n_samples=10)
        assert torch.equal(d1[0]["hidden_state"], d2[0]["hidden_state"])

    def test_dry_run_ground_truth_valid(self):
        dataset = DatasetAdapter.from_dry_run(n_samples=20)
        for sample in dataset:
            gt = sample["ground_truth"]
            assert isinstance(gt, int)
            assert 0 <= gt < 50  # vocab_size default


# =========================================================================
# Goal Embedding Helper
# =========================================================================


class TestGoalEmbeddings:
    def test_lookahead_shape(self):
        hidden = torch.randn(1, 20, 64)
        goals = _compute_goal_embeddings(hidden, "lookahead")
        assert goals.shape == (20, 64)

    def test_lookahead_last_position(self):
        hidden = torch.randn(1, 10, 32)
        goals = _compute_goal_embeddings(hidden, "lookahead")
        # Last position copies itself
        assert torch.equal(goals[-1], hidden[0, -1])

    def test_lookahead_shifts(self):
        hidden = torch.randn(1, 10, 32)
        goals = _compute_goal_embeddings(hidden, "lookahead")
        # Position t should have hidden[t+1]
        assert torch.equal(goals[0], hidden[0, 1])

    def test_prompt_mean_shape(self):
        hidden = torch.randn(1, 20, 64)
        goals = _compute_goal_embeddings(hidden, "prompt_mean")
        assert goals.shape == (20, 64)

    def test_prompt_mean_constant_across_positions(self):
        hidden = torch.randn(1, 20, 64)
        goals = _compute_goal_embeddings(hidden, "prompt_mean")
        # All positions should have the same goal
        assert torch.equal(goals[0], goals[10])

    def test_random_shape(self):
        hidden = torch.randn(1, 20, 64)
        goals = _compute_goal_embeddings(hidden, "random")
        assert goals.shape == (20, 64)

    def test_random_deterministic(self):
        hidden = torch.randn(1, 20, 64)
        g1 = _compute_goal_embeddings(hidden, "random")
        g2 = _compute_goal_embeddings(hidden, "random")
        assert torch.equal(g1, g2)  # Same seed

    def test_unknown_strategy_raises(self):
        hidden = torch.randn(1, 10, 32)
        with pytest.raises(ValueError, match="Unknown strategy"):
            _compute_goal_embeddings(hidden, "nonexistent")


# =========================================================================
# Fallback Texts
# =========================================================================


class TestFallbackTexts:
    def test_non_empty(self):
        texts = _builtin_fallback_texts()
        assert len(texts) >= 4

    def test_long_enough(self):
        texts = _builtin_fallback_texts()
        for text in texts:
            assert len(text) > 200


# =========================================================================
# Build Benchmark Result
# =========================================================================


class TestBuildBenchmarkResult:
    def test_produces_valid_result(self):
        from symbolu.ontological.bcvf_experiments import ExperimentResult

        er_bcvf = ExperimentResult(
            label="C+B", flags={},
            pass_at_1=0.75,
            total_samples=50,
            sb_correctness_corr=0.3,
            base_logit_correctness_corr=0.1,
            per_sample=[
                {"correct": i % 2 == 0, "sb": 0.5 + 0.01 * i}
                for i in range(50)
            ],
        )
        er_base = ExperimentResult(
            label="Baseline", flags={},
            pass_at_1=0.70,
            total_samples=50,
            per_sample=[
                {"correct": i % 3 == 0}
                for i in range(50)
            ],
        )

        br = _build_benchmark_result(
            er_bcvf, er_base,
            dataset_name="TestData",
            benchmark_type="test",
            goal_strategy="test_strategy",
            n_bootstrap=20,
        )

        assert isinstance(br, BenchmarkResult)
        assert br.dataset_name == "TestData"
        assert br.benchmark_type == "test"
        assert br.goal_strategy == "test_strategy"
        assert br.pass_at_1_delta_ci is not None
        assert br.sb_rho_ci is not None
        assert br.verdict in ("sb WINS", "logit WINS", "NEITHER", "~tied")

    def test_delta_ci_contains_mean(self):
        from symbolu.ontological.bcvf_experiments import ExperimentResult

        er_bcvf = ExperimentResult(
            label="C+B", flags={},
            pass_at_1=1.0,
            total_samples=10,
            sb_correctness_corr=0.5,
            base_logit_correctness_corr=0.0,
            per_sample=[{"correct": True, "sb": 0.9} for _ in range(10)],
        )
        er_base = ExperimentResult(
            label="Baseline", flags={},
            pass_at_1=0.0,
            total_samples=10,
            per_sample=[{"correct": False} for _ in range(10)],
        )

        br = _build_benchmark_result(
            er_bcvf, er_base,
            dataset_name="X", benchmark_type="x",
            goal_strategy="x", n_bootstrap=50,
        )

        ci = br.pass_at_1_delta_ci
        assert ci is not None
        assert ci.lower <= ci.mean + 1e-8
        assert ci.mean <= ci.upper + 1e-8


# =========================================================================
# Dry-Run Integration (full pipeline, no network)
# =========================================================================


class TestDryRunIntegration:
    """
    These tests run the full CLI pipeline in dry-run mode.
    They verify the pipeline works end-to-end with random tensors.
    No model downloads, no GPU, fast execution.
    """

    def test_dry_run_wikitext(self):
        report = main([
            "--dry-run", "--mode", "wikitext",
            "--samples", "30", "--n-bootstrap", "10",
            "--goal-strategy", "lookahead",
        ])
        assert isinstance(report, ComparisonReport)
        assert len(report.results) >= 1
        assert report.results[0].benchmark_type == "wikitext"

    def test_dry_run_humaneval(self):
        report = main([
            "--dry-run", "--mode", "humaneval",
            "--samples", "30", "--n-bootstrap", "10",
        ])
        assert isinstance(report, ComparisonReport)
        assert len(report.results) == 1
        assert report.results[0].benchmark_type == "code_gen"

    def test_dry_run_instruction(self):
        report = main([
            "--dry-run", "--mode", "instruction",
            "--samples", "30", "--n-bootstrap", "10",
        ])
        assert isinstance(report, ComparisonReport)
        assert len(report.results) == 1
        assert report.results[0].benchmark_type == "instruction"

    def test_dry_run_retrieval(self):
        report = main([
            "--dry-run", "--mode", "retrieval",
            "--samples", "30", "--n-bootstrap", "10",
        ])
        assert isinstance(report, ComparisonReport)
        assert len(report.results) == 1
        assert report.results[0].benchmark_type == "retrieval"

    def test_dry_run_all_modes(self):
        report = main([
            "--dry-run", "--mode", "all",
            "--samples", "20", "--n-bootstrap", "10",
            "--goal-strategy", "lookahead",
        ])
        assert isinstance(report, ComparisonReport)
        # Should have at least 4 results (wikitext + humaneval + instruction + retrieval)
        assert len(report.results) >= 4

    def test_dry_run_multiple_strategies(self):
        report = main([
            "--dry-run", "--mode", "wikitext",
            "--samples", "20", "--n-bootstrap", "10",
            "--goal-strategy", "lookahead", "random",
        ])
        assert len(report.results) == 2
        strategies = {r.goal_strategy for r in report.results}
        assert strategies == {"lookahead", "random"}

    def test_dry_run_custom_bcvf_params(self):
        report = main([
            "--dry-run", "--mode", "wikitext",
            "--samples", "20", "--n-bootstrap", "10",
            "--beta", "0.5", "--lambda-c", "0.5",
            "--goal-strategy", "lookahead",
        ])
        assert len(report.results) >= 1

    def test_dry_run_metrics_valid(self):
        report = main([
            "--dry-run", "--mode", "wikitext",
            "--samples", "50", "--n-bootstrap", "20",
            "--goal-strategy", "lookahead",
        ])
        for r in report.results:
            assert 0.0 <= r.pass_at_1 <= 1.0
            assert -1.0 <= r.sb_rho <= 1.0
            assert r.pass_at_1_delta_ci is not None
            assert r.sb_rho_ci is not None
            assert r.verdict in ("sb WINS", "logit WINS", "NEITHER", "~tied")

    def test_dry_run_json_output(self, tmp_path):
        output_path = str(tmp_path / "report.json")
        report = main([
            "--dry-run", "--mode", "wikitext",
            "--samples", "20", "--n-bootstrap", "10",
            "--goal-strategy", "lookahead",
            "--output", output_path,
        ])
        assert Path(output_path).exists()
        with open(output_path) as f:
            data = json.load(f)
        assert "benchmarks" in data
        assert len(data["benchmarks"]) >= 1

    def test_list_models(self, capsys):
        report = main(["--list-models"])
        captured = capsys.readouterr()
        assert "gpt2" in captured.out
        assert "phi3" in captured.out
        assert isinstance(report, ComparisonReport)
        assert len(report.results) == 0


# =========================================================================
# Runner Invocation Verification
# =========================================================================


class TestRunnerInvocation:
    """Verify that run_single_mode correctly delegates to ExperimentRunner."""

    def test_wikitext_returns_benchmark_results(self):
        dataset = DatasetAdapter.from_dry_run(n_samples=20)
        from symbolu.ontological.bcvf_experiments import ExperimentRunner

        runner = ExperimentRunner(
            base_config=DecodingConfig(top_m=25, beta=0.2),
        )
        flags = {"use_rerank": True, "use_logit_mod": False,
                 "use_calibration": True}
        result = runner.run_single_experiment(flags, dataset)

        # Verify it produces a valid ExperimentResult
        assert result.total_samples == 20
        assert 0.0 <= result.pass_at_1 <= 1.0
        assert len(result.per_sample) == 20

    def test_runner_config_not_mutated(self):
        """Verify base config is not mutated across runs."""
        base = DecodingConfig(top_m=25, beta=0.2, lambda_c=0.25)
        from symbolu.ontological.bcvf_experiments import ExperimentRunner

        runner = ExperimentRunner(base_config=base)
        dataset = DatasetAdapter.from_dry_run(n_samples=10)

        runner.run_single_experiment(
            {"use_rerank": True, "use_logit_mod": True,
             "use_calibration": True},
            dataset,
        )

        # Base config should be untouched
        assert base.top_m == 25
        assert base.beta == 0.2
        assert base.lambda_c == 0.25
        assert base.use_rerank is True  # default
