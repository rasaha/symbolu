"""
Ontological State Predictor — Training Curriculum Orchestrator.

Manages the three-phase micro-curriculum for state prediction:
- DHYANA (Meditation): State foundation, 1-step prediction
- SAMVADA (Dialogue): Prediction expansion, k-step lookahead
- KRTI (Action): Full integration with token generation

And the Body→Soul→Union macro-curriculum when paired with SRK:
- BODY: Ontological state learning (Dhyana + Samvada)
- SOUL: Reasoning via language modeling (SRK)
- UNION: Joint alignment across all five planes

References:
    - HYBRID_PHASE_JEPA_DESIGN.md §5.1 Three-Phase Curriculum
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Optional, Tuple, Callable
import torch


class JEPAPhase(Enum):
    """Internal JEPA training phases (micro-curriculum)."""
    DHYANA = 1    # Meditation: State foundation, k=1
    SAMVADA = 2   # Dialogue: Prediction expansion, k=4
    KRTI = 3      # Action: Full integration


class MacroPhase(Enum):
    """Macro-curriculum phases for SRK-JEPA integration."""
    BODY = auto()   # JEPA perceptual learning (Dhyana + Samvada)
    SOUL = auto()   # SRK reasoning (language modeling)
    UNION = auto()  # Joint alignment (Krti + SRK alignment)


@dataclass
class PhaseConfig:
    """Configuration for a single training phase."""

    # Prediction settings
    k_steps: int = 1                    # Number of prediction steps
    enable_intent_rotation: bool = False  # Enable intent phase rotation
    freeze_predictor: bool = False      # Freeze predictor weights

    # Loss weights
    jepa_weight: float = 1.0            # JEPA prediction loss
    variance_weight: float = 2.0        # VICReg variance loss
    covariance_weight: float = 0.5      # VICReg covariance loss
    ortho_weight: float = 0.0           # Orthogonality loss
    nll_weight: float = 0.0             # Next token prediction loss
    alignment_weight: float = 0.0       # SRK-JEPA alignment loss

    # OPB settings
    enable_opb_locking: bool = False    # Enable OPB dimension locking


# Canonical phase configurations from design document
PHASE_CONFIGS = {
    JEPAPhase.DHYANA: PhaseConfig(
        k_steps=1,
        enable_intent_rotation=False,
        freeze_predictor=True,  # Shallow MLP only
        jepa_weight=1.0,
        variance_weight=2.0,
        covariance_weight=0.5,
        ortho_weight=0.0,
        nll_weight=0.0,
        enable_opb_locking=False,
    ),
    JEPAPhase.SAMVADA: PhaseConfig(
        k_steps=4,
        enable_intent_rotation=True,
        freeze_predictor=False,  # Unfreeze full predictor
        jepa_weight=1.0,
        variance_weight=1.0,
        covariance_weight=0.5,
        ortho_weight=0.1,
        nll_weight=0.0,
        enable_opb_locking=False,
    ),
    JEPAPhase.KRTI: PhaseConfig(
        k_steps=4,
        enable_intent_rotation=True,
        freeze_predictor=False,
        jepa_weight=0.3,
        variance_weight=0.1,
        covariance_weight=0.1,
        ortho_weight=0.1,
        nll_weight=0.5,
        enable_opb_locking=True,  # Full OPB active
    ),
}


@dataclass
class CurriculumState:
    """Current state of the training curriculum."""

    current_step: int = 0
    total_steps: int = 50000

    # Phase tracking
    jepa_phase: JEPAPhase = JEPAPhase.DHYANA
    macro_phase: MacroPhase = MacroPhase.BODY

    # Phase boundaries (step numbers)
    dhyana_end: int = 0     # End of Dhyana (20%)
    samvada_end: int = 0    # End of Samvada (70% cumulative)
    body_end: int = 0       # End of Body macro-phase
    soul_end: int = 0       # End of Soul macro-phase

    # Metrics tracking
    avg_variance: float = 0.0
    avg_prediction_error: float = 0.0
    phase_transitions: int = 0

    # Dynamic graduation metrics (for threshold-based transitions)
    avg_jepa_loss: float = float('inf')      # Rolling average JEPA loss
    avg_alignment: float = 0.0               # Rolling average alignment score
    graduation_trigger: str = ""             # What triggered graduation (for logging)

    def __post_init__(self):
        """Calculate phase boundaries."""
        # JEPA micro-phases (within Body macro-phase)
        self.dhyana_end = int(self.total_steps * 0.20)
        self.samvada_end = int(self.total_steps * 0.70)

        # Macro-phases for SRK-JEPA (from CLI args)
        # These can be overridden by config


class TrainingCurriculumOrchestrator:
    """
    Orchestrates the Phase-JEPA training curriculum.

    Manages phase transitions, loss weight scheduling, and
    coordination between JEPA and SRK training.

    Example:
        >>> orchestrator = TrainingCurriculumOrchestrator(total_steps=50000)
        >>> for step in range(50000):
        ...     phase_config = orchestrator.get_current_config()
        ...     # Use phase_config for training
        ...     orchestrator.step(metrics={'variance': var, 'pred_error': err})
    """

    def __init__(
        self,
        total_steps: int = 50000,
        body_steps: int = 20000,
        soul_steps: int = 30000,
        auto_transition: bool = True,
        initial_phase: str = "body",
        callbacks: Optional[Dict[str, Callable]] = None,
        # Dynamic graduation thresholds
        graduation_loss_threshold: float = 20.0,      # Graduate if JEPA loss < this
        graduation_alignment_threshold: float = 25.0,  # V9.6.8: Was 72.0 - unrealistic
        enable_dynamic_graduation: bool = True,        # Enable threshold-based graduation
    ):
        """
        Initialize curriculum orchestrator.

        Args:
            total_steps: Total training steps
            body_steps: Steps for Body phase (JEPA perceptual)
            soul_steps: Steps for Soul phase (SRK reasoning)
            auto_transition: Automatically transition phases
            initial_phase: Starting macro-phase ('body', 'soul', 'union')
            callbacks: Optional callbacks for phase transitions
            graduation_loss_threshold: JEPA loss must be below this to graduate early
            graduation_alignment_threshold: Alignment must be above this to graduate early
            enable_dynamic_graduation: Whether to enable metric-based graduation
        """
        self.total_steps = total_steps
        self.body_steps = body_steps
        self.soul_steps = soul_steps
        self.auto_transition = auto_transition
        self.callbacks = callbacks or {}

        # Dynamic graduation settings
        self.graduation_loss_threshold = graduation_loss_threshold
        self.graduation_alignment_threshold = graduation_alignment_threshold
        self.enable_dynamic_graduation = enable_dynamic_graduation

        # Initialize state
        self.state = CurriculumState(
            total_steps=total_steps,
            body_end=body_steps,
            soul_end=body_steps + soul_steps,
        )

        # Set initial macro-phase
        self.state.macro_phase = MacroPhase[initial_phase.upper()]

        # Calculate JEPA micro-phase boundaries within Body phase
        if body_steps > 0:
            self.state.dhyana_end = int(body_steps * 0.25)  # 25% of Body
            self.state.samvada_end = body_steps  # Rest of Body

    def step(
        self,
        metrics: Optional[Dict[str, float]] = None,
        force_phase: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Advance curriculum by one step.

        Args:
            metrics: Training metrics for adaptive transitions
                - variance: VICReg variance component
                - pred_error: Prediction error
                - jepa_loss: Total JEPA loss (for dynamic graduation)
                - alignment: Alignment score (for dynamic graduation)
            force_phase: Force transition to specific phase

        Returns:
            Tuple of (phase_changed, new_phase_name)
        """
        self.state.current_step += 1
        metrics = metrics or {}

        # Update rolling metrics
        if 'variance' in metrics:
            self.state.avg_variance = (
                0.9 * self.state.avg_variance + 0.1 * metrics['variance']
            )
        if 'pred_error' in metrics:
            self.state.avg_prediction_error = (
                0.9 * self.state.avg_prediction_error + 0.1 * metrics['pred_error']
            )

        # Update dynamic graduation metrics (exponential moving average)
        if 'jepa_loss' in metrics:
            if self.state.avg_jepa_loss == float('inf'):
                # First update: initialize with actual value
                self.state.avg_jepa_loss = metrics['jepa_loss']
            else:
                self.state.avg_jepa_loss = (
                    0.95 * self.state.avg_jepa_loss + 0.05 * metrics['jepa_loss']
                )
        if 'alignment' in metrics:
            self.state.avg_alignment = (
                0.95 * self.state.avg_alignment + 0.05 * metrics['alignment']
            )

        # Check for forced phase transition
        if force_phase:
            return self._transition_to(force_phase)

        # Auto-transition logic
        if self.auto_transition:
            return self._check_auto_transition()

        return False, None

    def _check_auto_transition(self) -> Tuple[bool, Optional[str]]:
        """Check if automatic phase transition should occur.

        Implements two graduation pathways:
        1. Dynamic Graduation: Metric-based (loss < threshold AND alignment > threshold)
        2. Timeout Graduation: Step-based deadline (safety net)
        """
        step = self.state.current_step

        # Macro-phase transitions
        if self.state.macro_phase == MacroPhase.BODY:
            # 1. Dynamic Graduation (The "Smart" Logic)
            # Check if model is ready to graduate based on metrics
            if self.enable_dynamic_graduation and self.auto_transition:
                loss_ready = self.state.avg_jepa_loss < self.graduation_loss_threshold
                alignment_ready = self.state.avg_alignment > self.graduation_alignment_threshold

                if loss_ready and alignment_ready:
                    # Record what triggered graduation
                    self.state.graduation_trigger = (
                        f"Loss {self.state.avg_jepa_loss:.2f} < {self.graduation_loss_threshold} "
                        f"AND Align {self.state.avg_alignment:.1f} > {self.graduation_alignment_threshold}"
                    )
                    print(f"\n  🎓 DYNAMIC GRADUATION TRIGGERED at Step {step}!")
                    print(f"     └─ {self.state.graduation_trigger}")
                    return self._transition_to('soul')

            # 2. Timeout Graduation (Safety Net - Hard Deadline)
            if step >= self.state.body_end:
                self.state.graduation_trigger = f"Timeout at step {step} (deadline: {self.state.body_end})"
                print(f"\n  ⏰ TIMEOUT GRADUATION at Step {step} (deadline reached)")
                return self._transition_to('soul')

            # JEPA micro-phase transitions within Body
            if self.state.jepa_phase == JEPAPhase.DHYANA:
                if step >= self.state.dhyana_end:
                    return self._transition_jepa_phase(JEPAPhase.SAMVADA)

        elif self.state.macro_phase == MacroPhase.SOUL:
            if step >= self.state.soul_end:
                return self._transition_to('union')

        # Union phase continues until end
        return False, None

    def _transition_to(self, phase_name: str) -> Tuple[bool, Optional[str]]:
        """Transition to a specific macro-phase."""
        old_phase = self.state.macro_phase
        new_phase = MacroPhase[phase_name.upper()]

        if old_phase == new_phase:
            return False, None

        self.state.macro_phase = new_phase
        self.state.phase_transitions += 1

        # Set appropriate JEPA micro-phase
        if new_phase == MacroPhase.BODY:
            self.state.jepa_phase = JEPAPhase.DHYANA
        elif new_phase == MacroPhase.UNION:
            self.state.jepa_phase = JEPAPhase.KRTI

        # Fire callback if registered
        callback_name = f'on_{phase_name.lower()}'
        if callback_name in self.callbacks:
            self.callbacks[callback_name](self.state)

        return True, new_phase.name

    def _transition_jepa_phase(
        self,
        new_phase: JEPAPhase,
    ) -> Tuple[bool, Optional[str]]:
        """Transition JEPA micro-phase."""
        old_phase = self.state.jepa_phase

        if old_phase == new_phase:
            return False, None

        self.state.jepa_phase = new_phase

        # Fire callback
        callback_name = f'on_jepa_{new_phase.name.lower()}'
        if callback_name in self.callbacks:
            self.callbacks[callback_name](self.state)

        return True, f"JEPA_{new_phase.name}"

    def get_current_config(self) -> PhaseConfig:
        """Get configuration for current training phase."""
        base_config = PHASE_CONFIGS[self.state.jepa_phase]

        # Modify config based on macro-phase
        if self.state.macro_phase == MacroPhase.SOUL:
            # During Soul phase, JEPA is mostly frozen
            return PhaseConfig(
                k_steps=base_config.k_steps,
                enable_intent_rotation=False,
                freeze_predictor=True,
                jepa_weight=0.1,  # Minimal JEPA loss
                variance_weight=0.1,
                covariance_weight=0.1,
                ortho_weight=0.0,
                nll_weight=1.0,  # Focus on language modeling
                enable_opb_locking=True,
            )

        elif self.state.macro_phase == MacroPhase.UNION:
            # Union phase: enable alignment loss
            config = PhaseConfig(
                k_steps=base_config.k_steps,
                enable_intent_rotation=True,
                freeze_predictor=False,
                jepa_weight=base_config.jepa_weight,
                variance_weight=base_config.variance_weight,
                covariance_weight=base_config.covariance_weight,
                ortho_weight=base_config.ortho_weight,
                nll_weight=base_config.nll_weight,
                alignment_weight=1.0,  # Enable alignment
                enable_opb_locking=True,
            )
            return config

        return base_config

    def get_loss_weights(self) -> Dict[str, float]:
        """Get current loss weights as dictionary."""
        config = self.get_current_config()
        return {
            'jepa': config.jepa_weight,
            'variance': config.variance_weight,
            'covariance': config.covariance_weight,
            'ortho': config.ortho_weight,
            'nll': config.nll_weight,
            'alignment': config.alignment_weight,
        }

    def get_k_steps(self) -> int:
        """Get current prediction step count."""
        return self.get_current_config().k_steps

    def should_freeze_predictor(self) -> bool:
        """Check if predictor should be frozen."""
        return self.get_current_config().freeze_predictor

    def should_enable_intent_rotation(self) -> bool:
        """Check if intent phase rotation should be enabled."""
        return self.get_current_config().enable_intent_rotation

    def should_enable_opb(self) -> bool:
        """Check if OPB dimension locking should be enabled."""
        return self.get_current_config().enable_opb_locking

    def get_progress(self) -> Dict[str, float]:
        """Get training progress information."""
        step = self.state.current_step

        # Overall progress
        overall = step / self.total_steps if self.total_steps > 0 else 0.0

        # Phase-specific progress
        if self.state.macro_phase == MacroPhase.BODY:
            phase_progress = step / self.state.body_end if self.state.body_end > 0 else 0.0
        elif self.state.macro_phase == MacroPhase.SOUL:
            soul_start = self.state.body_end
            soul_duration = self.state.soul_end - soul_start
            phase_progress = (step - soul_start) / soul_duration if soul_duration > 0 else 0.0
        else:  # UNION
            union_start = self.state.soul_end
            union_duration = self.total_steps - union_start
            phase_progress = (step - union_start) / union_duration if union_duration > 0 else 0.0

        return {
            'overall': min(1.0, overall),
            'phase_progress': min(1.0, max(0.0, phase_progress)),
            'current_step': step,
            'total_steps': self.total_steps,
            'macro_phase': self.state.macro_phase.name,
            'jepa_phase': self.state.jepa_phase.name,
            'phase_transitions': self.state.phase_transitions,
        }

    def state_dict(self) -> Dict:
        """Get state dictionary for checkpointing."""
        return {
            'current_step': self.state.current_step,
            'jepa_phase': self.state.jepa_phase.value,
            'macro_phase': self.state.macro_phase.value,
            'avg_variance': self.state.avg_variance,
            'avg_prediction_error': self.state.avg_prediction_error,
            'phase_transitions': self.state.phase_transitions,
            # Dynamic graduation metrics
            'avg_jepa_loss': self.state.avg_jepa_loss,
            'avg_alignment': self.state.avg_alignment,
            'graduation_trigger': self.state.graduation_trigger,
            'config': {
                'total_steps': self.total_steps,
                'body_steps': self.body_steps,
                'soul_steps': self.soul_steps,
                'auto_transition': self.auto_transition,
                'graduation_loss_threshold': self.graduation_loss_threshold,
                'graduation_alignment_threshold': self.graduation_alignment_threshold,
                'enable_dynamic_graduation': self.enable_dynamic_graduation,
            },
        }

    def load_state_dict(self, state_dict: Dict) -> None:
        """Load state dictionary from checkpoint."""
        self.state.current_step = state_dict['current_step']
        self.state.jepa_phase = JEPAPhase(state_dict['jepa_phase'])
        self.state.macro_phase = MacroPhase(state_dict['macro_phase'])
        self.state.avg_variance = state_dict.get('avg_variance', 0.0)
        self.state.avg_prediction_error = state_dict.get('avg_prediction_error', 0.0)
        self.state.phase_transitions = state_dict.get('phase_transitions', 0)
        # Dynamic graduation metrics
        self.state.avg_jepa_loss = state_dict.get('avg_jepa_loss', float('inf'))
        self.state.avg_alignment = state_dict.get('avg_alignment', 0.0)
        self.state.graduation_trigger = state_dict.get('graduation_trigger', '')


class LossScheduler:
    """
    Curriculum-based loss weight scheduling.

    Provides smooth interpolation between phase loss weights
    during transitions.

    Reference: HYBRID_PHASE_JEPA_DESIGN.md §21
    """

    def __init__(
        self,
        orchestrator: TrainingCurriculumOrchestrator,
        transition_steps: int = 500,
    ):
        """
        Initialize loss scheduler.

        Args:
            orchestrator: Curriculum orchestrator instance
            transition_steps: Steps to smoothly transition weights
        """
        self.orchestrator = orchestrator
        self.transition_steps = transition_steps

        # Cache for smooth transitions
        self._prev_weights: Optional[Dict[str, float]] = None
        self._transition_start: int = 0

    def get_weights(self) -> Dict[str, float]:
        """
        Get current loss weights with smooth interpolation.

        Returns:
            Dictionary of loss component weights
        """
        current_weights = self.orchestrator.get_loss_weights()

        # Check if we need smooth transition
        if self._prev_weights is None:
            self._prev_weights = current_weights
            return current_weights

        # Check if weights changed (phase transition)
        if current_weights != self._prev_weights:
            self._transition_start = self.orchestrator.state.current_step
            old_weights = self._prev_weights
            self._prev_weights = current_weights

            # Start of transition
            return old_weights

        # During transition: interpolate
        steps_in_transition = (
            self.orchestrator.state.current_step - self._transition_start
        )

        if steps_in_transition < self.transition_steps:
            # Linear interpolation
            alpha = steps_in_transition / self.transition_steps
            return self._interpolate_weights(
                self._prev_weights,
                current_weights,
                alpha,
            )

        return current_weights

    def _interpolate_weights(
        self,
        old: Dict[str, float],
        new: Dict[str, float],
        alpha: float,
    ) -> Dict[str, float]:
        """Linearly interpolate between weight dictionaries."""
        return {
            key: (1 - alpha) * old.get(key, 0.0) + alpha * new.get(key, 0.0)
            for key in set(old.keys()) | set(new.keys())
        }


def create_curriculum_from_config(config) -> TrainingCurriculumOrchestrator:
    """
    Factory function to create curriculum orchestrator from config.

    Args:
        config: UnifiedTrainingConfig or similar with JEPA settings

    Returns:
        Configured TrainingCurriculumOrchestrator
    """
    return TrainingCurriculumOrchestrator(
        total_steps=getattr(config, 'max_steps', 50000),
        body_steps=getattr(config, 'jepa_phase_body_steps', 20000),
        soul_steps=getattr(config, 'jepa_phase_soul_steps', 30000),
        auto_transition=getattr(config, 'jepa_auto_phase_transition', False),
        initial_phase=getattr(config, 'jepa_training_phase', 'body'),
        # Dynamic graduation thresholds
        graduation_loss_threshold=getattr(config, 'jepa_graduation_loss_threshold', 20.0),
        graduation_alignment_threshold=getattr(config, 'jepa_graduation_alignment_threshold', 25.0),
        enable_dynamic_graduation=getattr(config, 'jepa_enable_dynamic_graduation', True),
    )
