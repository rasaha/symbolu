"""
TokenPrimitiveCache: Precomputed ontological codes for the full vocabulary.

Maintains a contiguous buffer O_tok of shape (V, 32) computed from the
embedding matrix via TokenOntologyProjector. Supports:
  - Periodic refresh during training (every N steps)
  - One-shot computation at inference
  - Efficient matrix-vector products for scoring

Phase 2 will extend this cache with additional token-side representations
(P_tok for JEPA, R_tok for CSR, V_tok for Vritti, G_tok for Guna).

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 1
"""

import torch
import torch.nn as nn
from typing import Optional, Dict

from symbolu.training.conscious_generation.token_ontology import TokenOntologyProjector


class TokenPrimitiveCache(nn.Module):
    """
    Caches precomputed token-side ontological representations for the full vocabulary.

    The cache is stored as a non-parameter buffer (not trained directly).
    It is refreshed periodically by re-running the projector on the current
    embedding matrix, allowing it to track embedding drift during training.

    Memory at V=50,257, state_dim=32, fp16: ~3.2 MB (negligible).

    Args:
        projector: TokenOntologyProjector that maps embeddings to 32D codes
        vocab_size: Vocabulary size
        state_dim: Ontological code dimension
        refresh_interval: Steps between cache refreshes (0 = manual only)
    """

    def __init__(
        self,
        projector: TokenOntologyProjector,
        vocab_size: int,
        state_dim: int = 32,
        refresh_interval: int = 100,
    ):
        super().__init__()
        self.projector = projector
        self.vocab_size = vocab_size
        self.state_dim = state_dim
        self.refresh_interval = refresh_interval

        # Cache buffer — not a parameter, but moves with .to(device)
        self.register_buffer("O_tok", torch.zeros(vocab_size, state_dim))
        self.register_buffer("_step_counter", torch.tensor(0, dtype=torch.long))
        self._is_initialized = False

    @torch.no_grad()
    def refresh(self, embedding_weight: torch.Tensor, chunk_size: int = 4096) -> None:
        """
        Recompute O_tok from the current embedding matrix.

        Processes in chunks to avoid materializing the full (V, embed_dim) -> (V, 32)
        computation in one pass on memory-constrained devices.

        Args:
            embedding_weight: Token embedding matrix (V, embed_dim)
            chunk_size: Number of tokens to process per chunk
        """
        V = embedding_weight.shape[0]
        assert V == self.vocab_size, (
            f"Embedding vocab {V} != cache vocab {self.vocab_size}"
        )

        for start in range(0, V, chunk_size):
            end = min(start + chunk_size, V)
            chunk = embedding_weight[start:end]
            self.O_tok[start:end] = self.projector(chunk)

        self._is_initialized = True

    def maybe_refresh(
        self, embedding_weight: torch.Tensor, step: int
    ) -> bool:
        """
        Refresh cache if enough steps have elapsed since last refresh.

        Args:
            embedding_weight: Current token embedding matrix
            step: Current training step

        Returns:
            True if cache was refreshed this call
        """
        if not self._is_initialized:
            self.refresh(embedding_weight)
            self._step_counter.fill_(step)
            return True

        if self.refresh_interval > 0 and (step - self._step_counter.item()) >= self.refresh_interval:
            self.refresh(embedding_weight)
            self._step_counter.fill_(step)
            return True

        return False

    def get_token_codes(self, token_ids: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Retrieve ontological codes for specific tokens or the full vocabulary.

        Args:
            token_ids: Token indices (any shape). If None, returns full O_tok.

        Returns:
            Ontological codes. Shape (*token_ids.shape, state_dim) or (V, state_dim).
        """
        if not self._is_initialized:
            raise RuntimeError(
                "TokenPrimitiveCache not initialized. Call refresh() first."
            )

        if token_ids is None:
            return self.O_tok

        return self.O_tok[token_ids]

    def get_diagnostics(self) -> Dict[str, float]:
        """Return cache health diagnostics."""
        if not self._is_initialized:
            return {"initialized": False}

        with torch.no_grad():
            # Check for degenerate values
            o_mean = self.O_tok.mean().item()
            o_std = self.O_tok.std().item()
            o_min = self.O_tok.min().item()
            o_max = self.O_tok.max().item()

            # Per-subgroup statistics
            bhava_entropy = -(
                self.O_tok[:, 0:12] * (self.O_tok[:, 0:12] + 1e-8).log()
            ).sum(dim=-1).mean().item()

            return {
                "initialized": True,
                "step": self._step_counter.item(),
                "O_tok_mean": o_mean,
                "O_tok_std": o_std,
                "O_tok_min": o_min,
                "O_tok_max": o_max,
                "bhava_entropy": bhava_entropy,
            }
