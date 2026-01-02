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
