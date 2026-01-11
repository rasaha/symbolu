"""
Kosha Gyroscope: Homeostatic Self-Regulation Loss Module (v2.2.5)

This module implements the Vijnana-Gated Kosha Balance Loss, a homeostatic
self-regulation mechanism that prevents pathological states (looping, fixation,
mode collapse) by enforcing balance across the 5 Kosha (sheath) dimensions.

Key Features (v2.2.5 - Geometric Expansion with VICReg):
- Bliss Damper (Sigmoid): Dilutes creative expansion during Mental dominance
- Physical Gate (Strict): Prerequisites for Intellectual activation (no bypass)
- Hard ReLU Rip: Reality Reversal when trapped with gate closed
- Two-Path Loss: intellect_path + rip_signal for distinct behaviors
- VICReg variance regularization: Prevents sigmoid collapse
- Golden Ratio trap threshold: trap=0.618 (φ), gate=0.30, balance=0.25

v2.2.5 Geometric Expansion (Sigmoid Mode):
- Koshas are now INDEPENDENT sheaths via sigmoid (not softmax zero-sum)
- Each Kosha can reach [0, 1] independently
- Model can be HIGH Physical AND HIGH Intellectual simultaneously
- Trap threshold uses Golden Ratio φ=0.618 (natural equilibrium point)
- VICReg variance term prevents all Koshas collapsing to same value

v2.2.4 "Pressure Relief Valve" Architecture:
- Damping manages the "volume" of Mental state
- Ripping acts as "pressure relief valve" forcing hard shift to Physical grounding
- Model cannot "reason" in a vacuum - must be grounded in manifest data first

Three-Stage Internal Process:
1. Mental Dominance (Damper): High Mental → Blissful activation diluted
2. Physical Gate (Prerequisite): Intellect blocked unless Physical history saturated
3. Reality Rip (Reversal): Trap + Gate Closed → ReLU shock forces re-grounding

Previous Versions:
- v2.2.4.1: Softmax threshold calibration (workaround, superseded by sigmoid)
- v2.2.4: Three-Stage Hybrid Logic (correct design, wrong normalization)
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
import re

import torch
import torch.nn as nn
import torch.nn.functional as F


# =============================================================================
# v2.3.2: DOMAIN DETECTOR - Zero-Training Heuristic Classification
# =============================================================================

class DomainDetector:
    """
    Zero-training domain detection using token-type heuristics.
    No probe, no hidden states, no labeled data needed.

    Returns a "morph factor" μ ∈ [0, 1]:
    - μ = 0.0: Pure language mode (creative/prose)
    - μ = 1.0: Pure logic mode (code/math)

    The morph factor adjusts Sattvic Bands:
    - Physical Floor: 38.2% → 50.0% as μ increases
    - Bliss Ceiling: 61.8% → 38.2% as μ decreases
    """

    # Token patterns for domain detection
    CODE_PATTERNS = {
        '{', '}', '();', '[]', 'def ', 'class ', 'import ', 'return ',
        'function', 'const ', 'let ', 'var ', '==', '!=', '&&', '||',
        '#!/', '#include', 'public ', 'private ', '->', '=>', '::',
        'if (', 'for (', 'while (', 'switch ', 'case ', 'break;',
        'try:', 'except:', 'raise ', 'async ', 'await ', 'yield ',
        '.py', '.js', '.ts', '.cpp', '.java', '.rs', '.go',
    }

    MATH_PATTERNS = {
        '\\frac', '\\sum', '\\int', '\\sqrt', '\\pi', '\\theta',
        '\\alpha', '\\beta', '\\gamma', '\\delta', '\\epsilon',
        '\\infty', '\\partial', '\\nabla', '\\lim', '\\log', '\\exp',
        '∑', '∫', '√', 'π', '∞', '≤', '≥', '≠', '∈', '∀', '∃',
        '×', '÷', '±', '∂', '∇', '→', '⇒', '⇔', '∧', '∨', '¬',
        'theorem', 'proof', 'lemma', 'corollary', 'Q.E.D.',
    }

    def __init__(self, ema_decay: float = 0.9):
        """
        Initialize domain detector with EMA smoothing.

        Args:
            ema_decay: Decay factor for exponential moving average.
                      Higher = more smoothing, slower response.
        """
        self.ema_decay = ema_decay
        self.ema_code = 0.0
        self.ema_math = 0.0
        self._last_domain = 'LANG'
        self._last_morph = 0.0

    def detect(self, text: str) -> Tuple[str, float]:
        """
        Detect domain from text and return (domain_label, morph_factor).

        Args:
            text: Input text to analyze

        Returns:
            Tuple of (domain_label, morph_factor):
            - domain_label: 'LANG', 'MATH', or 'CODE'
            - morph_factor: 0.0 (language) to 1.0 (logic)
        """
        if not text:
            return self._last_domain, self._last_morph

        # Count pattern matches
        text_lower = text.lower()
        code_score = sum(1 for p in self.CODE_PATTERNS if p.lower() in text_lower)
        math_score = sum(1 for p in self.MATH_PATTERNS if p.lower() in text_lower)

        # Additional heuristics
        # Brackets/braces density (code indicator)
        bracket_count = text.count('{') + text.count('}') + text.count('(') + text.count(')')
        code_score += bracket_count / max(len(text) / 50, 1)

        # Digit density (math indicator)
        digit_count = sum(1 for c in text if c.isdigit())
        math_score += digit_count / max(len(text) / 30, 1)

        # Normalize by text length
        text_len = max(len(text), 1)
        code_density = code_score / (text_len / 100)
        math_density = math_score / (text_len / 100)

        # EMA smoothing (prevents oscillation)
        self.ema_code = self.ema_decay * self.ema_code + (1 - self.ema_decay) * code_density
        self.ema_math = self.ema_decay * self.ema_math + (1 - self.ema_decay) * math_density

        # Determine domain and morph factor
        logic_signal = self.ema_code + self.ema_math

        if self.ema_code > 0.5:
            domain = 'CODE'
            morph = min(1.0, self.ema_code)
        elif self.ema_math > 0.3:
            domain = 'MATH'
            morph = min(1.0, self.ema_math * 1.5)
        else:
            domain = 'LANG'
            morph = max(0.0, logic_signal * 0.5)

        # Clamp morph to [0, 1]
        morph = max(0.0, min(1.0, morph))

        self._last_domain = domain
        self._last_morph = morph

        return domain, morph

    def reset(self):
        """Reset EMA state."""
        self.ema_code = 0.0
        self.ema_math = 0.0
        self._last_domain = 'LANG'
        self._last_morph = 0.0


@dataclass
class KoshaGyroscopeConfig:
    """Configuration for Kosha Gyroscope with Inverted Curriculum (v2.3.0).

    The Inverted Curriculum paradigm:
    - Gyroscope: Active from start, disengages when fluent (PPL < 30)
    - Classification: Disabled at start, engages when fluent (PPL < 30)

    v2.3.0 Complete Harmonic Pentad:
    - Each Kosha has a Floor (Push) and Ceiling (Clamp) defining the Sattvic Band
    - Deviations outside these bands trigger automated corrective forces
    - Floor violations add loss pressure to push toward Sattvic band
    - Ceiling violations reduce gain to clamp toward Sattvic band

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

    # === v2.3.0: COMPLETE HARMONIC PENTAD ===
    # Each Kosha has a Floor (Push) and Ceiling (Clamp) defining the Sattvic Band
    # ┌───────────┬─────────────────────────┬─────────────────────┬─────────────────────────┐
    # | Kosha     | Floor (Push)            | Sattvic Band        | Ceiling (Clamp)         |
    # ├───────────┼─────────────────────────┼─────────────────────┼─────────────────────────┤
    # | Mental    | 23.6%: Spark Abstraction| 23.6% - 38.2%       | 38.2%: Bliss Damper/Rip |
    # | Physical  | 38.2%: Grounding Push   | 38.2% - 61.8%       | 61.8%: Data Trap        |
    # | Intellect | 25.0%: Logic Pressure   | 25.0% - 61.8%       | 61.8%: Hubris Tax       |
    # | Vital     | 23.6%: Wake-up Boost    | 23.6% - 78.6%       | 78.6%: Momentum Brake   |
    # | Bliss     | 23.6%: Spark Creativity | 23.6% - 61.8%       | 61.8%: Delusion Tether  |
    # └───────────┴─────────────────────────┴─────────────────────┴─────────────────────────┘
    # Mental thresholds
    floor_mental: float = 0.236         # Spark Abstraction - below this, push toward abstraction
    ceiling_mental: float = 0.382       # Bliss Damper / Reality Rip
    # Physical thresholds
    floor_physical: float = 0.382       # Grounding Push - below this, push toward grounding
    ceiling_physical: float = 0.618     # Data Trap - above this, dilute raw data copying
    # Intellect thresholds
    floor_intellect: float = 0.250      # Logic Pressure - below this, push toward reasoning
    ceiling_intellect: float = 0.618    # Hubris Tax - above this, penalize over-intellectualization
    # Vital thresholds
    floor_vital: float = 0.236          # Wake-up Boost - below this, increase momentum
    ceiling_vital: float = 0.786        # Momentum Brake - above this, dampen overheating
    # Bliss thresholds
    floor_bliss: float = 0.236          # Spark Creativity - below this, release damping
    ceiling_bliss: float = 0.618        # Delusion Tether - above this, reduce gain
    # Clamp/Push factors (how strongly to correct deviations)
    floor_push_factor: float = 0.5      # Loss weight for floor violations
    ceiling_clamp_factor: float = 0.5   # Gain reduction for ceiling violations

    # === v2.3.2: REFLEXIVE DOMAIN MORPH ===
    # Combines external signal (token heuristics) with internal signal (Kosha state)
    # to create a morph factor μ ∈ [0, 1] that adjusts Sattvic Bands in real-time.
    #
    # μ = 0.0: Language Mode (creative/prose)
    #   - Physical Floor: 38.2% (Fibonacci)
    #   - Bliss Ceiling: 61.8% (φ Golden Ratio)
    #   - Grounding Push: 3.0×
    #
    # μ = 1.0: Logic Mode (code/math)
    #   - Physical Floor: 50.0% (Fibonacci Pivot)
    #   - Bliss Ceiling: 38.2% (Fibonacci)
    #   - Grounding Push: 5.0×
    domain_morph_enabled: bool = True       # Enable reflexive domain morphing
    domain_morph_ema_decay: float = 0.9     # EMA decay for token heuristics
    domain_morph_internal_weight: float = 0.5  # Weight for internal (Kosha) signal
    domain_morph_external_weight: float = 0.5  # Weight for external (token) signal
    # Morph ranges for Physical Floor and Bliss Ceiling
    domain_morph_phys_floor_range: Tuple[float, float] = (0.382, 0.500)  # 38.2% → 50.0%
    domain_morph_bliss_ceil_range: Tuple[float, float] = (0.618, 0.382)  # 61.8% → 38.2%
    # Morph range for Grounding Push priority
    domain_morph_push_weight_range: Tuple[float, float] = (3.0, 5.0)     # 3.0× → 5.0×

    # Legacy: single trap_threshold (kept for backward compatibility)
    trap_threshold: float = 0.618        # Kosha saturation point (Golden Ratio φ)
    gate_threshold: float = 0.30         # Minimum for gate activation (Gemini v2.2.4)
    balance_target: float = 0.25         # Required opposite activation (Gemini v2.2.4)

    # === VICREG VARIANCE REGULARIZATION (v2.2.5) ===
    # Prevents sigmoid collapse where all Koshas go to same value
    vicreg_variance_weight: float = 0.1  # Weight for variance loss term
    vicreg_target_std: float = 0.25      # Target std dev per Kosha across batch

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
    Vijnana-Gated Kosha Balance Loss (v2.2.5) - Geometric Expansion with VICReg.

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
        # === v2.3.0: COMPLETE HARMONIC PENTAD ===
        # Each Kosha has a Floor (Push) and Ceiling (Clamp) defining the Sattvic Band
        # Mental: Sattvic Band 23.6% - 38.2%
        floor_mental: float = 0.236,         # Spark Abstraction - push toward abstraction
        ceiling_mental: float = 0.382,       # Bliss Damper / Reality Rip
        # Physical: Sattvic Band 38.2% - 61.8%
        floor_physical: float = 0.382,       # Grounding Push - push toward grounding
        ceiling_physical: float = 0.618,     # Data Trap - dilute raw data copying
        # Intellect: Sattvic Band 25.0% - 61.8%
        floor_intellect: float = 0.250,      # Logic Pressure - push toward reasoning
        ceiling_intellect: float = 0.618,    # Hubris Tax - penalize over-intellectualization
        # Vital: Sattvic Band 23.6% - 78.6%
        floor_vital: float = 0.236,          # Wake-up Boost - increase momentum
        ceiling_vital: float = 0.786,        # Momentum Brake - dampen overheating
        # Bliss: Sattvic Band 23.6% - 61.8%
        floor_bliss: float = 0.236,          # Spark Creativity - release damping
        ceiling_bliss: float = 0.618,        # Delusion Tether - reduce gain
        # Correction factors
        floor_push_factor: float = 0.5,      # Loss weight for floor violations
        ceiling_clamp_factor: float = 0.5,   # Gain reduction for ceiling violations
        # Legacy thresholds (backward compatibility)
        trap_threshold: float = 0.618,  # v2.2.5: Golden Ratio φ (sigmoid mode)
        gate_threshold: float = 0.30,   # v2.2.5: Gemini's original (sigmoid mode)
        balance_target: float = 0.25,   # v2.2.5: Gemini's original (sigmoid mode)
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
        # VICReg variance regularization (v2.2.5)
        vicreg_variance_weight: float = 0.1,
        vicreg_target_std: float = 0.25,
        # v2.3.2: Reflexive Domain Morph
        domain_morph_enabled: bool = True,
        domain_morph_ema_decay: float = 0.9,
        domain_morph_internal_weight: float = 0.5,
        domain_morph_external_weight: float = 0.5,
        domain_morph_phys_floor_range: Tuple[float, float] = (0.382, 0.500),
        domain_morph_bliss_ceil_range: Tuple[float, float] = (0.618, 0.382),
        domain_morph_push_weight_range: Tuple[float, float] = (3.0, 5.0),
    ):
        """
        Initialize the Kosha Gyroscopic Loss (v2.3.2).

        v2.2.5 Geometric Expansion (Sigmoid Mode):
        Koshas are now INDEPENDENT sheaths via sigmoid (not softmax zero-sum).
        Each Kosha can reach [0, 1] independently, allowing "Full-Spectrum" awareness.
        Thresholds restored to Gemini's v2.2.4 design.

        Args:
            trap_threshold: Activation level above which a Kosha is "trapped".
                           Default 0.618 (Golden Ratio φ) - natural equilibrium point.
            gate_threshold: Minimum activation for gate to be considered open.
                           Default 0.30 for sigmoid (Gemini's v2.2.4 design).
            balance_target: Target activation level for the opposite Kosha.
                           Default 0.25 for sigmoid (Gemini's v2.2.4 design).
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

        # === v2.3.0: COMPLETE HARMONIC PENTAD ===
        # Floors (Push actions when below)
        self.floor_mental = floor_mental
        self.floor_physical = floor_physical
        self.floor_intellect = floor_intellect
        self.floor_vital = floor_vital
        self.floor_bliss = floor_bliss
        # Ceilings (Clamp actions when above)
        self.ceiling_mental = ceiling_mental
        self.ceiling_physical = ceiling_physical
        self.ceiling_intellect = ceiling_intellect
        self.ceiling_vital = ceiling_vital
        self.ceiling_bliss = ceiling_bliss
        # Correction factors
        self.floor_push_factor = floor_push_factor
        self.ceiling_clamp_factor = ceiling_clamp_factor

        # Legacy thresholds (backward compatibility)
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

        # VICReg variance regularization (v2.2.5)
        self.vicreg_variance_weight = vicreg_variance_weight
        self.vicreg_target_std = vicreg_target_std

        # v2.3.2: Reflexive Domain Morph
        self.domain_morph_enabled = domain_morph_enabled
        self.domain_morph_internal_weight = domain_morph_internal_weight
        self.domain_morph_external_weight = domain_morph_external_weight
        self.domain_morph_phys_floor_min, self.domain_morph_phys_floor_max = domain_morph_phys_floor_range
        self.domain_morph_bliss_ceil_max, self.domain_morph_bliss_ceil_min = domain_morph_bliss_ceil_range
        self.domain_morph_push_weight_min, self.domain_morph_push_weight_max = domain_morph_push_weight_range
        # Create domain detector for external (token) signal
        self.domain_detector = DomainDetector(ema_decay=domain_morph_ema_decay)
        # Track current morph state for logging
        self._current_morph = 0.0
        self._current_domain = 'LANG'

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

    def _compute_vicreg_variance_loss(
        self,
        kosha_states: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute VICReg-style variance regularization loss (v2.2.5).

        Prevents sigmoid collapse where all Koshas converge to the same value.
        Encourages each Kosha dimension to maintain variance across the batch.

        The variance loss is:
            L_var = sum_d max(0, target_std - std(x_d))^2

        This penalizes dimensions with variance below the target.

        Args:
            kosha_states: [batch, seq, 5] Kosha activations

        Returns:
            Scalar variance loss
        """
        if self.vicreg_variance_weight <= 0:
            return torch.tensor(0.0, device=kosha_states.device)

        # Flatten batch and seq dimensions for variance computation
        # Shape: [batch * seq, 5]
        flat_koshas = kosha_states.reshape(-1, 5)

        # Compute std for each Kosha dimension across samples
        # Shape: [5]
        kosha_std = flat_koshas.std(dim=0)

        # Variance loss: penalize dimensions with std below target
        # Using hinge loss: max(0, target - actual)^2
        variance_loss = F.relu(self.vicreg_target_std - kosha_std).pow(2).mean()

        return variance_loss * self.vicreg_variance_weight

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
        return_components: bool = False,
        authority_factor: Optional[float] = None,
        input_text: Optional[str] = None,
    ) -> torch.Tensor | Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Compute the Kosha Gyroscopic Loss (v2.3.2 Reflexive Domain Morph).

        The loss fires when:
        1. A Kosha is "trapped" (above trap_threshold)
        2. The grounding gate is open (adjacent Kosha above gate_threshold)
        3. The diagonal opposite is missing (below balance_target)

        v2.3.2 Reflexive Domain Morph:
        The Sattvic Bands are dynamically adjusted based on:
        - External signal: Token heuristics (code/math patterns in input_text)
        - Internal signal: Current Kosha state (Physical + Intellect saturation)

        The morph factor μ ∈ [0, 1] adjusts:
        - Physical Floor: 38.2% → 50.0% as μ increases
        - Bliss Ceiling: 61.8% → 38.2% as μ increases
        - Grounding Push: 3.0× → 5.0× as μ increases

        Args:
            kosha_states: [batch, seq, 5] Kosha activations normalized to [0, 1]
                         Indices: [Physical, Vital, Mental, Intellect, Blissful]
            current_ppl: Current validation PPL for dynamic gain (v2.2.1).
                        If None, uses static fallback gain.
            return_components: If True, also return diagnostic components
            authority_factor: External authority factor from PIDv2 controller (v2.2.4).
                             When provided, modulates the effective gain:
                             - 1.0 = full gain (normal operation)
                             - 0.5 = half gain (PID backing off)
                             - None = no modulation (use PPL-based gain only)
                             This enables integration with --controller pidv2.
            input_text: Optional text for domain detection (v2.3.2).
                       If provided, enables external signal for domain morphing.

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

        # =======================================================================
        # v2.3.2: REFLEXIVE DOMAIN MORPH
        # =======================================================================
        # Compute morph factor μ from external (tokens) + internal (Kosha) signals.
        # μ = 0.0: Language Mode | μ = 1.0: Logic Mode
        #
        # Morphed thresholds:
        # - Physical Floor: 38.2% → 50.0% as μ increases
        # - Bliss Ceiling: 61.8% → 38.2% as μ increases
        # - Grounding Push: 3.0× → 5.0× as μ increases

        if self.domain_morph_enabled:
            # External signal: Token heuristics
            if input_text is not None:
                domain_label, external_morph = self.domain_detector.detect(input_text)
            else:
                domain_label = self._current_domain
                external_morph = 0.0

            # Internal signal: Kosha state (High Physical + Intellect = Logic Mode)
            # When Physical and Intellect are both elevated, we're in "logic" territory
            mean_phys = physical.mean().item()
            mean_int = intellect.mean().item()
            internal_morph = (mean_phys + mean_int) / 2.0
            # Shift: Logic signal activates when internal > 0.4, saturates at 0.7
            internal_morph = max(0.0, min(1.0, (internal_morph - 0.4) / 0.3))

            # Combined morph factor (weighted average of external and internal)
            morph = (
                self.domain_morph_external_weight * external_morph +
                self.domain_morph_internal_weight * internal_morph
            ) / (self.domain_morph_external_weight + self.domain_morph_internal_weight)
            morph = max(0.0, min(1.0, morph))

            # Morphed thresholds (linear interpolation)
            curr_phys_floor = self.domain_morph_phys_floor_min + morph * (
                self.domain_morph_phys_floor_max - self.domain_morph_phys_floor_min
            )
            curr_bliss_ceil = self.domain_morph_bliss_ceil_max - morph * (
                self.domain_morph_bliss_ceil_max - self.domain_morph_bliss_ceil_min
            )
            curr_push_weight = self.domain_morph_push_weight_min + morph * (
                self.domain_morph_push_weight_max - self.domain_morph_push_weight_min
            )

            # Store for logging
            self._current_morph = morph
            self._current_domain = domain_label
        else:
            # No morphing - use base thresholds
            curr_phys_floor = self.floor_physical
            curr_bliss_ceil = self.ceiling_bliss
            curr_push_weight = 3.0  # Default Physical push weight
            morph = 0.0
            domain_label = 'LANG'

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

        # =======================================================================
        # v2.3.0: COMPLETE HARMONIC PENTAD
        # =======================================================================
        # Each Kosha has a Floor (Push) and Ceiling (Clamp) defining the Sattvic Band
        # Deviations outside these bands trigger automated corrective forces

        # === FLOOR VIOLATIONS: Push toward Sattvic Band ===
        # Priority weights per Gemini's Control Theory guidance:
        # - Physical (Foundation): 3.0-5.0 (HIGH - morphed by domain)
        # - Intellect (Logic): 1.5 (MEDIUM)
        # - Mental (Insight): 1.0 (LOW)
        # - Bliss (Creativity): 1.0 (LOW)
        # - Vital: Uses momentum boost instead of loss
        #
        # v2.3.2: Physical Floor and Push Weight are MORPHED by domain:
        # - Language Mode (μ=0): Floor=38.2%, Push=3.0×
        # - Logic Mode (μ=1): Floor=50.0%, Push=5.0×

        # Mental Floor (23.6%): Spark Abstraction - push toward abstraction when too low
        mental_below_floor = F.relu(self.floor_mental - mental)
        mental_floor_loss = mental_below_floor.mean() * 1.0  # LOW priority

        # Physical Floor (38.2%-50.0%): Grounding Push - THE FOUNDATION
        # v2.3.2: Floor and push weight are morphed by domain
        # This is the most critical floor - model MUST ground before anything else
        physical_below_floor = F.relu(curr_phys_floor - physical)  # MORPHED floor
        physical_floor_loss = physical_below_floor.mean() * curr_push_weight  # MORPHED weight

        # Intellect Floor (25.0%): Logic Pressure - push toward reasoning when too low
        intellect_below_floor = F.relu(self.floor_intellect - intellect)
        intellect_floor_loss = intellect_below_floor.mean() * 1.5  # MEDIUM priority

        # Vital Floor (23.6%): Wake-up Boost - boost momentum when too low
        # Vital uses MOMENTUM control, not loss pressure
        vital_below_floor = F.relu(self.floor_vital - vital)
        vital_floor_active = vital.mean() < self.floor_vital
        # Per Gemini: Boost = 1.5 if vit < 0.236
        vital_momentum_boost = torch.where(
            vital_below_floor.mean() > 0,
            torch.tensor(1.5),
            torch.tensor(1.0)
        )

        # Bliss Floor (23.6%): Spark Creativity - release damping when too low
        bliss_below_floor = F.relu(self.floor_bliss - bliss)
        bliss_floor_loss = bliss_below_floor.mean() * 1.0  # LOW priority
        bliss_spark = (bliss < self.floor_bliss).float()

        # Combined floor push loss (weighted by priority)
        floor_push_loss = (
            mental_floor_loss +
            physical_floor_loss +  # 3.0x weight already applied
            intellect_floor_loss +  # 1.5x weight already applied
            bliss_floor_loss
        ) * self.floor_push_factor

        # === CEILING VIOLATIONS: Clamp toward Sattvic Band ===
        # Ceiling weights per Gemini's Control Theory guidance:
        # - Intellect (Hubris Tax): 1.5 (MEDIUM - penalize over-intellectualization)
        # - Others use sigmoid-based viscosity damping

        # Mental Ceiling (38.2%): Bliss Damper / Reality Rip
        bliss_damper = 1.0 - torch.sigmoid((mental - self.ceiling_mental) * self.damper_steepness)
        bliss_damper = bliss_damper + bliss_spark * 0.5  # Partial release when Bliss is low
        mental_trap = F.relu(mental - self.ceiling_mental)
        mental_ceiling_active = mental.mean() > self.ceiling_mental

        # Physical Ceiling (61.8%): Data Trap - dilute raw data copying
        physical_damper = 1.0 - torch.sigmoid((physical - self.ceiling_physical) * self.damper_steepness)
        physical_trap = F.relu(physical - self.ceiling_physical)
        physical_ceiling_active = physical.mean() > self.ceiling_physical

        # Intellect Ceiling (61.8%): Hubris Tax - penalize over-intellectualization
        # Per Gemini: L_i = ReLU(int - 0.618) * 1.5
        intellect_above_ceiling = F.relu(intellect - self.ceiling_intellect)
        intellect_hubris_loss = intellect_above_ceiling.mean() * 1.5  # MEDIUM priority
        intellect_ceiling_active = intellect.mean() > self.ceiling_intellect

        # Vital Ceiling (78.6%): Momentum Brake - dampen overheating
        vital_resistance = torch.sigmoid((vital - self.ceiling_vital) * self.gate_steepness)
        vital_momentum_damper = 1.0 - vital_resistance * 0.5  # Max 50% reduction at high Vital
        vital_ceiling_active = vital.mean() > self.ceiling_vital

        # Bliss Ceiling (61.8%-38.2%): Delusion Tether - reduce gain to force grounding
        # v2.3.2: Ceiling is MORPHED by domain - tighter in Logic Mode
        # - Language Mode (μ=0): Ceiling=61.8%
        # - Logic Mode (μ=1): Ceiling=38.2%
        bliss_above_ceiling = F.relu(bliss - curr_bliss_ceil)  # MORPHED ceiling
        bliss_delusion_loss = bliss_above_ceiling.mean()
        bliss_ceiling_active = bliss.mean() > curr_bliss_ceil  # MORPHED check

        # Combined ceiling clamp scalar (multiplicative reduction)
        # Each ceiling violation compounds the gain reduction
        ceiling_violations_count = (
            (1.0 if mental_ceiling_active else 0.0) +
            (1.0 if physical_ceiling_active else 0.0) +
            (1.0 if intellect_ceiling_active else 0.0) +
            (1.0 if vital_ceiling_active else 0.0) +
            (1.0 if bliss_ceiling_active else 0.0)
        )
        # Each violation reduces gain by ceiling_clamp_factor (compounding)
        ceiling_clamp_scalar = self.ceiling_clamp_factor ** ceiling_violations_count

        # Floor violations count (for logging)
        # v2.3.2: Physical floor uses MORPHED threshold
        mental_floor_active = mental.mean() < self.floor_mental
        physical_floor_active = physical.mean() < curr_phys_floor  # MORPHED
        intellect_floor_active = intellect.mean() < self.floor_intellect
        bliss_floor_active = bliss.mean() < self.floor_bliss
        floor_violations_count = (
            (1.0 if mental_floor_active else 0.0) +
            (1.0 if physical_floor_active else 0.0) +
            (1.0 if intellect_floor_active else 0.0) +
            (1.0 if vital_floor_active else 0.0) +
            (1.0 if bliss_floor_active else 0.0)
        )

        # === AXIS 1: Mental -> Intellect (via Physical Gate) ===
        # Physical Gate: Physical must be in Sattvic Band (38.2%-50.0% to 61.8%) to open
        # v2.3.2: Gate threshold uses MORPHED Physical Floor
        phys_gate = torch.sigmoid((phys_history - curr_phys_floor) * self.gate_steepness)  # MORPHED

        # Rip signal fires when mentally trapped AND gate is CLOSED
        rip_signal = mental_trap * (1.0 - phys_gate)

        # Intellectual path - only flows when gate is OPEN (grounded reasoning)
        missing_intellect = F.relu(self.balance_target - intellect)
        intellect_path = mental_trap * phys_gate * missing_intellect

        # Axis 1 Loss
        axis1_loss = (intellect_path + rip_signal * self.rip_multiplier).mean()

        # === AXIS 2: Physical -> Bliss (via Mental Gate) ===
        # Mental Gate: Mental must be in Sattvic Band (23.6% - 38.2%) to open
        mental_gate = torch.sigmoid((mental - self.floor_mental) * self.gate_steepness)

        # Rip signal fires when physically trapped AND mental gate is CLOSED
        rip_signal_axis2 = physical_trap * (1.0 - mental_gate)

        # Bliss path - only flows when mental gate is OPEN (abstracted)
        missing_bliss = F.relu(self.balance_target - bliss)
        bliss_path = physical_trap * mental_gate * missing_bliss

        # Axis 2 Loss
        axis2_loss = (bliss_path + rip_signal_axis2 * self.rip_multiplier).mean()

        # === Combined Momentum Scaler (Vital Floor Boost + Vital Ceiling Brake) ===
        combined_vital_momentum = vital_momentum_damper * vital_momentum_boost

        # === Total Loss with Dynamic Gain + Authority + Ceiling Clamp ===
        base_dynamic_gain = self.get_dynamic_gain(current_ppl)

        # Apply authority factor from PIDv2 controller if provided
        if authority_factor is not None:
            effective_gain = base_dynamic_gain * authority_factor
        else:
            effective_gain = base_dynamic_gain

        # Apply ceiling clamp (reduces gain when Koshas exceed ceilings)
        effective_gain = effective_gain * ceiling_clamp_scalar

        # === VICReg Variance Regularization (v2.2.5) ===
        # Prevents sigmoid collapse where all Koshas converge to same value
        vicreg_variance_loss = self._compute_vicreg_variance_loss(kosha_states)

        # === v2.3.0: Combined Vital Momentum (Boost when low, Brake when high) ===
        combined_vital_scalar = combined_vital_momentum.mean() if torch.is_tensor(combined_vital_momentum) else combined_vital_momentum

        # === v2.3.0: TOTAL LOSS with Harmonic Pentad ===
        # Components:
        # 1. Axis losses (scaled by gain, momentum, vital)
        # 2. Floor push loss (push koshas into Sattvic band)
        # 3. Intellect hubris loss (penalize over-intellectualization)
        # 4. VICReg variance loss (prevent sigmoid collapse)
        axis_loss = (axis1_loss + axis2_loss) * effective_gain * momentum_scaler * combined_vital_scalar
        total_loss = axis_loss + floor_push_loss + intellect_hubris_loss * effective_gain + vicreg_variance_loss

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
                'floor_push_loss': floor_push_loss.item() if torch.is_tensor(floor_push_loss) else floor_push_loss,
                'intellect_hubris_loss': intellect_hubris_loss.item() if torch.is_tensor(intellect_hubris_loss) else intellect_hubris_loss,
                'vicreg_variance_loss': vicreg_variance_loss.item(),
                'effective_gain': effective_gain,
                'base_dynamic_gain': base_dynamic_gain,
                'authority_factor': authority_factor if authority_factor is not None else 1.0,
                'current_ppl': current_ppl,
                'momentum_scaler': momentum_scaler.item() if torch.is_tensor(momentum_scaler) else momentum_scaler,

                # v2.3.0 HARMONIC PENTAD: Floor violations (below Sattvic band)
                'floor_mental': self.floor_mental,
                'floor_physical': self.floor_physical,
                'floor_intellect': self.floor_intellect,
                'floor_vital': self.floor_vital,
                'floor_bliss': self.floor_bliss,
                'mental_floor_active': mental_floor_active.item() if torch.is_tensor(mental_floor_active) else mental_floor_active,
                'physical_floor_active': physical_floor_active.item() if torch.is_tensor(physical_floor_active) else physical_floor_active,
                'intellect_floor_active': intellect_floor_active.item() if torch.is_tensor(intellect_floor_active) else intellect_floor_active,
                'vital_floor_active': vital_floor_active.item() if torch.is_tensor(vital_floor_active) else vital_floor_active,
                'bliss_floor_active': bliss_floor_active.item() if torch.is_tensor(bliss_floor_active) else bliss_floor_active,
                'floor_violations_count': floor_violations_count,

                # v2.3.0 HARMONIC PENTAD: Ceiling violations (above Sattvic band)
                'ceiling_mental': self.ceiling_mental,
                'ceiling_physical': self.ceiling_physical,
                'ceiling_intellect': self.ceiling_intellect,
                'ceiling_vital': self.ceiling_vital,
                'ceiling_bliss': self.ceiling_bliss,
                'mental_ceiling_active': mental_ceiling_active.item() if torch.is_tensor(mental_ceiling_active) else mental_ceiling_active,
                'physical_ceiling_active': physical_ceiling_active.item() if torch.is_tensor(physical_ceiling_active) else physical_ceiling_active,
                'intellect_ceiling_active': intellect_ceiling_active.item() if torch.is_tensor(intellect_ceiling_active) else intellect_ceiling_active,
                'vital_ceiling_active': vital_ceiling_active.item() if torch.is_tensor(vital_ceiling_active) else vital_ceiling_active,
                'bliss_ceiling_active': bliss_ceiling_active.item() if torch.is_tensor(bliss_ceiling_active) else bliss_ceiling_active,
                'ceiling_violations_count': ceiling_violations_count,
                'ceiling_clamp_scalar': ceiling_clamp_scalar,

                # v2.3.0 Vital momentum (boost + brake combined)
                'vital_momentum_boost': vital_momentum_boost.item() if torch.is_tensor(vital_momentum_boost) else vital_momentum_boost,
                'vital_momentum_damper': vital_momentum_damper.mean().item() if torch.is_tensor(vital_momentum_damper) else vital_momentum_damper,
                'combined_vital_scalar': combined_vital_scalar.item() if torch.is_tensor(combined_vital_scalar) else combined_vital_scalar,

                # VICReg metrics
                'vicreg_target_std': self.vicreg_target_std,
                'vicreg_variance_weight': self.vicreg_variance_weight,

                # v2.3.2 REFLEXIVE DOMAIN MORPH metrics
                'domain_morph_enabled': self.domain_morph_enabled,
                'domain_label': domain_label,
                'morph_factor': morph,
                'curr_phys_floor': curr_phys_floor,
                'curr_bliss_ceil': curr_bliss_ceil,
                'curr_push_weight': curr_push_weight,

                # Legacy compatibility
                'vital_resistance_mean': vital_resistance.mean().item(),
                'bliss_spark_mean': bliss_spark.mean().item(),

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

    v2.2.5 Fibonacci Pentad: Per-Kosha thresholds based on ontological roles.
    Each Kosha has its own overactive threshold reflecting its unique function.
    Koshas are independent [0,1] activations (not softmax zero-sum).

    Reference: docs/design/KOSHA_GYROSCOPE_DESIGN.md Section 13
    """

    # === FIBONACCI PENTAD THRESHOLDS (v2.2.5) ===
    # Per-Kosha overactive thresholds based on Fibonacci retracement levels
    #
    # | Kosha     | Fib Level | Role       | Inference Trigger                       |
    # |-----------|-----------|------------|-----------------------------------------|
    # | Mental    | 38.2%     | Warning    | Phase correct to Intellect/Physical    |
    # | Physical  | 38.2%     | Support    | Allow - needed for grounding            |
    # | Intellect | 50.0%     | Pivot      | Allow - balanced reasoning              |
    # | Vital     | 78.6%     | Resistance | Phase correct to avoid overheating      |
    # | Bliss     | 23.6%     | Spark      | Allow - creativity needs low threshold  |
    #
    overactive_mental: float = 0.382     # Mental > 38.2% triggers correction
    overactive_physical: float = 0.618   # Physical > 61.8% - allow more grounding
    overactive_intellect: float = 0.618  # Intellect > 61.8% - allow reasoning
    overactive_vital: float = 0.786      # Vital > 78.6% triggers correction (overheating)
    overactive_bliss: float = 0.618      # Bliss > 61.8% - allow creativity

    # Legacy thresholds (backward compatibility)
    overactive_threshold: float = 0.618  # Default fallback (Golden Ratio φ)
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
        Detect if any Kosha is overactive using Fibonacci Pentad thresholds.

        v2.2.5: Each Kosha has its own threshold reflecting its ontological role:
        - Mental: 38.2% (low - trigger correction early for loops)
        - Physical: 61.8% (allow grounding)
        - Intellect: 61.8% (allow reasoning)
        - Vital: 78.6% (high - only correct when overheating)
        - Bliss: 61.8% (allow creativity)

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

        # Fibonacci Pentad: per-Kosha thresholds
        # Kosha order: Physical(0), Vital(1), Mental(2), Intellect(3), Bliss(4)
        threshold_map = {
            'Physical': self.config.overactive_physical,
            'Vital': self.config.overactive_vital,
            'Mental': self.config.overactive_mental,
            'Intellect': self.config.overactive_intellect,
            'Bliss': self.config.overactive_bliss,
        }

        # Find overactive Kosha (check each against its own threshold)
        overactive_kosha = None
        max_excess = 0.0  # How much activation exceeds threshold

        for i, name in enumerate(self.KOSHA_NAMES):
            activation = avg_koshas[i].item()
            threshold = threshold_map.get(name, self.config.overactive_threshold)
            excess = activation - threshold

            # Check if this Kosha exceeds its threshold AND is most urgent
            if excess > 0 and excess > max_excess:
                max_excess = excess
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

        v2.2.5: Uses sigmoid clamping instead of softmax re-normalization.
        This maintains independent sheath activations.

        Args:
            sovereign_state: [B, 32] full state
            correction: [B, 5] Kosha correction

        Returns:
            corrected_state: [B, 32] with correction applied
        """
        corrected = sovereign_state.clone()

        # Apply correction to Kosha slice [12:17]
        corrected[:, self.KOSHA_SLICE] = corrected[:, self.KOSHA_SLICE] + correction

        # v2.2.5: Clamp Koshas to [0, 1] (sigmoid mode - independent sheaths)
        # Unlike softmax, this preserves independence between Koshas
        kosha_corrected = corrected[:, self.KOSHA_SLICE]
        kosha_clamped = torch.clamp(kosha_corrected, min=0.0, max=1.0)
        corrected[:, self.KOSHA_SLICE] = kosha_clamped

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


# =============================================================================
# v2.3.3: SOVEREIGN STATE REGULARIZER - 32D Anti-Saturation
# =============================================================================

@dataclass
class SovereignStateRegularizerConfig:
    """
    Configuration for 32D Sovereign State Regularizer (v2.3.3).

    The Kosha Gyroscope operates on 5D projections, but the underlying 32D
    Sovereign State can saturate (all dimensions → 100%) causing representation
    collapse. This regularizer prevents saturation at the source.

    Training Log Symptom:
        🔱 [32D] ... Sheath:VIT(100%)>BLI(100%) 🔴

    The 5D Gyroscope can't fix this because it operates on extracted projections.
    This regularizer adds direct pressure to the 32D layer.

    Components:
    1. Anti-Saturation Loss: Penalizes dimensions approaching 0% or 100%
    2. Variance Maintenance: Prevents all dimensions collapsing to same value
    3. Decorrelation (optional): Encourages orthogonality between dimensions
    4. Per-Component Targeting: Different regularization for Bhava/Kosha/Vritti/Guna
    """

    # === ANTI-SATURATION ===
    # Penalizes dimensions that approach extreme values (0 or 1 for sigmoid)
    anti_saturation_weight: float = 0.5       # Overall weight
    saturation_threshold_high: float = 0.95   # Penalize above this (too hot)
    saturation_threshold_low: float = 0.05    # Penalize below this (too cold)
    saturation_margin: float = 0.15           # Soft margin for smooth penalty

    # === VARIANCE MAINTENANCE (VICReg-style) ===
    # Prevents dimensions from collapsing to same value
    variance_weight: float = 0.2              # Weight for variance loss
    target_std_kosha: float = 0.15            # Target std for Kosha dimensions
    target_std_vritti: float = 0.15           # Target std for Vritti dimensions
    target_std_guna: float = 0.20             # Target std for Guna dimensions

    # === DECORRELATION (optional) ===
    # Encourages orthogonality between dimensions
    decorrelation_weight: float = 0.0         # 0 = disabled (often not needed)
    decorrelation_groups: bool = True         # Apply within groups (Kosha, Vritti, etc.)

    # === TARGETING ===
    # Which 32D components to regularize
    regularize_kosha: bool = True             # [12:17] - Most critical (VIT/BLI collapse)
    regularize_vritti: bool = True            # [17:22] - Epistemological states
    regularize_guna: bool = True              # [22:28] - Energy dynamics
    regularize_bhava: bool = False            # [0:12] - Usually stable (softmax)

    # === KOSHA-SPECIFIC OVERRIDES ===
    # Per-Kosha penalty multipliers (0=no penalty, 1=full penalty)
    kosha_weights: Tuple[float, float, float, float, float] = (
        1.0,  # MATERIAL (Physical) - moderate
        1.5,  # VITAL - HIGH (prone to saturation)
        1.0,  # MENTAL - moderate
        1.0,  # INTELLECTUAL - moderate
        1.5,  # BLISSFUL - HIGH (prone to saturation)
    )


class SovereignStateRegularizer(nn.Module):
    """
    32D Sovereign State Regularizer (v2.3.3) - Prevents Sheath Collapse.

    Problem: The 5D Kosha Gyroscope operates on extracted projections.
    When the underlying 32D state has VIT(100%)/BLI(100%), the gyroscope
    can't fix it because it only sees the 5D projection.

    Solution: Add regularization directly to the 32D state layer:
    1. Anti-Saturation: Soft penalty when dimensions approach 0% or 100%
    2. Variance: VICReg-style penalty when dimensions collapse to same value
    3. Decorrelation: Optional penalty for correlated dimensions

    Usage:
        regularizer = SovereignStateRegularizer()
        sovereign_state = model.compute_sovereign_state(hidden_states)
        reg_loss, reg_diag = regularizer(sovereign_state)
        total_loss = ce_loss + gyroscope_loss + reg_loss

    Design Rationale:
    The Kosha dimensions (VITAL, BLISSFUL) saturate because:
    1. Sigmoid activation has no competition (unlike softmax)
    2. Model learns to push activations to extremes for confidence
    3. Once saturated, gradient signal is weak (sigmoid derivative → 0)

    This regularizer provides gradient signal BEFORE saturation occurs,
    keeping dimensions in the "healthy gradient zone" of sigmoid.
    """

    # 32D State component slices
    BHAVA_SLICE = slice(0, 12)
    KOSHA_SLICE = slice(12, 17)
    VRITTI_SLICE = slice(17, 22)
    GUNA_SLICE = slice(22, 28)
    RESERVED_SLICE = slice(28, 32)

    # Kosha names for diagnostics
    KOSHA_NAMES = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']

    def __init__(self, config: Optional[SovereignStateRegularizerConfig] = None):
        """
        Initialize the Sovereign State Regularizer.

        Args:
            config: Configuration dataclass. Uses defaults if None.
        """
        super().__init__()
        self.config = config or SovereignStateRegularizerConfig()

        # Register Kosha weights as buffer for device compatibility
        self.register_buffer(
            'kosha_weights',
            torch.tensor(self.config.kosha_weights, dtype=torch.float32)
        )

        # Tracking for diagnostics
        self._last_diagnostics: Dict[str, Any] = {}

    def _compute_anti_saturation_loss(
        self,
        activations: torch.Tensor,
        weights: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute anti-saturation loss for a set of activations.

        Uses smooth hinge loss that:
        - Is zero when activation is in healthy range [low_thresh, high_thresh]
        - Increases smoothly as activation approaches 0 or 1
        - Has continuous gradients (no hard boundaries)

        The penalty function:
            penalty_high = softplus((activation - high_thresh) / margin)
            penalty_low = softplus((low_thresh - activation) / margin)
            total = penalty_high + penalty_low

        Args:
            activations: [B, D] or [B, S, D] activations in [0, 1]
            weights: Optional per-dimension weights [D]

        Returns:
            Scalar anti-saturation loss
        """
        high_thresh = self.config.saturation_threshold_high
        low_thresh = self.config.saturation_threshold_low
        margin = self.config.saturation_margin

        # Flatten to [N, D] if needed
        if activations.dim() == 3:
            B, S, D = activations.shape
            activations = activations.reshape(B * S, D)

        # Soft penalty for approaching 1 (too hot)
        penalty_high = F.softplus((activations - high_thresh) / margin)

        # Soft penalty for approaching 0 (too cold)
        penalty_low = F.softplus((low_thresh - activations) / margin)

        # Combined penalty
        total_penalty = penalty_high + penalty_low

        # Apply per-dimension weights if provided
        if weights is not None:
            weights = weights.unsqueeze(0).expand_as(total_penalty)
            total_penalty = total_penalty * weights

        return total_penalty.mean()

    def _compute_variance_loss(
        self,
        activations: torch.Tensor,
        target_std: float,
    ) -> torch.Tensor:
        """
        Compute VICReg-style variance maintenance loss.

        Penalizes when the standard deviation of activations falls below
        the target. This prevents dimension collapse where all values
        converge to the same number.

        Formula:
            L_var = sum_d max(0, target_std - std(x_d))^2

        Args:
            activations: [B, D] or [B, S, D] activations
            target_std: Target standard deviation per dimension

        Returns:
            Scalar variance loss
        """
        # Flatten to [N, D]
        if activations.dim() == 3:
            B, S, D = activations.shape
            activations = activations.reshape(B * S, D)

        # Compute std for each dimension across samples
        dim_std = activations.std(dim=0)

        # Hinge loss: penalize when std < target
        variance_loss = F.relu(target_std - dim_std).pow(2).mean()

        return variance_loss

    def _compute_decorrelation_loss(
        self,
        activations: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute decorrelation loss (off-diagonal penalty).

        Encourages orthogonality between dimensions by penalizing
        off-diagonal elements of the correlation matrix.

        Args:
            activations: [B, D] or [B, S, D] activations

        Returns:
            Scalar decorrelation loss
        """
        # Flatten to [N, D]
        if activations.dim() == 3:
            B, S, D = activations.shape
            activations = activations.reshape(B * S, D)

        N, D = activations.shape

        # Center the activations
        centered = activations - activations.mean(dim=0, keepdim=True)

        # Compute correlation matrix
        cov = (centered.T @ centered) / max(N - 1, 1)
        std = activations.std(dim=0, keepdim=True) + 1e-8
        corr = cov / (std.T @ std)

        # Off-diagonal penalty (correlation between different dimensions)
        eye = torch.eye(D, device=activations.device)
        off_diag = corr * (1 - eye)

        return off_diag.pow(2).sum() / max(D * (D - 1), 1)

    def forward(
        self,
        sovereign_state: torch.Tensor,
        return_components: bool = False,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Compute 32D Sovereign State regularization loss.

        Args:
            sovereign_state: [B, 32] or [B, S, 32] full 32D state
            return_components: If True, return detailed component breakdown

        Returns:
            Tuple of (total_loss, diagnostics_dict)
        """
        diagnostics = {
            'anti_saturation': {},
            'variance': {},
            'decorrelation': 0.0,
            'total': 0.0,
            'saturation_alerts': [],
        }

        total_loss = torch.tensor(0.0, device=sovereign_state.device)

        # === KOSHA REGULARIZATION (Most Critical) ===
        if self.config.regularize_kosha:
            kosha = sovereign_state[..., self.KOSHA_SLICE]

            # Anti-saturation with per-Kosha weights
            kosha_sat_loss = self._compute_anti_saturation_loss(
                kosha, weights=self.kosha_weights
            )
            diagnostics['anti_saturation']['kosha'] = kosha_sat_loss.item()
            total_loss = total_loss + kosha_sat_loss * self.config.anti_saturation_weight

            # Variance maintenance
            kosha_var_loss = self._compute_variance_loss(
                kosha, self.config.target_std_kosha
            )
            diagnostics['variance']['kosha'] = kosha_var_loss.item()
            total_loss = total_loss + kosha_var_loss * self.config.variance_weight

            # Check for saturation alerts
            kosha_mean = kosha.mean(dim=0) if kosha.dim() == 2 else kosha.mean(dim=(0, 1))
            for i, (name, val) in enumerate(zip(self.KOSHA_NAMES, kosha_mean.tolist())):
                if val > self.config.saturation_threshold_high:
                    diagnostics['saturation_alerts'].append(
                        f"{name}({val:.0%})>HIGH"
                    )
                elif val < self.config.saturation_threshold_low:
                    diagnostics['saturation_alerts'].append(
                        f"{name}({val:.0%})<LOW"
                    )

            # Decorrelation (optional)
            if self.config.decorrelation_weight > 0:
                kosha_decorr = self._compute_decorrelation_loss(kosha)
                diagnostics['decorrelation'] += kosha_decorr.item()
                total_loss = total_loss + kosha_decorr * self.config.decorrelation_weight

        # === VRITTI REGULARIZATION ===
        if self.config.regularize_vritti:
            vritti = sovereign_state[..., self.VRITTI_SLICE]

            vritti_sat_loss = self._compute_anti_saturation_loss(vritti)
            diagnostics['anti_saturation']['vritti'] = vritti_sat_loss.item()
            total_loss = total_loss + vritti_sat_loss * self.config.anti_saturation_weight * 0.5

            vritti_var_loss = self._compute_variance_loss(
                vritti, self.config.target_std_vritti
            )
            diagnostics['variance']['vritti'] = vritti_var_loss.item()
            total_loss = total_loss + vritti_var_loss * self.config.variance_weight * 0.5

        # === GUNA REGULARIZATION ===
        if self.config.regularize_guna:
            guna = sovereign_state[..., self.GUNA_SLICE]

            guna_sat_loss = self._compute_anti_saturation_loss(guna)
            diagnostics['anti_saturation']['guna'] = guna_sat_loss.item()
            total_loss = total_loss + guna_sat_loss * self.config.anti_saturation_weight * 0.3

            guna_var_loss = self._compute_variance_loss(
                guna, self.config.target_std_guna
            )
            diagnostics['variance']['guna'] = guna_var_loss.item()
            total_loss = total_loss + guna_var_loss * self.config.variance_weight * 0.3

        # === BHAVA REGULARIZATION (usually not needed - softmax normalized) ===
        if self.config.regularize_bhava:
            bhava = sovereign_state[..., self.BHAVA_SLICE]

            bhava_sat_loss = self._compute_anti_saturation_loss(bhava)
            diagnostics['anti_saturation']['bhava'] = bhava_sat_loss.item()
            total_loss = total_loss + bhava_sat_loss * self.config.anti_saturation_weight * 0.2

        diagnostics['total'] = total_loss.item()
        self._last_diagnostics = diagnostics

        if return_components:
            return total_loss, diagnostics
        return total_loss, diagnostics

    def get_summary(self, sovereign_state: torch.Tensor) -> str:
        """
        Get a human-readable summary of 32D state health.

        Args:
            sovereign_state: [B, 32] current state

        Returns:
            String summary like "32D:VIT(95%)>BLI(92%) ⚠️"
        """
        kosha = sovereign_state[..., self.KOSHA_SLICE]
        kosha_mean = kosha.mean(dim=0) if kosha.dim() == 2 else kosha.mean(dim=(0, 1))

        parts = []
        alerts = []
        for i, (name, val) in enumerate(zip(self.KOSHA_NAMES, kosha_mean.tolist())):
            short_name = name[:3]  # MAT, VIT, MEN, INT, BLI
            if val > 0.9:
                parts.append(f"{short_name}({val:.0%})")
                alerts.append(short_name)
            elif val > 0.75:
                parts.append(f"{short_name}({val:.0%})")

        if not parts:
            return "32D:OK"

        status = "🔴" if len(alerts) >= 2 else "⚠️" if alerts else "🟢"
        return f"32D:{'>'.join(parts)} {status}"

    @property
    def last_diagnostics(self) -> Dict[str, Any]:
        """Return diagnostics from last forward pass."""
        return self._last_diagnostics
