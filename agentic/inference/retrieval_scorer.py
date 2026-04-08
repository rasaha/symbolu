#!/usr/bin/env python3
"""
Retrieval Score Provider for Logit Modulation
===============================================

Computes token-level retrieval scores R_y for the logit modulation
decoding rule:

    modified_logits = base_logits + α·R_y − β·C_y

Three scoring strategies are supported (configurable):

1. **dot_product** — Dot product between token embedding and retrieved
   context embedding.
2. **cosine** — Cosine similarity between token embedding and retrieved
   context embedding.
3. **external** — External retriever relevance score aligned to
   vocabulary tokens (passed directly).

Shape guarantee: retrieval_scores.shape == base_logits.shape

Author: Sovereign-1 Training Initiative
Date: February 2026
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

try:
    import torch
    import torch.nn.functional as F

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

if PYTORCH_AVAILABLE:

    class RetrievalStrategy(Enum):
        """Available retrieval scoring strategies."""

        DOT_PRODUCT = "dot_product"
        COSINE = "cosine"
        EXTERNAL = "external"

    @dataclass
    class RetrievalScorerConfig:
        """Configuration for retrieval scoring.

        Attributes:
            strategy: Which scoring method to use.
            normalize_scores: Whether to zero-mean and unit-variance
                normalize the retrieval scores before applying them.
            temperature: Temperature scaling applied to raw scores
                before they enter the logit modulation formula.
        """

        strategy: RetrievalStrategy = RetrievalStrategy.COSINE
        normalize_scores: bool = True
        temperature: float = 1.0

    class RetrievalScorer:
        """Computes per-token retrieval scores aligned to vocabulary.

        Given a retrieved context embedding and a vocabulary embedding
        matrix, produces a score tensor of shape [B, V] that can be
        added directly to base logits (after scaling by α).
        """

        def __init__(self, config: Optional[RetrievalScorerConfig] = None):
            self.config = config or RetrievalScorerConfig()

        def score(
            self,
            context_embedding: torch.Tensor,
            vocab_embeddings: torch.Tensor,
            external_scores: Optional[torch.Tensor] = None,
        ) -> torch.Tensor:
            """Compute retrieval scores for each vocab token.

            Args:
                context_embedding: [B, D] embedding of retrieved context.
                vocab_embeddings: [V, D] embedding matrix of the model.
                external_scores: [B, V] pre-computed external retriever
                    scores. Required only when strategy=EXTERNAL.

            Returns:
                scores: [B, V] retrieval scores aligned to vocabulary.

            Raises:
                ValueError: If strategy is EXTERNAL and no external_scores
                    are provided.
            """
            strategy = self.config.strategy

            if strategy == RetrievalStrategy.DOT_PRODUCT:
                # [B, D] @ [D, V] -> [B, V]
                scores = torch.matmul(context_embedding, vocab_embeddings.T)

            elif strategy == RetrievalStrategy.COSINE:
                # Normalize both
                ctx_norm = F.normalize(context_embedding, dim=-1)  # [B, D]
                vocab_norm = F.normalize(vocab_embeddings, dim=-1)  # [V, D]
                scores = torch.matmul(ctx_norm, vocab_norm.T)  # [B, V]

            elif strategy == RetrievalStrategy.EXTERNAL:
                if external_scores is None:
                    raise ValueError(
                        "external_scores must be provided when "
                        "strategy=EXTERNAL"
                    )
                scores = external_scores

            else:
                raise ValueError(f"Unknown retrieval strategy: {strategy}")

            # Apply temperature
            if self.config.temperature != 1.0:
                scores = scores / max(self.config.temperature, 1e-8)

            # Normalize to zero-mean, unit-variance
            if self.config.normalize_scores:
                mean = scores.mean(dim=-1, keepdim=True)
                std = scores.std(dim=-1, keepdim=True).clamp(min=1e-8)
                scores = (scores - mean) / std

            return scores

        def score_from_hidden(
            self,
            hidden_state: torch.Tensor,
            vocab_embeddings: torch.Tensor,
            retrieved_chunks: Optional[torch.Tensor] = None,
        ) -> torch.Tensor:
            """Compute retrieval scores using hidden state as context.

            Convenience method when retrieved context is the model's own
            hidden state (e.g., for self-retrieval or attention-based
            retrieval).

            Args:
                hidden_state: [B, D] model hidden state.
                vocab_embeddings: [V, D] embedding matrix.
                retrieved_chunks: [B, N, D] optional retrieved chunk
                    embeddings. If provided, they are mean-pooled to
                    produce the context embedding. Otherwise hidden_state
                    is used directly.

            Returns:
                scores: [B, V] retrieval scores.
            """
            if retrieved_chunks is not None:
                # Mean-pool retrieved chunks
                context = retrieved_chunks.mean(dim=1)  # [B, D]
            else:
                context = hidden_state

            return self.score(context, vocab_embeddings)

else:
    class RetrievalStrategy:  # type: ignore[no-redef]
        pass

    class RetrievalScorerConfig:  # type: ignore[no-redef]
        pass

    class RetrievalScorer:  # type: ignore[no-redef]
        pass
