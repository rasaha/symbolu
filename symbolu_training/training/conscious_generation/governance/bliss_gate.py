"""
BlissTokenGate: Per-token coherence gating based on cross-field agreement.

For each candidate token w in the shortlist:
  mu(w) = Sum_f alpha_f S_f(w)           -- weighted mean score
  D(w) = Sum_f alpha_f (S_f(w) - mu(w))^2  -- weighted disagreement
  B(w) = exp(-lambda_eff * D(w))          -- coherence factor in [0, 1]

Tokens with high cross-field agreement (low D) get B ~ 1.
Tokens where primitives disagree (high D) get B -> 0.

Governance integration:
  lambda_eff is modulated by two governance signals:
    1. BLISSFUL Kosha activation (Anandamaya) — higher → stricter coherence
    2. Guna energetic state (Sattva/Rajas/Tamas) — learnable per-Guna weights
       control how each energetic quality influences gate strength.
       e.g., Sattva (clarity) may learn to enforce stricter coherence,
       while Tamas (inertia) may learn to relax it.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 3
"""

import torch
import torch.nn as nn
from typing import Optional


# Kosha indices
KOSHA_BLISSFUL_IDX = 4  # Index within 5-dim Kosha vector

# Guna indices within 32D Sovereign State
GUNA_START = 22
GUNA_END = 28
NUM_GUNA_SOVEREIGN = 6   # 6D sigmoid in sovereign state
NUM_GUNA_CLASSICAL = 3   # 3 classical Gunas: Sattva, Rajas, Tamas


class BlissTokenGate(nn.Module):
    """
    Per-token coherence gate based on weighted primitive disagreement.

    Governance modulation from two sources:
        1. Kosha: lambda_eff += bliss_scale * kosha[BLISSFUL]
        2. Guna:  lambda_eff += guna_weights · softmax(guna_proj(guna_6d))

    The Guna modulation gives the gate 3 learnable parameters (one per
    classical Guna) so it can learn energetic-quality-dependent coherence.

    Args:
        lambda_B: Base temperature controlling gate sharpness.
        min_bliss: Minimum Bliss value to prevent complete zeroing.
        bliss_scale: How much BLISSFUL Kosha activation increases lambda.
        use_dynamic_bliss: Ablation switch — if False, uses fixed lambda_B
                           regardless of Kosha/Guna input.
    """

    def __init__(
        self,
        lambda_B: float = 1.0,
        min_bliss: float = 0.01,
        bliss_scale: float = 2.0,
        use_dynamic_bliss: bool = True,
    ):
        super().__init__()
        self.lambda_B = lambda_B
        self.min_bliss = min_bliss
        self.bliss_scale = bliss_scale
        self.use_dynamic_bliss = use_dynamic_bliss

        # Learnable Guna modulation: 6D sovereign → 3 classical Gunas → scalar
        self.guna_proj = nn.Linear(NUM_GUNA_SOVEREIGN, NUM_GUNA_CLASSICAL, bias=False)
        self.guna_weights = nn.Parameter(torch.zeros(NUM_GUNA_CLASSICAL))
        nn.init.xavier_normal_(self.guna_proj.weight, gain=0.3)

    def forward(
        self,
        T: torch.Tensor,
        alpha: torch.Tensor,
        kosha: Optional[torch.Tensor] = None,
        o_ctx: Optional[torch.Tensor] = None,
    ) -> dict:
        """
        Compute per-token Bliss coherence values.

        Args:
            T: Token Evaluation Tensor (..., K, 6) -- primitive scores
            alpha: Kosha routing weights (..., 6)
            kosha: Optional Kosha distribution (..., 5) from governance plane.
                   When provided, BLISSFUL activation modulates gate strength.
            o_ctx: Optional ontological state (..., 32). When provided, Guna
                   dims [22:28] modulate gate strength via learned weights.

        Returns:
            Dict with keys:
                'B': Bliss values (..., K) in [min_bliss, 1]
                'D': Disagreement values (..., K) >= 0
                'mu': Weighted mean scores (..., K)
                'lambda_eff': Effective lambda used (...,) or scalar
                'guna_3d': Classical Guna distribution (..., 3) if o_ctx provided
        """
        # alpha: (..., 6) -> (..., 1, 6) for broadcasting with T (..., K, 6)
        alpha_expanded = alpha.unsqueeze(-2)

        # Weighted mean: mu(w) = Sum_f alpha_f S_f(w)
        mu = (alpha_expanded * T).sum(dim=-1)  # (..., K)

        # Disagreement: D(w) = Sum_f alpha_f (S_f(w) - mu(w))^2
        deviations_sq = (T - mu.unsqueeze(-1)) ** 2  # (..., K, 6)
        D = (alpha_expanded * deviations_sq).sum(dim=-1)  # (..., K)

        # Compute effective lambda (governance-modulated)
        lambda_eff = torch.tensor(self.lambda_B, device=T.device, dtype=T.dtype)
        guna_3d = None

        if self.use_dynamic_bliss:
            # Kosha modulation: BLISSFUL activation
            if kosha is not None:
                blissful = kosha[..., KOSHA_BLISSFUL_IDX]  # (...,)
                lambda_eff = lambda_eff + self.bliss_scale * blissful

            # Guna modulation: 6D sovereign → 3 classical → learned scalar
            if o_ctx is not None:
                guna_6d = o_ctx[..., GUNA_START:GUNA_END]  # (..., 6)
                guna_3d = torch.softmax(self.guna_proj(guna_6d), dim=-1)  # (..., 3)
                guna_mod = (self.guna_weights * guna_3d).sum(dim=-1)  # (...,)
                lambda_eff = lambda_eff + guna_mod

        # Expand for broadcasting with D (..., K)
        if lambda_eff.dim() > 0:
            lambda_for_gate = lambda_eff.unsqueeze(-1)  # (..., 1)
        else:
            lambda_for_gate = lambda_eff

        # Bliss gate: B(w) = exp(-lambda_eff * D(w))
        B = torch.exp(-lambda_for_gate * D)

        # Apply minimum floor
        B = torch.clamp(B, min=self.min_bliss)

        result = {
            "B": B,
            "D": D,
            "mu": mu,
            "lambda_eff": lambda_eff,
        }
        if guna_3d is not None:
            result["guna_3d"] = guna_3d

        return result
