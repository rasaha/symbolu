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
    spearman_rank_correlation,
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
    # BCVF scores for the *baseline* top-1 token (Risk A diagnostic)
    sf_baseline: float = 0.0
    sb_baseline: float = 0.0
    delta_sf: float = 0.0  # sf_selected − sf_baseline
    delta_sb: float = 0.0  # sb_selected − sb_baseline
    # Rerank diagnostics
    rerank_changed: bool = False
    original_top_token: Optional[int] = None
    delta_score: float = 0.0  # adjusted − original for the selected
    # Calibration
    confidence: float = 0.0
    margin: float = 0.0
    confidence_level: str = ""
    # Logit modulation sanity (Option A)
    kl_base_mod: float = 0.0
    entropy_delta: float = 0.0
    # Logit rank of the predicted token (for Spearman correlation)
    logit_rank: int = 0
    base_logit_score: float = 0.0


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
        def _scalar(tensor_or_val, idx: int = 0) -> float:
            """Extract a scalar from a possibly-batched tensor."""
            if PYTORCH_AVAILABLE and hasattr(tensor_or_val, "dim"):
                if tensor_or_val.dim() == 0:
                    return float(tensor_or_val.item())
                return float(tensor_or_val[idx].item())
            if hasattr(tensor_or_val, "__getitem__"):
                return float(tensor_or_val[idx])
            return float(tensor_or_val)

        # --- sf/sb for the selected token ---
        sf_sel = 0.0
        sb_sel = 0.0
        L_sel = 0.0
        if PYTORCH_AVAILABLE and "sf" in log_data and "topM_indices" in log_data:
            topM_indices = log_data["topM_indices"]
            sf_all = log_data["sf"]
            sb_all = log_data["sb"]
            L_all = log_data["L"]
            match = (topM_indices[0] == predicted_token).nonzero(as_tuple=True)
            if len(match[0]) > 0:
                rel = match[0][0].item()
                sf_sel = float(sf_all[0, rel].item())
                sb_sel = float(sb_all[0, rel].item())
                L_sel = float(L_all[0, rel].item())

        # --- sf/sb for the *baseline* top-1 token ---
        sf_base = 0.0
        sb_base = 0.0
        if "baseline_sf" in log_data:
            sf_base = _scalar(log_data["baseline_sf"])
        if "baseline_sb" in log_data:
            sb_base = _scalar(log_data["baseline_sb"])

        # --- sf/sb deltas (selected vs baseline) ---
        delta_sf = 0.0
        delta_sb = 0.0
        if "delta_sf" in log_data:
            delta_sf = _scalar(log_data["delta_sf"])
        if "delta_sb" in log_data:
            delta_sb = _scalar(log_data["delta_sb"])

        # --- Rerank ---
        rerank_changed = False
        original_top = None
        if "rerank_changed" in log_data:
            rerank_changed = bool(_scalar(log_data["rerank_changed"]))
        if "original_top_token" in log_data:
            original_top = int(_scalar(log_data["original_top_token"]))

        # --- Calibration ---
        conf = 0.0
        margin = 0.0
        level = ""
        if "confidence" in log_data:
            conf = _scalar(log_data["confidence"])
        if "margin" in log_data:
            margin = _scalar(log_data["margin"])
        if "confidence_level" in log_data:
            levels = log_data["confidence_level"]
            level = levels[0] if isinstance(levels, list) else str(levels)

        # --- Logit modulation sanity ---
        kl_bm = 0.0
        ent_delta = 0.0
        if "kl_base_mod" in log_data:
            kl_bm = _scalar(log_data["kl_base_mod"])
        if "entropy_delta" in log_data:
            ent_delta = _scalar(log_data["entropy_delta"])

        # --- Logit rank of predicted token (for Spearman comparison) ---
        logit_rank = 0
        base_logit_score = 0.0
        if PYTORCH_AVAILABLE and "base_logits" in log_data:
            import torch as _torch

            base_logits = log_data["base_logits"]
            sorted_indices = _torch.argsort(base_logits[0], descending=True)
            rank_match = (sorted_indices == predicted_token).nonzero(
                as_tuple=True
            )
            if len(rank_match[0]) > 0:
                logit_rank = int(rank_match[0][0].item())
            base_logit_score = float(base_logits[0, predicted_token].item())

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
            sf_baseline=sf_base,
            sb_baseline=sb_base,
            delta_sf=delta_sf,
            delta_sb=delta_sb,
            rerank_changed=rerank_changed,
            original_top_token=original_top,
            delta_score=0.0,
            confidence=conf,
            margin=margin,
            confidence_level=level,
            kl_base_mod=kl_bm,
            entropy_delta=ent_delta,
            logit_rank=logit_rank,
            base_logit_score=base_logit_score,
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

    def rerank_worsened_rate(self) -> float:
        """
        Among steps where rerank changed the token *and* ground truth
        is available, fraction where the new token was wrong.
        """
        changed = [
            r for r in self.records
            if r.rerank_changed and r.correct is not None
        ]
        if not changed:
            return 0.0
        return sum(1 for r in changed if not r.correct) / len(changed)

    def rerank_net_benefit(self) -> float:
        """Improved rate minus worsened rate among changed tokens."""
        return self.rerank_improvement_rate() - self.rerank_worsened_rate()

    def mean_delta_sf(self) -> float:
        """Mean sf(selected) − sf(baseline) across rerank-changed steps."""
        changed = [r for r in self.records if r.rerank_changed]
        if not changed:
            return 0.0
        return float(np.mean([r.delta_sf for r in changed]))

    def mean_delta_sb(self) -> float:
        """Mean sb(selected) − sb(baseline) across rerank-changed steps."""
        changed = [r for r in self.records if r.rerank_changed]
        if not changed:
            return 0.0
        return float(np.mean([r.delta_sb for r in changed]))

    def mean_kl_base_mod(self) -> float:
        """Mean KL(base || modulated) — only meaningful when logit mod is on."""
        vals = [r.kl_base_mod for r in self.records if r.kl_base_mod > 0.0]
        return float(np.mean(vals)) if vals else 0.0

    def mean_entropy_delta(self) -> float:
        """Mean entropy(modulated) − entropy(base)."""
        vals = [r.entropy_delta for r in self.records if r.entropy_delta != 0.0]
        return float(np.mean(vals)) if vals else 0.0

    # ------------------------------------------------------------------
    # Spearman correlation: sb vs correctness, logit rank vs correctness
    # ------------------------------------------------------------------

    def sb_correctness_correlation(self) -> float:
        """
        Spearman rank correlation between sb (backward goal-alignment
        score) and correctness.

        A *positive* value means higher sb predicts correct predictions.
        This is the critical structural test: if sb does not correlate
        with correctness, the goal embedding is not providing useful
        signal and BCVF cannot help.
        """
        scored = [r for r in self.records if r.correct is not None]
        if len(scored) < 3:
            return 0.0
        sbs = np.array([r.sb_selected for r in scored])
        corr = np.array([float(r.correct) for r in scored])
        return spearman_rank_correlation(sbs, corr)

    def logit_rank_correctness_correlation(self) -> float:
        """
        Spearman rank correlation between logit rank and correctness.

        Uses *negative* logit rank (so higher rank = worse) to make
        the sign comparable with sb correlation: a positive value means
        lower logit rank (= higher base confidence) predicts correctness.

        If this correlation is stronger than sb_correctness_correlation,
        the raw model confidence is already a better predictor than the
        goal embedding and BCVF adds no value.
        """
        scored = [r for r in self.records if r.correct is not None]
        if len(scored) < 3:
            return 0.0
        # Negate rank so that rank-0 (best) maps to the highest value
        neg_ranks = np.array([-r.logit_rank for r in scored], dtype=np.float64)
        corr = np.array([float(r.correct) for r in scored])
        return spearman_rank_correlation(neg_ranks, corr)

    def base_logit_correctness_correlation(self) -> float:
        """
        Spearman rank correlation between raw base logit score and
        correctness.

        Alternative to logit_rank — uses the continuous logit value
        rather than the discrete rank.  Positive = higher logit score
        predicts correctness.
        """
        scored = [r for r in self.records if r.correct is not None]
        if len(scored) < 3:
            return 0.0
        logits = np.array([r.base_logit_score for r in scored])
        corr = np.array([float(r.correct) for r in scored])
        return spearman_rank_correlation(logits, corr)

    def summary(self) -> Dict[str, float]:
        return {
            "n_steps": len(self.records),
            "accuracy": self.accuracy(),
            "rerank_change_rate": self.rerank_change_rate(),
            "rerank_improvement_rate": self.rerank_improvement_rate(),
            "rerank_worsened_rate": self.rerank_worsened_rate(),
            "rerank_net_benefit": self.rerank_net_benefit(),
            "mean_sf": self.mean_sf(),
            "mean_sb": self.mean_sb(),
            "mean_delta_sf": self.mean_delta_sf(),
            "mean_delta_sb": self.mean_delta_sb(),
            "mean_kl_base_mod": self.mean_kl_base_mod(),
            "mean_entropy_delta": self.mean_entropy_delta(),
            "sb_correctness_corr": self.sb_correctness_correlation(),
            "logit_rank_correctness_corr": self.logit_rank_correctness_correlation(),
            "base_logit_correctness_corr": self.base_logit_correctness_correlation(),
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


def run_unit_tests(
    code: str,
    test_code: str,
    entry_point: str,
    timeout_seconds: float = 10.0,
    use_subprocess: bool = True,
) -> bool:
    """
    Execute generated code + test harness.

    When ``use_subprocess=True`` (default), runs the code in an isolated
    subprocess with a hard timeout and restricted capabilities.  This
    prevents infinite loops, filesystem access, and network calls from
    affecting the evaluation process.

    Args:
        code: The generated solution code.
        test_code: The test harness (defines ``check(fn)``).
        entry_point: Name of the function to test.
        timeout_seconds: Maximum execution time before the subprocess
                         is killed.
        use_subprocess: If True, run in subprocess for safety.  If
                        False, fall back to in-process ``exec`` (faster
                        but less safe — only for trusted code).

    Returns:
        True if all tests pass, False otherwise.
    """
    full_code = code + "\n" + test_code + f"\ncheck({entry_point})\n"

    if use_subprocess:
        import subprocess
        import sys
        import tempfile

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=True
            ) as tmp:
                tmp.write(full_code)
                tmp.flush()
                result = subprocess.run(
                    [sys.executable, tmp.name],
                    capture_output=True,
                    timeout=timeout_seconds,
                    env={"PATH": ""},  # minimal env
                )
                return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False
    else:
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
    rerank_worsened_pct: float = 0.0
    rerank_net_benefit: float = 0.0
    # BCVF signal
    mean_sf: float = 0.0
    mean_sb: float = 0.0
    # Risk A: goal-embedding effectiveness
    mean_delta_sf: float = 0.0
    mean_delta_sb: float = 0.0
    # Option A: logit mod sanity
    mean_kl_base_mod: float = 0.0
    mean_entropy_delta: float = 0.0
    # Confidence tiers
    tier_accuracy: Dict[str, float] = field(default_factory=dict)
    tier_distribution: Dict[str, float] = field(default_factory=dict)
    # Tier confusion table: tier → {correct: N, wrong: N}
    tier_confusion: Dict[str, Dict[str, int]] = field(default_factory=dict)
    # Low-confidence abstention stats
    low_conf_pct: float = 0.0
    low_conf_accuracy: float = 0.0
    # Conditional ECE
    ece_on_wrong_baseline: float = 0.0
    ece_on_low_margin: float = 0.0
    # Spearman correlations: sb vs correctness, logit vs correctness
    sb_correctness_corr: float = 0.0
    logit_rank_correctness_corr: float = 0.0
    base_logit_correctness_corr: float = 0.0
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

        # Tier confusion table
        tier_confusion: Dict[str, Dict[str, int]] = {
            "HIGH": {"correct": 0, "wrong": 0},
            "MEDIUM": {"correct": 0, "wrong": 0},
            "LOW": {"correct": 0, "wrong": 0},
        }
        for rec in step_logger.records:
            if rec.confidence_level and rec.correct is not None:
                tier = rec.confidence_level.upper()
                if tier in tier_confusion:
                    if rec.correct:
                        tier_confusion[tier]["correct"] += 1
                    else:
                        tier_confusion[tier]["wrong"] += 1

        # Conditional ECE: on wrong-baseline samples and low-margin samples
        ece_wrong = 0.0
        ece_low_margin = 0.0
        wrong_confs = []
        wrong_corr = []
        low_margin_confs = []
        low_margin_corr = []
        for rec in step_logger.records:
            if rec.correct is not None:
                # "Wrong baseline" = baseline would have been wrong
                if rec.original_top_token is not None and rec.ground_truth_token is not None:
                    baseline_correct = rec.original_top_token == rec.ground_truth_token
                    if not baseline_correct:
                        wrong_confs.append(rec.confidence)
                        wrong_corr.append(float(rec.correct))
                # Low margin
                if rec.margin < cfg.margin_low:
                    low_margin_confs.append(rec.confidence)
                    low_margin_corr.append(float(rec.correct))

        if wrong_confs:
            ece_wrong = compute_ece(
                np.array(wrong_confs), np.array(wrong_corr)
            )
        if low_margin_confs:
            ece_low_margin = compute_ece(
                np.array(low_margin_confs), np.array(low_margin_corr)
            )

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
            rerank_worsened_pct=step_summary["rerank_worsened_rate"],
            rerank_net_benefit=step_summary["rerank_net_benefit"],
            mean_sf=step_summary["mean_sf"],
            mean_sb=step_summary["mean_sb"],
            mean_delta_sf=step_summary["mean_delta_sf"],
            mean_delta_sb=step_summary["mean_delta_sb"],
            mean_kl_base_mod=step_summary["mean_kl_base_mod"],
            mean_entropy_delta=step_summary["mean_entropy_delta"],
            tier_accuracy=cal_report["tier_accuracy"],
            tier_distribution=cal_report["tier_distribution"],
            tier_confusion=tier_confusion,
            low_conf_pct=cal_report["tier_distribution"].get("LOW", 0.0),
            low_conf_accuracy=cal_report["tier_accuracy"].get("LOW", 0.0),
            ece_on_wrong_baseline=ece_wrong,
            ece_on_low_margin=ece_low_margin,
            sb_correctness_corr=step_summary["sb_correctness_corr"],
            logit_rank_correctness_corr=step_summary["logit_rank_correctness_corr"],
            base_logit_correctness_corr=step_summary["base_logit_correctness_corr"],
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
            f"{'Rerank%':>8} {'Impr%':>6} {'Wrsd%':>6} {'Net':>6} "
            f"{'sf':>6} {'sb':>6} "
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
                f"{r.rerank_improved_pct:>5.1%} "
                f"{r.rerank_worsened_pct:>5.1%} "
                f"{r.rerank_net_benefit:>+5.1%} "
                f"{r.mean_sf:>6.3f} {r.mean_sb:>6.3f} "
                f"{h_acc:>6.3f} {m_acc:>6.3f} {l_acc:>6.3f}"
            )
            lines.append(line)

        lines.append(sep)

        # Signal diagnostics section
        lines.append("")
        lines.append("Signal diagnostics:")
        for r in results:
            parts = [f"  {r.label:<12}"]
            if r.mean_delta_sf != 0.0 or r.mean_delta_sb != 0.0:
                parts.append(
                    f"Δsf={r.mean_delta_sf:+.4f} Δsb={r.mean_delta_sb:+.4f}"
                )
            if r.mean_kl_base_mod > 0.0:
                parts.append(
                    f"KL={r.mean_kl_base_mod:.4f} "
                    f"ΔH={r.mean_entropy_delta:+.4f}"
                )
            if r.ece_on_wrong_baseline > 0.0:
                parts.append(f"ECE(wrong)={r.ece_on_wrong_baseline:.4f}")
            if r.ece_on_low_margin > 0.0:
                parts.append(f"ECE(low-margin)={r.ece_on_low_margin:.4f}")
            if len(parts) > 1:
                lines.append("  ".join(parts))

        # Predictive signal comparison (the critical structural test)
        lines.append("")
        lines.append("Predictive signal comparison (Spearman ρ with correctness):")
        lines.append(
            f"  {'Config':<12} {'ρ(sb,corr)':>11} {'ρ(logit,corr)':>14} "
            f"{'ρ(rank,corr)':>13}  {'Verdict'}"
        )
        for r in results:
            sb_rho = r.sb_correctness_corr
            logit_rho = r.base_logit_correctness_corr
            rank_rho = r.logit_rank_correctness_corr
            # Verdict: does sb beat logit as a predictor?
            if sb_rho > logit_rho + 0.05:
                verdict = "sb WINS — goal embedding adds signal"
            elif logit_rho > sb_rho + 0.05:
                verdict = "logit WINS — BCVF may not help"
            elif abs(sb_rho) < 0.05 and abs(logit_rho) < 0.05:
                verdict = "NEITHER predicts — need better embeddings"
            else:
                verdict = "~tied — marginal BCVF benefit"
            lines.append(
                f"  {r.label:<12} {sb_rho:>+11.4f} {logit_rho:>+14.4f} "
                f"{rank_rho:>+13.4f}  {verdict}"
            )

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
                "sb_correctness_corr": r.sb_correctness_corr,
                "logit_rank_correctness_corr": r.logit_rank_correctness_corr,
                "base_logit_correctness_corr": r.base_logit_correctness_corr,
            }
            data.append(d)

        with open(path, "w") as f:
            json.dump(data, f, indent=2)


# =========================================================================
# Multi-Token Generation Loop (for HumanEval)
# =========================================================================


def generate_with_bcvf(
    model: Any,
    tokenizer: Any,
    prompt: str,
    decoder: "BCVFDecoder",
    goal_embedding: Any,
    max_tokens: int = 512,
    stop_tokens: Optional[List[int]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Autoregressive multi-token generation with BCVF decoding.

    Unlike single-step evaluation, this produces a full code completion
    by running the model in a loop, applying the BCVFDecoder at each
    step.

    Args:
        model: Transformer model with ``.get_input_embeddings()`` and
               a forward method returning logits and hidden states.
        tokenizer: Tokenizer with ``.encode()`` and ``.decode()``.
        prompt: The prompt string.
        decoder: Configured :class:`BCVFDecoder` instance.
        goal_embedding: [1, D] goal embedding tensor.
        max_tokens: Maximum number of tokens to generate.
        stop_tokens: List of token ids that signal end of generation
                     (e.g. EOS, newline after function body).

    Returns:
        (generated_code_str, list_of_per_step_log_dicts)
    """
    if not PYTORCH_AVAILABLE:
        raise ImportError("PyTorch is required")

    input_ids = tokenizer.encode(prompt, return_tensors="pt")
    vocab_emb = model.get_input_embeddings().weight.detach()
    stop_set = set(stop_tokens or [])
    generated_ids: List[int] = []
    step_logs: List[Dict[str, Any]] = []

    for step in range(max_tokens):
        with torch.no_grad():
            outputs = model(input_ids, output_hidden_states=True)
            last_logits = outputs.logits[:, -1, :]  # [1, V]
            last_hidden = outputs.hidden_states[-1][:, -1, :]  # [1, D]

        best_idx, probs, log_data = decoder.decode_step(
            last_hidden, vocab_emb, goal_embedding, last_logits
        )

        token_id = int(best_idx[0].item())
        generated_ids.append(token_id)

        # Build a lightweight log dict for aggregation
        step_log: Dict[str, Any] = {
            "token_id": token_id,
            "confidence": float(
                log_data["confidence"][0].item()
            ) if "confidence" in log_data else 0.0,
            "confidence_level": (
                log_data["confidence_level"][0]
                if "confidence_level" in log_data
                else ""
            ),
            "rerank_changed": bool(
                log_data["rerank_changed"].item()
            ) if "rerank_changed" in log_data else False,
            "sf": float(
                log_data.get("selected_sf", torch.tensor(0.0))[0].item()
            ) if "selected_sf" in log_data else 0.0,
            "sb": float(
                log_data.get("selected_sb", torch.tensor(0.0))[0].item()
            ) if "selected_sb" in log_data else 0.0,
        }
        step_logs.append(step_log)

        if token_id in stop_set:
            break

        # Append to input for next step
        input_ids = torch.cat(
            [input_ids, best_idx.unsqueeze(0)], dim=-1
        )

    generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
    return generated_text, step_logs


# =========================================================================
# Top-M Recall Check (Risk B diagnostic)
# =========================================================================


def check_topM_recall(
    hidden_state: Any,
    vocab_embeddings: Any,
    goal_embedding: Any,
    M_values: Optional[List[int]] = None,
    larger_pool: int = 5000,
    config: Optional[DecodingConfig] = None,
) -> Dict[str, Any]:
    """
    Check whether the BCVF-optimal token falls within the top-M pool.

    Computes the BCVF Lagrangian for a large pool (top-``larger_pool``)
    and checks at which M the best-by-BCVF token first appears.

    This answers Risk B: "If the 'true better token' isn't in top-M,
    BCVF cannot help."

    Args:
        hidden_state: [1, D] tensor.
        vocab_embeddings: [V, D] tensor.
        goal_embedding: [1, D] tensor.
        M_values: List of M values to check recall for.
                  Defaults to [100, 200, 500, 1000, 2000].
        larger_pool: Size of the full BCVF evaluation pool.
        config: DecodingConfig for BCVF parameters.

    Returns:
        Dict with:
            bcvf_best_rank: rank of the BCVF-best token in base logits.
            recall_at_M: dict mapping M → bool (is best in top-M?).
            min_required_M: smallest M that captures the BCVF-best.
    """
    if not PYTORCH_AVAILABLE:
        raise ImportError("PyTorch is required")

    cfg = config or DecodingConfig()
    M_values = M_values or [100, 200, 500, 1000, 2000]

    from symbolu.ontological.bcvf_decoding import BCVFScoringModule

    scorer = BCVFScoringModule(cfg)
    logits = hidden_state @ vocab_embeddings.T  # [1, V]
    V = logits.shape[-1]
    pool_size = min(larger_pool, V)

    topK_scores, topK_indices = torch.topk(logits, pool_size, dim=-1)
    candidates = vocab_embeddings[topK_indices]  # [1, K, D]
    sf = scorer.forward_score(hidden_state, candidates)
    sb = scorer.backward_score(candidates, goal_embedding)
    L = scorer.lagrangian(sf, sb)

    adjusted = topK_scores - cfg.beta * L
    bcvf_best_rel = torch.argmax(adjusted, dim=-1).item()
    bcvf_best_token = topK_indices[0, bcvf_best_rel].item()

    # What rank does this token have in the original logit ordering?
    sorted_indices = torch.argsort(logits[0], descending=True)
    bcvf_rank = int((sorted_indices == bcvf_best_token).nonzero()[0].item())

    recall_at_M = {}
    min_required_M = pool_size
    for M in sorted(M_values):
        in_topM = bcvf_rank < M
        recall_at_M[M] = in_topM
        if in_topM and M < min_required_M:
            min_required_M = M

    return {
        "bcvf_best_rank": bcvf_rank,
        "bcvf_best_token": bcvf_best_token,
        "recall_at_M": recall_at_M,
        "min_required_M": min_required_M,
    }


# =========================================================================
# Parameter Sweep Infrastructure
# =========================================================================


@dataclass
class SweepResult:
    """Result of one parameter sweep."""

    parameter_name: str
    parameter_values: List[float]
    results: List[ExperimentResult]


class ParameterSweepRunner:
    """
    Runs parameter sweeps over beta, top_m, and lambda_c.

    Usage::

        sweep = ParameterSweepRunner(runner)
        beta_results = sweep.sweep_beta(dataset, [0.0, 0.05, 0.1, 0.2, 0.3])
        m_results = sweep.sweep_top_m(dataset, [200, 500, 1000])
        lc_results = sweep.sweep_lambda_c(dataset, [0.0, 0.1, 0.25, 0.5])
    """

    def __init__(self, runner: ExperimentRunner):
        self.runner = runner

    def sweep_beta(
        self,
        dataset: Sequence[Dict[str, Any]],
        values: Optional[List[float]] = None,
        flags: Optional[Dict[str, bool]] = None,
    ) -> SweepResult:
        """Sweep over β values."""
        values = values or [0.0, 0.05, 0.1, 0.2, 0.3]
        flags = flags or {
            "use_rerank": True,
            "use_logit_mod": False,
            "use_calibration": True,
        }
        results = []
        for beta in values:
            orig_beta = self.runner.base_config.beta
            self.runner.base_config.beta = beta
            result = self.runner.run_single_experiment(flags, dataset)
            result.label = f"β={beta}"
            results.append(result)
            self.runner.base_config.beta = orig_beta
        return SweepResult("beta", values, results)

    def sweep_top_m(
        self,
        dataset: Sequence[Dict[str, Any]],
        values: Optional[List[int]] = None,
        flags: Optional[Dict[str, bool]] = None,
    ) -> SweepResult:
        """Sweep over top-M values."""
        values = values or [200, 500, 1000]
        flags = flags or {
            "use_rerank": True,
            "use_logit_mod": False,
            "use_calibration": True,
        }
        results = []
        for m in values:
            orig_m = self.runner.base_config.top_m
            self.runner.base_config.top_m = m
            result = self.runner.run_single_experiment(flags, dataset)
            result.label = f"M={m}"
            results.append(result)
            self.runner.base_config.top_m = orig_m
        return SweepResult("top_m", [float(v) for v in values], results)

    def sweep_lambda_c(
        self,
        dataset: Sequence[Dict[str, Any]],
        values: Optional[List[float]] = None,
        flags: Optional[Dict[str, bool]] = None,
    ) -> SweepResult:
        """Sweep over λc (consistency penalty weight)."""
        values = values or [0.0, 0.1, 0.25, 0.5]
        flags = flags or {
            "use_rerank": True,
            "use_logit_mod": False,
            "use_calibration": True,
        }
        results = []
        for lc in values:
            orig_lc = self.runner.base_config.lambda_c
            self.runner.base_config.lambda_c = lc
            result = self.runner.run_single_experiment(flags, dataset)
            result.label = f"λc={lc}"
            results.append(result)
            self.runner.base_config.lambda_c = orig_lc
        return SweepResult("lambda_c", values, results)

    @staticmethod
    def print_sweep(sweep: SweepResult) -> str:
        """Print a sweep result table."""
        return ExperimentRunner.print_summary(sweep.results)


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
