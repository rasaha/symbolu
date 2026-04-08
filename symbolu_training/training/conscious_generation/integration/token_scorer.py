"""
IntegratedTokenScorer: Combines Kosha routing and Bliss gating into Z*(w).

Z(w)  = Sum_f alpha_f S_f(w)          -- Kosha-weighted score
Z*(w) = B(w) * Z(w)                   -- Bliss-gated integrated score

Governance pipeline:
  1. KoshaDomainRouter produces alpha_t from Kosha [12:17] x Domain
  2. BlissTokenGate produces B(w) with lambda modulated by BLISSFUL Kosha
  3. IntegratedTokenScorer combines them into Z*(w)

The governance plane (Pranamaya) actively controls both:
  - WHICH primitives matter (via Kosha x Domain routing)
  - HOW strict coherence is (via BLISSFUL Kosha → BlissGate lambda)

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 3
"""

import torch
import torch.nn as nn
from typing import Dict, Optional


class IntegratedTokenScorer(nn.Module):
    """
    Produces integrated token scores Z*(w) via governance-plane routing + gating.

    Args:
        kosha_router: KoshaDomainRouter instance
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
        domain: Optional[torch.Tensor] = None,
        candidate_ids: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute integrated scores Z*(w) for candidate tokens.

        Args:
            T: Token Evaluation Tensor (..., K, 6) -- primitive scores
            hidden: Transformer hidden states (..., embed_dim)
            o_ctx: Context ontological state (..., state_dim)
            domain: Domain distribution (..., num_domains). Optional;
                    when absent, router falls back to residual-only.
            candidate_ids: Token indices (..., K) -- passed through

        Returns:
            Dict with keys:
                'Z_star': Bliss-gated integrated scores (..., K)
                'Z': Raw Kosha-weighted scores (..., K)
                'alpha': Kosha routing weights (..., 6)
                'B': Bliss coherence values (..., K)
                'D': Disagreement values (..., K)
                'kosha': Extracted Kosha distribution (..., 5)
                'lambda_eff': Effective Bliss gate lambda
                'candidate_ids': Token indices (passthrough)
        """
        # Step 1: Governance-plane routing (Kosha x Domain → alpha)
        # Expand o_ctx to match hidden's sequence dim if needed (MistralCG
        # returns pooled [B, 32] state vs [B, T, D] hidden states)
        _o_ctx = o_ctx
        if hidden.dim() == 3 and o_ctx.dim() == 2:
            _o_ctx = o_ctx.unsqueeze(1).expand(-1, hidden.shape[1], -1)
        router_result = self.kosha_router(hidden, _o_ctx, domain=domain)
        alpha = router_result["alpha"]   # (..., 6)
        kosha = router_result["kosha"]   # (..., 5)

        # Step 2: Bliss gating (with Kosha + Guna modulating lambda)
        bliss_result = self.bliss_gate(T, alpha, kosha=kosha, o_ctx=_o_ctx)
        B = bliss_result["B"]       # (..., K)
        D = bliss_result["D"]       # (..., K)
        Z = bliss_result["mu"]      # (..., K) -- this IS Z(w) = Sum_f alpha_f S_f(w)

        # Step 3: Gated score
        Z_star = B * Z  # (..., K)

        result = {
            "Z_star": Z_star,
            "Z": Z,
            "alpha": alpha,
            "B": B,
            "D": D,
            "kosha": kosha,
            "lambda_eff": bliss_result["lambda_eff"],
            "router_result": router_result,
        }
        if "guna_3d" in bliss_result:
            result["guna_3d"] = bliss_result["guna_3d"]
        if candidate_ids is not None:
            result["candidate_ids"] = candidate_ids

        return result
