"""
Sovereign Loss Functions and Training Utilities
================================================

Version: 9.8.0
Reference: docs/architecture/SOVEREIGN_REASONING_KERNEL_DESIGN.md Section 28

Implements the multi-objective loss functions for SRK training:
- B1: Consistency Lagrangian (forward-backward divergence)
- U2: Phase Coherence (attention head alignment)
- S8: Stability Constraint (entropy decrease requirement)

Also includes:
- SovereignAnnealer: Lambda warmup for training stability
- TeleologicalOptimizer: Gradient clipping based on consistency
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


# =============================================================================
# LOSS CONFIGURATION
# =============================================================================

@dataclass
class SovereignLossConfig:
    """Configuration for Sovereign Loss computation."""

    # B1: Consistency Lagrangian
    lambda_f: float = 1.0  # Forward score weight
    lambda_b: float = 1.0  # Backward score weight
    lambda_c: float = 0.5  # Divergence penalty weight

    # U2: Phase Coherence
    lambda_coherence: float = 0.2

    # S8: Stability Constraint
    lambda_entropy: float = 0.1
    entropy_threshold: float = 0.7  # Target entropy level

    # Task loss
    lambda_task: float = 1.0

    # Nidra (dormancy) penalty
    enable_nidra_penalty: bool = True
    nidra_penalty_weight: float = 0.05


# =============================================================================
# BACKWARD SCORE CALCULATOR
# =============================================================================

class BackwardScoreCalculator(nn.Module):
    """
    Computes the Backward Score (s_b) for the Consistency Lagrangian.

    During Training:
        s_b = similarity(hidden_state, karma_state)
        Measures: "Is the current hidden state consistent with the
                  Reasoning Chain (Karma) I initiated?"

    During Inference:
        s_b can be overridden by UOM (User-Ontological Mirror) to
        target a Sattvic Anchor for intervention.
    """

    def __init__(self, hidden_dim: int = 768, state_dim: int = 32):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.state_dim = state_dim

        # Project hidden to state space for comparison
        self.hidden_projector = nn.Linear(hidden_dim, state_dim)

    def forward(
        self,
        hidden_states: torch.Tensor,
        karma_state: torch.Tensor,
        target_state: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute backward score.

        Args:
            hidden_states: [B, N, D] hidden states
            karma_state: [B, 32] karma from previous step
            target_state: [B, 32] optional override target (inference)

        Returns:
            s_b: [B] backward score in [0, 1]
        """
        # Pool hidden states
        pooled = hidden_states.mean(dim=1)  # [B, D]

        # Project to state space
        projected = self.hidden_projector(pooled)  # [B, 32]

        # Use target_state if provided (inference), else karma (training)
        target = target_state if target_state is not None else karma_state

        # Cosine similarity as backward score
        s_b = F.cosine_similarity(projected, target, dim=-1)

        # Map from [-1, 1] to [0, 1]
        s_b = (s_b + 1) / 2

        return s_b


# =============================================================================
# FORWARD SCORE CALCULATOR
# =============================================================================

class ForwardScoreCalculator(nn.Module):
    """
    Computes the Forward Score (s_f) for linguistic coherence.

    s_f measures how well the model's output aligns with expected
    linguistic patterns (grammar, fluency, coherence).
    """

    def __init__(self):
        super().__init__()

    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute forward score from prediction confidence.

        Args:
            logits: [B, N, V] model logits
            targets: [B, N] target token ids
            mask: [B, N] optional attention mask

        Returns:
            s_f: [B] forward score in [0, 1]
        """
        B, N, V = logits.shape

        # Get prediction probabilities
        probs = F.softmax(logits, dim=-1)  # [B, N, V]

        # Get probability of correct tokens
        target_probs = torch.gather(
            probs, dim=-1, index=targets.unsqueeze(-1)
        ).squeeze(-1)  # [B, N]

        # Apply mask if provided
        if mask is not None:
            target_probs = target_probs * mask
            valid_count = mask.sum(dim=-1).clamp(min=1)
            s_f = target_probs.sum(dim=-1) / valid_count
        else:
            s_f = target_probs.mean(dim=-1)

        return s_f


# =============================================================================
# PHASE COHERENCE CALCULATOR
# =============================================================================

class PhaseCoherenceCalculator(nn.Module):
    """
    Computes Phase Coherence (U2) from attention head phases.

    Measures alignment of attention head rotational phases.
    High coherence = heads are working in harmony.
    Low coherence = heads are in conflict.
    """

    def __init__(self, num_heads: int = 12):
        super().__init__()
        self.num_heads = num_heads

    def forward(
        self,
        attention_phases: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute phase coherence.

        Args:
            attention_phases: [B, H, N] phases from PhaseExtractionHook

        Returns:
            coherence: [B] phase coherence in [0, 1]
        """
        if attention_phases is None:
            # Return neutral coherence if phases not available
            return torch.tensor(0.5)

        B, H, N = attention_phases.shape

        # Compute circular variance of phases across heads
        # Low variance = high coherence
        sin_sum = torch.sin(attention_phases).mean(dim=1)  # [B, N]
        cos_sum = torch.cos(attention_phases).mean(dim=1)  # [B, N]

        # Resultant length (R) measures concentration
        R = torch.sqrt(sin_sum**2 + cos_sum**2)  # [B, N]

        # Average over sequence
        coherence = R.mean(dim=-1)  # [B]

        return coherence


# =============================================================================
# SOVEREIGN LOSS MODULE
# =============================================================================

class SovereignLoss(nn.Module):
    """
    Multi-objective loss for Sovereign Reasoning Kernel training.

    L_total = L_task
            + λ_consistency × L_lagrangian (B1)
            + λ_entropy × L_stability (S8)
            + λ_coherence × L_phase (U2)

    Keeps loss computation separate from SRK state management.
    """

    def __init__(self, config: Optional[SovereignLossConfig] = None):
        super().__init__()
        self.config = config or SovereignLossConfig()

        self.backward_calculator = BackwardScoreCalculator()
        self.forward_calculator = ForwardScoreCalculator()
        self.coherence_calculator = PhaseCoherenceCalculator()

    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
        hidden_states: torch.Tensor,
        karma_state: torch.Tensor,
        srk_diagnostics: Dict[str, float],
        attention_phases: Optional[torch.Tensor] = None,
        mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute total Sovereign loss.

        Args:
            logits: [B, N, V] model output logits
            targets: [B, N] target token ids
            hidden_states: [B, N, D] final hidden states
            karma_state: [B, 32] karma from SRK
            srk_diagnostics: Dict from SRK forward pass
            attention_phases: [B, H, N] optional phases from hook
            mask: [B, N] optional attention mask

        Returns:
            total_loss: Scalar loss tensor
            metrics: Dict of loss components for logging
        """
        metrics = {}

        # 1. Standard task loss (Cross-Entropy)
        B, N, V = logits.shape
        L_task = F.cross_entropy(
            logits.view(-1, V),
            targets.view(-1),
            ignore_index=-100,
        )
        metrics['L_task'] = L_task.item()

        # 2. B1: Consistency Lagrangian
        s_f = self.forward_calculator(logits, targets, mask)
        s_b = self.backward_calculator(hidden_states, karma_state)

        # Lagrangian: penalize divergence between forward and backward
        L_lagrangian = ((s_f - s_b) ** 2).mean()
        metrics['s_f'] = s_f.mean().item()
        metrics['s_b'] = s_b.mean().item()
        metrics['L_lagrangian'] = L_lagrangian.item()

        # 3. S8: Stability constraint (entropy should decrease)
        entropy_delta = srk_diagnostics.get('entropy_delta', 0.0)
        L_stability = F.relu(torch.tensor(entropy_delta, device=logits.device))
        metrics['L_stability'] = L_stability.item()

        # 4. U2: Phase coherence
        coherence = self.coherence_calculator(attention_phases)
        L_phase = 1.0 - coherence.mean() if isinstance(coherence, torch.Tensor) else 0.5
        if isinstance(L_phase, torch.Tensor):
            metrics['L_phase'] = L_phase.item()
            metrics['phase_coherence'] = coherence.mean().item()
        else:
            metrics['L_phase'] = L_phase
            metrics['phase_coherence'] = 0.5

        # 5. Nidra penalty (prevent dormancy)
        L_nidra = torch.tensor(0.0, device=logits.device)
        if self.config.enable_nidra_penalty:
            void_activation = srk_diagnostics.get('vritti_status', {}).get('VOID', 0.0)
            L_nidra = torch.tensor(void_activation, device=logits.device)
            metrics['L_nidra'] = L_nidra.item()

        # Combine losses
        L_total = (
            self.config.lambda_task * L_task +
            self.config.lambda_c * L_lagrangian +
            self.config.lambda_entropy * L_stability +
            self.config.lambda_coherence * (L_phase if isinstance(L_phase, torch.Tensor) else torch.tensor(L_phase, device=logits.device)) +
            self.config.nidra_penalty_weight * L_nidra
        )

        metrics['L_total'] = L_total.item()

        return L_total, metrics


# =============================================================================
# SOVEREIGN ANNEALER (Lambda Warmup)
# =============================================================================

class SovereignAnnealer:
    """
    Ramps up Ontological constraints (Backward Score) only after
    Linguistic competence (Forward Score) is established.

    Phase 1 (Steps 0-warmup): System 1 dominant (learn to speak)
    Phase 2 (Steps warmup+): System 2 engaged (learn to reason)

    This prevents early training collapse from Lagrangian explosion.
    """

    def __init__(
        self,
        total_steps: int = 50000,
        warmup_steps: int = 5000,
    ):
        self.total_steps = total_steps
        self.warmup_steps = warmup_steps

    def get_lambdas(self, current_step: int) -> Dict[str, float]:
        """
        Get current lambda values based on training progress.

        Args:
            current_step: Current training step

        Returns:
            Dict of lambda values for each loss component
        """
        if current_step < self.warmup_steps:
            # Phase 1: Learn to Speak (System 1 dominant)
            progress = current_step / self.warmup_steps

            return {
                'lambda_f': 1.0,                        # Linguistic Coherence (full)
                'lambda_b': 0.0 + progress,             # Ontological Alignment (ramping)
                'lambda_c': 0.0 + (progress * 0.5),     # Divergence penalty (ramping slower)
                'lambda_entropy': 0.1 + (progress * 0.2),  # SCC constraint (ramping)
                'lambda_coherence': 0.1 + (progress * 0.1),  # USE constraint (ramping)
            }
        else:
            # Phase 2: Learn to Reason (System 2 engaged)
            post_warmup_progress = (
                (current_step - self.warmup_steps) /
                (self.total_steps - self.warmup_steps)
            )

            return {
                'lambda_f': 1.0,
                'lambda_b': 1.0,
                'lambda_c': 0.5,
                'lambda_entropy': 0.3,
                'lambda_coherence': 0.2,
            }

    def get_phase_name(self, current_step: int) -> str:
        """Return human-readable phase name for logging."""
        if current_step < self.warmup_steps * 0.2:
            return "CALIBRATION"
        elif current_step < self.warmup_steps:
            return "LINGUISTIC_FOUNDATION"
        elif current_step < self.warmup_steps * 2:
            return "ONTOLOGICAL_ALIGNMENT"
        elif current_step < self.total_steps * 0.5:
            return "STABILIZATION"
        else:
            return "MATURATION"

    def update_loss_config(
        self,
        config: SovereignLossConfig,
        current_step: int,
    ) -> SovereignLossConfig:
        """
        Update loss config with annealed lambdas.

        Args:
            config: Current loss config
            current_step: Current training step

        Returns:
            Updated config with annealed values
        """
        lambdas = self.get_lambdas(current_step)

        config.lambda_f = lambdas['lambda_f']
        config.lambda_b = lambdas['lambda_b']
        config.lambda_c = lambdas['lambda_c']
        config.lambda_entropy = lambdas['lambda_entropy']
        config.lambda_coherence = lambdas['lambda_coherence']

        return config


# =============================================================================
# TELEOLOGICAL OPTIMIZER (Gradient Clipping)
# =============================================================================

class TeleologicalOptimizer:
    """
    Wraps base optimizer with gradient clipping based on consistency.

    Clips gradients when the Consistency Lagrangian indicates
    high divergence between forward and backward scores.

    This prevents destructive updates when the model is confused.
    """

    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        max_grad_norm: float = 1.0,
        consistency_clip_threshold: float = 0.5,
    ):
        self.optimizer = optimizer
        self.max_grad_norm = max_grad_norm
        self.consistency_clip_threshold = consistency_clip_threshold

    def step(
        self,
        model: nn.Module,
        diagnostics: Optional[Dict[str, float]] = None,
    ):
        """
        Perform optimization step with teleological gradient clipping.

        Args:
            model: Model to optimize
            diagnostics: Dict containing s_f, s_b from loss computation
        """
        # Compute consistency-based clip factor
        clip_factor = self.max_grad_norm

        if diagnostics is not None:
            s_f = diagnostics.get('s_f', 0.5)
            s_b = diagnostics.get('s_b', 0.5)
            divergence = abs(s_f - s_b)

            if divergence > self.consistency_clip_threshold:
                # Reduce gradient magnitude when confused
                clip_factor = self.max_grad_norm * (1.0 - divergence)
                clip_factor = max(clip_factor, 0.1)  # Minimum clip

        # Clip gradients
        torch.nn.utils.clip_grad_norm_(model.parameters(), clip_factor)

        # Optimizer step
        self.optimizer.step()

    def zero_grad(self):
        """Zero gradients."""
        self.optimizer.zero_grad()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'SovereignLossConfig',
    'SovereignLoss',
    'SovereignAnnealer',
    'TeleologicalOptimizer',
    'BackwardScoreCalculator',
    'ForwardScoreCalculator',
    'PhaseCoherenceCalculator',
]
