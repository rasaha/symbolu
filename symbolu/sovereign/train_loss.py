"""
Sovereign Training Loss - Multi-Objective Loss for LLM Training.

This module extends the core SovereignLoss with training-specific
loss functions for the Wikitext-103 training pipeline.

Integrates with existing Symbolu components:
- symbolu.resonance for phoneme processing
- symbolu.guna_modulation for entropy state
- symbolu.formulas for vritti mapping
- symbolu.sovereign.loss for core loss functions

The key insight is that the model must learn not just WHAT to say,
but also WHY (intent) and HOW (structure).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class TrainingLossConfig:
    """Configuration for training loss."""

    # Loss weights
    lambda_token: float = 1.0  # Main prediction loss
    lambda_r: float = 0.1  # Intent consistency
    lambda_s: float = 0.1  # Referent accuracy
    lambda_c: float = 0.05  # Phonetic structure

    # Label smoothing
    label_smoothing: float = 0.1

    # Ignore index for padding
    ignore_index: int = -100


@dataclass(frozen=True)
class TrainingLossOutput:
    """Output container for training loss computation."""

    total: torch.Tensor
    token: torch.Tensor
    r_signal: torch.Tensor
    s_signal: torch.Tensor
    c_signal: torch.Tensor

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for logging."""
        return {
            "loss/total": self.total.item(),
            "loss/token": self.token.item(),
            "loss/r_signal": self.r_signal.item(),
            "loss/s_signal": self.s_signal.item(),
            "loss/c_signal": self.c_signal.item(),
        }


class MultiObjectiveLoss(nn.Module):
    """
    Multi-Objective Loss for Sovereign Model Training.

    Loss formula:
    ```
    L_total = λ_token · L_token + λ_R · L_R + λ_S · L_S + λ_C · L_C
    ```

    Where:
    - L_token: CrossEntropy(logits, targets) - next word prediction
    - L_R: CrossEntropy(r_pred, r_true) - ontological intent
    - L_S: CrossEntropy(s_pred, s_true) - referent category
    - L_C: MSE(c_pred, c_true) - phonetic structure
    """

    def __init__(self, config: Optional[TrainingLossConfig] = None):
        super().__init__()

        if config is None:
            config = TrainingLossConfig()

        self.config = config

        # Token prediction loss (with label smoothing)
        self.token_loss = nn.CrossEntropyLoss(
            ignore_index=config.ignore_index,
            label_smoothing=config.label_smoothing,
        )

        # R-Signal loss (intent consistency)
        self.r_loss = nn.CrossEntropyLoss(
            ignore_index=config.ignore_index,
            label_smoothing=config.label_smoothing * 0.5,
        )

        # S-Signal loss (referent accuracy)
        self.s_loss = nn.CrossEntropyLoss(
            ignore_index=config.ignore_index,
            label_smoothing=config.label_smoothing * 0.5,
        )

        # C-Signal loss (phonetic structure)
        self.c_loss = nn.MSELoss(reduction="mean")

    def forward(
        self,
        token_logits: torch.Tensor,
        r_logits: torch.Tensor,
        s_logits: torch.Tensor,
        c_pred: torch.Tensor,
        target_tokens: torch.Tensor,
        target_r: torch.Tensor,
        target_s: torch.Tensor,
        target_c: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> TrainingLossOutput:
        """Compute multi-objective loss."""
        # Flatten for loss computation
        token_logits_flat = token_logits.view(-1, token_logits.size(-1))
        r_logits_flat = r_logits.view(-1, r_logits.size(-1))
        s_logits_flat = s_logits.view(-1, s_logits.size(-1))

        target_tokens_flat = target_tokens.view(-1)
        target_r_flat = target_r.view(-1)
        target_s_flat = target_s.view(-1)

        # Compute individual losses
        l_token = self.token_loss(token_logits_flat, target_tokens_flat)
        l_r = self.r_loss(r_logits_flat, target_r_flat)
        l_s = self.s_loss(s_logits_flat, target_s_flat)

        # C-Signal loss
        if attention_mask is not None:
            mask = attention_mask.unsqueeze(-1).expand_as(c_pred)
            c_pred_masked = c_pred * mask
            target_c_masked = target_c * mask
            l_c = self.c_loss(c_pred_masked, target_c_masked)
        else:
            l_c = self.c_loss(c_pred, target_c)

        # Weighted combination
        l_total = (
            self.config.lambda_token * l_token
            + self.config.lambda_r * l_r
            + self.config.lambda_s * l_s
            + self.config.lambda_c * l_c
        )

        return TrainingLossOutput(
            total=l_total,
            token=l_token,
            r_signal=l_r,
            s_signal=l_s,
            c_signal=l_c,
        )


class RSignalCoherenceLoss(nn.Module):
    """
    Additional loss for R-Signal coherence across sequence.

    Penalizes rapid changes in intent (R-Signal) which indicate
    incoherent generation.
    """

    def __init__(self, max_jump: int = 2, penalty_weight: float = 0.1):
        super().__init__()
        self.max_jump = max_jump
        self.penalty_weight = penalty_weight

    def forward(
        self,
        r_logits: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Compute coherence penalty."""
        r_pred = r_logits.argmax(dim=-1)
        r_diff = torch.abs(r_pred[:, 1:] - r_pred[:, :-1])
        violations = F.relu(r_diff.float() - self.max_jump)

        if attention_mask is not None:
            mask = attention_mask[:, 1:] * attention_mask[:, :-1]
            violations = violations * mask

        return violations.mean() * self.penalty_weight


class IntentDriftMonitor:
    """Monitor for detecting intent drift during generation."""

    def __init__(self, window_size: int = 10, drift_threshold: float = 0.5):
        self.window_size = window_size
        self.drift_threshold = drift_threshold
        self.r_history: list = []
        self.baseline_r: Optional[int] = None

    def reset(self):
        self.r_history = []
        self.baseline_r = None

    def update(self, r_signal: int) -> Dict[str, float]:
        self.r_history.append(r_signal)

        if len(self.r_history) > self.window_size:
            self.r_history = self.r_history[-self.window_size:]

        if self.baseline_r is None and len(self.r_history) >= 3:
            from collections import Counter
            counts = Counter(self.r_history[:3])
            self.baseline_r = counts.most_common(1)[0][0]

        if self.baseline_r is not None:
            drift = abs(r_signal - self.baseline_r) / 12.0
            is_drifting = drift > self.drift_threshold
        else:
            drift = 0.0
            is_drifting = False

        return {
            "r_signal": r_signal,
            "baseline_r": self.baseline_r,
            "drift": drift,
            "is_drifting": is_drifting,
        }


@dataclass
class VrittiLossConfig:
    """Configuration for Vritti-aware loss."""

    # Standard loss weights
    lambda_token: float = 1.0
    lambda_vritti: float = 0.2  # Vritti prediction weight

    # Transition penalty weight
    transition_weight: float = 0.5

    # Label smoothing
    label_smoothing: float = 0.1

    # Ignore index for padding
    ignore_index: int = -100


@dataclass(frozen=True)
class VrittiLossOutput:
    """Output container for Vritti loss computation."""

    total: torch.Tensor
    token: torch.Tensor
    vritti: torch.Tensor
    transition_penalty: torch.Tensor
    stiffness_factor: torch.Tensor  # Mean Kp applied

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for logging."""
        return {
            "loss/total": self.total.item(),
            "loss/token": self.token.item(),
            "loss/vritti": self.vritti.item(),
            "loss/transition": self.transition_penalty.item(),
            "stiffness": self.stiffness_factor.item(),
        }


class VrittiLoss(nn.Module):
    """
    Vritti-Driven Loss Function.

    Computes standard cross-entropy loss for token prediction but applies a
    **Stiffness Multiplier** based on the Vritti state. Incorporates the
    **Vritti Transition Penalty** to prevent illegal "Ontological Teleportation".

    The key insight:
    - Factual errors (Pramāṇa) are punished 4.5x harder than filler errors (Nidrā)
    - Transitions between incompatible states are penalized
    - The PID gains define the "physics" of gradient scaling
    """

    def __init__(self, config: Optional[VrittiLossConfig] = None):
        super().__init__()

        if config is None:
            config = VrittiLossConfig()
        self.config = config

        # Token prediction loss (per-element, not reduced)
        self.ce_loss = nn.CrossEntropyLoss(
            reduction='none',
            ignore_index=config.ignore_index,
        )

        # Vritti prediction loss
        self.vritti_ce = nn.CrossEntropyLoss(
            reduction='none',
            label_smoothing=config.label_smoothing,
        )

        # PID Physics Table: [Pramāṇa, Viparyaya, Vikalpa, Smṛti, Nidrā]
        self.register_buffer('kp_table', torch.tensor([0.9, 0.7, 0.3, 0.5, 0.2]))
        self.register_buffer('ki_table', torch.tensor([0.01, 0.2, 0.05, 0.4, 0.7]))
        self.register_buffer('kd_table', torch.tensor([0.01, 0.2, 0.6, 0.1, 0.01]))

        # Transition Penalty Matrix: [From, To]
        # Higher value = more penalty for that transition
        self.register_buffer('penalty_matrix', torch.tensor([
            #  Pra   Vip   Vik   Smr   Nid
            [0.1,  0.8,  0.9,  0.2,  0.5],  # From Pramāṇa
            [0.5,  0.1,  0.5,  0.5,  0.5],  # From Viparyaya
            [0.7,  0.5,  0.1,  0.3,  0.2],  # From Vikalpa
            [0.2,  0.4,  0.4,  0.1,  0.3],  # From Smṛti
            [0.9,  0.8,  0.5,  0.2,  0.1],  # From Nidrā
        ]))

    def forward(
        self,
        token_logits: torch.Tensor,
        vritti_logits: torch.Tensor,
        target_tokens: torch.Tensor,
        target_vritti: torch.Tensor,
        prev_vritti: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> VrittiLossOutput:
        """
        Compute Vritti-aware loss.

        Args:
            token_logits: [B, N, Vocab] - Language model outputs
            vritti_logits: [B, N, 5] - Vritti head outputs
            target_tokens: [B, N] - Ground truth tokens
            target_vritti: [B, N] - Ground truth Vritti states (0-4)
            prev_vritti: [B, N] - Previous step Vritti for transition check
            attention_mask: [B, N] - Optional attention mask

        Returns:
            VrittiLossOutput with all loss components
        """
        B, N, V = token_logits.shape

        # 1. Token Prediction Loss (The "Body")
        token_loss = self.ce_loss(
            token_logits.view(-1, V),
            target_tokens.view(-1)
        ).view(B, N)

        # 2. Vritti Prediction Loss (The "Intent")
        vritti_loss = self.vritti_ce(
            vritti_logits.view(-1, 5),
            target_vritti.view(-1)
        ).view(B, N)

        # 3. Extract PID Stiffness (Kp) for the target mode
        # Clamp to valid range to avoid index errors
        target_vritti_clamped = target_vritti.clamp(0, 4)
        kp_stiffness = self.kp_table[target_vritti_clamped]  # [B, N]

        # 4. Apply Stiffness to Token Gradients
        # Factual (Pramāṇa) errors punished 4.5x harder than filler (Nidrā)
        weighted_token_loss = token_loss * kp_stiffness

        # 5. Compute Transition Penalty
        if prev_vritti is not None:
            prev_clamped = prev_vritti.clamp(0, 4)
            curr_clamped = target_vritti_clamped
            transition_penalty = self.penalty_matrix[prev_clamped, curr_clamped]
            transition_loss = transition_penalty.mean()
        else:
            transition_loss = torch.tensor(0.0, device=token_logits.device)

        # 6. Apply attention mask if provided
        if attention_mask is not None:
            mask = attention_mask.float()
            weighted_token_loss = weighted_token_loss * mask
            vritti_loss = vritti_loss * mask
            # Normalize by mask sum
            mask_sum = mask.sum().clamp(min=1.0)
            weighted_token_loss = weighted_token_loss.sum() / mask_sum
            vritti_loss = vritti_loss.sum() / mask_sum
        else:
            weighted_token_loss = weighted_token_loss.mean()
            vritti_loss = vritti_loss.mean()

        # 7. Total Sovereign Loss
        total_loss = (
            self.config.lambda_token * weighted_token_loss
            + self.config.lambda_vritti * vritti_loss
            + self.config.transition_weight * transition_loss
        )

        return VrittiLossOutput(
            total=total_loss,
            token=weighted_token_loss,
            vritti=vritti_loss,
            transition_penalty=transition_loss,
            stiffness_factor=kp_stiffness.mean(),
        )

    def get_mode_gains(self, vritti_ids: torch.Tensor) -> torch.Tensor:
        """
        Get [Kp, Ki, Kd] gains for given Vritti states.

        Args:
            vritti_ids: [B, N] tensor of Vritti IDs (0-4)

        Returns:
            [B, N, 3] tensor of PID gains
        """
        vritti_ids = vritti_ids.clamp(0, 4)
        kp = self.kp_table[vritti_ids]
        ki = self.ki_table[vritti_ids]
        kd = self.kd_table[vritti_ids]
        return torch.stack([kp, ki, kd], dim=-1)
