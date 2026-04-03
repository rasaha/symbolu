"""
VrittiTokenScorer: S_vritti(w) — cognitive mode compatibility scoring.

Token-side:   q_w^(v) = softmax(U_v @ e_w) in Delta^4  (5 Vritti classes)
Context-side: q_t^(v) = softmax(W_v @ [h_t; o_t])
Score:        S_vritti(w) = (q_t^(v))^T @ q_w^(v)  (dot-product compatibility)

The 5 Vritti classes are: FACT, ERROR, IMAGINATION, VOID, MEMORY
(matching VRITTI_NAMES[17:22] in the sovereign state).

Token profiles are cached in V_tok (V, 5) — each token gets a
learned cognitive mode distribution indicating which contexts
it is most appropriate for.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 2
"""

import torch
import torch.nn as nn
from typing import Optional

# Vritti class names matching sovereign state [17:22]
VRITTI_CLASSES = ['FACT', 'ERROR', 'IMAGINATION', 'VOID', 'MEMORY']
NUM_VRITTI = 5


class VrittiTokenScorer(nn.Module):
    """
    Dot-product Vritti compatibility scorer.

    Each token and context position gets a probability distribution
    over 5 cognitive modes. Compatible tokens have similar distributions
    (high dot product between probability vectors).

    Args:
        embed_dim: Token embedding dimension
        state_dim: Ontological code dimension (32)
        num_classes: Number of Vritti classes (5)
    """

    def __init__(
        self,
        embed_dim: int,
        state_dim: int = 32,
        num_classes: int = NUM_VRITTI,
    ):
        super().__init__()
        self.num_classes = num_classes

        # Token-side: e_w -> q_w^(v) in Simplex
        self.token_proj = nn.Linear(embed_dim, num_classes)

        # Context-side: [h_t; o_t] -> q_t^(v) in Simplex
        self.context_proj = nn.Linear(embed_dim + state_dim, num_classes)

        self._init_weights()

    def _init_weights(self):
        """Initialize for near-uniform initial distributions."""
        nn.init.xavier_normal_(self.token_proj.weight, gain=0.3)
        self.token_proj.bias.data.fill_(0.0)
        nn.init.xavier_normal_(self.context_proj.weight, gain=0.3)
        self.context_proj.bias.data.fill_(0.0)

    def compute_token_repr(self, embeddings: torch.Tensor) -> torch.Tensor:
        """
        Compute token-side Vritti profiles for caching.

        Args:
            embeddings: Token embeddings (V, embed_dim)

        Returns:
            v_tok: Vritti profiles (V, 5) — softmax normalized
        """
        return torch.softmax(self.token_proj(embeddings), dim=-1)

    def compute_context_repr(
        self, hidden: torch.Tensor, o_ctx: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute context-side Vritti profile.

        Args:
            hidden: Transformer hidden states (..., embed_dim)
            o_ctx: Context ontological state (..., state_dim)

        Returns:
            v_ctx: Context Vritti profile (..., 5) — softmax normalized
        """
        combined = torch.cat([hidden, o_ctx], dim=-1)
        return torch.softmax(self.context_proj(combined), dim=-1)

    def forward(
        self,
        v_ctx: torch.Tensor,
        V_tok: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute Vritti compatibility scores via dot product.

        Both inputs are probability distributions on the simplex,
        so their dot product is in [0, 1] with 1 = perfect alignment.

        Args:
            v_ctx: Context Vritti profile (..., 5)
            V_tok: Cached token Vritti profiles (V, 5) or (K, 5)

        Returns:
            Scores (..., V) or (..., K) in [0, 1]
        """
        return v_ctx @ V_tok.t()
