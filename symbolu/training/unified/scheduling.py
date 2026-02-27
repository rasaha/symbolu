import math
import logging
import torch
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class SovereignPhaseController:
    """
    Sovereign Phase Controller - The "Nervous System" for Breaking Barriers.

    Implements graduated response, rotation damping, and layer-specific targeting
    to break through training plateaus and mode collapse without gradient instability.

    Three-Part Architecture:
    1. Graduated Response: Proportional intervention based on entropy + variance
    2. Rotation Damping: Smooth phase transitions to prevent gradient spikes
    3. Layer-Specific Targeting: Surgical interventions based on diagnostics

    Hysteresis Design:
    - Entry thresholds: entropy < 0.4 OR variance < 0.001
    - Exit thresholds: entropy > 0.55 AND variance > 0.002 AND min_duration
    - Prevents "1-step cycle" oscillation (boost → release → boost)

    Version: 1.0.0 (V9.8.8)
    Reference: docs/SOVEREIGN_PHASE_CONTROLLER_DESIGN.md
    """

    def __init__(
        self,
        enable: bool = False,
        entropy_critical: float = 0.4,
        entropy_warning: float = 0.5,
        entropy_recovered: float = 0.55,
        variance_critical: float = 0.0005,
        variance_warning: float = 0.001,
        variance_recovered: float = 0.002,
        min_boost_duration: int = 100,
        alpha: float = 0.2,
        max_rotation_per_step: float = 0.3,
        damping_coefficient: float = 0.9,
        velocity_threshold: float = 0.2,
    ):
        """
        Initialize Sovereign Phase Controller.

        Args:
            enable: Enable controller (default: False for safety)
            entropy_critical: Red alert threshold (emergency boost)
            entropy_warning: Yellow alert threshold (caution boost)
            entropy_recovered: Exit threshold (hysteresis)
            variance_critical: Red alert variance threshold
            variance_warning: Yellow alert variance threshold
            variance_recovered: Exit variance threshold
            min_boost_duration: Minimum steps to stay in boost mode
            alpha: EMA smoothing coefficient for rotation damping
            max_rotation_per_step: Maximum rotation per step (radians)
            damping_coefficient: Velocity damping coefficient
            velocity_threshold: Velocity above which damping applies
        """
        self.enable = enable

        # Thresholds with hysteresis
        self.entropy_critical = entropy_critical
        self.entropy_warning = entropy_warning
        self.entropy_recovered = entropy_recovered
        self.variance_critical = variance_critical
        self.variance_warning = variance_warning
        self.variance_recovered = variance_recovered

        # Graduated response levels (steering force multipliers)
        self.steering_levels = {
            'normal': 0.15,    # Baseline gentle nudge
            'caution': 0.30,   # Slight concern
            'warning': 0.60,   # Moderate intervention
            'critical': 1.0,   # Full nuclear option
        }

        # Damping parameters
        self.alpha = alpha
        self.max_rotation = max_rotation_per_step
        self.damping = damping_coefficient
        self.velocity_threshold = velocity_threshold

        # Hysteresis state
        self.boost_active = False
        self.boost_start_step = None
        self.min_boost_duration = min_boost_duration

        # Layer-specific rotation state (for damping)
        self.theta_prev = {}

        # Statistics
        self.total_interventions = 0
        self.layer_intervention_counts = {}

    def compute_intervention_level(
        self,
        entropy: float,
        variance: float,
    ) -> str:
        """
        Compute intervention level based on entropy and variance.

        Uses BOTH metrics to avoid false positives from noise.

        Returns:
            'critical', 'warning', 'caution', or 'normal'
        """
        # Critical: Either metric at critical level
        if entropy < self.entropy_critical or variance < self.variance_critical:
            return 'critical'

        # Warning: Both metrics moderately concerning
        elif entropy < 0.45 and variance < 0.001:
            return 'warning'

        # Caution: Either metric at warning level
        elif entropy < self.entropy_warning or variance < self.variance_warning:
            return 'caution'

        else:
            return 'normal'

    def compute_damped_rotation(
        self,
        layer: str,
        theta_target: float,
        step: int,
    ) -> float:
        """
        Apply exponential smoothing + velocity limiting to phase rotation.

        Prevents gradient discontinuities and oscillation by:
        1. EMA smoothing: θ_applied = θ_prev + α(θ_target - θ_prev)
        2. Velocity limiting: |Δθ| ≤ max_rotation_per_step
        3. Velocity damping: If moving too fast, reduce by damping coefficient

        Args:
            layer: Layer identifier (e.g., 'O4', 'O9', 'O12')
            theta_target: Target rotation angle (radians)
            step: Current training step

        Returns:
            Damped rotation angle to apply (radians)
        """
        # Initialize if first time seeing this layer
        if layer not in self.theta_prev:
            self.theta_prev[layer] = 0.0

        theta_prev = self.theta_prev[layer]

        # Step 1: Exponential smoothing
        theta_delta = self.alpha * (theta_target - theta_prev)

        # Step 2: Velocity limiting (prevent sudden jumps)
        if abs(theta_delta) > self.max_rotation:
            theta_delta = math.copysign(self.max_rotation, theta_delta)

        # Step 3: Apply
        theta_applied = theta_prev + theta_delta

        # Step 4: Velocity damping (prevent oscillation)
        velocity = abs(theta_applied - theta_prev)
        if velocity > self.velocity_threshold:
            theta_applied = theta_applied * self.damping

        # Store for next step
        self.theta_prev[layer] = theta_applied

        return theta_applied

    def get_layer_targets(
        self,
        diagnostics: dict,
    ) -> dict:
        """
        Determine which layers need intervention based on diagnostics.

        Maps observable symptoms to layer-specific rotations:
        - Vritti (mental states) → Layer targeting
        - Bhava (intentions) → Integration layer
        - Kosha (sheaths) → Synthesis layers

        Args:
            diagnostics: Dictionary containing vritti, bhava, kosha metrics

        Returns:
            Dict[layer_name, target_angle_radians]
        """
        targets = {}

        # Extract diagnostics (handle missing keys gracefully)
        vritti = diagnostics.get('vritti', {})
        bhava = diagnostics.get('bhava', {})
        kosha = diagnostics.get('kosha', {})

        # === Vritti-based interventions ===
        # Vikalpa loop (mental distortion) → Rotate O9 toward grounding
        m_vikal = vritti.get('M_Vikal', 0.0)
        if m_vikal > 0.8:
            targets['O9'] = -math.pi / 4  # -45° toward Pramana (grounding)

        # Pramana stuck (over-grounding) → Rotate O4 toward recall
        p_pram = vritti.get('P_Pram', 0.0)
        if p_pram > 0.9:
            targets['O4'] = math.pi / 6   # +30° toward Smriti (memory)

        # Smriti trap (stuck in memory) → Rotate O12 toward creativity
        i_smrit = vritti.get('I_Smrit', 0.0)
        if i_smrit > 0.9:
            targets['O12'] = math.pi / 3  # +60° toward Viparyaya (creativity)

        # === Bhava-based interventions ===
        # Single Bhava dominance → Rotate O6 (integration layer)
        if bhava:
            bhava_max = max(bhava.values()) if bhava.values() else 0.0
            if bhava_max > 0.4:
                targets['O6'] = 0.0  # Rotate toward balance (neutral angle)

        # === Kosha-based interventions ===
        # Kosha imbalance → Dual rotation O9+O12
        if kosha:
            kosha_max = max(kosha.values()) if kosha.values() else 0.0
            if kosha_max > 0.7:
                targets['O9'] = math.pi / 8     # +22.5°
                targets['O12'] = -math.pi / 8   # -22.5° (counter-rotate)

        return targets

    def update(
        self,
        step: int,
        entropy: float,
        variance: float,
        diagnostics: dict,
    ) -> dict:
        """
        Main update loop - combines graduated response, damping, and targeting.

        Args:
            step: Current training step
            entropy: Current entropy value
            variance: Current entropy variance
            diagnostics: Dictionary with vritti, bhava, kosha metrics

        Returns:
            Dictionary containing:
                - 'rotations': Dict[layer_name, rotation_radians]
                - 'level': Intervention level ('critical', 'warning', etc.)
                - 'boost_active': Whether boost mode is active
                - 'steering_force': Current steering force multiplier
                - 'would_trigger': True if would trigger (for disabled mode)
        """
        # Determine intervention level
        level = self.compute_intervention_level(entropy, variance)
        steering_force = self.steering_levels[level]

        # Check if we should enter boost mode (with hysteresis)
        would_trigger = False
        if not self.boost_active and level in ['warning', 'critical']:
            would_trigger = True
            if self.enable:
                self.boost_active = True
                self.boost_start_step = step
                self.total_interventions += 1

        # Check if we should exit boost mode (with hysteresis)
        if self.boost_active:
            steps_boosting = step - self.boost_start_step
            if (steps_boosting > self.min_boost_duration and
                entropy > self.entropy_recovered and
                variance > self.variance_recovered):
                self.boost_active = False

        # Get layer-specific targets
        targets = self.get_layer_targets(diagnostics)

        # Apply damped rotations
        rotations = {}
        for layer, theta_target in targets.items():
            theta_damped = self.compute_damped_rotation(layer, theta_target, step)
            # Scale by intervention level (only if enabled)
            if self.enable and self.boost_active:
                rotations[layer] = theta_damped * steering_force
                # Track statistics
                if layer not in self.layer_intervention_counts:
                    self.layer_intervention_counts[layer] = 0
                self.layer_intervention_counts[layer] += 1
            else:
                # Return what WOULD be applied (for diagnostics)
                rotations[layer] = theta_damped * steering_force

        return {
            'rotations': rotations,
            'level': level,
            'boost_active': self.boost_active,
            'steering_force': steering_force,
            'would_trigger': would_trigger,
            'targets': targets,
        }

    def get_statistics(self) -> dict:
        """Get intervention statistics for logging."""
        return {
            'total_interventions': self.total_interventions,
            'layer_intervention_counts': self.layer_intervention_counts.copy(),
            'boost_active': self.boost_active,
        }


class DynamicWindowScheduler:
    """
    Dynamic Window Scheduler - PPL-Adaptive Local Attention Window Sizing.

    Implements curriculum learning for attention span: small windows early
    (syntax learning), large windows late (long-range reasoning).

    Philosophy:
    - Early training (high PPL): Small window → Faster, cleaner gradients
    - Late training (low PPL): Large window → Long-range dependencies

    Memory Tradeoff:
    - Smaller window = Less VRAM = Can increase batch size
    - O(N×W) complexity: halving window = 50% memory savings

    Smooth Progression:
    - Uses intermediate values (not just powers of 2)
    - Gradual transitions (interpolates over N steps)
    - Growth rate limiting (max 25% per transition)

    Version: 1.0.0 (V9.8.9)
    Reference: Curriculum learning for receptive field dimension
    """

    def __init__(
        self,
        enable: bool = False,
        window_schedule: dict = None,
        growth_rate_max: float = 1.25,
        shrink_rate_max: float = 0.80,
        align_to_multiple: int = 32,
        smooth_transition_steps: int = 100,
        min_steps_between_changes: int = 200,
        hysteresis_factor: float = 0.15,
        vram_shrink_threshold: float = 0.85,
        initial_ppl: float = None,
    ):
        """
        Initialize Dynamic Window Scheduler.

        Args:
            enable: Enable dynamic window sizing (default: False for safety)
            window_schedule: Dict mapping PPL → window_size. Default:
                {800:128, 500:160, 350:192, 240:224, 170:256, 125:288, 95:320,
                 75:352, 60:384, 48:416, 39:448, 32:480, 26:512, 21:576,
                 17:640, 14:704, 11:768, 9:832, 7:896, 5:960, 3:1024}
            growth_rate_max: Maximum growth per transition (1.25 = 25% max)
            shrink_rate_max: Maximum shrink per transition (0.80 = 20% max)
            align_to_multiple: Round windows to multiples (32 for GPU alignment)
            smooth_transition_steps: Interpolate window over N steps (prevents jumps)
            min_steps_between_changes: Cooldown between target changes (stability)
            hysteresis_factor: PPL gap for shrinking (prevents thrashing)
            vram_shrink_threshold: Emergency shrink if VRAM > threshold
            initial_ppl: Starting PPL (for checkpoint resume). If provided, sets
                appropriate starting window. If None, starts at smallest (128).
        """
        self.enable = enable

        # Default schedule: smooth progression aligned to 32
        if window_schedule is None:
            window_schedule = {
                800: 128,   # Syntax learning (very high PPL)
                500: 160,   # Basic semantics (+25%)
                350: 192,   # Improving semantics (+20%)
                240: 224,   # Good semantics (+17%)
                170: 256,   # Paragraph coherence (+14%)
                125: 288,   # Multi-sentence (+13%)
                95: 320,    # Short documents (+11%)
                75: 352,    # Medium documents (+10%)
                60: 384,    # Long documents (+9%)
                48: 416,    # Very long context (+8%)
                39: 448,    # Reasoning start (+8%)
                32: 480,    # Multi-hop reasoning (+7%)
                26: 512,    # Complex reasoning (+7%)
                21: 576,    # Advanced reasoning (+13%)
                17: 640,    # Expert reasoning (+11%)
                14: 704,    # Deep reasoning (+10%)
                11: 768,    # Master level (+9%)
                9: 832,     # Expert+ level (+8%)
                7: 896,     # Near mastery (+8%)
                5: 960,     # Approaching mastery (+7%)
                3: 1024,    # Full context mastery (+7%)
            }

        # Sort schedule by PPL descending
        self.schedule = sorted(window_schedule.items(), reverse=True)

        # Parameters
        self.growth_rate_max = growth_rate_max
        self.shrink_rate_max = shrink_rate_max
        self.align_to = align_to_multiple
        self.smooth_steps = smooth_transition_steps
        self.min_steps_between = min_steps_between_changes
        self.hysteresis = hysteresis_factor
        self.vram_threshold = vram_shrink_threshold

        # State: Initialize window based on PPL if provided
        if initial_ppl is not None:
            # Find appropriate starting window for current PPL
            starting_window = self.schedule[-1][1]  # Default to max (1024)
            for ppl_threshold, window_size in self.schedule:
                if initial_ppl > ppl_threshold:
                    starting_window = window_size
                    break
            self.current_window = self._align_window(starting_window)
        else:
            # No initial PPL: start with smallest window (fresh training)
            self.current_window = self.schedule[0][1]  # First entry (128)

        self.target_window = self.current_window
        self.transition_start_step = 0
        self.transition_start_window = self.current_window
        self.last_target_change_step = 0

        # Statistics
        self.total_expansions = 0
        self.total_shrinks = 0
        self.total_vram_overrides = 0

    def _align_window(self, window: int) -> int:
        """Align window to multiple for GPU efficiency."""
        if self.align_to > 1:
            return ((window + self.align_to - 1) // self.align_to) * self.align_to
        return window

    def _smooth_transition(self, step: int) -> int:
        """
        Smoothly interpolate from start window to target window.

        Instead of jumping 384 → 512 instantly:
        - Step 0: 384
        - Step 25: 416 (25% progress)
        - Step 50: 448 (50% progress)
        - Step 75: 480 (75% progress)
        - Step 100: 512 (complete)
        """
        if step < self.transition_start_step:
            return self.transition_start_window

        steps_since_start = step - self.transition_start_step
        if steps_since_start >= self.smooth_steps:
            return self.target_window

        # Linear interpolation
        progress = steps_since_start / self.smooth_steps
        interpolated = (
            self.transition_start_window +
            (self.target_window - self.transition_start_window) * progress
        )

        return self._align_window(int(interpolated))

    def update(
        self,
        step: int,
        val_ppl: float,
        vram_usage: float = 0.0,
    ) -> dict:
        """
        Update window size based on PPL and VRAM.

        Args:
            step: Current training step
            val_ppl: Validation PPL
            vram_usage: VRAM usage fraction (0.0-1.0)

        Returns:
            Dictionary containing:
                - 'window': Current window size (interpolated)
                - 'target': Target window size
                - 'changed': Whether target changed this step
                - 'reason': Reason for change
                - 'would_change': True if would change (for disabled mode)
        """
        # Cooldown check (prevent thrashing)
        steps_since_change = step - self.last_target_change_step
        cooldown_active = steps_since_change < self.min_steps_between

        # Determine target window from schedule
        scheduled_target = self.schedule[-1][1]  # Default to max
        for ppl_threshold, window_size in self.schedule:
            if val_ppl > ppl_threshold:
                scheduled_target = self._align_window(window_size)
                break

        # VRAM pressure override (safety)
        vram_override = False
        if vram_usage > 0.90:
            # Critical VRAM - emergency shrink
            scheduled_target = min(scheduled_target, self._align_window(256))
            vram_override = True
        elif vram_usage > self.vram_threshold:
            # High VRAM - don't expand
            scheduled_target = min(scheduled_target, self.target_window)
            if scheduled_target < self.target_window:
                vram_override = True

        # Check if target should change
        would_change = False
        reason = "stable"

        if scheduled_target != self.target_window and not cooldown_active:
            would_change = True

            # Growth: Apply rate limiting
            if scheduled_target > self.target_window:
                max_allowed = int(self.target_window * self.growth_rate_max)
                if scheduled_target > max_allowed:
                    scheduled_target = self._align_window(max_allowed)
                    reason = "growth_rate_limited"
                else:
                    reason = f"ppl_improved_{val_ppl:.0f}"

                # Hysteresis check for growth
                # Only grow if PPL is definitively below threshold
                ppl_hysteresis_met = True
                for ppl_thresh, win_size in self.schedule:
                    if win_size == scheduled_target:
                        # Require PPL to be below threshold - hysteresis%
                        if val_ppl > ppl_thresh * (1 - self.hysteresis):
                            ppl_hysteresis_met = False
                            would_change = False
                            reason = "hysteresis_block_growth"
                        break

            # Shrink: Apply rate limiting
            elif scheduled_target < self.target_window:
                min_allowed = int(self.target_window * self.shrink_rate_max)
                if scheduled_target < min_allowed:
                    scheduled_target = self._align_window(min_allowed)
                    reason = "shrink_rate_limited"
                else:
                    reason = f"ppl_degraded_{val_ppl:.0f}"

                # Hysteresis check for shrinking
                # Only shrink if PPL is definitively above threshold
                ppl_hysteresis_met = True
                for ppl_thresh, win_size in self.schedule:
                    if win_size == self.target_window:
                        # Require PPL to be above threshold + hysteresis%
                        if val_ppl < ppl_thresh * (1 + self.hysteresis):
                            ppl_hysteresis_met = False
                            would_change = False
                            reason = "hysteresis_block_shrink"
                        break

            if vram_override:
                reason = f"vram_override_{vram_usage:.0%}"

        # Apply target change if enabled
        target_changed = False
        if would_change and self.enable:
            self.transition_start_step = step
            self.transition_start_window = self.current_window
            self.target_window = scheduled_target
            self.last_target_change_step = step
            target_changed = True

            # Update statistics
            if scheduled_target > self.transition_start_window:
                self.total_expansions += 1
            else:
                self.total_shrinks += 1
            if vram_override:
                self.total_vram_overrides += 1

        # Compute current window (smooth interpolation)
        old_window = self.current_window
        if self.enable:
            self.current_window = self._smooth_transition(step)
        else:
            # When disabled, show what target would be
            self.current_window = old_window

        return {
            'window': self.current_window,
            'target': self.target_window if self.enable else scheduled_target,
            'changed': target_changed,
            'reason': reason,
            'would_change': would_change,
            'cooldown_active': cooldown_active,
            'steps_until_cooldown': max(0, self.min_steps_between - steps_since_change),
            'interpolation_progress': min(1.0, (step - self.transition_start_step) / self.smooth_steps) if self.enable else 0.0,
        }

    def set_initial_window_from_ppl(self, ppl: float) -> int:
        """
        Set starting window based on current PPL (for checkpoint resume).

        Args:
            ppl: Current validation PPL

        Returns:
            The window size that was set
        """
        # Find appropriate window for this PPL
        starting_window = self.schedule[-1][1]  # Default to max (1024)
        for ppl_threshold, window_size in self.schedule:
            if ppl > ppl_threshold:
                starting_window = window_size
                break

        self.current_window = self._align_window(starting_window)
        self.target_window = self.current_window
        self.transition_start_window = self.current_window

        return self.current_window

    def get_statistics(self) -> dict:
        """Get window change statistics for logging."""
        return {
            'current_window': self.current_window,
            'target_window': self.target_window,
            'total_expansions': self.total_expansions,
            'total_shrinks': self.total_shrinks,
            'total_vram_overrides': self.total_vram_overrides,
        }


class AdaptiveTrainingController:
    """
    Dynamically adjusts training hyperparameters based on observed metrics.

    Instead of manual tuning, this controller:
    1. Monitors PPL velocity, coherence, and loss stability
    2. Adjusts learning rate when training is too slow or unstable
    3. Modulates PIDv2 Kp based on train/val gap
    4. Logs all adjustments for transparency

    Philosophy:
    - If model is learning slowly (low velocity) → increase LR
    - If model is unstable (high variance) → decrease LR
    - If train >> val (overfitting) → decrease Kp
    - If train ≈ val (underfitting) → increase Kp

    Usage:
        controller = AdaptiveTrainingController(optimizer, config)
        # In training loop after validation:
        controller.update(train_loss, val_loss, val_ppl, coherence, step)
    """

    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        # LR adaptation
        base_lr: float = 3e-4,
        lr_min: float = 1e-5,
        lr_max: float = 1e-3,
        lr_boost_factor: float = 1.5,
        lr_decay_factor: float = 0.7,
        # PPL velocity thresholds
        velocity_slow_threshold: float = -2.0,   # % per eval, below this = too slow
        velocity_spike_threshold: float = 10.0,  # % per eval, above this = unstable
        # Plateau detection
        plateau_window: int = 5,                 # Evals to check for plateau
        plateau_threshold: float = 1.0,          # % improvement threshold
        # Kp adaptation
        kp_base: float = 0.20,
        kp_min: float = 0.10,
        kp_max: float = 0.50,
        # Stability
        min_steps_between_adjustments: int = 200,
        # V9.8.2: Safeguards to prevent runaway LR
        max_lr_relative: float = 10.0,           # Max LR = base_lr * this (prevents runaway)
        loss_spike_threshold: float = 5.0,       # % loss increase triggers emergency decay
        grad_norm_spike_threshold: float = 100.0,  # Gradient norm above this triggers decay
        emergency_decay_factor: float = 0.5,     # Aggressive decay for emergencies
        consecutive_spike_limit: int = 3,        # After N consecutive spikes, halt boosts
    ):
        self.optimizer = optimizer
        self.base_lr = base_lr
        self.lr_min = lr_min
        # V9.8.2: Clamp lr_max to max_lr_relative * base_lr
        self.lr_max = min(lr_max, base_lr * max_lr_relative)
        self.lr_boost_factor = lr_boost_factor
        self.lr_decay_factor = lr_decay_factor

        self.velocity_slow_threshold = velocity_slow_threshold
        self.velocity_spike_threshold = velocity_spike_threshold

        self.plateau_window = plateau_window
        self.plateau_threshold = plateau_threshold

        self.kp_base = kp_base
        self.kp_min = kp_min
        self.kp_max = kp_max
        self.current_kp = kp_base

        self.min_steps_between_adjustments = min_steps_between_adjustments
        self.last_adjustment_step = 0

        # V9.8.2: Safeguard parameters
        self.max_lr_relative = max_lr_relative
        self.loss_spike_threshold = loss_spike_threshold
        self.grad_norm_spike_threshold = grad_norm_spike_threshold
        self.emergency_decay_factor = emergency_decay_factor
        self.consecutive_spike_limit = consecutive_spike_limit

        # History tracking
        self.val_ppl_history = []
        self.train_loss_history = []
        self.val_loss_history = []
        self.coherence_history = []
        self.adjustment_log = []
        self.grad_norm_history = []  # V9.8.2: Track gradient norms

        # State
        self.current_lr_multiplier = 1.0
        self.boost_count = 0
        self.decay_count = 0
        self.plateau_count = 0
        self.emergency_count = 0  # V9.8.2: Track emergency interventions
        self.consecutive_spikes = 0  # V9.8.2: Track consecutive loss spikes
        self.boost_blocked = False  # V9.8.2: Block boosts after too many spikes

        print(f"\n  [AdaptiveTraining] Controller initialized:")
        print(f"    Base LR: {base_lr:.2e} (range: {lr_min:.2e} - {self.lr_max:.2e})")
        print(f"    Velocity thresholds: slow < {velocity_slow_threshold}%, spike > {velocity_spike_threshold}%")
        print(f"    Kp range: {kp_min} - {kp_max} (base: {kp_base})")
        print(f"    V9.8.2 Safeguards: max_relative={max_lr_relative}x, loss_spike={loss_spike_threshold}%")
        print(f"    Plateau detection: {plateau_window} evals, {plateau_threshold}% threshold")

    def _compute_velocity(self) -> float:
        """Compute PPL velocity (% change per eval)."""
        if len(self.val_ppl_history) < 2:
            return 0.0
        current = self.val_ppl_history[-1]
        previous = self.val_ppl_history[-2]
        if previous == 0:
            return 0.0
        return ((current - previous) / previous) * 100

    def _detect_plateau(self) -> bool:
        """Detect if PPL has plateaued (< threshold improvement over window)."""
        if len(self.val_ppl_history) < self.plateau_window:
            return False
        recent = self.val_ppl_history[-self.plateau_window:]
        first = recent[0]
        last = recent[-1]
        if first == 0:
            return False
        improvement = ((first - last) / first) * 100
        return improvement < self.plateau_threshold

    def _compute_train_val_gap(self) -> float:
        """Compute gap between train and val loss (overfitting indicator)."""
        if not self.train_loss_history or not self.val_loss_history:
            return 0.0
        train = self.train_loss_history[-1]
        val = self.val_loss_history[-1]
        if val == 0:
            return 0.0
        return ((val - train) / val) * 100  # Positive = val > train = normal

    def update(
        self,
        train_loss: float,
        val_loss: float,
        val_ppl: float,
        coherence: float,
        global_step: int,
        authority_controller=None,  # PIDv2 controller reference
        grad_norm: float = None,  # V9.8.2: Optional gradient norm for monitoring
    ) -> Dict[str, Any]:
        """
        Update controller with current metrics and adjust hyperparameters.

        Returns dict of adjustments made.
        """
        # Record history
        self.val_ppl_history.append(val_ppl)
        self.train_loss_history.append(train_loss)
        self.val_loss_history.append(val_loss)
        self.coherence_history.append(coherence)
        if grad_norm is not None:
            self.grad_norm_history.append(grad_norm)

        # Keep history bounded
        max_history = 50
        if len(self.val_ppl_history) > max_history:
            self.val_ppl_history = self.val_ppl_history[-max_history:]
            self.train_loss_history = self.train_loss_history[-max_history:]
            self.val_loss_history = self.val_loss_history[-max_history:]
            self.coherence_history = self.coherence_history[-max_history:]
            self.grad_norm_history = self.grad_norm_history[-max_history:]

        adjustments = {"step": global_step, "actions": []}
        current_lr = self.optimizer.param_groups[0]['lr']

        # === V9.8.2: EMERGENCY BRAKE - Check for runaway LR ===
        lr_relative = current_lr / self.base_lr
        if lr_relative > self.max_lr_relative:
            # LR has exceeded safe bounds - emergency clamp
            safe_lr = self.base_lr * self.max_lr_relative
            for pg in self.optimizer.param_groups:
                pg['lr'] = safe_lr
            self.emergency_count += 1
            self.boost_blocked = True  # Block further boosts
            adjustments["actions"].append(f"EMERGENCY_CLAMP: {current_lr:.2e}→{safe_lr:.2e} (>{self.max_lr_relative}x base)")
            print(f"\n  🚨 [AdaptiveTraining] EMERGENCY CLAMP: {current_lr:.2e} → {safe_lr:.2e} (exceeded {self.max_lr_relative}x base LR)")
            self.last_adjustment_step = global_step
            current_lr = safe_lr

        # === V9.8.2: Loss Spike Detection ===
        loss_spike_detected = False
        if len(self.val_loss_history) >= 2:
            prev_loss = self.val_loss_history[-2]
            curr_loss = self.val_loss_history[-1]
            if prev_loss > 0:
                loss_change_pct = ((curr_loss - prev_loss) / prev_loss) * 100
                if loss_change_pct > self.loss_spike_threshold:
                    loss_spike_detected = True
                    self.consecutive_spikes += 1

                    # Emergency decay on loss spike
                    new_lr = max(self.lr_min, current_lr * self.emergency_decay_factor)
                    if new_lr != current_lr:
                        for pg in self.optimizer.param_groups:
                            pg['lr'] = new_lr
                        self.emergency_count += 1
                        adjustments["actions"].append(f"LOSS_SPIKE_DECAY: {current_lr:.2e}→{new_lr:.2e} (loss +{loss_change_pct:.1f}%)")
                        print(f"\n  🔥 [AdaptiveTraining] LOSS SPIKE DECAY: {current_lr:.2e} → {new_lr:.2e} (loss increased {loss_change_pct:.1f}%)")
                        self.last_adjustment_step = global_step
                        current_lr = new_lr

                    # Block boosts after consecutive spikes
                    if self.consecutive_spikes >= self.consecutive_spike_limit:
                        self.boost_blocked = True
                        print(f"  ⛔ [AdaptiveTraining] BOOST BLOCKED: {self.consecutive_spikes} consecutive loss spikes")
                else:
                    # Loss improved or stable - reset spike counter
                    self.consecutive_spikes = 0
                    if loss_change_pct < -2.0:  # Loss improving well
                        self.boost_blocked = False  # Allow boosts again

        # === V9.8.2: Gradient Norm Spike Detection ===
        if grad_norm is not None and grad_norm > self.grad_norm_spike_threshold:
            new_lr = max(self.lr_min, current_lr * self.emergency_decay_factor)
            if new_lr != current_lr:
                for pg in self.optimizer.param_groups:
                    pg['lr'] = new_lr
                self.emergency_count += 1
                self.boost_blocked = True
                adjustments["actions"].append(f"GRAD_SPIKE_DECAY: {current_lr:.2e}→{new_lr:.2e} (grad_norm={grad_norm:.1f})")
                print(f"\n  💥 [AdaptiveTraining] GRAD SPIKE DECAY: {current_lr:.2e} → {new_lr:.2e} (grad_norm={grad_norm:.1f} > {self.grad_norm_spike_threshold})")
                self.last_adjustment_step = global_step
                current_lr = new_lr

        # Check if we can make regular adjustments (skip if emergency just happened)
        if global_step - self.last_adjustment_step < self.min_steps_between_adjustments:
            if adjustments["actions"]:
                self.adjustment_log.append(adjustments)
            return adjustments

        velocity = self._compute_velocity()
        is_plateau = self._detect_plateau()
        train_val_gap = self._compute_train_val_gap()

        # === LR Adaptation ===
        # Case 1: PPL spiking (unstable) → decay LR
        if velocity > self.velocity_spike_threshold:
            new_lr = max(self.lr_min, current_lr * self.lr_decay_factor)
            if new_lr != current_lr:
                for pg in self.optimizer.param_groups:
                    pg['lr'] = new_lr
                self.decay_count += 1
                adjustments["actions"].append(f"LR_DECAY: {current_lr:.2e}→{new_lr:.2e} (spike: {velocity:+.1f}%)")
                print(f"\n  🔻 [AdaptiveTraining] LR DECAY: {current_lr:.2e} → {new_lr:.2e} (PPL spike: {velocity:+.1f}%)")
                self.last_adjustment_step = global_step

        # Case 2: Learning too slow or plateau → boost LR (V9.8.2: only if not blocked)
        elif (velocity > self.velocity_slow_threshold or is_plateau) and not self.boost_blocked:
            if is_plateau:
                self.plateau_count += 1

            # Only boost if we're not already at max
            new_lr = min(self.lr_max, current_lr * self.lr_boost_factor)
            if new_lr != current_lr and new_lr > current_lr:
                for pg in self.optimizer.param_groups:
                    pg['lr'] = new_lr
                self.boost_count += 1
                reason = "plateau" if is_plateau else f"slow: {velocity:.1f}%"
                adjustments["actions"].append(f"LR_BOOST: {current_lr:.2e}→{new_lr:.2e} ({reason})")
                print(f"\n  🔺 [AdaptiveTraining] LR BOOST: {current_lr:.2e} → {new_lr:.2e} ({reason})")
                self.last_adjustment_step = global_step
        elif self.boost_blocked and (velocity > self.velocity_slow_threshold or is_plateau):
            # Log that boost was blocked
            reason = "plateau" if is_plateau else f"slow: {velocity:.1f}%"
            print(f"\n  ⏸️  [AdaptiveTraining] LR BOOST BLOCKED ({reason}) - waiting for stable loss")

        # === Kp Adaptation (if PIDv2 controller provided) ===
        if authority_controller is not None and hasattr(authority_controller, 'Kp_min'):
            # Adjust Kp based on train/val gap
            # Large positive gap (val >> train) = overfitting → lower Kp
            # Small or negative gap = underfitting → higher Kp

            if train_val_gap > 20:  # Significant overfitting
                new_kp_min = max(self.kp_min, authority_controller.Kp_min * 0.8)
                new_kp_max = max(self.kp_min, authority_controller.Kp_max * 0.8)
                if new_kp_min != authority_controller.Kp_min:
                    authority_controller.Kp_min = new_kp_min
                    authority_controller.Kp_max = new_kp_max
                    adjustments["actions"].append(f"Kp_REDUCE: gap={train_val_gap:.1f}%")
                    print(f"\n  📉 [AdaptiveTraining] Kp REDUCED (train/val gap: {train_val_gap:.1f}%)")
                    self.last_adjustment_step = global_step

            elif train_val_gap < 5 and velocity > self.velocity_slow_threshold:
                # Underfitting and slow → increase Kp
                new_kp_min = min(self.kp_max, authority_controller.Kp_min * 1.2)
                new_kp_max = min(self.kp_max, authority_controller.Kp_max * 1.2)
                if new_kp_max != authority_controller.Kp_max:
                    authority_controller.Kp_min = new_kp_min
                    authority_controller.Kp_max = new_kp_max
                    adjustments["actions"].append(f"Kp_BOOST: gap={train_val_gap:.1f}%")
                    print(f"\n  📈 [AdaptiveTraining] Kp BOOSTED (underfitting, gap: {train_val_gap:.1f}%)")
                    self.last_adjustment_step = global_step

        if adjustments["actions"]:
            self.adjustment_log.append(adjustments)

        return adjustments

    def get_status_string(self) -> str:
        """Get formatted status string."""
        velocity = self._compute_velocity() if len(self.val_ppl_history) >= 2 else 0.0
        plateau = "PLATEAU" if self._detect_plateau() else "OK"
        current_lr = self.optimizer.param_groups[0]['lr']
        lr_relative = current_lr / self.base_lr
        blocked = " BLOCKED" if self.boost_blocked else ""
        return f"AdaptLR:{current_lr:.2e}({lr_relative:.1f}x) vel:{velocity:+.1f}% [{plateau}] boosts:{self.boost_count} decays:{self.decay_count} emerg:{self.emergency_count}{blocked}"

    def enforce_lr_bounds(self, global_step: int = 0) -> bool:
        """
        V9.8.3: Step-level LR safeguard - call EVERY training step.

        This catches runaway LR from schedulers or restored checkpoints
        that the validation-time update() method would miss.

        Returns True if LR was clamped.
        """
        current_lr = self.optimizer.param_groups[0]['lr']
        lr_relative = current_lr / self.base_lr

        clamped = False

        # Check upper bound
        if lr_relative > self.max_lr_relative:
            safe_lr = self.base_lr * self.max_lr_relative
            for pg in self.optimizer.param_groups:
                pg['lr'] = safe_lr
            self.emergency_count += 1
            self.boost_blocked = True
            print(f"\n  🚨 [AdaptiveTraining] STEP {global_step} LR CLAMPED: {current_lr:.2e} → {safe_lr:.2e} (exceeded {self.max_lr_relative}x base)")
            clamped = True

        # Check lower bound
        elif current_lr < self.lr_min:
            for pg in self.optimizer.param_groups:
                pg['lr'] = self.lr_min
            print(f"\n  ⚠️ [AdaptiveTraining] STEP {global_step} LR FLOOR: {current_lr:.2e} → {self.lr_min:.2e}")
            clamped = True

        return clamped

    def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry for logging."""
        current_lr = self.optimizer.param_groups[0]['lr']
        return {
            "current_lr": current_lr,
            "lr_relative": current_lr / self.base_lr,  # V9.8.2: Track relative LR
            "velocity": self._compute_velocity() if len(self.val_ppl_history) >= 2 else 0.0,
            "is_plateau": self._detect_plateau(),
            "train_val_gap": self._compute_train_val_gap(),
            "boost_count": self.boost_count,
            "decay_count": self.decay_count,
            "plateau_count": self.plateau_count,
            "emergency_count": self.emergency_count,  # V9.8.2: Emergency interventions
            "consecutive_spikes": self.consecutive_spikes,  # V9.8.2: Loss spike tracker
            "boost_blocked": self.boost_blocked,  # V9.8.2: Whether boosts are blocked
            "adjustment_log": self.adjustment_log[-10:],  # Last 10 adjustments
        }


class AdaptiveWarmupScheduler:
    """
    Learning rate scheduler with PPL-based warmup transition.

    Instead of a fixed warmup period, warmup ends when:
    1. PPL drops below warmup_until_ppl threshold, OR
    2. max_warmup_steps is reached (fallback)

    This ensures the model reaches a stable learning state before
    transitioning to cosine decay.

    LR trajectory:
    - Warmup phase: Linear ramp from start_factor * lr to lr
    - Decay phase: Cosine decay from lr to eta_min

    Usage:
        scheduler = AdaptiveWarmupScheduler(optimizer, config)
        # In training loop:
        scheduler.step(current_ppl)  # Pass current PPL
    """

    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        base_lr: float,
        max_steps: int,
        max_warmup_steps: int = 500,
        warmup_until_ppl: float = 500.0,
        start_factor: float = 0.1,
        eta_min_factor: float = 0.1,
    ):
        self.optimizer = optimizer
        self.base_lr = base_lr
        self.max_steps = max_steps
        self.max_warmup_steps = max_warmup_steps
        self.warmup_until_ppl = warmup_until_ppl
        self.start_factor = start_factor
        self.eta_min = base_lr * eta_min_factor

        # State
        self.current_step = 0
        self.warmup_ended = False
        self.warmup_end_step = None
        self.warmup_end_ppl = None

        # Set initial LR
        self._set_lr(base_lr * start_factor)

    def _set_lr(self, lr: float):
        """Set learning rate for all param groups."""
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr

    def _get_warmup_lr(self) -> float:
        """Linear warmup from start_factor * base_lr to base_lr."""
        if self.max_warmup_steps == 0:
            return self.base_lr
        progress = min(1.0, self.current_step / self.max_warmup_steps)
        return self.base_lr * (self.start_factor + progress * (1.0 - self.start_factor))

    def _get_cosine_lr(self) -> float:
        """Cosine decay from base_lr to eta_min."""
        if self.warmup_end_step is None:
            return self.base_lr

        # Steps since warmup ended
        decay_step = self.current_step - self.warmup_end_step
        decay_total = self.max_steps - self.warmup_end_step

        if decay_total <= 0:
            return self.eta_min

        progress = min(1.0, decay_step / decay_total)
        # Cosine decay: lr * (1 + cos(pi * progress)) / 2, scaled to [eta_min, base_lr]
        cosine_factor = 0.5 * (1.0 + math.cos(math.pi * progress))
        return self.eta_min + (self.base_lr - self.eta_min) * cosine_factor

    def step(self, current_ppl: float = float('inf')):
        """
        Update learning rate based on current step and PPL.

        Args:
            current_ppl: Current training PPL (pass inf if unknown)
        """
        self.current_step += 1

        # Check if warmup should end
        if not self.warmup_ended:
            ppl_condition = self.warmup_until_ppl > 0 and current_ppl < self.warmup_until_ppl
            step_condition = self.current_step >= self.max_warmup_steps

            if ppl_condition or step_condition:
                self.warmup_ended = True
                self.warmup_end_step = self.current_step
                self.warmup_end_ppl = current_ppl
                trigger = "PPL" if ppl_condition else "steps"
                print(f"🔥 [LR] Warmup ended at step {self.current_step} (trigger: {trigger}, "
                      f"PPL: {current_ppl:.1f}) - switching to cosine decay")

        # Compute and set LR
        if self.warmup_ended:
            lr = self._get_cosine_lr()
        else:
            lr = self._get_warmup_lr()

        self._set_lr(lr)

    def get_last_lr(self) -> list:
        """Return last computed LR (for compatibility with PyTorch schedulers)."""
        return [param_group['lr'] for param_group in self.optimizer.param_groups]

    def state_dict(self) -> dict:
        """Return scheduler state for checkpointing."""
        return {
            "current_step": self.current_step,
            "warmup_ended": self.warmup_ended,
            "warmup_end_step": self.warmup_end_step,
            "warmup_end_ppl": self.warmup_end_ppl,
        }

    def load_state_dict(self, state: dict):
        """Restore scheduler state from checkpoint."""
        self.current_step = state.get("current_step", 0)
        self.warmup_ended = state.get("warmup_ended", False)
        self.warmup_end_step = state.get("warmup_end_step")
        self.warmup_end_ppl = state.get("warmup_end_ppl")


class PPLAlphaCurriculum:
    """
    Dynamically adjusts alpha_phase/alpha_local based on current PPL.

    Philosophy:
    - High PPL (early training): Phase attention dominates to establish stable patterns
    - Low PPL (later training): Local/quadratic attention takes over for refinement

    The phase attention is slower but builds the "state scaffold" that quadratic
    attention needs. By letting phase dominate early, we ensure stable foundations
    before the faster quadratic attention refines the details.

    Formula:
        if ppl >= ppl_high:
            alpha_phase = alpha_high (e.g., 0.8)
        elif ppl <= ppl_low:
            alpha_phase = alpha_low (e.g., 0.3)
        else:
            # Linear interpolation
            alpha_phase = alpha_low + (ppl - ppl_low) * (alpha_high - alpha_low) / (ppl_high - ppl_low)
        alpha_local = 1.0 - alpha_phase

    Usage:
        curriculum = PPLAlphaCurriculum(config)
        # In training loop:
        alpha_phase, alpha_local = curriculum.get_alphas(current_ppl)
        update_model_alphas(model, alpha_phase, alpha_local)
    """

    def __init__(
        self,
        alpha_high: float = 0.8,
        alpha_low: float = 0.3,
        ppl_high: float = 1000.0,
        ppl_low: float = 100.0,
        ema_decay: float = 0.95,  # EMA smoothing for PPL
        # Adaptive window size
        enable_adaptive_window: bool = False,
        window_size_high_ppl: int = 128,  # Small window when PPL high (fast phase)
        window_size_low_ppl: int = 256,   # Large window when PPL low (local context)
    ):
        self.alpha_high = alpha_high
        self.alpha_low = alpha_low
        self.ppl_high = ppl_high
        self.ppl_low = ppl_low
        self.ema_decay = ema_decay

        # Adaptive window
        self.enable_adaptive_window = enable_adaptive_window
        self.window_size_high_ppl = window_size_high_ppl
        self.window_size_low_ppl = window_size_low_ppl
        self.current_window_size = window_size_high_ppl if enable_adaptive_window else None
        self.window_transition_logged = False

        # State
        self.ppl_ema = None
        self.current_alpha_phase = alpha_high  # Start with phase dominant
        self.current_alpha_local = 1.0 - alpha_high
        self.last_transition_ppl = None
        self.transition_logged = False

    def update(self, current_ppl: float) -> tuple:
        """
        Update alpha values based on current PPL.

        Args:
            current_ppl: Current training PPL

        Returns:
            (alpha_phase, alpha_local) tuple
        """
        # Update EMA
        if self.ppl_ema is None:
            self.ppl_ema = current_ppl
        else:
            self.ppl_ema = self.ema_decay * self.ppl_ema + (1 - self.ema_decay) * current_ppl

        ppl = self.ppl_ema

        # Compute alpha_phase based on PPL
        if ppl >= self.ppl_high:
            alpha_phase = self.alpha_high
        elif ppl <= self.ppl_low:
            alpha_phase = self.alpha_low
        else:
            # Linear interpolation
            alpha_phase = self.alpha_low + (ppl - self.ppl_low) * (self.alpha_high - self.alpha_low) / (self.ppl_high - self.ppl_low)

        alpha_local = 1.0 - alpha_phase

        # Log transition when we cross the midpoint (PPL ~550)
        midpoint_ppl = (self.ppl_high + self.ppl_low) / 2
        if not self.transition_logged and self.ppl_ema < midpoint_ppl:
            print(f"🔄 [PPL-Alpha] Phase→Local transition: PPL={self.ppl_ema:.1f} < {midpoint_ppl:.0f}")
            print(f"   α_phase: {self.alpha_high:.2f} → {alpha_phase:.2f}, α_local: {1-self.alpha_high:.2f} → {alpha_local:.2f}")
            self.transition_logged = True
            self.last_transition_ppl = self.ppl_ema

        self.current_alpha_phase = alpha_phase
        self.current_alpha_local = alpha_local

        # Adaptive window size (step change at midpoint)
        if self.enable_adaptive_window:
            old_window = self.current_window_size
            if ppl >= midpoint_ppl:
                self.current_window_size = self.window_size_high_ppl
            else:
                self.current_window_size = self.window_size_low_ppl

            # Log window transition
            if not self.window_transition_logged and old_window != self.current_window_size:
                print(f"📐 [PPL-Alpha] Window size transition: {old_window} → {self.current_window_size}")
                self.window_transition_logged = True

        return alpha_phase, alpha_local

    def get_alphas(self) -> tuple:
        """Return current alpha values."""
        return self.current_alpha_phase, self.current_alpha_local

    def get_window_size(self) -> int:
        """Return current window size (None if adaptive window disabled)."""
        return self.current_window_size

    def get_status(self) -> str:
        """Return status string for logging."""
        if self.ppl_ema is None:
            return "PPL-Alpha: not initialized"
        status = f"PPL-Alpha: EMA={self.ppl_ema:.1f}, α_phase={self.current_alpha_phase:.2f}, α_local={self.current_alpha_local:.2f}"
        if self.enable_adaptive_window:
            status += f", window={self.current_window_size}"
        return status

    def state_dict(self) -> dict:
        """Return state for checkpointing."""
        return {
            "ppl_ema": self.ppl_ema,
            "current_alpha_phase": self.current_alpha_phase,
            "current_alpha_local": self.current_alpha_local,
            "transition_logged": self.transition_logged,
            "last_transition_ppl": self.last_transition_ppl,
        }

    def load_state_dict(self, state: dict):
        """Restore state from checkpoint."""
        self.ppl_ema = state.get("ppl_ema")
        self.current_alpha_phase = state.get("current_alpha_phase", self.alpha_high)
        self.current_alpha_local = state.get("current_alpha_local", 1.0 - self.alpha_high)
        self.transition_logged = state.get("transition_logged", False)
        self.last_transition_ppl = state.get("last_transition_ppl")


class ResonanceStateScheduler:
    """
    Implements the Rational Sovereign Sequence (RSS) for staged engagement
    of auxiliary gradient systems based on PPL thresholds.

    The key insight: Layer dependencies require careful ordering.
    - Layer 7 (CSR) feeds into Layer 9 (Kosha)
    - If CSR is actively shifting Layer 7 semantics, Kosha learns "orphaned" mappings
    - Solution: Stagger engagement so each layer stabilizes before the next builds on it

    Engagement Order (SAFEST → RISKIEST):
    1. EvoFlow   (PPL < 100) - Internal coherence, distributed gradients
    2. Toroidal  (PPL < 60)  - Feedback loops need stable grammar
    3. CSR       (PPL < 45)  - Semantic shift with linear warm-up (2500 steps)
    4. Kosha     (PPL < 35)  - Only after CSR earthquake settles (weight > 0.5)

    The "Stagger is the Secret" - CSR and Kosha must NOT engage together.
    CSR causes a "semantic earthquake" at Layer 7. Kosha must wait for the
    dust to settle before defining "State of Reality" at Layer 9.

    HYSTERESIS: Once a component engages, it stays engaged permanently.
    This prevents bounce behavior from PPL fluctuations during training.
    Components cannot disengage once they pass their PPL threshold.

    Usage:
        controller = ResonanceStateScheduler(config)
        # In training loop:
        weights = controller.get_gate_weights(current_ppl, global_step)
        # Apply weights to auxiliary losses
    """

    # Phase names for logging
    PHASE_FOUNDATION = "FOUNDATION"      # PPL > 100, only LM loss
    PHASE_COHERENCE = "COHERENCE"        # PPL < 100, EvoFlow active
    PHASE_FEEDBACK = "FEEDBACK"          # PPL < 60, Toroidal active
    PHASE_ONTOLOGY = "ONTOLOGY"          # PPL < 45, CSR warming up
    PHASE_SOVEREIGN = "SOVEREIGN"        # PPL < 35, Kosha active

    def __init__(
        self,
        # PPL thresholds for engagement
        evoflow_ppl_threshold: float = 100.0,
        toroidal_ppl_threshold: float = 60.0,
        csr_ppl_threshold: float = 45.0,
        kosha_ppl_threshold: float = 35.0,
        # Warm-up configuration
        csr_warmup_steps: int = 2500,
        kosha_csr_weight_threshold: float = 0.5,  # Kosha waits for CSR > 0.5
        # Optional: use validation PPL (more stable) vs training PPL
        use_val_ppl: bool = True,
    ):
        self.evoflow_ppl_threshold = evoflow_ppl_threshold
        self.toroidal_ppl_threshold = toroidal_ppl_threshold
        self.csr_ppl_threshold = csr_ppl_threshold
        self.kosha_ppl_threshold = kosha_ppl_threshold

        self.csr_warmup_steps = csr_warmup_steps
        self.kosha_csr_weight_threshold = kosha_csr_weight_threshold
        self.use_val_ppl = use_val_ppl

        # State tracking - HYSTERESIS: once engaged, stay engaged
        self.evoflow_engaged = False     # EvoFlow permanent engagement flag
        self.toroidal_engaged = False    # Toroidal permanent engagement flag
        self.csr_engage_step = None      # Step when CSR first engaged
        self.kosha_engage_step = None    # Step when Kosha first engaged
        self.current_phase = self.PHASE_FOUNDATION

        # Phase transition logging
        self.phase_history = []
        self._last_logged_phase = None

    def get_gate_weights(
        self,
        current_ppl: float,
        global_step: int,
        val_ppl: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Calculate dynamic weights for each auxiliary system based on PPL.

        Args:
            current_ppl: Current training PPL (from loss)
            global_step: Current training step
            val_ppl: Optional validation PPL (used if use_val_ppl=True)

        Returns:
            Dict with weights for: 'evoflow', 'toroidal', 'csr', 'kosha'
            Weights range from 0.0 (detached) to 1.0 (fully engaged)
        """
        # Use validation PPL if available and configured
        ppl = val_ppl if (self.use_val_ppl and val_ppl is not None) else current_ppl

        # Initialize weights (all detached by default)
        weights = {
            'evoflow': 0.0,
            'toroidal': 0.0,
            'csr': 0.0,
            'kosha': 0.0,
        }

        # Phase 1: EvoFlow (Internal Coherence)
        # HYSTERESIS: Once engaged, stay engaged permanently
        if ppl < self.evoflow_ppl_threshold:
            self.evoflow_engaged = True
        if self.evoflow_engaged:
            weights['evoflow'] = 1.0

        # Phase 2: Toroidal (Global Feedback)
        # HYSTERESIS: Once engaged, stay engaged permanently
        if ppl < self.toroidal_ppl_threshold:
            self.toroidal_engaged = True
        if self.toroidal_engaged:
            weights['toroidal'] = 1.0

        # Phase 3: CSR (Semantic Earthquake) - with linear warm-up
        # HYSTERESIS: Once csr_engage_step is set, CSR stays engaged
        if ppl < self.csr_ppl_threshold:
            if self.csr_engage_step is None:
                self.csr_engage_step = global_step
        if self.csr_engage_step is not None:
            # Linear warm-up: 0.0 → 1.0 over csr_warmup_steps
            elapsed = global_step - self.csr_engage_step
            weights['csr'] = min(1.0, elapsed / self.csr_warmup_steps)

        # Phase 4: Kosha (Sovereign Synthesis)
        # Only engages when:
        # 1. PPL < kosha_ppl_threshold
        # 2. CSR has warmed up past the threshold (earthquake settling)
        # HYSTERESIS: Once kosha_engage_step is set, Kosha stays engaged
        if ppl < self.kosha_ppl_threshold and weights['csr'] >= self.kosha_csr_weight_threshold:
            if self.kosha_engage_step is None:
                self.kosha_engage_step = global_step
        if self.kosha_engage_step is not None:
            weights['kosha'] = 1.0

        # Update phase tracking
        self._update_phase(weights, ppl, global_step)

        return weights

    def _update_phase(self, weights: Dict[str, float], ppl: float, step: int):
        """Update current phase and log transitions."""
        # Determine current phase from weights
        if weights['kosha'] > 0:
            new_phase = self.PHASE_SOVEREIGN
        elif weights['csr'] > 0:
            new_phase = self.PHASE_ONTOLOGY
        elif weights['toroidal'] > 0:
            new_phase = self.PHASE_FEEDBACK
        elif weights['evoflow'] > 0:
            new_phase = self.PHASE_COHERENCE
        else:
            new_phase = self.PHASE_FOUNDATION

        # Log phase transition
        if new_phase != self.current_phase:
            self.phase_history.append({
                'step': step,
                'ppl': ppl,
                'from_phase': self.current_phase,
                'to_phase': new_phase,
                'weights': weights.copy(),
            })
            self.current_phase = new_phase

    def get_phase_transition_message(self) -> Optional[str]:
        """Get message for phase transition (call once per step for logging)."""
        if self.current_phase != self._last_logged_phase:
            self._last_logged_phase = self.current_phase

            phase_icons = {
                self.PHASE_FOUNDATION: "🏗️",
                self.PHASE_COHERENCE: "🔄",
                self.PHASE_FEEDBACK: "🌀",
                self.PHASE_ONTOLOGY: "📜",
                self.PHASE_SOVEREIGN: "👑",
            }

            phase_descriptions = {
                self.PHASE_FOUNDATION: "Foundation (LM only)",
                self.PHASE_COHERENCE: "Coherence (EvoFlow active)",
                self.PHASE_FEEDBACK: "Feedback (Toroidal active)",
                self.PHASE_ONTOLOGY: "Ontology (CSR warming up)",
                self.PHASE_SOVEREIGN: "Sovereign (Full RSS active)",
            }

            icon = phase_icons.get(self.current_phase, "❓")
            desc = phase_descriptions.get(self.current_phase, self.current_phase)

            return f"{icon} [RSS] Phase Transition → {desc}"
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get current controller status for logging/debugging."""
        return {
            'phase': self.current_phase,
            'engaged': {
                'evoflow': self.evoflow_engaged,
                'toroidal': self.toroidal_engaged,
                'csr': self.csr_engage_step is not None,
                'kosha': self.kosha_engage_step is not None,
            },
            'csr_engage_step': self.csr_engage_step,
            'kosha_engage_step': self.kosha_engage_step,
            'csr_warmup_progress': (
                None if self.csr_engage_step is None
                else "warming up"
            ),
            'phase_transitions': len(self.phase_history),
            'thresholds': {
                'evoflow': self.evoflow_ppl_threshold,
                'toroidal': self.toroidal_ppl_threshold,
                'csr': self.csr_ppl_threshold,
                'kosha': self.kosha_ppl_threshold,
            },
        }


def update_alpha_schedule(model: "torch.nn.Module", step: int, config: "Any") -> float:
    """
    Update alpha_phase for HybridAttentionLayer modules based on decay schedule.

    Returns current alpha_phase value.
    """
    # V9.8.10: Check if model type contains "hybrid" or "phase" (supports ontological_hybrid)
    if "hybrid" not in config.model_type and "phase" not in config.model_type:
        return config.alpha_phase  # No alpha scheduling for pure ontological/standard models

    # Calculate current alpha based on linear decay
    # V9.8.10: Use phase_ramp_steps if available (more intuitive), fallback to alpha_decay_steps
    decay_steps = getattr(config, 'phase_ramp_steps', config.alpha_decay_steps)
    if step >= decay_steps:
        current_alpha = config.alpha_phase_end
    else:
        frac = step / decay_steps
        current_alpha = config.alpha_phase_start + frac * (config.alpha_phase_end - config.alpha_phase_start)

    # Update all HybridAttentionLayer modules
    for module in model.modules():
        if hasattr(module, 'alpha_phase') and isinstance(module.alpha_phase, torch.nn.Parameter):
            module.alpha_phase.data.fill_(current_alpha)
            if hasattr(module, 'alpha_local'):
                module.alpha_local.data.fill_(1.0 - current_alpha)

    return current_alpha
