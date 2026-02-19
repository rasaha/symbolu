"""
SpandaHybridWrapper: Wraps any backbone transformer with Spanda emission.

Replaces lm_head emission with anchor-based emission while keeping
the backbone and softmax unchanged.

Compatible with PhaseTransformer and StandardTransformer.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Any, Optional

from .state import SpandaState
from .emission import AnchorEmission
from .regularizers import SpandaRegularizers


class SpandaHybridWrapper(nn.Module):
    """
    Wraps a backbone transformer with Spanda emission.

    Architecture:
        h_t = backbone(x_<=t)                 # unchanged
        Delta_t = MLP(h_t)                     # SpandaState
        Psi_t = gamma * Psi_{t-1} + Delta_t   # leaky integration
        Psi_t = norm_clamp(Psi_t)              # bounded
        z_y = -||Psi_t - A[y]||^2 / tau       # AnchorEmission
        p(y) = softmax(z_y)                    # unchanged

    The backbone's lm_head and logit_scale are NOT used; emission goes
    through Spanda instead.

    Args:
        backbone: A PhaseTransformer or StandardTransformer instance.
        psi_dim: Dimension of Psi state (default 256).
        decay_gamma: Leaky integration factor (default 0.99).
        alpha: L_step regularizer weight (default 1e-4).
        beta: L_smooth regularizer weight (default 1e-4).
    """

    def __init__(
        self,
        backbone: nn.Module,
        psi_dim: int = 256,
        decay_gamma: float = 0.99,
        alpha: float = 1e-4,
        beta: float = 1e-4,
    ):
        super().__init__()

        self.backbone = backbone
        embed_dim = backbone.config.embed_dim
        vocab_size = backbone.config.vocab_size

        # Spanda modules
        self.spanda_state = SpandaState(
            embed_dim=embed_dim,
            psi_dim=psi_dim,
            decay_gamma=decay_gamma,
        )
        self.anchor_emission = AnchorEmission(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            psi_dim=psi_dim,
        )
        self.regularizers = SpandaRegularizers(alpha=alpha, beta=beta)

        # Store config for external access
        self.psi_dim = psi_dim
        self.decay_gamma = decay_gamma

    def forward(
        self,
        input_ids: torch.Tensor,
        return_hidden: bool = False,
        return_spanda_state: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Forward pass with Spanda emission replacing lm_head.

        Args:
            input_ids: [B, N] token indices.
            return_hidden: Return backbone hidden states.
            return_spanda_state: Return Psi and Delta for diagnostics.
            **kwargs: Additional args passed to backbone forward.

        Returns:
            Dict with:
                'logits': [B, T, V] from anchor emission
                'reg_losses': dict with l_step, l_smooth, total_reg
                'psi': [B, T, psi_dim] (if return_spanda_state)
                'delta': [B, T, psi_dim] (if return_spanda_state)
                'hidden_states': (if return_hidden)
                'last_hidden_state': [B, T, embed_dim]
        """
        # Get hidden states from backbone (before lm_head).
        # PhaseTransformer has forward_hidden(); StandardTransformer uses
        # forward(return_last_hidden=True).
        if hasattr(self.backbone, "forward_hidden"):
            h = self.backbone.forward_hidden(input_ids)  # [B, T, embed_dim]
        else:
            backbone_out = self.backbone(input_ids, return_last_hidden=True)
            h = backbone_out["last_hidden_state"]  # [B, T, embed_dim]

        # Spanda state evolution
        psi, delta = self.spanda_state(h)  # [B, T, psi_dim], [B, T, psi_dim]

        # Anchor emission (replaces lm_head)
        token_embed_weight = self.backbone.token_embed.weight  # [V, embed_dim]
        logits = self.anchor_emission(psi, token_embed_weight)  # [B, T, V]

        # Regularization losses
        reg_losses = self.regularizers(delta)

        result = {
            "logits": logits,
            "reg_losses": reg_losses,
            "last_hidden_state": h,
        }

        if return_spanda_state:
            result["psi"] = psi
            result["delta"] = delta

        return result

    def set_regularizer_phase(self, phase: int):
        """Set regularizer phase (1=CE only, 2=+L_step, 3=+L_step+L_smooth)."""
        self.regularizers.set_phase(phase)

    @property
    def config(self):
        """Proxy to backbone config."""
        return self.backbone.config

    def get_anchors_normalized(self) -> torch.Tensor:
        """Get current unit-norm anchors for diagnostics."""
        token_embed_weight = self.backbone.token_embed.weight
        return self.anchor_emission.get_anchors_normalized(token_embed_weight)

    @property
    def temperature(self) -> float:
        """Current emission temperature."""
        return self.anchor_emission.temperature
