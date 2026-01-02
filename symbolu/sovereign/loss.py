"""
Sovereign-1 Loss Function: Decomposed State Friction
=====================================================

Implements the hardened loss function that prevents "Signal Washing" by
decomposing the 128D state vector into weighted components.

Loss = CrossEntropy + α * (w_g*L_guna + w_s*L_s + w_r*L_r + w_c*L_c) + β*L_transition

Key insight: Without decomposition, high-frequency C-Signal (phonetics) would
dominate gradients, starving the semantically critical R-Signal of learning.

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 2.4.4
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class SovereignLossConfig:
    """Configuration for Sovereign-1 loss function."""

    # Signal weights (prioritize meaning over sound)
    weight_guna: float = 1.0      # Dynamics baseline
    weight_s: float = 2.0         # Referent accuracy
    weight_r: float = 5.0         # Ontological accuracy (CRITICAL)
    weight_c: float = 0.5         # Phonetic accuracy (lowest)

    # Alpha decay schedule
    alpha_initial: float = 1.0
    alpha_final: float = 0.2
    decay_epochs: int = 3

    # Transition penalty
    transition_weight: float = 0.5

    # State layout
    guna_dim: int = 16
    s_dim: int = 32
    r_dim: int = 48
    c_dim: int = 32


class SovereignLoss(nn.Module):
    """
    Decomposed State Friction Loss for Sovereign-1 Architecture.

    This loss function prevents "Signal Washing" by:
    1. Decomposing state into 4 signals (Guna, S, R, C)
    2. Applying different weights to each signal
    3. Prioritizing R-Signal (meaning) over C-Signal (sound)
    4. Adding transition penalty for illegal Bhava jumps

    State Layout: Guna[0:16] | S-Signal[16:48] | R-Signal[48:96] | C-Signal[96:128]
    """

    # Default weights per Sovereign-1 spec
    DEFAULT_WEIGHTS = {
        "guna": 1.0,   # Dynamics (baseline)
        "s": 2.0,      # Referent accuracy
        "r": 5.0,      # Ontological accuracy (CRITICAL)
        "c": 0.5       # Phonetic accuracy
    }

    def __init__(
        self,
        config: Optional[SovereignLossConfig] = None,
        weights: Optional[Dict[str, float]] = None,
    ):
        super().__init__()
        self.config = config or SovereignLossConfig()
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.ce_loss = nn.CrossEntropyLoss(ignore_index=-100)

    def get_alpha(self, epoch: int) -> float:
        """Compute decayed alpha for state friction."""
        if epoch >= self.config.decay_epochs:
            return self.config.alpha_final
        progress = epoch / self.config.decay_epochs
        return self.config.alpha_initial - progress * (
            self.config.alpha_initial - self.config.alpha_final
        )

    def _slice_state(
        self,
        state_tensor: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Slice 128D state vector into constituent signals.

        Layout: Guna[16] | S[32] | R[48] | C[32] = 128 total
        """
        g_end = self.config.guna_dim
        s_end = g_end + self.config.s_dim
        r_end = s_end + self.config.r_dim
        c_end = r_end + self.config.c_dim

        guna = state_tensor[..., :g_end]
        s_signal = state_tensor[..., g_end:s_end]
        r_signal = state_tensor[..., s_end:r_end]
        c_signal = state_tensor[..., r_end:c_end]

        return guna, s_signal, r_signal, c_signal

    def forward(
        self,
        logits: torch.Tensor,              # [B, N, V]
        targets: torch.Tensor,             # [B, N]
        predicted_state: torch.Tensor,     # [B, N, 128] or [B, 128]
        target_state: torch.Tensor,        # [B, N, 128] or [B, 128]
        prev_state: Optional[torch.Tensor] = None,
        epoch: int = 0,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Compute decomposed Sovereign loss.

        Returns:
            total_loss: Scalar tensor
            metrics: Dict with detailed component losses for monitoring
        """
        # 1. Standard Cross-Entropy (Token Prediction)
        if logits.dim() == 3:
            B, N, V = logits.shape
            ce = self.ce_loss(logits.view(-1, V), targets.view(-1))
        else:
            ce = self.ce_loss(logits, targets)

        # Handle 2D state tensors (batch-level)
        if predicted_state.dim() == 2:
            predicted_state = predicted_state.unsqueeze(1)
            target_state = target_state.unsqueeze(1)
            if prev_state is not None:
                prev_state = prev_state.unsqueeze(1)

        # 2. Decomposed State Friction
        pred_g, pred_s, pred_r, pred_c = self._slice_state(predicted_state)
        targ_g, targ_s, targ_r, targ_c = self._slice_state(target_state)

        # Calculate individual MSE losses
        l_guna = F.mse_loss(pred_g, targ_g)
        l_s = F.mse_loss(pred_s, targ_s)
        l_r = F.mse_loss(pred_r, targ_r)  # THE CRITICAL SEMANTIC LOSS
        l_c = F.mse_loss(pred_c, targ_c)

        # Weighted sum
        state_friction = (
            self.weights["guna"] * l_guna +
            self.weights["s"] * l_s +
            self.weights["r"] * l_r +
            self.weights["c"] * l_c
        )

        # 3. Bhava Transition Penalty
        l_transition = torch.tensor(0.0, device=logits.device)
        if prev_state is not None:
            _, _, prev_r, _ = self._slice_state(prev_state)
            transition_probs = self._compute_transition_prob(prev_r, pred_r)
            l_transition = (1.0 - transition_probs).mean()

        # 4. Total Loss with Alpha Decay
        alpha = self.get_alpha(epoch)
        total = ce + alpha * state_friction + self.config.transition_weight * l_transition

        # 5. Diagnostic Metrics
        ontology_phoneme_ratio = l_r.item() / (l_c.item() + 1e-9)
        meaning_fraction = l_r.item() / (state_friction.item() + 1e-9)

        return total, {
            "loss_total": total.item(),
            "loss_ce": ce.item(),
            "loss_friction": state_friction.item(),
            "loss_transition": l_transition.item(),
            "alpha": alpha,
            "friction_components": {
                "guna": l_guna.item(),
                "referent": l_s.item(),
                "ontology": l_r.item(),
                "phoneme": l_c.item(),
            },
            # Key diagnostic ratios
            "ontology_to_phoneme_ratio": ontology_phoneme_ratio,
            "meaning_fraction": meaning_fraction,
            # Health indicators
            "signal_washing": ontology_phoneme_ratio < 1.0,  # BAD if True
            "semantic_healthy": ontology_phoneme_ratio > 3.0,  # GOOD if True
        }

    def _compute_transition_prob(
        self,
        prev_r: torch.Tensor,
        curr_r: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute transition probability based on R-Signal changes.
        Higher = smoother transitions, Lower = more abrupt jumps.
        """
        return F.cosine_similarity(prev_r, curr_r, dim=-1).clamp(0, 1)


class LegacyLossAdapter:
    """
    Adapter to use SovereignLoss with existing ontological model outputs.

    Maps the current 156D output (12D onto + 144D bhava) to Sovereign state.
    """

    def __init__(self, sovereign_loss: SovereignLoss):
        self.loss = sovereign_loss

    def compute_loss(
        self,
        outputs: Dict[str, torch.Tensor],
        targets: torch.Tensor,
        epoch: int = 0,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Compute loss from existing ontological model outputs.

        Maps:
        - ontological_probs [12] -> Part of R-Signal
        - bhava_vector [144] -> Decomposed into R/S signals
        """
        logits = outputs['logits']
        B = logits.shape[0]
        device = logits.device

        # Build pseudo-state from existing outputs
        onto_probs = outputs.get('ontological_probs', torch.zeros(B, 12, device=device))
        bhava_vec = outputs.get('bhava_vector', torch.zeros(B, 144, device=device))
        coherence = outputs.get('global_coherence', torch.ones(B, device=device))

        # Construct 128D state
        predicted_state = self._build_state(onto_probs, bhava_vec, coherence, device)

        # Target state is zero (ground truth unknown in self-supervised)
        target_state = torch.zeros_like(predicted_state)

        return self.loss(logits, targets, predicted_state, target_state, epoch=epoch)

    def _build_state(
        self,
        onto_probs: torch.Tensor,  # [B, 12]
        bhava_vec: torch.Tensor,   # [B, 144]
        coherence: torch.Tensor,   # [B]
        device: torch.device,
    ) -> torch.Tensor:
        """Build 128D state from legacy outputs."""
        B = onto_probs.shape[0]

        # Guna [16]: Derived from coherence
        guna = coherence.unsqueeze(-1).expand(-1, 16)

        # S-Signal [32]: First 32 dims of bhava
        s_signal = bhava_vec[:, :32]

        # R-Signal [48]: Ontology (12) + bhava subset (36)
        r_onto = F.pad(onto_probs, (0, 36))  # Pad 12 -> 48
        r_signal = r_onto + bhava_vec[:, 32:80] * 0.1  # Blend

        # C-Signal [32]: Remaining bhava
        c_signal = bhava_vec[:, 80:112]
        c_signal = F.pad(c_signal, (0, max(0, 32 - c_signal.shape[-1])))

        return torch.cat([guna, s_signal, r_signal, c_signal], dim=-1)
