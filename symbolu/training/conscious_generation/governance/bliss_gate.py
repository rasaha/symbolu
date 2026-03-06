"""
BlissTokenGate: Per-token coherence gating based on cross-field agreement.

For each candidate token w in the shortlist:
  μ(w) = Σ_f α_f S_f(w)           — weighted mean score
  D(w) = Σ_f α_f (S_f(w) - μ(w))²  — weighted disagreement
  B(w) = exp(-λ_B · D(w))          — coherence factor in [0, 1]

Tokens with high cross-field agreement (low D) get B ≈ 1.
Tokens where primitives disagree (high D) get B → 0.

This implements the per-token Bliss gate for the governance layer.
The global BlissCoherenceFunctional remains as a diagnostic complement.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 3
"""

import torch
import torch.nn as nn


class BlissTokenGate(nn.Module):
    """
    Per-token coherence gate based on weighted primitive disagreement.

    Args:
        lambda_B: Temperature controlling gate sharpness.
                  Higher = more aggressive gating of disagreement.
        min_bliss: Minimum Bliss value to prevent complete zeroing.
    """

    def __init__(
        self,
        lambda_B: float = 1.0,
        min_bliss: float = 0.01,
    ):
        super().__init__()
        self.lambda_B = lambda_B
        self.min_bliss = min_bliss

    def forward(
        self,
        T: torch.Tensor,
        alpha: torch.Tensor,
    ) -> dict:
        """
        Compute per-token Bliss coherence values.

        Args:
            T: Token Evaluation Tensor (..., K, 6) — primitive scores
            alpha: Kosha routing weights (..., 6)

        Returns:
            Dict with keys:
                'B': Bliss values (..., K) in [min_bliss, 1]
                'D': Disagreement values (..., K) ≥ 0
                'mu': Weighted mean scores (..., K)
        """
        # alpha: (..., 6) -> (..., 1, 6) for broadcasting with T (..., K, 6)
        alpha_expanded = alpha.unsqueeze(-2)

        # Weighted mean: μ(w) = Σ_f α_f S_f(w)
        mu = (alpha_expanded * T).sum(dim=-1)  # (..., K)

        # Disagreement: D(w) = Σ_f α_f (S_f(w) - μ(w))²
        deviations_sq = (T - mu.unsqueeze(-1)) ** 2  # (..., K, 6)
        D = (alpha_expanded * deviations_sq).sum(dim=-1)  # (..., K)

        # Bliss gate: B(w) = exp(-λ_B · D(w))
        B = torch.exp(-self.lambda_B * D)

        # Apply minimum floor
        B = torch.clamp(B, min=self.min_bliss)

        return {
            "B": B,
            "D": D,
            "mu": mu,
        }
