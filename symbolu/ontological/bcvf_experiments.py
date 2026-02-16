#!/usr/bin/env python3
"""
BCVF Experiment Runner & HumanEval Integration
================================================

Provides:

1.  **Ablation experiment matrix** – runs all 2³ = 8 combinations of
    (rerank, logit_mod, calibration) and collects per-step diagnostics.

2.  **Step-level logger** – records every decode step to answer:
    - Was the top token changed by reranking?
    - What was the Δ score between original and adjusted?
    - What were sf, sb for the selected token?
    - What confidence tier was assigned?
    - Was the prediction correct?

3.  **HumanEval-style evaluation loop** – generates code from a prompt,
    runs unit tests, and tracks pass@1 / pass@k with calibration.

4.  **Stop-condition evaluator** – checks the predefined go/no-go
    criteria after each experiment.

Usage::

    from symbolu.ontological.bcvf_experiments import (
        EXPERIMENT_MATRIX,
        ExperimentRunner,
        StepLogger,
    )

    runner = ExperimentRunner(model, tokenizer)
    results = runner.run_ablation(dataset)
    runner.print_summary(results)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

try:
    import torch

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

import numpy as np

from symbolu.ontological.bcvf_decoding import BCVFDecoder, DecodingConfig
from symbolu.ontological.bcvf_calibration import (
    CalibrationTracker,
    compute_ece,
    compute_brier,
)


# =========================================================================
# Experiment Matrix
# =========================================================================

EXPERIMENT_MATRIX: List[Dict[str, bool]] = [
    # Baseline – vanilla softmax
    {"use_rerank": False, "use_logit_mod": False, "use_calibration": False},
    # B only – calibration observation
    {"use_rerank": False, "use_logit_mod": False, "use_calibration": True},
    # C only – reranking
    {"use_rerank": True, "use_logit_mod": False, "use_calibration": False},
    # C + B
    {"use_rerank": True, "use_logit_mod": False, "use_calibration": True},
    # A only – logit modulation
    {"use_rerank": False, "use_logit_mod": True, "use_calibration": False},
    # A + B
    {"use_rerank": False, "use_logit_mod": True, "use_calibration": True},
    # A + C
    {"use_rerank": True, "use_logit_mod": True, "use_calibration": False},
    # A + B + C – full pipeline
    {"use_rerank": True, "use_logit_mod": True, "use_calibration": True},
]


def config_label(flags: Dict[str, bool]) -> str:
    """Human-readable label for an experiment configuration."""
    parts = []
    if flags.get("use_logit_mod"):
        parts.append("A")
    if flags.get("use_calibration"):
        parts.append("B")
    if flags.get("use_rerank"):
        parts.append("C")
    return "+".join(parts) if parts else "baseline"


# =========================================================================
# Step-Level Logger
# =========================================================================


@dataclass
class StepRecord:
    """Diagnostic record for a single decode step."""

    step_index: int
    predicted_token: int
    ground_truth_token: Optional[int] = None
    correct: Optional[bool] = None
    # BCVF scores for the selected token
    sf_selected: float = 0.0
    sb_selected: float = 0.0
    lagrangian_selected: float = 0.0
    # Rerank diagnostics
    rerank_changed: bool = False
    original_top_token: Optional[int] = None
    delta_score: float = 0.0  # adjusted − original for the selected
    # Calibration
    confidence: float = 0.0
    margin: float = 0.0
    confidence_level: str = ""


class StepLogger:
    """
    Accumulates :class:`StepRecord` entries for one generation run.

    Provides aggregate statistics to determine if BCVF is providing
    meaningful signal.
    """

    def __init__(self) -> None:
        self.records: List[StepRecord] = []

    def log(self, record: StepRecord) -> None:
        self.records.append(record)

    @staticmethod
    def from_decode_log(
        step_index: int,
        log_data: Dict[str, Any],
        predicted_token: int,
        ground_truth_token: Optional[int] = None,
    ) -> StepRecord:
        """
        Build a :class:`StepRecord` from the ``log_data`` dict returned
        by :meth:`BCVFDecoder.decode_step`.
        """
        # Extract sf/sb for the selected token
        sf_sel = 0.0
        sb_sel = 0.0
        L_sel = 0.0
        if PYTORCH_AVAILABLE and "sf" in log_data and "topM_indices" in log_data:
            topM_indices = log_data["topM_indices"]  # [B, M]
            sf_all = log_data["sf"]  # [B, M]
            sb_all = log_data["sb"]
            L_all = log_data["L"]
            # Find the relative index of the predicted token in topM
            match = (topM_indices[0] == predicted_token).nonzero(as_tuple=True)
            if len(match[0]) > 0:
                rel = match[0][0].item()
                sf_sel = float(sf_all[0, rel].item())
                sb_sel = float(sb_all[0, rel].item())
                L_sel = float(L_all[0, rel].item())

        rerank_changed = False
        original_top = None
        delta = 0.0
        if "rerank_changed" in log_data:
            rc = log_data["rerank_changed"]
            rerank_changed = bool(rc.item()) if PYTORCH_AVAILABLE else bool(rc)
        if "original_top_token" in log_data:
            ot = log_data["original_top_token"]
            original_top = int(ot.item()) if PYTORCH_AVAILABLE else int(ot)

        conf = 0.0
        margin = 0.0
        level = ""
        if "confidence" in log_data:
            c = log_data["confidence"]
            conf = float(c[0].item()) if PYTORCH_AVAILABLE else float(c)
        if "margin" in log_data:
            m = log_data["margin"]
            margin = float(m[0].item()) if PYTORCH_AVAILABLE else float(m)
        if "confidence_level" in log_data:
            levels = log_data["confidence_level"]
            level = levels[0] if isinstance(levels, list) else str(levels)

        correct = None
        if ground_truth_token is not None:
            correct = predicted_token == ground_truth_token

        return StepRecord(
            step_index=step_index,
            predicted_token=predicted_token,
            ground_truth_token=ground_truth_token,
            correct=correct,
            sf_selected=sf_sel,
            sb_selected=sb_sel,
            lagrangian_selected=L_sel,
            rerank_changed=rerank_changed,
            original_top_token=original_top,
            delta_score=delta,
            confidence=conf,
            margin=margin,
            confidence_level=level,
        )

    # ------------------------------------------------------------------
    # Aggregate statistics
    # ------------------------------------------------------------------

    def rerank_change_rate(self) -> float:
        """Fraction of steps where reranking changed the top token."""
        if not self.records:
            return 0.0
        changed = sum(1 for r in self.records if r.rerank_changed)
        return changed / len(self.records)

    def rerank_improvement_rate(self) -> float:
        """
        Among steps where rerank changed the token *and* ground truth
        is available, fraction where the new token was correct.
        """
        changed = [
            r for r in self.records
            if r.rerank_changed and r.correct is not None
        ]
        if not changed:
            return 0.0
        return sum(1 for r in changed if r.correct) / len(changed)

    def accuracy(self) -> float:
        scored = [r for r in self.records if r.correct is not None]
        if not scored:
            return 0.0
        return sum(1 for r in scored if r.correct) / len(scored)

    def mean_sf(self) -> float:
        if not self.records:
            return 0.0
        return float(np.mean([r.sf_selected for r in self.records]))

    def mean_sb(self) -> float:
        if not self.records:
            return 0.0
        return float(np.mean([r.sb_selected for r in self.records]))

    def summary(self) -> Dict[str, float]:
        return {
            "n_steps": len(self.records),
            "accuracy": self.accuracy(),
            "rerank_change_rate": self.rerank_change_rate(),
            "rerank_improvement_rate": self.rerank_improvement_rate(),
            "mean_sf": self.mean_sf(),
            "mean_sb": self.mean_sb(),
        }


# =========================================================================
# HumanEval Integration
# =========================================================================


@dataclass
class HumanEvalSample:
    """One HumanEval-style problem."""

    task_id: str
    prompt: str
    canonical_solution: str
    test_code: str
    entry_point: str


@dataclass
class HumanEvalResult:
    """Result for a single HumanEval problem under one config."""

    task_id: str
    config_label: str
    generated_code: str
    passed: bool
    confidence: float
    confidence_level: str
    rerank_changed_any: bool
    sf_mean: float
    sb_mean: float


def load_humaneval(path: Optional[str] = None) -> List[HumanEvalSample]:
    """
    Load HumanEval problems from a JSONL file.

    If ``path`` is None, attempts to use the ``human_eval`` package
    (``pip install human-eval``), falling back to a JSONL on disk.

    Returns:
        List of HumanEvalSample.
    """
    samples: List[HumanEvalSample] = []

    if path is not None:
        p = Path(path)
        if p.exists():
            with open(p) as f:
                for line in f:
                    obj = json.loads(line)
                    samples.append(
                        HumanEvalSample(
                            task_id=obj["task_id"],
                            prompt=obj["prompt"],
                            canonical_solution=obj.get("canonical_solution", ""),
                            test_code=obj.get("test", ""),
                            entry_point=obj.get("entry_point", ""),
                        )
                    )
            return samples

    # Try HuggingFace datasets
    try:
        from datasets import load_dataset  # type: ignore[import-untyped]

        ds = load_dataset("openai_humaneval", split="test")
        for item in ds:
            samples.append(
                HumanEvalSample(
                    task_id=item["task_id"],
                    prompt=item["prompt"],
                    canonical_solution=item.get("canonical_solution", ""),
                    test_code=item.get("test", ""),
                    entry_point=item.get("entry_point", ""),
                )
            )
    except Exception:
        pass

    return samples


def run_unit_tests(code: str, test_code: str, entry_point: str) -> bool:
    """
    Execute generated code + test harness in a sandboxed ``exec``.

    Returns True if all tests pass, False otherwise.

    WARNING: This uses ``exec()`` and should only be run on trusted /
    generated code in an isolated environment.
    """
    full_code = code + "\n" + test_code + f"\ncheck({entry_point})\n"
    try:
        exec_globals: Dict[str, Any] = {}
        exec(full_code, exec_globals)  # noqa: S102
        return True
    except Exception:
        return False


# =========================================================================
# Experiment Runner
# =========================================================================


@dataclass
class ExperimentResult:
    """Aggregated results for one experiment configuration."""

    label: str
    flags: Dict[str, bool]
    # Accuracy metrics
    pass_at_1: float = 0.0
    total_samples: int = 0
    correct_count: int = 0
    # Calibration
    ece: float = 0.0
    brier: float = 0.0
    # Rerank diagnostics
    rerank_change_pct: float = 0.0
    rerank_improved_pct: float = 0.0
    # BCVF signal
    mean_sf: float = 0.0
    mean_sb: float = 0.0
    # Confidence tiers
    tier_accuracy: Dict[str, float] = field(default_factory=dict)
    tier_distribution: Dict[str, float] = field(default_factory=dict)
    # Low-confidence abstention stats
    low_conf_pct: float = 0.0
    low_conf_accuracy: float = 0.0
    # Raw
    per_sample: List[Dict[str, Any]] = field(default_factory=list)


class ExperimentRunner:
    """
    Runs the full ablation matrix over a dataset and collects
    diagnostics for every configuration.

    This is the main entry point for benchmarking the BCVF decoding
    pipeline.  It supports both next-token-prediction datasets (where
    ground truth is a single token) and code-generation (HumanEval)
    style tasks.

    Args:
        model: A transformer model with ``.get_input_embeddings()`` and
               a forward method returning hidden states / logits.
        tokenizer: Corresponding tokenizer.
        base_config: Base :class:`DecodingConfig` whose non-ablated
                     fields (top_m, beta, lambdas) are used for all
                     experiments.
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

    # ------------------------------------------------------------------
    def _make_config(self, flags: Dict[str, bool]) -> DecodingConfig:
        """Create a DecodingConfig by overlaying ablation flags."""
        cfg = DecodingConfig(
            top_m=self.base_config.top_m,
            lambda_f=self.base_config.lambda_f,
            lambda_b=self.base_config.lambda_b,
            lambda_c=self.base_config.lambda_c,
            beta=self.base_config.beta,
            conf_high=self.base_config.conf_high,
            conf_med=self.base_config.conf_med,
            margin_low=self.base_config.margin_low,
            use_rerank=flags.get("use_rerank", False),
            use_logit_mod=flags.get("use_logit_mod", False),
            use_calibration=flags.get("use_calibration", False),
        )
        return cfg

    # ------------------------------------------------------------------
    def run_single_experiment(
        self,
        flags: Dict[str, bool],
        dataset: Sequence[Dict[str, Any]],
        goal_embed_fn: Optional[Callable] = None,
    ) -> ExperimentResult:
        """
        Run one experiment configuration over the full dataset.

        Each element of ``dataset`` should be a dict with at least:
            - ``hidden_state``:  [1, D] tensor or callable to produce it
            - ``ground_truth``:  int token id (optional)
            - ``logits``:        [1, V] tensor (optional)
            - ``prompt``:        str (optional, for goal embedding)

        Args:
            flags: Ablation flags dict.
            dataset: Sequence of sample dicts.
            goal_embed_fn: Optional callable(prompt_str) -> [1, D] tensor.

        Returns:
            ExperimentResult with all metrics.
        """
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch is required")

        label = config_label(flags)
        cfg = self._make_config(flags)
        decoder = BCVFDecoder(cfg)

        tracker = CalibrationTracker()
        step_logger = StepLogger()
        per_sample: List[Dict[str, Any]] = []

        vocab_emb = None
        if self.model is not None:
            vocab_emb = self.model.get_input_embeddings().weight.detach()

        for i, sample in enumerate(dataset):
            hidden = sample["hidden_state"]
            if callable(hidden):
                hidden = hidden()
            if not isinstance(hidden, torch.Tensor):
                hidden = torch.tensor(hidden, dtype=torch.float32)
            hidden = hidden.to(self.device)

            # Goal embedding
            if "goal_embedding" in sample:
                goal = sample["goal_embedding"]
                if not isinstance(goal, torch.Tensor):
                    goal = torch.tensor(goal, dtype=torch.float32)
            elif goal_embed_fn is not None and "prompt" in sample:
                goal = goal_embed_fn(sample["prompt"])
            else:
                goal = hidden.clone()
            goal = goal.to(self.device)

            logits = sample.get("logits")
            if logits is not None:
                if not isinstance(logits, torch.Tensor):
                    logits = torch.tensor(logits, dtype=torch.float32)
                logits = logits.to(self.device)

            if vocab_emb is None:
                D = hidden.shape[-1]
                V = logits.shape[-1] if logits is not None else 1000
                vocab_emb = torch.randn(V, D, device=self.device)

            best_idx, probs, log_data = decoder.decode_step(
                hidden, vocab_emb, goal, logits
            )

            pred_token = int(best_idx[0].item())
            gt = sample.get("ground_truth")

            record = StepLogger.from_decode_log(
                step_index=i,
                log_data=log_data,
                predicted_token=pred_token,
                ground_truth_token=gt,
            )
            step_logger.log(record)

            correct = record.correct
            conf = record.confidence
            level = record.confidence_level

            if correct is not None:
                tracker.update(
                    confidence=conf,
                    correct=correct,
                    confidence_level=level if level else None,
                )

            per_sample.append({
                "index": i,
                "predicted": pred_token,
                "ground_truth": gt,
                "correct": correct,
                "confidence": conf,
                "confidence_level": level,
                "rerank_changed": record.rerank_changed,
                "sf": record.sf_selected,
                "sb": record.sb_selected,
            })

        # Aggregate
        cal_report = tracker.report()
        step_summary = step_logger.summary()

        return ExperimentResult(
            label=label,
            flags=flags,
            pass_at_1=cal_report["accuracy"],
            total_samples=cal_report["n"],
            correct_count=int(cal_report["accuracy"] * cal_report["n"]),
            ece=cal_report["ece"],
            brier=cal_report["brier"],
            rerank_change_pct=step_summary["rerank_change_rate"],
            rerank_improved_pct=step_summary["rerank_improvement_rate"],
            mean_sf=step_summary["mean_sf"],
            mean_sb=step_summary["mean_sb"],
            tier_accuracy=cal_report["tier_accuracy"],
            tier_distribution=cal_report["tier_distribution"],
            low_conf_pct=cal_report["tier_distribution"].get("LOW", 0.0),
            low_conf_accuracy=cal_report["tier_accuracy"].get("LOW", 0.0),
            per_sample=per_sample,
        )

    # ------------------------------------------------------------------
    def run_ablation(
        self,
        dataset: Sequence[Dict[str, Any]],
        goal_embed_fn: Optional[Callable] = None,
        matrix: Optional[List[Dict[str, bool]]] = None,
    ) -> List[ExperimentResult]:
        """
        Run the full ablation matrix.

        Args:
            dataset: Evaluation samples.
            goal_embed_fn: Optional goal embedding function.
            matrix: Custom experiment matrix (defaults to EXPERIMENT_MATRIX).

        Returns:
            List of ExperimentResult, one per configuration.
        """
        matrix = matrix or EXPERIMENT_MATRIX
        results: List[ExperimentResult] = []
        for flags in matrix:
            result = self.run_single_experiment(flags, dataset, goal_embed_fn)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    def run_humaneval(
        self,
        problems: List[HumanEvalSample],
        generate_fn: Callable[
            [str, BCVFDecoder], Tuple[str, List[Dict[str, Any]]]
        ],
        matrix: Optional[List[Dict[str, bool]]] = None,
    ) -> List[ExperimentResult]:
        """
        Run HumanEval-style evaluation.

        ``generate_fn(prompt, decoder)`` should return
        ``(generated_code, list_of_step_log_dicts)``.

        Args:
            problems: List of HumanEvalSample.
            generate_fn: Code generation function.
            matrix: Experiment configurations.

        Returns:
            List of ExperimentResult.
        """
        matrix = matrix or EXPERIMENT_MATRIX
        all_results: List[ExperimentResult] = []

        for flags in matrix:
            label = config_label(flags)
            cfg = self._make_config(flags)
            decoder = BCVFDecoder(cfg)
            tracker = CalibrationTracker()
            per_sample: List[Dict[str, Any]] = []
            rerank_changed_count = 0
            total_steps = 0
            sf_sum = 0.0
            sb_sum = 0.0

            for problem in problems:
                code, step_logs = generate_fn(problem.prompt, decoder)
                passed = run_unit_tests(
                    code, problem.test_code, problem.entry_point
                )

                # Aggregate step-level stats
                any_changed = False
                step_sfs: List[float] = []
                step_sbs: List[float] = []
                for sl in step_logs:
                    if sl.get("rerank_changed"):
                        any_changed = True
                        rerank_changed_count += 1
                    total_steps += 1
                    step_sfs.append(sl.get("sf", 0.0))
                    step_sbs.append(sl.get("sb", 0.0))

                avg_conf = float(np.mean([
                    sl.get("confidence", 0.0) for sl in step_logs
                ])) if step_logs else 0.0
                conf_level = step_logs[-1].get(
                    "confidence_level", ""
                ) if step_logs else ""

                tracker.update(
                    confidence=avg_conf,
                    correct=passed,
                    confidence_level=conf_level if conf_level else None,
                )

                mean_sf = float(np.mean(step_sfs)) if step_sfs else 0.0
                mean_sb = float(np.mean(step_sbs)) if step_sbs else 0.0
                sf_sum += mean_sf
                sb_sum += mean_sb

                per_sample.append({
                    "task_id": problem.task_id,
                    "passed": passed,
                    "confidence": avg_conf,
                    "confidence_level": conf_level,
                    "rerank_changed_any": any_changed,
                    "sf_mean": mean_sf,
                    "sb_mean": mean_sb,
                })

            cal_report = tracker.report()
            n = len(problems)

            all_results.append(
                ExperimentResult(
                    label=label,
                    flags=flags,
                    pass_at_1=cal_report["accuracy"],
                    total_samples=n,
                    correct_count=int(cal_report["accuracy"] * n),
                    ece=cal_report["ece"],
                    brier=cal_report["brier"],
                    rerank_change_pct=(
                        rerank_changed_count / total_steps
                        if total_steps > 0
                        else 0.0
                    ),
                    mean_sf=sf_sum / n if n > 0 else 0.0,
                    mean_sb=sb_sum / n if n > 0 else 0.0,
                    tier_accuracy=cal_report["tier_accuracy"],
                    tier_distribution=cal_report["tier_distribution"],
                    low_conf_pct=cal_report["tier_distribution"].get("LOW", 0.0),
                    low_conf_accuracy=cal_report["tier_accuracy"].get("LOW", 0.0),
                    per_sample=per_sample,
                )
            )

        return all_results

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @staticmethod
    def print_summary(results: List[ExperimentResult]) -> str:
        """
        Format a comparison table across all experiment configs.

        Returns the table as a string (also prints it).
        """
        header = (
            f"{'Config':<12} {'pass@1':>7} {'ECE':>7} {'Brier':>7} "
            f"{'Rerank%':>8} {'sf':>6} {'sb':>6} "
            f"{'H-acc':>6} {'M-acc':>6} {'L-acc':>6}"
        )
        sep = "-" * len(header)
        lines = [sep, header, sep]

        for r in results:
            h_acc = r.tier_accuracy.get("HIGH", 0.0)
            m_acc = r.tier_accuracy.get("MEDIUM", 0.0)
            l_acc = r.tier_accuracy.get("LOW", 0.0)
            line = (
                f"{r.label:<12} {r.pass_at_1:>7.3f} {r.ece:>7.4f} "
                f"{r.brier:>7.4f} {r.rerank_change_pct:>7.1%} "
                f"{r.mean_sf:>6.3f} {r.mean_sb:>6.3f} "
                f"{h_acc:>6.3f} {m_acc:>6.3f} {l_acc:>6.3f}"
            )
            lines.append(line)

        lines.append(sep)
        table = "\n".join(lines)
        print(table)
        return table

    @staticmethod
    def save_results(
        results: List[ExperimentResult],
        path: str = "bcvf_experiment_results.json",
    ) -> None:
        """Save results to JSON for later analysis."""
        data = []
        for r in results:
            d = {
                "label": r.label,
                "flags": r.flags,
                "pass_at_1": r.pass_at_1,
                "total_samples": r.total_samples,
                "correct_count": r.correct_count,
                "ece": r.ece,
                "brier": r.brier,
                "rerank_change_pct": r.rerank_change_pct,
                "rerank_improved_pct": r.rerank_improved_pct,
                "mean_sf": r.mean_sf,
                "mean_sb": r.mean_sb,
                "tier_accuracy": r.tier_accuracy,
                "tier_distribution": r.tier_distribution,
                "low_conf_pct": r.low_conf_pct,
                "low_conf_accuracy": r.low_conf_accuracy,
            }
            data.append(d)

        with open(path, "w") as f:
            json.dump(data, f, indent=2)


# =========================================================================
# Stop-Condition Evaluator
# =========================================================================


@dataclass
class GoNoGoVerdict:
    """Result of stop-condition evaluation."""

    should_continue: bool
    reasons: List[str]


def evaluate_stop_conditions(
    baseline: ExperimentResult,
    best_bcvf: ExperimentResult,
    beta: float = 0.2,
) -> GoNoGoVerdict:
    """
    Check the predefined stop/go criteria.

    Stop pursuing BCVF if:
        - pass@1 drops at β ≤ 0.3
        - Reranking changes < 2% of tokens
        - Calibration tiers do not correlate with correctness
        - Gains < 1-2% on real tasks

    Continue if:
        - Calibration improves significantly
        - pass@1 increases
        - Wrong answers have lower confidence
        - Drift decreases in long generation

    Args:
        baseline: Results from the baseline (no BCVF) experiment.
        best_bcvf: Results from the best BCVF experiment.
        beta: Current β value.

    Returns:
        GoNoGoVerdict indicating whether to continue.
    """
    reasons: List[str] = []
    should_continue = True

    # 1. pass@1 regression check
    delta_pass = best_bcvf.pass_at_1 - baseline.pass_at_1
    if delta_pass < -0.001 and beta <= 0.3:
        reasons.append(
            f"STOP: pass@1 dropped by {delta_pass:.3f} at β={beta}"
        )
        should_continue = False

    # 2. Rerank signal check
    if best_bcvf.rerank_change_pct < 0.02:
        reasons.append(
            f"STOP: Reranking only changes {best_bcvf.rerank_change_pct:.1%} "
            f"of tokens (< 2% threshold)"
        )
        should_continue = False

    # 3. Calibration tier correlation
    tier_acc = best_bcvf.tier_accuracy
    h_acc = tier_acc.get("HIGH", 0.0)
    l_acc = tier_acc.get("LOW", 0.0)
    if h_acc > 0 and l_acc > 0 and h_acc <= l_acc:
        reasons.append(
            f"STOP: Calibration tiers not meaningful "
            f"(HIGH acc={h_acc:.3f} <= LOW acc={l_acc:.3f})"
        )
        should_continue = False

    # 4. Minimal gain check
    if 0.0 <= delta_pass < 0.01:
        reasons.append(
            f"WARNING: Gain is only {delta_pass:.3f} (<1% threshold)"
        )
        # Not a hard stop, but a warning

    # Positive signals
    if delta_pass >= 0.01:
        reasons.append(f"GO: pass@1 improved by {delta_pass:.3f}")
    if best_bcvf.ece < baseline.ece * 0.9:
        reasons.append(
            f"GO: ECE improved from {baseline.ece:.4f} to {best_bcvf.ece:.4f}"
        )
    if h_acc > l_acc + 0.1:
        reasons.append(
            f"GO: Calibration meaningful (HIGH={h_acc:.3f} > LOW={l_acc:.3f})"
        )

    return GoNoGoVerdict(should_continue=should_continue, reasons=reasons)
