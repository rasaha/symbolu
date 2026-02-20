#!/usr/bin/env python3
"""
BCVF Contrastive Structural Pressure on Representations
=========================================================

Training objective that forces hidden-state geometry to separate
"BCVF-aligned" vs "BCVF-misaligned" continuations for the same prefix.

This is NOT scalar guidance or reranking — it is direct contrastive
pressure on the model's internal representations (hidden states).

Core idea:
    For a prefix x[0:t], the hidden state h_t is projected to a
    low-dimensional representation r_t = normalize(P(h_t)).
    The objective enforces that r_t is closer (cosine) to the
    BCVF-aligned future continuation than to BCVF-misaligned ones.

Loss:
    L_rep = Σ_k w_k * relu(margin - cos(r_t, r_pos) + cos(r_t, r_neg_k))

    where w_k = sigmoid(alpha * (s_pos - s_neg_k)) weights negatives
    by BCVF score difference (harder negatives contribute less).

Negative sampling:
    Stage A: Sample K_pool=256 candidates from model's top-p distribution.
    Stage B: Select K negatives via BCVF scoring:
        - K/2 "near-miss" (highest s_neg below s_pos)
        - K/2 "bad" negatives (lowest s_neg)

Usage:
    from symbolu.ontological.bcvf_contrastive import (
        BCVFContrastiveConfig,
        BCVFContrastiveHead,
        BCVFNegativeSampler,
        compute_bcvf_contrastive_loss,
        log_bcvf_contrastive_diagnostics,
    )
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False


# =========================================================================
# Configuration
# =========================================================================


@dataclass
class BCVFContrastiveConfig:
    """Configuration for BCVF contrastive structural pressure.

    Attributes:
        use_bcvf_contrastive: Master toggle for the contrastive objective.
        lambda_rep: Weight for contrastive loss in total loss.
        K: Number of negatives per sampled position.
        K_pool: Candidate pool size for Stage A sampling.
        margin: Margin for the ranking loss.
        alpha: Temperature for BCVF-based negative weighting.
        eta: Scale for token-embedding injection in proxy r_neg.
        d_r: Projection output dimensionality.
        T_sample: Number of positions per sequence to sample.
        projector_type: "linear" or "mlp" for the projection head.
        top_p: Top-p for Stage A candidate sampling.
        use_exact_neg: If True, use exact 1-step forward for negatives
            (expensive). Default False uses proxy method.
    """

    use_bcvf_contrastive: bool = False
    lambda_rep: float = 0.1
    K: int = 16
    K_pool: int = 256
    margin: float = 0.15
    alpha: float = 2.0
    eta: float = 0.3
    d_r: int = 128
    T_sample: int = 4
    projector_type: str = "mlp"  # "linear" or "mlp"
    top_p: float = 0.95
    use_exact_neg: bool = False


# =========================================================================
# Projection Head
# =========================================================================

if PYTORCH_AVAILABLE:

    class BCVFContrastiveHead(nn.Module):
        """Projection head mapping hidden states to contrastive space.

        Projects h_t (shape [*, D]) to r_t (shape [*, d_r]) with L2
        normalization. Supports linear or 2-layer MLP with GELU.

        Args:
            hidden_dim: Model hidden dimension D.
            proj_dim: Output projection dimension d_r.
            projector_type: "linear" or "mlp".
        """

        def __init__(
            self,
            hidden_dim: int,
            proj_dim: int = 128,
            projector_type: str = "mlp",
        ):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.proj_dim = proj_dim

            if projector_type == "linear":
                self.projector = nn.Linear(hidden_dim, proj_dim)
            elif projector_type == "mlp":
                self.projector = nn.Sequential(
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.GELU(),
                    nn.Linear(hidden_dim, proj_dim),
                )
            else:
                raise ValueError(
                    f"Unknown projector_type: {projector_type}. "
                    f"Use 'linear' or 'mlp'."
                )

            self._init_weights()

        def _init_weights(self):
            """Initialize with small weights to avoid disrupting early training."""
            for m in self.modules():
                if isinstance(m, nn.Linear):
                    nn.init.normal_(m.weight, std=0.02)
                    if m.bias is not None:
                        nn.init.zeros_(m.bias)

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            """Project and normalize hidden states.

            Args:
                h: [*, D] hidden states.

            Returns:
                r: [*, d_r] L2-normalized projections.
            """
            return F.normalize(self.projector(h.float()), p=2, dim=-1)

    # =====================================================================
    # BCVF Scorer Adapter
    # =====================================================================

    def score_bcvf_for_token(
        prefix_text: str,
        token_text: str,
    ) -> float:
        """Score a (prefix, next-token) pair using BCVF.

        Uses the ConsistencyLagrangian from the existing BCVF module.
        The forward score is based on fluency/coherence of prefix+token,
        the backward score on goal alignment.

        For training efficiency, this returns consistency_weight directly.

        Args:
            prefix_text: The prefix context as text.
            token_text: The candidate next token as text.

        Returns:
            Score in [0, 1] where higher = more BCVF-aligned.
        """
        from symbolu.ontological.bcvf import (
            ForwardScorer,
            BackwardScorer,
            ConsistencyLagrangian,
        )

        combined = prefix_text + token_text
        fwd = ForwardScorer(use_ontological=False)
        bwd = BackwardScorer()
        lagrangian = ConsistencyLagrangian()

        sf = fwd.score(combined)
        sb = bwd.score(combined, goal=prefix_text)
        score_obj = lagrangian.score_candidate(sf, sb)
        return score_obj.consistency_weight

    def score_bcvf_batch_from_logits(
        logits_t: torch.Tensor,
        token_ids: torch.Tensor,
        tokenizer: Any = None,
        prefix_ids: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Fast approximate BCVF scoring using logit-based heuristics.

        When a tokenizer is not available or for speed, we use a proxy:
        BCVF score ~ sigmoid(logit_rank_normalized) * fluency_proxy.

        This captures the key property: tokens the model considers likely
        AND that maintain coherence get higher scores.

        Args:
            logits_t: [B, V] logits at position t.
            token_ids: [B, K] candidate token IDs to score.
            tokenizer: Optional tokenizer for text-based scoring.
            prefix_ids: Optional [B, T] prefix token IDs.

        Returns:
            scores: [B, K] BCVF scores in [0, 1].
        """
        B, V = logits_t.shape
        K = token_ids.shape[1]

        # Gather logits for candidate tokens
        candidate_logits = logits_t.gather(
            1, token_ids.clamp(0, V - 1)
        )  # [B, K]

        # Normalize to [0, 1] range using sigmoid of z-scored logits
        logit_mean = logits_t.mean(dim=-1, keepdim=True)  # [B, 1]
        logit_std = logits_t.std(dim=-1, keepdim=True).clamp(min=1e-6)  # [B, 1]
        z_scores = (candidate_logits - logit_mean) / logit_std  # [B, K]

        # BCVF proxy: sigmoid maps z-scores to (0, 1)
        # High logit -> high forward feasibility (sf)
        # We also penalize extreme tokens (very high logit) slightly
        # to capture the consistency term (sf ≈ sb)
        sf_proxy = torch.sigmoid(z_scores)  # [B, K]

        # Backward proxy: tokens closer to the distribution mode
        # are more "goal-aligned" (consistency with forward)
        probs = F.softmax(logits_t, dim=-1)  # [B, V]
        candidate_probs = probs.gather(1, token_ids.clamp(0, V - 1))  # [B, K]
        max_prob = probs.max(dim=-1, keepdim=True).values  # [B, 1]
        sb_proxy = (candidate_probs / max_prob.clamp(min=1e-8)).clamp(0, 1)  # [B, K]

        # Consistency Lagrangian proxy: w = exp(-beta * L)
        # L = (1-sf)^2 + (1-sb)^2 + 0.5*(sf-sb)^2
        beta = 2.0
        L = (1 - sf_proxy) ** 2 + (1 - sb_proxy) ** 2 + 0.5 * (sf_proxy - sb_proxy) ** 2
        scores = torch.exp(-beta * L)  # [B, K]

        return scores.detach()

    # =====================================================================
    # Negative Sampler
    # =====================================================================

    class BCVFNegativeSampler:
        """Two-stage negative sampler for contrastive training.

        Stage A: Sample K_pool candidates from model's top-p distribution.
        Stage B: Select K negatives via BCVF scoring:
            - K/2 near-miss (highest BCVF below positive)
            - K/2 bad (lowest BCVF)

        Args:
            K: Number of negatives to return.
            K_pool: Candidate pool size.
            top_p: Nucleus sampling threshold.
        """

        def __init__(
            self,
            K: int = 16,
            K_pool: int = 256,
            top_p: float = 0.95,
        ):
            self.K = K
            self.K_pool = K_pool
            self.top_p = top_p

        @torch.no_grad()
        def sample(
            self,
            logits_t: torch.Tensor,
            ground_truth_ids: torch.Tensor,
            tokenizer: Any = None,
            prefix_ids: Optional[torch.Tensor] = None,
        ) -> Tuple[torch.Tensor, torch.Tensor]:
            """Sample K negatives per batch element.

            Args:
                logits_t: [B, V] logits at position t.
                ground_truth_ids: [B] ground truth token IDs.
                tokenizer: Optional tokenizer for BCVF scoring.
                prefix_ids: Optional [B, T] prefix for BCVF scoring.

            Returns:
                neg_ids: [B, K] selected negative token IDs.
                neg_bcvf_scores: [B, K] BCVF scores for negatives.
            """
            B, V = logits_t.shape
            device = logits_t.device
            K = self.K
            K_half = K // 2

            # Stage A: Top-p sampling to get candidate pool
            sorted_logits, sorted_indices = logits_t.sort(
                dim=-1, descending=True
            )
            sorted_probs = F.softmax(sorted_logits, dim=-1)
            cumulative_probs = sorted_probs.cumsum(dim=-1)

            # Mask tokens beyond top-p
            K_pool = min(self.K_pool, V)

            # Take top-K_pool candidates (approximation of top-p)
            pool_indices = sorted_indices[:, :K_pool]  # [B, K_pool]

            # Remove ground truth from pool
            gt_expanded = ground_truth_ids.unsqueeze(1).expand_as(pool_indices)
            gt_mask = pool_indices == gt_expanded
            # Replace GT positions with a random token from pool
            replacement = sorted_indices[:, K_pool:K_pool + 1].expand_as(pool_indices)
            # Only replace where GT was found; use pool's last token as fallback
            fallback = sorted_indices[:, min(K_pool, V - 1)].unsqueeze(1).expand_as(pool_indices)
            if K_pool < V:
                pool_indices = torch.where(gt_mask, replacement, pool_indices)
            else:
                pool_indices = torch.where(gt_mask, fallback, pool_indices)

            # Stage B: BCVF scoring
            bcvf_scores = score_bcvf_batch_from_logits(
                logits_t, pool_indices, tokenizer=tokenizer,
                prefix_ids=prefix_ids,
            )  # [B, K_pool]

            # Get positive BCVF score for comparison
            gt_score = score_bcvf_batch_from_logits(
                logits_t,
                ground_truth_ids.unsqueeze(1),
                tokenizer=tokenizer,
                prefix_ids=prefix_ids,
            ).squeeze(1)  # [B]

            # Select negatives:
            # Near-miss: highest BCVF below s_pos
            # Bad: lowest BCVF
            neg_ids_list = []
            neg_scores_list = []

            for b in range(B):
                scores_b = bcvf_scores[b]  # [K_pool]
                ids_b = pool_indices[b]  # [K_pool]
                s_pos_b = gt_score[b]

                # Near-miss: below s_pos, sorted descending
                below_mask = scores_b < s_pos_b
                if below_mask.sum() >= K_half:
                    below_scores = scores_b[below_mask]
                    below_ids = ids_b[below_mask]
                    _, near_miss_order = below_scores.sort(descending=True)
                    near_miss_idx = near_miss_order[:K_half]
                    nm_ids = below_ids[near_miss_idx]
                    nm_scores = below_scores[near_miss_idx]
                else:
                    # Not enough below s_pos; take top-K_half by score
                    _, top_order = scores_b.sort(descending=True)
                    nm_ids = ids_b[top_order[:K_half]]
                    nm_scores = scores_b[top_order[:K_half]]

                # Bad: lowest BCVF
                _, bad_order = scores_b.sort(descending=False)
                bad_ids = ids_b[bad_order[:K_half]]
                bad_scores = scores_b[bad_order[:K_half]]

                # Combine
                selected_ids = torch.cat([nm_ids, bad_ids])[:K]
                selected_scores = torch.cat([nm_scores, bad_scores])[:K]

                # Pad if needed
                if selected_ids.shape[0] < K:
                    pad_size = K - selected_ids.shape[0]
                    # Pad with random pool tokens
                    perm = torch.randperm(K_pool, device=device)[:pad_size]
                    selected_ids = torch.cat([selected_ids, ids_b[perm]])
                    selected_scores = torch.cat([selected_scores, scores_b[perm]])

                neg_ids_list.append(selected_ids)
                neg_scores_list.append(selected_scores)

            neg_ids = torch.stack(neg_ids_list)  # [B, K]
            neg_bcvf_scores = torch.stack(neg_scores_list)  # [B, K]

            return neg_ids, neg_bcvf_scores

    # =====================================================================
    # Contrastive Loss Computation
    # =====================================================================

    def compute_bcvf_contrastive_loss(
        h_all: torch.Tensor,
        logits_all: torch.Tensor,
        labels: torch.Tensor,
        contrastive_head: BCVFContrastiveHead,
        token_embeddings: torch.Tensor,
        config: BCVFContrastiveConfig,
        sampler: BCVFNegativeSampler,
        tokenizer: Any = None,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """Compute BCVF contrastive loss on representation geometry.

        Samples T_sample positions per sequence, computes contrastive
        loss between BCVF-aligned and BCVF-misaligned continuations.

        Args:
            h_all: [B, T, D] hidden states from the backbone (last layer
                before lm_head, or any chosen layer).
            logits_all: [B, T, V] logits from the model.
            labels: [B, T] ground truth token IDs (-100 for padding).
            contrastive_head: BCVFContrastiveHead projection module.
            token_embeddings: [V, D] token embedding matrix.
            config: BCVFContrastiveConfig.
            sampler: BCVFNegativeSampler.
            tokenizer: Optional tokenizer.

        Returns:
            loss: Scalar contrastive loss.
            diagnostics: Dict of diagnostic metrics.
        """
        B, T, D = h_all.shape
        V = logits_all.shape[-1]
        device = h_all.device
        K = config.K

        # Find valid positions: labels[t+1] != -100 and t < T-1
        # We need h_t, h_{t+1}, and labels[t] (which is the gt for position t)
        valid_mask = (labels != -100)  # [B, T]

        # We need positions where both t and t+1 are valid
        valid_positions = valid_mask[:, :-1] & valid_mask[:, 1:]  # [B, T-1]

        total_loss = torch.tensor(0.0, device=device)
        n_sampled = 0

        # Diagnostics accumulators
        cos_pos_sum = 0.0
        cos_neg_sum = 0.0
        bcvf_pos_sum = 0.0
        bcvf_neg_sum = 0.0
        bcvf_neg_sq_sum = 0.0
        w_k_std_sum = 0.0
        logit_std_sum = 0.0
        entropy_sum = 0.0
        bcvf_logit_norm_corr_sum = 0.0
        r_dim_std_sum = 0.0
        n_diag = 0

        for b in range(B):
            # Get valid positions for this batch element
            valid_t = valid_positions[b].nonzero(as_tuple=True)[0]  # [N_valid]

            if len(valid_t) < 1:
                continue

            # Sample T_sample positions
            n_sample = min(config.T_sample, len(valid_t))
            perm = torch.randperm(len(valid_t), device=device)[:n_sample]
            sampled_t = valid_t[perm]  # [T_sample]

            for t_idx in sampled_t:
                t = t_idx.item()

                # Extract hidden states
                h_t = h_all[b, t]  # [D]
                h_tp1 = h_all[b, t + 1]  # [D]

                # Project
                r_t = contrastive_head(h_t.unsqueeze(0))  # [1, d_r]
                r_pos = contrastive_head(h_tp1.unsqueeze(0))  # [1, d_r]

                # Get logits and ground truth for this position
                logits_t = logits_all[b, t].unsqueeze(0)  # [1, V]
                gt_id = labels[b, t + 1]  # scalar (ground truth for t+1 is labels[t+1])

                if gt_id.item() == -100:
                    continue

                # Sample negatives
                neg_ids, neg_bcvf_scores = sampler.sample(
                    logits_t,
                    gt_id.unsqueeze(0),
                    tokenizer=tokenizer,
                )  # [1, K], [1, K]

                neg_ids = neg_ids[0]  # [K]
                neg_bcvf_scores = neg_bcvf_scores[0]  # [K]

                # Compute positive BCVF score
                pos_bcvf = score_bcvf_batch_from_logits(
                    logits_t,
                    gt_id.unsqueeze(0).unsqueeze(0),
                ).squeeze()  # scalar

                # Compute r_neg using proxy method:
                # Use interpolation: h_neg = (1-eta)*h_t + eta*E[y_neg]
                # This creates meaningfully distinct representations while
                # staying in the same space. The positive uses h_{t+1} from
                # the actual forward pass, so the contrast is between
                # "real next-step hidden" vs "hypothetical next-step hidden".
                neg_embeds = token_embeddings[neg_ids]  # [K, D]
                # Scale embeddings to match h_t norm for balanced interpolation
                h_t_norm = h_t.norm().clamp(min=1e-6)
                neg_embeds_scaled = F.normalize(neg_embeds, dim=-1) * h_t_norm
                h_t_expanded = h_t.unsqueeze(0).expand(K, -1)  # [K, D]
                h_neg_proxy = (1 - config.eta) * h_t_expanded + config.eta * neg_embeds_scaled
                r_neg = contrastive_head(h_neg_proxy)  # [K, d_r]

                # Compute cosine similarities
                cos_pos = F.cosine_similarity(
                    r_t, r_pos, dim=-1
                )  # [1]
                cos_neg = F.cosine_similarity(
                    r_t.expand(K, -1), r_neg, dim=-1
                )  # [K]

                # Compute BCVF-based weights
                # w_k = sigmoid(alpha * (s_pos - s_neg_k))
                s_diff = pos_bcvf - neg_bcvf_scores  # [K]
                w_k = torch.sigmoid(config.alpha * s_diff)  # [K]

                # Margin ranking loss:
                # L_rep = Σ_k w_k * relu(margin - cos_pos + cos_neg_k)
                per_neg_loss = w_k * F.relu(
                    config.margin - cos_pos + cos_neg
                )  # [K]
                position_loss = per_neg_loss.sum()

                total_loss = total_loss + position_loss
                n_sampled += 1

                # Accumulate diagnostics
                cos_pos_sum += cos_pos.item()
                cos_neg_sum += cos_neg.mean().item()
                bcvf_pos_sum += pos_bcvf.item()
                bcvf_neg_sum += neg_bcvf_scores.mean().item()
                bcvf_neg_sq_sum += (neg_bcvf_scores ** 2).mean().item()
                w_k_std_sum += w_k.std().item()

                # Calibration artifact checks
                with torch.no_grad():
                    logit_std = logits_t.std().item()
                    probs_t = F.softmax(logits_t, dim=-1)
                    entropy_t = -(probs_t * torch.log(probs_t + 1e-9)).sum().item()
                    logit_std_sum += logit_std
                    entropy_sum += entropy_t

                    # Check r_t dimensionwise std (collapse check)
                    r_dim_std_sum += r_t.std().item()

                n_diag += 1

        # Normalize loss
        if n_sampled > 0:
            total_loss = total_loss / n_sampled
        else:
            total_loss = torch.tensor(0.0, device=device, requires_grad=True)

        # Build diagnostics
        diagnostics = {}
        if n_diag > 0:
            mean_cos_pos = cos_pos_sum / n_diag
            mean_cos_neg = cos_neg_sum / n_diag
            diagnostics = {
                "bcvf_rep/cos_pos_mean": mean_cos_pos,
                "bcvf_rep/cos_neg_mean": mean_cos_neg,
                "bcvf_rep/separation_delta": mean_cos_pos - mean_cos_neg,
                "bcvf_rep/bcvf_pos_mean": bcvf_pos_sum / n_diag,
                "bcvf_rep/bcvf_neg_mean": bcvf_neg_sum / n_diag,
                "bcvf_rep/bcvf_neg_var": (
                    bcvf_neg_sq_sum / n_diag
                    - (bcvf_neg_sum / n_diag) ** 2
                ),
                "bcvf_rep/w_k_std_mean": w_k_std_sum / n_diag,
                "bcvf_rep/r_dim_std_mean": r_dim_std_sum / n_diag,
                "bcvf_rep/logit_std_mean": logit_std_sum / n_diag,
                "bcvf_rep/entropy_mean": entropy_sum / n_diag,
                "bcvf_rep/loss": total_loss.item(),
                "bcvf_rep/n_sampled": float(n_sampled),
            }

            # Calibration artifact warning
            if n_diag >= 2:
                # Simple heuristic: if logit_std correlates strongly with
                # bcvf scores, warn about calibration artifacts
                if abs(diagnostics["bcvf_rep/logit_std_mean"]) > 50.0:
                    diagnostics["bcvf_rep/calibration_warning"] = 1.0
                else:
                    diagnostics["bcvf_rep/calibration_warning"] = 0.0

        return total_loss, diagnostics

    # =====================================================================
    # Diagnostics Logger
    # =====================================================================

    def log_bcvf_contrastive_diagnostics(
        diagnostics: Dict[str, float],
        step: int,
        writer: Any = None,
        print_every: int = 100,
    ) -> Optional[str]:
        """Log BCVF contrastive diagnostics.

        Args:
            diagnostics: Dict from compute_bcvf_contrastive_loss.
            step: Global training step.
            writer: Optional TensorBoard SummaryWriter.
            print_every: Print to console every N steps.

        Returns:
            Formatted log string if printing, else None.
        """
        if not diagnostics:
            return None

        # TensorBoard logging
        if writer is not None:
            for key, val in diagnostics.items():
                if isinstance(val, (int, float)):
                    writer.add_scalar(key, val, step)

        # Console logging
        if step % print_every == 0:
            delta = diagnostics.get("bcvf_rep/separation_delta", 0.0)
            cos_pos = diagnostics.get("bcvf_rep/cos_pos_mean", 0.0)
            cos_neg = diagnostics.get("bcvf_rep/cos_neg_mean", 0.0)
            loss = diagnostics.get("bcvf_rep/loss", 0.0)
            calib_warn = diagnostics.get("bcvf_rep/calibration_warning", 0.0)

            msg = (
                f"  [BCVF-REP Step {step}] "
                f"L_rep={loss:.4f} | "
                f"cos_pos={cos_pos:.3f} cos_neg={cos_neg:.3f} "
                f"delta={delta:.3f}"
            )
            if calib_warn > 0:
                msg += " | CALIB-WARN: high logit_std"

            print(msg)
            return msg

        return None

    # =====================================================================
    # Integration Helper
    # =====================================================================

    def extract_hidden_states_for_contrastive(
        model: nn.Module,
        outputs: Any,
        input_ids: torch.Tensor,
    ) -> Optional[torch.Tensor]:
        """Extract hidden states suitable for contrastive learning.

        Tries multiple strategies to get [B, T, D] hidden states from
        the model's output or via hooks.

        Args:
            model: The transformer model.
            outputs: Model forward output (dict or tensor).
            input_ids: [B, T] input token IDs.

        Returns:
            h: [B, T, D] hidden states, or None if extraction failed.
        """
        # Strategy 1: Dict output with explicit hidden_states key
        if isinstance(outputs, dict):
            # Check for hidden_states list (HF-style)
            if "hidden_states" in outputs and outputs["hidden_states"] is not None:
                hs = outputs["hidden_states"]
                if isinstance(hs, (list, tuple)) and len(hs) > 0:
                    return hs[-1]  # Last layer
                elif isinstance(hs, torch.Tensor):
                    return hs

            # Check for 'output' or 'logits' key that might be pre-lm_head
            # We need hidden states BEFORE the lm_head, not logits
            # Try to find a 'last_hidden_state' key
            if "last_hidden_state" in outputs:
                return outputs["last_hidden_state"]

        # Strategy 2: Reconstruct from logits via inverse lm_head
        # This is a fallback — we compute h = logits @ lm_head.weight.T
        # (pseudo-inverse approximation)
        logits = None
        if isinstance(outputs, dict):
            logits = outputs.get("logits", outputs.get("output"))
        elif isinstance(outputs, torch.Tensor):
            logits = outputs

        if logits is not None and logits.dim() == 3:
            # Try to find lm_head weight
            lm_head_weight = None
            for name, module in model.named_modules():
                if "lm_head" in name and isinstance(module, nn.Linear):
                    lm_head_weight = module.weight  # [V, D]
                    break

            if lm_head_weight is not None:
                # Approximate h from logits: h ≈ logits @ pinv(W)
                # For tied embeddings, W.T @ W ≈ I (approximately)
                # Use W.T as cheap pseudo-inverse
                W = lm_head_weight.detach().float()  # [V, D]
                # h ≈ logits @ W.T @ (W @ W.T)^{-1} but for tied embeddings
                # just use h ≈ logits @ W / (norm factors)
                # Better: use the last layer norm output which IS the hidden state
                # For now, compute a simple projection
                h = logits.float() @ W  # [B, T, D] (approximate)
                # Normalize to prevent scale issues
                h = F.normalize(h, p=2, dim=-1) * math.sqrt(W.shape[1])
                return h

        # Strategy 3: Use a forward hook to capture hidden states
        # (This would need to be set up beforehand - return None here)
        return None

    def get_token_embedding_weight(model: nn.Module) -> Optional[torch.Tensor]:
        """Get the token embedding weight matrix from the model.

        Args:
            model: The transformer model.

        Returns:
            [V, D] embedding weight, or None.
        """
        # Try common attribute names
        for attr_path in [
            "token_embed",
            "embed_tokens",
            "wte",
            "embeddings.word_embeddings",
            "transformer.wte",
        ]:
            parts = attr_path.split(".")
            obj = model
            found = True
            for part in parts:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    found = False
                    break
            if found and isinstance(obj, nn.Embedding):
                return obj.weight.detach()

        # Try get_input_embeddings (HF API)
        if hasattr(model, "get_input_embeddings"):
            emb = model.get_input_embeddings()
            if emb is not None and hasattr(emb, "weight"):
                return emb.weight.detach()

        return None

    # =====================================================================
    # Hidden-State Capture Hook
    # =====================================================================

    class HiddenStateCaptureHook:
        """Forward hook that captures last-layer hidden states.

        Registers on the model's final layer norm (before lm_head)
        to capture the hidden states needed for contrastive learning
        without modifying the model's forward signature.

        Usage:
            hook = HiddenStateCaptureHook()
            hook.register(model)
            outputs = model(x)
            h = hook.get()  # [B, T, D]
            hook.remove()
        """

        def __init__(self):
            self._hidden_states: Optional[torch.Tensor] = None
            self._handle = None

        def _hook_fn(self, module, input, output):
            """Capture the output of the norm layer."""
            if isinstance(output, torch.Tensor):
                self._hidden_states = output
            elif isinstance(output, tuple) and len(output) > 0:
                self._hidden_states = output[0]

        def register(self, model: nn.Module) -> bool:
            """Register hook on the model's final norm layer.

            Tries common norm layer names. Returns True if successful.
            """
            # Try to find the final layer norm before lm_head
            norm_module = None
            for name in ["norm", "ln_f", "final_norm", "layer_norm"]:
                if hasattr(model, name):
                    candidate = getattr(model, name)
                    if isinstance(candidate, (nn.LayerNorm, nn.Module)):
                        norm_module = candidate
                        break

            if norm_module is None:
                # Fallback: try to find the last LayerNorm in the model
                last_ln = None
                for name, module in model.named_modules():
                    if isinstance(module, nn.LayerNorm):
                        last_ln = module
                if last_ln is not None:
                    norm_module = last_ln

            if norm_module is not None:
                self._handle = norm_module.register_forward_hook(self._hook_fn)
                return True

            return False

        def get(self) -> Optional[torch.Tensor]:
            """Get captured hidden states. Returns None if not captured."""
            return self._hidden_states

        def clear(self):
            """Clear captured states to free memory."""
            self._hidden_states = None

        def remove(self):
            """Remove the hook."""
            if self._handle is not None:
                self._handle.remove()
                self._handle = None
            self._hidden_states = None


else:
    # Stubs when PyTorch is not available
    class BCVFContrastiveHead:  # type: ignore[no-redef]
        pass

    class BCVFNegativeSampler:  # type: ignore[no-redef]
        pass

    class HiddenStateCaptureHook:  # type: ignore[no-redef]
        pass

    def compute_bcvf_contrastive_loss(*args, **kwargs):  # type: ignore[no-redef]
        raise ImportError("PyTorch required")

    def log_bcvf_contrastive_diagnostics(*args, **kwargs):  # type: ignore[no-redef]
        raise ImportError("PyTorch required")
