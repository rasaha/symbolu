#!/usr/bin/env python3
"""
Bilinear BCVF Scorer — Low-Rank Anisotropic Metric Learning
=============================================================

Replaces cosine-based ``sb_i = cos(e_i, goal)`` with a learned bilinear
scoring function::

    s_i = (U^T h_t) . (V^T e_i)

where U, V in R^{D x r} are low-rank projection matrices (rank r,
default 64).  The idea is that correctness signal may be present in h_t
but requires an anisotropic metric rather than raw cosine similarity.

Training uses InfoNCE / softmax contrastive loss over a top-M candidate
pool: the correct token should score higher than the M-1 negatives.

At eval time, the scorer replaces the cosine-based backward score (sb)
in the BCVF pipeline, bypassing goal embedding entirely.

Usage::

    # Quick dry-run
    python scripts/run_bcvf_benchmarks.py --dry-run --train-bilinear

    # WikiText with Phi-3
    python scripts/run_bcvf_benchmarks.py --mode wikitext --model phi3 \\
        --train-bilinear --bilinear-train-samples 10000 --samples 5000

    # HumanEval gate check
    python scripts/run_bcvf_benchmarks.py --mode humaneval --model phi3 \\
        --samples 1640 --train-bilinear --goal-strategy bilinear
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

from symbolu.ontological.bcvf_calibration import (
    compute_brier,
    compute_ece,
    spearman_rank_correlation,
)


# =========================================================================
# Configuration
# =========================================================================


@dataclass
class BilinearConfig:
    """Configuration for BilinearBCVF scorer.

    Attributes:
        rank: Low-rank dimension for U, V projections.
        use_sigmoid: Apply sigmoid(gamma * s) for [0,1] bounded scores.
        gamma_init: Initial value for learnable gamma scalar.
        gamma_learnable: Whether gamma is a learnable parameter.
        top_m: Number of top-logit candidates for training negatives.
        lr: AdamW learning rate.
        epochs: Training epochs.
        batch_size: Mini-batch size.
        weight_decay: L2 regularisation on U, V.
        train_samples: Number of training positions to collect.
        eval_samples: Number of eval positions.
        seed: Random seed.
        rho_improvement_threshold: Min rho improvement over best baseline
            to declare BILINEAR WINS.
        alpha_values: Alpha sweep values for gated logit modulation.
    """

    rank: int = 64
    use_sigmoid: bool = True
    gamma_init: float = 1.0
    gamma_learnable: bool = True
    top_m: int = 500
    lr: float = 1e-3
    epochs: int = 3
    batch_size: int = 64
    weight_decay: float = 1e-4
    train_samples: int = 10_000
    eval_samples: int = 5_000
    seed: int = 42
    rho_improvement_threshold: float = 0.05
    alpha_values: List[float] = field(
        default_factory=lambda: [0.01, 0.02, 0.05, 0.1]
    )


# =========================================================================
# BilinearScorer (nn.Module)
# =========================================================================

if PYTORCH_AVAILABLE:

    class BilinearScorer(nn.Module):
        """Low-rank bilinear scorer for token candidates.

        Computes::

            qh = h @ U            -> (B, r)
            ke = E @ V            -> (B, M, r)
            s  = (qh * ke).sum()  -> (B, M)

        Optionally applies ``sigmoid(gamma * s)`` for bounded output.

        Args:
            hidden_dim: Model hidden dimension D.
            rank: Low-rank projection dimension r.
            use_sigmoid: If True, apply sigmoid(gamma * s).
            gamma_init: Initial gamma value.
            gamma_learnable: If True, gamma is a learned parameter.
        """

        def __init__(
            self,
            hidden_dim: int,
            rank: int = 64,
            use_sigmoid: bool = True,
            gamma_init: float = 1.0,
            gamma_learnable: bool = True,
        ):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.rank = rank
            self.use_sigmoid = use_sigmoid

            # Low-rank projections: U for hidden state, V for embeddings
            self.U = nn.Parameter(
                torch.randn(hidden_dim, rank) * 0.02
            )
            self.V = nn.Parameter(
                torch.randn(hidden_dim, rank) * 0.02
            )

            # Optional learnable scaling
            if gamma_learnable:
                self.gamma = nn.Parameter(
                    torch.tensor(float(gamma_init))
                )
            else:
                self.register_buffer(
                    "gamma", torch.tensor(float(gamma_init))
                )

        def forward(
            self,
            h: torch.Tensor,
            E: torch.Tensor,
        ) -> torch.Tensor:
            """Score candidates against hidden state.

            Args:
                h: [B, D] hidden state (fp32 for stability).
                E: [B, M, D] candidate token embeddings.

            Returns:
                scores: [B, M] bilinear scores (float32).
            """
            # Ensure fp32 for numerical stability
            h = h.float()
            E = E.float()
            U = self.U.float()
            V = self.V.float()
            gamma = self.gamma.float()

            qh = h @ U                            # [B, r]
            ke = E @ V                             # [B, M, r]
            s = (qh.unsqueeze(1) * ke).sum(-1)     # [B, M]

            if self.use_sigmoid:
                s = torch.sigmoid(gamma * s)

            return s

        def score_flat(
            self,
            h: torch.Tensor,
            e: torch.Tensor,
        ) -> torch.Tensor:
            """Score a flat set of embeddings (no candidate dim).

            Args:
                h: [B, D] hidden state.
                e: [B, D] single embedding per sample.

            Returns:
                scores: [B] scalar scores.
            """
            return self.forward(h, e.unsqueeze(1)).squeeze(1)

    # =====================================================================
    # Training Data Collection
    # =====================================================================

    @dataclass
    class BilinearSample:
        """One training/eval sample for BilinearScorer."""

        h_t: torch.Tensor          # [D] hidden state
        logits_t: torch.Tensor      # [V] raw logits
        ground_truth_token: int     # correct next token id
        correct: int                # 1 if argmax(logits) == gt, else 0

    def collect_bilinear_samples_from_adapter(
        dataset: List[Dict[str, Any]],
        n_samples: int,
    ) -> List[BilinearSample]:
        """Collect BilinearSamples from a DatasetAdapter-style dataset.

        Each dataset element must have:
            hidden_state: [1, D] tensor
            logits: [1, V] tensor
            ground_truth: int token id
        """
        samples: List[BilinearSample] = []

        for item in dataset:
            if len(samples) >= n_samples:
                break

            h = item["hidden_state"]
            if h.dim() == 2:
                h = h[0]  # [D]
            logits = item["logits"]
            if logits.dim() == 2:
                logits = logits[0]  # [V]
            gt = int(item["ground_truth"])
            correct = 1 if int(logits.argmax().item()) == gt else 0

            samples.append(BilinearSample(
                h_t=h.detach().cpu().float(),
                logits_t=logits.detach().cpu().float(),
                ground_truth_token=gt,
                correct=correct,
            ))

        return samples

    # =====================================================================
    # Bilinear Trainer
    # =====================================================================

    def _build_candidate_batch(
        samples: List[BilinearSample],
        indices: List[int],
        vocab_embeddings: torch.Tensor,
        top_m: int,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Build a training batch with candidate sets.

        For each sample, selects top-M candidates from logits, ensuring
        the ground truth is included (replacing the lowest-logit
        candidate if necessary).

        Returns:
            h_batch: [B, D]
            E_batch: [B, M, D] candidate embeddings
            target_indices: [B] index of ground truth within M candidates
            correctness: [B] binary correctness indicator
        """
        B = len(indices)
        D = vocab_embeddings.shape[1]
        M = top_m

        h_list = []
        E_list = []
        target_list = []
        correct_list = []

        for idx in indices:
            s = samples[idx]
            logits = s.logits_t
            gt = s.ground_truth_token
            V = logits.shape[0]
            eff_m = min(M, V)

            # Top-M by logit
            topM_scores, topM_ids = torch.topk(logits, eff_m)

            # Check if ground truth is in top-M
            gt_in_topM = (topM_ids == gt).any()

            if not gt_in_topM:
                # Replace lowest-logit candidate with ground truth
                topM_ids[-1] = gt
                topM_scores[-1] = logits[gt]

            # Find target index within candidates
            target_idx = (topM_ids == gt).nonzero(as_tuple=True)[0][0].item()

            # Gather embeddings
            E_candidates = vocab_embeddings[topM_ids]  # [M, D]

            # Pad if needed (when V < M)
            if eff_m < M:
                pad = torch.zeros(M - eff_m, D, dtype=E_candidates.dtype)
                E_candidates = torch.cat([E_candidates, pad], dim=0)

            h_list.append(s.h_t)
            E_list.append(E_candidates)
            target_list.append(target_idx)
            correct_list.append(s.correct)

        h_batch = torch.stack(h_list)               # [B, D]
        E_batch = torch.stack(E_list)                # [B, M, D]
        targets = torch.tensor(target_list, dtype=torch.long)  # [B]
        correctness = torch.tensor(correct_list, dtype=torch.float32)

        return h_batch, E_batch, targets, correctness

    def train_bilinear_scorer(
        samples: List[BilinearSample],
        vocab_embeddings: torch.Tensor,
        config: BilinearConfig,
        device: str = "cpu",
    ) -> Tuple[BilinearScorer, List[float]]:
        """Train BilinearScorer with InfoNCE / softmax contrastive loss.

        For each sample (h_t, ground_truth, top-M candidates), we compute
        bilinear scores over candidates and apply cross_entropy loss to
        push the ground truth score above negatives.

        Args:
            samples: Training samples with h_t, logits, ground_truth.
            vocab_embeddings: [V, D] token embedding matrix.
            config: BilinearConfig with hyperparameters.
            device: Torch device.

        Returns:
            (trained_scorer, loss_curve) where loss_curve is per-epoch
            average loss.
        """
        D = vocab_embeddings.shape[1]
        vocab_embeddings = vocab_embeddings.detach().float().to(device)

        scorer = BilinearScorer(
            hidden_dim=D,
            rank=config.rank,
            use_sigmoid=False,  # Raw scores for cross-entropy
            gamma_init=config.gamma_init,
            gamma_learnable=config.gamma_learnable,
        ).to(device)

        optimizer = torch.optim.AdamW(
            scorer.parameters(),
            lr=config.lr,
            weight_decay=config.weight_decay,
        )

        torch.manual_seed(config.seed)
        n = len(samples)
        batch_size = config.batch_size
        top_m = min(config.top_m, vocab_embeddings.shape[0])
        loss_curve: List[float] = []

        for epoch in range(config.epochs):
            perm = torch.randperm(n).tolist()
            epoch_loss = 0.0
            n_batches = 0

            for start in range(0, n, batch_size):
                end = min(start + batch_size, n)
                batch_indices = perm[start:end]

                h_batch, E_batch, targets, _ = _build_candidate_batch(
                    samples, batch_indices, vocab_embeddings, top_m,
                )
                h_batch = h_batch.to(device)
                E_batch = E_batch.to(device)
                targets = targets.to(device)

                # Forward: raw (unbounded) scores for cross-entropy
                scores = scorer(h_batch, E_batch)  # [B, M]

                loss = F.cross_entropy(scores, targets)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()
                n_batches += 1

            avg_loss = epoch_loss / max(n_batches, 1)
            loss_curve.append(avg_loss)
            print(
                f"  [bilinear] Epoch {epoch+1}/{config.epochs}: "
                f"loss={avg_loss:.4f}"
            )

        # After training, set use_sigmoid for eval
        scorer.use_sigmoid = config.use_sigmoid
        scorer.eval()

        return scorer, loss_curve

    # =====================================================================
    # Evaluation
    # =====================================================================

    @dataclass
    class BilinearEvalResult:
        """Evaluation result for BilinearScorer."""

        dataset_name: str
        n_eval: int

        # Primary predictive signal
        rho_sb_bilin: float           # Spearman rho(sb_bilin, correctness)
        rho_sb_bilin_top1: float      # rho(sb_top1_bilin, correctness)

        # Baseline signals
        rho_maxprob: float            # rho(max_prob, correctness)
        rho_margin: float             # rho(margin, correctness)
        rho_neg_entropy: float        # rho(-entropy, correctness)
        rho_logit_gap: float          # rho(logit_gap, correctness)

        # Verdict
        bilinear_wins: bool
        best_baseline_rho: float
        best_baseline_name: str
        rho_improvement: float

        # sb stats
        sb_mean: float
        sb_std: float
        sb_top1_mean: float
        sb_gap_mean: float            # mean(top1 - top2) in sb

        # Calibration
        ece: float
        brier: float
        ece_on_wrong_baseline: float
        ece_on_low_margin: float

        # Pass@1 with reranking
        pass_at_1_base: float
        pass_at_1_bilinear: float
        pass_at_1_delta: float
        rerank_pct: float             # fraction of positions reranked

        # Training
        loss_curve: List[float] = field(default_factory=list)

        # Alpha sweep for logit modulation
        alpha_sweep: Dict[float, Dict[str, float]] = field(
            default_factory=dict
        )

    def evaluate_bilinear_scorer(
        scorer: BilinearScorer,
        samples: List[BilinearSample],
        vocab_embeddings: torch.Tensor,
        config: BilinearConfig,
        dataset_name: str = "eval",
        device: str = "cpu",
    ) -> BilinearEvalResult:
        """Evaluate trained BilinearScorer on held-out data.

        Computes:
        - Spearman rho of sb_bilin vs correctness
        - Comparison to baselines (maxprob, margin, -entropy, logit_gap)
        - ECE/Brier calibration of sb_bilin as confidence proxy
        - Pass@1 with bilinear reranking
        - Verdict: BILINEAR WINS / BASELINE WINS / NEITHER / ~tied
        """
        vocab_embeddings = vocab_embeddings.detach().float().to(device)
        scorer = scorer.to(device)
        scorer.eval()

        top_m = min(config.top_m, vocab_embeddings.shape[0])

        # Collect per-sample metrics
        sb_bilin_all = []       # mean sb across candidates (as confidence)
        sb_top1_all = []        # sb of top-1 candidate
        sb_gap_all = []         # sb_top1 - sb_top2
        maxprob_all = []
        margin_all = []
        neg_entropy_all = []
        logit_gap_all = []
        correctness_all = []
        base_pred_correct = []  # baseline (argmax) correctness
        bilin_pred_correct = [] # bilinear reranking correctness

        with torch.no_grad():
            for s in samples:
                logits = s.logits_t.to(device)
                h = s.h_t.unsqueeze(0).to(device)    # [1, D]
                gt = s.ground_truth_token
                V = logits.shape[0]
                eff_m = min(top_m, V)

                # Top-M candidates
                topM_scores, topM_ids = torch.topk(logits, eff_m)

                # Baseline predictions
                base_pred = int(logits.argmax().item())
                base_correct = int(base_pred == gt)
                base_pred_correct.append(base_correct)

                # Candidate embeddings
                E_cand = vocab_embeddings[topM_ids].unsqueeze(0)  # [1, M, D]

                # Bilinear scores
                sb = scorer(h, E_cand)  # [1, M]
                sb_vals = sb[0]

                # sb stats
                sb_mean_val = sb_vals.mean().item()
                sb_sorted, sb_sorted_idx = sb_vals.sort(descending=True)
                sb_top1 = sb_sorted[0].item()
                sb_top2 = sb_sorted[1].item() if len(sb_sorted) > 1 else sb_top1
                sb_gap = sb_top1 - sb_top2

                sb_bilin_all.append(sb_mean_val)
                sb_top1_all.append(sb_top1)
                sb_gap_all.append(sb_gap)

                # Bilinear reranking: pick candidate with best
                # adjusted = base_logit - beta * (1 - sb)^2
                # Simplified: just pick highest sb among top-M
                bilin_best_rel = sb_vals.argmax().item()
                bilin_best_token = int(topM_ids[bilin_best_rel].item())
                bilin_correct = int(bilin_best_token == gt)
                bilin_pred_correct.append(bilin_correct)

                # Baseline signals
                probs = F.softmax(logits, dim=-1)
                max_prob = probs.max().item()
                sorted_probs, _ = probs.sort(descending=True)
                margin = (sorted_probs[0] - sorted_probs[1]).item()
                entropy = -(probs * torch.log(probs + 1e-10)).sum().item()
                sorted_logits, _ = logits.sort(descending=True)
                logit_gap = (sorted_logits[0] - sorted_logits[1]).item()

                maxprob_all.append(max_prob)
                margin_all.append(margin)
                neg_entropy_all.append(-entropy)
                logit_gap_all.append(logit_gap)

                correct = 1 if base_pred == gt else 0
                correctness_all.append(correct)

        # Convert to arrays
        sb_bilin_arr = np.array(sb_bilin_all)
        sb_top1_arr = np.array(sb_top1_all)
        sb_gap_arr = np.array(sb_gap_all)
        maxprob_arr = np.array(maxprob_all)
        margin_arr = np.array(margin_all)
        neg_ent_arr = np.array(neg_entropy_all)
        logit_gap_arr = np.array(logit_gap_all)
        corr_arr = np.array(correctness_all)
        base_correct_arr = np.array(base_pred_correct)
        bilin_correct_arr = np.array(bilin_pred_correct)

        # Spearman correlations
        rho_sb = spearman_rank_correlation(sb_bilin_arr, corr_arr)
        rho_sb_top1 = spearman_rank_correlation(sb_top1_arr, corr_arr)
        rho_maxprob = spearman_rank_correlation(maxprob_arr, corr_arr)
        rho_margin = spearman_rank_correlation(margin_arr, corr_arr)
        rho_neg_ent = spearman_rank_correlation(neg_ent_arr, corr_arr)
        rho_logit_gap = spearman_rank_correlation(logit_gap_arr, corr_arr)

        # Best baseline
        baselines = {
            "maxprob": rho_maxprob,
            "margin": rho_margin,
            "-entropy": rho_neg_ent,
            "logit_gap": rho_logit_gap,
        }
        best_bl_name = max(baselines, key=baselines.get)
        best_bl_rho = baselines[best_bl_name]

        # Use the better of rho_sb and rho_sb_top1 for verdict
        best_bilin_rho = max(rho_sb, rho_sb_top1)
        rho_improvement = best_bilin_rho - best_bl_rho
        bilinear_wins = rho_improvement > config.rho_improvement_threshold

        # Calibration: use sb_top1 as confidence proxy
        # Clamp to [0,1] for calibration metrics
        sb_conf = np.clip(sb_top1_arr, 0.0, 1.0)
        ece_val = compute_ece(sb_conf, corr_arr)
        brier_val = compute_brier(sb_conf, corr_arr)

        # Conditional ECE on wrong-baseline
        wrong_mask = base_correct_arr == 0
        ece_wrong = 0.0
        if wrong_mask.sum() >= 5:
            ece_wrong = compute_ece(sb_conf[wrong_mask], corr_arr[wrong_mask])

        # Conditional ECE on low-margin (margin < 0.07)
        low_margin_mask = margin_arr < 0.07
        ece_low_margin = 0.0
        if low_margin_mask.sum() >= 5:
            ece_low_margin = compute_ece(
                sb_conf[low_margin_mask], corr_arr[low_margin_mask]
            )

        # Pass@1
        n_eval = len(samples)
        pass_at_1_base = float(base_correct_arr.mean())
        pass_at_1_bilin = float(bilin_correct_arr.mean())
        pass_at_1_delta = pass_at_1_bilin - pass_at_1_base
        rerank_pct = float(
            (bilin_correct_arr != base_correct_arr).mean()
        )

        # Alpha sweep: logit modulation gated by bilinear score
        alpha_results: Dict[float, Dict[str, float]] = {}
        if config.alpha_values:
            for alpha in config.alpha_values:
                mod_correct = []
                with torch.no_grad():
                    for s in samples:
                        logits = s.logits_t.to(device)
                        h = s.h_t.unsqueeze(0).to(device)
                        gt = s.ground_truth_token
                        V = logits.shape[0]
                        eff_m = min(top_m, V)

                        topM_scores, topM_ids = torch.topk(logits, eff_m)
                        E_cand = vocab_embeddings[topM_ids].unsqueeze(0)
                        sb = scorer(h, E_cand)[0]

                        # Modulate: adjusted_logit = base_logit + alpha * sb
                        adjusted = topM_scores + alpha * sb
                        best_rel = adjusted.argmax().item()
                        best_tok = int(topM_ids[best_rel].item())
                        mod_correct.append(int(best_tok == gt))

                mod_arr = np.array(mod_correct)
                mod_pass1 = float(mod_arr.mean())
                alpha_results[alpha] = {
                    "pass_at_1": mod_pass1,
                    "delta": mod_pass1 - pass_at_1_base,
                }

        return BilinearEvalResult(
            dataset_name=dataset_name,
            n_eval=n_eval,
            rho_sb_bilin=rho_sb,
            rho_sb_bilin_top1=rho_sb_top1,
            rho_maxprob=rho_maxprob,
            rho_margin=rho_margin,
            rho_neg_entropy=rho_neg_ent,
            rho_logit_gap=rho_logit_gap,
            bilinear_wins=bilinear_wins,
            best_baseline_rho=best_bl_rho,
            best_baseline_name=best_bl_name,
            rho_improvement=rho_improvement,
            sb_mean=float(sb_bilin_arr.mean()),
            sb_std=float(sb_bilin_arr.std()),
            sb_top1_mean=float(sb_top1_arr.mean()),
            sb_gap_mean=float(sb_gap_arr.mean()),
            ece=ece_val,
            brier=brier_val,
            ece_on_wrong_baseline=ece_wrong,
            ece_on_low_margin=ece_low_margin,
            pass_at_1_base=pass_at_1_base,
            pass_at_1_bilinear=pass_at_1_bilin,
            pass_at_1_delta=pass_at_1_delta,
            rerank_pct=rerank_pct,
            alpha_sweep=alpha_results,
        )

    # =====================================================================
    # Reporting
    # =====================================================================

    def print_bilinear_report(
        results: List[BilinearEvalResult],
        loss_curves: Optional[Dict[str, List[float]]] = None,
    ) -> str:
        """Print formatted Bilinear Evaluation Report.

        Args:
            results: List of BilinearEvalResult (one per dataset).
            loss_curves: Optional dict of dataset_name -> loss_curve.

        Returns:
            Formatted report string.
        """
        lines: List[str] = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("Bilinear BCVF Evaluation Report")
        lines.append("=" * 70)

        # --- Loss curves ---
        if loss_curves:
            lines.append("")
            lines.append("Training Loss Curves:")
            for name, curve in loss_curves.items():
                curve_str = " -> ".join(f"{v:.4f}" for v in curve)
                lines.append(f"  {name}: {curve_str}")

        # --- Per-dataset results ---
        for r in results:
            lines.append("")
            lines.append(f"--- {r.dataset_name} ({r.n_eval} positions) ---")
            lines.append("")

            # Predictive signal table
            lines.append(
                "Predictive signal (Spearman rho with correctness):"
            )
            lines.append(
                f"  {'Metric':<20} {'rho':>8}  {'vs best BL':>10}"
            )
            lines.append(f"  {'-'*42}")

            best_bl = r.best_baseline_rho
            lines.append(
                f"  {'sb_bilin (mean)':.<20} "
                f"{r.rho_sb_bilin:>+8.4f}  "
                f"{r.rho_sb_bilin - best_bl:>+10.4f}"
            )
            lines.append(
                f"  {'sb_bilin (top1)':.<20} "
                f"{r.rho_sb_bilin_top1:>+8.4f}  "
                f"{r.rho_sb_bilin_top1 - best_bl:>+10.4f}"
            )
            lines.append(
                f"  {'maxprob':.<20} {r.rho_maxprob:>+8.4f}"
            )
            lines.append(
                f"  {'margin':.<20} {r.rho_margin:>+8.4f}"
            )
            lines.append(
                f"  {'-entropy':.<20} {r.rho_neg_entropy:>+8.4f}"
            )
            lines.append(
                f"  {'logit_gap':.<20} {r.rho_logit_gap:>+8.4f}"
            )
            lines.append(
                f"  Best baseline: {r.best_baseline_name} "
                f"(rho={r.best_baseline_rho:+.4f})"
            )

            # Verdict
            lines.append("")
            if r.bilinear_wins:
                verdict = (
                    f"BILINEAR WINS (rho improvement "
                    f"{r.rho_improvement:+.4f} > threshold)"
                )
            elif abs(r.rho_improvement) < 0.02:
                verdict = (
                    f"~TIED (rho improvement "
                    f"{r.rho_improvement:+.4f})"
                )
            elif max(abs(r.rho_sb_bilin), abs(r.rho_sb_bilin_top1)) < 0.05:
                verdict = (
                    "NEITHER — bilinear rho too weak "
                    f"(max={max(abs(r.rho_sb_bilin), abs(r.rho_sb_bilin_top1)):.4f})"
                )
            else:
                verdict = (
                    f"BASELINE WINS ({r.best_baseline_name} stronger, "
                    f"improvement={r.rho_improvement:+.4f})"
                )
            lines.append(f"  VERDICT: {verdict}")

            # sb stats
            lines.append("")
            lines.append("sb_bilin statistics:")
            lines.append(
                f"  mean={r.sb_mean:.4f}  std={r.sb_std:.4f}  "
                f"top1_mean={r.sb_top1_mean:.4f}  "
                f"gap_mean={r.sb_gap_mean:.4f}"
            )

            # Calibration
            lines.append("")
            lines.append("Calibration (sb_bilin as confidence):")
            lines.append(f"  ECE={r.ece:.4f}  Brier={r.brier:.4f}")
            lines.append(
                f"  ECE(wrong baseline)={r.ece_on_wrong_baseline:.4f}  "
                f"ECE(low margin)={r.ece_on_low_margin:.4f}"
            )

            # Pass@1
            lines.append("")
            lines.append("Pass@1 effect:")
            lines.append(
                f"  Baseline: {r.pass_at_1_base:.4f}  "
                f"Bilinear: {r.pass_at_1_bilinear:.4f}  "
                f"Delta: {r.pass_at_1_delta:+.4f}  "
                f"Rerank%: {r.rerank_pct:.1%}"
            )

            # Stop conditions
            lines.append("")
            stop_reasons = []
            if r.pass_at_1_delta < -0.002 and r.n_eval >= 1000:
                stop_reasons.append(
                    f"HARD STOP: pass@1 regressed by "
                    f"{r.pass_at_1_delta:.4f}"
                )
            if r.rerank_pct < 0.02:
                stop_reasons.append(
                    f"STOP: rerank% too low ({r.rerank_pct:.1%} < 2%)"
                )
            if not r.bilinear_wins:
                stop_reasons.append(
                    "STOP: bilinear did not win predictive signal"
                )

            if stop_reasons:
                lines.append("Stop conditions triggered:")
                for reason in stop_reasons:
                    lines.append(f"  {reason}")
            else:
                lines.append(
                    "CONTINUE: bilinear wins and no regressions."
                )

            # Alpha sweep
            if r.alpha_sweep:
                lines.append("")
                lines.append(
                    "Logit modulation alpha sweep "
                    "(adjusted = base_logit + alpha * sb):"
                )
                lines.append(
                    f"  {'alpha':>8}  {'pass@1':>8}  {'delta':>8}"
                )
                for alpha, vals in sorted(r.alpha_sweep.items()):
                    lines.append(
                        f"  {alpha:>8.3f}  "
                        f"{vals['pass_at_1']:>8.4f}  "
                        f"{vals['delta']:>+8.4f}"
                    )

        lines.append("")
        lines.append("=" * 70)

        report = "\n".join(lines)
        print(report)
        return report

    # =====================================================================
    # Full Pipeline
    # =====================================================================

    def run_bilinear_pipeline(
        model: Any,
        tokenizer: Any,
        datasets: Dict[str, List[Dict[str, Any]]],
        config: BilinearConfig,
        device: str = "cpu",
    ) -> Tuple[List[BilinearEvalResult], Dict[str, List[float]]]:
        """Run full bilinear scorer pipeline: collect, train, eval.

        Args:
            model: HuggingFace model or dry-run stub.
            tokenizer: Tokenizer.
            datasets: Dict of dataset_name -> adapter-style samples.
            config: BilinearConfig.
            device: Torch device.

        Returns:
            (eval_results, loss_curves) where loss_curves maps
            dataset_name -> per-epoch losses.
        """
        # Get vocab embeddings
        vocab_emb = model.get_input_embeddings().weight.detach().float()

        all_results: List[BilinearEvalResult] = []
        all_loss_curves: Dict[str, List[float]] = {}

        for ds_name, ds_data in datasets.items():
            if not ds_data:
                print(f"  [bilinear] Skipping {ds_name}: no data")
                continue

            print(f"\n  [bilinear] Processing: {ds_name}")

            # Collect samples
            total_needed = config.train_samples + config.eval_samples
            samples = collect_bilinear_samples_from_adapter(
                ds_data, n_samples=total_needed,
            )

            if len(samples) < 20:
                print(
                    f"  [bilinear] Only {len(samples)} samples "
                    f"for {ds_name}, skipping"
                )
                continue

            # Split train/eval
            n_train = min(config.train_samples, int(len(samples) * 0.7))
            train_samples = samples[:n_train]
            eval_samples = samples[n_train:]

            if len(eval_samples) < 10:
                eval_samples = samples[-min(100, len(samples)):]

            print(
                f"  [bilinear] Train: {len(train_samples)}, "
                f"Eval: {len(eval_samples)}"
            )

            # Train
            scorer, loss_curve = train_bilinear_scorer(
                train_samples, vocab_emb, config, device,
            )
            all_loss_curves[ds_name] = loss_curve

            # Evaluate
            result = evaluate_bilinear_scorer(
                scorer, eval_samples, vocab_emb, config,
                dataset_name=ds_name, device=device,
            )
            result.loss_curve = loss_curve
            all_results.append(result)

        return all_results, all_loss_curves


else:
    # Stubs when PyTorch is not available

    class BilinearScorer:  # type: ignore[no-redef]
        pass

    class BilinearSample:  # type: ignore[no-redef]
        pass

    class BilinearEvalResult:  # type: ignore[no-redef]
        pass

    def collect_bilinear_samples_from_adapter(*args, **kwargs):  # type: ignore[no-redef]
        raise ImportError("PyTorch is required for BilinearBCVF")

    def train_bilinear_scorer(*args, **kwargs):  # type: ignore[no-redef]
        raise ImportError("PyTorch is required for BilinearBCVF")

    def evaluate_bilinear_scorer(*args, **kwargs):  # type: ignore[no-redef]
        raise ImportError("PyTorch is required for BilinearBCVF")

    def print_bilinear_report(*args, **kwargs):  # type: ignore[no-redef]
        raise ImportError("PyTorch is required for BilinearBCVF")

    def run_bilinear_pipeline(*args, **kwargs):  # type: ignore[no-redef]
        raise ImportError("PyTorch is required for BilinearBCVF")
