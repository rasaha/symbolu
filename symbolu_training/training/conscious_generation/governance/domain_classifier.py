"""
DomainClassifier: Learned domain classification for CG governance routing.

Replaces the hardcoded Gyroscope → domain bridge with a learned projector
that maps hidden-state context to an 8-category domain distribution.

The 8 categories match KoshaDomainRouter.DEFAULT_DOMAINS:
  0: code, 1: math, 2: factual, 3: chat,
  4: emotional, 5: narrative, 6: planning, 7: retrieval

Input: pooled hidden state + sovereign state (available in CG training path)
Output: 8-dim softmax domain distribution

When disabled (flag off), the existing hardcoded domain_bridge.py path
remains active. When enabled, this classifier's output replaces it.

Reference: docs/design/DOMAIN_CONDITIONING_ARCHITECTURE.md (MVP subset)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional


NUM_DOMAINS = 8
DOMAIN_NAMES = ["code", "math", "factual", "chat", "emotional", "narrative", "planning", "retrieval"]


class DomainClassifier(nn.Module):
    """
    Lightweight learned domain classifier for CG governance routing.

    Maps pooled hidden state (+ optional sovereign state) to an 8-category
    domain distribution compatible with KoshaDomainRouter.

    Args:
        embed_dim: Hidden state dimension (e.g., 4096 for Mistral-7B)
        state_dim: Sovereign state dimension (32). Set to 0 to use hidden only.
        num_domains: Number of domain categories (8)
        hidden_dim: MLP hidden dimension (default: embed_dim // 8)
    """

    def __init__(
        self,
        embed_dim: int,
        state_dim: int = 32,
        num_domains: int = NUM_DOMAINS,
        hidden_dim: Optional[int] = None,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.state_dim = state_dim
        self.num_domains = num_domains

        input_dim = embed_dim + state_dim
        hidden = hidden_dim or (embed_dim // 8)

        self.classifier = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, num_domains),
        )

        self._init_weights()

    def _init_weights(self):
        """Initialize for near-uniform initial domain distribution."""
        for module in self.classifier:
            if isinstance(module, nn.Linear):
                nn.init.xavier_normal_(module.weight, gain=0.3)
                nn.init.zeros_(module.bias)

    def forward(
        self,
        hidden: torch.Tensor,
        o_ctx: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Classify domain from context representations.

        Args:
            hidden: Hidden states. If 3D (B, T, D), mean-pooled over T.
                    If 2D (B, D), used directly.
            o_ctx: Sovereign state (B, state_dim) or (B, T, state_dim).
                   Optional — if None and state_dim > 0, zeros are used.

        Returns:
            Dict with:
                'domain': Softmax domain distribution (B, 8)
                'logits': Raw domain logits (B, 8)
                'entropy': Per-sample entropy (B,)
        """
        # Pool hidden if sequence-level
        if hidden.dim() == 3:
            h_pooled = hidden.mean(dim=1)  # (B, D)
        else:
            h_pooled = hidden  # (B, D)

        # Handle sovereign state
        if self.state_dim > 0:
            if o_ctx is not None:
                if o_ctx.dim() == 3:
                    s_pooled = o_ctx.mean(dim=1)  # (B, state_dim)
                else:
                    s_pooled = o_ctx  # (B, state_dim)
            else:
                s_pooled = torch.zeros(
                    h_pooled.shape[0], self.state_dim,
                    device=h_pooled.device, dtype=h_pooled.dtype,
                )
            combined = torch.cat([h_pooled, s_pooled], dim=-1)
        else:
            combined = h_pooled

        logits = self.classifier(combined)  # (B, 8)
        domain = F.softmax(logits, dim=-1)  # (B, 8)

        # Entropy for diagnostics
        entropy = -(domain * (domain + 1e-8).log()).sum(dim=-1)  # (B,)

        return {
            'domain': domain,
            'logits': logits,
            'entropy': entropy,
        }

    def compute_loss(
        self,
        logits: torch.Tensor,
        target: torch.Tensor,
        soft_target: bool = True,
    ) -> torch.Tensor:
        """
        Domain classification loss for weak-supervision bootstrap.

        Args:
            logits: Raw domain logits (B, 8)
            target: Target distribution (B, 8) if soft_target=True,
                    or class indices (B,) if soft_target=False.
            soft_target: Whether target is a soft distribution (from hardcoded bridge)
                        or hard class indices.

        Returns:
            Scalar loss
        """
        if soft_target:
            # KL divergence against soft target (hardcoded bridge distribution)
            log_probs = F.log_softmax(logits, dim=-1)
            loss = F.kl_div(log_probs, target, reduction='batchmean', log_target=False)
        else:
            # Standard cross-entropy against hard labels
            loss = F.cross_entropy(logits, target)

        return loss
