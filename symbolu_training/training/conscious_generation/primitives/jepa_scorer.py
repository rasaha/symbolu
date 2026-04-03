"""
PlausibilityTokenScorer: S_plausibility(w) — contextual plausibility scoring.

Token-side:   p_w = f_plaus_tok([e_w; o_w]) in R^{d_j}  (MLP)
Context-side: p_t = f_plaus_ctx([h_t; o_t]) in R^{d_j}  (MLP)
Score:        S_plausibility(w) = p_t^T M_plaus p_w  (bilinear, optionally low-rank)

Token representations are cached in P_tok (V, d_j) and refreshed
periodically alongside the ontology cache.

This is a contextual plausibility scorer — separate from the Ontological
State Predictor (symbolu/jepa/predictor.py) which handles self-supervised
state prediction. PlausibilityTokenScorer produces per-token plausibility
scores for the conscious generation pipeline.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 2
"""

import torch
import torch.nn as nn
from typing import Optional


class PlausibilityTokenScorer(nn.Module):
    """
    Bilinear plausibility scorer for token-context compatibility.

    Args:
        embed_dim: Token embedding dimension
        state_dim: Ontological code dimension (32)
        jepa_dim: Plausibility representation dimension (d_j, default 16)
        hidden_dim: Hidden dimension of context-side MLP
        use_low_rank: Factor M_plaus = A B^T
        rank: Low-rank factorization rank
    """

    def __init__(
        self,
        embed_dim: int,
        state_dim: int = 32,
        jepa_dim: int = 16,
        hidden_dim: Optional[int] = None,
        use_low_rank: bool = True,
        rank: int = 8,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.state_dim = state_dim
        self.jepa_dim = jepa_dim
        self.use_low_rank = use_low_rank

        hidden = hidden_dim or (embed_dim // 4)

        # Token-side MLP: [e_w; o_w] -> p_w
        self.token_mlp = nn.Sequential(
            nn.Linear(embed_dim + state_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, jepa_dim),
        )

        # Context-side MLP: [h_t; o_t] -> p_t
        self.context_mlp = nn.Sequential(
            nn.Linear(embed_dim + state_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, jepa_dim),
        )

        # Bilinear form M_plaus
        if use_low_rank:
            self.A = nn.Parameter(torch.empty(jepa_dim, rank))
            self.B = nn.Parameter(torch.empty(jepa_dim, rank))
            nn.init.orthogonal_(self.A, gain=0.5)
            nn.init.orthogonal_(self.B, gain=0.5)
        else:
            self.M = nn.Parameter(torch.eye(jepa_dim) + 0.01 * torch.randn(jepa_dim, jepa_dim))

    def compute_token_repr(
        self, embeddings: torch.Tensor, o_tok: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute token-side plausibility representations for caching.

        Args:
            embeddings: Token embeddings (V, embed_dim) or (N, embed_dim)
            o_tok: Ontological codes (V, state_dim) or (N, state_dim)

        Returns:
            p_tok: Plausibility representations (V, d_j) or (N, d_j)
        """
        combined = torch.cat([embeddings, o_tok], dim=-1)
        return self.token_mlp(combined)

    def compute_context_repr(
        self, hidden: torch.Tensor, o_ctx: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute context-side plausibility representation.

        Args:
            hidden: Transformer hidden states (..., embed_dim)
            o_ctx: Context ontological state (..., state_dim)

        Returns:
            p_ctx: Context plausibility representation (..., d_j)
        """
        combined = torch.cat([hidden, o_ctx], dim=-1)
        return self.context_mlp(combined)

    def forward(
        self,
        p_ctx: torch.Tensor,
        P_tok: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute plausibility scores.

        Args:
            p_ctx: Context plausibility repr (..., d_j)
            P_tok: Cached token plausibility reprs (V, d_j) or (K, d_j)

        Returns:
            Scores (..., V) or (..., K)
        """
        if self.use_low_rank:
            intermediate = p_ctx @ self.B  # (..., rank)
            m_p = intermediate @ self.A.t()  # (..., d_j)
        else:
            m_p = p_ctx @ self.M.t()  # (..., d_j)

        return m_p @ P_tok.t()


# Backward-compatible alias
JEPATokenScorer = PlausibilityTokenScorer
