"""
TokenOntologyProjector: Per-token ontological projection.

Maps token embeddings e_w -> o_w in R^32 using the same subgroup
normalization as the context-side SovereignStateProjector:
  - Bhava[0:12]:   softmax (ontological identity distribution)
  - Kosha[12:17]:  softmax (consciousness sheath distribution)
  - Vritti[17:22]: softmax (cognitive mode distribution)
  - Guna[22:28]:   sigmoid (independent energy activations)
  - Reserved[28:32]: tanh (bounded feedback signals)

This gives every vocabulary token its own "ontological code" o_w,
enabling all downstream primitive scorers to compute token-context
compatibility in the shared 32D manifold.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 1
"""

import torch
import torch.nn as nn
from typing import Optional

try:
    from symbolu.phase_transformer import (
        SOVEREIGN_STATE_DIM,
        BHAVA_SLICE,
        KOSHA_SLICE,
    )
except ImportError:
    SOVEREIGN_STATE_DIM = 32
    BHAVA_SLICE = slice(0, 12)
    KOSHA_SLICE = slice(12, 17)


class TokenOntologyProjector(nn.Module):
    """
    Projects token embeddings to 32D ontological codes with subgroup normalization.

    Architecture: LayerNorm -> Linear(embed_dim, state_dim)
    Single linear layer (no MLP) — tokens have less context than hidden states,
    so a simpler projector avoids overfitting to surface-level embedding patterns.

    Args:
        embed_dim: Token embedding dimension (e.g. 512, 768)
        state_dim: Ontological code dimension (default 32, must match sovereign state)
    """

    # Subgroup ranges matching SovereignStateProjector
    BHAVA_RANGE = (0, 12)
    KOSHA_RANGE = (12, 17)
    VRITTI_RANGE = (17, 22)
    GUNA_RANGE = (22, 28)
    RESERVED_RANGE = (28, 32)

    def __init__(self, embed_dim: int, state_dim: int = SOVEREIGN_STATE_DIM):
        super().__init__()
        self.embed_dim = embed_dim
        self.state_dim = state_dim

        self.layer_norm = nn.LayerNorm(embed_dim)
        self.proj = nn.Linear(embed_dim, state_dim)

        self._init_weights()

    def _init_weights(self):
        """Initialize for near-uniform initial distributions."""
        with torch.no_grad():
            nn.init.xavier_normal_(self.proj.weight, gain=0.5)
            self.proj.bias.fill_(0.0)

    def forward(self, embeddings: torch.Tensor) -> torch.Tensor:
        """
        Project token embeddings to ontological codes.

        Args:
            embeddings: Token embeddings [..., embed_dim]

        Returns:
            Ontological codes [..., state_dim] with subgroup normalization applied
        """
        raw = self.proj(self.layer_norm(embeddings))
        return self._apply_constraints(raw)

    def forward_raw(self, embeddings: torch.Tensor) -> torch.Tensor:
        """Return raw (pre-normalization) projection for diagnostics."""
        return self.proj(self.layer_norm(embeddings))

    def _apply_constraints(self, raw: torch.Tensor) -> torch.Tensor:
        """Apply subgroup normalization matching SovereignStateProjector."""
        bhava = torch.softmax(raw[..., 0:12], dim=-1)
        kosha = torch.softmax(raw[..., 12:17], dim=-1)
        vritti = torch.softmax(raw[..., 17:22], dim=-1)
        guna = torch.sigmoid(raw[..., 22:28])
        reserved = torch.tanh(raw[..., 28:32])

        return torch.cat([bhava, kosha, vritti, guna, reserved], dim=-1)
