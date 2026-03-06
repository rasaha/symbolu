"""
OntologyCompatibilityScorer: S_ont(w) = o_t^T M_ont o_w

Computes ontological compatibility between a context-side ontological state
o_t (from SovereignStateProjector) and token-side ontological codes o_w
(from TokenOntologyProjector / TokenPrimitiveCache).

Supports two parameterizations:
  1. Full bilinear: M_ont in R^{32x32} (1024 params)
  2. Low-rank factored: M_ont = A B^T where A,B in R^{32xr} (64r params)

The low-rank factored form is default (rank=8 -> 512 params) and
provides implicit regularization while reducing parameter count.

For efficient full-vocabulary scoring:
  S_ont = O_tok @ (M_ont @ o_t)  ->  (V,) scores in a single matmul

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 1
"""

import torch
import torch.nn as nn
from typing import Optional

try:
    from symbolu.phase_transformer import SOVEREIGN_STATE_DIM
except ImportError:
    SOVEREIGN_STATE_DIM = 32


class OntologyCompatibilityScorer(nn.Module):
    """
    Bilinear scorer for ontological compatibility between context and tokens.

    Given context state o_t in R^d and token codes O_tok in R^{V x d},
    computes S_ont(w) = o_t^T M o_w for all tokens w in the vocabulary
    (or a candidate shortlist).

    Args:
        state_dim: Dimension of ontological codes (default 32)
        use_low_rank: If True, factor M = A @ B^T for parameter efficiency
        rank: Rank for low-rank factorization (ignored if use_low_rank=False)
    """

    def __init__(
        self,
        state_dim: int = SOVEREIGN_STATE_DIM,
        use_low_rank: bool = True,
        rank: int = 8,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.use_low_rank = use_low_rank
        self.rank = rank

        if use_low_rank:
            # M_ont = A @ B^T, where A, B in R^{state_dim x rank}
            self.A = nn.Parameter(torch.empty(state_dim, rank))
            self.B = nn.Parameter(torch.empty(state_dim, rank))
            self._init_low_rank()
        else:
            # Full bilinear form M_ont in R^{state_dim x state_dim}
            self.M = nn.Parameter(torch.empty(state_dim, state_dim))
            self._init_full()

    def _init_low_rank(self):
        """Initialize low-rank factors for near-identity initial behavior."""
        nn.init.orthogonal_(self.A, gain=0.5)
        nn.init.orthogonal_(self.B, gain=0.5)

    def _init_full(self):
        """Initialize full bilinear form near identity."""
        nn.init.eye_(self.M)
        # Small perturbation to break symmetry
        with torch.no_grad():
            self.M.add_(torch.randn_like(self.M) * 0.01)

    def get_bilinear_matrix(self) -> torch.Tensor:
        """Return the effective M_ont matrix (for diagnostics)."""
        if self.use_low_rank:
            return self.A @ self.B.t()
        return self.M

    def forward(
        self,
        o_t: torch.Tensor,
        O_tok: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute ontological compatibility scores.

        Args:
            o_t: Context ontological state (B, T, d) or (B, d)
            O_tok: Token ontological codes (V, d) or (K, d) for shortlist

        Returns:
            Scores: (B, T, V) or (B, V) — one score per candidate token
        """
        # Compute M @ o_t -> intermediate vector
        if self.use_low_rank:
            # M @ o_t = A @ (B^T @ o_t)
            # o_t: (..., d), B: (d, r) -> B^T @ o_t: (..., r) -> A @ result: (..., d)
            intermediate = o_t @ self.B  # (..., r)
            m_o_t = intermediate @ self.A.t()  # (..., d)
        else:
            m_o_t = o_t @ self.M.t()  # (..., d)

        # S_ont = O_tok @ m_o_t^T -> scores over vocabulary
        # m_o_t: (..., d), O_tok: (V, d) -> scores: (..., V)
        scores = m_o_t @ O_tok.t()  # (..., V)

        return scores

    def score_shortlist(
        self,
        o_t: torch.Tensor,
        o_candidates: torch.Tensor,
    ) -> torch.Tensor:
        """
        Score a specific shortlist of candidate token codes.

        More memory-efficient than scoring the full vocabulary when only
        top-K candidates are needed.

        Args:
            o_t: Context state (..., d)
            o_candidates: Candidate token codes (..., K, d)

        Returns:
            Scores (..., K)
        """
        if self.use_low_rank:
            m_o_t = (o_t @ self.B) @ self.A.t()  # (..., d)
        else:
            m_o_t = o_t @ self.M.t()  # (..., d)

        # Batched dot product: (..., K)
        return (o_candidates * m_o_t.unsqueeze(-2)).sum(dim=-1)
