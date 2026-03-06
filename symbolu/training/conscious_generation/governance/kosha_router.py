"""
KoshaPrimitiveRouter: Dynamic context-dependent weighting over 6 primitives.

Produces α_t = softmax(W_k [h_t ; o_t]) ∈ Δ⁵ — a probability distribution
over {base, ontology, JEPA, CSR, Vritti, Guna} that determines how much each
primitive score contributes to the integrated token score Z(w).

The Kosha weighting is context-dependent: factual contexts may upweight JEPA
(plausibility), while narrative contexts may upweight CSR (resonance).

Initialization modes:
  - "uniform": All primitives start with equal weight
  - "base_dominant": α_base starts high (~0.8), others low (~0.04 each)

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 3
"""

import torch
import torch.nn as nn
from typing import Optional

NUM_PRIMITIVES = 6
PRIMITIVE_NAMES = ["base", "ontology", "jepa", "csr", "vritti", "guna"]


class KoshaPrimitiveRouter(nn.Module):
    """
    Context-dependent routing weights over 6 primitive scores.

    Args:
        embed_dim: Transformer hidden state dimension
        state_dim: Ontological code dimension (32)
        num_primitives: Number of primitives to route over (6)
        hidden_dim: Hidden dimension for the routing MLP (None = embed_dim // 4)
        init_mode: "uniform" or "base_dominant"
        temperature: Softmax temperature for sharper/softer routing
    """

    def __init__(
        self,
        embed_dim: int,
        state_dim: int = 32,
        num_primitives: int = NUM_PRIMITIVES,
        hidden_dim: Optional[int] = None,
        init_mode: str = "uniform",
        temperature: float = 1.0,
    ):
        super().__init__()
        self.num_primitives = num_primitives
        self.temperature = temperature
        self.init_mode = init_mode

        hidden = hidden_dim or (embed_dim // 4)

        self.router = nn.Sequential(
            nn.Linear(embed_dim + state_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, num_primitives),
        )

        self._init_weights(init_mode)

    def _init_weights(self, init_mode: str) -> None:
        """Initialize routing weights."""
        # Small init for near-uniform initial routing
        for module in self.router:
            if isinstance(module, nn.Linear):
                nn.init.xavier_normal_(module.weight, gain=0.3)
                module.bias.data.fill_(0.0)

        if init_mode == "base_dominant":
            # Bias the final layer to produce high α_base initially
            # softmax([3, 0, 0, 0, 0, 0]) ≈ [0.80, 0.04, ...]
            final_layer = self.router[-1]
            final_layer.bias.data[0] = 3.0

    def forward(
        self,
        hidden: torch.Tensor,
        o_ctx: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute Kosha routing weights.

        Args:
            hidden: Transformer hidden states (..., embed_dim)
            o_ctx: Context ontological state (..., state_dim)

        Returns:
            alpha: Routing weights (..., 6) summing to 1 on last dim
        """
        combined = torch.cat([hidden, o_ctx], dim=-1)
        logits = self.router(combined)
        return torch.softmax(logits / self.temperature, dim=-1)

    def get_diagnostics(self, alpha: torch.Tensor) -> dict:
        """Compute routing diagnostics from a batch of weights."""
        with torch.no_grad():
            mean_alpha = alpha.mean(dim=tuple(range(alpha.dim() - 1)))
            entropy = -(alpha * (alpha + 1e-8).log()).sum(dim=-1).mean()
            max_weight = alpha.max(dim=-1).values.mean()
            return {
                "alpha_mean": {name: mean_alpha[i].item()
                               for i, name in enumerate(PRIMITIVE_NAMES)},
                "alpha_entropy": entropy.item(),
                "alpha_max_weight": max_weight.item(),
            }
