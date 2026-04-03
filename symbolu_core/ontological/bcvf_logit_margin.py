#!/usr/bin/env python3
"""
BCVF Logit-Margin + Entropy Band Regularization
=================================================

Perplexity-aligned contrastive pressure that operates directly on logits
instead of hidden-state cosine similarity.

Core insight: PPL = exp(CE), and CE only cares about -log p(y_t).
Cosine separation in representation space does not directly improve
token likelihood. Logit-margin loss does.

Loss:
    L_total = L_CE + λ_m * L_margin + λ_H * L_entropy

    L_margin = mean(relu(m - (z_pos - z_neg_max)))
        where z_pos = logit of ground truth token
              z_neg_max = max logit among non-target tokens

    L_entropy = mean(relu(H_min - H_t) + relu(H_t - H_max))
        where H_t = -sum(p_i * log(p_i)) per position

Usage:
    from symbolu_core.ontological.bcvf_logit_margin import (
        LogitMarginConfig,
        compute_logit_margin_loss,
        log_logit_margin_diagnostics,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    import torch
    import torch.nn.functional as F

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False


@dataclass
class LogitMarginConfig:
    """Configuration for logit-margin BCVF + entropy band.

    Attributes:
        use_logit_margin: Master toggle.
        lambda_margin: Weight for margin loss in total loss.
        lambda_entropy: Weight for entropy band loss in total loss.
        margin: Minimum logit gap z_pos - z_neg_max.
        H_min: Lower entropy band boundary.
        H_max: Upper entropy band boundary.
        top_k_neg: Number of hard negatives to average over (1 = hardest only).
    """

    use_logit_margin: bool = False
    lambda_margin: float = 0.05
    lambda_entropy: float = 0.01
    margin: float = 0.7
    H_min: float = 1.5
    H_max: float = 4.0
    top_k_neg: int = 1


if PYTORCH_AVAILABLE:

    def compute_logit_margin_loss(
        logits: torch.Tensor,
        targets: torch.Tensor,
        config: LogitMarginConfig,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, float]]:
        """Compute logit-margin and entropy-band losses.

        Args:
            logits: [B, T, V] raw logits from lm_head.
            targets: [B, T] ground truth token IDs (-100 for padding).
            config: LogitMarginConfig.

        Returns:
            margin_loss: Scalar logit-margin loss.
            entropy_loss: Scalar entropy-band loss.
            diagnostics: Dict of diagnostic metrics.
        """
        B, T, V = logits.shape
        device = logits.device

        # Mask valid positions (not padding)
        valid_mask = targets != -100  # [B, T]
        n_valid = valid_mask.sum().item()

        if n_valid == 0:
            zero = torch.tensor(0.0, device=device, requires_grad=True)
            return zero, zero, {}

        # Flatten for efficient computation
        flat_logits = logits.view(-1, V)  # [B*T, V]
        flat_targets = targets.view(-1)  # [B*T]
        flat_mask = valid_mask.view(-1)  # [B*T]

        # Select valid positions only
        valid_idx = flat_mask.nonzero(as_tuple=True)[0]
        v_logits = flat_logits[valid_idx]  # [N, V]
        v_targets = flat_targets[valid_idx]  # [N]
        N = v_logits.shape[0]

        # ── Logit Margin Loss ──
        # z_pos = logit of ground truth
        pos_logits = v_logits.gather(1, v_targets.unsqueeze(1)).squeeze(1)  # [N]

        # Mask out ground truth to find hard negatives
        neg_mask = torch.zeros_like(v_logits, dtype=torch.bool)
        neg_mask.scatter_(1, v_targets.unsqueeze(1), True)
        masked_logits = v_logits.masked_fill(neg_mask, float('-inf'))

        if config.top_k_neg == 1:
            # Hardest single negative
            neg_logits = masked_logits.max(dim=-1).values  # [N]
        else:
            # Average of top-k hard negatives
            top_neg, _ = masked_logits.topk(config.top_k_neg, dim=-1)  # [N, k]
            neg_logits = top_neg.mean(dim=-1)  # [N]

        # margin_loss = relu(m - (z_pos - z_neg))
        logit_gap = pos_logits - neg_logits  # [N]
        per_token_margin = F.relu(config.margin - logit_gap)  # [N]
        margin_loss = per_token_margin.mean()

        # ── Entropy Band Loss ──
        with torch.no_grad():
            probs = F.softmax(v_logits, dim=-1)  # [N, V]
            entropy = -(probs * torch.log(probs + 1e-9)).sum(dim=-1)  # [N]

        # Recompute with grad for the penalty
        log_probs = F.log_softmax(v_logits, dim=-1)
        probs_grad = log_probs.exp()
        entropy_grad = -(probs_grad * log_probs).sum(dim=-1)  # [N]

        entropy_penalty = (
            F.relu(config.H_min - entropy_grad)
            + F.relu(entropy_grad - config.H_max)
        )  # [N]
        entropy_loss = entropy_penalty.mean()

        # ── Diagnostics ──
        with torch.no_grad():
            margin_violation_pct = (per_token_margin > 0).float().mean().item() * 100
            mean_gap = logit_gap.mean().item()
            mean_entropy = entropy.mean().item()
            std_entropy = entropy.std().item()
            mean_pos_logit = pos_logits.mean().item()
            mean_neg_logit = neg_logits.mean().item()
            # How many tokens have entropy below/above band
            below_band_pct = (entropy < config.H_min).float().mean().item() * 100
            above_band_pct = (entropy > config.H_max).float().mean().item() * 100

        diagnostics = {
            "bcvf_lm/margin_loss": margin_loss.item(),
            "bcvf_lm/entropy_loss": entropy_loss.item(),
            "bcvf_lm/logit_gap_mean": mean_gap,
            "bcvf_lm/pos_logit_mean": mean_pos_logit,
            "bcvf_lm/neg_logit_mean": mean_neg_logit,
            "bcvf_lm/margin_violation_pct": margin_violation_pct,
            "bcvf_lm/entropy_mean": mean_entropy,
            "bcvf_lm/entropy_std": std_entropy,
            "bcvf_lm/below_band_pct": below_band_pct,
            "bcvf_lm/above_band_pct": above_band_pct,
            "bcvf_lm/n_valid": float(N),
        }

        return margin_loss, entropy_loss, diagnostics

    def log_logit_margin_diagnostics(
        diagnostics: Dict[str, float],
        step: int,
        writer: Any = None,
        print_every: int = 100,
    ) -> Optional[str]:
        """Log logit-margin diagnostics.

        Args:
            diagnostics: Dict from compute_logit_margin_loss.
            step: Global training step.
            writer: Optional TensorBoard SummaryWriter.
            print_every: Print to console every N steps.

        Returns:
            Formatted log string if printing, else None.
        """
        if not diagnostics:
            return None

        # TensorBoard
        if writer is not None:
            for key, val in diagnostics.items():
                if isinstance(val, (int, float)):
                    writer.add_scalar(key, val, step)

        # Console
        if step % print_every == 0:
            m_loss = diagnostics.get("bcvf_lm/margin_loss", 0.0)
            e_loss = diagnostics.get("bcvf_lm/entropy_loss", 0.0)
            gap = diagnostics.get("bcvf_lm/logit_gap_mean", 0.0)
            viol = diagnostics.get("bcvf_lm/margin_violation_pct", 0.0)
            ent = diagnostics.get("bcvf_lm/entropy_mean", 0.0)

            msg = (
                f"  [BCVF-LM Step {step}] "
                f"L_margin={m_loss:.4f} L_ent={e_loss:.4f} | "
                f"gap={gap:.2f} viol={viol:.0f}% | "
                f"H={ent:.2f}"
            )
            print(msg)
            return msg

        return None


else:
    # Stubs when PyTorch is not available
    def compute_logit_margin_loss(*args, **kwargs):
        raise ImportError("PyTorch required")

    def log_logit_margin_diagnostics(*args, **kwargs):
        raise ImportError("PyTorch required")
