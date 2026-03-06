"""
TwoStageGenerator: End-to-end inference pipeline for field-integrated generation.

Stage 1: Extract top-K candidates from base transformer logits.
Stage 2: Full primitive re-ranking via TokenEvaluationTensor → IntegratedTokenScorer
         → FieldIntegratedSoftmax.

This module is used at inference time by OntologicalHybridTransformer.generate()
when use_field_integrated_softmax=True.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 4 (D.6)
"""

import torch
import torch.nn as nn
from typing import Dict, Optional


class TwoStageGenerator(nn.Module):
    """
    Two-stage generation: base shortlist → field-integrated re-ranking.

    Orchestrates the full pipeline:
      1. Get top-K from base logits
      2. Run TokenEvaluationTensor to score candidates per primitive
      3. Run IntegratedTokenScorer (Kosha + Bliss) to get Z*(w)
      4. Run FieldIntegratedSoftmax for final distribution

    Args:
        token_eval_tensor: TokenEvaluationTensor module (Phase 2).
        integrated_scorer: IntegratedTokenScorer module (Phase 3).
        field_softmax: FieldIntegratedSoftmax module (Phase 4).
        shortlist_k: Number of candidates to extract from base logits.
    """

    def __init__(
        self,
        token_eval_tensor: nn.Module,
        integrated_scorer: nn.Module,
        field_softmax: nn.Module,
        shortlist_k: int = 128,
    ):
        super().__init__()
        self.token_eval_tensor = token_eval_tensor
        self.integrated_scorer = integrated_scorer
        self.field_softmax = field_softmax
        self.shortlist_k = shortlist_k

    def forward(
        self,
        logits: torch.Tensor,
        hidden: torch.Tensor,
        o_ctx: torch.Tensor,
        cache: Optional[object] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Run the two-stage generation pipeline.

        Args:
            logits: Base transformer logits (..., V).
            hidden: Transformer hidden states (..., embed_dim).
            o_ctx: Context ontological state (..., state_dim).
            cache: TokenPrimitiveCache instance (for TET).

        Returns:
            Dict with keys:
                'log_probs': Full-vocab log-probabilities (..., V).
                'probs': Full-vocab probabilities (..., V).
                'Z_star': Bliss-gated scores (..., K).
                'alpha': Kosha routing weights (..., 6).
                'B': Bliss values (..., K).
                'D': Disagreement values (..., K).
                'candidate_ids': Shortlist token IDs (..., K).
                'shortlist_log_probs': Log-probs over shortlist (..., K).
        """
        # Stage 1: Build Token Evaluation Tensor (extracts top-K, scores per primitive)
        tet_result = self.token_eval_tensor(
            logits=logits,
            hidden=hidden,
            o_ctx=o_ctx,
            cache=cache,
            k=self.shortlist_k,
        )
        T = tet_result['T']                        # (..., K, 6)
        candidate_ids = tet_result['candidate_ids']  # (..., K)

        # Stage 2: Integrated scoring (Kosha routing + Bliss gating)
        integ_result = self.integrated_scorer(
            T=T,
            hidden=hidden,
            o_ctx=o_ctx,
            candidate_ids=candidate_ids,
        )
        Z_star = integ_result['Z_star']  # (..., K)

        # Stage 3: Field-integrated softmax → full-vocab distribution
        softmax_result = self.field_softmax(
            Z_star=Z_star,
            candidate_ids=candidate_ids,
            T=T,
            Z=integ_result.get("Z"),
            B=integ_result.get("B"),
        )

        # Merge all results
        return {
            "log_probs": softmax_result["log_probs"],
            "probs": softmax_result["probs"],
            "shortlist_log_probs": softmax_result["shortlist_log_probs"],
            "Z_star": Z_star,
            "T": T,
            "alpha": integ_result["alpha"],
            "B": integ_result["B"],
            "D": integ_result["D"],
            "candidate_ids": candidate_ids,
        }
