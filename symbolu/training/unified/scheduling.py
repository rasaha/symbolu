import math
import logging
import torch
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


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
