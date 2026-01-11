"""
Kosha Gyroscope: Homeostatic Self-Regulation Loss Module (v2.2.4)

This module implements the Vijnana-Gated Kosha Balance Loss, a homeostatic
self-regulation mechanism that prevents pathological states (looping, fixation,
mode collapse) by enforcing balance across the 5 Kosha (sheath) dimensions.

Key Features (v2.2.4 - Three-Stage Hybrid Logic):
- Bliss Damper (Sigmoid): Dilutes creative expansion during Mental dominance
- Physical Gate (Strict): Prerequisites for Intellectual activation (no bypass)
- Hard ReLU Rip: Reality Reversal when trapped with gate closed
- Two-Path Loss: intellect_path + rip_signal for distinct behaviors

v2.2.4 "Pressure Relief Valve" Architecture:
- Damping manages the "volume" of Mental state
- Ripping acts as "pressure relief valve" forcing hard shift to Physical grounding
- Model cannot "reason" in a vacuum - must be grounded in manifest data first

Three-Stage Internal Process:
1. Mental Dominance (Damper): High Mental → Blissful activation diluted
2. Physical Gate (Prerequisite): Intellect blocked unless Physical history saturated
3. Reality Rip (Reversal): Trap + Gate Closed → ReLU shock forces re-grounding

Previous Versions:
- v2.2.3.1: Soft-threshold damping (gate bypass approach - deprecated)
- v2.2.1: Dynamic Weight Scheduler (PPL-based gain ramping - retained)

R-T Quadrant Geometry:
- Physical  (+,+): Manifest, Past
- Mental    (-,+): Unmanifest, Past
- Intellect (+,-): Manifest, Future
- Blissful  (-,-): Unmanifest, Future
- Vital: Energy/Momentum (not mapped to quadrant)

References:
- docs/design/KOSHA_GYROSCOPE_DESIGN.md v2.2.4
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
    """Configuration for Kosha Gyroscope with Inverted Curriculum (v2.2.4).

    The Inverted Curriculum paradigm:
    - Gyroscope: Active from start, disengages when fluent (PPL < 30)
    - Classification: Disabled at start, engages when fluent (PPL < 30)

    v2.2.4 Three-Stage Hybrid Logic:
    1. Bliss Damper (Sigmoid): Dilutes creative expansion during Mental dominance
    2. Physical Gate (Strict): Intellect requires Physical grounding (no bypass!)
    3. Hard ReLU Rip: Reality Reversal when trapped + gate closed

    v2.2.1 Dynamic Weight Scheduler retained for PPL-based gain ramping.
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

    # === THREE-STAGE HYBRID LOGIC (v2.2.4) ===
    # Damper steepness controls how aggressively Bliss is diluted
    damper_steepness: float = 5.0        # Sigmoid steepness for bliss damper
    # Gate steepness controls how sharp the Physical gate transition is
    gate_steepness: float = 5.0          # Sigmoid steepness for gate
    # Rip multiplier for Reality Reversal (hard shock when trapped + gate closed)
    rip_multiplier: float = 2.0          # Multiplier for rip_signal loss

    # Legacy: steepness (deprecated in v2.2.4, split into damper/gate steepness)
    steepness: float = 5.0               # Kept for backward compatibility

    # === DYNAMIC WEIGHT SCHEDULER (v2.2.1) ===
    base_gain: float = 0.15              # Gentle observation (PPL > 100)
    max_gain: float = 3.0                # Strict enforcement (PPL -> 30)
    ppl_ceiling: float = 100.0           # PPL above which gain stays at base
    target_ppl: float = 30.0             # PPL at which gain reaches max

    # Legacy: Static gain (deprecated, use base_gain/max_gain instead)
    gain: float = 2.0                    # Fallback if dynamic gain disabled
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
    Vijnana-Gated Kosha Balance Loss (v2.2.4) - Three-Stage Hybrid Logic.

    Implements homeostatic regulation with the "Pressure Relief Valve" architecture:
    1. Bliss Damper (Sigmoid): Dilutes Bliss during Mental dominance
    2. Physical Gate (Strict): Prerequisites for Intellect (no bypass!)
    3. Hard ReLU Rip: Reality Reversal on pathological loops

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

    v2.2.4 Three-Stage Internal Process:

    Stage 1 - BLISS DAMPER (Mental Dominance Regulation):
        As Manomaya (Mental) increases, Anandamaya (Bliss) is mathematically diluted.
        This prevents the model from "hallucinating" or jumping to creative tangents
        while caught in a pattern loop.
        Formula: bliss_damper = 1.0 - sigmoid((mental - threshold) * steepness)

    Stage 2 - PHYSICAL GATE (Intellectual Prerequisite):
        Unlike v2.2.3.1's bypass approach, the gate is now a STRICT requirement.
        Intellect remains "starved" of gradient flow unless Physical history is active.
        This stops "fake reasoning" - model learns that expressing structure
        requires providing factual grounding first.
        Formula: phys_gate = sigmoid((phys_history - threshold) * steepness)

    Stage 3 - REALITY RIP (Hard Reversal):
        If model stays in high-Mental state without Physical gate opening,
        the ReLU Rip fires. This creates a discontinuous gradient "shock"
        that smashes the current latent trajectory and forces re-grounding.
        Formula: rip_signal = mental_trap * (1.0 - phys_gate)

    Two-Path Loss Architecture:
        - intellect_path: Flows when gate is OPEN (grounded reasoning)
        - rip_signal: Fires when gate is CLOSED (reality reversal)
        Combined: axis1_loss = (intellect_path + rip_signal * rip_multiplier).mean()

    Dynamic Weight Scheduler (v2.2.1 - retained):
    - Phase A (PPL > 100): Gentle observation at base_gain (0.15)
    - Phase B (PPL 100 -> 30): Linear ramp to max_gain (3.0)
    - Phase C (PPL < 30): Gyroscope disengages, gain ramps to 0
    """

    def __init__(
        self,
        trap_threshold: float = 0.75,
        gate_threshold: float = 0.30,
        balance_target: float = 0.25,
        gate_temperature: float = 10.0,
        # Three-Stage Hybrid Logic (v2.2.4)
        damper_steepness: float = 5.0,
        gate_steepness: float = 5.0,
        rip_multiplier: float = 2.0,
        # Legacy: steepness (deprecated, use damper_steepness/gate_steepness)
        steepness: float = 5.0,
        # Dynamic Weight Scheduler (v2.2.1)
        base_gain: float = 0.15,
        max_gain: float = 3.0,
        ppl_ceiling: float = 100.0,
        target_ppl: float = 30.0,
        # Legacy static gain (fallback)
        gain: Optional[float] = None,
        # Refinements
        temporal_window: int = 3,
        vital_momentum_enabled: bool = True,
        vital_momentum_range: Tuple[float, float] = (0.5, 1.5),
    ):
        """
        Initialize the Kosha Gyroscopic Loss (v2.2.4).

        Args:
            trap_threshold: Activation level above which a Kosha is "trapped"
            gate_threshold: Minimum activation for gate to be considered open
            balance_target: Target activation level for the opposite Kosha
            gate_temperature: Temperature for soft gate sigmoid (higher = sharper)
            damper_steepness: Sigmoid steepness for Bliss damper (v2.2.4)
                              Controls how aggressively Bliss is diluted during Mental dominance
            gate_steepness: Sigmoid steepness for Physical gate (v2.2.4)
                            Controls sharpness of the grounding prerequisite
            rip_multiplier: Multiplier for Reality Rip signal (v2.2.4)
                            Higher = stronger "circuit breaker" effect
            steepness: Legacy parameter (deprecated, use damper_steepness/gate_steepness)
            base_gain: Starting gain when PPL > ppl_ceiling (gentle observation)
            max_gain: Maximum gain when PPL approaches target_ppl (strict enforcement)
            ppl_ceiling: PPL above which gain stays at base_gain
            target_ppl: PPL at which gain reaches max_gain
            gain: Legacy static gain (deprecated, use base_gain/max_gain)
            temporal_window: Number of tokens to average for Physical history
            vital_momentum_enabled: Whether to use Vital for dynamic gain
            vital_momentum_range: (min, max) range for momentum scaler
        """
        super().__init__()
        self.trap_threshold = trap_threshold
        self.gate_threshold = gate_threshold
        self.balance_target = balance_target
        self.gate_temperature = gate_temperature

        # Three-Stage Hybrid Logic (v2.2.4)
        self.damper_steepness = damper_steepness
        self.gate_steepness = gate_steepness
        self.rip_multiplier = rip_multiplier

        # Legacy: steepness (fallback for backward compatibility)
        self.steepness = steepness

        # Dynamic Weight Scheduler (v2.2.1)
        self.base_gain = base_gain
        self.max_gain = max_gain
        self.ppl_ceiling = ppl_ceiling
        self.target_ppl = target_ppl

        # Legacy fallback
        self._static_gain = gain if gain is not None else base_gain

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

    def _soft_threshold(
        self,
        x: torch.Tensor,
        threshold: float
    ) -> torch.Tensor:
        """
        Soft threshold with shifted sigmoid (v2.2.3.1).

        Provides smooth transition at threshold while preserving "clean zero"
        property below threshold. Unlike raw sigmoid which outputs ~0.5 at
        threshold and never reaches 0, this shifted version:
        - Outputs 0 when x <= threshold
        - Smoothly ramps to 1.0 as x exceeds threshold
        - Has continuous gradients everywhere (no "Reality Rips")

        The shift maps sigmoid(0) -> 0 instead of sigmoid(0) -> 0.5:
            shifted = clamp(2.0 * (sigmoid(z) - 0.5), min=0)

        Args:
            x: Input tensor of activations
            threshold: Activation level to detect crossing

        Returns:
            Soft threshold output in range [0, 1]
        """
        z = (x - threshold) * self.steepness
        raw_sigmoid = torch.sigmoid(z)
        # Shift: sigmoid(0)=0.5 -> 0, sigmoid(inf)=1.0 -> 1.0
        # clamp ensures we don't go negative when x << threshold
        return torch.clamp(2.0 * (raw_sigmoid - 0.5), min=0.0)

    def _soft_deficit(
        self,
        x: torch.Tensor,
        target: float
    ) -> torch.Tensor:
        """
        Soft deficit detection with shifted sigmoid (v2.2.3.1).

        Detects how far below target an activation is, with smooth transitions.
        Like _soft_threshold but inverted:
        - Outputs 0 when x >= target (no deficit)
        - Smoothly ramps to 1.0 as x falls below target
        - Has continuous gradients everywhere

        Args:
            x: Input tensor of activations
            target: Target activation level

        Returns:
            Soft deficit output in range [0, 1]
        """
        z = (target - x) * self.steepness
        raw_sigmoid = torch.sigmoid(z)
        return torch.clamp(2.0 * (raw_sigmoid - 0.5), min=0.0)

    def get_dynamic_gain(self, current_ppl: Optional[float] = None) -> float:
        """
        Compute dynamic gain based on current PPL (v2.2.1).

        The gain ramps from base_gain to max_gain as PPL drops from
        ppl_ceiling to target_ppl. This prevents "Aphasia" (model afraid
        to repeat valid tokens) during early training.

        Phase A (PPL > 100): Gentle observation at base_gain
        Phase B (PPL 100 -> 30): Linear ramp to max_gain
        Phase C (PPL < 30): Gain at max (but gyroscope should be disengaging)

        Args:
            current_ppl: Current validation perplexity. If None, returns base_gain.

        Returns:
            Dynamic gain value in range [base_gain, max_gain]
        """
        if current_ppl is None:
            return self._static_gain

        if current_ppl >= self.ppl_ceiling:
            return self.base_gain

        # Linear interpolation from base_gain to max_gain
        # as PPL drops from ppl_ceiling to target_ppl
        progress = (self.ppl_ceiling - current_ppl) / (self.ppl_ceiling - self.target_ppl)
        progress = max(0.0, min(1.0, progress))

        return self.base_gain + (progress * (self.max_gain - self.base_gain))

    def forward(
        self,
        kosha_states: torch.Tensor,
        current_ppl: Optional[float] = None,
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
            current_ppl: Current validation PPL for dynamic gain (v2.2.1).
                        If None, uses static fallback gain.
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

        # =======================================================================
        # AXIS 1: Mental -> Intellect (via Physical) - v2.2.4 Three-Stage Hybrid
        # =======================================================================
        #
        # This axis handles the "Titus Titus Titus" problem with three mechanisms:
        #
        # STAGE 1 - BLISS DAMPER (Mental Dominance Regulation):
        #   As Mental increases, Bliss is mathematically diluted.
        #   Prevents "hallucinating" or jumping to creative tangents during loops.
        #
        # STAGE 2 - PHYSICAL GATE (Intellectual Prerequisite):
        #   Intellect is "starved" unless Physical history is active.
        #   This is STRICT - no bypass! Model must ground before reasoning.
        #
        # STAGE 3 - REALITY RIP (Hard Reversal):
        #   If trapped + gate closed → ReLU shock forces re-grounding.
        #   This "smashes" the loop trajectory back to Physical quadrant.

        # Stage 1: BLISS DAMPER - dilutes creative expansion during Mental dominance
        # When Mental > threshold, bliss_damper approaches 0, diluting Bliss influence
        bliss_damper = 1.0 - torch.sigmoid((mental - self.trap_threshold) * self.damper_steepness)

        # Stage 2: PHYSICAL GATE - strict prerequisite for Intellect (NO BYPASS!)
        # Gate only opens when Physical history is above threshold
        phys_gate = torch.sigmoid((phys_history - self.gate_threshold) * self.gate_steepness)

        # Stage 3: REALITY RIP - Hard ReLU for "circuit breaker" effect
        # Uses ReLU (not sigmoid) for discontinuous gradient shock
        mental_trap = F.relu(mental - self.trap_threshold)

        # Rip signal fires when trapped AND gate is CLOSED
        # This forces model back to Physical/Manifest quadrant
        rip_signal = mental_trap * (1.0 - phys_gate)

        # Intellectual path - only flows when gate is OPEN (grounded reasoning)
        missing_intellect = F.relu(self.balance_target - intellect)
        intellect_path = mental_trap * phys_gate * missing_intellect

        # TWO-PATH LOSS: Grounded path + Reality reversal
        # rip_signal gets multiplied by rip_multiplier for stronger "shock"
        axis1_loss = (intellect_path + rip_signal * self.rip_multiplier).mean()

        # =======================================================================
        # AXIS 2: Physical -> Blissful (via Mental) - v2.2.4 Three-Stage Hybrid
        # =======================================================================
        #
        # This axis handles the "just copying tokens" problem symmetrically:
        # - High Physical = raw data regurgitation
        # - Low Bliss = no creative expansion
        # - Mental Gate = check if model has abstracted the pattern
        #
        # Same three-stage logic applied to Physical → Bliss transition

        # Stage 1: PHYSICAL DAMPER - dilutes grounding during Physical dominance
        # (Prevents over-grounding that blocks creativity)
        physical_damper = 1.0 - torch.sigmoid((physical - self.trap_threshold) * self.damper_steepness)

        # Stage 2: MENTAL GATE - strict prerequisite for Bliss (NO BYPASS!)
        mental_gate = torch.sigmoid((mental - self.gate_threshold) * self.gate_steepness)

        # Stage 3: REALITY RIP - Hard ReLU for Physical trap
        physical_trap = F.relu(physical - self.trap_threshold)

        # Rip signal fires when physically trapped AND mental gate is CLOSED
        rip_signal_axis2 = physical_trap * (1.0 - mental_gate)

        # Bliss path - only flows when mental gate is OPEN (abstracted)
        missing_bliss = F.relu(self.balance_target - bliss)
        bliss_path = physical_trap * mental_gate * missing_bliss

        # TWO-PATH LOSS: Abstracted path + Reality reversal
        axis2_loss = (bliss_path + rip_signal_axis2 * self.rip_multiplier).mean()

        # === Total Loss with Dynamic Gain (v2.2.1) ===
        # Get PPL-based dynamic gain
        effective_gain = self.get_dynamic_gain(current_ppl)
        total_loss = (axis1_loss + axis2_loss) * effective_gain * momentum_scaler

        if return_components:
            # v2.2.4: Compute diagnostic metrics for Three-Stage Hybrid Logic

            # Rip signal metrics (Reality Reversal detection)
            rip_signal_mean = rip_signal.mean().item()
            rip_signal_max = rip_signal.max().item()
            rip_signal_axis2_mean = rip_signal_axis2.mean().item()

            # Damper metrics (Mental/Physical dominance regulation)
            bliss_damper_mean = bliss_damper.mean().item()
            physical_damper_mean = physical_damper.mean().item()

            # Gate-locked detection (trapped with gate closed)
            gate_locked_axis1 = ((mental_trap > 0) & (phys_gate < 0.5)).float().mean().item()
            gate_locked_axis2 = ((physical_trap > 0) & (mental_gate < 0.5)).float().mean().item()

            # Path flow metrics (which path is active)
            intellect_path_mean = intellect_path.mean().item()
            bliss_path_mean = bliss_path.mean().item()

            components = {
                # Loss breakdown
                'axis1_loss': axis1_loss.item(),
                'axis2_loss': axis2_loss.item(),
                'effective_gain': effective_gain,
                'current_ppl': current_ppl,
                'momentum_scaler': momentum_scaler.item() if torch.is_tensor(momentum_scaler) else momentum_scaler,

                # v2.2.4 THREE-STAGE HYBRID METRICS
                # Stage 1: Damper metrics
                'bliss_damper_mean': bliss_damper_mean,
                'physical_damper_mean': physical_damper_mean,

                # Stage 2: Gate metrics (strict, no bypass)
                'phys_gate_mean': phys_gate.mean().item(),
                'mental_gate_mean': mental_gate.mean().item(),

                # Stage 3: Rip signal metrics (Reality Reversal)
                'rip_signal_mean': rip_signal_mean,
                'rip_signal_max': rip_signal_max,
                'rip_signal_axis2_mean': rip_signal_axis2_mean,

                # Gate-locked states (trapped + gate closed = RIP firing)
                'gate_locked_axis1': gate_locked_axis1,
                'gate_locked_axis2': gate_locked_axis2,

                # Path flow (grounded vs reversal)
                'intellect_path_mean': intellect_path_mean,
                'bliss_path_mean': bliss_path_mean,

                # Trap detection (ReLU-based)
                'mental_trap_mean': mental_trap.mean().item(),
                'physical_trap_mean': physical_trap.mean().item(),

                # Target deficit
                'missing_intellect_mean': missing_intellect.mean().item(),
                'missing_bliss_mean': missing_bliss.mean().item(),

                # Energy level
                'vital_mean': vital.mean().item(),

                # v2.2.4 config
                'damper_steepness': self.damper_steepness,
                'gate_steepness': self.gate_steepness,
                'rip_multiplier': self.rip_multiplier,

                # Kosha state summary
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


# =============================================================================
# Kosha-Vritti Resonance Loss (v2.3.0)
# =============================================================================

@dataclass
class VrittiResonanceConfig:
    """Configuration for Vritti Resonance Loss (Phase 2 only).

    The Kosha-Vritti Mapping Matrix:
    - Annamaya (Physical)   -> Pramana (Right Knowledge)
    - Pranamaya (Vital)     -> Nidra (Sleep/Inertia)
    - Manomaya (Mental)     -> Vikalpa (Imagination)
    - Vijnanamaya (Intellect) -> Smriti (Memory)
    - Anandamaya (Bliss)    -> Viparyaya (Misconception)
    """

    # Enable/disable individual resonance violations
    enable_pramana_physical: bool = True   # Right Knowledge needs Physical grounding
    enable_smriti_intellect: bool = True   # Memory needs Intellect validation
    enable_vikalpa_mental: bool = True     # Imagination needs Mental activity
    enable_viparyaya_bliss: bool = True    # Misconception tracks ungrounded Bliss
    enable_nidra_vital: bool = True        # Sleep tracks Vital depletion

    # Loss weighting
    resonance_lambda: float = 0.1          # Weight for total resonance loss
    pramana_weight: float = 1.0
    smriti_weight: float = 1.0
    vikalpa_weight: float = 1.0
    viparyaya_weight: float = 0.5          # Lower weight - creative expansion is OK
    nidra_weight: float = 0.5              # Lower weight - energy management

    # Phase 2 only - don't activate until graduation
    require_graduation: bool = True


class VrittiResonanceLoss(nn.Module):
    """
    Kosha-Vritti Resonance Loss (v2.3.0).

    Ensures emergent Vrittis are properly anchored to their primary Koshas.
    This prevents the model from "mislabeling" its internal state—for example,
    claiming Pramana (Right Knowledge) while actually in Vikalpa (Imagination Loop).

    The Kosha-Vritti Mapping:
    - Physical (Annamaya)   -> Pramana (Right Knowledge)
    - Vital (Pranamaya)     -> Nidra (Sleep/Inertia) [inverse]
    - Mental (Manomaya)     -> Vikalpa (Imagination)
    - Intellect (Vijnanamaya) -> Smriti (Memory/Recall)
    - Bliss (Anandamaya)    -> Viparyaya (Misconception)

    Phase Integration:
    - Phase 1 (PPL > 30): DISABLED (read-only logging)
    - Phase 2 (PPL < 30): ACTIVE with resonance_lambda weight

    Reference: docs/design/KOSHA_GYROSCOPE_DESIGN.md Section 12
    """

    # Kosha indices (from 32D sovereign state [12:17])
    PHYSICAL_IDX = 0    # Annamaya
    VITAL_IDX = 1       # Pranamaya
    MENTAL_IDX = 2      # Manomaya
    INTELLECT_IDX = 3   # Vijnanamaya
    BLISS_IDX = 4       # Anandamaya

    # Vritti indices (from 32D sovereign state [17:22])
    PRAMANA_IDX = 0     # Right Knowledge
    VIPARYAYA_IDX = 1   # Misconception
    VIKALPA_IDX = 2     # Imagination
    NIDRA_IDX = 3       # Sleep
    SMRITI_IDX = 4      # Memory

    def __init__(
        self,
        config: Optional[VrittiResonanceConfig] = None,
        resonance_lambda: float = 0.1,
    ):
        """
        Initialize Vritti Resonance Loss.

        Args:
            config: Full configuration (overrides other args)
            resonance_lambda: Weight for resonance loss (if config not provided)
        """
        super().__init__()

        if config is not None:
            self.config = config
        else:
            self.config = VrittiResonanceConfig(resonance_lambda=resonance_lambda)

        self.active = not self.config.require_graduation  # Start inactive if Phase 2 only

    def activate(self):
        """Activate resonance loss (called at graduation)."""
        self.active = True

    def forward(
        self,
        kosha_states: torch.Tensor,
        vritti_states: torch.Tensor,
        return_components: bool = False
    ) -> torch.Tensor | Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Compute Vritti Resonance Loss.

        Penalizes misalignment between Kosha activation and Vritti emergence.

        Args:
            kosha_states: [B, N, 5] or [B, 5] Kosha activations
            vritti_states: [B, N, 5] or [B, 5] Vritti probabilities
            return_components: If True, return diagnostic breakdown

        Returns:
            Scalar loss (0 if not active) or (loss, components_dict)
        """
        if not self.active:
            if return_components:
                return torch.tensor(0.0, device=kosha_states.device), {'active': False}
            return torch.tensor(0.0, device=kosha_states.device)

        # Handle both 2D and 3D tensors
        if kosha_states.dim() == 2:
            kosha_states = kosha_states.unsqueeze(1)
        if vritti_states.dim() == 2:
            vritti_states = vritti_states.unsqueeze(1)

        # Extract Kosha dimensions
        physical = kosha_states[..., self.PHYSICAL_IDX]
        vital = kosha_states[..., self.VITAL_IDX]
        mental = kosha_states[..., self.MENTAL_IDX]
        intellect = kosha_states[..., self.INTELLECT_IDX]
        bliss = kosha_states[..., self.BLISS_IDX]

        # Extract Vritti dimensions
        pramana = vritti_states[..., self.PRAMANA_IDX]
        viparyaya = vritti_states[..., self.VIPARYAYA_IDX]
        vikalpa = vritti_states[..., self.VIKALPA_IDX]
        nidra = vritti_states[..., self.NIDRA_IDX]
        smriti = vritti_states[..., self.SMRITI_IDX]

        components = {'active': True}
        total_loss = torch.tensor(0.0, device=kosha_states.device)

        # === RESONANCE VIOLATIONS ===

        # 1. Pramana (Right Knowledge) requires Physical grounding
        #    Can't claim "Right Knowledge" without manifest data
        if self.config.enable_pramana_physical:
            pramana_violation = F.relu(pramana - physical).mean()
            total_loss = total_loss + self.config.pramana_weight * pramana_violation
            components['pramana_physical'] = pramana_violation.item()

        # 2. Smriti (Memory) requires Intellect validation
        #    Memory/recall needs logical structure
        if self.config.enable_smriti_intellect:
            smriti_violation = F.relu(smriti - intellect).mean()
            total_loss = total_loss + self.config.smriti_weight * smriti_violation
            components['smriti_intellect'] = smriti_violation.item()

        # 3. Vikalpa (Imagination) should track Mental
        #    Imagination without mental activity is incoherent
        if self.config.enable_vikalpa_mental:
            vikalpa_violation = F.relu(vikalpa - mental).mean()
            total_loss = total_loss + self.config.vikalpa_weight * vikalpa_violation
            components['vikalpa_mental'] = vikalpa_violation.item()

        # 4. Viparyaya (Misconception) tracks ungrounded Bliss
        #    Misconception = Bliss expanding without Physical anchor
        if self.config.enable_viparyaya_bliss:
            # Two conditions: Viparyaya without Bliss, OR Viparyaya with Physical (grounded != misconception)
            viparyaya_violation = (
                F.relu(viparyaya - bliss).mean() +
                F.relu(viparyaya * physical).mean()  # Penalize grounded misconception
            )
            total_loss = total_loss + self.config.viparyaya_weight * viparyaya_violation
            components['viparyaya_bliss'] = viparyaya_violation.item()

        # 5. Nidra (Sleep) tracks Vital depletion (inverse relationship)
        #    High Nidra + High Vital = violation (should be shutting down)
        if self.config.enable_nidra_vital:
            nidra_violation = F.relu(nidra * vital).mean()
            total_loss = total_loss + self.config.nidra_weight * nidra_violation
            components['nidra_vital'] = nidra_violation.item()

        # Apply lambda scaling
        total_loss = total_loss * self.config.resonance_lambda
        components['total_loss'] = total_loss.item()

        if return_components:
            return total_loss, components
        return total_loss

    def compute_alignment_scores(
        self,
        kosha_states: torch.Tensor,
        vritti_states: torch.Tensor
    ) -> Dict[str, float]:
        """
        Compute Kosha-Vritti alignment scores for diagnostic logging.

        Returns alignment in [0, 1] where 1 = perfect alignment.
        This is the inverse of violation - high alignment = low violation.

        Args:
            kosha_states: [B, N, 5] or [B, 5] Kosha activations
            vritti_states: [B, N, 5] or [B, 5] Vritti probabilities

        Returns:
            Dict of alignment scores for each Kosha-Vritti pair
        """
        # Handle both 2D and 3D tensors
        if kosha_states.dim() == 2:
            kosha_states = kosha_states.unsqueeze(1)
        if vritti_states.dim() == 2:
            vritti_states = vritti_states.unsqueeze(1)

        # Extract dimensions
        physical = kosha_states[..., self.PHYSICAL_IDX]
        vital = kosha_states[..., self.VITAL_IDX]
        mental = kosha_states[..., self.MENTAL_IDX]
        intellect = kosha_states[..., self.INTELLECT_IDX]
        bliss = kosha_states[..., self.BLISS_IDX]

        pramana = vritti_states[..., self.PRAMANA_IDX]
        viparyaya = vritti_states[..., self.VIPARYAYA_IDX]
        vikalpa = vritti_states[..., self.VIKALPA_IDX]
        nidra = vritti_states[..., self.NIDRA_IDX]
        smriti = vritti_states[..., self.SMRITI_IDX]

        # Compute correlations (alignment scores)
        # Higher correlation = better alignment
        def correlation(a: torch.Tensor, b: torch.Tensor) -> float:
            a_flat = a.flatten()
            b_flat = b.flatten()
            if a_flat.std() < 1e-6 or b_flat.std() < 1e-6:
                return 0.0
            corr = torch.corrcoef(torch.stack([a_flat, b_flat]))[0, 1]
            return corr.item() if not torch.isnan(corr) else 0.0

        return {
            'physical_pramana': correlation(physical, pramana),
            'mental_vikalpa': correlation(mental, vikalpa),
            'intellect_smriti': correlation(intellect, smriti),
            'bliss_viparyaya': correlation(bliss, viparyaya),
            'vital_nidra_inv': -correlation(vital, nidra),  # Inverse relationship
        }


# =============================================================================
# Kosha Phase Corrector (Inference-Time Guardrail) - v2.4.0
# =============================================================================

@dataclass
class KoshaPhaseCorrectorConfig:
    """Configuration for inference-time Kosha Phase Correction.

    This module provides DIRECT phase rotation during inference to prevent
    stuck states when no gradient-based learning is available.

    Philosophy:
    - Training: Indirect (loss gradients) → Model LEARNS balance
    - Inference: Direct (phase rotation) → Runtime GUARDRAILS

    Reference: docs/design/KOSHA_GYROSCOPE_DESIGN.md Section 13
    """

    # Imbalance detection thresholds
    overactive_threshold: float = 0.75   # Kosha > this triggers correction
    underactive_threshold: float = 0.15  # Kosha < this is considered deficient

    # Correction strength
    correction_strength: float = 0.3     # How much to rotate (0-1)
    max_correction_per_step: float = 0.2 # Maximum change per inference step

    # Target equilibrium (balanced Kosha distribution)
    equilibrium_target: float = 0.2      # Ideal per-Kosha activation (1/5)

    # Enable/disable specific corrections
    enable_mental_correction: bool = True    # Prevent Vikalpa loops
    enable_bliss_correction: bool = True     # Prevent Viparyaya drift
    enable_vital_correction: bool = True     # Prevent Nidra collapse
    enable_physical_correction: bool = True  # Prevent Pramana over-grounding
    enable_intellect_correction: bool = True # Prevent Smriti over-recall

    # Diagonal pathway corrections (from Gyroscope design)
    enable_diagonal_mental_intellect: bool = True  # Mental → Intellect via Physical
    enable_diagonal_physical_bliss: bool = True    # Physical → Bliss via Mental


class KoshaPhaseCorrector(nn.Module):
    """
    Kosha Phase Corrector - Inference-Time Direct Phase Rotation.

    Unlike the KoshaGyroscopicLoss (which provides training gradients), this
    module DIRECTLY rotates the phase/state during inference to prevent stuck
    states.

    When a Kosha becomes overactive during generation, this module:
    1. Detects the imbalance
    2. Computes corrective rotation vector
    3. Applies rotation directly to sovereign state
    4. Logs the intervention for diagnostics

    This is the "guardrail on the cliff" - it doesn't teach driving,
    but prevents falling off during deployment.

    Reference: docs/design/KOSHA_GYROSCOPE_DESIGN.md Section 13
    """

    # Kosha indices (from 32D sovereign state [12:17])
    KOSHA_SLICE = slice(12, 17)
    PHYSICAL_IDX = 12   # Annamaya
    VITAL_IDX = 13      # Pranamaya
    MENTAL_IDX = 14     # Manomaya
    INTELLECT_IDX = 15  # Vijnanamaya
    BLISS_IDX = 16      # Anandamaya

    # Kosha names for diagnostics
    KOSHA_NAMES = ['Physical', 'Vital', 'Mental', 'Intellect', 'Bliss']

    def __init__(
        self,
        config: Optional[KoshaPhaseCorrectorConfig] = None,
    ):
        """
        Initialize Kosha Phase Corrector.

        Args:
            config: Configuration for correction behavior
        """
        super().__init__()
        self.config = config or KoshaPhaseCorrectorConfig()

        # Correction statistics for diagnostics
        self.correction_count = 0
        self.last_correction: Optional[Dict[str, Any]] = None

        # Build rotation matrices for each Kosha transition
        # These define "where to rotate TO" when a Kosha is overactive
        self._build_rotation_targets()

    def _build_rotation_targets(self):
        """
        Build target rotation vectors for each overactive Kosha.

        When Kosha X is overactive, rotate toward its diagonal complement:
        - Mental (overactive) → boost Intellect (via Physical gate)
        - Physical (overactive) → boost Bliss (via Mental gate)
        - Bliss (overactive) → boost Physical (grounding)
        - Vital (overactive) → allow Nidra (shutdown is OK)
        - Intellect (overactive) → boost Mental (creativity)
        """
        # Target distribution when specific Kosha is overactive
        # Format: [Physical, Vital, Mental, Intellect, Bliss]
        self.rotation_targets = {
            'Physical': torch.tensor([0.15, 0.20, 0.25, 0.20, 0.20]),   # → Bliss/Mental
            'Vital': torch.tensor([0.20, 0.15, 0.20, 0.25, 0.20]),      # → Intellect
            'Mental': torch.tensor([0.25, 0.15, 0.15, 0.30, 0.15]),     # → Intellect (priority)
            'Intellect': torch.tensor([0.20, 0.20, 0.25, 0.15, 0.20]),  # → Mental
            'Bliss': torch.tensor([0.30, 0.15, 0.20, 0.20, 0.15]),      # → Physical (grounding)
        }

    def detect_imbalance(
        self,
        kosha_states: torch.Tensor,
    ) -> Tuple[bool, Optional[str], Dict[str, float]]:
        """
        Detect if any Kosha is overactive.

        Args:
            kosha_states: [B, 5] or [B, N, 5] Kosha activations

        Returns:
            is_imbalanced: Whether correction is needed
            overactive_kosha: Name of overactive Kosha (or None)
            kosha_values: Dict of current Kosha values
        """
        # Handle 3D input
        if kosha_states.dim() == 3:
            kosha_states = kosha_states.mean(dim=1)  # Average over sequence

        # Average over batch
        avg_koshas = kosha_states.mean(dim=0)  # [5]

        kosha_values = {
            name: avg_koshas[i].item()
            for i, name in enumerate(self.KOSHA_NAMES)
        }

        # Find overactive Kosha
        overactive_kosha = None
        max_activation = 0.0

        for i, name in enumerate(self.KOSHA_NAMES):
            activation = avg_koshas[i].item()
            if activation > self.config.overactive_threshold:
                if activation > max_activation:
                    max_activation = activation
                    overactive_kosha = name

        is_imbalanced = overactive_kosha is not None

        return is_imbalanced, overactive_kosha, kosha_values

    def compute_correction(
        self,
        kosha_states: torch.Tensor,
        overactive_kosha: str,
    ) -> torch.Tensor:
        """
        Compute corrective rotation vector.

        Args:
            kosha_states: [B, 5] current Kosha states
            overactive_kosha: Name of the overactive Kosha

        Returns:
            correction: [B, 5] correction to apply
        """
        B = kosha_states.shape[0]

        # Get target distribution for this imbalance
        target = self.rotation_targets[overactive_kosha].to(kosha_states.device)
        target = target.unsqueeze(0).expand(B, -1)  # [B, 5]

        # Compute difference
        delta = target - kosha_states

        # Scale by correction strength
        correction = delta * self.config.correction_strength

        # Clamp to max correction per step
        correction = torch.clamp(
            correction,
            min=-self.config.max_correction_per_step,
            max=self.config.max_correction_per_step
        )

        return correction

    def apply_correction(
        self,
        sovereign_state: torch.Tensor,
        correction: torch.Tensor,
    ) -> torch.Tensor:
        """
        Apply correction to full 32D sovereign state.

        Args:
            sovereign_state: [B, 32] full state
            correction: [B, 5] Kosha correction

        Returns:
            corrected_state: [B, 32] with correction applied
        """
        corrected = sovereign_state.clone()

        # Apply correction to Kosha slice [12:17]
        corrected[:, self.KOSHA_SLICE] = corrected[:, self.KOSHA_SLICE] + correction

        # Re-normalize Koshas to sum to 1 (softmax-like)
        kosha_corrected = corrected[:, self.KOSHA_SLICE]
        kosha_normalized = F.softmax(kosha_corrected, dim=-1)
        corrected[:, self.KOSHA_SLICE] = kosha_normalized

        return corrected

    def forward(
        self,
        sovereign_state: torch.Tensor,
        force_correction: bool = False,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Apply inference-time phase correction if needed.

        IMPORTANT: This should only be called during inference (model.eval()).
        During training, use KoshaGyroscopicLoss instead.

        Args:
            sovereign_state: [B, 32] current sovereign state
            force_correction: If True, always apply correction (for testing)

        Returns:
            corrected_state: [B, 32] potentially corrected state
            diagnostics: Dict with correction details
        """
        diagnostics = {
            'correction_applied': False,
            'overactive_kosha': None,
            'kosha_values': {},
            'correction_magnitude': 0.0,
        }

        # Extract Kosha states
        kosha_states = sovereign_state[:, self.KOSHA_SLICE]  # [B, 5]

        # Detect imbalance
        is_imbalanced, overactive_kosha, kosha_values = self.detect_imbalance(kosha_states)
        diagnostics['kosha_values'] = kosha_values

        if not is_imbalanced and not force_correction:
            return sovereign_state, diagnostics

        # We have an imbalance - compute and apply correction
        if overactive_kosha is None:
            overactive_kosha = 'Mental'  # Default for forced correction

        diagnostics['overactive_kosha'] = overactive_kosha
        diagnostics['correction_applied'] = True

        # Check if this specific correction is enabled
        enable_map = {
            'Physical': self.config.enable_physical_correction,
            'Vital': self.config.enable_vital_correction,
            'Mental': self.config.enable_mental_correction,
            'Intellect': self.config.enable_intellect_correction,
            'Bliss': self.config.enable_bliss_correction,
        }

        if not enable_map.get(overactive_kosha, True):
            diagnostics['correction_applied'] = False
            diagnostics['reason'] = f'{overactive_kosha} correction disabled'
            return sovereign_state, diagnostics

        # Compute correction
        correction = self.compute_correction(kosha_states, overactive_kosha)
        diagnostics['correction_magnitude'] = correction.abs().mean().item()

        # Apply correction
        corrected_state = self.apply_correction(sovereign_state, correction)

        # Update statistics
        self.correction_count += 1
        self.last_correction = diagnostics.copy()

        return corrected_state, diagnostics

    def get_statistics(self) -> Dict[str, Any]:
        """Get correction statistics for logging."""
        return {
            'total_corrections': self.correction_count,
            'last_correction': self.last_correction,
        }

    def reset_statistics(self):
        """Reset correction statistics."""
        self.correction_count = 0
        self.last_correction = None


class InferenceGuardrail(nn.Module):
    """
    Combined inference-time guardrail that integrates:
    1. KoshaPhaseCorrector - Direct phase rotation
    2. VrittiResonanceLoss - Alignment checking (diagnostic only during inference)

    This is the "safety net" for deployment.

    Usage:
        guardrail = InferenceGuardrail()

        # During inference loop:
        with torch.no_grad():
            corrected_state, diagnostics = guardrail(sovereign_state)
    """

    def __init__(
        self,
        phase_corrector_config: Optional[KoshaPhaseCorrectorConfig] = None,
        vritti_config: Optional[VrittiResonanceConfig] = None,
    ):
        """
        Initialize combined inference guardrail.

        Args:
            phase_corrector_config: Config for phase correction
            vritti_config: Config for Vritti alignment checking
        """
        super().__init__()

        self.phase_corrector = KoshaPhaseCorrector(
            config=phase_corrector_config
        )

        # Vritti resonance for diagnostic alignment checking
        # Note: Set require_graduation=False for inference (always active)
        vritti_cfg = vritti_config or VrittiResonanceConfig(require_graduation=False)
        self.vritti_checker = VrittiResonanceLoss(config=vritti_cfg)
        self.vritti_checker.activate()  # Always active during inference

    def forward(
        self,
        sovereign_state: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Apply inference guardrails.

        Args:
            sovereign_state: [B, 32] current state

        Returns:
            corrected_state: [B, 32] with corrections applied
            diagnostics: Combined diagnostics from all guardrails
        """
        diagnostics = {}

        # 1. Phase correction for Kosha imbalance
        corrected_state, phase_diag = self.phase_corrector(sovereign_state)
        diagnostics['phase_correction'] = phase_diag

        # 2. Vritti alignment check (diagnostic only - no gradient)
        kosha_states = corrected_state[:, 12:17]
        vritti_states = corrected_state[:, 17:22]

        alignment = self.vritti_checker.compute_alignment_scores(
            kosha_states, vritti_states
        )
        diagnostics['vritti_alignment'] = alignment

        # 3. Compute overall "health" score
        health_score = self._compute_health_score(corrected_state, alignment)
        diagnostics['health_score'] = health_score

        return corrected_state, diagnostics

    def _compute_health_score(
        self,
        state: torch.Tensor,
        alignment: Dict[str, float],
    ) -> float:
        """
        Compute overall state health score (0-1).

        Components:
        - Kosha balance (variance should be low)
        - Vritti alignment (correlations should be high)
        - No single Kosha dominating
        """
        koshas = state[:, 12:17].mean(dim=0)

        # 1. Kosha balance (low variance = good)
        kosha_variance = koshas.var().item()
        balance_score = max(0, 1.0 - kosha_variance * 5)  # Penalize high variance

        # 2. Vritti alignment (average of absolute correlations)
        align_values = [abs(v) for v in alignment.values()]
        alignment_score = sum(align_values) / len(align_values) if align_values else 0.5

        # 3. No domination (max Kosha shouldn't be too high)
        max_kosha = koshas.max().item()
        domination_penalty = max(0, max_kosha - 0.4) * 2  # Penalty if any > 0.4

        # Combined score
        health = (balance_score * 0.4 + alignment_score * 0.4 + (1 - domination_penalty) * 0.2)
        return max(0.0, min(1.0, health))
