"""
BlissCoherenceLoss: Encourages cross-field agreement on correct tokens.

The key insight: correct tokens should have LOW disagreement (high Bliss),
while incorrect tokens (especially hard negatives) should have HIGH
disagreement (low Bliss). This teaches the model that multi-field consensus
is a signal of correctness.

Loss formulation:
  L_bliss = -log(B(w_correct)) + mean(-log(1 - B(w_neg)))

Where B(w) = exp(-λ_B · D(w)) is the per-token Bliss value and D(w) is
the weighted cross-primitive disagreement.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 3
"""

import torch
import torch.nn as nn
from typing import Dict


class BlissCoherenceLoss(nn.Module):
    """
    Token-level Bliss coherence loss.

    Encourages:
      - Correct tokens to have high Bliss (low disagreement)
      - Hard negative tokens to have low Bliss (high disagreement)

    Args:
        neg_weight: Weight for the negative term relative to positive
        max_neg_samples: Maximum number of negatives to use per position
    """

    def __init__(
        self,
        neg_weight: float = 0.5,
        max_neg_samples: int = 16,
    ):
        super().__init__()
        self.neg_weight = neg_weight
        self.max_neg_samples = max_neg_samples

    def forward(
        self,
        B: torch.Tensor,
        D: torch.Tensor,
        target_ids: torch.Tensor,
        candidate_ids: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute Bliss coherence loss.

        Args:
            B: Bliss values (..., K) in [0, 1]
            D: Disagreement values (..., K) ≥ 0
            target_ids: Ground truth token ids (...,)
            candidate_ids: Candidate token ids (..., K)

        Returns:
            Dict with 'loss', 'pos_bliss', 'neg_bliss', 'pos_disagreement',
            'neg_disagreement'.
        """
        # Find correct token in candidates
        target_expanded = target_ids.unsqueeze(-1)  # (..., 1)
        target_mask = (candidate_ids == target_expanded)  # (..., K)
        has_target = target_mask.any(dim=-1)  # (...)

        if not has_target.any():
            zero = torch.tensor(0.0, device=B.device, dtype=B.dtype)
            return {
                "loss": zero,
                "pos_bliss": zero,
                "neg_bliss": zero,
                "pos_disagreement": zero,
                "neg_disagreement": zero,
            }

        # Extract Bliss values for correct and incorrect tokens
        B_flat = B[has_target]           # (N, K)
        mask_flat = target_mask[has_target]  # (N, K)
        D_flat = D[has_target]           # (N, K)

        # Positive: Bliss of correct token
        B_pos = (B_flat * mask_flat.float()).sum(dim=-1)  # (N,)
        D_pos = (D_flat * mask_flat.float()).sum(dim=-1)  # (N,)

        # Negative: Bliss of incorrect tokens (sample up to max_neg_samples)
        neg_mask = ~mask_flat  # (N, K)
        B_neg = B_flat.masked_fill(~neg_mask, 0.0)

        # Subsample negatives if needed
        K = B_flat.shape[-1]
        if K - 1 > self.max_neg_samples:
            # Use top-scoring negatives (hardest negatives)
            B_neg_sorted = B_neg.sort(dim=-1, descending=True).values
            B_neg_sampled = B_neg_sorted[..., :self.max_neg_samples]
        else:
            B_neg_sampled = B_neg[neg_mask].reshape(B_flat.shape[0], -1)

        # Positive loss: -log(B(w_correct)) — encourage high Bliss for correct
        pos_loss = -torch.log(B_pos + 1e-8).mean()

        # Negative loss: -log(1 - B(w_neg)) — encourage low Bliss for incorrect
        neg_loss = -torch.log(1.0 - B_neg_sampled + 1e-8).mean()

        loss = pos_loss + self.neg_weight * neg_loss

        # Diagnostics
        with torch.no_grad():
            neg_D = D_flat.masked_fill(~neg_mask, 0.0)
            mean_neg_D = neg_D.sum() / neg_mask.float().sum().clamp(min=1)

        return {
            "loss": loss,
            "pos_bliss": B_pos.mean().detach(),
            "neg_bliss": B_neg_sampled.mean().detach(),
            "pos_disagreement": D_pos.mean().detach(),
            "neg_disagreement": mean_neg_D,
        }
