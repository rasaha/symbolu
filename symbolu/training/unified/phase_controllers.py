"""
Phase controllers for training intervention and adaptive hyperparameter tuning.

Contains the Sovereign Phase Controller (graduated intervention system)
and the Adaptive Training Controller (dynamic LR/Kp adjustment).

Split from scheduling.py
"""

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

        V11.3 FIX: Variance-only should NOT trigger CRITICAL. Low variance
        just means entropy is stable — that's fine when entropy itself is
        healthy (e.g. 0.5). Only trigger CRITICAL when entropy is truly
        collapsed. Low variance + moderate entropy → warning at most.

        Returns:
            'critical', 'warning', 'caution', or 'normal'
        """
        # Critical: Entropy truly collapsed (regardless of variance)
        if entropy < self.entropy_critical:
            return 'critical'

        # Warning: Entropy somewhat low AND stagnant (stuck in bad place)
        elif entropy < 0.45 and variance < self.variance_critical:
            return 'warning'

        # Caution: Entropy at warning level, OR stagnant below recovery
        elif entropy < self.entropy_warning:
            return 'caution'
        elif variance < self.variance_critical and entropy < self.entropy_recovered:
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
        # V10.23: Spike-aware boost dampening
        max_boost_from_base: float = 2.0,         # Max LR = base_lr * this (cap compounding)
        spike_dampen_threshold: int = 10,          # If >=N params spiked after last boost, dampen next
        boost_cooldown_steps: int = 400,           # Min steps between boosts
    ):
        self.optimizer = optimizer
        self.base_lr = base_lr
        self.lr_min = lr_min
        # V9.8.2: Clamp lr_max to max_lr_relative * base_lr
        self.lr_max = min(lr_max, base_lr * max_lr_relative)
        self.lr_boost_factor = lr_boost_factor
        self.lr_decay_factor = lr_decay_factor
        # V9.9.1: Reference to scheduler so LR boosts persist through cosine decay
        self._scheduler = None

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

        # V10.23: Spike-aware boost dampening
        self._grad_variance_tracker = None  # Set via set_grad_variance_tracker()
        self._last_boost_step = 0  # Step of last LR boost
        self._max_boost_from_base: float = max_boost_from_base  # Max LR as multiple of base_lr
        self._spike_dampen_threshold: int = spike_dampen_threshold  # Spike count to trigger dampening
        self._boost_cooldown_steps: int = boost_cooldown_steps  # Min steps between boosts

        print(f"\n  [AdaptiveTraining] Controller initialized:")
        print(f"    Base LR: {base_lr:.2e} (range: {lr_min:.2e} - {self.lr_max:.2e})")
        print(f"    Velocity thresholds: slow < {velocity_slow_threshold}%, spike > {velocity_spike_threshold}%")
        print(f"    Kp range: {kp_min} - {kp_max} (base: {kp_base})")
        print(f"    V9.8.2 Safeguards: max_relative={max_lr_relative}x, loss_spike={loss_spike_threshold}%")
        print(f"    V10.23: Boost cap={max_boost_from_base}x base, spike_dampen>={spike_dampen_threshold} params, cooldown={boost_cooldown_steps} steps")
        print(f"    Plateau detection: {plateau_window} evals, {plateau_threshold}% threshold")
        print(f"    V9.9.1: Scheduler-aware LR adjustments ENABLED")

    def set_scheduler(self, scheduler):
        """V9.9.1: Link to scheduler so LR boosts/decays persist through cosine decay."""
        self._scheduler = scheduler

    def set_grad_variance_tracker(self, tracker):
        """V10.23: Link to gradient variance tracker for spike-aware boost dampening."""
        self._grad_variance_tracker = tracker

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
                # V9.9.1: Also update scheduler base_lr so decay persists through cosine schedule
                if self._scheduler is not None and hasattr(self._scheduler, 'adjust_base_lr'):
                    self._scheduler.adjust_base_lr(new_lr)
                self.decay_count += 1
                adjustments["actions"].append(f"LR_DECAY: {current_lr:.2e}→{new_lr:.2e} (spike: {velocity:+.1f}%)")
                print(f"\n  🔻 [AdaptiveTraining] LR DECAY: {current_lr:.2e} → {new_lr:.2e} (PPL spike: {velocity:+.1f}%)")
                self.last_adjustment_step = global_step

        # Case 2: Learning too slow or plateau → boost LR (V9.8.2: only if not blocked)
        elif (velocity > self.velocity_slow_threshold or is_plateau) and not self.boost_blocked:
            if is_plateau:
                self.plateau_count += 1

            # Skip futile boosts: if cosine schedule has decayed below lr_min floor,
            # boosting base_lr just gets cosine-decayed back below floor within a few
            # steps. The floor clamp already maintains lr_min — boosting is pointless.
            cosine_below_floor = (
                self._scheduler is not None and
                hasattr(self._scheduler, '_get_cosine_lr') and
                self._scheduler._get_cosine_lr() < self.lr_min
            )

            if cosine_below_floor:
                reason = "plateau" if is_plateau else f"slow: {velocity:.1f}%"
                if not hasattr(self, '_floor_boost_skip_logged') or not self._floor_boost_skip_logged:
                    print(f"\n  ⏸️  [AdaptiveTraining] LR BOOST SKIPPED ({reason}) - cosine schedule below floor, boost would be futile")
                    self._floor_boost_skip_logged = True
            else:
                # V10.23: Cooldown — don't boost if too soon after last boost
                steps_since_boost = global_step - self._last_boost_step
                if self._last_boost_step > 0 and steps_since_boost < self._boost_cooldown_steps:
                    reason = "plateau" if is_plateau else f"slow: {velocity:.1f}%"
                    print(f"\n  ⏸️  [AdaptiveTraining] LR BOOST COOLDOWN ({reason}) - {steps_since_boost}/{self._boost_cooldown_steps} steps since last boost")
                else:
                    # V10.23: Compute effective boost factor with spike dampening
                    effective_boost = self.lr_boost_factor

                    # Check if previous boost caused widespread spikes
                    if self._grad_variance_tracker is not None and self._last_boost_step > 0:
                        spike_count = self._grad_variance_tracker.get_spike_count_since(self._last_boost_step)
                        if spike_count >= self._spike_dampen_threshold:
                            # Linear dampening: threshold(10)→0.75x, 2x threshold(20)→0.5x, 4x threshold(40)→no boost
                            dampen = max(0.0, 1.0 - spike_count / (self._spike_dampen_threshold * 4))
                            effective_boost = 1.0 + (self.lr_boost_factor - 1.0) * dampen
                            print(f"\n  🛡️  [AdaptiveTraining] BOOST DAMPENED: {spike_count} params spiked after last boost → factor {self.lr_boost_factor:.2f} → {effective_boost:.3f}")

                    # V10.23: Hard cap — never exceed max_boost_from_base * base_lr
                    hard_cap = self.base_lr * self._max_boost_from_base
                    new_lr = min(self.lr_max, hard_cap, current_lr * effective_boost)

                    if new_lr > current_lr:
                        for pg in self.optimizer.param_groups:
                            pg['lr'] = new_lr
                        # V9.9.1: Also update scheduler base_lr so boost persists through cosine decay
                        if self._scheduler is not None and hasattr(self._scheduler, 'adjust_base_lr'):
                            self._scheduler.adjust_base_lr(new_lr)
                        self.boost_count += 1
                        self._last_boost_step = global_step
                        reason = "plateau" if is_plateau else f"slow: {velocity:.1f}%"
                        adjustments["actions"].append(f"LR_BOOST: {current_lr:.2e}→{new_lr:.2e} ({reason})")
                        print(f"\n  🔺 [AdaptiveTraining] LR BOOST: {current_lr:.2e} → {new_lr:.2e} ({reason})")
                        self.last_adjustment_step = global_step
                    elif new_lr <= current_lr:
                        reason = "plateau" if is_plateau else f"slow: {velocity:.1f}%"
                        print(f"\n  ⏸️  [AdaptiveTraining] LR BOOST CAPPED ({reason}) - already at {current_lr:.2e} (cap: {hard_cap:.2e})")
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
            # Only log floor clamp once, then every 100 steps to avoid spam
            if not hasattr(self, '_floor_clamp_logged_step') or global_step - self._floor_clamp_logged_step >= 100:
                print(f"\n  ⚠️ [AdaptiveTraining] LR FLOOR: {current_lr:.2e} → {self.lr_min:.2e} (cosine schedule below floor, clamping)")
                self._floor_clamp_logged_step = global_step
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


# =============================================================================
# V10.22: Adaptive Slot Memory LR Controller
# =============================================================================
# Dynamically adjusts the slot param group LR scale based on:
#   - retr_loss velocity (plateau → boost, spike → decay)
#   - slot ablation delta (neutral → boost, helping → hold)
#   - write_gate level (too low → boost to prevent slot shutdown)
# Also maintains the slot LR ratio when the main LR changes.
# =============================================================================

class AdaptiveSlotLRController:
    """
    Three-phase proportional slot LR controller.

    Phase 1 (bootstrap): Fixed slot LR — waits for warmup_complete signal from
                         the training loop (PPL-based or step-based) AND sufficient
                         signal history before adapting. No arbitrary step count.
    Phase 2 (adaptive):  Continuous proportional control via exponential update:
                         LR_slot(t+1) = LR_slot(t) * e^(eta * s)
                         where s = weighted health score from write gate, retr loss
                         velocity, and ablation delta. Smooth — no discrete jumps.
    Phase 3 (stabilize): Freeze slot LR to lock in the converged scale.

    Auto-enabled when slot memory params are present. No CLI flag needed.
    """

    def __init__(
        self,
        optimizer,
        initial_scale: float = 0.1,
        scale_min: float = 0.1,
        scale_max: float = 0.8,
        # Proportional controller gain
        eta: float = 0.03,
        # Health score component weights (sum to ~1)
        weight_gate: float = 0.4,
        weight_retr_velocity: float = 0.35,
        weight_ablation: float = 0.25,
        # Gate target for health score
        target_gate: float = 0.20,
        # Phase transition thresholds
        min_observations_for_phase2: int = 3,  # Need at least N signal observations before adapting
        stabilize_after_steps: Optional[int] = None,  # None = never auto-freeze
        stabilize_scale_variance_threshold: float = 0.005,  # Auto-freeze when scale variance drops below this
        # History
        history_window: int = 5,
        # V16.1: Tied coherence floor — derives coherence floor from scale
        coherence_floor_initial: float = 0.3,
    ):
        self.optimizer = optimizer
        self.current_scale = initial_scale
        self.scale_min = scale_min
        self.scale_max = scale_max
        self.eta = eta
        self.weight_gate = weight_gate
        self.weight_retr_velocity = weight_retr_velocity
        self.weight_ablation = weight_ablation
        self.target_gate = target_gate
        self.min_observations_for_phase2 = min_observations_for_phase2
        self.stabilize_after_steps = stabilize_after_steps
        self.stabilize_scale_variance_threshold = stabilize_scale_variance_threshold
        self.history_window = history_window

        # V16.1: Tied coherence floor
        self.coherence_floor_initial = coherence_floor_initial

        # State
        self.retr_loss_history: List[float] = []
        self.ablation_delta_history: List[float] = []
        self.write_gate_history: List[float] = []
        self.scale_history: List[float] = []  # For detecting convergence
        self.phase: int = 1  # 1=bootstrap, 2=adaptive, 3=stabilized
        self.phase_transitions: List[Dict] = []
        self.total_updates: int = 0
        self.cumulative_signal: float = 0.0  # Running sum of health scores

    def record_retr_loss(self, retr_loss: float):
        self.retr_loss_history.append(retr_loss)
        if len(self.retr_loss_history) > 30:
            self.retr_loss_history = self.retr_loss_history[-30:]

    def record_ablation_delta(self, delta: float):
        self.ablation_delta_history.append(delta)
        if len(self.ablation_delta_history) > 15:
            self.ablation_delta_history = self.ablation_delta_history[-15:]

    def record_write_gate(self, write_gate: float):
        self.write_gate_history.append(write_gate)
        if len(self.write_gate_history) > 30:
            self.write_gate_history = self.write_gate_history[-30:]

    def _compute_health_score(self) -> Optional[float]:
        """
        Compute composite slot health score s in roughly [-1, +1].
        Positive = slots need more LR (boost), negative = slots need less (decay).

        V11.1: Fixed three signal bugs that created a death spiral:
        1. Gate signal penalized gate being above target (normal operation)
        2. Retr velocity treated improvement as "hold" instead of "boost"
        3. Together they kept health score permanently negative → LR at floor
        """
        signals = []
        weights = []

        # Signal 1: Write gate — only penalize extremes
        # V11.1: Gate above target is normal healthy operation (not a decay signal).
        # Only signal negative if gate is collapsed near floor, or so high it's
        # writing noise. The "sweet spot" range [floor*1.5, target*2] is neutral.
        if self.write_gate_history:
            recent_wg = self.write_gate_history[-self.history_window:]
            gate_mean = sum(recent_wg) / len(recent_wg)
            gate_floor = 0.05  # Match slot memory gate_floor default
            if gate_mean < gate_floor * 1.5:
                # Gate collapsed — boost LR to rescue
                gate_signal = 0.5
            elif gate_mean > self.target_gate * 3.0:
                # Gate too open — writing everything, back off
                gate_signal = -0.5
            else:
                # Normal operation — neutral
                gate_signal = 0.0
            signals.append(gate_signal)
            weights.append(self.weight_gate)

        # Signal 2: Retrieval loss velocity
        # V11.1: Improving retr_loss = slots are learning useful content.
        # This should be a POSITIVE signal (boost LR to learn faster),
        # not "hold" as before. Only back off if retr_loss is spiking.
        if len(self.retr_loss_history) >= self.history_window:
            recent = self.retr_loss_history[-self.history_window:]
            if recent[0] != 0:
                velocity_pct = ((recent[-1] - recent[0]) / abs(recent[0])) * 100
                # Improving (negative velocity) → positive signal (boost, learning works)
                # Plateau (near zero) → slight positive (try harder)
                # Spiking (positive velocity) → negative (back off)
                # Flip sign: improvement should boost, not suppress
                vel_signal = max(-1.0, min(1.0, -velocity_pct / 20.0))
                signals.append(vel_signal)
                weights.append(self.weight_retr_velocity)

        # Signal 3: Ablation delta
        # V11.1: When ablation delta ≈ 0, this is ambiguous (could mean slots
        # haven't specialized yet, not that they're harmful). Use asymmetric
        # response: negative delta is a clear "decay" signal, but zero/small
        # positive should be neutral, not a strong signal either way.
        if self.ablation_delta_history:
            last_delta = self.ablation_delta_history[-1]
            if last_delta < -1.0:
                # Slots actively hurting — strong decay signal
                abl_signal = max(-1.0, last_delta / 5.0)
            elif last_delta > 1.0:
                # Slots helping — moderate boost to consolidate
                abl_signal = min(0.5, last_delta / 10.0)
            else:
                # Near zero — neutral (don't suppress based on ambiguity)
                abl_signal = 0.0
            signals.append(abl_signal)
            weights.append(self.weight_ablation)

        if not signals:
            return None

        # Weighted average
        total_weight = sum(weights)
        score = sum(s * w for s, w in zip(signals, weights)) / total_weight
        return score

    def update(self, global_step: int, warmup_complete: bool = False) -> Dict[str, Any]:
        """
        Three-phase update. Call at eval time.

        Args:
            global_step: Current training step.
            warmup_complete: Whether LR warmup has finished (PPL-based or step-based).
                Phase 1→2 transition requires this AND sufficient signal history.

        Returns dict with phase info and any scale change.
        """
        actions: Dict[str, Any] = {"step": global_step, "phase": self.phase, "adjustments": []}

        # --- Phase 1→2: requires warmup done + enough observations to compute health ---
        if self.phase == 1 and warmup_complete:
            n_obs = len(self.write_gate_history) + len(self.retr_loss_history)
            if n_obs >= self.min_observations_for_phase2:
                self.phase = 2
                self.phase_transitions.append({"from": 1, "to": 2, "step": global_step})
                print(f"  [SLOT-LR] Phase 1→2: warmup complete + {n_obs} observations, "
                      f"entering proportional control (scale={self.current_scale:.4f})")

        if self.phase == 2:
            # Check for auto-stabilize: scale variance over recent window
            # V11.1: Don't freeze if scale is pinned at a boundary — that's
            # low variance from clamping, not genuine convergence. Only
            # stabilize when scale has settled in the interior of [min, max].
            if len(self.scale_history) >= 10:
                recent_scales = self.scale_history[-10:]
                mean_s = sum(recent_scales) / len(recent_scales)
                variance = sum((x - mean_s) ** 2 for x in recent_scales) / len(recent_scales)
                at_boundary = (mean_s <= self.scale_min * 1.05 or
                               mean_s >= self.scale_max * 0.95)
                if variance < self.stabilize_scale_variance_threshold and not at_boundary:
                    self.phase = 3
                    self.phase_transitions.append({"from": 2, "to": 3, "step": global_step,
                                                   "reason": f"scale_converged (var={variance:.6f})"})
                    print(f"  [SLOT-LR] Phase 2→3: scale converged at {self.current_scale:.4f} "
                          f"(var={variance:.6f}), freezing")

            # Hard step limit for stabilize
            if self.phase == 2 and self.stabilize_after_steps is not None:
                if global_step >= self.stabilize_after_steps:
                    self.phase = 3
                    self.phase_transitions.append({"from": 2, "to": 3, "step": global_step,
                                                   "reason": "step_limit"})
                    print(f"  [SLOT-LR] Phase 2→3: step limit reached, freezing at scale={self.current_scale:.4f}")

        # --- Phase 1: Hold fixed ---
        if self.phase == 1:
            self.sync_slot_lr()
            return actions

        # --- Phase 3: Frozen (with escape hatch) ---
        # V11.1: If frozen at a boundary (scale ≈ min or max), allow re-entry
        # to phase 2 if health score suggests the freeze was premature.
        # This breaks the death spiral where bad signals → floor → "converged."
        if self.phase == 3:
            at_floor = self.current_scale <= self.scale_min * 1.05
            at_ceiling = self.current_scale >= self.scale_max * 0.95
            if at_floor or at_ceiling:
                health_score = self._compute_health_score()
                # If health says boost but we're at floor (or decay but at ceiling),
                # the freeze was premature — re-enter phase 2
                if health_score is not None:
                    should_unfreeze = (at_floor and health_score > 0.1) or \
                                     (at_ceiling and health_score < -0.1)
                    if should_unfreeze:
                        self.phase = 2
                        self.phase_transitions.append({
                            "from": 3, "to": 2, "step": global_step,
                            "reason": f"boundary_escape (scale={self.current_scale:.4f}, "
                                      f"health={health_score:+.3f})"
                        })
                        print(f"  [SLOT-LR] Phase 3→2: unfreezing from boundary "
                              f"(scale={self.current_scale:.4f}, health={health_score:+.3f})")
                        # Fall through to phase 2 processing below
            if self.phase == 3:
                self.sync_slot_lr()
                return actions

        # --- Phase 2: Proportional control ---
        health_score = self._compute_health_score()
        if health_score is None:
            self.sync_slot_lr()
            return actions

        old_scale = self.current_scale
        # Exponential update: scale *= e^(eta * s)
        self.current_scale *= math.exp(self.eta * health_score)
        # Clamp
        self.current_scale = max(self.scale_min, min(self.scale_max, self.current_scale))

        self.scale_history.append(self.current_scale)
        if len(self.scale_history) > 50:
            self.scale_history = self.scale_history[-50:]

        self.total_updates += 1
        self.cumulative_signal += health_score

        delta = self.current_scale - old_scale
        if abs(delta) > 1e-6:
            main_lr = self.optimizer.param_groups[0]['lr']
            new_slot_lr = main_lr * self.current_scale
            print(f"  [SLOT-LR] scale {old_scale:.4f} → {self.current_scale:.4f} "
                  f"(s={health_score:+.3f}, slot_lr={new_slot_lr:.2e})")
            actions["adjustments"].append({
                "old_scale": old_scale,
                "new_scale": self.current_scale,
                "health_score": health_score,
            })

        self.sync_slot_lr()
        return actions

    def get_coherence_floor(self) -> float:
        """V16.1: Derive coherence floor from current scale and phase.

        Inversely tracks scale: when scale is low (slots struggling),
        floor is high (permissive writes). When scale is high (slots
        thriving), floor drops (strict coherence filtering). Phase 3
        always returns 0 (fully locked down).
        """
        if self.coherence_floor_initial <= 0:
            return 0.0
        if self.phase == 3:
            return 0.0
        # Normalize scale position within [scale_min, scale_max]
        scale_range = self.scale_max - self.scale_min
        if scale_range <= 0:
            return 0.0
        scale_frac = (self.current_scale - self.scale_min) / scale_range
        scale_frac = max(0.0, min(1.0, scale_frac))
        # Invert: high scale → low floor, low scale → high floor
        return self.coherence_floor_initial * (1.0 - scale_frac)

    def sync_slot_lr(self):
        """Ensure slot param group LR = main_lr * current_scale."""
        if len(self.optimizer.param_groups) < 2:
            return
        main_lr = self.optimizer.param_groups[0]['lr']
        self.optimizer.param_groups[1]['lr'] = main_lr * self.current_scale

    def get_status_string(self) -> str:
        health = self._compute_health_score()
        h_str = f"{health:+.3f}" if health is not None else "N/A"
        phase_names = {1: "bootstrap", 2: "adaptive", 3: "stabilized"}
        coh_floor = self.get_coherence_floor()
        return (f"SlotLR: phase={phase_names[self.phase]} scale={self.current_scale:.4f} "
                f"health={h_str} coh_floor={coh_floor:.3f} updates={self.total_updates}")

    def state_dict(self) -> Dict[str, Any]:
        return {
            "current_scale": self.current_scale,
            "phase": self.phase,
            "retr_loss_history": self.retr_loss_history,
            "ablation_delta_history": self.ablation_delta_history,
            "write_gate_history": self.write_gate_history,
            "scale_history": self.scale_history,
            "total_updates": self.total_updates,
            "cumulative_signal": self.cumulative_signal,
            "phase_transitions": self.phase_transitions,
            "coherence_floor_initial": self.coherence_floor_initial,
        }

    def load_state_dict(self, state: Dict[str, Any]):
        self.current_scale = state.get("current_scale", self.current_scale)
        self.phase = state.get("phase", self.phase)
        self.retr_loss_history = state.get("retr_loss_history", [])
        self.ablation_delta_history = state.get("ablation_delta_history", [])
        self.write_gate_history = state.get("write_gate_history", [])
        self.scale_history = state.get("scale_history", [])
        self.total_updates = state.get("total_updates", 0)
        self.cumulative_signal = state.get("cumulative_signal", 0.0)
        self.phase_transitions = state.get("phase_transitions", [])
        self.coherence_floor_initial = state.get("coherence_floor_initial", self.coherence_floor_initial)
