"""
Kosha Gyroscope: Homeostatic Self-Regulation Loss Module (v2.2.0)

This module implements the Vijnana-Gated Kosha Balance Loss, a homeostatic
self-regulation mechanism that prevents pathological states (looping, fixation,
mode collapse) by enforcing balance across the 5 Kosha (sheath) dimensions.

Key Features:
- Vital Momentum: Dynamic gain based on Pranamaya energy
- Temporal Grounding: Physical history over 3-token window
- Vijnana Gate: Intellectual verification before state transitions
- Diagonal Opposition: Mental <-> Intellect, Physical <-> Blissful

R-T Quadrant Geometry:
- Physical  (+,+): Manifest, Past
- Mental    (-,+): Unmanifest, Past
- Intellect (+,-): Manifest, Future
- Blissful  (-,-): Unmanifest, Future
- Vital: Energy/Momentum (not mapped to quadrant)

References:
- docs/design/KOSHA_GYROSCOPE_DESIGN.md v2.2.0
- Taittiriya Upanishad (Pancha Kosha model)
- Yoga Sutras of Patanjali (Dharana concept)
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class KoshaGyroscopeConfig:
    """Configuration for Kosha Gyroscope with Inverted Curriculum.

    The Inverted Curriculum paradigm:
    - Gyroscope: Active from start, disengages when fluent (PPL < 30)
    - Classification: Disabled at start, engages when fluent (PPL < 30)
    """

    # === INVERTED CURRICULUM ===
    # Gyroscope (Instructor) - ON from step 0
    enable_gyroscope: bool = True
    gyroscope_disengage_ppl: float = 30.0   # OFF when PPL drops below this

    # Kosha Classification (Student) - OFF initially
    enable_kosha_classification: bool = False
    classification_engage_ppl: float = 30.0  # ON when PPL drops below this

    # Warmup for initial gyroscope activation
    gyroscope_warmup_steps: int = 100        # Steps before gyroscope fully active

    # Trap detection thresholds
    trap_threshold: float = 0.75         # Kosha saturation point
    gate_threshold: float = 0.30         # Minimum for gate activation
    balance_target: float = 0.25         # Required opposite activation

    # Loss scaling
    gain: float = 2.0                    # Base gain (increased for v2.2.0)
    gain_rampdown_steps: int = 500       # Steps to ramp gain to 0 at disengage
    gate_temperature: float = 10.0       # Softness of gate (higher = sharper)

    # v2.2.0 Refinements
    temporal_window: int = 3             # Physical history window size
    vital_momentum_enabled: bool = True  # Enable dynamic gain via Vital
    vital_momentum_range: Tuple[float, float] = (0.5, 1.5)  # Min/max scaler

    # Integration
    kosha_steering_layer: int = 9        # Layer to extract Kosha states from


class KoshaGyroscopicLoss(nn.Module):
    """
    Vijnana-Gated Kosha Balance Loss (v2.2.0).

    Implements homeostatic regulation with:
    - Diagonal transitions: Mental <-> Intellect, Physical <-> Blissful
    - Vijnana Gate: Intellectual verification before state transitions
    - Vital Momentum: Dynamic gain based on Pranamaya energy
    - Temporal Grounding: Physical history over 3-token window

    The loss enforces balance across the R-T quadrant geometry:

        TIME AXIS
        + (PAST)
            |
    MENTAL  |  PHYSICAL
    (-,+)   |   (+,+)
            |
    --------+-------- REALITY AXIS
            |
    BLISS   |  INTELLECT
    (-,-)   |   (+,-)
            |
        - (FUTURE)

    Diagonal pairs are polar opposites:
    - Mental (looping) <-> Intellect (structure)
    - Physical (inertia) <-> Blissful (expansion)
    """

    def __init__(
        self,
        trap_threshold: float = 0.75,
        gate_threshold: float = 0.30,
        balance_target: float = 0.25,
        gate_temperature: float = 10.0,
        gain: float = 2.0,
        temporal_window: int = 3,
        vital_momentum_enabled: bool = True,
        vital_momentum_range: Tuple[float, float] = (0.5, 1.5),
    ):
        """
        Initialize the Kosha Gyroscopic Loss.

        Args:
            trap_threshold: Activation level above which a Kosha is "trapped"
            gate_threshold: Minimum activation for gate to be considered open
            balance_target: Target activation level for the opposite Kosha
            gate_temperature: Temperature for soft gate sigmoid (higher = sharper)
            gain: Base multiplier for the loss
            temporal_window: Number of tokens to average for Physical history
            vital_momentum_enabled: Whether to use Vital for dynamic gain
            vital_momentum_range: (min, max) range for momentum scaler
        """
        super().__init__()
        self.trap_threshold = trap_threshold
        self.gate_threshold = gate_threshold
        self.balance_target = balance_target
        self.gate_temperature = gate_temperature
        self.gain = gain
        self.temporal_window = temporal_window
        self.vital_momentum_enabled = vital_momentum_enabled
        self.vital_min, self.vital_max = vital_momentum_range

        # Kosha indices in the 5D projection
        self.PHYSICAL_IDX = 0   # Annamaya (+,+)
        self.VITAL_IDX = 1      # Pranamaya (energy)
        self.MENTAL_IDX = 2     # Manomaya (-,+)
        self.INTELLECT_IDX = 3  # Vijnanamaya (+,-)
        self.BLISS_IDX = 4      # Anandamaya (-,-)

    def _compute_temporal_grounding(
        self,
        physical: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute temporally-smoothed Physical activation.

        Instead of checking physical[t] alone (volatile), we check the
        mean of the last N tokens to ensure stable grounding.

        Args:
            physical: [batch, seq] Physical Kosha activations

        Returns:
            [batch, seq] Temporally smoothed Physical activations
        """
        if physical.shape[1] < self.temporal_window:
            return physical

        # Use 1D average pooling for efficiency
        # Shape: [batch, seq] -> [batch, 1, seq] -> pool -> [batch, seq]
        phys_history = F.avg_pool1d(
            physical.unsqueeze(1),
            kernel_size=self.temporal_window,
            stride=1,
            padding=self.temporal_window // 2
        ).squeeze(1)

        # Handle edge case where output length differs
        if phys_history.shape[1] != physical.shape[1]:
            phys_history = phys_history[:, :physical.shape[1]]

        return phys_history

    def _compute_vital_momentum(
        self,
        vital: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute dynamic gain multiplier based on Vital (Pranamaya) energy.

        In Vedic theory, Prana is the energy that moves mind and matter.
        - Low Vital = Inertia/stagnation -> Increase gain (pull harder)
        - High Vital = Flow/momentum -> Decrease gain (subtle correction)

        Args:
            vital: [batch, seq] Vital Kosha activations

        Returns:
            Scalar momentum scaler in range [vital_min, vital_max]
        """
        if not self.vital_momentum_enabled:
            return torch.ones(1, device=vital.device)

        # Mean Vital across batch and sequence
        mean_vital = vital.mean()

        # Invert: Low Vital -> High gain, High Vital -> Low gain
        # Assuming Vital is normalized to [0, 1], we compute:
        # scaler = vital_max - (vital_max - vital_min) * mean_vital
        # This gives vital_max when mean_vital=0, vital_min when mean_vital=1
        momentum_scaler = self.vital_max - (self.vital_max - self.vital_min) * mean_vital

        return momentum_scaler

    def forward(
        self,
        kosha_states: torch.Tensor,
        return_components: bool = False
    ) -> torch.Tensor | Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Compute the Kosha Gyroscopic Loss.

        The loss fires when:
        1. A Kosha is "trapped" (above trap_threshold)
        2. The grounding gate is open (adjacent Kosha above gate_threshold)
        3. The diagonal opposite is missing (below balance_target)

        Args:
            kosha_states: [batch, seq, 5] Kosha activations normalized to [0, 1]
                         Indices: [Physical, Vital, Mental, Intellect, Blissful]
            return_components: If True, also return diagnostic components

        Returns:
            If return_components=False: Scalar loss value
            If return_components=True: (loss, components_dict)
        """
        # Extract individual Koshas
        physical = kosha_states[:, :, self.PHYSICAL_IDX]   # (+,+) Manifest, Past
        vital = kosha_states[:, :, self.VITAL_IDX]         # Energy/Momentum
        mental = kosha_states[:, :, self.MENTAL_IDX]       # (-,+) Unmanifest, Past
        intellect = kosha_states[:, :, self.INTELLECT_IDX] # (+,-) Manifest, Future
        bliss = kosha_states[:, :, self.BLISS_IDX]         # (-,-) Unmanifest, Future

        # === REFINEMENT 1: Temporal Grounding ===
        # Use Physical history, not just current token
        phys_history = self._compute_temporal_grounding(physical)

        # === REFINEMENT 2: Vital Momentum ===
        # Dynamic gain based on energy level
        momentum_scaler = self._compute_vital_momentum(vital)

        # --- AXIS 1: Mental -> Intellect (via Physical) ---
        # Transition path: Mental (loop) -> Physical (ground) -> Intellect (structure)
        #
        # This axis handles the "Titus Titus Titus" problem:
        # - High Mental = repetitive pattern detected
        # - Low Intellect = no logical structure justifying the pattern
        # - Physical Gate = check if model is grounded in manifest reality
        #
        # If Mental HIGH + Intellect LOW + Physical grounded -> PUNISH (break the loop)
        # If Mental HIGH + Intellect HIGH -> ALLOW (valid focus, Dharana)

        mental_trap = F.relu(mental - self.trap_threshold)
        phys_gate = torch.sigmoid(
            self.gate_temperature * (phys_history - self.gate_threshold)
        )
        missing_intellect = F.relu(self.balance_target - intellect)
        axis1_loss = (mental_trap * phys_gate * missing_intellect).mean()

        # --- AXIS 2: Physical -> Blissful (via Mental) ---
        # Transition path: Physical (inertia) -> Mental (abstraction) -> Bliss (expansion)
        #
        # This axis handles the "just copying tokens" problem:
        # - High Physical = raw data regurgitation
        # - Low Bliss = no creative expansion
        # - Mental Gate = check if model has abstracted the pattern
        #
        # If Physical HIGH + Bliss LOW + Mental abstracted -> PUNISH (force creativity)

        physical_trap = F.relu(physical - self.trap_threshold)
        mental_gate = torch.sigmoid(
            self.gate_temperature * (mental - self.gate_threshold)
        )
        missing_bliss = F.relu(self.balance_target - bliss)
        axis2_loss = (physical_trap * mental_gate * missing_bliss).mean()

        # === Total Loss with Dynamic Gain ===
        total_loss = (axis1_loss + axis2_loss) * self.gain * momentum_scaler

        if return_components:
            components = {
                'axis1_loss': axis1_loss.item(),
                'axis2_loss': axis2_loss.item(),
                'momentum_scaler': momentum_scaler.item() if torch.is_tensor(momentum_scaler) else momentum_scaler,
                'mental_trap_mean': mental_trap.mean().item(),
                'physical_trap_mean': physical_trap.mean().item(),
                'phys_gate_mean': phys_gate.mean().item(),
                'mental_gate_mean': mental_gate.mean().item(),
                'missing_intellect_mean': missing_intellect.mean().item(),
                'missing_bliss_mean': missing_bliss.mean().item(),
                'vital_mean': vital.mean().item(),
                'kosha_means': {
                    'physical': physical.mean().item(),
                    'vital': vital.mean().item(),
                    'mental': mental.mean().item(),
                    'intellect': intellect.mean().item(),
                    'bliss': bliss.mean().item(),
                }
            }
            return total_loss, components

        return total_loss

    def detect_insanity_state(
        self,
        kosha_states: torch.Tensor,
        mental_threshold: float = 0.8,
        intellect_threshold: float = 0.2
    ) -> torch.Tensor:
        """
        Detect "Insanity" state: High Mental + Low Intellect.

        This is the pathological loop state where the model is repeating
        patterns without intellectual justification.

        Args:
            kosha_states: [batch, seq, 5] Kosha activations
            mental_threshold: Mental activation above this is "high"
            intellect_threshold: Intellect activation below this is "low"

        Returns:
            [batch, seq] Boolean mask of insanity states
        """
        mental = kosha_states[:, :, self.MENTAL_IDX]
        intellect = kosha_states[:, :, self.INTELLECT_IDX]

        return (mental > mental_threshold) & (intellect < intellect_threshold)

    def detect_dharana_state(
        self,
        kosha_states: torch.Tensor,
        mental_threshold: float = 0.6,
        intellect_threshold: float = 0.4
    ) -> torch.Tensor:
        """
        Detect "Dharana" (focused concentration) state: High Mental + High Intellect.

        This is the valid focus state where repetition is justified by
        intellectual structure (e.g., Fibonacci, poetry).

        Args:
            kosha_states: [batch, seq, 5] Kosha activations
            mental_threshold: Mental activation above this is "high"
            intellect_threshold: Intellect activation above this is "high"

        Returns:
            [batch, seq] Boolean mask of Dharana states
        """
        mental = kosha_states[:, :, self.MENTAL_IDX]
        intellect = kosha_states[:, :, self.INTELLECT_IDX]

        return (mental > mental_threshold) & (intellect > intellect_threshold)


class InvertedCurriculumController:
    """
    Controller for the Inverted Curriculum paradigm.

    The Inverted Curriculum:
    - Phase 1 (Instructor-Led): Gyroscope ON, Classification OFF (PPL > 30)
    - Phase 2 (Self-Learning): Gyroscope OFF, Classification ON (PPL < 30)

    The Gyroscope is the "instructor" that teaches balance from step 0.
    Once the model is fluent (PPL < 30), it "graduates" and self-regulates.
    """

    def __init__(
        self,
        config: KoshaGyroscopeConfig,
    ):
        """
        Initialize the curriculum controller.

        Args:
            config: Gyroscope configuration
        """
        self.config = config
        self.gyroscope_active = config.enable_gyroscope
        self.classification_active = config.enable_kosha_classification
        self.disengage_step: Optional[int] = None
        self.graduated = False

    def check_graduation(
        self,
        val_ppl: float,
        global_step: int
    ) -> bool:
        """
        Check if the model should graduate from instructor-led to self-learning.

        Args:
            val_ppl: Current validation perplexity
            global_step: Current training step

        Returns:
            True if graduation just occurred
        """
        if self.graduated:
            return False

        if self.gyroscope_active and val_ppl < self.config.gyroscope_disengage_ppl:
            self.disengage_step = global_step
            self.classification_active = True
            self.graduated = True
            return True

        return False

    def get_gyroscope_scale(self, global_step: int) -> float:
        """
        Get the current scaling factor for the gyroscope loss.

        Handles warmup at start and rampdown at graduation.

        Args:
            global_step: Current training step

        Returns:
            Scale factor in [0, 1]
        """
        if not self.gyroscope_active:
            return 0.0

        # Warmup scaling
        warmup_scale = min(1.0, global_step / self.config.gyroscope_warmup_steps)

        # Rampdown scaling after disengage
        if self.disengage_step is not None:
            steps_since_disengage = global_step - self.disengage_step
            rampdown_scale = max(
                0.0,
                1.0 - steps_since_disengage / self.config.gain_rampdown_steps
            )
            if rampdown_scale <= 0.0:
                self.gyroscope_active = False
        else:
            rampdown_scale = 1.0

        return warmup_scale * rampdown_scale

    def get_status(self) -> Dict[str, Any]:
        """Get current curriculum status for logging."""
        return {
            'gyroscope_active': self.gyroscope_active,
            'classification_active': self.classification_active,
            'graduated': self.graduated,
            'disengage_step': self.disengage_step,
        }
