"""
GunaTokenScorer: S_guna(w) — energetic compatibility scoring.

Token-side:   q_w^(g) = softmax(U_g @ e_w) in Delta^2  (3 classical Gunas)
Context-side: q_t^(g) = softmax(W_g @ [h_t; o_t])
Score:        S_guna(w) = (q_t^(g))^T @ G @ q_w^(g)  (bilinear with learnable G)

The 3 classical Gunas are: Sattva (clarity), Rajas (activity), Tamas (inertia).
The sovereign state uses 6 Guna dimensions [22:28]; this scorer maps to the
classical 3-class framework for token-level scoring. The 6D representation
remains in the sovereign state for diagnostics and control.

The learnable G matrix (3x3) captures the energetic compatibility structure:
e.g., Sattvic contexts prefer Sattvic tokens (diagonal), but Rajasic contexts
might tolerate Sattvic tokens more than Tamasic (off-diagonal asymmetry).

Token profiles are cached in G_tok (V, 3).

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 2
"""

import torch
import torch.nn as nn
from typing import Optional

GUNA_CLASSES = ['SATTVA', 'RAJAS', 'TAMAS']
NUM_GUNA = 3


class GunaTokenScorer(nn.Module):
    """
    Bilinear Guna energetic compatibility scorer.

    Args:
        embed_dim: Token embedding dimension
        state_dim: Ontological code dimension (32)
        num_classes: Number of Guna classes (3)
    """

    def __init__(
        self,
        embed_dim: int,
        state_dim: int = 32,
        num_classes: int = NUM_GUNA,
    ):
        super().__init__()
        self.num_classes = num_classes

        # Token-side: e_w -> q_w^(g) in Simplex
        self.token_proj = nn.Linear(embed_dim, num_classes)

        # Context-side: [h_t; o_t] -> q_t^(g) in Simplex
        self.context_proj = nn.Linear(embed_dim + state_dim, num_classes)

        # Learnable compatibility matrix G (3x3)
        # Initialized near identity — compatible by default
        self.G = nn.Parameter(
            torch.eye(num_classes) + 0.01 * torch.randn(num_classes, num_classes)
        )

        self._init_weights()

    def _init_weights(self):
        """Initialize for near-uniform initial Guna distributions."""
        nn.init.xavier_normal_(self.token_proj.weight, gain=0.3)
        self.token_proj.bias.data.fill_(0.0)
        nn.init.xavier_normal_(self.context_proj.weight, gain=0.3)
        self.context_proj.bias.data.fill_(0.0)

    def compute_token_repr(self, embeddings: torch.Tensor) -> torch.Tensor:
        """
        Compute token-side Guna profiles for caching.

        Args:
            embeddings: Token embeddings (V, embed_dim)

        Returns:
            g_tok: Guna profiles (V, 3) — softmax normalized
        """
        return torch.softmax(self.token_proj(embeddings), dim=-1)

    def compute_context_repr(
        self, hidden: torch.Tensor, o_ctx: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute context-side Guna profile.

        Args:
            hidden: Transformer hidden states (..., embed_dim)
            o_ctx: Context ontological state (..., state_dim)

        Returns:
            g_ctx: Context Guna profile (..., 3) — softmax normalized
        """
        combined = torch.cat([hidden, o_ctx], dim=-1)
        return torch.softmax(self.context_proj(combined), dim=-1)

    def forward(
        self,
        g_ctx: torch.Tensor,
        G_tok: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute Guna compatibility scores via bilinear form.

        S_guna(w) = g_ctx^T @ G @ g_tok_w

        Args:
            g_ctx: Context Guna profile (..., 3)
            G_tok: Cached token Guna profiles (V, 3) or (K, 3)

        Returns:
            Scores (..., V) or (..., K)
        """
        # g_ctx @ G -> (..., 3), then matmul with G_tok^T -> (..., V)
        transformed = g_ctx @ self.G  # (..., 3)
        return transformed @ G_tok.t()
