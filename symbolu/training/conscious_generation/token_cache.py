"""
TokenPrimitiveCache: Precomputed token-side representations for all primitives.

Phase 1 buffer:
  O_tok (V, 32)  — ontological codes via TokenOntologyProjector

Phase 2 buffers:
  P_tok (V, d_j) — plausibility representations
  R_tok (V, d_c) — CSR phonemic resonance representations
  V_tok (V, 5)   — Vritti cognitive mode profiles
  G_tok (V, 3)   — Guna energetic profiles

Total memory at V=50,257, fp16: 50,257 × (32+16+16+5+3) × 2 ≈ 7.2 MB.

Supports periodic chunked refresh during training and one-shot computation
at inference.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 1–2
"""

import torch
import torch.nn as nn
from typing import Optional, Dict, Any

from symbolu.training.conscious_generation.token_ontology import TokenOntologyProjector


class TokenPrimitiveCache(nn.Module):
    """
    Caches precomputed token-side representations for the full vocabulary.

    All caches are stored as non-parameter buffers (not trained directly).
    They are refreshed periodically by re-running respective projectors on
    the current embedding matrix, allowing them to track drift during training.

    Args:
        projector: TokenOntologyProjector that maps embeddings to 32D codes
        vocab_size: Vocabulary size
        state_dim: Ontological code dimension (32)
        refresh_interval: Steps between cache refreshes (0 = manual only)
        jepa_dim: JEPA representation dimension (d_j)
        csr_dim: CSR representation dimension (d_c)
        vritti_classes: Number of Vritti classes (5)
        guna_classes: Number of Guna classes (3)
    """

    def __init__(
        self,
        projector: TokenOntologyProjector,
        vocab_size: int,
        state_dim: int = 32,
        refresh_interval: int = 100,
        jepa_dim: int = 16,
        csr_dim: int = 16,
        vritti_classes: int = 5,
        guna_classes: int = 3,
    ):
        super().__init__()
        self.projector = projector
        self.vocab_size = vocab_size
        self.state_dim = state_dim
        self.refresh_interval = refresh_interval
        self.jepa_dim = jepa_dim
        self.csr_dim = csr_dim
        self.vritti_classes = vritti_classes
        self.guna_classes = guna_classes

        # Phase 1: Ontological codes
        self.register_buffer("O_tok", torch.zeros(vocab_size, state_dim))

        # Phase 2: Primitive-specific representations
        self.register_buffer("P_tok", torch.zeros(vocab_size, jepa_dim))
        self.register_buffer("R_tok", torch.zeros(vocab_size, csr_dim))
        self.register_buffer("V_tok", torch.zeros(vocab_size, vritti_classes))
        self.register_buffer("G_tok", torch.zeros(vocab_size, guna_classes))

        self.register_buffer("_step_counter", torch.tensor(0, dtype=torch.long))
        self._is_initialized = False

        # Phase 2 scorer references — set via set_scorers() after construction
        self._plausibility_scorer = None
        self._csr_scorer = None
        self._vritti_scorer = None
        self._guna_scorer = None
        self._csr_affinity_fn = None  # callable: (V, embed_dim) -> (V, 12)

    def set_scorers(
        self,
        jepa_scorer: Optional[Any] = None,
        csr_scorer: Optional[Any] = None,
        vritti_scorer: Optional[Any] = None,
        guna_scorer: Optional[Any] = None,
        csr_affinity_fn: Optional[Any] = None,
    ) -> None:
        """Register Phase 2 scorer modules for cache refresh."""
        self._plausibility_scorer = jepa_scorer
        self._csr_scorer = csr_scorer
        self._vritti_scorer = vritti_scorer
        self._guna_scorer = guna_scorer
        self._csr_affinity_fn = csr_affinity_fn

    @torch.no_grad()
    def refresh(
        self,
        embedding_weight: torch.Tensor,
        chunk_size: int = 4096,
        csr_affinity: Optional[torch.Tensor] = None,
    ) -> None:
        """
        Recompute all cached token-side representations.

        Processes in chunks to limit peak memory. Phase 2 buffers are only
        refreshed if their respective scorers have been registered.

        Args:
            embedding_weight: Token embedding matrix (V, embed_dim)
            chunk_size: Number of tokens to process per chunk
            csr_affinity: Precomputed CSR affinity vectors (V, 12).
                         If None and csr_affinity_fn is set, it will be called.
        """
        V = embedding_weight.shape[0]
        assert V == self.vocab_size, (
            f"Embedding vocab {V} != cache vocab {self.vocab_size}"
        )

        # Resolve CSR affinity if needed
        if csr_affinity is None and self._csr_scorer is not None and self._csr_affinity_fn is not None:
            csr_affinity = self._csr_affinity_fn(embedding_weight)

        for start in range(0, V, chunk_size):
            end = min(start + chunk_size, V)
            chunk_emb = embedding_weight[start:end]

            # Phase 1: Ontological codes
            o_chunk = self.projector(chunk_emb)
            self.O_tok[start:end] = o_chunk

            # Phase 2: Plausibility — needs [e_w; o_w]
            if self._plausibility_scorer is not None:
                self.P_tok[start:end] = self._plausibility_scorer.compute_token_repr(
                    chunk_emb, o_chunk
                )

            # Phase 2: CSR — needs phoneme affinity
            if self._csr_scorer is not None and csr_affinity is not None:
                self.R_tok[start:end] = self._csr_scorer.compute_token_repr(
                    csr_affinity[start:end]
                )

            # Phase 2: Vritti — needs embeddings
            if self._vritti_scorer is not None:
                self.V_tok[start:end] = self._vritti_scorer.compute_token_repr(
                    chunk_emb
                )

            # Phase 2: Guna — needs embeddings
            if self._guna_scorer is not None:
                self.G_tok[start:end] = self._guna_scorer.compute_token_repr(
                    chunk_emb
                )

        self._is_initialized = True

    def maybe_refresh(
        self,
        embedding_weight: torch.Tensor,
        step: int,
        csr_affinity: Optional[torch.Tensor] = None,
    ) -> bool:
        """
        Refresh cache if enough steps have elapsed since last refresh.

        Args:
            embedding_weight: Current token embedding matrix
            step: Current training step
            csr_affinity: Optional precomputed CSR affinity vectors

        Returns:
            True if cache was refreshed this call
        """
        if not self._is_initialized:
            self.refresh(embedding_weight, csr_affinity=csr_affinity)
            self._step_counter.fill_(step)
            return True

        if self.refresh_interval > 0 and (step - self._step_counter.item()) >= self.refresh_interval:
            self.refresh(embedding_weight, csr_affinity=csr_affinity)
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

    def get_cached_repr(
        self,
        name: str,
        token_ids: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Retrieve any cached representation by name.

        Args:
            name: One of 'O_tok', 'P_tok', 'R_tok', 'V_tok', 'G_tok'
            token_ids: Token indices. If None, returns full buffer.

        Returns:
            Cached representations for the requested primitive.
        """
        if not self._is_initialized:
            raise RuntimeError(
                "TokenPrimitiveCache not initialized. Call refresh() first."
            )

        buf = getattr(self, name, None)
        if buf is None:
            raise ValueError(f"Unknown cache buffer: {name}")

        if token_ids is None:
            return buf

        return buf[token_ids]

    def get_diagnostics(self) -> Dict[str, float]:
        """Return cache health diagnostics."""
        if not self._is_initialized:
            return {"initialized": False}

        with torch.no_grad():
            diag: Dict[str, Any] = {
                "initialized": True,
                "step": self._step_counter.item(),
            }

            # O_tok statistics
            diag["O_tok_mean"] = self.O_tok.mean().item()
            diag["O_tok_std"] = self.O_tok.std().item()
            diag["O_tok_min"] = self.O_tok.min().item()
            diag["O_tok_max"] = self.O_tok.max().item()

            # Bhava entropy
            bhava = self.O_tok[:, 0:12]
            diag["bhava_entropy"] = -(
                bhava * (bhava + 1e-8).log()
            ).sum(dim=-1).mean().item()

            # Phase 2 buffer norms (if populated)
            for name, buf in [
                ("P_tok", self.P_tok),
                ("R_tok", self.R_tok),
                ("V_tok", self.V_tok),
                ("G_tok", self.G_tok),
            ]:
                norm = buf.norm(dim=-1).mean().item()
                diag[f"{name}_mean_norm"] = norm

            return diag
