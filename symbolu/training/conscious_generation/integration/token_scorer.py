"""
IntegratedTokenScorer: Combines Kosha routing and Bliss gating into Z*(w).

Z(w)  = Σ_f α_f S_f(w)          — Kosha-weighted score
Z*(w) = B(w) · Z(w)              — Bliss-gated integrated score

This module orchestrates the full governance pipeline:
  1. KoshaPrimitiveRouter produces α_t
  2. BlissTokenGate produces B(w), D(w), μ(w)
  3. IntegratedTokenScorer combines them into Z*(w)

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 3
"""

import torch
import torch.nn as nn
from typing import Dict, Any, Optional


class IntegratedTokenScorer(nn.Module):
    """
    Produces integrated token scores Z*(w) via Kosha routing + Bliss gating.

    Args:
        kosha_router: KoshaPrimitiveRouter instance
        bliss_gate: BlissTokenGate instance
    """

    def __init__(
        self,
        kosha_router: nn.Module,
        bliss_gate: nn.Module,
    ):
        super().__init__()
        self.kosha_router = kosha_router
        self.bliss_gate = bliss_gate

    def forward(
        self,
        T: torch.Tensor,
        hidden: torch.Tensor,
        o_ctx: torch.Tensor,
        candidate_ids: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute integrated scores Z*(w) for candidate tokens.

        Args:
            T: Token Evaluation Tensor (..., K, 6) — primitive scores
            hidden: Transformer hidden states (..., embed_dim)
            o_ctx: Context ontological state (..., state_dim)
            candidate_ids: Token indices (..., K) — passed through for convenience

        Returns:
            Dict with keys:
                'Z_star': Bliss-gated integrated scores (..., K)
                'Z': Raw Kosha-weighted scores (..., K)
                'alpha': Kosha routing weights (..., 6)
                'B': Bliss coherence values (..., K)
                'D': Disagreement values (..., K)
                'candidate_ids': Token indices (passthrough)
        """
        # Step 1: Kosha routing weights
        alpha = self.kosha_router(hidden, o_ctx)  # (..., 6)

        # Step 2: Bliss gating
        bliss_result = self.bliss_gate(T, alpha)
        B = bliss_result["B"]       # (..., K)
        D = bliss_result["D"]       # (..., K)
        Z = bliss_result["mu"]      # (..., K) — this IS Z(w) = Σ_f α_f S_f(w)

        # Step 3: Gated score
        Z_star = B * Z  # (..., K)

        result = {
            "Z_star": Z_star,
            "Z": Z,
            "alpha": alpha,
            "B": B,
            "D": D,
        }
        if candidate_ids is not None:
            result["candidate_ids"] = candidate_ids

        return result
