"""
BlissTokenGate: Per-token coherence gating based on cross-field agreement.

For each candidate token w in the shortlist:
  mu(w) = Sum_f alpha_f S_f(w)           -- weighted mean score
  D(w) = Sum_f alpha_f (S_f(w) - mu(w))^2  -- weighted disagreement
  B(w) = exp(-lambda_B * D(w))          -- coherence factor in [0, 1]

Tokens with high cross-field agreement (low D) get B ~ 1.
Tokens where primitives disagree (high D) get B -> 0.

Governance integration (Pranamaya plane):
  When Kosha distribution is provided, lambda_B is modulated by the
  BLISSFUL Kosha activation. Higher blissful = stricter coherence.
  This makes the gate strength a governance decision, not a fixed constant.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 3
"""

import torch
import torch.nn as nn
from typing import Optional


# Kosha indices
KOSHA_BLISSFUL_IDX = 4  # Index within 5-dim Kosha vector


class BlissTokenGate(nn.Module):
    """
    Per-token coherence gate based on weighted primitive disagreement.

    When kosha distribution is provided, lambda_B is dynamically modulated:
        lambda_eff = base_lambda + bliss_scale * kosha[BLISSFUL]

    This makes coherence enforcement a governance-plane decision:
        - BLISSFUL dominant → strict coherence (high lambda)
        - MATERIAL dominant → loose coherence (base lambda only)

    Args:
        lambda_B: Base temperature controlling gate sharpness.
        min_bliss: Minimum Bliss value to prevent complete zeroing.
        bliss_scale: How much BLISSFUL Kosha activation increases lambda.
    """

    def __init__(
        self,
        lambda_B: float = 1.0,
        min_bliss: float = 0.01,
        bliss_scale: float = 2.0,
    ):
        super().__init__()
        self.lambda_B = lambda_B
        self.min_bliss = min_bliss
        self.bliss_scale = bliss_scale

    def forward(
        self,
        T: torch.Tensor,
        alpha: torch.Tensor,
        kosha: Optional[torch.Tensor] = None,
    ) -> dict:
        """
        Compute per-token Bliss coherence values.

        Args:
            T: Token Evaluation Tensor (..., K, 6) -- primitive scores
            alpha: Kosha routing weights (..., 6)
            kosha: Optional Kosha distribution (..., 5) from governance plane.
                   When provided, BLISSFUL activation modulates gate strength.

        Returns:
            Dict with keys:
                'B': Bliss values (..., K) in [min_bliss, 1]
                'D': Disagreement values (..., K) >= 0
                'mu': Weighted mean scores (..., K)
                'lambda_eff': Effective lambda used (...,) or scalar
        """
        # alpha: (..., 6) -> (..., 1, 6) for broadcasting with T (..., K, 6)
        alpha_expanded = alpha.unsqueeze(-2)

        # Weighted mean: mu(w) = Sum_f alpha_f S_f(w)
        mu = (alpha_expanded * T).sum(dim=-1)  # (..., K)

        # Disagreement: D(w) = Sum_f alpha_f (S_f(w) - mu(w))^2
        deviations_sq = (T - mu.unsqueeze(-1)) ** 2  # (..., K, 6)
        D = (alpha_expanded * deviations_sq).sum(dim=-1)  # (..., K)

        # Compute effective lambda (governance-modulated)
        if kosha is not None:
            blissful = kosha[..., KOSHA_BLISSFUL_IDX]  # (...,)
            lambda_eff = self.lambda_B + self.bliss_scale * blissful
            # Expand for broadcasting with D (..., K)
            lambda_for_gate = lambda_eff.unsqueeze(-1)  # (..., 1)
        else:
            lambda_eff = torch.tensor(self.lambda_B, device=T.device, dtype=T.dtype)
            lambda_for_gate = self.lambda_B

        # Bliss gate: B(w) = exp(-lambda_eff * D(w))
        B = torch.exp(-lambda_for_gate * D)

        # Apply minimum floor
        B = torch.clamp(B, min=self.min_bliss)

        return {
            "B": B,
            "D": D,
            "mu": mu,
            "lambda_eff": lambda_eff,
        }
