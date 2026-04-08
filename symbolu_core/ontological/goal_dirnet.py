#!/usr/bin/env python3
"""
GoalDirNet — Learned Future-Direction Predictor
=================================================

Trains a small MLP to predict the *direction* of the next hidden state
from past-only features, then feeds the prediction as a **goal vector
into the BCVF reranking pipeline** to test whether the learned direction
improves token selection.

Core idea
---------
At each token position ``t`` (teacher forcing):

* Target direction:  ``u_t = normalize(h_{t+1})``
* Predicted direction: ``u_hat_t = normalize(GoalDirNet(features_t))``

Evaluation uses ``u_hat_t`` as the goal vector in BCVF reranking::

    score_i = cos(normalize(W_e[i]), normalize(u_hat_t))

This is structurally homologous to the oracle BCVF mechanism::

    score_i = cos(W_e[i], mean_future_hidden)

The key metric is ``sb_learned = cos(W_e[predicted_token], u_hat_t)``,
whose Spearman rho with correctness is compared against logit-derived
baselines (margin, maxprob, entropy, logit_gap).

Note: the earlier ``s_goal = cos(h_t, u_hat_t)`` formulation was
**structurally incorrect** — it measured state stability (how much the
hidden state changes), not token correctness in embedding space.

Feature modes (past-only — no peeking at future tokens)
--------------------------------------------------------
* ``ht``             — just ``h_t`` (baseline)
* ``ht_mean``        — ``[h_t, mean_pool(h_{t-W+1}..h_t)]``
* ``ht_mean_logits`` — ``[h_t, mean_pool, entropy, margin, maxprob, logit_gap]``

Architecture
------------
2-layer MLP with GELU, hidden dim 512 (configurable), output normalised
to unit vector.  Loss = ``1 - cos(u_hat, u_target)`` averaged.

Usage::

    # Train + evaluate on dry-run data
    python scripts/run_bcvf_benchmarks.py --dry-run --train-goal-dirnet

    # Train on wikitext (Phi-3.5 — the model with oracle signal)
    python scripts/run_bcvf_benchmarks.py --mode wikitext --model phi3 \\
        --train-goal-dirnet --goal-features ht --train-goal-samples 10000

    # Full suite with alpha sweep (gated by sb_learned win)
    python scripts/run_bcvf_benchmarks.py --mode all --model phi3 \\
        --train-goal-dirnet --alpha-sweep 0.05 0.1 0.2
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
class GoalDirNetConfig:
    """Configuration for GoalDirNet training and evaluation.

    Attributes:
        feature_mode: Feature extraction mode (ht, ht_mean, ht_mean_logits).
        hidden_dim: MLP hidden layer size.
        window_size: Number of past hidden states for mean pooling.
        lr: Learning rate for Adam.
        epochs: Number of training epochs.
        batch_size: Mini-batch size.
        weight_decay: L2 regularisation.
        train_samples: Number of training positions to collect.
        eval_samples: Number of held-out evaluation positions.
        train_ratio: Fraction of collected data used for training.
        seed: Random seed for reproducibility.
        alpha_values: Alpha sweep values for logit modulation (gated).
        rho_improvement_threshold: Minimum rho improvement to declare win.
    """

    feature_mode: str = "ht"
    hidden_dim: int = 512
    window_size: int = 8
    lr: float = 1e-3
    epochs: int = 3
    batch_size: int = 256
    weight_decay: float = 1e-5
    train_samples: int = 50_000
    eval_samples: int = 5_000
    train_ratio: float = 0.8
    seed: int = 42
    alpha_values: List[float] = field(
        default_factory=lambda: [0.05, 0.1, 0.2]
    )
    rho_improvement_threshold: float = 0.05


# =========================================================================
# Feature Builder (past-only)
# =========================================================================

if PYTORCH_AVAILABLE:

    class GoalDirFeatureBuilder:
        """Extracts past-only features for GoalDirNet.

        All features are computable at step ``t`` without any future
        information.  The builder takes pre-collected hidden states and
        logits and produces feature tensors.

        Args:
            feature_mode: One of ``ht``, ``ht_mean``, ``ht_mean_logits``.
            window_size: Window for mean pooling in ``ht_mean`` modes.
        """

        def __init__(
            self,
            feature_mode: str = "ht",
            window_size: int = 8,
        ):
            if feature_mode not in ("ht", "ht_mean", "ht_mean_logits"):
                raise ValueError(
                    f"Unknown feature_mode: {feature_mode}. "
                    f"Expected ht, ht_mean, or ht_mean_logits."
                )
            self.feature_mode = feature_mode
            self.window_size = window_size

        def feature_dim(self, hidden_dim: int) -> int:
            """Compute the output feature dimension."""
            if self.feature_mode == "ht":
                return hidden_dim
            elif self.feature_mode == "ht_mean":
                return hidden_dim * 2
            elif self.feature_mode == "ht_mean_logits":
                return hidden_dim * 2 + 4  # +entropy, margin, maxprob, logit_gap
            else:
                return hidden_dim

        def build_features(
            self,
            hidden_states: torch.Tensor,
            logits: Optional[torch.Tensor] = None,
            positions: Optional[List[int]] = None,
        ) -> torch.Tensor:
            """Build feature vectors for the given positions.

            Args:
                hidden_states: [T, D] hidden states for the full sequence.
                logits: [T, V] logits for the full sequence (needed for
                    ``ht_mean_logits``).
                positions: List of positions to extract features for.
                    If None, extracts for all valid positions (0..T-2).

            Returns:
                features: [N, F] feature tensor where F = feature_dim(D).
            """
            T, D = hidden_states.shape

            if positions is None:
                positions = list(range(T - 1))

            features_list = []

            for t in positions:
                # h_t (always included)
                h_t = hidden_states[t]  # [D]

                if self.feature_mode == "ht":
                    features_list.append(h_t)

                elif self.feature_mode in ("ht_mean", "ht_mean_logits"):
                    # Mean pool of last W hidden states up to t
                    start = max(0, t - self.window_size + 1)
                    window = hidden_states[start : t + 1]  # [W', D]
                    mean_pool = window.mean(dim=0)  # [D]

                    if self.feature_mode == "ht_mean":
                        features_list.append(
                            torch.cat([h_t, mean_pool], dim=0)
                        )
                    else:
                        # ht_mean_logits: add logit-derived features
                        if logits is not None and t < logits.shape[0]:
                            logits_t = logits[t]  # [V]
                            probs = F.softmax(logits_t, dim=0)
                            sorted_probs, _ = probs.sort(descending=True)

                            maxprob = sorted_probs[0]
                            margin = sorted_probs[0] - sorted_probs[1] if sorted_probs.shape[0] > 1 else sorted_probs[0]
                            entropy = -(probs * torch.log(probs + 1e-10)).sum()

                            sorted_logits, _ = logits_t.sort(descending=True)
                            logit_gap = sorted_logits[0] - sorted_logits[1] if sorted_logits.shape[0] > 1 else sorted_logits[0]

                            logit_feats = torch.stack([
                                entropy, margin, maxprob, logit_gap
                            ])
                        else:
                            logit_feats = torch.zeros(4, device=h_t.device, dtype=h_t.dtype)

                        features_list.append(
                            torch.cat([h_t, mean_pool, logit_feats], dim=0)
                        )

            if not features_list:
                F_dim = self.feature_dim(D)
                return torch.zeros(0, F_dim, device=hidden_states.device, dtype=hidden_states.dtype)

            return torch.stack(features_list, dim=0)

        @staticmethod
        def compute_logit_baselines(
            logits: torch.Tensor,
        ) -> Dict[str, torch.Tensor]:
            """Compute logit-derived baseline confidence scores.

            Args:
                logits: [N, V] logits tensor.

            Returns:
                Dict with keys: margin, maxprob, neg_entropy, logit_gap.
                Each value is [N] shaped.
            """
            probs = F.softmax(logits, dim=-1)  # [N, V]
            sorted_probs, _ = probs.sort(dim=-1, descending=True)

            maxprob = sorted_probs[:, 0]  # [N]
            margin = sorted_probs[:, 0] - sorted_probs[:, 1]  # [N]

            entropy = -(probs * torch.log(probs + 1e-10)).sum(dim=-1)  # [N]
            neg_entropy = -entropy

            sorted_logits, _ = logits.sort(dim=-1, descending=True)
            logit_gap = sorted_logits[:, 0] - sorted_logits[:, 1]  # [N]

            return {
                "margin": margin,
                "maxprob": maxprob,
                "neg_entropy": neg_entropy,
                "logit_gap": logit_gap,
            }

    # =====================================================================
    # GoalDirNet Model
    # =====================================================================

    class GoalDirNet(nn.Module):
        """Small MLP that predicts the direction of the next hidden state.

        Architecture: input_dim -> hidden_dim (GELU) -> output_dim (GELU)
        -> L2-normalised output.

        Loss: ``L_dir = 1 - cos(u_hat, u_target)`` averaged.

        Args:
            input_dim: Dimensionality of input features.
            output_dim: Dimensionality of output (= hidden state dim D).
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
                nn.Linear(hidden_dim, output_dim),
                nn.GELU(),
            )
            self.output_dim = output_dim

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """Forward pass returning L2-normalised direction.

            Args:
                x: [B, input_dim] feature tensor.

            Returns:
                u_hat: [B, output_dim] unit vectors.
            """
            raw = self.net(x)  # [B, output_dim]
            return F.normalize(raw, p=2, dim=-1)

        @staticmethod
        def direction_loss(
            u_hat: torch.Tensor,
            u_target: torch.Tensor,
        ) -> torch.Tensor:
            """Cosine direction loss: 1 - cos(u_hat, u_target).

            Args:
                u_hat: [B, D] predicted directions (normalised).
                u_target: [B, D] target directions (normalised).

            Returns:
                Scalar loss (mean over batch).
            """
            cos_sim = F.cosine_similarity(u_hat, u_target, dim=-1)
            return (1.0 - cos_sim).mean()

    # =====================================================================
    # Data Collection
    # =====================================================================

    @dataclass
    class GoalDirSample:
        """One collected training/eval sample for GoalDirNet."""

        features: torch.Tensor      # [F] past-only features
        h_t: torch.Tensor           # [D] hidden state at t
        h_next: torch.Tensor        # [D] hidden state at t+1
        u_target: torch.Tensor      # [D] normalised h_{t+1}
        logits_t: torch.Tensor      # [V] logits at t
        correct: int                 # 1 if argmax(logits_t) == y_{t+1}
        ground_truth_token: int = 0  # actual ground truth token id

    def collect_goal_dir_samples(
        model: Any,
        tokenizer: Any,
        texts: List[str],
        feature_builder: GoalDirFeatureBuilder,
        n_samples: int,
        device: str = "cpu",
        max_seq_len: int = 512,
        seed: int = 42,
    ) -> List[GoalDirSample]:
        """Collect GoalDirNet training samples from text passages.

        Runs the model forward on each passage, extracts per-position
        (features, h_t, h_{t+1}, logits, correct) tuples.

        Args:
            model: Transformer model.
            tokenizer: Tokenizer.
            texts: Text passages to process.
            feature_builder: Feature extraction module.
            n_samples: Maximum number of samples to collect.
            device: Torch device.
            max_seq_len: Maximum sequence length.
            seed: Random seed.

        Returns:
            List of GoalDirSample.
        """
        torch.manual_seed(seed)
        samples: List[GoalDirSample] = []

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

            # Build features for all valid positions
            features = feature_builder.build_features(
                hidden_all, logits_all,
            )  # [T-1, F]

            positions_needed = min(T - 1, n_samples - len(samples))
            for t in range(positions_needed):
                h_t = hidden_all[t]
                h_next = hidden_all[t + 1]
                u_target = F.normalize(h_next.unsqueeze(0), p=2, dim=-1).squeeze(0)

                pred_token = logits_all[t].argmax().item()
                gt_token = int(ground_truth[t].item())
                correct = 1 if pred_token == gt_token else 0

                samples.append(GoalDirSample(
                    features=features[t].cpu(),
                    h_t=h_t.cpu(),
                    h_next=h_next.cpu(),
                    u_target=u_target.cpu(),
                    logits_t=logits_all[t].cpu(),
                    correct=correct,
                    ground_truth_token=gt_token,
                ))

            if (text_idx + 1) % 5 == 0 and len(samples) > 0:
                print(
                    f"  [goal_dirnet] Collected {len(samples)}/{n_samples}"
                )

        print(f"  [goal_dirnet] Total collected: {len(samples)} samples")
        return samples

    def collect_from_dataset_adapter(
        dataset: List[Dict[str, Any]],
        feature_builder: GoalDirFeatureBuilder,
        n_samples: int,
        seed: int = 42,
    ) -> List[GoalDirSample]:
        """Collect GoalDirNet samples from pre-built DatasetAdapter output.

        This works with the existing ``DatasetAdapter.from_dry_run()`` and
        similar methods that provide per-position hidden states and logits.

        For GoalDirNet we need consecutive hidden states (h_t, h_{t+1}),
        so we synthesise h_{t+1} as the next sample's hidden_state when
        samples come from the same sequence.  For dry-run / independent
        samples, we create synthetic targets.

        Args:
            dataset: List of dicts with hidden_state, logits, ground_truth.
            feature_builder: Feature builder.
            n_samples: Max samples.
            seed: Random seed.

        Returns:
            List of GoalDirSample.
        """
        torch.manual_seed(seed)
        samples: List[GoalDirSample] = []
        N = min(len(dataset), n_samples + 1)

        for i in range(min(N - 1, n_samples)):
            sample = dataset[i]
            next_sample = dataset[i + 1] if i + 1 < N else dataset[i]

            h_t = sample["hidden_state"]
            if isinstance(h_t, torch.Tensor):
                h_t = h_t.squeeze(0).float()
            else:
                h_t = torch.tensor(h_t, dtype=torch.float32).squeeze(0)

            h_next = next_sample["hidden_state"]
            if isinstance(h_next, torch.Tensor):
                h_next = h_next.squeeze(0).float()
            else:
                h_next = torch.tensor(h_next, dtype=torch.float32).squeeze(0)

            # Ensure 1D
            if h_t.dim() > 1:
                h_t = h_t.squeeze(0)
            if h_next.dim() > 1:
                h_next = h_next.squeeze(0)

            u_target = F.normalize(h_next.unsqueeze(0), p=2, dim=-1).squeeze(0)

            logits_t = sample.get("logits")
            if logits_t is not None:
                if isinstance(logits_t, torch.Tensor):
                    logits_t = logits_t.squeeze(0).float()
                else:
                    logits_t = torch.tensor(logits_t, dtype=torch.float32).squeeze(0)
                if logits_t.dim() > 1:
                    logits_t = logits_t.squeeze(0)
            else:
                logits_t = torch.zeros(10)

            gt = sample.get("ground_truth", 0)
            gt_token = int(gt)
            pred = logits_t.argmax().item()
            correct = 1 if pred == gt else 0

            D = h_t.shape[0]
            # Build feature for single position
            # Stack h_t as a single-position sequence
            h_seq = h_t.unsqueeze(0)  # [1, D]
            l_seq = logits_t.unsqueeze(0) if logits_t is not None else None  # [1, V]
            feat = feature_builder.build_features(h_seq, l_seq, positions=[0])
            if feat.shape[0] > 0:
                feat = feat[0]
            else:
                feat = h_t

            samples.append(GoalDirSample(
                features=feat.cpu(),
                h_t=h_t.cpu(),
                h_next=h_next.cpu(),
                u_target=u_target.cpu(),
                logits_t=logits_t.cpu(),
                correct=correct,
                ground_truth_token=gt_token,
            ))

        print(f"  [goal_dirnet] Collected {len(samples)} from adapter dataset")
        return samples

    # =====================================================================
    # Training Loop
    # =====================================================================

    def train_goal_dirnet(
        samples: List[GoalDirSample],
        config: GoalDirNetConfig,
        device: str = "cpu",
    ) -> Tuple[GoalDirNet, Dict[str, float]]:
        """Train GoalDirNet on collected samples.

        Args:
            samples: Training samples.
            config: Training configuration.
            device: Torch device.

        Returns:
            Tuple of (trained model, training stats dict).
        """
        if not samples:
            raise ValueError("No training samples provided")

        torch.manual_seed(config.seed)

        # Determine dimensions
        input_dim = samples[0].features.shape[0]
        output_dim = samples[0].u_target.shape[0]

        # Build tensors
        features = torch.stack([s.features for s in samples]).to(device)
        targets = torch.stack([s.u_target for s in samples]).to(device)

        N = features.shape[0]
        n_train = int(N * config.train_ratio)
        if n_train < 1:
            n_train = N

        train_features = features[:n_train]
        train_targets = targets[:n_train]

        # Create model
        model = GoalDirNet(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_dim=config.hidden_dim,
        ).to(device)

        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=config.lr,
            weight_decay=config.weight_decay,
        )

        # Training
        model.train()
        stats: Dict[str, float] = {
            "n_train": n_train,
            "n_total": N,
            "input_dim": input_dim,
            "output_dim": output_dim,
        }

        for epoch in range(config.epochs):
            epoch_loss = 0.0
            n_batches = 0

            # Shuffle
            perm = torch.randperm(n_train, device=device)
            train_features_shuffled = train_features[perm]
            train_targets_shuffled = train_targets[perm]

            for start in range(0, n_train, config.batch_size):
                end = min(start + config.batch_size, n_train)
                batch_feat = train_features_shuffled[start:end]
                batch_tgt = train_targets_shuffled[start:end]

                u_hat = model(batch_feat)
                loss = GoalDirNet.direction_loss(u_hat, batch_tgt)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()
                n_batches += 1

            avg_loss = epoch_loss / max(n_batches, 1)
            stats[f"loss_epoch_{epoch}"] = avg_loss
            print(f"  [goal_dirnet] Epoch {epoch + 1}/{config.epochs} "
                  f"loss={avg_loss:.6f}")

        stats["final_loss"] = stats.get(f"loss_epoch_{config.epochs - 1}", 0.0)
        model.eval()
        return model, stats

    # =====================================================================
    # Evaluation
    # =====================================================================

    @dataclass
    class GoalDirEvalResult:
        """Evaluation result for GoalDirNet vs baselines on one dataset.

        The primary metric is ``rho_sb_learned``: Spearman correlation between
        ``cos(W_e[predicted_token], u_hat)`` and correctness.  This measures
        whether the learned goal direction predicts token correctness via the
        same embedding-space mechanism as oracle BCVF.
        """

        dataset_name: str
        n_eval: int
        # Spearman rho with correctness
        rho_sb_learned: float = 0.0
        rho_margin: float = 0.0
        rho_maxprob: float = 0.0
        rho_neg_entropy: float = 0.0
        rho_logit_gap: float = 0.0
        # Calibration
        ece_maxprob: float = 0.0
        brier_maxprob: float = 0.0
        ece_sb_calibrated: float = 0.0
        brier_sb_calibrated: float = 0.0
        # Logistic calibration params
        cal_a: float = 1.0
        cal_b: float = 0.0
        # Gating verdict
        sb_learned_wins: bool = False
        best_baseline_rho: float = 0.0
        best_baseline_name: str = ""
        rho_improvement: float = 0.0
        # Pass@1 with learned-goal BCVF reranking
        pass_at_1_baseline: float = 0.0
        pass_at_1_reranked: float = 0.0
        rerank_pct: float = 0.0
        # Training stats
        training_stats: Dict[str, float] = field(default_factory=dict)
        # Alpha sweep results
        alpha_sweep: Dict[float, Dict[str, float]] = field(
            default_factory=dict
        )

    def evaluate_goal_dirnet(
        net: GoalDirNet,
        samples: List[GoalDirSample],
        vocab_embeddings: torch.Tensor,
        dataset_name: str = "unknown",
        device: str = "cpu",
        top_m: int = 500,
        beta: float = 0.2,
    ) -> GoalDirEvalResult:
        """Evaluate GoalDirNet by feeding u_hat as goal into BCVF reranking.

        Uses the structurally correct approach: rerank top-M candidates via
        ``sb = sigmoid(5 * cos(normalize(W_e[i]), normalize(u_hat_t)))``
        through the full BCVF Lagrangian, matching the oracle mechanism.

        Computes:
        1. ``sb_learned = cos(W_e[base_top1], u_hat)`` — Spearman rho
           with correctness (structurally homologous to oracle sb_rho)
        2. Reranked pass@1 using u_hat as BCVF goal vector
        3. Baselines: margin, maxprob, entropy, logit_gap

        Args:
            net: Trained GoalDirNet.
            samples: Evaluation samples (must have ground_truth_token).
            vocab_embeddings: [V, D] token embedding matrix (W_e).
            dataset_name: Name for reporting.
            device: Torch device.
            top_m: Number of top candidates for BCVF reranking.
            beta: BCVF beta parameter.

        Returns:
            GoalDirEvalResult with all metrics.
        """
        if not samples:
            return GoalDirEvalResult(dataset_name=dataset_name, n_eval=0)

        net.eval()
        net = net.to(device)
        vocab_embeddings = vocab_embeddings.to(device)

        features = torch.stack([s.features for s in samples]).to(device)
        h_ts = torch.stack([s.h_t for s in samples]).to(device)
        logits_all = torch.stack([s.logits_t for s in samples]).to(device)
        correct = np.array([s.correct for s in samples], dtype=np.float64)
        gt_tokens = np.array([s.ground_truth_token for s in samples])

        N, V = logits_all.shape

        with torch.no_grad():
            u_hat = net(features)  # [N, D] — already L2-normalized

        # ---- Normalize embeddings for clean cosine geometry ----
        vocab_normed = F.normalize(vocab_embeddings, p=2, dim=-1)  # [V, D]
        u_hat_normed = F.normalize(u_hat, p=2, dim=-1)  # enforce

        # ---- sb_learned: cos(W_e[base_top1], u_hat) for each sample ----
        base_preds = logits_all.argmax(dim=-1)  # [N]
        base_pred_embs = vocab_normed[base_preds]  # [N, D]
        sb_learned = F.cosine_similarity(
            base_pred_embs, u_hat_normed, dim=-1
        ).cpu().numpy()  # [N]

        # ---- BCVF reranking with learned goal ----
        top_m_actual = min(top_m, V)
        topM_scores, topM_indices = torch.topk(
            logits_all, top_m_actual, dim=-1
        )  # [N, M]
        topM_embs = vocab_normed[topM_indices]  # [N, M, D]

        # Forward score: sf = sigmoid(5 * cos(h_t, candidate))
        sf = torch.sigmoid(5.0 * F.cosine_similarity(
            h_ts.unsqueeze(1), topM_embs, dim=-1
        ))  # [N, M]

        # Backward score: sb = sigmoid(5 * cos(candidate, u_hat))
        sb = torch.sigmoid(5.0 * F.cosine_similarity(
            topM_embs, u_hat_normed.unsqueeze(1), dim=-1
        ))  # [N, M]

        # Lagrangian: L = (1-sf)^2 + (1-sb)^2 + 0.25*(sf-sb)^2
        L = (1.0 - sf) ** 2 + (1.0 - sb) ** 2 + 0.25 * (sf - sb) ** 2

        # Rerank: adjusted = base_logit - beta * L
        adjusted = topM_scores - beta * L
        best_rel = torch.argmax(adjusted, dim=-1)  # [N]
        reranked_tokens = topM_indices.gather(
            1, best_rel.unsqueeze(-1)
        ).squeeze(-1)  # [N]

        reranked_tokens_np = reranked_tokens.cpu().numpy()
        base_preds_np = base_preds.cpu().numpy()

        # ---- Pass@1 ----
        base_pass = float((base_preds_np == gt_tokens).mean())
        reranked_pass = float((reranked_tokens_np == gt_tokens).mean())
        rerank_changed = int((reranked_tokens_np != base_preds_np).sum())
        rerank_pct = rerank_changed / N if N > 0 else 0.0

        # ---- Baselines (logit-derived) ----
        baselines = GoalDirFeatureBuilder.compute_logit_baselines(logits_all)
        margin = baselines["margin"].cpu().numpy()
        maxprob = baselines["maxprob"].cpu().numpy()
        neg_entropy = baselines["neg_entropy"].cpu().numpy()
        logit_gap = baselines["logit_gap"].cpu().numpy()

        # ---- Spearman rho with correctness ----
        rho_sb_learned = spearman_rank_correlation(sb_learned, correct)
        rho_margin = spearman_rank_correlation(margin, correct)
        rho_maxprob = spearman_rank_correlation(maxprob, correct)
        rho_neg_entropy = spearman_rank_correlation(neg_entropy, correct)
        rho_logit_gap = spearman_rank_correlation(logit_gap, correct)

        # ---- Find best baseline ----
        baseline_rhos = {
            "margin": rho_margin,
            "maxprob": rho_maxprob,
            "neg_entropy": rho_neg_entropy,
            "logit_gap": rho_logit_gap,
        }
        best_name = max(baseline_rhos, key=lambda k: baseline_rhos[k])
        best_rho = baseline_rhos[best_name]

        rho_improvement = rho_sb_learned - best_rho
        sb_learned_wins = rho_improvement >= 0.05

        # ---- Calibration ----
        ece_maxprob = compute_ece(maxprob, correct)
        brier_maxprob = compute_brier(maxprob, correct)

        cal_a, cal_b = _fit_logistic_calibration(sb_learned, correct)
        sb_calibrated = _sigmoid(cal_a * sb_learned + cal_b)
        ece_sb_cal = compute_ece(sb_calibrated, correct)
        brier_sb_cal = compute_brier(sb_calibrated, correct)

        return GoalDirEvalResult(
            dataset_name=dataset_name,
            n_eval=len(samples),
            rho_sb_learned=rho_sb_learned,
            rho_margin=rho_margin,
            rho_maxprob=rho_maxprob,
            rho_neg_entropy=rho_neg_entropy,
            rho_logit_gap=rho_logit_gap,
            ece_maxprob=ece_maxprob,
            brier_maxprob=brier_maxprob,
            ece_sb_calibrated=ece_sb_cal,
            brier_sb_calibrated=brier_sb_cal,
            cal_a=cal_a,
            cal_b=cal_b,
            sb_learned_wins=sb_learned_wins,
            best_baseline_rho=best_rho,
            best_baseline_name=best_name,
            rho_improvement=rho_improvement,
            pass_at_1_baseline=base_pass,
            pass_at_1_reranked=reranked_pass,
            rerank_pct=rerank_pct,
        )

    # =====================================================================
    # Alpha Sweep (logit modulation — gated by GoalDirNet win)
    # =====================================================================

    def run_alpha_sweep(
        net: GoalDirNet,
        samples: List[GoalDirSample],
        vocab_embeddings: torch.Tensor,
        alpha_values: List[float],
        dataset_name: str = "unknown",
        device: str = "cpu",
    ) -> Dict[float, Dict[str, float]]:
        """Run logit modulation with alpha sweep.

        For each alpha, modulates logits:
            z'_i = z_i + alpha * cos(e_i, u_hat_t)

        Then computes pass@1 and rerank%.

        Args:
            net: Trained GoalDirNet.
            samples: Evaluation samples (with logits and correct labels).
            vocab_embeddings: [V, D] embedding matrix.
            alpha_values: List of alpha values to sweep.
            dataset_name: For reporting.
            device: Torch device.

        Returns:
            Dict mapping alpha -> {pass_at_1, rerank_pct, delta_pass_at_1}.
        """
        if not samples:
            return {}

        net.eval()
        net = net.to(device)
        vocab_embeddings = vocab_embeddings.to(device)

        features = torch.stack([s.features for s in samples]).to(device)
        logits_all = torch.stack([s.logits_t for s in samples]).to(device)
        correct = np.array([s.correct for s in samples], dtype=np.float64)

        # Baseline pass@1 (using original logits)
        baseline_preds = logits_all.argmax(dim=-1).cpu().numpy()
        gt = np.array([s.correct for s in samples])  # Already binary
        baseline_pass = float(correct.mean())

        with torch.no_grad():
            u_hat = net(features)  # [N, D]

        # Normalise vocab embeddings for cosine
        vocab_normed = F.normalize(vocab_embeddings, p=2, dim=-1)  # [V, D]

        results: Dict[float, Dict[str, float]] = {}

        for alpha in alpha_values:
            with torch.no_grad():
                # cos(e_i, u_hat_t) for all vocab tokens
                # u_hat: [N, D], vocab_normed: [V, D]
                cos_boost = torch.mm(u_hat, vocab_normed.T)  # [N, V]
                modulated_logits = logits_all + alpha * cos_boost

                mod_preds = modulated_logits.argmax(dim=-1).cpu().numpy()

            # Recompute correctness using actual ground truth tokens
            mod_correct = np.zeros(len(samples))
            rerank_count = 0
            for i, s in enumerate(samples):
                orig_pred = int(logits_all[i].argmax().item())
                mod_pred = int(mod_preds[i])
                gt_token = s.ground_truth_token

                if mod_pred != orig_pred:
                    rerank_count += 1

                mod_correct[i] = 1.0 if mod_pred == gt_token else 0.0

            mod_pass = float(mod_correct.mean())
            rerank_pct = rerank_count / len(samples) if samples else 0.0

            results[alpha] = {
                "pass_at_1": mod_pass,
                "delta_pass_at_1": mod_pass - baseline_pass,
                "rerank_pct": rerank_pct,
                "baseline_pass_at_1": baseline_pass,
            }

        return results

    # =====================================================================
    # Reporting
    # =====================================================================

    def print_goal_dirnet_report(
        eval_results: List[GoalDirEvalResult],
        alpha_results: Optional[Dict[str, Dict[float, Dict[str, float]]]] = None,
    ) -> str:
        """Print GoalDirNet evaluation report.

        Args:
            eval_results: List of per-dataset eval results.
            alpha_results: Optional dict mapping dataset -> alpha sweep results.

        Returns:
            Formatted report string.
        """
        lines = []
        lines.append("")
        lines.append("=" * 90)
        lines.append("GoalDirNet Evaluation Report (u_hat → BCVF goal)")
        lines.append("=" * 90)

        # Table 1: Spearman rho comparison
        lines.append("")
        lines.append("1. Predictive Signal (Spearman rho with correctness):")
        lines.append("   sb_learned = cos(W_e[pred_token], u_hat)")
        lines.append("-" * 90)
        lines.append(
            f"  {'Dataset':<20} {'sb_lrnd':>8} {'margin':>8} {'maxprob':>8} "
            f"{'-entropy':>8} {'logit_gap':>9} {'best_base':>10} {'delta':>7} {'Verdict':>10}"
        )
        lines.append("-" * 90)

        for r in eval_results:
            verdict = "GO" if r.sb_learned_wins else "NO WIN"
            lines.append(
                f"  {r.dataset_name:<20} {r.rho_sb_learned:>+8.4f} "
                f"{r.rho_margin:>+8.4f} {r.rho_maxprob:>+8.4f} "
                f"{r.rho_neg_entropy:>+8.4f} {r.rho_logit_gap:>+9.4f} "
                f"{r.best_baseline_rho:>+10.4f} {r.rho_improvement:>+7.4f} "
                f"{verdict:>10}"
            )

        lines.append("-" * 90)

        # Table 2: Pass@1 with learned-goal BCVF reranking
        lines.append("")
        lines.append("2. Pass@1 with Learned-Goal BCVF Reranking:")
        lines.append("-" * 72)
        lines.append(
            f"  {'Dataset':<20} {'base':>8} {'reranked':>9} "
            f"{'delta':>8} {'rerank%':>8} {'Verdict':>10}"
        )
        lines.append("-" * 72)

        for r in eval_results:
            delta = r.pass_at_1_reranked - r.pass_at_1_baseline
            if delta > 0.005:
                v = "IMPROVED"
            elif delta < -0.005:
                v = "REGRESSED"
            else:
                v = "NEUTRAL"
            lines.append(
                f"  {r.dataset_name:<20} {r.pass_at_1_baseline:>8.4f} "
                f"{r.pass_at_1_reranked:>9.4f} {delta:>+8.4f} "
                f"{r.rerank_pct:>7.1%} {v:>10}"
            )

        lines.append("-" * 72)

        # Table 3: Calibration
        lines.append("")
        lines.append("3. Calibration (ECE / Brier — lower is better):")
        lines.append("-" * 72)
        lines.append(
            f"  {'Dataset':<20} {'ECE(maxprob)':>12} {'ECE(sb_lrn)':>12} "
            f"{'Brier(mp)':>10} {'Brier(sb)':>10}"
        )
        lines.append("-" * 72)

        for r in eval_results:
            lines.append(
                f"  {r.dataset_name:<20} {r.ece_maxprob:>12.4f} "
                f"{r.ece_sb_calibrated:>12.4f} "
                f"{r.brier_maxprob:>10.4f} {r.brier_sb_calibrated:>10.4f}"
            )

        lines.append("-" * 72)

        # Table 4: GO/STOP verdicts
        lines.append("")
        lines.append("4. GO / STOP Gating:")
        lines.append("-" * 60)

        any_win = False
        for r in eval_results:
            if r.sb_learned_wins:
                lines.append(
                    f"  {r.dataset_name:<20} GO  — sb_learned beats "
                    f"{r.best_baseline_name} by {r.rho_improvement:+.4f}"
                )
                any_win = True
            else:
                lines.append(
                    f"  {r.dataset_name:<20} STOP — no signal win "
                    f"(delta={r.rho_improvement:+.4f}, "
                    f"best={r.best_baseline_name})"
                )

        lines.append("-" * 60)

        if any_win:
            lines.append(
                "  >> GoalDirNet sb_learned shows signal advantage — "
                "proceed with logit modulation."
            )
        else:
            lines.append(
                "  >> GoalDirNet does NOT beat baselines — "
                "skip logit modulation."
            )

        # Table 5: Alpha sweep (if present)
        if alpha_results:
            lines.append("")
            lines.append("5. Alpha Sweep (logit modulation — gated by GoalDirNet win):")
            lines.append("-" * 80)
            lines.append(
                f"  {'Dataset':<20} {'alpha':>6} {'pass@1':>8} "
                f"{'delta':>8} {'rerank%':>8} {'Safe?':>6}"
            )
            lines.append("-" * 80)

            for ds_name, sweep in alpha_results.items():
                for alpha, metrics in sorted(sweep.items()):
                    delta = metrics["delta_pass_at_1"]
                    safe = "YES" if delta >= 0 else "NO"
                    lines.append(
                        f"  {ds_name:<20} {alpha:>6.2f} "
                        f"{metrics['pass_at_1']:>8.4f} "
                        f"{delta:>+8.4f} "
                        f"{metrics['rerank_pct']:>7.1%} "
                        f"{safe:>6}"
                    )

            lines.append("-" * 80)

            # Check HumanEval safety
            for ds_name, sweep in alpha_results.items():
                if "humaneval" in ds_name.lower():
                    for alpha, metrics in sweep.items():
                        if metrics["delta_pass_at_1"] < 0:
                            lines.append(
                                f"  !! STOP: HumanEval pass@1 regression "
                                f"at alpha={alpha} — unsafe for code"
                            )

        lines.append("")
        lines.append("=" * 90)

        report = "\n".join(lines)
        print(report)
        return report

    # =====================================================================
    # Logistic calibration helpers
    # =====================================================================

    def _sigmoid(x: np.ndarray) -> np.ndarray:
        """Numerically stable sigmoid."""
        return np.where(
            x >= 0,
            1.0 / (1.0 + np.exp(-x)),
            np.exp(x) / (1.0 + np.exp(x)),
        )

    def _fit_logistic_calibration(
        scores: np.ndarray,
        labels: np.ndarray,
        max_iter: int = 100,
        lr: float = 0.1,
    ) -> Tuple[float, float]:
        """Fit simple logistic calibration: sigmoid(a*score + b).

        Uses gradient descent on binary cross-entropy.

        Args:
            scores: [N] raw scores.
            labels: [N] binary labels (0 or 1).
            max_iter: Maximum optimisation iterations.
            lr: Learning rate.

        Returns:
            Tuple (a, b) calibration parameters.
        """
        scores = np.asarray(scores, dtype=np.float64)
        labels = np.asarray(labels, dtype=np.float64)
        N = len(scores)
        if N == 0:
            return 1.0, 0.0

        a = 1.0
        b = 0.0

        for _ in range(max_iter):
            z = a * scores + b
            p = _sigmoid(z)
            p = np.clip(p, 1e-7, 1 - 1e-7)

            # Gradients of BCE
            err = p - labels
            grad_a = float(np.dot(err, scores) / N)
            grad_b = float(err.mean())

            a -= lr * grad_a
            b -= lr * grad_b

        return float(a), float(b)

    # =====================================================================
    # Full Pipeline: train + eval + report
    # =====================================================================

    def run_goal_dirnet_pipeline(
        model: Any,
        tokenizer: Any,
        datasets: Dict[str, List[Dict[str, Any]]],
        config: GoalDirNetConfig,
        device: str = "cpu",
        run_alpha_sweep_flag: bool = False,
    ) -> Tuple[List[GoalDirEvalResult], Optional[Dict[str, Dict[float, Dict[str, float]]]]]:
        """Run the full GoalDirNet pipeline: collect, train, evaluate.

        Args:
            model: Transformer model (or dry-run stub).
            tokenizer: Tokenizer.
            datasets: Dict mapping mode name -> list of adapter samples.
            config: GoalDirNet configuration.
            device: Torch device.
            run_alpha_sweep_flag: Whether to run alpha sweep (gated).

        Returns:
            Tuple of (eval_results, alpha_results_or_None).
        """
        feature_builder = GoalDirFeatureBuilder(
            feature_mode=config.feature_mode,
            window_size=config.window_size,
        )

        # Get vocab embeddings (W_e) from model — needed for BCVF reranking
        vocab_emb = None
        if model is not None:
            try:
                vocab_emb = model.get_input_embeddings().weight.detach()
            except Exception:
                pass
        if vocab_emb is None:
            # Fallback for dry-run or missing model
            sample_dataset = next(iter(datasets.values()), [])
            if sample_dataset:
                V = sample_dataset[0].get("logits", torch.zeros(1, 10)).shape[-1]
                D = sample_dataset[0].get("hidden_state", torch.zeros(1, 64)).shape[-1]
            else:
                V, D = 50, 64
            torch.manual_seed(config.seed)
            vocab_emb = torch.randn(V, D)

        all_eval_results: List[GoalDirEvalResult] = []
        alpha_results: Dict[str, Dict[float, Dict[str, float]]] = {}

        for mode_name, dataset in datasets.items():
            print(f"\n--- GoalDirNet: {mode_name} ---")

            if not dataset:
                print(f"  No data for {mode_name}, skipping")
                continue

            # Collect samples from adapter dataset
            n_total = min(
                config.train_samples + config.eval_samples,
                len(dataset) - 1,
            )
            if n_total < 10:
                print(f"  Too few samples ({n_total}) for {mode_name}, skipping")
                continue

            all_samples = collect_from_dataset_adapter(
                dataset, feature_builder,
                n_samples=n_total,
                seed=config.seed,
            )

            if len(all_samples) < 10:
                print(f"  Collected too few ({len(all_samples)}), skipping")
                continue

            # Split train / eval
            n_train = int(len(all_samples) * config.train_ratio)
            n_train = max(n_train, 2)
            train_samples = all_samples[:n_train]
            eval_samples = all_samples[n_train:]
            if len(eval_samples) < 3:
                eval_samples = all_samples[n_train - 3:]

            print(f"  Train: {len(train_samples)}, Eval: {len(eval_samples)}")

            # Train
            net, train_stats = train_goal_dirnet(
                train_samples, config, device=device,
            )

            # Evaluate — feed u_hat as BCVF goal, rerank via cos(W_e, u_hat)
            eval_result = evaluate_goal_dirnet(
                net, eval_samples,
                vocab_embeddings=vocab_emb,
                dataset_name=mode_name,
                device=device,
            )
            eval_result.training_stats = train_stats
            all_eval_results.append(eval_result)

            # Alpha sweep (gated by sb_learned win)
            if run_alpha_sweep_flag and eval_result.sb_learned_wins:
                print(f"  [goal_dirnet] sb_learned WINS on {mode_name}, "
                      f"running alpha sweep...")

                sweep = run_alpha_sweep(
                    net, eval_samples, vocab_emb,
                    alpha_values=config.alpha_values,
                    dataset_name=mode_name,
                    device=device,
                )
                alpha_results[mode_name] = sweep
            elif run_alpha_sweep_flag:
                print(f"  [goal_dirnet] sb_learned does NOT win on "
                      f"{mode_name}, skipping alpha sweep")

        return all_eval_results, alpha_results if alpha_results else None

else:
    # Stubs when PyTorch is not available
    class GoalDirFeatureBuilder:  # type: ignore[no-redef]
        pass

    class GoalDirNet:  # type: ignore[no-redef]
        pass

    class GoalDirSample:  # type: ignore[no-redef]
        pass

    class GoalDirEvalResult:  # type: ignore[no-redef]
        pass
