#!/usr/bin/env python3
"""
Contrastive Token Ranking (CTR) — Discriminative Goal Learning
================================================================

Replaces the failed "predict h_{t+1} direction" approach with a
discriminative objective: learn a direction vector d_hat from h_t that
ranks the true next token above plausible alternatives.

Two approaches, tested in order:

1. **Nonparametric kNN-Dir baseline** (fast falsification):
   Build a memory of (key=normalize(h_t), value=direction_t) pairs from
   training data.  At test time, retrieve k nearest neighbours and
   average their directions.  If this fails, no parametric model will
   help either.

2. **Learned contrastive GoalDirNet** (InfoNCE):
   Train GoalDirNet with InfoNCE loss instead of direction regression.
   Positive: embedding of true next token.
   Negatives: embeddings of top-M candidate tokens (hard negatives).

Direction definitions
---------------------
* ``htp1``:  d_t = normalize(h_{t+1})
* ``delta``: d_t = normalize(h_{t+1} - h_t)  (surprise / correction)

Evaluation metrics
------------------
* Rank of true token under cos(E[token], d_hat) among top-M candidates
* Cos-margin: cos(E[y_true], d_hat) - max_{i != y_true} cos(E[i], d_hat)
* Spearman rho(cos_score, correctness) vs logit baselines
* Pass@1 with CTR reranking and gated logit modulation

Usage::

    # Fast nonparametric test
    python scripts/run_bcvf_benchmarks.py --mode wikitext --model phi3 \\
        --ctr-knn --ctr-direction delta --ctr-knn-k 32

    # Learned contrastive
    python scripts/run_bcvf_benchmarks.py --mode wikitext --model phi3 \\
        --train-goal-contrastive --ctr-direction delta \\
        --train-goal-samples 10000 --eval-goal-samples 2000
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

from symbolu_core.ontological.bcvf_calibration import (
    compute_brier,
    compute_ece,
    spearman_rank_correlation,
)


# =========================================================================
# Configuration
# =========================================================================


@dataclass
class CTRConfig:
    """Configuration for Contrastive Token Ranking.

    Attributes:
        direction_mode: How to compute the target direction from
            consecutive hidden states.  ``htp1`` = normalize(h_{t+1}),
            ``delta`` = normalize(h_{t+1} - h_t).
        knn_k: Number of neighbours for kNN-Dir retrieval.
        top_m: Number of top logit candidates for reranking / negatives.
        alpha_values: Alpha sweep values for gated logit modulation.
        tau: Temperature for InfoNCE loss.
        n_hard_negatives: Number of hard negatives from top-M per sample.
        n_random_negatives: Number of random vocab negatives per sample.
        hidden_dim: MLP hidden layer size for learned CTR.
        lr: Learning rate.
        epochs: Training epochs.
        batch_size: Mini-batch size.
        weight_decay: L2 regularisation.
        train_samples: Number of training positions.
        eval_samples: Number of eval positions.
        train_ratio: Fraction for training (rest = eval).
        seed: Random seed.
        rho_improvement_threshold: Min rho improvement over best baseline
            to declare a win.
    """

    direction_mode: str = "delta"
    knn_k: int = 32
    top_m: int = 500
    alpha_values: List[float] = field(
        default_factory=lambda: [0.01, 0.02, 0.05]
    )
    tau: float = 0.07
    n_hard_negatives: int = 64
    n_random_negatives: int = 32
    hidden_dim: int = 512
    lr: float = 1e-3
    epochs: int = 5
    batch_size: int = 256
    weight_decay: float = 1e-5
    train_samples: int = 50_000
    eval_samples: int = 5_000
    train_ratio: float = 0.8
    seed: int = 42
    rho_improvement_threshold: float = 0.02


# =========================================================================
# Direction computation
# =========================================================================


def compute_direction(
    h_t: torch.Tensor,
    h_tp1: torch.Tensor,
    mode: str = "delta",
) -> torch.Tensor:
    """Compute target direction from consecutive hidden states.

    Args:
        h_t: [..., D] current hidden state.
        h_tp1: [..., D] next hidden state.
        mode: ``htp1`` or ``delta``.

    Returns:
        [..., D] unit direction vector.
    """
    if mode == "htp1":
        return F.normalize(h_tp1, p=2, dim=-1)
    elif mode == "delta":
        diff = h_tp1 - h_t
        return F.normalize(diff, p=2, dim=-1)
    else:
        raise ValueError(f"Unknown direction mode: {mode}")


# =========================================================================
# Data structure for CTR samples
# =========================================================================

if PYTORCH_AVAILABLE:

    @dataclass
    class CTRSample:
        """One collected sample for contrastive token ranking."""

        h_t: torch.Tensor            # [D] hidden state at t
        h_next: torch.Tensor         # [D] hidden state at t+1
        direction: torch.Tensor      # [D] target direction (normalized)
        logits_t: torch.Tensor       # [V] logits at t
        correct: int                  # 1 if argmax(logits_t) == y_{t+1}
        ground_truth_token: int       # actual ground truth token id
        features: torch.Tensor       # [F] past-only features (for learned)

    # =====================================================================
    # kNN Direction Memory (nonparametric baseline)
    # =====================================================================

    class KNNDirectionMemory:
        """Nonparametric direction retrieval via k-nearest neighbours.

        Stores (key=normalize(h_t), value=direction_t) pairs.  At query
        time, retrieves k nearest neighbours by cosine similarity and
        averages their directions.

        Uses brute-force cosine search (sufficient for ~200k entries).
        For larger memories, swap in FAISS.

        Args:
            dim: Hidden state dimensionality.
        """

        def __init__(self, dim: int):
            self.dim = dim
            self._keys: List[torch.Tensor] = []
            self._vals: List[torch.Tensor] = []
            self.keys: Optional[torch.Tensor] = None  # [N, D] after finalize
            self.vals: Optional[torch.Tensor] = None   # [N, D] after finalize

        def add_batch(
            self,
            h_t_batch: torch.Tensor,
            d_batch: torch.Tensor,
        ) -> None:
            """Add a batch of (key, direction) pairs.

            Args:
                h_t_batch: [B, D] hidden states.
                d_batch: [B, D] target directions.
            """
            self._keys.append(F.normalize(h_t_batch, p=2, dim=-1).cpu())
            self._vals.append(F.normalize(d_batch, p=2, dim=-1).cpu())

        def finalize(self) -> None:
            """Concatenate all batches into contiguous tensors."""
            self.keys = torch.cat(self._keys, dim=0)  # [N, D]
            self.vals = torch.cat(self._vals, dim=0)   # [N, D]
            self._keys = []
            self._vals = []

        def __len__(self) -> int:
            if self.keys is not None:
                return self.keys.shape[0]
            return sum(k.shape[0] for k in self._keys)

        @torch.no_grad()
        def query(
            self,
            h_t_batch: torch.Tensor,
            k: int = 32,
        ) -> torch.Tensor:
            """Retrieve averaged direction for each query.

            Args:
                h_t_batch: [B, D] query hidden states.
                k: Number of neighbours.

            Returns:
                d_hat: [B, D] retrieved direction estimates (normalized).
            """
            assert self.keys is not None, "Call finalize() first"
            device = h_t_batch.device
            q = F.normalize(h_t_batch, p=2, dim=-1).cpu()  # [B, D]

            # Cosine similarity = dot product of normalized vectors
            # [B, D] @ [D, N] -> [B, N]
            sims = q @ self.keys.T
            _, topk_idx = sims.topk(min(k, self.keys.shape[0]), dim=-1)  # [B, k]

            # Gather neighbour directions and average
            # [B, k, D]
            neighbour_dirs = self.vals[topk_idx]
            d_hat = F.normalize(neighbour_dirs.mean(dim=1), p=2, dim=-1)

            return d_hat.to(device)

    # =====================================================================
    # Nonparametric baselines (no kNN, even cheaper)
    # =====================================================================

    def softmax_weighted_direction(
        logits: torch.Tensor,
        vocab_embeddings: torch.Tensor,
        top_m: int = 500,
    ) -> torch.Tensor:
        """Nonparametric goal: softmax-weighted embedding centroid.

        d_hat = normalize(sum_i p_i * E[i]) over top-M tokens.

        Args:
            logits: [B, V] logits.
            vocab_embeddings: [V, D] token embeddings.
            top_m: Number of top tokens.

        Returns:
            d_hat: [B, D] direction estimate (normalized).
        """
        top_m = min(top_m, logits.shape[-1])
        top_vals, top_idx = torch.topk(logits, top_m, dim=-1)  # [B, M]
        probs = F.softmax(top_vals, dim=-1)  # [B, M]
        cand_embs = vocab_embeddings[top_idx]  # [B, M, D]
        weighted = (probs.unsqueeze(-1) * cand_embs).sum(dim=1)  # [B, D]
        return F.normalize(weighted, p=2, dim=-1)

    # =====================================================================
    # CTR Reranking (shared by kNN and learned)
    # =====================================================================

    @torch.no_grad()
    def ctr_rerank(
        logits: torch.Tensor,
        vocab_embeddings: torch.Tensor,
        d_hat: torch.Tensor,
        top_m: int = 500,
        alpha: float = 0.0,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Rerank top-M tokens using CTR cosine scores.

        Args:
            logits: [B, V] base logits.
            vocab_embeddings: [V, D] token embeddings.
            d_hat: [B, D] direction estimate (normalized).
            top_m: Number of candidates.
            alpha: Logit modulation strength (0 = ranking only).

        Returns:
            chosen: [B] chosen token ids.
            ctr_scores: [B, M] cosine scores for top-M.
            top_idx: [B, M] token indices.
            z_prime: [B, M] modulated scores.
        """
        top_m = min(top_m, logits.shape[-1])
        top_vals, top_idx = torch.topk(logits, top_m, dim=-1)  # [B, M]
        cand_embs = F.normalize(
            vocab_embeddings[top_idx], p=2, dim=-1
        )  # [B, M, D]
        d_exp = F.normalize(d_hat, p=2, dim=-1).unsqueeze(1)  # [B, 1, D]

        # CTR score = cos(E[token], d_hat)
        ctr_scores = (cand_embs * d_exp).sum(dim=-1)  # [B, M]

        # Modulated logits
        z_prime = top_vals + alpha * ctr_scores  # [B, M]

        pick = z_prime.argmax(dim=-1)  # [B]
        chosen = top_idx.gather(1, pick.unsqueeze(-1)).squeeze(-1)  # [B]

        return chosen, ctr_scores, top_idx, z_prime

    # =====================================================================
    # Data Collection for CTR
    # =====================================================================

    def collect_ctr_samples(
        model: Any,
        tokenizer: Any,
        texts: List[str],
        config: CTRConfig,
        device: str = "cpu",
        max_seq_len: int = 512,
    ) -> List[CTRSample]:
        """Collect CTR training/eval samples from text passages.

        Args:
            model: Transformer model.
            tokenizer: Tokenizer.
            texts: Text passages.
            config: CTR configuration.
            device: Torch device.
            max_seq_len: Maximum sequence length.

        Returns:
            List of CTRSample.
        """
        from symbolu_core.ontological.goal_dirnet import GoalDirFeatureBuilder

        feature_builder = GoalDirFeatureBuilder(
            feature_mode="ht", window_size=8,
        )

        torch.manual_seed(config.seed)
        n_samples = config.train_samples + config.eval_samples
        samples: List[CTRSample] = []

        for text_idx, text in enumerate(texts):
            if len(samples) >= n_samples:
                break

            tokens = tokenizer.encode(
                text, return_tensors="pt", truncation=True,
                max_length=max_seq_len,
            ).to(device)

            if tokens.shape[1] < 5:
                continue

            with torch.no_grad():
                outputs = model(
                    tokens, output_hidden_states=True, use_cache=False,
                )
                logits_all = outputs.logits[0]            # [T, V]
                hidden_all = outputs.hidden_states[-1][0]  # [T, D]

            T = tokens.shape[1]
            ground_truth = tokens[0, 1:]  # [T-1]

            positions_needed = min(T - 1, n_samples - len(samples))
            for t in range(positions_needed):
                h_t = hidden_all[t]
                h_next = hidden_all[t + 1]
                direction = compute_direction(
                    h_t, h_next, mode=config.direction_mode,
                )

                pred_token = logits_all[t].argmax().item()
                gt_token = int(ground_truth[t].item())
                correct = 1 if pred_token == gt_token else 0

                samples.append(CTRSample(
                    h_t=h_t.cpu(),
                    h_next=h_next.cpu(),
                    direction=direction.cpu(),
                    logits_t=logits_all[t].cpu(),
                    correct=correct,
                    ground_truth_token=gt_token,
                    features=h_t.cpu(),  # ht-only features
                ))

            if (text_idx + 1) % 5 == 0 and len(samples) > 0:
                print(f"  [ctr] Collected {len(samples)}/{n_samples}")

        print(f"  [ctr] Total collected: {len(samples)} samples")
        return samples

    def collect_ctr_from_adapter(
        dataset: List[Dict[str, Any]],
        config: CTRConfig,
    ) -> List[CTRSample]:
        """Convert pre-built DatasetAdapter samples to CTRSample format.

        Args:
            dataset: List of dicts with hidden_state, logits, ground_truth.
            config: CTR configuration.

        Returns:
            List of CTRSample.
        """
        torch.manual_seed(config.seed)
        n_samples = config.train_samples + config.eval_samples
        samples: List[CTRSample] = []
        N = min(len(dataset), n_samples + 1)

        for i in range(min(N - 1, n_samples)):
            sample = dataset[i]
            next_sample = dataset[i + 1] if i + 1 < N else dataset[i]

            h_t = sample["hidden_state"]
            if isinstance(h_t, torch.Tensor):
                h_t = h_t.squeeze(0).float()
            else:
                h_t = torch.tensor(h_t, dtype=torch.float32).squeeze(0)
            if h_t.dim() > 1:
                h_t = h_t.squeeze(0)

            h_next = next_sample["hidden_state"]
            if isinstance(h_next, torch.Tensor):
                h_next = h_next.squeeze(0).float()
            else:
                h_next = torch.tensor(h_next, dtype=torch.float32).squeeze(0)
            if h_next.dim() > 1:
                h_next = h_next.squeeze(0)

            direction = compute_direction(
                h_t, h_next, mode=config.direction_mode,
            )

            logits_t = sample.get("logits")
            if logits_t is not None:
                if isinstance(logits_t, torch.Tensor):
                    logits_t = logits_t.squeeze(0).float()
                else:
                    logits_t = torch.tensor(
                        logits_t, dtype=torch.float32
                    ).squeeze(0)
                if logits_t.dim() > 1:
                    logits_t = logits_t.squeeze(0)
            else:
                logits_t = torch.zeros(10)

            gt = sample.get("ground_truth", 0)
            gt_token = int(gt)
            pred = logits_t.argmax().item()
            correct = 1 if pred == gt_token else 0

            samples.append(CTRSample(
                h_t=h_t.cpu(),
                h_next=h_next.cpu(),
                direction=direction.cpu(),
                logits_t=logits_t.cpu(),
                correct=correct,
                ground_truth_token=gt_token,
                features=h_t.cpu(),
            ))

        print(f"  [ctr] Collected {len(samples)} from adapter dataset")
        return samples

    # =====================================================================
    # Learned Contrastive GoalDirNet (InfoNCE)
    # =====================================================================

    class ContrastiveGoalNet(nn.Module):
        """MLP that produces a direction for contrastive token ranking.

        Trained with InfoNCE: the output direction should put the true
        next-token embedding above hard negatives (other top-M tokens).

        Architecture: input_dim -> hidden -> hidden -> output_dim,
        L2-normalized output.

        Args:
            input_dim: Feature dimensionality (= D for ht-only).
            output_dim: Output dimensionality (= D, embedding space).
            hidden_dim: Hidden layer size.
        """

        def __init__(
            self,
            input_dim: int,
            output_dim: int,
            hidden_dim: int = 512,
        ):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.GELU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.GELU(),
                nn.Linear(hidden_dim, output_dim),
            )
            self.output_dim = output_dim

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """Forward pass returning L2-normalised direction.

            Args:
                x: [B, input_dim] features.

            Returns:
                d_hat: [B, output_dim] unit vectors.
            """
            raw = self.net(x)
            return F.normalize(raw, p=2, dim=-1)

    def train_contrastive_goal_net(
        samples: List[CTRSample],
        vocab_embeddings: torch.Tensor,
        config: CTRConfig,
        device: str = "cpu",
    ) -> Tuple[ContrastiveGoalNet, Dict[str, float]]:
        """Train ContrastiveGoalNet with InfoNCE loss.

        For each sample:
        - Positive: E[y_true] (true next token embedding)
        - Hard negatives: E[top-M tokens excluding y_true]
        - Random negatives: E[random vocab tokens]

        Loss: -log(exp(cos(d_hat, e_pos)/tau) / sum_all exp(cos/tau))

        Args:
            samples: Training samples.
            vocab_embeddings: [V, D] token embedding matrix.
            config: CTR configuration.
            device: Torch device.

        Returns:
            Tuple of (trained model, training stats).
        """
        if not samples:
            raise ValueError("No training samples")

        torch.manual_seed(config.seed)

        input_dim = samples[0].features.shape[0]
        output_dim = vocab_embeddings.shape[1]
        V = vocab_embeddings.shape[0]

        # Build tensors first to determine dtype, then cast vocab_emb
        # to match (samples are float32; model weights may be bfloat16)
        features = torch.stack([s.features for s in samples]).to(device)
        vocab_emb = F.normalize(
            vocab_embeddings.to(device=device, dtype=features.dtype),
            p=2, dim=-1,
        )  # [V, D]
        gt_tokens = torch.tensor(
            [s.ground_truth_token for s in samples], dtype=torch.long
        ).to(device)
        logits_all = torch.stack([s.logits_t for s in samples]).to(device)

        N = features.shape[0]
        n_train = int(N * config.train_ratio)
        n_train = max(n_train, 2)

        train_feat = features[:n_train]
        train_gt = gt_tokens[:n_train]
        train_logits = logits_all[:n_train]

        # Create model
        model = ContrastiveGoalNet(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_dim=config.hidden_dim,
        ).to(device)

        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=config.lr,
            weight_decay=config.weight_decay,
        )

        stats: Dict[str, float] = {
            "n_train": n_train,
            "n_total": N,
            "input_dim": input_dim,
            "output_dim": output_dim,
            "n_hard_neg": config.n_hard_negatives,
            "n_random_neg": config.n_random_negatives,
            "tau": config.tau,
        }

        model.train()
        n_hard = config.n_hard_negatives
        n_rand = config.n_random_negatives

        for epoch in range(config.epochs):
            epoch_loss = 0.0
            n_batches = 0

            perm = torch.randperm(n_train, device=device)
            train_feat_s = train_feat[perm]
            train_gt_s = train_gt[perm]
            train_logits_s = train_logits[perm]

            for start in range(0, n_train, config.batch_size):
                end = min(start + config.batch_size, n_train)
                batch_feat = train_feat_s[start:end]     # [B, F]
                batch_gt = train_gt_s[start:end]         # [B]
                batch_logits = train_logits_s[start:end]  # [B, V]
                B = batch_feat.shape[0]

                # Predict direction
                d_hat = model(batch_feat)  # [B, D]

                # Positive embeddings
                e_pos = vocab_emb[batch_gt]  # [B, D]

                # Hard negatives: top-M from logits, excluding gt
                top_m = min(n_hard + 1, V)
                _, top_idx = torch.topk(
                    batch_logits, top_m, dim=-1
                )  # [B, top_m]

                # Mask out the ground truth token
                gt_mask = top_idx == batch_gt.unsqueeze(-1)  # [B, top_m]
                # Replace gt positions with a random token
                replacement = torch.randint(
                    0, V, (B, top_m), device=device
                )
                neg_idx = torch.where(gt_mask, replacement, top_idx)
                neg_idx = neg_idx[:, :n_hard]  # [B, n_hard]

                # Random negatives
                rand_idx = torch.randint(
                    0, V, (B, n_rand), device=device
                )  # [B, n_rand]

                # All negative indices
                all_neg_idx = torch.cat(
                    [neg_idx, rand_idx], dim=-1
                )  # [B, n_hard + n_rand]
                e_neg = vocab_emb[all_neg_idx]  # [B, N_neg, D]

                # InfoNCE loss
                # pos_score: [B]
                pos_score = (d_hat * e_pos).sum(dim=-1) / config.tau

                # neg_scores: [B, N_neg]
                neg_scores = torch.bmm(
                    e_neg, d_hat.unsqueeze(-1)
                ).squeeze(-1) / config.tau  # [B, N_neg]

                # log_sum_exp over [pos, neg1, neg2, ...]
                all_scores = torch.cat(
                    [pos_score.unsqueeze(-1), neg_scores], dim=-1
                )  # [B, 1 + N_neg]
                loss = -pos_score + torch.logsumexp(all_scores, dim=-1)
                loss = loss.mean()

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()
                n_batches += 1

            avg_loss = epoch_loss / max(n_batches, 1)
            stats[f"loss_epoch_{epoch}"] = avg_loss
            print(
                f"  [ctr] Epoch {epoch + 1}/{config.epochs} "
                f"InfoNCE loss={avg_loss:.4f}"
            )

        stats["final_loss"] = stats.get(
            f"loss_epoch_{config.epochs - 1}", 0.0
        )
        model.eval()
        return model, stats

    # =====================================================================
    # Evaluation
    # =====================================================================

    @dataclass
    class CTREvalResult:
        """Evaluation result for CTR (kNN or learned) vs baselines.

        The primary metrics are:
        - rho_ctr: Spearman rho between CTR cosine score and correctness
        - mean_true_rank: mean rank of true token under CTR scoring
        - cos_margin: mean cosine margin (pos - best neg)
        """

        dataset_name: str
        method: str  # "knn_htp1", "knn_delta", "learned", "softmax_wt"
        n_eval: int = 0

        # CTR-specific metrics
        rho_ctr: float = 0.0
        mean_true_rank: float = 0.0
        median_true_rank: float = 0.0
        cos_margin_mean: float = 0.0
        cos_margin_median: float = 0.0
        mrr: float = 0.0  # mean reciprocal rank

        # Baseline comparisons (Spearman rho with correctness)
        rho_margin: float = 0.0
        rho_maxprob: float = 0.0
        rho_neg_entropy: float = 0.0
        rho_logit_gap: float = 0.0

        # Gating
        ctr_wins: bool = False
        best_baseline_rho: float = 0.0
        best_baseline_name: str = ""
        rho_improvement: float = 0.0

        # Pass@1 (with CTR reranking)
        pass_at_1_baseline: float = 0.0
        pass_at_1_reranked: float = 0.0
        rerank_pct: float = 0.0

        # Alpha sweep
        alpha_sweep: Dict[float, Dict[str, float]] = field(
            default_factory=dict
        )

        # Training stats (for learned method)
        training_stats: Dict[str, float] = field(default_factory=dict)

    def evaluate_ctr(
        d_hat_fn,
        samples: List[CTRSample],
        vocab_embeddings: torch.Tensor,
        dataset_name: str = "unknown",
        method: str = "knn",
        device: str = "cpu",
        top_m: int = 500,
        alpha_values: Optional[List[float]] = None,
        config: Optional[CTRConfig] = None,
    ) -> CTREvalResult:
        """Evaluate a CTR direction estimator.

        Args:
            d_hat_fn: Callable(h_t_batch: [B,D]) -> d_hat: [B,D].
                The direction estimator (kNN, learned, or nonparametric).
            samples: Evaluation samples.
            vocab_embeddings: [V, D] token embeddings.
            dataset_name: For reporting.
            method: Label for this method.
            device: Torch device.
            top_m: Number of candidates.
            alpha_values: Alpha values for modulation sweep.
            config: CTR config (for threshold).

        Returns:
            CTREvalResult with all metrics.
        """
        if not samples:
            return CTREvalResult(
                dataset_name=dataset_name, method=method
            )

        config = config or CTRConfig()
        alpha_values = alpha_values or config.alpha_values

        h_ts = torch.stack([s.h_t for s in samples]).to(device)
        logits_all = torch.stack([s.logits_t for s in samples]).to(device)

        # Cast vocab embeddings to match sample dtype (samples are
        # collected as float32; model weights may be bfloat16)
        vocab_emb = F.normalize(
            vocab_embeddings.to(device=device, dtype=h_ts.dtype),
            p=2, dim=-1,
        )
        correct = np.array([s.correct for s in samples], dtype=np.float64)
        gt_tokens = np.array([s.ground_truth_token for s in samples])

        N, V = logits_all.shape
        top_m_actual = min(top_m, V)

        # Get direction estimates
        # Process in batches to avoid OOM
        batch_size = 512
        d_hats = []
        for i in range(0, N, batch_size):
            end = min(i + batch_size, N)
            d_batch = d_hat_fn(h_ts[i:end])
            d_hats.append(d_batch)
        d_hat = torch.cat(d_hats, dim=0).detach()  # [N, D]
        d_hat = F.normalize(d_hat, p=2, dim=-1)

        # ---- CTR scores for top-M ----
        top_vals, top_idx = torch.topk(
            logits_all, top_m_actual, dim=-1
        )  # [N, M]
        cand_embs = vocab_emb[top_idx]  # [N, M, D]
        ctr_scores = (
            cand_embs * d_hat.unsqueeze(1)
        ).sum(dim=-1)  # [N, M]

        # ---- Rank of true token under CTR ----
        gt_tokens_t = torch.tensor(
            gt_tokens, dtype=torch.long, device=device
        )
        # Score for the true token
        gt_embs = vocab_emb[gt_tokens_t]  # [N, D]
        s_true = (gt_embs * d_hat).sum(dim=-1)  # [N]

        # Find rank among top-M (how many have higher score than true?)
        # If gt is not in top-M, use rank = top_m
        gt_in_topM = (top_idx == gt_tokens_t.unsqueeze(-1))  # [N, M]
        gt_in_topM_any = gt_in_topM.any(dim=-1)  # [N]

        # Rank = number of candidates with higher CTR score than true
        ranks = (ctr_scores > s_true.unsqueeze(-1)).sum(dim=-1).float()
        # For tokens not in top-M, set rank = top_m
        ranks = torch.where(
            gt_in_topM_any, ranks, torch.tensor(
                float(top_m_actual), device=device
            )
        )
        ranks_np = ranks.cpu().numpy()

        # ---- Cosine margin ----
        # Margin = s_true - max(s_neg) among top-M excluding gt
        ctr_scores_masked = ctr_scores.clone()
        ctr_scores_masked[gt_in_topM] = float("-inf")
        best_neg_score = ctr_scores_masked.max(dim=-1).values  # [N]
        cos_margins = (s_true - best_neg_score).cpu().numpy()

        # ---- CTR score for base top-1 prediction (for Spearman) ----
        base_preds = logits_all.argmax(dim=-1)  # [N]
        base_pred_embs = vocab_emb[base_preds]  # [N, D]
        s_pred = (base_pred_embs * d_hat).sum(dim=-1).cpu().numpy()

        # ---- Baselines ----
        from symbolu_core.ontological.goal_dirnet import GoalDirFeatureBuilder
        baselines = GoalDirFeatureBuilder.compute_logit_baselines(logits_all)
        margin_bl = baselines["margin"].cpu().numpy()
        maxprob_bl = baselines["maxprob"].cpu().numpy()
        neg_entropy_bl = baselines["neg_entropy"].cpu().numpy()
        logit_gap_bl = baselines["logit_gap"].cpu().numpy()

        # ---- Spearman rho with correctness ----
        rho_ctr = spearman_rank_correlation(s_pred, correct)
        rho_margin = spearman_rank_correlation(margin_bl, correct)
        rho_maxprob = spearman_rank_correlation(maxprob_bl, correct)
        rho_neg_entropy = spearman_rank_correlation(neg_entropy_bl, correct)
        rho_logit_gap = spearman_rank_correlation(logit_gap_bl, correct)

        # ---- Best baseline ----
        baseline_rhos = {
            "margin": rho_margin,
            "maxprob": rho_maxprob,
            "-entropy": rho_neg_entropy,
            "logit_gap": rho_logit_gap,
        }
        best_name = max(baseline_rhos, key=lambda k: baseline_rhos[k])
        best_rho = baseline_rhos[best_name]
        rho_imp = rho_ctr - best_rho
        ctr_wins = rho_imp >= config.rho_improvement_threshold

        # ---- Pass@1 baseline vs CTR reranked (alpha=0) ----
        base_preds_np = base_preds.cpu().numpy()
        base_pass = float((base_preds_np == gt_tokens).mean())

        # CTR reranking at alpha=0 (pure cosine ranking over top-M)
        chosen_a0, _, _, _ = ctr_rerank(
            logits_all, vocab_emb, d_hat,
            top_m=top_m_actual, alpha=0.0,
        )
        chosen_a0_np = chosen_a0.cpu().numpy()
        reranked_pass = float((chosen_a0_np == gt_tokens).mean())
        rerank_changed = int((chosen_a0_np != base_preds_np).sum())
        rerank_pct = rerank_changed / N if N > 0 else 0.0

        # ---- Alpha sweep ----
        alpha_results: Dict[float, Dict[str, float]] = {}
        for alpha in alpha_values:
            chosen_a, _, _, _ = ctr_rerank(
                logits_all, vocab_emb, d_hat,
                top_m=top_m_actual, alpha=alpha,
            )
            chosen_np = chosen_a.cpu().numpy()
            mod_pass = float((chosen_np == gt_tokens).mean())
            mod_changed = int((chosen_np != base_preds_np).sum())
            alpha_results[alpha] = {
                "pass_at_1": mod_pass,
                "delta_pass_at_1": mod_pass - base_pass,
                "rerank_pct": mod_changed / N if N > 0 else 0.0,
                "baseline_pass_at_1": base_pass,
            }

        # ---- MRR ----
        mrr = float((1.0 / (ranks_np + 1.0)).mean())

        return CTREvalResult(
            dataset_name=dataset_name,
            method=method,
            n_eval=N,
            rho_ctr=rho_ctr,
            mean_true_rank=float(ranks_np.mean()),
            median_true_rank=float(np.median(ranks_np)),
            cos_margin_mean=float(cos_margins.mean()),
            cos_margin_median=float(np.median(cos_margins)),
            mrr=mrr,
            rho_margin=rho_margin,
            rho_maxprob=rho_maxprob,
            rho_neg_entropy=rho_neg_entropy,
            rho_logit_gap=rho_logit_gap,
            ctr_wins=ctr_wins,
            best_baseline_rho=best_rho,
            best_baseline_name=best_name,
            rho_improvement=rho_imp,
            pass_at_1_baseline=base_pass,
            pass_at_1_reranked=reranked_pass,
            rerank_pct=rerank_pct,
            alpha_sweep=alpha_results,
        )

    # =====================================================================
    # Reporting
    # =====================================================================

    def print_ctr_report(
        eval_results: List[CTREvalResult],
    ) -> str:
        """Print CTR evaluation report.

        Args:
            eval_results: List of per-method/dataset eval results.

        Returns:
            Formatted report string.
        """
        lines = []
        lines.append("")
        lines.append("=" * 100)
        lines.append(
            "Contrastive Token Ranking (CTR) Evaluation Report"
        )
        lines.append("=" * 100)

        # Table 1: Predictive signal comparison
        lines.append("")
        lines.append(
            "1. Predictive Signal (Spearman rho with correctness):"
        )
        lines.append("-" * 100)
        lines.append(
            f"  {'Dataset':<22} {'Method':<14} {'rho_ctr':>8} "
            f"{'margin':>8} {'maxprob':>8} {'-entropy':>8} "
            f"{'logit_gap':>9} {'best_bl':>8} {'delta':>7} "
            f"{'Verdict':>10}"
        )
        lines.append("-" * 100)

        for r in eval_results:
            verdict = "CTR WINS" if r.ctr_wins else "NO WIN"
            lines.append(
                f"  {r.dataset_name:<22} {r.method:<14} "
                f"{r.rho_ctr:>+8.4f} {r.rho_margin:>+8.4f} "
                f"{r.rho_maxprob:>+8.4f} {r.rho_neg_entropy:>+8.4f} "
                f"{r.rho_logit_gap:>+9.4f} {r.best_baseline_rho:>+8.4f} "
                f"{r.rho_improvement:>+7.4f} {verdict:>10}"
            )

        lines.append("-" * 100)

        # Table 2: Token ranking quality
        lines.append("")
        lines.append(
            "2. Token Ranking Quality (true token rank under CTR "
            "among top-M):"
        )
        lines.append("-" * 90)
        lines.append(
            f"  {'Dataset':<22} {'Method':<14} {'mean_rank':>9} "
            f"{'med_rank':>9} {'MRR':>8} {'cos_margin':>10} "
            f"{'cos_med':>8}"
        )
        lines.append("-" * 90)

        for r in eval_results:
            lines.append(
                f"  {r.dataset_name:<22} {r.method:<14} "
                f"{r.mean_true_rank:>9.1f} {r.median_true_rank:>9.1f} "
                f"{r.mrr:>8.4f} {r.cos_margin_mean:>+10.4f} "
                f"{r.cos_margin_median:>+8.4f}"
            )

        lines.append("-" * 90)

        # Table 3: Pass@1
        lines.append("")
        lines.append("3. Pass@1 with CTR Reranking (alpha=0):")
        lines.append("-" * 72)
        lines.append(
            f"  {'Dataset':<22} {'Method':<14} {'base':>8} "
            f"{'reranked':>9} {'delta':>8} {'rerank%':>8}"
        )
        lines.append("-" * 72)

        for r in eval_results:
            delta = r.pass_at_1_reranked - r.pass_at_1_baseline
            lines.append(
                f"  {r.dataset_name:<22} {r.method:<14} "
                f"{r.pass_at_1_baseline:>8.4f} "
                f"{r.pass_at_1_reranked:>9.4f} {delta:>+8.4f} "
                f"{r.rerank_pct:>7.1%}"
            )

        lines.append("-" * 72)

        # Table 4: Alpha sweep
        has_sweep = any(r.alpha_sweep for r in eval_results)
        if has_sweep:
            lines.append("")
            lines.append(
                "4. Gated Logit Modulation "
                "(z'_i = z_i + alpha * cos(E[i], d_hat)):"
            )
            lines.append("-" * 80)
            lines.append(
                f"  {'Dataset':<22} {'Method':<10} {'alpha':>6} "
                f"{'pass@1':>8} {'delta':>8} {'rerank%':>8} {'Safe?':>6}"
            )
            lines.append("-" * 80)

            for r in eval_results:
                for alpha, metrics in sorted(r.alpha_sweep.items()):
                    delta = metrics["delta_pass_at_1"]
                    safe = "YES" if delta >= 0 else "NO"
                    lines.append(
                        f"  {r.dataset_name:<22} {r.method:<10} "
                        f"{alpha:>6.3f} {metrics['pass_at_1']:>8.4f} "
                        f"{delta:>+8.4f} "
                        f"{metrics['rerank_pct']:>7.1%} {safe:>6}"
                    )

            lines.append("-" * 80)

        # Table 5: GO/STOP verdicts
        lines.append("")
        lines.append("5. GO / STOP Gating:")
        lines.append("-" * 60)

        any_win = False
        for r in eval_results:
            if r.ctr_wins:
                lines.append(
                    f"  {r.dataset_name:<22} {r.method:<14} GO  "
                    f"(delta={r.rho_improvement:+.4f} vs "
                    f"{r.best_baseline_name})"
                )
                any_win = True
            else:
                lines.append(
                    f"  {r.dataset_name:<22} {r.method:<14} STOP "
                    f"(delta={r.rho_improvement:+.4f} vs "
                    f"{r.best_baseline_name})"
                )

        lines.append("-" * 60)

        if any_win:
            lines.append(
                "  >> CTR shows signal advantage — proceed with "
                "gated logit modulation."
            )
        else:
            lines.append(
                "  >> CTR does NOT beat baselines — goal direction "
                "from h_t is not discriminative."
            )
            lines.append(
                "  >> This confirms: oracle signal depends on "
                "genuinely future-only information."
            )

        lines.append("=" * 100)

        report = "\n".join(lines)
        print(report)
        return report

    # =====================================================================
    # Full Pipeline
    # =====================================================================

    def run_ctr_pipeline(
        model: Any,
        tokenizer: Any,
        datasets: Dict[str, List[Dict[str, Any]]],
        config: CTRConfig,
        device: str = "cpu",
        run_knn: bool = True,
        run_learned: bool = False,
        run_nonparametric: bool = True,
    ) -> List[CTREvalResult]:
        """Run the full CTR pipeline: collect, build, evaluate.

        Steps:
        1. Collect CTR samples from adapter datasets
        2. (Optional) Build kNN memory from train split, evaluate
        3. (Optional) Run nonparametric softmax-weighted baseline
        4. (Optional) Train ContrastiveGoalNet, evaluate

        Args:
            model: Transformer model.
            tokenizer: Tokenizer.
            datasets: Dict mapping mode name -> adapter samples.
            config: CTR configuration.
            device: Torch device.
            run_knn: Run kNN-Dir baseline.
            run_learned: Train and eval ContrastiveGoalNet.
            run_nonparametric: Run softmax-weighted baseline.

        Returns:
            List of CTREvalResult (one per method per dataset).
        """
        # Get vocab embeddings (cast to float32 — samples are float32;
        # model weights may be bfloat16 for Phi-3.5 etc.)
        vocab_emb = None
        if model is not None:
            try:
                vocab_emb = (
                    model.get_input_embeddings()
                    .weight.detach()
                    .float()
                )
            except Exception:
                pass
        if vocab_emb is None:
            sample_dataset = next(iter(datasets.values()), [])
            if sample_dataset:
                V = sample_dataset[0].get(
                    "logits", torch.zeros(1, 10)
                ).shape[-1]
                D = sample_dataset[0].get(
                    "hidden_state", torch.zeros(1, 64)
                ).shape[-1]
            else:
                V, D = 50, 64
            torch.manual_seed(config.seed)
            vocab_emb = torch.randn(V, D)

        all_results: List[CTREvalResult] = []

        for mode_name, dataset in datasets.items():
            print(f"\n--- CTR: {mode_name} ---")

            if not dataset or len(dataset) < 10:
                print(f"  Too few samples for {mode_name}, skipping")
                continue

            # Collect CTR samples
            all_samples = collect_ctr_from_adapter(dataset, config)
            if len(all_samples) < 10:
                print(f"  Collected too few ({len(all_samples)}), skipping")
                continue

            n_train = int(len(all_samples) * config.train_ratio)
            n_train = max(n_train, 2)
            train_samples = all_samples[:n_train]
            eval_samples = all_samples[n_train:]
            if len(eval_samples) < 3:
                eval_samples = all_samples[max(0, n_train - 3):]

            print(
                f"  Train: {len(train_samples)}, "
                f"Eval: {len(eval_samples)}"
            )

            # ---- Nonparametric: softmax-weighted ----
            if run_nonparametric:
                print(f"  Running softmax-weighted baseline...")

                def _softmax_wt_fn(h_batch):
                    # Need logits for this — approximate with
                    # h @ vocab_emb.T
                    ve = vocab_emb.to(
                        device=h_batch.device, dtype=h_batch.dtype,
                    )
                    approx_logits = h_batch @ ve.T
                    return softmax_weighted_direction(
                        approx_logits, ve, top_m=config.top_m,
                    )

                result_sw = evaluate_ctr(
                    d_hat_fn=_softmax_wt_fn,
                    samples=eval_samples,
                    vocab_embeddings=vocab_emb,
                    dataset_name=mode_name,
                    method="softmax_wt",
                    device=device,
                    top_m=config.top_m,
                    config=config,
                )
                all_results.append(result_sw)

            # ---- kNN-Dir ----
            if run_knn:
                print(
                    f"  Building kNN memory "
                    f"({len(train_samples)} entries, "
                    f"direction={config.direction_mode})..."
                )

                D = train_samples[0].h_t.shape[0]
                memory = KNNDirectionMemory(dim=D)

                # Add training samples in batches
                batch_h = []
                batch_d = []
                for s in train_samples:
                    batch_h.append(s.h_t)
                    batch_d.append(s.direction)
                    if len(batch_h) >= 1024:
                        memory.add_batch(
                            torch.stack(batch_h),
                            torch.stack(batch_d),
                        )
                        batch_h, batch_d = [], []
                if batch_h:
                    memory.add_batch(
                        torch.stack(batch_h),
                        torch.stack(batch_d),
                    )
                memory.finalize()

                print(
                    f"  Memory: {len(memory)} entries, "
                    f"querying with k={config.knn_k}"
                )

                def _knn_fn(h_batch, _mem=memory, _k=config.knn_k):
                    return _mem.query(h_batch, k=_k)

                result_knn = evaluate_ctr(
                    d_hat_fn=_knn_fn,
                    samples=eval_samples,
                    vocab_embeddings=vocab_emb,
                    dataset_name=mode_name,
                    method=f"knn_{config.direction_mode}",
                    device=device,
                    top_m=config.top_m,
                    config=config,
                )
                all_results.append(result_knn)

            # ---- Learned contrastive ----
            if run_learned:
                print(
                    f"  Training ContrastiveGoalNet "
                    f"(InfoNCE, {config.epochs} epochs)..."
                )

                net, train_stats = train_contrastive_goal_net(
                    train_samples, vocab_emb, config, device=device,
                )

                def _learned_fn(h_batch, _net=net):
                    return _net(h_batch.to(next(_net.parameters()).device))

                result_learned = evaluate_ctr(
                    d_hat_fn=_learned_fn,
                    samples=eval_samples,
                    vocab_embeddings=vocab_emb,
                    dataset_name=mode_name,
                    method="learned_infonce",
                    device=device,
                    top_m=config.top_m,
                    config=config,
                )
                result_learned.training_stats = train_stats
                all_results.append(result_learned)

        return all_results

else:
    # Stubs when PyTorch is not available
    class KNNDirectionMemory:  # type: ignore[no-redef]
        pass

    class ContrastiveGoalNet:  # type: ignore[no-redef]
        pass

    class CTRSample:  # type: ignore[no-redef]
        pass

    class CTREvalResult:  # type: ignore[no-redef]
        pass
