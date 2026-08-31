#!/usr/bin/env python3
"""
Auxiliary Loss Supervisor — Appendix F Stage 5
================================================

Orchestrates auxiliary loss supervision for conscious generation training.
Combines L_token (standard next-token prediction) with auxiliary losses
that keep CG dimensions meaningful:

    L_total = L_token + λ₁·L_csr + λ₂·L_vritti + λ₃·L_kosha + λ₄·L_bliss + λ₅·L_ont

Key components:
- AuxiliaryLossConfig: Lambda weights for each auxiliary loss
- TokenOntologyProjection: Projects token embeddings to 32D codes for L_ont
- BlissCoherenceProjection: Learned coherence projection for redefined L_bliss
- GradientSafetyMonitor: Monitors aux/backbone gradient ratio
- AuxiliaryLossSupervisor: Orchestrates all losses with safety monitoring

Training protocol (F.7.4):
  Stage A: All λ = 0 (backbone stabilization)
  Stage B: Enable λ_kosha only (ontology activation)
  Stage C: Enable λ_csr, λ_vritti, λ_ont (primitive activation)
  Stage D: Enable λ_bliss, all losses active (full integration)

Reference: Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.7

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 5 — Auxiliary Loss Supervision
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

import torch
import torch.nn as nn
import torch.nn.functional as F


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class AuxiliaryLossConfig:
    """Lambda weights and settings for auxiliary loss supervision.

    Attributes:
        lambda_csr: Weight for CSR alignment loss (phoneme resonance).
        lambda_vritti: Weight for Vritti classification loss (cognitive mode).
        lambda_kosha: Weight for Kosha routing regularization.
        lambda_bliss: Weight for Bliss coherence loss (redefined for
            representation conditioning).
        lambda_ont: Weight for ontological compatibility loss (contrastive).
        d_coherence: Dimension of the coherence projection for L_bliss.
        onto_dim: Ontological code dimension for L_ont.
        gradient_safety_low: Below this aux/backbone ratio, losses are
            ineffective — consider increasing lambdas.
        gradient_safety_high: Above this ratio, losses may dominate —
            consider reducing lambdas.
        cache_refresh_interval: Steps between refreshing O_tok cache.
    """
    lambda_csr: float = 0.01
    lambda_vritti: float = 0.02
    lambda_kosha: float = 0.005
    lambda_bliss: float = 0.02
    lambda_ont: float = 0.01
    d_coherence: int = 64
    onto_dim: int = 32
    gradient_safety_low: float = 0.01
    gradient_safety_high: float = 0.5
    cache_refresh_interval: int = 1000


# =============================================================================
# TOKEN ONTOLOGY PROJECTION (F.7.8)
# =============================================================================

class TokenOntologyProjection(nn.Module):
    """Projects token embeddings to ontological codes for L_ont training.

    Provides a training signal that makes the ontological projection
    meaningful. Does NOT participate in the inference path — exists
    purely for auxiliary supervision.

    Args:
        embed_dim: Token embedding dimension.
        onto_dim: Ontological code dimension (32).
    """

    def __init__(self, embed_dim: int, onto_dim: int = 32):
        super().__init__()
        self.projection = nn.Linear(embed_dim, onto_dim, bias=False)

    def forward(self, token_embeddings: torch.Tensor) -> torch.Tensor:
        """Project token embeddings to ontological codes.

        Args:
            token_embeddings: [V, D] or [B, K, D] for shortlist.

        Returns:
            o_w: [V, onto_dim] or [B, K, onto_dim] ontological codes.
        """
        return self.projection(token_embeddings)


# =============================================================================
# BLISS COHERENCE PROJECTION (F.7.2.1)
# =============================================================================

class BlissCoherenceProjection(nn.Module):
    """Learned coherence projection for redefined Bliss loss.

    Under representation conditioning (Stages 2/8), there is no per-token
    scoring step. Bliss coherence is redefined as a property of the
    conditioned representation:

        C(x, w) = cos(f_coh(x_conditioned), proj_tok(e_w))

    where f_coh is a small MLP projecting conditioned hidden state to
    a coherence embedding space.

    Args:
        hidden_dim: Conditioned hidden state dimension.
        embed_dim: Token embedding dimension.
        d_coherence: Coherence embedding dimension (64).
    """

    def __init__(self, hidden_dim: int, embed_dim: int, d_coherence: int = 64):
        super().__init__()
        self.d_coherence = d_coherence

        # Context-side: conditioned hidden → coherence space
        self.context_proj = nn.Sequential(
            nn.Linear(hidden_dim, d_coherence),
            nn.GELU(),
            nn.Linear(d_coherence, d_coherence),
        )

        # Token-side: embedding → coherence space
        self.token_proj = nn.Linear(embed_dim, d_coherence, bias=False)

    def forward(
        self,
        conditioned_hidden: torch.Tensor,
        token_embeddings: torch.Tensor,
    ) -> torch.Tensor:
        """Compute coherence scores between conditioned state and tokens.

        Args:
            conditioned_hidden: Conditioned hidden states (..., hidden_dim).
            token_embeddings: Token embeddings (..., embed_dim).

        Returns:
            coherence: Cosine similarity scores (...,).
        """
        ctx = F.normalize(self.context_proj(conditioned_hidden), dim=-1)
        tok = F.normalize(self.token_proj(token_embeddings), dim=-1)
        return (ctx * tok).sum(dim=-1)

    def compute_contrastive_loss(
        self,
        conditioned_hidden: torch.Tensor,
        correct_embeddings: torch.Tensor,
        negative_embeddings: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """Compute contrastive Bliss coherence loss.

        L_bliss = -log(σ(C(x, w_correct) - C(x, w_negative)))

        Args:
            conditioned_hidden: (..., hidden_dim).
            correct_embeddings: (..., embed_dim) — correct token embeddings.
            negative_embeddings: (..., embed_dim) — negative token embeddings.

        Returns:
            Dict with 'loss', 'pos_coherence', 'neg_coherence'.
        """
        pos = self.forward(conditioned_hidden, correct_embeddings)
        neg = self.forward(conditioned_hidden, negative_embeddings)
        loss = -torch.log(torch.sigmoid(pos - neg) + 1e-8).mean()
        return {
            "loss": loss,
            "pos_coherence": pos.mean().detach(),
            "neg_coherence": neg.mean().detach(),
        }


# =============================================================================
# GRADIENT SAFETY MONITOR (F.7.6)
# =============================================================================

class GradientSafetyMonitor:
    """Monitors auxiliary/backbone gradient ratio for training safety.

    Gradient ratio bounds (F.7.6):
        < 0.01:     Auxiliary losses ineffective — increase λ weights.
        0.01–0.1:   Healthy range — auxiliary signals train without dominating.
        0.1–0.5:    Caution — monitor perplexity closely.
        > 0.5:      Danger — reduce λ weights immediately.

    Usage::

        monitor = GradientSafetyMonitor()
        diagnostics = monitor.check(aux_grad_norm=0.05, backbone_grad_norm=1.0)
        # diagnostics = {"ratio": 0.05, "status": "healthy", ...}
    """

    def __init__(self, config: AuxiliaryLossConfig = None):
        self.config = config or AuxiliaryLossConfig()
        self.history: List[float] = []

    def check(
        self,
        aux_grad_norm: float,
        backbone_grad_norm: float,
    ) -> Dict[str, Any]:
        """Check auxiliary/backbone gradient ratio.

        Args:
            aux_grad_norm: L2 norm of gradients from auxiliary losses.
            backbone_grad_norm: L2 norm of gradients from L_token.

        Returns:
            Dict with 'ratio', 'status', 'action'.
        """
        if backbone_grad_norm < 1e-8:
            ratio = 0.0
        else:
            ratio = aux_grad_norm / backbone_grad_norm

        self.history.append(ratio)

        if ratio < self.config.gradient_safety_low:
            status = "ineffective"
            action = "increase lambda weights"
        elif ratio <= 0.1:
            status = "healthy"
            action = "none"
        elif ratio <= self.config.gradient_safety_high:
            status = "caution"
            action = "monitor perplexity closely"
        else:
            status = "danger"
            action = "reduce lambda weights immediately"

        return {
            "ratio": ratio,
            "status": status,
            "action": action,
            "aux_grad_norm": aux_grad_norm,
            "backbone_grad_norm": backbone_grad_norm,
        }

    @property
    def mean_ratio(self) -> float:
        """Mean gradient ratio over recorded history."""
        if not self.history:
            return 0.0
        return sum(self.history) / len(self.history)


# =============================================================================
# AUXILIARY LOSS SUPERVISOR (F.7.3)
# =============================================================================

class AuxiliaryLossSupervisor(nn.Module):
    """Orchestrates auxiliary loss computation for conscious generation training.

    Combines L_token with weighted auxiliary losses:
        L_total = L_token + λ₁·L_csr + λ₂·L_vritti + λ₃·L_kosha + λ₄·L_bliss + λ₅·L_ont

    Integrates with existing loss modules:
    - PrimitiveAuxiliaryLosses for L_csr, L_vritti
    - KoshaRoutingLoss for L_kosha
    - BlissCoherenceProjection for redefined L_bliss
    - OntologicalStructureLoss for L_ont

    Args:
        config: AuxiliaryLossConfig with lambda weights.
        hidden_dim: Conditioned hidden state dimension.
        embed_dim: Token embedding dimension.
    """

    def __init__(
        self,
        config: AuxiliaryLossConfig,
        hidden_dim: int,
        embed_dim: int,
    ):
        super().__init__()
        self.config = config

        # Token ontology projection for L_ont
        self.token_onto_proj = TokenOntologyProjection(
            embed_dim=embed_dim,
            onto_dim=config.onto_dim,
        )

        # Bliss coherence projection for redefined L_bliss
        self.bliss_proj = BlissCoherenceProjection(
            hidden_dim=hidden_dim,
            embed_dim=embed_dim,
            d_coherence=config.d_coherence,
        )

        # Bilinear form for ontological compatibility
        self.M_ont = nn.Parameter(
            torch.eye(config.onto_dim) * 0.1
            + 0.01 * torch.randn(config.onto_dim, config.onto_dim)
        )

        # Gradient safety monitor
        self.gradient_monitor = GradientSafetyMonitor(config)

        # O_tok cache
        self._o_tok_cache: Optional[torch.Tensor] = None
        self._cache_step = -config.cache_refresh_interval  # Force first refresh

    def refresh_token_cache(
        self,
        embedding_weight: torch.Tensor,
        current_step: int,
    ) -> None:
        """Refresh O_tok cache if interval has elapsed.

        Args:
            embedding_weight: [V, embed_dim] token embedding matrix.
            current_step: Current training step.
        """
        if current_step - self._cache_step >= self.config.cache_refresh_interval:
            with torch.no_grad():
                self._o_tok_cache = self.token_onto_proj(embedding_weight).detach()
            self._cache_step = current_step

    def compute_ont_loss(
        self,
        o_context: torch.Tensor,
        correct_ids: torch.Tensor,
        negative_ids: torch.Tensor,
        embedding_weight: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """Compute ontological compatibility loss L_ont.

        L_ont = -log(σ(s_correct - s_negative))
        where s = o_t^T M_ont o_w

        Args:
            o_context: Context ontological state (..., onto_dim).
            correct_ids: Ground truth token ids (...,).
            negative_ids: Negative sample token ids (...,).
            embedding_weight: [V, embed_dim] for projection.

        Returns:
            Dict with 'loss', 's_correct', 's_negative'.
        """
        # Project correct and negative token embeddings
        o_correct = self.token_onto_proj(embedding_weight[correct_ids])
        o_negative = self.token_onto_proj(embedding_weight[negative_ids])

        # Bilinear compatibility scores
        # o_context: (..., D), M_ont: (D, D), o_w: (..., D)
        s_correct = torch.einsum('...i,ij,...j->...', o_context, self.M_ont, o_correct)
        s_negative = torch.einsum('...i,ij,...j->...', o_context, self.M_ont, o_negative)

        loss = -torch.log(torch.sigmoid(s_correct - s_negative) + 1e-8).mean()

        return {
            "loss": loss,
            "s_correct": s_correct.mean().detach(),
            "s_negative": s_negative.mean().detach(),
        }

    def forward(
        self,
        loss_token: torch.Tensor,
        loss_csr: Optional[torch.Tensor] = None,
        loss_vritti: Optional[torch.Tensor] = None,
        loss_kosha: Optional[torch.Tensor] = None,
        loss_bliss: Optional[torch.Tensor] = None,
        loss_ont: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """Compute total loss with weighted auxiliary contributions.

        Missing losses are treated as zero (graceful degradation for
        staged curriculum activation).

        Args:
            loss_token: Standard next-token prediction loss.
            loss_csr: CSR alignment auxiliary loss.
            loss_vritti: Vritti classification auxiliary loss.
            loss_kosha: Kosha routing regularization loss.
            loss_bliss: Bliss coherence auxiliary loss.
            loss_ont: Ontological compatibility auxiliary loss.

        Returns:
            Dict with 'loss_total' and individual weighted components.
        """
        zero = torch.tensor(0.0, device=loss_token.device, dtype=loss_token.dtype)

        l_csr = loss_csr if loss_csr is not None else zero
        l_vritti = loss_vritti if loss_vritti is not None else zero
        l_kosha = loss_kosha if loss_kosha is not None else zero
        l_bliss = loss_bliss if loss_bliss is not None else zero
        l_ont = loss_ont if loss_ont is not None else zero

        loss_total = (
            loss_token
            + self.config.lambda_csr * l_csr
            + self.config.lambda_vritti * l_vritti
            + self.config.lambda_kosha * l_kosha
            + self.config.lambda_bliss * l_bliss
            + self.config.lambda_ont * l_ont
        )

        return {
            "loss_total": loss_total,
            "loss_token": loss_token.detach(),
            "loss_csr": l_csr.detach(),
            "loss_vritti": l_vritti.detach(),
            "loss_kosha": l_kosha.detach(),
            "loss_bliss": l_bliss.detach(),
            "loss_ont": l_ont.detach(),
            "weighted_csr": (self.config.lambda_csr * l_csr).detach(),
            "weighted_vritti": (self.config.lambda_vritti * l_vritti).detach(),
            "weighted_kosha": (self.config.lambda_kosha * l_kosha).detach(),
            "weighted_bliss": (self.config.lambda_bliss * l_bliss).detach(),
            "weighted_ont": (self.config.lambda_ont * l_ont).detach(),
        }
