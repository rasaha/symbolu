"""
AnchorEmission: Distance-based logit computation via algebraic expansion.

Logits: z_y = (-||Psi||^2 + 2 * Psi^T A[y] - ||A[y]||^2) / tau

Anchors are normalized to unit norm every forward pass.
Temperature tau is learnable (log-parametrized), initialized to psi_dim / 30.

Weight tying uses Option B: anchors = normalize(Projection(token_embedding.weight)).
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class AnchorEmission(nn.Module):
    """
    Anchor-based emission: computes logits as negative squared distance
    from Psi to vocabulary anchors, divided by learnable temperature.

    Uses algebraic expansion to avoid [B, T, V, psi_dim] diff tensor.

    Args:
        vocab_size: Vocabulary size.
        embed_dim: Embedding dimension of backbone (for projection).
        psi_dim: Dimension of Psi / anchor space.
    """

    def __init__(self, vocab_size: int, embed_dim: int, psi_dim: int = 256):
        super().__init__()
        self.vocab_size = vocab_size
        self.psi_dim = psi_dim

        # Option B weight tying: projection from embed_dim -> psi_dim
        self.anchor_proj = nn.Linear(embed_dim, psi_dim, bias=False)

        # Learnable temperature, log-parameterized to stay positive.
        # Initialize tau = psi_dim / 30.
        self.log_temperature = nn.Parameter(
            torch.tensor(math.log(psi_dim / 30.0))
        )

    def forward(
        self, psi: torch.Tensor, token_embed_weight: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute logits via algebraic expansion of negative squared distance.

        Args:
            psi: [B, T, psi_dim] -- Psi state sequence.
            token_embed_weight: [V, embed_dim] -- token embedding weight matrix.

        Returns:
            logits: [B, T, V]
        """
        tau = self.log_temperature.exp()

        # Option B: project token embeddings and normalize to unit norm
        anchors = F.normalize(self.anchor_proj(token_embed_weight), dim=-1)  # [V, psi_dim]

        # Algebraic expansion of -||Psi - A[y]||^2 / tau:
        # = (-||Psi||^2 + 2 * Psi^T A[y] - ||A[y]||^2) / tau
        #
        # Since anchors are unit-norm: ||A[y]||^2 = 1 for all y.
        anchor_norm_sq = torch.ones(
            anchors.size(0), device=anchors.device, dtype=anchors.dtype
        )  # [V] = 1.0
        psi_norm_sq = (psi ** 2).sum(dim=-1, keepdim=True)  # [B, T, 1]
        dot = psi @ anchors.T  # [B, T, V]

        logits = (2 * dot - anchor_norm_sq.unsqueeze(0).unsqueeze(0) - psi_norm_sq) / tau
        return logits  # [B, T, V]

    def get_anchors_normalized(self, token_embed_weight: torch.Tensor) -> torch.Tensor:
        """Return unit-norm anchors for diagnostics."""
        return F.normalize(self.anchor_proj(token_embed_weight), dim=-1)

    @property
    def temperature(self) -> float:
        """Current temperature value (for logging)."""
        return self.log_temperature.exp().item()
