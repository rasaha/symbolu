"""
PrimitiveAuxiliaryLosses: Per-primitive token-level contrastive losses.

Each primitive gets a dedicated loss that teaches it to distinguish correct
from incorrect token-context pairs:

  L_jepa:   Contrastive plausibility — correct tokens should score higher
  L_csr:    Resonance alignment — phonemically appropriate tokens preferred
  L_vritti: Cognitive mode classification — tokens match context's mode
  L_guna:   Energetic compatibility — tokens match context's guna profile

All losses share the same structure:
  1. From the Token Evaluation Tensor T ∈ ℝ^{K×6}, extract the column
     for the relevant primitive f
  2. Identify the correct token's score as the positive
  3. Compute margin-based or InfoNCE loss against the other K-1 negatives

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 3
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional


class PrimitiveAuxiliaryLosses(nn.Module):
    """
    Unified per-primitive auxiliary loss computation.

    Extracts each primitive's scores from T, computes contrastive loss
    against ground truth token position.

    Args:
        loss_type: "margin" (hinge) or "infonce" (softmax cross-entropy)
        margin: Margin for hinge loss (ignored if loss_type="infonce")
        temperature: Temperature for InfoNCE (ignored if loss_type="margin")
        primitive_indices: Dict mapping primitive name to column index in T.
                          Defaults to the standard ordering.
    """

    # Standard column ordering in Token Evaluation Tensor
    DEFAULT_INDICES = {
        "jepa": 2,
        "csr": 3,
        "vritti": 4,
        "guna": 5,
    }

    def __init__(
        self,
        loss_type: str = "infonce",
        margin: float = 0.1,
        temperature: float = 0.1,
        primitive_indices: Optional[Dict[str, int]] = None,
    ):
        super().__init__()
        self.loss_type = loss_type
        self.margin = margin
        self.temperature = temperature
        self.primitive_indices = primitive_indices or self.DEFAULT_INDICES

    def forward(
        self,
        T: torch.Tensor,
        target_ids: torch.Tensor,
        candidate_ids: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute per-primitive auxiliary losses.

        Args:
            T: Token Evaluation Tensor (..., K, 6)
            target_ids: Ground truth token ids (...,)
            candidate_ids: Candidate token ids (..., K)

        Returns:
            Dict with per-primitive losses and a combined total:
                'L_jepa', 'L_csr', 'L_vritti', 'L_guna', 'loss'
        """
        # Find which candidate position matches the target
        target_expanded = target_ids.unsqueeze(-1)  # (..., 1)
        target_mask = (candidate_ids == target_expanded)  # (..., K)

        # If target isn't in the shortlist, return zero losses
        has_target = target_mask.any(dim=-1)  # (...)
        if not has_target.any():
            zero = torch.tensor(0.0, device=T.device, dtype=T.dtype)
            result = {"loss": zero}
            for name in self.primitive_indices:
                result[f"L_{name}"] = zero
            return result

        results = {}
        total = torch.tensor(0.0, device=T.device, dtype=T.dtype)

        for name, col_idx in self.primitive_indices.items():
            scores = T[..., col_idx]  # (..., K)
            prim_loss = self._contrastive_loss(scores, target_mask, has_target)
            results[f"L_{name}"] = prim_loss
            total = total + prim_loss

        results["loss"] = total
        return results

    def _contrastive_loss(
        self,
        scores: torch.Tensor,
        target_mask: torch.Tensor,
        has_target: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute contrastive loss for a single primitive.

        Args:
            scores: Primitive scores (..., K)
            target_mask: Boolean mask for correct token (..., K)
            has_target: Whether target is in shortlist (...)

        Returns:
            Scalar loss
        """
        if self.loss_type == "infonce":
            return self._infonce_loss(scores, target_mask, has_target)
        else:
            return self._margin_loss(scores, target_mask, has_target)

    def _infonce_loss(
        self,
        scores: torch.Tensor,
        target_mask: torch.Tensor,
        has_target: torch.Tensor,
    ) -> torch.Tensor:
        """InfoNCE: correct token should have highest score among candidates."""
        # Mask to only positions where target is in shortlist
        # Flatten batch dims for cross-entropy
        flat_scores = scores[has_target]  # (N, K)
        flat_mask = target_mask[has_target]  # (N, K)

        if flat_scores.numel() == 0:
            return torch.tensor(0.0, device=scores.device, dtype=scores.dtype)

        # Target index for each sample
        target_idx = flat_mask.float().argmax(dim=-1)  # (N,)

        # Cross-entropy over candidates (temperature-scaled)
        loss = F.cross_entropy(flat_scores / self.temperature, target_idx)
        return loss

    def _margin_loss(
        self,
        scores: torch.Tensor,
        target_mask: torch.Tensor,
        has_target: torch.Tensor,
    ) -> torch.Tensor:
        """Margin loss: correct token score should exceed negatives by margin."""
        flat_scores = scores[has_target]  # (N, K)
        flat_mask = target_mask[has_target]  # (N, K)

        if flat_scores.numel() == 0:
            return torch.tensor(0.0, device=scores.device, dtype=scores.dtype)

        # Positive score: score of correct token
        pos_scores = (flat_scores * flat_mask.float()).sum(dim=-1)  # (N,)

        # Negative scores: all other candidates
        neg_mask = ~flat_mask  # (N, K)
        neg_scores = flat_scores.masked_fill(~neg_mask, float('-inf'))

        # Max negative score
        max_neg = neg_scores.max(dim=-1).values  # (N,)

        # Hinge loss: max(0, margin - (pos - max_neg))
        loss = torch.clamp(self.margin - (pos_scores - max_neg), min=0.0).mean()
        return loss
