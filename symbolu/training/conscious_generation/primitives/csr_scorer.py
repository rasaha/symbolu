"""
CSRTokenScorer: S_csr(w) — phonemic/mental resonance scoring.

Token-side:   r_w = f_csr_tok(csr_affinity_w) in R^{d_c}  (learned projection from 12D phoneme affinity)
Context-side: r_t = f_csr_ctx([h_t; o_t]) in R^{d_c}  (learned projection)
Score:        S_csr(w) = r_t^T M_csr r_w  (bilinear, optionally low-rank)

Token-side representations are derived from the existing CSR phoneme
pipeline (csr_phoneme_provider.py) which maps each token to a 12D
affinity vector via ARPABET phoneme decomposition.

Token representations are cached in R_tok (V, d_c) and refreshed
periodically. The existing CSR hidden-state injection at Layer 7
remains as complementary enrichment — this scorer is purely for
token-level resonance evaluation.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 2
"""

import torch
import torch.nn as nn
from typing import Optional


class CSRTokenScorer(nn.Module):
    """
    Bilinear CSR resonance scorer for phonemic compatibility.

    Args:
        embed_dim: Token embedding dimension (for context MLP)
        state_dim: Ontological code dimension (32)
        csr_affinity_dim: CSR phoneme affinity dimension (12)
        csr_dim: CSR representation dimension (d_c, default 16)
        use_low_rank: Factor M_csr = A B^T
        rank: Low-rank factorization rank
    """

    def __init__(
        self,
        embed_dim: int,
        state_dim: int = 32,
        csr_affinity_dim: int = 12,
        csr_dim: int = 16,
        use_low_rank: bool = True,
        rank: int = 8,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.csr_dim = csr_dim

        # Token-side: 12D phoneme affinity -> d_c
        self.token_proj = nn.Sequential(
            nn.Linear(csr_affinity_dim, csr_dim),
            nn.GELU(),
            nn.Linear(csr_dim, csr_dim),
        )

        # Context-side: [h_t; o_t] -> d_c
        self.context_proj = nn.Sequential(
            nn.Linear(embed_dim + state_dim, embed_dim // 4),
            nn.GELU(),
            nn.Linear(embed_dim // 4, csr_dim),
        )

        # Bilinear form M_csr
        if use_low_rank:
            self.A = nn.Parameter(torch.empty(csr_dim, rank))
            self.B = nn.Parameter(torch.empty(csr_dim, rank))
            nn.init.orthogonal_(self.A, gain=0.5)
            nn.init.orthogonal_(self.B, gain=0.5)
        else:
            self.M = nn.Parameter(torch.eye(csr_dim) + 0.01 * torch.randn(csr_dim, csr_dim))

        self.use_low_rank = use_low_rank

    def compute_token_repr(self, csr_affinity: torch.Tensor) -> torch.Tensor:
        """
        Compute token-side CSR representations for caching.

        Args:
            csr_affinity: Phoneme affinity vectors (V, 12) or (N, 12)

        Returns:
            r_tok: CSR representations (V, d_c) or (N, d_c)
        """
        return self.token_proj(csr_affinity)

    def compute_context_repr(
        self, hidden: torch.Tensor, o_ctx: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute context-side CSR representation.

        Args:
            hidden: Transformer hidden states (..., embed_dim)
            o_ctx: Context ontological state (..., state_dim)

        Returns:
            r_ctx: Context CSR representation (..., d_c)
        """
        combined = torch.cat([hidden, o_ctx], dim=-1)
        return self.context_proj(combined)

    def forward(
        self,
        r_ctx: torch.Tensor,
        R_tok: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute CSR resonance scores.

        Args:
            r_ctx: Context CSR repr (..., d_c)
            R_tok: Cached token CSR reprs (V, d_c) or (K, d_c)

        Returns:
            Scores (..., V) or (..., K)
        """
        if self.use_low_rank:
            intermediate = r_ctx @ self.B  # (..., rank)
            m_r = intermediate @ self.A.t()  # (..., d_c)
        else:
            m_r = r_ctx @ self.M.t()  # (..., d_c)

        return m_r @ R_tok.t()
