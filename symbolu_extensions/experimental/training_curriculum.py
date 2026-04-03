#!/usr/bin/env python3
"""
Training Curriculum: Phased Constraint Introduction
====================================================

This module implements the training curriculum from the Google
Architecture Proposals - a systematic approach to introducing
alignment constraints during model training.

Key Insight:
------------
Introducing all constraints at once can destabilize training.
Instead, we use a phased curriculum:

Phase 1: Base capability + orthogonality
Phase 2: Add Phase-Lock constraint
Phase 3: Add Smṛti persistence
Phase 4: Full axiom enforcement

Curriculum Design:
------------------
    Epoch 0-N₁: Warm-up
    ├── Token prediction loss only
    ├── No alignment constraints
    └── Build base language capability

    Epoch N₁-N₂: Orthogonality Phase
    ├── Add L_ortho loss
    ├── Project R matrices to Stiefel manifold
    └── Learn truth-preserving transformations

    Epoch N₂-N₃: Phase-Lock Phase
    ├── Add Phase-Lock constraint
    ├── Start with low τ, increase gradually
    └── Learn internal-external alignment

    Epoch N₃-N₄: Persistence Phase
    ├── Add Smṛti drift correction
    ├── Anchor to S_0
    └── Prevent catastrophic drift

    Epoch N₄+: Full Enforcement
    ├── All constraints active
    ├── Axiom checking enabled
    └── Logic gate validation

Usage:
------
    from symbolu_extensions.experimental.training_curriculum import (
        TrainingCurriculum,
        CurriculumConfig,
        CurriculumPhase,
    )

    curriculum = TrainingCurriculum(CurriculumConfig(
        warmup_epochs=5,
        ortho_epochs=10,
        phase_lock_epochs=10,
        persistence_epochs=5,
    ))

    for epoch in range(total_epochs):
        phase = curriculum.get_phase(epoch)
        loss_weights = curriculum.get_loss_weights(epoch)

        # Use in training loop
        loss = compute_loss(model_output, loss_weights)
"""

import torch
import torch.nn as nn
from typing import Dict, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import math


# =============================================================================
# CURRICULUM PHASES
# =============================================================================

class CurriculumPhase(Enum):
    """Training curriculum phases."""
    WARMUP = "warmup"              # Base capability only
    ORTHOGONALITY = "orthogonality"  # Add L_ortho
    PHASE_LOCK = "phase_lock"       # Add Phase-Lock
    PERSISTENCE = "persistence"     # Add Smṛti
    FULL = "full"                   # All constraints


@dataclass
class CurriculumConfig:
    """Configuration for training curriculum."""
    # Phase durations (in epochs)
    warmup_epochs: int = 5
    ortho_epochs: int = 10
    phase_lock_epochs: int = 10
    persistence_epochs: int = 5

    # Loss weight schedules
    lambda_token_base: float = 1.0
    lambda_state_base: float = 0.3
    lambda_ortho_base: float = 0.5
    lambda_phase_lock_base: float = 0.3
    lambda_persistence_base: float = 0.1
    lambda_axiom_base: float = 0.2
    lambda_logic_base: float = 0.1

    # Constraint scheduling
    tau_initial: float = 0.3       # Initial Phase-Lock threshold
    tau_final: float = 0.7         # Final Phase-Lock threshold
    drift_lambda_initial: float = 0.01  # Initial Smṛti strength
    drift_lambda_final: float = 0.05    # Final Smṛti strength

    # Ramp-up settings
    ramp_type: str = "linear"      # "linear", "cosine", "exponential"

    @property
    def total_curriculum_epochs(self) -> int:
        return (
            self.warmup_epochs +
            self.ortho_epochs +
            self.phase_lock_epochs +
            self.persistence_epochs
        )


# =============================================================================
# TRAINING CURRICULUM
# =============================================================================

class TrainingCurriculum:
    """
    Manages the phased introduction of alignment constraints.

    This class:
    1. Tracks current training phase based on epoch
    2. Computes loss weights for each phase
    3. Schedules constraint parameters (τ, λ, etc.)
    4. Provides callbacks for phase transitions
    """

    def __init__(self, config: CurriculumConfig):
        self.config = config
        self._phase_callbacks: Dict[CurriculumPhase, list] = {
            phase: [] for phase in CurriculumPhase
        }
        self._current_phase = CurriculumPhase.WARMUP

    def get_phase(self, epoch: int) -> CurriculumPhase:
        """Determine current curriculum phase based on epoch."""
        c = self.config

        if epoch < c.warmup_epochs:
            phase = CurriculumPhase.WARMUP
        elif epoch < c.warmup_epochs + c.ortho_epochs:
            phase = CurriculumPhase.ORTHOGONALITY
        elif epoch < c.warmup_epochs + c.ortho_epochs + c.phase_lock_epochs:
            phase = CurriculumPhase.PHASE_LOCK
        elif epoch < c.total_curriculum_epochs:
            phase = CurriculumPhase.PERSISTENCE
        else:
            phase = CurriculumPhase.FULL

        # Trigger callbacks if phase changed
        if phase != self._current_phase:
            self._trigger_phase_transition(self._current_phase, phase)
            self._current_phase = phase

        return phase

    def get_loss_weights(self, epoch: int) -> Dict[str, float]:
        """
        Get loss weights for current epoch.

        Returns:
            Dict mapping loss names to weights
        """
        phase = self.get_phase(epoch)
        c = self.config

        weights = {
            'token': c.lambda_token_base,
            'state': c.lambda_state_base,
            'ortho': 0.0,
            'phase_lock': 0.0,
            'persistence': 0.0,
            'axiom': 0.0,
            'logic': 0.0,
        }

        if phase == CurriculumPhase.WARMUP:
            # Only base losses
            pass

        elif phase == CurriculumPhase.ORTHOGONALITY:
            # Ramp up orthogonality loss
            progress = self._get_phase_progress(epoch, phase)
            weights['ortho'] = c.lambda_ortho_base * self._ramp(progress)

        elif phase == CurriculumPhase.PHASE_LOCK:
            # Full ortho, ramp up phase-lock
            weights['ortho'] = c.lambda_ortho_base
            progress = self._get_phase_progress(epoch, phase)
            weights['phase_lock'] = c.lambda_phase_lock_base * self._ramp(progress)

        elif phase == CurriculumPhase.PERSISTENCE:
            # Full ortho and phase-lock, ramp up persistence
            weights['ortho'] = c.lambda_ortho_base
            weights['phase_lock'] = c.lambda_phase_lock_base
            progress = self._get_phase_progress(epoch, phase)
            weights['persistence'] = c.lambda_persistence_base * self._ramp(progress)

        elif phase == CurriculumPhase.FULL:
            # All constraints active
            weights['ortho'] = c.lambda_ortho_base
            weights['phase_lock'] = c.lambda_phase_lock_base
            weights['persistence'] = c.lambda_persistence_base
            weights['axiom'] = c.lambda_axiom_base
            weights['logic'] = c.lambda_logic_base

        return weights

    def get_tau(self, epoch: int) -> float:
        """Get Phase-Lock threshold τ for current epoch."""
        phase = self.get_phase(epoch)
        c = self.config

        if phase.value < CurriculumPhase.PHASE_LOCK.value:
            # Before phase-lock phase, use initial (permissive)
            return c.tau_initial

        elif phase == CurriculumPhase.PHASE_LOCK:
            # During phase-lock phase, ramp up
            progress = self._get_phase_progress(epoch, phase)
            return c.tau_initial + (c.tau_final - c.tau_initial) * self._ramp(progress)

        else:
            # After phase-lock phase, use final
            return c.tau_final

    def get_drift_lambda(self, epoch: int) -> float:
        """Get Smṛti drift correction strength λ for current epoch."""
        phase = self.get_phase(epoch)
        c = self.config

        if phase.value < CurriculumPhase.PERSISTENCE.value:
            return c.drift_lambda_initial

        elif phase == CurriculumPhase.PERSISTENCE:
            progress = self._get_phase_progress(epoch, phase)
            return (
                c.drift_lambda_initial +
                (c.drift_lambda_final - c.drift_lambda_initial) * self._ramp(progress)
            )

        else:
            return c.drift_lambda_final

    def _get_phase_progress(self, epoch: int, phase: CurriculumPhase) -> float:
        """Get progress within current phase (0 to 1)."""
        c = self.config

        if phase == CurriculumPhase.WARMUP:
            start, duration = 0, c.warmup_epochs
        elif phase == CurriculumPhase.ORTHOGONALITY:
            start, duration = c.warmup_epochs, c.ortho_epochs
        elif phase == CurriculumPhase.PHASE_LOCK:
            start, duration = c.warmup_epochs + c.ortho_epochs, c.phase_lock_epochs
        elif phase == CurriculumPhase.PERSISTENCE:
            start, duration = c.warmup_epochs + c.ortho_epochs + c.phase_lock_epochs, c.persistence_epochs
        else:
            return 1.0

        if duration == 0:
            return 1.0

        progress = (epoch - start) / duration
        return min(1.0, max(0.0, progress))

    def _ramp(self, progress: float) -> float:
        """Apply ramp function to progress."""
        ramp_type = self.config.ramp_type

        if ramp_type == "linear":
            return progress
        elif ramp_type == "cosine":
            return 0.5 * (1 - math.cos(math.pi * progress))
        elif ramp_type == "exponential":
            return (math.exp(progress) - 1) / (math.e - 1)
        else:
            return progress

    def register_phase_callback(
        self,
        phase: CurriculumPhase,
        callback: Callable[[CurriculumPhase, CurriculumPhase], None],
    ):
        """Register callback for phase transition."""
        self._phase_callbacks[phase].append(callback)

    def _trigger_phase_transition(
        self,
        old_phase: CurriculumPhase,
        new_phase: CurriculumPhase,
    ):
        """Trigger callbacks for phase transition."""
        for callback in self._phase_callbacks[new_phase]:
            callback(old_phase, new_phase)


# =============================================================================
# CURRICULUM-AWARE LOSS FUNCTION
# =============================================================================

class CurriculumLoss(nn.Module):
    """
    Loss function that respects curriculum scheduling.

    Combines:
    - Token prediction loss
    - State-delta loss
    - Orthogonality loss (from phase_alignment)
    - Phase-Lock loss (from phase_alignment)
    - Persistence loss (Smṛti drift)
    - Axiom loss (from logic_gates)
    - Logic loss (Vyāpti, Hetvābhāsa)
    """

    def __init__(
        self,
        curriculum: TrainingCurriculum,
        state_dim: int = 124,
        bhava_dim: int = 12,
    ):
        super().__init__()
        self.curriculum = curriculum
        self.state_dim = state_dim
        self.bhava_dim = bhava_dim

        # Import components (lazy to avoid circular imports)
        self._ortho_loss = None
        self._phase_lock = None
        self._smriti = None
        self._axiom_checker = None
        self._logic_gate = None

    def _init_components(self, device):
        """Initialize loss components on first use."""
        from .phase_alignment import (
            OrthogonalityLoss,
            PhaseLockGate,
            SmritiPersistenceLoop,
        )
        from .logic_gates import AxiomChecker, LogicGate

        if self._ortho_loss is None:
            self._ortho_loss = OrthogonalityLoss().to(device)
            self._phase_lock = PhaseLockGate(
                bhava_dim=self.bhava_dim,
                state_dim=self.state_dim,
            ).to(device)
            self._smriti = SmritiPersistenceLoop(
                state_dim=self.state_dim,
            ).to(device)
            self._axiom_checker = AxiomChecker().to(device)
            self._logic_gate = LogicGate().to(device)

    def forward(
        self,
        epoch: int,
        logits: torch.Tensor,
        labels: torch.Tensor,
        cognitive_state: torch.Tensor,
        R_matrix: Optional[torch.Tensor] = None,
        delta_predicted: Optional[torch.Tensor] = None,
        delta_actual: Optional[torch.Tensor] = None,
        premise: Optional[torch.Tensor] = None,
        conclusion: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute curriculum-aware loss.

        Args:
            epoch: Current training epoch
            logits: [B, T, vocab] model predictions
            labels: [B, T] target tokens
            cognitive_state: [B, T, state_dim] cognitive states
            R_matrix: Optional R matrix for orthogonality loss
            delta_predicted: Optional predicted state deltas
            delta_actual: Optional actual state deltas
            premise: Optional premise embeddings for logic checks
            conclusion: Optional conclusion embeddings

        Returns:
            Dict with individual and total losses
        """
        device = logits.device
        self._init_components(device)

        # Get curriculum parameters
        weights = self.curriculum.get_loss_weights(epoch)
        tau = self.curriculum.get_tau(epoch)
        drift_lambda = self.curriculum.get_drift_lambda(epoch)

        losses = {}

        # 1. Token prediction loss (always active)
        vocab_size = logits.size(-1)
        shift_logits = logits[:, :-1].contiguous()
        shift_labels = labels[:, 1:].contiguous()
        token_loss = nn.functional.cross_entropy(
            shift_logits.view(-1, vocab_size),
            shift_labels.view(-1),
            ignore_index=-100,
        )
        losses['token_loss'] = weights['token'] * token_loss

        # 2. State-delta loss (always active)
        if delta_predicted is not None and delta_actual is not None:
            state_loss = nn.functional.mse_loss(delta_predicted, delta_actual)
        else:
            state_loss = torch.tensor(0.0, device=device)
        losses['state_loss'] = weights['state'] * state_loss

        # 3. Orthogonality loss (from ORTHOGONALITY phase)
        if R_matrix is not None and weights['ortho'] > 0:
            ortho_loss = self._ortho_loss(R_matrix)
        else:
            ortho_loss = torch.tensor(0.0, device=device)
        losses['ortho_loss'] = weights['ortho'] * ortho_loss

        # 4. Phase-Lock loss (from PHASE_LOCK phase)
        if weights['phase_lock'] > 0:
            # Update tau dynamically
            self._phase_lock.phase_lock.tau_base = tau
            pl_losses = self._phase_lock.compute_loss(cognitive_state)
            phase_lock_loss = pl_losses['phase_lock_loss']
        else:
            phase_lock_loss = torch.tensor(0.0, device=device)
        losses['phase_lock_loss'] = weights['phase_lock'] * phase_lock_loss

        # 5. Persistence loss (from PERSISTENCE phase)
        if weights['persistence'] > 0:
            self._smriti.lambda_drift = drift_lambda
            persistence_loss = self._smriti.compute_drift_loss(cognitive_state)
        else:
            persistence_loss = torch.tensor(0.0, device=device)
        losses['persistence_loss'] = weights['persistence'] * persistence_loss

        # 6. Axiom loss (from FULL phase)
        if weights['axiom'] > 0:
            axiom_loss = self._axiom_checker.compute_loss(cognitive_state)
        else:
            axiom_loss = torch.tensor(0.0, device=device)
        losses['axiom_loss'] = weights['axiom'] * axiom_loss

        # 7. Logic loss (from FULL phase)
        if weights['logic'] > 0 and premise is not None and conclusion is not None:
            logic_losses = self._logic_gate.compute_loss(
                cognitive_state, premise, conclusion
            )
            logic_loss = logic_losses['total_logic_loss']
        else:
            logic_loss = torch.tensor(0.0, device=device)
        losses['logic_loss'] = weights['logic'] * logic_loss

        # Total loss
        total_loss = sum(losses.values())
        losses['total_loss'] = total_loss

        # Add metadata
        losses['_epoch'] = epoch
        losses['_phase'] = self.curriculum.get_phase(epoch).value
        losses['_tau'] = tau
        losses['_drift_lambda'] = drift_lambda

        return losses


# =============================================================================
# TRAINING LOOP HELPER
# =============================================================================

class CurriculumTrainer:
    """
    Helper class for curriculum-based training.

    Provides:
    - Progress tracking
    - Phase transition logging
    - Automatic parameter scheduling
    - Early stopping per phase
    """

    def __init__(
        self,
        model: nn.Module,
        curriculum: TrainingCurriculum,
        optimizer: torch.optim.Optimizer,
        device: torch.device,
    ):
        self.model = model
        self.curriculum = curriculum
        self.optimizer = optimizer
        self.device = device

        # Tracking
        self.epoch = 0
        self.step = 0
        self.phase_history: list = []

        # Register logging callbacks
        for phase in CurriculumPhase:
            curriculum.register_phase_callback(phase, self._log_phase_transition)

    def _log_phase_transition(
        self,
        old_phase: CurriculumPhase,
        new_phase: CurriculumPhase,
    ):
        """Log phase transitions."""
        self.phase_history.append({
            'epoch': self.epoch,
            'step': self.step,
            'from': old_phase.value,
            'to': new_phase.value,
        })
        print(f"\n[Curriculum] Phase transition: {old_phase.value} → {new_phase.value}")
        print(f"            at epoch {self.epoch}, step {self.step}")

    def get_training_state(self) -> Dict[str, Any]:
        """Get current training state for checkpointing."""
        return {
            'epoch': self.epoch,
            'step': self.step,
            'phase': self.curriculum.get_phase(self.epoch).value,
            'phase_history': self.phase_history,
            'tau': self.curriculum.get_tau(self.epoch),
            'drift_lambda': self.curriculum.get_drift_lambda(self.epoch),
            'loss_weights': self.curriculum.get_loss_weights(self.epoch),
        }

    def log_metrics(self, losses: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """Format losses for logging."""
        metrics = {}
        for name, value in losses.items():
            if isinstance(value, torch.Tensor):
                metrics[name] = value.item()
            elif isinstance(value, (int, float)):
                metrics[name] = value
        return metrics


# =============================================================================
# CONSTRAINT WARMUP SCHEDULER
# =============================================================================

class ConstraintWarmupScheduler:
    """
    Schedules constraint strength during warmup.

    Instead of hard phase boundaries, this allows smooth
    ramping of constraint strengths within a phase.
    """

    def __init__(
        self,
        initial_strength: float = 0.0,
        final_strength: float = 1.0,
        warmup_steps: int = 1000,
        schedule: str = "linear",
    ):
        self.initial = initial_strength
        self.final = final_strength
        self.warmup_steps = warmup_steps
        self.schedule = schedule
        self.current_step = 0

    def step(self) -> float:
        """Get current constraint strength and advance step."""
        if self.current_step >= self.warmup_steps:
            return self.final

        progress = self.current_step / self.warmup_steps

        if self.schedule == "linear":
            strength = self.initial + (self.final - self.initial) * progress
        elif self.schedule == "cosine":
            strength = self.initial + (self.final - self.initial) * (
                0.5 * (1 - math.cos(math.pi * progress))
            )
        elif self.schedule == "exponential":
            strength = self.initial + (self.final - self.initial) * (
                (math.exp(progress) - 1) / (math.e - 1)
            )
        else:
            strength = self.initial + (self.final - self.initial) * progress

        self.current_step += 1
        return strength

    def reset(self):
        """Reset to initial step."""
        self.current_step = 0


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("Training Curriculum Demo")
    print("=" * 60)

    # Create curriculum
    config = CurriculumConfig(
        warmup_epochs=5,
        ortho_epochs=10,
        phase_lock_epochs=10,
        persistence_epochs=5,
        ramp_type="cosine",
    )
    curriculum = TrainingCurriculum(config)

    print("\nCurriculum Configuration:")
    print(f"  Total curriculum epochs: {config.total_curriculum_epochs}")
    print(f"  Warmup: epochs 0-{config.warmup_epochs-1}")
    print(f"  Orthogonality: epochs {config.warmup_epochs}-{config.warmup_epochs+config.ortho_epochs-1}")
    print(f"  Phase-Lock: epochs {config.warmup_epochs+config.ortho_epochs}-{config.warmup_epochs+config.ortho_epochs+config.phase_lock_epochs-1}")
    print(f"  Persistence: epochs {config.warmup_epochs+config.ortho_epochs+config.phase_lock_epochs}-{config.total_curriculum_epochs-1}")
    print(f"  Full: epochs {config.total_curriculum_epochs}+")

    print("\n" + "-" * 60)
    print("Phase Progression:")
    print("-" * 60)

    sample_epochs = [0, 3, 5, 10, 15, 20, 25, 30, 35, 40]
    for epoch in sample_epochs:
        phase = curriculum.get_phase(epoch)
        weights = curriculum.get_loss_weights(epoch)
        tau = curriculum.get_tau(epoch)
        drift = curriculum.get_drift_lambda(epoch)

        print(f"\nEpoch {epoch:2d}: {phase.value:15s}")
        print(f"  τ (Phase-Lock): {tau:.3f}")
        print(f"  λ (Drift):      {drift:.4f}")
        print(f"  Loss weights:")
        for name, weight in weights.items():
            if weight > 0:
                print(f"    {name:12s}: {weight:.3f}")

    print("\n" + "=" * 60)
    print("Training Curriculum Demo Complete")
