#!/usr/bin/env python3
"""
Tests for validate_bcvf_signal.py — the real-LLM signal validation CLI.

Tests cover all logic that can be verified without loading a real model:
    - Goal embedding strategy computation
    - Verdict determination logic
    - Model alias resolution
    - Report formatting
    - CLI argument parsing
    - SignalValidationResult construction
"""

import sys
from pathlib import Path

import pytest
import numpy as np

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

torch = pytest.importorskip("torch")

from scripts.validate_bcvf_signal import (
    ABLATION_MATRIX,
    AblationStrategyResult,
    FullValidationReport,
    SignalValidationResult,
    build_parser,
    compute_goal_embeddings,
    determine_overall_verdict,
    format_ablation_report,
    format_report,
    resolve_model_name,
)
from symbolu.ontological.bcvf_experiments import ExperimentResult


# ===========================================================================
# Goal Embedding Strategies
# ===========================================================================


class TestGoalEmbeddingStrategies:
    def test_lookahead_shifts_by_one(self):
        """Lookahead goal at position t should be hidden state at t+1."""
        T, D = 10, 32
        hidden = torch.arange(T * D, dtype=torch.float32).reshape(1, T, D)
        goals = compute_goal_embeddings(hidden, "lookahead")
        assert goals.shape == (T, D)
        # Position 0's goal should be position 1's hidden state
        assert torch.allclose(goals[0], hidden[0, 1])
        # Position T-2's goal should be position T-1's hidden state
        assert torch.allclose(goals[T - 2], hidden[0, T - 1])
        # Last position uses itself (no lookahead available)
        assert torch.allclose(goals[T - 1], hidden[0, T - 1])

    def test_prompt_mean_uses_first_quarter(self):
        """Prompt-mean with default should use first 25% of positions."""
        T, D = 20, 16
        hidden = torch.randn(1, T, D)
        goals = compute_goal_embeddings(hidden, "prompt_mean", prompt_length=0)
        expected_mean = hidden[0, : T // 4].mean(dim=0)
        assert goals.shape == (T, D)
        # All positions should get the same goal
        assert torch.allclose(goals[0], goals[T - 1])
        assert torch.allclose(goals[0], expected_mean)

    def test_prompt_mean_custom_length(self):
        """Prompt-mean with explicit prompt_length."""
        T, D = 20, 16
        hidden = torch.randn(1, T, D)
        goals = compute_goal_embeddings(hidden, "prompt_mean", prompt_length=8)
        expected_mean = hidden[0, :8].mean(dim=0)
        assert torch.allclose(goals[0], expected_mean)

    def test_random_is_deterministic(self):
        """Random strategy should be seeded and deterministic."""
        hidden = torch.randn(1, 10, 16)
        goals1 = compute_goal_embeddings(hidden, "random")
        goals2 = compute_goal_embeddings(hidden, "random")
        assert torch.allclose(goals1, goals2)

    def test_random_differs_from_hidden(self):
        """Random goals should NOT match the hidden states."""
        hidden = torch.ones(1, 10, 16) * 5.0
        goals = compute_goal_embeddings(hidden, "random")
        assert not torch.allclose(goals, hidden[0])

    def test_unknown_strategy_raises(self):
        hidden = torch.randn(1, 5, 8)
        with pytest.raises(ValueError, match="Unknown strategy"):
            compute_goal_embeddings(hidden, "nonexistent")


# ===========================================================================
# Verdict Logic
# ===========================================================================


class TestVerdictDetermination:
    def _make_result(self, strategy, sb_rho, logit_rho):
        return SignalValidationResult(
            strategy=strategy,
            model_name="test",
            n_samples=100,
            sb_correctness_rho=sb_rho,
            base_logit_correctness_rho=logit_rho,
        )

    def test_go_when_sb_wins(self):
        """When sb_rho > logit_rho + 0.05 and sb_rho > 0.1, verdict is GO."""
        results = [
            self._make_result("lookahead", sb_rho=0.35, logit_rho=0.15),
            self._make_result("random", sb_rho=0.02, logit_rho=0.01),
        ]
        verdict = determine_overall_verdict(results)
        assert "GO" in verdict
        assert "independent signal" in verdict.lower()

    def test_stop_when_logit_wins(self):
        """When logit_rho > sb_rho + 0.05, verdict is STOP RERANKING."""
        results = [
            self._make_result("lookahead", sb_rho=0.10, logit_rho=0.30),
            self._make_result("random", sb_rho=0.01, logit_rho=0.02),
        ]
        verdict = determine_overall_verdict(results)
        assert "STOP RERANKING" in verdict

    def test_stop_when_sb_near_zero(self):
        """When sb shows no signal even with oracle, verdict is STOP."""
        results = [
            self._make_result("lookahead", sb_rho=0.02, logit_rho=0.03),
            self._make_result("random", sb_rho=0.01, logit_rho=0.01),
        ]
        verdict = determine_overall_verdict(results)
        assert "STOP" in verdict
        assert "no signal" in verdict.lower()

    def test_marginal_when_tied(self):
        """When sb and logits are close, verdict is MARGINAL."""
        results = [
            self._make_result("lookahead", sb_rho=0.20, logit_rho=0.18),
            self._make_result("random", sb_rho=0.01, logit_rho=0.02),
        ]
        verdict = determine_overall_verdict(results)
        assert "MARGINAL" in verdict

    def test_invalid_when_random_shows_correlation(self):
        """When random baseline shows spurious correlation, flag it."""
        results = [
            self._make_result("lookahead", sb_rho=0.30, logit_rho=0.10),
            self._make_result("random", sb_rho=0.25, logit_rho=0.05),
        ]
        verdict = determine_overall_verdict(results)
        assert "INVALID" in verdict

    def test_incomplete_without_lookahead(self):
        """If no lookahead strategy, verdict is INCOMPLETE."""
        results = [
            self._make_result("prompt_mean", sb_rho=0.20, logit_rho=0.10),
        ]
        verdict = determine_overall_verdict(results)
        assert "INCOMPLETE" in verdict


# ===========================================================================
# Model Alias Resolution
# ===========================================================================


class TestModelAliasResolution:
    def test_gpt2_alias(self):
        assert resolve_model_name("gpt2") == "gpt2"

    def test_phi3_alias(self):
        assert resolve_model_name("phi3") == "microsoft/phi-3.5-mini-instruct"

    def test_phi3_with_dash(self):
        assert resolve_model_name("phi-3") == "microsoft/phi-3.5-mini-instruct"

    def test_stablelm_alias(self):
        assert resolve_model_name("stablelm") == "stabilityai/stablelm-zephyr-3b"

    def test_openllama_alias(self):
        assert resolve_model_name("openllama3b") == "openlm-research/open_llama_3b_v2"

    def test_full_name_passthrough(self):
        """Full HF names should pass through unchanged."""
        full = "meta-llama/Llama-2-7b-hf"
        assert resolve_model_name(full) == full

    def test_case_insensitive(self):
        assert resolve_model_name("GPT2") == "gpt2"
        assert resolve_model_name("Phi3") == "microsoft/phi-3.5-mini-instruct"


# ===========================================================================
# Report Formatting
# ===========================================================================


class TestReportFormatting:
    def _make_report(self) -> FullValidationReport:
        return FullValidationReport(
            model_name="test-model",
            model_params="3.00B",
            device="cuda",
            dataset="wikitext",
            n_samples=500,
            bcvf_config={"top_m": 500, "beta": 0.2},
            strategies=[
                SignalValidationResult(
                    strategy="lookahead", model_name="test",
                    n_samples=500,
                    sb_correctness_rho=0.25,
                    base_logit_correctness_rho=0.15,
                    logit_rank_correctness_rho=0.12,
                    confidence_correctness_rho=0.18,
                    accuracy=0.45,
                    elapsed_seconds=30.0,
                    verdict="sb WINS",
                ),
                SignalValidationResult(
                    strategy="random", model_name="test",
                    n_samples=500,
                    sb_correctness_rho=0.02,
                    base_logit_correctness_rho=0.01,
                    logit_rank_correctness_rho=0.01,
                    confidence_correctness_rho=0.03,
                    accuracy=0.44,
                    elapsed_seconds=28.0,
                    verdict="NEITHER",
                ),
            ],
            overall_verdict="GO — sb provides independent signal",
        )

    def test_report_contains_model_info(self):
        report = format_report(self._make_report())
        assert "test-model" in report
        assert "3.00B" in report
        assert "cuda" in report

    def test_report_contains_strategy_table(self):
        report = format_report(self._make_report())
        assert "lookahead" in report
        assert "random" in report
        assert "rho(sb)" in report
        assert "rho(logit)" in report

    def test_report_contains_interpretation(self):
        report = format_report(self._make_report())
        assert "INTERPRETATION" in report
        assert "oracle upper bound" in report.lower()

    def test_report_contains_overall_verdict(self):
        report = format_report(self._make_report())
        assert "OVERALL VERDICT" in report
        assert "GO" in report

    def test_report_flags_random_baseline(self):
        """Report should note that random baseline is clean."""
        report = format_report(self._make_report())
        assert "Clean" in report or "clean" in report


# ===========================================================================
# CLI Argument Parsing
# ===========================================================================


class TestCLIParsing:
    def test_default_args(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.model == "gpt2"
        assert args.samples == 500
        assert args.top_m == 500
        assert args.beta == 0.2
        assert args.strategies == ["lookahead", "prompt_mean", "random"]
        assert args.device == "auto"
        assert args.ablation is False
        assert args.dry_run is False

    def test_ablation_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--ablation", "--dry-run"])
        assert args.ablation is True
        assert args.dry_run is True

    def test_custom_model(self):
        parser = build_parser()
        args = parser.parse_args(["--model", "phi3", "--samples", "100"])
        assert args.model == "phi3"
        assert args.samples == 100

    def test_custom_strategies(self):
        parser = build_parser()
        args = parser.parse_args(["--strategies", "lookahead", "random"])
        assert args.strategies == ["lookahead", "random"]

    def test_custom_bcvf_params(self):
        parser = build_parser()
        args = parser.parse_args(["--top-m", "200", "--beta", "0.1"])
        assert args.top_m == 200
        assert args.beta == pytest.approx(0.1)

    def test_output_path(self):
        parser = build_parser()
        args = parser.parse_args(["--output", "/tmp/results.json"])
        assert args.output == "/tmp/results.json"

    def test_dtype_choices(self):
        parser = build_parser()
        for dtype in ["auto", "float16", "bfloat16", "float32"]:
            args = parser.parse_args(["--dtype", dtype])
            assert args.dtype == dtype


# ===========================================================================
# SignalValidationResult
# ===========================================================================


class TestSignalValidationResult:
    def test_default_values(self):
        r = SignalValidationResult(strategy="test", model_name="m", n_samples=0)
        assert r.sb_correctness_rho == 0.0
        assert r.logit_rank_correctness_rho == 0.0
        assert r.verdict == ""

    def test_verdict_populated(self):
        r = SignalValidationResult(
            strategy="lookahead", model_name="m", n_samples=100,
            sb_correctness_rho=0.3,
            base_logit_correctness_rho=0.1,
            verdict="sb WINS",
        )
        assert r.verdict == "sb WINS"
        assert r.sb_correctness_rho > r.base_logit_correctness_rho


# ===========================================================================
# Ablation Matrix
# ===========================================================================


class TestAblationMatrix:
    def test_matrix_has_four_configs(self):
        """The ablation matrix should have exactly 4 configs."""
        assert len(ABLATION_MATRIX) == 4

    def test_baseline_is_first(self):
        """First config should be vanilla baseline (all False)."""
        baseline = ABLATION_MATRIX[0]
        assert baseline["use_rerank"] is False
        assert baseline["use_logit_mod"] is False
        assert baseline["use_calibration"] is False

    def test_b_only_config(self):
        """Second config should be calibration-only."""
        b = ABLATION_MATRIX[1]
        assert b["use_rerank"] is False
        assert b["use_calibration"] is True
        assert b["use_logit_mod"] is False

    def test_c_only_config(self):
        """Third config should be rerank-only."""
        c = ABLATION_MATRIX[2]
        assert c["use_rerank"] is True
        assert c["use_calibration"] is False
        assert c["use_logit_mod"] is False

    def test_full_pipeline_config(self):
        """Fourth config should be A+B+C."""
        full = ABLATION_MATRIX[3]
        assert full["use_rerank"] is True
        assert full["use_logit_mod"] is True
        assert full["use_calibration"] is True


# ===========================================================================
# Ablation Report Formatting
# ===========================================================================


class TestAblationReport:
    def _make_ablation(self, strategy, sb_rho, logit_rho,
                       baseline_ece=0.10, best_ece=0.08,
                       delta_pass1=0.01):
        """Helper to create an AblationStrategyResult with mock ExperimentResults."""
        results = []
        for flags in ABLATION_MATRIX:
            from symbolu.ontological.bcvf_experiments import config_label
            label = config_label(flags)
            results.append(ExperimentResult(
                label=label,
                flags=flags,
                pass_at_1=0.5 + delta_pass1 if flags.get("use_rerank") else 0.5,
                rerank_change_pct=0.05 if flags.get("use_rerank") else 0.0,
                rerank_net_benefit=0.02 if flags.get("use_rerank") else 0.0,
                sb_correctness_corr=sb_rho,
                base_logit_correctness_corr=logit_rho,
                ece=best_ece if flags.get("use_calibration") else baseline_ece,
                brier=0.2,
                mean_kl_base_mod=0.5 if flags.get("use_logit_mod") else 0.0,
                mean_entropy_delta=-0.1 if flags.get("use_logit_mod") else 0.0,
            ))
        return AblationStrategyResult(
            strategy=strategy,
            experiment_results=results,
            baseline_pass1=0.5,
            best_bcvf_pass1=0.5 + delta_pass1,
            delta_pass1=delta_pass1,
            sb_rho_at_best=sb_rho,
            logit_rho_at_best=logit_rho,
            baseline_ece=baseline_ece,
            best_ece=best_ece,
        )

    def test_report_contains_all_configs(self):
        abl = self._make_ablation("lookahead", 0.3, 0.1)
        report = format_ablation_report("test", "3B", [abl])
        assert "baseline" in report
        assert "A+B+C" in report
        assert "SOFTMAX REVAMP" in report

    def test_condition_1_detected(self):
        """When sb_rho > logit_rho and pass@1 didn't drop, condition 1 fires."""
        abl = self._make_ablation("lookahead", sb_rho=0.3, logit_rho=0.1,
                                  delta_pass1=0.01)
        report = format_ablation_report("test", "3B", [abl])
        assert "CONDITION 1 MET" in report
        assert "Predictive-signal win" in report

    def test_condition_2_detected(self):
        """When ECE improves by >10% via logit modulation, condition 2 fires."""
        abl = self._make_ablation("lookahead", sb_rho=0.1, logit_rho=0.1,
                                  baseline_ece=0.20, best_ece=0.10,
                                  delta_pass1=0.0)
        report = format_ablation_report("test", "3B", [abl])
        assert "CONDITION 2 MET" in report
        assert "calibration win" in report.lower()

    def test_neither_condition_detected(self):
        """When neither condition is met, report says so."""
        abl = self._make_ablation("lookahead", sb_rho=0.05, logit_rho=0.10,
                                  baseline_ece=0.10, best_ece=0.10,
                                  delta_pass1=-0.01)
        report = format_ablation_report("test", "3B", [abl])
        assert "NEITHER CONDITION MET" in report

    def test_overall_verdict_go(self):
        """Overall verdict should be GO when lookahead shows condition 1."""
        abl = self._make_ablation("lookahead", sb_rho=0.3, logit_rho=0.1,
                                  delta_pass1=0.02)
        report = format_ablation_report("test", "3B", [abl])
        assert "ready to be revamped" in report.lower()

    def test_overall_verdict_calibration_only(self):
        """When logit mod improves calibration, recommend Option A."""
        abl = self._make_ablation("lookahead", sb_rho=0.05, logit_rho=0.10,
                                  baseline_ece=0.20, best_ece=0.08,
                                  delta_pass1=-0.005)
        report = format_ablation_report("test", "3B", [abl])
        assert "logit modulation" in report.lower() or "option a" in report.lower()

    def test_report_shows_exact_columns(self):
        """Report should contain the exact metrics ChatGPT requested + AUROC."""
        abl = self._make_ablation("lookahead", 0.2, 0.1)
        report = format_ablation_report("test", "3B", [abl])
        assert "pass@1" in report
        assert "Rerank%" in report
        assert "NetBen" in report
        assert "sb_rho" in report
        assert "logit_rho" in report
        assert "ECE" in report
        assert "Brier" in report
        assert "KL" in report
        assert "dH" in report
        assert "AUC_l" in report
        assert "AUC_s" in report
        assert "AUC_c" in report

    def test_auroc_verdict_present(self):
        """Report should contain AUROC correctness-prediction verdict."""
        abl = self._make_ablation("lookahead", 0.2, 0.1)
        report = format_ablation_report("test", "3B", [abl])
        assert "AUROC correctness-prediction test" in report
        assert "AUROC(logit)" in report
        assert "AUROC(sb)" in report
        assert "AUROC(combined)" in report
