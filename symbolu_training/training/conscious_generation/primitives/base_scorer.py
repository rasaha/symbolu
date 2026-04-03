"""
BaseScorer: S_base(w) — extracts standard transformer logits.

Thin wrapper around the existing vocabulary projection (lm_head).
No new parameters. Provides a uniform interface so that the
TokenEvaluationTensor can treat all 6 primitives identically.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 2
"""

import torch
import torch.nn as nn
from typing import Optional


class BaseScorer(nn.Module):
    """
    Extracts S_base(w) from existing transformer logits.

    No learnable parameters — just reshapes / selects from the logit
    tensor produced by the model's lm_head.

    Usage:
        scorer = BaseScorer()
        S_base = scorer(logits, candidate_ids)  # (B, T, K)
    """

    def __init__(self):
        super().__init__()

    def forward(
        self,
        logits: torch.Tensor,
        candidate_ids: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Extract base scores for candidate tokens.

        Args:
            logits: Full vocabulary logits (..., V)
            candidate_ids: Token indices to select (..., K).
                          If None, returns full vocabulary scores.

        Returns:
            Base scores (..., K) or (..., V)
        """
        if candidate_ids is None:
            return logits

        # Gather scores for candidate tokens
        # candidate_ids: (..., K), logits: (..., V)
        return logits.gather(dim=-1, index=candidate_ids)
