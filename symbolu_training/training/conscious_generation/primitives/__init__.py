"""
Primitive scoring heads for Conscious Generation.

Phase 1: OntologyCompatibilityScorer
Phase 2: BaseScorer, PlausibilityTokenScorer, CSRTokenScorer, VrittiTokenScorer,
         GunaTokenScorer, TokenEvaluationTensor (orchestrator)
"""

from symbolu_training.training.conscious_generation.primitives.ontology_scorer import (
    OntologyCompatibilityScorer,
)
from symbolu_training.training.conscious_generation.primitives.base_scorer import BaseScorer
from symbolu_training.training.conscious_generation.primitives.jepa_scorer import (
    PlausibilityTokenScorer,
    JEPATokenScorer,  # backward-compatible alias
)
from symbolu_training.training.conscious_generation.primitives.csr_scorer import CSRTokenScorer
from symbolu_training.training.conscious_generation.primitives.vritti_scorer import VrittiTokenScorer
from symbolu_training.training.conscious_generation.primitives.guna_scorer import GunaTokenScorer
from symbolu_training.training.conscious_generation.primitives.crs_combined_scorer import CRSCombinedScorer

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Dict, Any


class TokenEvaluationTensor(nn.Module):
    """
    Orchestrator that produces T_t ∈ ℝ^{K×6} — multi-dimensional evaluation
    of K candidate tokens at each position.

    Steps:
      1. Extract top-K candidates from base logits
      2. Gather cached token-side representations for the K candidates
      3. Compute context-side representations from (hidden, o_ctx)
      4. Score each primitive: base, ontology, plausibility, CSR, Vritti, Guna
      5. Stack into T_t ∈ ℝ^{K×6}

    Column order: [S_base, S_ont, S_plausibility, S_csr, S_vritti, S_guna]

    Args:
        base_scorer: BaseScorer instance
        ontology_scorer: OntologyCompatibilityScorer instance
        jepa_scorer: PlausibilityTokenScorer instance
        csr_scorer: CSRTokenScorer instance
        vritti_scorer: VrittiTokenScorer instance
        guna_scorer: GunaTokenScorer instance
        shortlist_k: Number of top-K candidates to evaluate
    """

    PRIMITIVE_NAMES = ["base", "ontology", "jepa", "csr", "vritti", "guna"]
    NUM_PRIMITIVES = 6

    def __init__(
        self,
        base_scorer: BaseScorer,
        ontology_scorer: OntologyCompatibilityScorer,
        jepa_scorer: PlausibilityTokenScorer,
        csr_scorer: CSRTokenScorer,
        vritti_scorer: VrittiTokenScorer,
        guna_scorer: GunaTokenScorer,
        shortlist_k: int = 128,
        crs_combined_scorer: Optional[CRSCombinedScorer] = None,
    ):
        super().__init__()
        self.base_scorer = base_scorer
        self.ontology_scorer = ontology_scorer
        self.jepa_scorer = jepa_scorer
        self.csr_scorer = csr_scorer
        self.vritti_scorer = vritti_scorer
        self.guna_scorer = guna_scorer
        self.shortlist_k = shortlist_k
        # CRS Phase 2: When set, column 3 becomes combined CRS instead of raw CSR
        self.crs_combined_scorer = crs_combined_scorer

    def select_candidates(
        self, logits: torch.Tensor, k: Optional[int] = None
    ) -> tuple:
        """
        Select top-K candidate tokens from base logits.

        Args:
            logits: Full vocabulary logits (..., V)
            k: Override shortlist size (default: self.shortlist_k)

        Returns:
            (candidate_scores, candidate_ids):
                candidate_scores: (..., K) base logit scores
                candidate_ids: (..., K) token indices
        """
        k = k or self.shortlist_k
        k = min(k, logits.shape[-1])
        return logits.topk(k, dim=-1)

    def forward(
        self,
        logits: torch.Tensor,
        hidden: torch.Tensor,
        o_ctx: torch.Tensor,
        cache: Any,
        k: Optional[int] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute the Token Evaluation Tensor T_t for top-K candidates.

        Args:
            logits: Full vocabulary logits (..., V)
            hidden: Transformer hidden states (..., embed_dim)
            o_ctx: Context ontological state (..., state_dim)
            cache: TokenPrimitiveCache with populated buffers
            k: Override shortlist size

        Returns:
            Dict with keys:
                'T': Token Evaluation Tensor (..., K, 6)
                'candidate_ids': Token indices (..., K)
                'candidate_base_scores': Base logit scores (..., K)
        """
        # Step 1: Select top-K candidates
        base_scores, candidate_ids = self.select_candidates(logits, k)
        K = candidate_ids.shape[-1]

        # Step 2: Gather cached representations for candidates
        # candidate_ids shape: (..., K) — flatten for indexing, then reshape
        flat_ids = candidate_ids.reshape(-1)

        O_cand = cache.get_cached_repr("O_tok", flat_ids).reshape(
            *candidate_ids.shape, -1
        )  # (..., K, 32)
        P_cand = cache.get_cached_repr("P_tok", flat_ids).reshape(
            *candidate_ids.shape, -1
        )  # (..., K, d_j)
        R_cand = cache.get_cached_repr("R_tok", flat_ids).reshape(
            *candidate_ids.shape, -1
        )  # (..., K, d_c)
        V_cand = cache.get_cached_repr("V_tok", flat_ids).reshape(
            *candidate_ids.shape, -1
        )  # (..., K, 5)
        G_cand = cache.get_cached_repr("G_tok", flat_ids).reshape(
            *candidate_ids.shape, -1
        )  # (..., K, 3)

        # Step 3: Compute context-side representations
        # Ontology scorer uses o_ctx directly (no separate context projection)
        # Expand o_ctx to match hidden's sequence dimension if needed:
        # hidden is [B, T, D], o_ctx may be [B, state_dim] (pooled) from
        # MistralCGWrapper. Scorers' compute_context_repr expect matching dims.
        _o_ctx = o_ctx
        if hidden.dim() == 3 and o_ctx.dim() == 2:
            _o_ctx = o_ctx.unsqueeze(1).expand(-1, hidden.shape[1], -1)  # [B, T, state_dim]
        p_ctx = self.jepa_scorer.compute_context_repr(hidden, _o_ctx)  # (..., d_j)
        r_ctx = self.csr_scorer.compute_context_repr(hidden, _o_ctx)  # (..., d_c)
        v_ctx = self.vritti_scorer.compute_context_repr(hidden, _o_ctx)  # (..., 5)
        g_ctx = self.guna_scorer.compute_context_repr(hidden, _o_ctx)  # (..., 3)

        # Step 4: Score each primitive over the K candidates
        s_base = base_scores

        # S_ont: o_ctx^T @ M @ o_cand for each candidate
        s_ont = self._score_ontology(_o_ctx, O_cand)

        # S_jepa: p_ctx (..., d_j) vs P_cand (..., K, d_j)
        s_jepa = self._score_bilinear(
            p_ctx, P_cand, self.jepa_scorer
        )

        # Column 3: CRS combined score (when enabled) or legacy CSR
        crs_branch_data = None
        if self.crs_combined_scorer is not None:
            # Gather S_tok for candidates (CRS semantic cache)
            S_cand = cache.get_cached_repr("S_tok", flat_ids).reshape(
                *candidate_ids.shape, -1
            )  # (..., K, d_s)

            # Kosha slices for C branch
            kosha_ctx = F.softmax(_o_ctx[..., 12:17], dim=-1)
            Kosha_cand = O_cand[..., 12:17]

            crs_result = self.crs_combined_scorer(
                v_ctx=v_ctx,
                kosha_ctx=kosha_ctx,
                V_cand=V_cand,
                Kosha_cand=Kosha_cand,
                r_ctx=r_ctx,
                R_cand=R_cand,
                hidden=hidden,
                o_ctx=_o_ctx,
                S_cand=S_cand,
                base_logits_cand=base_scores,
            )
            s_col3 = crs_result["crs_score"]
            crs_branch_data = crs_result  # saved for diagnostics
        else:
            # Legacy CSR path
            s_col3 = self._score_bilinear(
                r_ctx, R_cand, self.csr_scorer
            )

        # S_vritti: dot product v_ctx (..., 5) vs V_cand (..., K, 5)
        s_vritti = torch.einsum("...d,...kd->...k", v_ctx, V_cand)

        # S_guna: g_ctx^T @ G @ g_tok for each candidate
        g_transformed = g_ctx @ self.guna_scorer.G  # (..., 3)
        s_guna = torch.einsum("...d,...kd->...k", g_transformed, G_cand)

        # Step 5: Stack into T_t ∈ ℝ^{..., K, 6}
        # Column order: [S_base, S_ont, S_plausibility, CRS_or_CSR, S_vritti, S_guna]
        T = torch.stack([s_base, s_ont, s_jepa, s_col3, s_vritti, s_guna], dim=-1)

        result = {
            "T": T,
            "candidate_ids": candidate_ids,
            "candidate_base_scores": base_scores,
        }
        if crs_branch_data is not None:
            result["crs_branch_data"] = crs_branch_data
        return result

    def _score_ontology(
        self, o_ctx: torch.Tensor, O_cand: torch.Tensor
    ) -> torch.Tensor:
        """
        Score ontology for K candidates per position.

        Args:
            o_ctx: Context ontology repr (..., d_o)
            O_cand: Candidate ontology codes (..., K, 32)

        Returns:
            Scores (..., K)
        """
        scorer = self.ontology_scorer
        if scorer.use_low_rank:
            intermediate = o_ctx @ scorer.B  # (..., rank)
            m_o = intermediate @ scorer.A.t()  # (..., state_dim)
        else:
            m_o = o_ctx @ scorer.M.t()  # (..., state_dim)

        # (..., state_dim) @ (..., K, state_dim)^T -> (..., K)
        return torch.einsum("...d,...kd->...k", m_o, O_cand)

    def _score_bilinear(
        self, ctx: torch.Tensor, tok_cand: torch.Tensor, scorer: nn.Module
    ) -> torch.Tensor:
        """
        Score bilinear form for K candidates per position.

        Args:
            ctx: Context repr (..., d)
            tok_cand: Candidate reprs (..., K, d)
            scorer: Scorer with A/B or M parameters

        Returns:
            Scores (..., K)
        """
        if scorer.use_low_rank:
            intermediate = ctx @ scorer.B  # (..., rank)
            m_ctx = intermediate @ scorer.A.t()  # (..., d)
        else:
            m_ctx = ctx @ scorer.M.t()  # (..., d)

        return torch.einsum("...d,...kd->...k", m_ctx, tok_cand)


__all__ = [
    "OntologyCompatibilityScorer",
    "BaseScorer",
    "PlausibilityTokenScorer",
    "JEPATokenScorer",  # backward-compatible alias
    "CSRTokenScorer",
    "CRSCombinedScorer",
    "VrittiTokenScorer",
    "GunaTokenScorer",
    "TokenEvaluationTensor",
]
