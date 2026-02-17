#!/usr/bin/env python3
"""
BCVF Benchmark Suite — Realistic Deployment Evaluation
=======================================================

Extends the BCVF experiment framework with three deployment-realistic
benchmarks to determine whether BCVF provides signal beyond oracle
lookahead:

1. **HumanEval code generation** — goal embedding from problem
   description (docstring + signature).

2. **Instruction-following** — goal embedding from instruction text
   only (no answer leakage).

3. **Retrieval-augmented generation** — goal embedding from a
   retrieved context passage.

Each benchmark plugs into the existing :class:`ExperimentRunner` and
:class:`StepLogger` pipeline, adding no new decoding logic.

Additionally provides:

- Bootstrap confidence intervals for pass@1 delta and Spearman rho.
- Unified cross-benchmark comparison report with verdicts.

Usage::

    from symbolu.ontological.bcvf_benchmarks import (
        BenchmarkRunner,
        BenchmarkSuite,
        bootstrap_ci,
    )

    suite = BenchmarkSuite(model, tokenizer, device="cpu")
    report = suite.run_all(
        humaneval_problems=problems,
        instruction_pairs=pairs,
        retrieval_corpus=corpus,
        retrieval_queries=queries,
    )
    suite.print_comparison(report)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

try:
    import torch
    import torch.nn.functional as F

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

import numpy as np

from symbolu.ontological.bcvf_decoding import BCVFDecoder, DecodingConfig
from symbolu.ontological.bcvf_calibration import (
    CalibrationTracker,
    compute_ece,
    spearman_rank_correlation,
)
from symbolu.ontological.bcvf_experiments import (
    EXPERIMENT_MATRIX,
    ExperimentResult,
    ExperimentRunner,
    StepLogger,
    StepRecord,
    config_label,
    evaluate_stop_conditions,
    evaluate_energy_stop_conditions,
    generate_with_bcvf,
    run_unit_tests,
)
from symbolu.ontological.bcvf_goal_embeddings import (
    GoalEmbeddingFactory,
    SimpleRetriever,
    compute_text_embedding,
)


# =========================================================================
# Data Structures
# =========================================================================


@dataclass
class InstructionSample:
    """One instruction-response pair for the instruction benchmark."""

    instruction: str
    response: str
    task_id: str = ""


@dataclass
class RetrievalSample:
    """One sample for the retrieval-augmented benchmark."""

    query_text: str
    ground_truth_text: str
    context_text: str = ""  # Retrieved passage (filled by retriever)
    task_id: str = ""


@dataclass
class BootstrapCI:
    """95% bootstrap confidence interval."""

    mean: float
    lower: float
    upper: float
    n_bootstrap: int = 1000

    def __str__(self) -> str:
        return f"{self.mean:+.4f} [{self.lower:+.4f}, {self.upper:+.4f}]"


@dataclass
class BenchmarkResult:
    """
    Extended result for a single benchmark + config combination.

    Inherits all fields from ExperimentResult and adds benchmark-specific
    metadata and bootstrap CIs.
    """

    experiment_result: ExperimentResult
    # Benchmark metadata
    dataset_name: str = ""
    benchmark_type: str = ""  # "code_gen", "instruction", "retrieval", "wikitext"
    goal_strategy: str = ""
    # Bootstrap CIs
    pass_at_1_delta_ci: Optional[BootstrapCI] = None
    sb_rho_ci: Optional[BootstrapCI] = None
    logit_rho_ci: Optional[BootstrapCI] = None
    # Verdict
    verdict: str = ""
    # Energy mode: "baseline" or "bayesian"
    energy_mode: str = "baseline"

    @property
    def sb_rho(self) -> float:
        return self.experiment_result.sb_correctness_corr

    @property
    def logit_rho(self) -> float:
        return self.experiment_result.base_logit_correctness_corr

    @property
    def pass_at_1(self) -> float:
        return self.experiment_result.pass_at_1

    @property
    def label(self) -> str:
        return self.experiment_result.label


@dataclass
class ComparisonReport:
    """Aggregated comparison across all benchmarks."""

    results: List[BenchmarkResult] = field(default_factory=list)
    baseline_pass_at_1: Dict[str, float] = field(default_factory=dict)
    timestamp: str = ""


# =========================================================================
# Bootstrap Confidence Intervals
# =========================================================================


def bootstrap_ci(
    values: np.ndarray,
    statistic_fn: Callable[[np.ndarray], float],
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    seed: Optional[int] = None,
) -> BootstrapCI:
    """
    Compute bootstrap confidence interval for an arbitrary statistic.

    Args:
        values: 1-D array of observations.
        statistic_fn: Function that computes the statistic from a sample.
        n_bootstrap: Number of bootstrap resamples.
        confidence: Confidence level (default 0.95 for 95% CI).
        seed: Random seed for reproducibility.

    Returns:
        BootstrapCI with mean, lower, and upper bounds.
    """
    rng = np.random.RandomState(seed)
    n = len(values)

    if n == 0:
        return BootstrapCI(mean=0.0, lower=0.0, upper=0.0, n_bootstrap=0)

    observed = statistic_fn(values)
    bootstrap_stats = np.empty(n_bootstrap)

    for i in range(n_bootstrap):
        sample = rng.choice(values, size=n, replace=True)
        bootstrap_stats[i] = statistic_fn(sample)

    alpha = (1.0 - confidence) / 2.0
    lower = float(np.percentile(bootstrap_stats, 100 * alpha))
    upper = float(np.percentile(bootstrap_stats, 100 * (1.0 - alpha)))

    return BootstrapCI(
        mean=float(observed),
        lower=lower,
        upper=upper,
        n_bootstrap=n_bootstrap,
    )


def bootstrap_pass_at_1_delta(
    baseline_correct: np.ndarray,
    bcvf_correct: np.ndarray,
    n_bootstrap: int = 1000,
    seed: Optional[int] = None,
) -> BootstrapCI:
    """
    Bootstrap CI for the pass@1 delta (bcvf - baseline).

    Args:
        baseline_correct: Binary array, 1 = correct under baseline.
        bcvf_correct: Binary array, 1 = correct under BCVF.
        n_bootstrap: Number of bootstrap resamples.
        seed: Random seed.

    Returns:
        BootstrapCI for the delta.
    """
    rng = np.random.RandomState(seed)
    baseline_correct = np.asarray(baseline_correct, dtype=np.float64)
    bcvf_correct = np.asarray(bcvf_correct, dtype=np.float64)
    n = len(baseline_correct)

    if n == 0:
        return BootstrapCI(mean=0.0, lower=0.0, upper=0.0, n_bootstrap=0)

    observed_delta = float(bcvf_correct.mean() - baseline_correct.mean())
    deltas = np.empty(n_bootstrap)

    for i in range(n_bootstrap):
        idx = rng.choice(n, size=n, replace=True)
        deltas[i] = bcvf_correct[idx].mean() - baseline_correct[idx].mean()

    lower = float(np.percentile(deltas, 2.5))
    upper = float(np.percentile(deltas, 97.5))

    return BootstrapCI(
        mean=observed_delta,
        lower=lower,
        upper=upper,
        n_bootstrap=n_bootstrap,
    )


def bootstrap_spearman(
    x: np.ndarray,
    y: np.ndarray,
    n_bootstrap: int = 1000,
    seed: Optional[int] = None,
) -> BootstrapCI:
    """
    Bootstrap CI for Spearman rank correlation.

    Args:
        x: 1-D numeric array.
        y: 1-D numeric array of same length.
        n_bootstrap: Number of bootstrap resamples.
        seed: Random seed.

    Returns:
        BootstrapCI for Spearman rho.
    """
    rng = np.random.RandomState(seed)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = len(x)

    if n < 3:
        return BootstrapCI(mean=0.0, lower=0.0, upper=0.0, n_bootstrap=0)

    observed = spearman_rank_correlation(x, y)
    rhos = np.empty(n_bootstrap)

    for i in range(n_bootstrap):
        idx = rng.choice(n, size=n, replace=True)
        rhos[i] = spearman_rank_correlation(x[idx], y[idx])

    lower = float(np.percentile(rhos, 2.5))
    upper = float(np.percentile(rhos, 97.5))

    return BootstrapCI(
        mean=float(observed),
        lower=lower,
        upper=upper,
        n_bootstrap=n_bootstrap,
    )


# =========================================================================
# Verdict logic
# =========================================================================


def compute_verdict(sb_rho: float, logit_rho: float) -> str:
    """
    Determine verdict from Spearman correlations.

    Rules:
        - sb WINS if sb_rho > logit_rho + 0.05
        - logit WINS if logit_rho > sb_rho + 0.05
        - NEITHER if both < 0.05 in absolute value
        - ~tied otherwise
    """
    if abs(sb_rho) < 0.05 and abs(logit_rho) < 0.05:
        return "NEITHER"
    if sb_rho > logit_rho + 0.05:
        return "sb WINS"
    if logit_rho > sb_rho + 0.05:
        return "logit WINS"
    return "~tied"


# =========================================================================
# Benchmark Runner
# =========================================================================


class BenchmarkRunner:
    """
    Runs individual BCVF benchmarks using the existing ExperimentRunner.

    Each ``run_*`` method prepares a dataset in the format expected by
    :meth:`ExperimentRunner.run_single_experiment` and delegates to it.

    Args:
        model: Transformer model.
        tokenizer: Tokenizer.
        base_config: Base DecodingConfig.
        device: Torch device string.
    """

    def __init__(
        self,
        model: Any = None,
        tokenizer: Any = None,
        base_config: Optional[DecodingConfig] = None,
        device: str = "cpu",
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.base_config = base_config or DecodingConfig()
        self.device = device
        self.experiment_runner = ExperimentRunner(
            model=model,
            tokenizer=tokenizer,
            base_config=self.base_config,
            device=device,
        )
        self.goal_factory = GoalEmbeddingFactory(
            model=model,
            tokenizer=tokenizer,
            device=device,
        )

    # ------------------------------------------------------------------
    # 1. HumanEval Code Generation
    # ------------------------------------------------------------------

    def run_humaneval_experiment(
        self,
        problems: Sequence[Dict[str, Any]],
        flags: Optional[Dict[str, bool]] = None,
        n_bootstrap: int = 1000,
    ) -> BenchmarkResult:
        """
        Run HumanEval code generation benchmark.

        Each problem dict should have:
            - ``prompt``: str (docstring + signature)
            - ``hidden_state``: [1, D] tensor
            - ``logits``: [1, V] tensor
            - ``ground_truth``: int token id (for next-token eval)

        The goal embedding is computed from the ``prompt`` field by
        mean-pooling last hidden states (``code_problem_only`` strategy).

        For full code-generation evaluation (pass@1 via unit tests),
        use :meth:`run_humaneval_generation` instead.

        Args:
            problems: Sequence of problem dicts.
            flags: Ablation flags (defaults to rerank+calibration).
            n_bootstrap: Number of bootstrap samples for CIs.

        Returns:
            BenchmarkResult with metrics and CIs.
        """
        flags = flags or {
            "use_rerank": True,
            "use_logit_mod": False,
            "use_calibration": True,
        }

        # Prepare dataset with goal embeddings from problem descriptions
        dataset = self._prepare_text_goal_dataset(
            samples=problems,
            text_key="prompt",
            goal_strategy="code_problem_only",
        )

        # Run experiment
        result = self.experiment_runner.run_single_experiment(
            flags, dataset
        )

        # Compute baseline for delta
        baseline_flags = {
            "use_rerank": False,
            "use_logit_mod": False,
            "use_calibration": False,
        }
        baseline_result = self.experiment_runner.run_single_experiment(
            baseline_flags, dataset
        )

        # Bootstrap CIs
        bcvf_correct = np.array([
            1.0 if s.get("correct") else 0.0
            for s in result.per_sample
        ])
        baseline_correct = np.array([
            1.0 if s.get("correct") else 0.0
            for s in baseline_result.per_sample
        ])

        delta_ci = bootstrap_pass_at_1_delta(
            baseline_correct, bcvf_correct,
            n_bootstrap=n_bootstrap, seed=42,
        )

        sb_values = np.array([s.get("sb", 0.0) for s in result.per_sample])
        correct_values = bcvf_correct
        sb_ci = bootstrap_spearman(
            sb_values, correct_values,
            n_bootstrap=n_bootstrap, seed=42,
        )

        logit_rho = result.base_logit_correctness_corr
        logit_ci = BootstrapCI(
            mean=logit_rho, lower=logit_rho, upper=logit_rho,
            n_bootstrap=0,
        )

        verdict = compute_verdict(
            result.sb_correctness_corr,
            result.base_logit_correctness_corr,
        )

        return BenchmarkResult(
            experiment_result=result,
            dataset_name="HumanEval",
            benchmark_type="code_gen",
            goal_strategy="code_problem_only",
            pass_at_1_delta_ci=delta_ci,
            sb_rho_ci=sb_ci,
            logit_rho_ci=logit_ci,
            verdict=verdict,
        )

    # ------------------------------------------------------------------
    # 2. Instruction-Following
    # ------------------------------------------------------------------

    def run_instruction_experiment(
        self,
        samples: Sequence[Dict[str, Any]],
        flags: Optional[Dict[str, bool]] = None,
        n_bootstrap: int = 1000,
    ) -> BenchmarkResult:
        """
        Run instruction-following benchmark.

        Each sample dict should have:
            - ``instruction``: str (the instruction text)
            - ``hidden_state``: [1, D] tensor
            - ``logits``: [1, V] tensor
            - ``ground_truth``: int token id

        Goal embedding is computed from ``instruction`` only (no answer
        leakage) using the ``instruction_only`` strategy.

        Args:
            samples: Sequence of sample dicts.
            flags: Ablation flags.
            n_bootstrap: Bootstrap sample count.

        Returns:
            BenchmarkResult with metrics and CIs.
        """
        flags = flags or {
            "use_rerank": True,
            "use_logit_mod": False,
            "use_calibration": True,
        }

        dataset = self._prepare_text_goal_dataset(
            samples=samples,
            text_key="instruction",
            goal_strategy="instruction_only",
        )

        result = self.experiment_runner.run_single_experiment(
            flags, dataset
        )

        baseline_flags = {
            "use_rerank": False,
            "use_logit_mod": False,
            "use_calibration": False,
        }
        baseline_result = self.experiment_runner.run_single_experiment(
            baseline_flags, dataset
        )

        bcvf_correct = np.array([
            1.0 if s.get("correct") else 0.0
            for s in result.per_sample
        ])
        baseline_correct = np.array([
            1.0 if s.get("correct") else 0.0
            for s in baseline_result.per_sample
        ])

        delta_ci = bootstrap_pass_at_1_delta(
            baseline_correct, bcvf_correct,
            n_bootstrap=n_bootstrap, seed=42,
        )

        sb_values = np.array([s.get("sb", 0.0) for s in result.per_sample])
        sb_ci = bootstrap_spearman(
            sb_values, bcvf_correct,
            n_bootstrap=n_bootstrap, seed=42,
        )

        verdict = compute_verdict(
            result.sb_correctness_corr,
            result.base_logit_correctness_corr,
        )

        return BenchmarkResult(
            experiment_result=result,
            dataset_name="Instruction",
            benchmark_type="instruction",
            goal_strategy="instruction_only",
            pass_at_1_delta_ci=delta_ci,
            sb_rho_ci=sb_ci,
            verdict=verdict,
        )

    # ------------------------------------------------------------------
    # 3. Retrieval-Augmented Generation
    # ------------------------------------------------------------------

    def run_retrieval_experiment(
        self,
        samples: Sequence[Dict[str, Any]],
        flags: Optional[Dict[str, bool]] = None,
        n_bootstrap: int = 1000,
    ) -> BenchmarkResult:
        """
        Run retrieval-augmented generation benchmark.

        Each sample dict should have:
            - ``context``: str (the retrieved passage)
            - ``hidden_state``: [1, D] tensor
            - ``logits``: [1, V] tensor
            - ``ground_truth``: int token id

        Goal embedding is computed from the ``context`` field using
        the ``retrieval_context`` strategy.

        For automatic retrieval, use :meth:`prepare_retrieval_samples`
        to populate context from a corpus before calling this method.

        Args:
            samples: Sequence of sample dicts with ``context`` field.
            flags: Ablation flags.
            n_bootstrap: Bootstrap sample count.

        Returns:
            BenchmarkResult with metrics and CIs.
        """
        flags = flags or {
            "use_rerank": True,
            "use_logit_mod": False,
            "use_calibration": True,
        }

        dataset = self._prepare_text_goal_dataset(
            samples=samples,
            text_key="context",
            goal_strategy="retrieval_context",
        )

        result = self.experiment_runner.run_single_experiment(
            flags, dataset
        )

        baseline_flags = {
            "use_rerank": False,
            "use_logit_mod": False,
            "use_calibration": False,
        }
        baseline_result = self.experiment_runner.run_single_experiment(
            baseline_flags, dataset
        )

        bcvf_correct = np.array([
            1.0 if s.get("correct") else 0.0
            for s in result.per_sample
        ])
        baseline_correct = np.array([
            1.0 if s.get("correct") else 0.0
            for s in baseline_result.per_sample
        ])

        delta_ci = bootstrap_pass_at_1_delta(
            baseline_correct, bcvf_correct,
            n_bootstrap=n_bootstrap, seed=42,
        )

        sb_values = np.array([s.get("sb", 0.0) for s in result.per_sample])
        sb_ci = bootstrap_spearman(
            sb_values, bcvf_correct,
            n_bootstrap=n_bootstrap, seed=42,
        )

        verdict = compute_verdict(
            result.sb_correctness_corr,
            result.base_logit_correctness_corr,
        )

        return BenchmarkResult(
            experiment_result=result,
            dataset_name="Retrieval-Augmented",
            benchmark_type="retrieval",
            goal_strategy="retrieval_context",
            pass_at_1_delta_ci=delta_ci,
            sb_rho_ci=sb_ci,
            verdict=verdict,
        )

    # ------------------------------------------------------------------
    # Dataset preparation helpers
    # ------------------------------------------------------------------

    def _prepare_text_goal_dataset(
        self,
        samples: Sequence[Dict[str, Any]],
        text_key: str,
        goal_strategy: str,
    ) -> List[Dict[str, Any]]:
        """
        Prepare a dataset with goal embeddings computed from a text field.

        For each sample, if ``goal_embedding`` is already present it is
        used as-is.  Otherwise, the text at ``text_key`` is encoded by
        the goal factory.

        When no model is available (unit-test mode), generates random
        goal embeddings with the correct dimension.
        """
        dataset: List[Dict[str, Any]] = []

        for sample in samples:
            entry = dict(sample)  # shallow copy

            if "goal_embedding" not in entry:
                text = entry.get(text_key, "")
                if (
                    text
                    and self.model is not None
                    and self.tokenizer is not None
                ):
                    goal = self.goal_factory.build(
                        goal_strategy, text=text
                    )
                    entry["goal_embedding"] = goal
                else:
                    # Fallback: use hidden_state shape to create random goal
                    h = entry.get("hidden_state")
                    if PYTORCH_AVAILABLE and h is not None:
                        if isinstance(h, torch.Tensor):
                            D = h.shape[-1]
                        else:
                            D = len(h) if hasattr(h, "__len__") else 64
                        entry["goal_embedding"] = torch.randn(1, D)

            dataset.append(entry)

        return dataset

    def prepare_retrieval_samples(
        self,
        query_samples: Sequence[Dict[str, Any]],
        corpus_texts: Sequence[str],
        corpus_embeddings: Optional[Any] = None,
        top_k: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Populate ``context`` field by retrieving from a corpus.

        Uses cosine similarity between query hidden state (mean-pooled)
        and corpus embeddings.  If ``corpus_embeddings`` are not provided,
        generates random embeddings (for testing).

        Args:
            query_samples: Samples with ``hidden_state`` and ``ground_truth``.
            corpus_texts: List of corpus passage strings.
            corpus_embeddings: Optional [N, D] tensor of corpus embeddings.
            top_k: Number of passages to retrieve (uses top-1 as context).

        Returns:
            Updated samples with ``context`` field populated.
        """
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch is required")

        retriever = SimpleRetriever(
            model=self.model,
            tokenizer=self.tokenizer,
            device=self.device,
        )

        if corpus_embeddings is not None:
            retriever.index_from_embeddings(corpus_texts, corpus_embeddings)
        elif self.model is not None and self.tokenizer is not None:
            retriever.index(corpus_texts)
        else:
            # Generate random embeddings for testing
            D = 64
            sample_h = query_samples[0].get("hidden_state") if query_samples else None
            if sample_h is not None and isinstance(sample_h, torch.Tensor):
                D = sample_h.shape[-1]
            random_emb = torch.randn(len(corpus_texts), D)
            retriever.index_from_embeddings(corpus_texts, random_emb)

        result_samples = []
        for sample in query_samples:
            entry = dict(sample)
            h = entry.get("hidden_state")

            if h is not None:
                if isinstance(h, torch.Tensor):
                    if h.dim() == 2:
                        query_emb = h  # [1, D]
                    else:
                        query_emb = h.unsqueeze(0)
                else:
                    query_emb = torch.tensor(h, dtype=torch.float32)
                    if query_emb.dim() == 1:
                        query_emb = query_emb.unsqueeze(0)

                hits = retriever.retrieve(query_emb, top_k=top_k)
                if hits:
                    entry["context"] = hits[0]["text"]
                else:
                    entry["context"] = ""
            else:
                entry["context"] = ""

            result_samples.append(entry)

        return result_samples


# =========================================================================
# Benchmark Suite — runs all benchmarks and produces comparison
# =========================================================================


class BenchmarkSuite:
    """
    Orchestrates all BCVF benchmarks and produces a unified comparison.

    Args:
        model: Transformer model.
        tokenizer: Tokenizer.
        base_config: Base DecodingConfig.
        device: Torch device.
    """

    def __init__(
        self,
        model: Any = None,
        tokenizer: Any = None,
        base_config: Optional[DecodingConfig] = None,
        device: str = "cpu",
    ):
        self.runner = BenchmarkRunner(
            model=model,
            tokenizer=tokenizer,
            base_config=base_config,
            device=device,
        )
        self.base_config = base_config or DecodingConfig()

    def run_all(
        self,
        humaneval_problems: Optional[Sequence[Dict[str, Any]]] = None,
        instruction_samples: Optional[Sequence[Dict[str, Any]]] = None,
        retrieval_samples: Optional[Sequence[Dict[str, Any]]] = None,
        flags: Optional[Dict[str, bool]] = None,
        n_bootstrap: int = 1000,
    ) -> ComparisonReport:
        """
        Run all available benchmarks and collect results.

        Args:
            humaneval_problems: HumanEval dataset (optional).
            instruction_samples: Instruction pairs (optional).
            retrieval_samples: Retrieval samples with ``context`` (optional).
            flags: Ablation flags for the BCVF config to test.
            n_bootstrap: Bootstrap resample count.

        Returns:
            ComparisonReport aggregating all benchmark results.
        """
        report = ComparisonReport(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

        if humaneval_problems is not None and len(humaneval_problems) > 0:
            result = self.runner.run_humaneval_experiment(
                humaneval_problems,
                flags=flags,
                n_bootstrap=n_bootstrap,
            )
            report.results.append(result)

        if instruction_samples is not None and len(instruction_samples) > 0:
            result = self.runner.run_instruction_experiment(
                instruction_samples,
                flags=flags,
                n_bootstrap=n_bootstrap,
            )
            report.results.append(result)

        if retrieval_samples is not None and len(retrieval_samples) > 0:
            result = self.runner.run_retrieval_experiment(
                retrieval_samples,
                flags=flags,
                n_bootstrap=n_bootstrap,
            )
            report.results.append(result)

        return report

    # ------------------------------------------------------------------
    # Unified comparison report
    # ------------------------------------------------------------------

    @staticmethod
    def print_comparison(report: ComparisonReport) -> str:
        """
        Print a unified cross-benchmark comparison table.

        Columns:
            Dataset | Type | Goal | pass@1 | Δpass@1 [95% CI] |
            sb_rho [95% CI] | logit_rho | Verdict

        Returns the table as a string (also prints it).
        """
        header = (
            f"{'Dataset':<20} {'Type':<14} {'Goal':<20} "
            f"{'Energy':<10} "
            f"{'pass@1':>7} {'Δpass@1':>8} {'95% CI':>22} "
            f"{'sb_rho':>8} {'95% CI':>22} "
            f"{'logit_rho':>10} {'Verdict':<14}"
        )
        sep = "=" * len(header)
        lines = [sep, header, sep]

        for r in report.results:
            delta_str = ""
            delta_ci_str = ""
            if r.pass_at_1_delta_ci is not None:
                delta_str = f"{r.pass_at_1_delta_ci.mean:>+8.4f}"
                delta_ci_str = (
                    f"[{r.pass_at_1_delta_ci.lower:+.4f}, "
                    f"{r.pass_at_1_delta_ci.upper:+.4f}]"
                )
            else:
                delta_str = f"{'N/A':>8}"
                delta_ci_str = f"{'':>22}"

            sb_ci_str = ""
            if r.sb_rho_ci is not None:
                sb_ci_str = (
                    f"[{r.sb_rho_ci.lower:+.4f}, "
                    f"{r.sb_rho_ci.upper:+.4f}]"
                )

            line = (
                f"{r.dataset_name:<20} {r.benchmark_type:<14} "
                f"{r.goal_strategy:<20} "
                f"{r.energy_mode:<10} "
                f"{r.pass_at_1:>7.3f} {delta_str} {delta_ci_str:>22} "
                f"{r.sb_rho:>+8.4f} {sb_ci_str:>22} "
                f"{r.logit_rho:>+10.4f} {r.verdict:<14}"
            )
            lines.append(line)

        lines.append(sep)

        # Overall assessment
        lines.append("")
        lines.append("Assessment:")
        sb_wins = sum(1 for r in report.results if "sb WINS" in r.verdict)
        logit_wins = sum(
            1 for r in report.results if "logit WINS" in r.verdict
        )
        neither = sum(
            1 for r in report.results if "NEITHER" in r.verdict
        )
        tied = sum(1 for r in report.results if "tied" in r.verdict)

        lines.append(
            f"  sb WINS: {sb_wins}  |  logit WINS: {logit_wins}  |  "
            f"NEITHER: {neither}  |  ~tied: {tied}"
        )

        if sb_wins > logit_wins and sb_wins > 0:
            lines.append(
                "  >> BCVF shows deployment-relevant signal across benchmarks."
            )
        elif logit_wins >= sb_wins and logit_wins > 0:
            lines.append(
                "  >> BCVF does NOT outperform logit confidence — "
                "oracle-only value."
            )
        else:
            lines.append(
                "  >> Inconclusive — neither signal dominates."
            )

        table = "\n".join(lines)
        print(table)
        return table

    # ------------------------------------------------------------------
    # JSON export
    # ------------------------------------------------------------------

    @staticmethod
    def save_report(
        report: ComparisonReport,
        path: str = "bcvf_benchmark_report.json",
    ) -> None:
        """Save the comparison report to JSON."""
        data = {
            "timestamp": report.timestamp,
            "benchmarks": [],
        }
        for r in report.results:
            entry = {
                "dataset_name": r.dataset_name,
                "benchmark_type": r.benchmark_type,
                "goal_strategy": r.goal_strategy,
                "pass_at_1": r.pass_at_1,
                "sb_rho": r.sb_rho,
                "logit_rho": r.logit_rho,
                "verdict": r.verdict,
                "config_label": r.label,
                "energy_mode": r.energy_mode,
            }
            if r.pass_at_1_delta_ci is not None:
                entry["pass_at_1_delta_ci"] = {
                    "mean": r.pass_at_1_delta_ci.mean,
                    "lower": r.pass_at_1_delta_ci.lower,
                    "upper": r.pass_at_1_delta_ci.upper,
                }
            if r.sb_rho_ci is not None:
                entry["sb_rho_ci"] = {
                    "mean": r.sb_rho_ci.mean,
                    "lower": r.sb_rho_ci.lower,
                    "upper": r.sb_rho_ci.upper,
                }
            data["benchmarks"].append(entry)

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


# =========================================================================
# Extended print_summary — patched into ExperimentRunner
# =========================================================================


def print_energy_comparison(
    baseline_results: List[BenchmarkResult],
    energy_results: List[BenchmarkResult],
    alpha: float,
    energy_beta: float,
    uncertainty_mode: str,
) -> str:
    """
    Print a comparison table specific to Bayesian Energy Softmax.

    Columns: Mode | α | β | Uncertainty | pass@1 | Δpass | ECE | Brier | ρ | Verdict

    Args:
        baseline_results: Results without energy softmax.
        energy_results: Results with energy softmax.
        alpha: Energy α parameter.
        energy_beta: Energy β parameter.
        uncertainty_mode: Uncertainty estimator name.

    Returns:
        The table as a string (also printed).
    """
    header = (
        f"{'Mode':<12} {'α':>5} {'β':>5} {'Uncertainty':<12} "
        f"{'pass@1':>7} {'Δpass':>8} {'ECE':>8} {'Brier':>8} "
        f"{'ρ':>8} {'Verdict':<10}"
    )
    sep = "─" * len(header)
    lines = [sep, header, sep]

    # Build paired rows (baseline → energy for each dataset)
    pairs = {}
    for br in baseline_results:
        pairs.setdefault(br.dataset_name, {})["baseline"] = br
    for er in energy_results:
        pairs.setdefault(er.dataset_name, {})["energy"] = er

    for dataset_name, pair in pairs.items():
        bl = pair.get("baseline")
        en = pair.get("energy")

        if bl is not None:
            exp = bl.experiment_result
            lines.append(
                f"{'baseline':<12} {'–':>5} {'–':>5} {'–':<12} "
                f"{exp.pass_at_1:>7.3f} {'–':>8} "
                f"{exp.ece:>8.4f} {exp.brier:>8.4f} "
                f"{exp.sb_correctness_corr:>+8.4f} {'–':<10}"
            )

        if en is not None and bl is not None:
            exp_e = en.experiment_result
            exp_b = bl.experiment_result
            delta_pass = exp_e.pass_at_1 - exp_b.pass_at_1

            verdict_obj = evaluate_energy_stop_conditions(exp_b, exp_e)
            verdict_str = "PASS" if verdict_obj.should_continue else "FAIL"

            lines.append(
                f"{'bayesian':<12} {alpha:>5.2f} {energy_beta:>5.2f} "
                f"{uncertainty_mode:<12} "
                f"{exp_e.pass_at_1:>7.3f} {delta_pass:>+8.4f} "
                f"{exp_e.ece:>8.4f} {exp_e.brier:>8.4f} "
                f"{exp_e.sb_correctness_corr:>+8.4f} {verdict_str:<10}"
            )

            # Print stop-condition reasons
            for reason in verdict_obj.reasons:
                lines.append(f"    {reason}")

        lines.append("")

    lines.append(sep)

    table = "\n".join(lines)
    print(table)
    return table


def print_extended_summary(
    results: List[BenchmarkResult],
) -> str:
    """
    Extended summary that includes benchmark metadata and bootstrap CIs.

    This is a standalone function that wraps the existing
    ExperimentRunner.print_summary() and adds benchmark-specific rows.
    """
    # First print the standard experiment summary
    experiment_results = [r.experiment_result for r in results]
    base_table = ExperimentRunner.print_summary(experiment_results)

    lines = [base_table]
    lines.append("")
    lines.append("Benchmark-specific results with 95% bootstrap CIs:")
    lines.append("-" * 90)
    lines.append(
        f"  {'Dataset':<16} {'Goal':<18} {'Δpass@1':>10} "
        f"{'95% CI':>24} {'sb_rho':>8} {'95% CI':>24} {'Verdict':<12}"
    )
    lines.append("-" * 90)

    for r in results:
        delta_str = ""
        delta_ci_str = ""
        if r.pass_at_1_delta_ci is not None:
            delta_str = f"{r.pass_at_1_delta_ci.mean:>+10.4f}"
            delta_ci_str = (
                f"[{r.pass_at_1_delta_ci.lower:+.4f}, "
                f"{r.pass_at_1_delta_ci.upper:+.4f}]"
            )

        sb_ci_str = ""
        if r.sb_rho_ci is not None:
            sb_ci_str = (
                f"[{r.sb_rho_ci.lower:+.4f}, "
                f"{r.sb_rho_ci.upper:+.4f}]"
            )

        lines.append(
            f"  {r.dataset_name:<16} {r.goal_strategy:<18} "
            f"{delta_str} {delta_ci_str:>24} "
            f"{r.sb_rho:>+8.4f} {sb_ci_str:>24} {r.verdict:<12}"
        )

    lines.append("-" * 90)
    table = "\n".join(lines)
    print(table)
    return table
