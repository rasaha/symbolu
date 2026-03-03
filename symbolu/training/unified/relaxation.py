"""
Dynamic Relaxation Controller for managing 9:3 -> 6:6 split transitions.

Monitors Sattvic Stability Index and triggers relaxation with dampened thaw,
weight transfer, and Guna-Lock.

Extracted from train_unified_llm.py
"""

import math
from typing import Optional, Dict, List, Tuple, Any

import torch
import torch.nn as nn

from symbolu.training.unified.gradient_control import HierarchicalGradientScaler, WeightTransfer


class DynamicRelaxationController:
    """
    Manages dynamic transition from 9:3 (Authority-heavy) to 6:6 (Balanced) split.

    The controller monitors a StabilityIndex and triggers relaxation when the
    model has achieved sufficient "Sattvic Plateau" - meaning the Authority
    layers have firmly imprinted ontological structure.

    Phases:
    1. AUTHORITY (9:3): Heavy dampening, ontological imprinting
    2. MONITORING: Track StabilityIndex over rolling window
    3. RELAXATION: Transition to 6:6 with Dampened Thaw
    4. BALANCED (6:6): Increased sensory expressivity
    5. RECOVERY: Viparyaya reset if PPL spikes after relaxation

    StabilityIndex = 0.7 * GC + 0.3 * (1 - S_Drift_EMA)

    Usage:
        controller = DynamicRelaxationController(gradient_scaler, model, config)
        # In training loop:
        should_relax, action = controller.update(guna_coherence, s_drift_ema, val_ppl, step)
        if action == "RELAX":
            controller.execute_relaxation(current_step=step)  # Triggers WeightTransfer + Guna-Lock
        elif action == "RECOVER":
            controller.execute_recovery()  # Releases Guna-Lock
    """

    # Controller states
    STATE_AUTHORITY = "AUTHORITY"       # 9:3 split, heavy dampening
    STATE_MONITORING = "MONITORING"     # Tracking stability for transition
    STATE_RELAXING = "RELAXING"         # Transitioning to 6:6
    STATE_BALANCED = "BALANCED"         # 6:6 split, balanced learning
    STATE_RECOVERY = "RECOVERY"         # Viparyaya reset, back to 9:3

    def __init__(
        self,
        gradient_scaler: HierarchicalGradientScaler,
        model: nn.Module,
        # Stability thresholds
        stability_threshold: float = 0.82,
        stability_window: int = 500,        # Steps for stability check (rolling window)
        streak_target: int = 5,             # Consecutive stable evals for 'consecutive' mode
        mode: str = "consecutive",          # "consecutive", "average", or "sa_ratio"
        # Split configurations
        authority_split: Tuple[int, int] = (9, 3),  # Initial 9:3
        balanced_split: Tuple[int, int] = (6, 6),   # Target 6:6
        # Dampening configurations
        authority_alpha_max: float = 0.5,    # α ceiling for 9:3
        balanced_alpha_max: float = 0.7,     # α ceiling for 6:6
        thaw_alpha_start: float = 0.05,      # Dampened Thaw start for new layers
        thaw_warmup_steps: int = 250,        # Steps to ramp new layers
        # Recovery settings
        ppl_spike_threshold: float = 0.20,   # 20% PPL increase triggers recovery
        recovery_steps: int = 200,           # Steps to stay in recovery
        # Monitoring
        guna_coherence_weight: float = 0.7,
        s_drift_weight: float = 0.3,
        # Weight Transfer settings
        guna_lock_steps: int = 50,           # Steps to freeze W_q/W_k post-swap
        enable_weight_transfer: bool = True,  # Enable weight transfer during relaxation
        # Force relaxation at specific step (bypasses stability check)
        force_relaxation_step: int = None,   # If set, force 9:3→6:6 at this step
        # Sovereign Saturation Gate (automatic detection)
        enable_saturation_gate: bool = True,  # Enable automatic saturation detection
        saturation_coherence_threshold: float = 0.74,  # Coherence threshold for trigger
        saturation_patience: int = 50,        # Steps where sensory derivative must be flat
        saturation_thaw_start: float = 0.3,   # New sensory layers start at this α
        saturation_thaw_end: float = 0.7,     # Ramp to this α
        saturation_thaw_steps: int = 100,     # Steps to ramp new layers
    ):
        self.gradient_scaler = gradient_scaler
        self.model = model

        # Thresholds
        self.stability_threshold = stability_threshold
        self.stability_window = stability_window
        self.streak_target = streak_target
        self.mode = mode.lower()
        self.ppl_spike_threshold = ppl_spike_threshold
        self.recovery_steps = recovery_steps

        # Validate mode
        if self.mode not in ("consecutive", "average", "sa_ratio"):
            raise ValueError(f"relaxation_mode must be 'consecutive', 'average', or 'sa_ratio', got '{mode}'")

        # Split configurations
        self.authority_split = authority_split
        self.balanced_split = balanced_split
        self.authority_alpha_max = authority_alpha_max
        self.balanced_alpha_max = balanced_alpha_max
        self.thaw_alpha_start = thaw_alpha_start
        self.thaw_warmup_steps = thaw_warmup_steps

        # Weights for StabilityIndex
        self.guna_coherence_weight = guna_coherence_weight
        self.s_drift_weight = s_drift_weight

        # Weight Transfer for 9:3 → 6:6 transition
        self.enable_weight_transfer = enable_weight_transfer
        self.guna_lock_steps = guna_lock_steps

        # Force relaxation at specific step
        self.force_relaxation_step = force_relaxation_step
        self.force_relaxation_triggered = False  # Track if we've already forced

        # Sovereign Saturation Gate
        self.enable_saturation_gate = enable_saturation_gate
        self.saturation_coherence_threshold = saturation_coherence_threshold
        self.saturation_patience = saturation_patience
        self.saturation_thaw_start = saturation_thaw_start
        self.saturation_thaw_end = saturation_thaw_end
        self.saturation_thaw_steps = saturation_thaw_steps
        # Saturation tracking
        self.sensory_flow_history = []  # Track sensory flow for derivative
        self.saturation_flat_count = 0  # Count of steps with flat derivative
        self.saturation_triggered = False  # Track if saturation gate fired
        self.saturation_thaw_step = None  # Step when thaw started

        # V9.5.0 Dynamic Streak Controller: Entropy-triggered flip
        self.metabolic_step_counter = 0   # Consecutive steps meeting validity criteria
        self.metabolic_entropy_threshold = 0.45  # Below this = looping, need fast escape
        self.metabolic_vram_safety = 0.90  # Don't flip if VRAM > 90%
        self._current_target_streak = 500  # Dynamic target (50 or 500 based on entropy)

        # V9.5.1 Multi-Stage Granular Evolution: 9:3 → 6:6 → 5:7 → 4:8 → 3:9
        self.evolution_stages = [(9, 3), (6, 6), (5, 7), (4, 8), (3, 9)]
        self.current_stage_idx = 0  # Start at 9:3
        self.evolution_streak = 0   # Steps meeting evolution criteria
        self.evolution_patience = 200  # Steps needed to trigger next stage
        self.evolution_entropy_floor = 0.42  # Abort if entropy drops below this
        self.evolution_coherence_min = 0.82  # Must maintain high coherence

        # V9.9.1 Multi-Stage Evolution with PPL/Step triggers
        self.evolution_trigger_mode = "metrics"  # "metrics", "ppl", "step", "auto"
        self.evolution_ppl_triggers = []  # PPL thresholds: [100, 50, 25, 15]
        self.evolution_step_triggers = []  # Step triggers: [10000, 30000, 50000, 70000]
        self.evolution_ppl_window = 10  # Steps to average PPL for smoother triggers
        self.evolution_thaw_alpha = 0.1  # Initial gradient scale for new sensory layers
        self.evolution_thaw_steps = 300  # Steps to ramp new sensory layer gradients
        self.ppl_history = []  # Rolling PPL history for averaging
        self.evolution_ppl_triggered = [False] * 10  # Track which PPL triggers fired
        self.evolution_step_triggered = [False] * 10  # Track which step triggers fired

        # V9.5.2 Emergency Stress-Probe (Phase A: 3:9 Rajas)
        self.stress_probe_active = False  # Currently in stress-probe mode
        self.stress_probe_start_step = None  # When stress-probe started
        self.stress_probe_degeneracy_streak = 0  # Consecutive evals of degeneracy detection
        self.stress_probe_exit_streak = 0  # Consecutive evals meeting exit criteria
        self.pre_stress_probe_split = None  # Split before stress-probe (to restore)
        self.pre_stress_probe_lr = None  # LR before stress-probe (to restore)
        self.stress_probe_steps_in = 0  # Steps spent in stress-probe
        # Gradual LR restore tracking (ChatGPT guardrail)
        self.stress_probe_lr_restoring = False  # Currently restoring LR
        self.stress_probe_lr_restore_start_step = None  # When LR restore started
        self.stress_probe_reduced_lr = None  # The reduced LR during stress-probe

        # [S5] Entropy Gate: Block relaxation if entropy too high
        self.entropy_gate_threshold = 0.50  # Must be below this to relax
        self.entropy_gate_blocked = False   # Track if we blocked due to entropy
        self.last_entropy = None            # For logging
        if enable_weight_transfer:
            # Layers 6, 7, 8 become Sensory in 6:6 split
            # Layer 5 becomes the new Witness
            self.weight_transfer = WeightTransfer(
                model=model,
                guna_lock_steps=guna_lock_steps,
                anchor_layer_idx=balanced_split[0] - 1,  # New Witness is layer 5 in 6:6
                transferred_layers=(6, 7, 8),  # These layers change from Authority to Sensory
            )
        else:
            self.weight_transfer = None

        # State tracking
        self.state = self.STATE_AUTHORITY
        self.stability_streak = 0
        self.stability_history = []
        self.ssi_rolling_window = []  # For average mode
        self.sa_rolling_window = []   # For sa_ratio mode
        self.max_history = 1000

        # PPL tracking for recovery
        self.pre_relaxation_ppl = None
        self.recovery_start_step = None
        self.relaxation_step = None

        # Integration Tax tracking (Jolt Log)
        self.integration_tax_logged = False
        self.post_relaxation_ppl_samples = []
        self.integration_tax_sample_count = 10  # Steps to wait before measuring

        # Telemetry
        self.transitions = []
        self.current_split = authority_split

        print(f"\n  [DynamicRelaxation] Controller initialized:")
        print(f"    Mode: {self.mode.upper()}")
        print(f"    Initial split: {authority_split[0]}:{authority_split[1]}")
        print(f"    Target split: {balanced_split[0]}:{balanced_split[1]}")
        print(f"    Stability threshold: {stability_threshold}")
        print(f"    Stability window: {stability_window} steps")
        if enable_weight_transfer:
            print(f"    Weight Transfer: ENABLED")
            print(f"    Guna-Lock: {guna_lock_steps} steps post-swap")
        if force_relaxation_step is not None:
            print(f"    ⚡ Force Relaxation: Step {force_relaxation_step} (bypasses stability check)")
        if enable_saturation_gate:
            print(f"    🎯 Saturation Gate: ENABLED")
            print(f"       Coherence threshold: {saturation_coherence_threshold}")
            print(f"       Patience: {saturation_patience} steps flat derivative")
            print(f"       Dampened Thaw: α {saturation_thaw_start}→{saturation_thaw_end} over {saturation_thaw_steps} steps")

    def compute_stability_index(
        self,
        guna_coherence: float,
        s_drift_ema: float,
    ) -> float:
        """
        Compute the Sattvic Stability Index.

        StabilityIndex = w_gc * GC + w_drift * (1 - S_Drift_EMA)

        High values indicate:
        - GC high: Authority layers have locked global phase rotation
        - S_Drift low: Reality signal aligned with ontological intent
        """
        # Input validation - clamp and warn on out-of-bounds values
        if not (0.0 <= guna_coherence <= 1.0):
            guna_coherence = max(0.0, min(1.0, guna_coherence))
        if not (0.0 <= s_drift_ema <= 1.0):
            s_drift_ema = max(0.0, min(1.0, s_drift_ema))

        # Handle NaN/Inf gracefully
        if math.isnan(guna_coherence) or math.isinf(guna_coherence):
            guna_coherence = 0.5
        if math.isnan(s_drift_ema) or math.isinf(s_drift_ema):
            s_drift_ema = 0.5

        stability = (
            self.guna_coherence_weight * guna_coherence +
            self.s_drift_weight * (1.0 - s_drift_ema)
        )
        return max(0.0, min(1.0, stability))

    def _check_relaxation_ready(self, stability_index: float, sa_ratio: float = None) -> bool:
        """
        Check if relaxation should trigger based on current mode.

        Modes:
        - consecutive: Requires SSI >= threshold for N consecutive steps
        - average: Requires average SSI >= threshold over rolling N-step window
        - sa_ratio: Requires average S/A ratio >= threshold over rolling N-step window
        """
        if self.mode == "consecutive":
            # Consecutive mode: reset on any dip, use streak_target for trigger
            if stability_index >= self.stability_threshold:
                self.stability_streak += 1
                return self.stability_streak >= self.streak_target
            else:
                self.stability_streak = 0
                return False

        elif self.mode == "sa_ratio":
            # S/A Ratio mode: rolling window mean of S/A ratio
            if sa_ratio is None:
                return False

            self.sa_rolling_window.append(sa_ratio)
            if len(self.sa_rolling_window) > self.stability_window:
                self.sa_rolling_window.pop(0)

            if len(self.sa_rolling_window) >= self.stability_window:
                avg_sa = sum(self.sa_rolling_window) / len(self.sa_rolling_window)
                self.stability_streak = len(self.sa_rolling_window)  # For display
                return avg_sa >= self.stability_threshold

            self.stability_streak = len(self.sa_rolling_window)
            return False

        else:  # average mode (SSI-based)
            # Average mode: rolling window mean
            self.ssi_rolling_window.append(stability_index)
            if len(self.ssi_rolling_window) > self.stability_window:
                self.ssi_rolling_window.pop(0)

            if len(self.ssi_rolling_window) >= self.stability_window:
                avg_ssi = sum(self.ssi_rolling_window) / len(self.ssi_rolling_window)
                return avg_ssi >= self.stability_threshold

            return False

    def _check_saturation_gate(
        self,
        coherence: float,
        sensory_flow: float,
        global_step: int,
    ) -> bool:
        """
        Sovereign Saturation Gate: Detect when sensory layers are saturated.

        Triggers when:
        1. Coherence >= saturation_coherence_threshold (0.74)
        2. Sensory flow derivative is flat for saturation_patience steps (50)

        Returns True if saturation detected and relaxation should trigger.
        """
        if not self.enable_saturation_gate or self.saturation_triggered:
            return False

        # Check coherence threshold first
        if coherence < self.saturation_coherence_threshold:
            self.saturation_flat_count = 0  # Reset if coherence drops
            return False

        # Track sensory flow history
        self.sensory_flow_history.append(sensory_flow)
        if len(self.sensory_flow_history) > self.saturation_patience + 10:
            self.sensory_flow_history.pop(0)

        # Need enough history to compute derivative
        if len(self.sensory_flow_history) < 10:
            return False

        # Compute derivative (change over last 10 steps)
        recent = self.sensory_flow_history[-10:]
        derivative = abs(recent[-1] - recent[0]) / 10.0

        # Check if derivative is "flat" (< 0.001 change per step)
        # Sensory flow at 1.00 means it's saturated
        is_saturated = sensory_flow >= 0.99 or derivative < 0.001

        if is_saturated:
            self.saturation_flat_count += 1
        else:
            self.saturation_flat_count = max(0, self.saturation_flat_count - 1)

        # Trigger if flat for patience steps
        if self.saturation_flat_count >= self.saturation_patience:
            self.saturation_triggered = True
            self.saturation_thaw_step = global_step
            return True

        return False

    def check_metabolic_flip(
        self,
        metrics: Dict[str, float],
        vram_usage: float,
        global_step: int,
    ) -> str:
        """
        V9.5.0 Dynamic Streak Controller: Entropy-triggered 9:3 → 6:6 flip.

        Key insight: Entropy determines streak LENGTH, VRAM determines streak VALIDITY.
        - Low entropy (<0.45) = looping = SHORT streak (50) to escape quickly
        - High entropy (>0.45) = learning = LONG streak (500) to solidify

        Validity criteria (must pass every step):
        1. Coherence > 0.74 (Sattvic stability)
        2. VRAM < 90% (safety gate)

        If validity fails, counter resets to 0.
        Returns "TRIGGER_FLIP" when dynamic target reached.
        """
        if self.saturation_triggered:
            return "ALREADY_FLIPPED"

        coherence = metrics.get('coherence', 0.0)
        entropy = metrics.get('entropy', 1.0)

        # 1. Validity Criteria (must pass to increment counter)
        is_stable = coherence > self.saturation_coherence_threshold  # 0.74
        is_safe = vram_usage < self.metabolic_vram_safety            # 0.90

        # 2. Dynamic Streak Target based on Entropy
        # Low entropy = looping/repetition = need SHORT streak to escape
        # High entropy = still learning = need LONG streak to solidify
        if entropy < self.metabolic_entropy_threshold:  # 0.45
            target_streak = 50   # Emergency "Escape" Mode - break loops fast
        else:
            target_streak = 500  # Standard "Sattvic" Mode - let authority crystallize

        # 3. Increment or Reset Counter (based on validity, not entropy)
        if is_stable and is_safe:
            self.metabolic_step_counter += 1
        else:
            self.metabolic_step_counter = 0  # Hard reset if validity fails

        # 4. Execute Flip when dynamic target reached
        if self.metabolic_step_counter >= target_streak:
            self.saturation_triggered = True
            self.saturation_thaw_step = global_step
            mode = "ESCAPE" if entropy < self.metabolic_entropy_threshold else "SATTVIC"
            print(f"\n  🚀 [DYNAMIC FLIP] Step {global_step}: {mode} mode - target {target_streak} reached")
            print(f"      Coherence: {coherence:.3f} > 0.74 ✓")
            print(f"      Entropy:   {entropy:.3f} {'< 0.45 (looping)' if entropy < 0.45 else '>= 0.45 (learning)'}")
            print(f"      VRAM:      {vram_usage*100:.1f}% < 90% ✓")
            return "TRIGGER_FLIP"

        # Store current target for status display
        self._current_target_streak = target_streak
        return "WAITING"

    def check_granular_evolution(
        self,
        metrics: Dict[str, float],
        vram_usage: float,
        global_step: int,
    ) -> str:
        """
        V9.5.1 Granular Evolution: Check for multi-stage transitions.

        After 6:6, can evolve to 5:7 → 4:8 → 3:9 based on:
        - Coherence > 0.82 (stability)
        - Entropy > 0.42 (diversity floor - prevent repetition curse)
        - VRAM < 90% (safety)

        Triggers when criteria met for evolution_patience steps (200).
        """
        # Only check if we're past the initial 6:6 stage
        if self.current_stage_idx < 1:
            return "NOT_READY"

        # Already at final stage (3:9)
        if self.current_stage_idx >= len(self.evolution_stages) - 1:
            return "FINAL_STAGE"

        coherence = metrics.get('coherence', 0.0)
        entropy = metrics.get('entropy', 1.0)

        # Evolution criteria (different from initial flip)
        is_stable = coherence > self.evolution_coherence_min  # 0.82
        is_diverse = entropy > self.evolution_entropy_floor   # 0.42 - MUST have diversity
        is_safe = vram_usage < self.metabolic_vram_safety     # 0.90

        # Key insight: We want to evolve when STIFF (low entropy) but stable
        # This breaks the repetition curse by adding sensory capacity
        wants_evolution = entropy < 0.45 and coherence > 0.85  # Stiff but stable

        if is_stable and is_safe and (is_diverse or wants_evolution):
            self.evolution_streak += 1
        else:
            self.evolution_streak = 0  # Hard reset

        # Trigger evolution when patience reached
        if self.evolution_streak >= self.evolution_patience:
            next_stage = self.evolution_stages[self.current_stage_idx + 1]
            return f"EVOLVE_TO_{next_stage[0]}_{next_stage[1]}"

        return "WAITING"

    def execute_granular_evolution(self, global_step: int) -> Tuple[int, int]:
        """
        Execute transition to next evolution stage.

        Returns the new (authority, sensory) split.
        """
        if self.current_stage_idx >= len(self.evolution_stages) - 1:
            return self.current_split

        # Advance to next stage
        self.current_stage_idx += 1
        new_split = self.evolution_stages[self.current_stage_idx]

        # Reset evolution streak for next stage
        self.evolution_streak = 0

        # Update current split
        self.current_split = new_split

        # Print evolution message
        prev_split = self.evolution_stages[self.current_stage_idx - 1]
        print(f"\n  🌀 [GRANULAR EVOLUTION] Step {global_step}")
        print(f"      {prev_split[0]}:{prev_split[1]} → {new_split[0]}:{new_split[1]}")
        print(f"      Authority layers: 0-{new_split[0]-1}")
        print(f"      Sensory layers: {new_split[0]}-11")
        print(f"      Transitional layer: {new_split[0]} (newly sensory)")

        return new_split

    def configure_evolution(
        self,
        trigger_mode: str = "auto",
        ppl_triggers: str = "",
        step_triggers: str = "",
        custom_stages: str = "",
        patience: int = 200,
        coherence_min: float = 0.82,
        entropy_floor: float = 0.42,
        ppl_window: int = 10,
        thaw_alpha: float = 0.1,
        thaw_steps: int = 300,
    ):
        """
        V9.9.1 Configure multi-stage evolution from config parameters.

        Args:
            trigger_mode: "metrics", "ppl", "step", or "auto"
            ppl_triggers: Comma-separated PPL thresholds (e.g., "100,50,25,15")
            step_triggers: Comma-separated step thresholds (e.g., "10000,30000,50000,70000")
            custom_stages: Comma-separated stages (e.g., "9:3,6:6,4:8,3:9")
            patience: Steps of stable metrics before evolution (metrics mode)
            coherence_min: Minimum coherence for evolution (metrics mode)
            entropy_floor: Minimum entropy for evolution (metrics mode)
            ppl_window: Steps to average PPL for smoother triggers
            thaw_alpha: Initial gradient scale for newly sensory layers
            thaw_steps: Steps to ramp newly sensory layer gradients
        """
        self.evolution_trigger_mode = trigger_mode.lower()
        self.evolution_patience = patience
        self.evolution_coherence_min = coherence_min
        self.evolution_entropy_floor = entropy_floor
        self.evolution_ppl_window = ppl_window
        self.evolution_thaw_alpha = thaw_alpha
        self.evolution_thaw_steps = thaw_steps

        # Parse PPL triggers
        if ppl_triggers:
            try:
                self.evolution_ppl_triggers = [float(x.strip()) for x in ppl_triggers.split(",") if x.strip()]
                self.evolution_ppl_triggered = [False] * len(self.evolution_ppl_triggers)
            except ValueError:
                print(f"  ⚠️ [EVOLUTION] Invalid PPL triggers: {ppl_triggers}, using empty list")
                self.evolution_ppl_triggers = []

        # Parse step triggers
        if step_triggers:
            try:
                self.evolution_step_triggers = [int(x.strip()) for x in step_triggers.split(",") if x.strip()]
                self.evolution_step_triggered = [False] * len(self.evolution_step_triggers)
            except ValueError:
                print(f"  ⚠️ [EVOLUTION] Invalid step triggers: {step_triggers}, using empty list")
                self.evolution_step_triggers = []

        # Parse custom stages
        if custom_stages:
            try:
                stages = []
                for stage in custom_stages.split(","):
                    parts = stage.strip().split(":")
                    if len(parts) == 2:
                        auth, sens = int(parts[0]), int(parts[1])
                        if auth + sens == 12:  # Validate 12-layer model
                            stages.append((auth, sens))
                        else:
                            print(f"  ⚠️ [EVOLUTION] Stage {stage} doesn't sum to 12, skipping")
                if stages:
                    self.evolution_stages = stages
                    print(f"  🔧 [EVOLUTION] Custom stages: {' → '.join(f'{a}:{s}' for a, s in stages)}")
            except ValueError:
                print(f"  ⚠️ [EVOLUTION] Invalid custom stages: {custom_stages}, using default")

        # Auto-detect best mode if "auto"
        if self.evolution_trigger_mode == "auto":
            if self.evolution_ppl_triggers:
                self.evolution_trigger_mode = "ppl"
            elif self.evolution_step_triggers:
                self.evolution_trigger_mode = "step"
            else:
                self.evolution_trigger_mode = "metrics"

        # Log configuration
        print(f"\n  🧬 [MULTI-STAGE EVOLUTION] Configuration:")
        print(f"      Trigger mode: {self.evolution_trigger_mode.upper()}")
        print(f"      Stages: {' → '.join(f'{a}:{s}' for a, s in self.evolution_stages)}")
        if self.evolution_trigger_mode == "ppl" and self.evolution_ppl_triggers:
            print(f"      PPL triggers: {self.evolution_ppl_triggers}")
        elif self.evolution_trigger_mode == "step" and self.evolution_step_triggers:
            print(f"      Step triggers: {self.evolution_step_triggers}")
        else:
            print(f"      Metrics: coherence>{coherence_min}, entropy>{entropy_floor}, patience={patience}")
        print(f"      Thaw: α={thaw_alpha}→0.7 over {thaw_steps} steps")

    def check_evolution_triggers(
        self,
        metrics: Dict[str, float],
        vram_usage: float,
        global_step: int,
        current_ppl: float = None,
    ) -> str:
        """
        V9.9.1 Unified evolution trigger check supporting multiple modes.

        Args:
            metrics: Training metrics dict (coherence, entropy, etc.)
            vram_usage: Current VRAM utilization (0-1)
            global_step: Current training step
            current_ppl: Current validation PPL (optional, for PPL mode)

        Returns:
            "EVOLVE_TO_X_Y" if should evolve, "WAITING"/"NOT_READY"/etc. otherwise
        """
        # Only check if we're past the initial 9:3 stage
        if self.current_stage_idx < 1:
            return "NOT_READY"

        # Already at final stage
        if self.current_stage_idx >= len(self.evolution_stages) - 1:
            return "FINAL_STAGE"

        # Safety: VRAM check applies to all modes
        if vram_usage >= self.metabolic_vram_safety:
            return "VRAM_UNSAFE"

        # Track PPL history for smoothing
        if current_ppl is not None:
            self.ppl_history.append(current_ppl)
            if len(self.ppl_history) > self.evolution_ppl_window:
                self.ppl_history.pop(0)

        # Mode-specific trigger logic
        if self.evolution_trigger_mode == "ppl":
            return self._check_ppl_evolution(current_ppl, global_step)
        elif self.evolution_trigger_mode == "step":
            return self._check_step_evolution(global_step)
        else:  # "metrics" mode (default)
            return self.check_granular_evolution(metrics, vram_usage, global_step)

    def _check_ppl_evolution(self, current_ppl: float, global_step: int) -> str:
        """
        Check if PPL has dropped below the next trigger threshold.

        Uses smoothed PPL (average over window) to avoid noise-triggered evolutions.
        """
        if not self.evolution_ppl_triggers:
            return "NO_PPL_TRIGGERS"

        if current_ppl is None or len(self.ppl_history) < 3:
            return "WAITING_PPL"

        # Use smoothed PPL
        smoothed_ppl = sum(self.ppl_history) / len(self.ppl_history)

        # Find the next untriggered PPL threshold
        next_trigger_idx = self.current_stage_idx  # stages are 0-indexed, triggers map to transitions
        if next_trigger_idx >= len(self.evolution_ppl_triggers):
            return "ALL_PPL_TRIGGERS_USED"

        trigger_ppl = self.evolution_ppl_triggers[next_trigger_idx]

        # Check if PPL has dropped below threshold
        if smoothed_ppl <= trigger_ppl and not self.evolution_ppl_triggered[next_trigger_idx]:
            self.evolution_ppl_triggered[next_trigger_idx] = True
            next_stage = self.evolution_stages[self.current_stage_idx + 1]
            print(f"\n  📉 [PPL EVOLUTION] Smoothed PPL {smoothed_ppl:.2f} <= {trigger_ppl}")
            print(f"      Triggering evolution to {next_stage[0]}:{next_stage[1]}")
            return f"EVOLVE_TO_{next_stage[0]}_{next_stage[1]}"

        return "WAITING"

    def _check_step_evolution(self, global_step: int) -> str:
        """
        Check if training has reached the next step trigger.
        """
        if not self.evolution_step_triggers:
            return "NO_STEP_TRIGGERS"

        # Find the next untriggered step threshold
        next_trigger_idx = self.current_stage_idx  # stages are 0-indexed
        if next_trigger_idx >= len(self.evolution_step_triggers):
            return "ALL_STEP_TRIGGERS_USED"

        trigger_step = self.evolution_step_triggers[next_trigger_idx]

        # Check if step has been reached
        if global_step >= trigger_step and not self.evolution_step_triggered[next_trigger_idx]:
            self.evolution_step_triggered[next_trigger_idx] = True
            next_stage = self.evolution_stages[self.current_stage_idx + 1]
            print(f"\n  📊 [STEP EVOLUTION] Step {global_step} >= {trigger_step}")
            print(f"      Triggering evolution to {next_stage[0]}:{next_stage[1]}")
            return f"EVOLVE_TO_{next_stage[0]}_{next_stage[1]}"

        return "WAITING"

    def get_evolution_status(self) -> Dict[str, any]:
        """
        Get current evolution status for logging/display.
        """
        current = self.evolution_stages[self.current_stage_idx]
        next_stage = None
        if self.current_stage_idx < len(self.evolution_stages) - 1:
            next_stage = self.evolution_stages[self.current_stage_idx + 1]

        status = {
            "current_stage": f"{current[0]}:{current[1]}",
            "stage_idx": self.current_stage_idx,
            "total_stages": len(self.evolution_stages),
            "next_stage": f"{next_stage[0]}:{next_stage[1]}" if next_stage else "FINAL",
            "trigger_mode": self.evolution_trigger_mode,
            "evolution_streak": self.evolution_streak,
        }

        if self.evolution_trigger_mode == "ppl" and self.evolution_ppl_triggers:
            next_idx = min(self.current_stage_idx, len(self.evolution_ppl_triggers) - 1)
            status["next_ppl_trigger"] = self.evolution_ppl_triggers[next_idx] if next_idx < len(self.evolution_ppl_triggers) else None
            if self.ppl_history:
                status["smoothed_ppl"] = sum(self.ppl_history) / len(self.ppl_history)
        elif self.evolution_trigger_mode == "step" and self.evolution_step_triggers:
            next_idx = min(self.current_stage_idx, len(self.evolution_step_triggers) - 1)
            status["next_step_trigger"] = self.evolution_step_triggers[next_idx] if next_idx < len(self.evolution_step_triggers) else None

        return status

    def check_stress_probe(
        self,
        metrics: Dict[str, float],
        config,
        global_step: int,
    ) -> str:
        """
        V9.5.2 Emergency Stress-Probe Detection.

        ChatGPT Guardrails: Compound trigger confirmation
        - Low entropy (< 0.42) is REQUIRED
        - AND at least ONE of: REP-3 > 0.18, UTR < 0.55, DRS > 12
        - Must hold for 2 consecutive evals

        Gemini Protocol: Freeze Authority, flood with Sensory to break stiffness.
        """
        if not config.enable_stress_probe:
            return "DISABLED"

        # Don't trigger if already in stress-probe
        if self.stress_probe_active:
            return "ALREADY_ACTIVE"

        coherence = metrics.get('coherence', 0.0)
        entropy = metrics.get('entropy', 1.0)
        rep3 = metrics.get('rep3', 0.0)  # REP-3 from quality metrics
        utr = metrics.get('utr', 1.0)  # Unique Token Ratio
        drs = metrics.get('drs', 0.0)  # Degeneracy Repetition Score

        # ChatGPT Guardrails: Conservative compound trigger
        # Requirement 1: Model must be stiff (high coherence)
        is_stiff = coherence > config.stress_probe_coherence_min  # 0.80

        # Requirement 2: Low entropy (REQUIRED)
        is_low_entropy = entropy < config.stress_probe_entropy_trigger  # 0.42

        # Requirement 3: At least ONE degeneracy signal
        has_high_rep3 = rep3 > config.stress_probe_rep3_trigger  # 0.18
        has_low_utr = utr < config.stress_probe_utr_trigger  # 0.55
        has_high_drs = drs > config.stress_probe_drs_trigger  # 12

        has_degeneracy_signal = has_high_rep3 or has_low_utr or has_high_drs

        # Compound trigger: stiff AND low_entropy AND at_least_one_signal
        is_degenerate = is_stiff and is_low_entropy and has_degeneracy_signal

        if is_degenerate:
            self.stress_probe_degeneracy_streak += 1
            # Log degeneracy detection for debugging
            if self.stress_probe_degeneracy_streak == 1:
                signals = []
                if has_high_rep3:
                    signals.append(f"REP-3={rep3:.3f}>{config.stress_probe_rep3_trigger}")
                if has_low_utr:
                    signals.append(f"UTR={utr:.3f}<{config.stress_probe_utr_trigger}")
                if has_high_drs:
                    signals.append(f"DRS={drs:.1f}>{config.stress_probe_drs_trigger}")
                print(f"  ⚠️ [STRESS-PROBE] Degeneracy detected: Ent={entropy:.3f}, {', '.join(signals)}")
        else:
            self.stress_probe_degeneracy_streak = 0

        # Trigger after patience consecutive evals of degeneracy (ChatGPT: 2)
        if self.stress_probe_degeneracy_streak >= config.stress_probe_patience:
            return "TRIGGER_STRESS_PROBE"

        return "MONITORING"

    def execute_stress_probe(
        self,
        config,
        current_lr: float,
        global_step: int,
    ) -> Tuple[Tuple[int, int], float]:
        """
        Execute transition to 3:9 stress-probe mode.

        Returns: (new_split, new_lr)
        - Jumps to 3:9 split (nearly all Sensory)
        - Reduces LR to stress_probe_lr_factor (65%)
        - Records pre-stress-probe state for restoration
        """
        # Save current state for restoration
        self.pre_stress_probe_split = self.current_split
        self.pre_stress_probe_lr = current_lr

        # Activate stress-probe
        self.stress_probe_active = True
        self.stress_probe_start_step = global_step
        self.stress_probe_steps_in = 0
        self.stress_probe_degeneracy_streak = 0  # Reset

        # Jump to 3:9 (Phase A: Rajas)
        new_split = (3, 9)
        self.current_split = new_split

        # Also update stage index to reflect 3:9
        self.current_stage_idx = len(self.evolution_stages) - 1  # Final stage

        # Reduce LR
        new_lr = current_lr * config.stress_probe_lr_factor

        print(f"\n  🚨 [STRESS-PROBE] EMERGENCY ACTIVATION - Step {global_step}")
        print(f"      {self.pre_stress_probe_split[0]}:{self.pre_stress_probe_split[1]} → 3:9 (Phase A: Rajas)")
        print(f"      Authority Scale: {config.stress_probe_authority_scale} (nearly frozen)")
        print(f"      LR: {current_lr:.6f} → {new_lr:.6f} ({config.stress_probe_lr_factor*100:.0f}%)")
        print(f"      Exit Criteria: Ent > {config.stress_probe_exit_entropy} OR REP-3 < {config.stress_probe_exit_rep3}")
        print(f"      Max Steps: {config.stress_probe_max_steps}")

        return new_split, new_lr

    def check_stress_probe_exit(
        self,
        metrics: Dict[str, float],
        config,
        global_step: int,
    ) -> str:
        """
        Check if stress-probe should exit.

        ChatGPT Guardrails:
        - Minimum 100 steps (don't exit early)
        - Exit when Entropy > 0.55 for 2 consecutive evals
        - Maximum 300 steps (forced exit)
        """
        if not self.stress_probe_active:
            return "NOT_ACTIVE"

        self.stress_probe_steps_in += 1

        entropy = metrics.get('entropy', 0.0)
        rep3 = metrics.get('rep3', 1.0)

        # ChatGPT Guardrail: Enforce minimum steps
        if self.stress_probe_steps_in < config.stress_probe_min_steps:
            return "CONTINUE"

        # Success criteria: diversity restored
        entropy_ok = entropy > config.stress_probe_exit_entropy  # 0.55
        rep3_ok = rep3 < config.stress_probe_exit_rep3  # 0.12

        # ChatGPT Guardrail: Require 2 consecutive evals meeting exit criteria
        if entropy_ok:
            self.stress_probe_exit_streak += 1
        else:
            self.stress_probe_exit_streak = 0

        # Forced exit: max steps reached
        max_reached = self.stress_probe_steps_in >= config.stress_probe_max_steps

        # Exit success: 2 consecutive good evals (ChatGPT: entropy > 0.55 for 2 evals)
        if self.stress_probe_exit_streak >= 2 and rep3_ok:
            return "EXIT_SUCCESS"
        elif max_reached:
            return "EXIT_FORCED"

        # Log progress every 50 steps during stress-probe
        if self.stress_probe_steps_in % 50 == 0:
            print(f"  📊 [STRESS-PROBE] Step {self.stress_probe_steps_in}/{config.stress_probe_max_steps}: "
                  f"Ent={entropy:.3f}, REP-3={rep3:.3f}, exit_streak={self.stress_probe_exit_streak}")

        return "CONTINUE"

    def exit_stress_probe(
        self,
        global_step: int,
        exit_reason: str,
        config,
    ) -> Tuple[Tuple[int, int], float]:
        """
        Exit stress-probe and return to 6:6 (Sattva).

        ChatGPT Guardrails:
        - Return to 6:6, not 9:3
        - Gradual LR restore over ~50 steps
        - Re-enable adaptive LR after 100 steps

        Returns: (new_split, initial_lr_for_restore)
        """
        # Return to 6:6 (not pre-stress-probe split - we want balanced digestion)
        new_split = (6, 6)
        self.current_split = new_split
        self.current_stage_idx = 1  # 6:6 stage

        # Record stress-probe statistics
        duration = self.stress_probe_steps_in

        # Deactivate stress-probe but setup gradual LR restore
        self.stress_probe_active = False
        self.stress_probe_steps_in = 0
        self.stress_probe_exit_streak = 0

        # ChatGPT Guardrail: Gradual LR restore over ~50 steps
        self.stress_probe_lr_restoring = True
        self.stress_probe_lr_restore_start_step = global_step
        self.stress_probe_reduced_lr = self.pre_stress_probe_lr * config.stress_probe_lr_factor

        print(f"\n  ✅ [STRESS-PROBE] EXIT - Step {global_step}")
        print(f"      Reason: {exit_reason}")
        print(f"      Duration: {duration} steps")
        print(f"      3:9 → 6:6 (Phase B: Sattva - Digestion)")
        print(f"      LR Restore: {self.stress_probe_reduced_lr:.6f} → {self.pre_stress_probe_lr:.6f}")
        print(f"      Restore Steps: {config.stress_probe_lr_restore_steps}")

        # Return reduced LR (gradual restore will ramp up)
        return new_split, self.stress_probe_reduced_lr

    def get_stress_probe_restore_lr(
        self,
        global_step: int,
        config,
    ) -> float:
        """
        Compute LR during gradual restore period after stress-probe exit.

        ChatGPT Guardrail: Restore LR gradually over ~50 steps.
        """
        if not self.stress_probe_lr_restoring:
            return self.pre_stress_probe_lr

        steps_since_exit = global_step - self.stress_probe_lr_restore_start_step

        # Check if restore complete
        if steps_since_exit >= config.stress_probe_lr_restore_steps:
            self.stress_probe_lr_restoring = False
            print(f"  ✓ [STRESS-PROBE] LR restore complete: {self.pre_stress_probe_lr:.6f}")
            return self.pre_stress_probe_lr

        # Linear ramp from reduced_lr to pre_stress_probe_lr
        progress = steps_since_exit / config.stress_probe_lr_restore_steps
        current_lr = self.stress_probe_reduced_lr + progress * (
            self.pre_stress_probe_lr - self.stress_probe_reduced_lr
        )

        return current_lr

    def update_stability_per_step(self, coherence: float, sa_ratio: float = None) -> None:
        """
        V9.4.9: Update stability streak every gradient step (not just at validation).

        This ensures the streak counter reflects actual gradient steps, not log intervals.
        """
        if self.state != self.STATE_AUTHORITY:
            return  # Only track during authority phase

        if self.mode == "consecutive":
            # Consecutive mode: streak of coherence >= threshold
            stability = coherence  # Use raw coherence for simplicity
            if stability >= self.stability_threshold:
                self.stability_streak += 1
            else:
                self.stability_streak = 0  # Hard reset

        elif self.mode == "sa_ratio" and sa_ratio is not None:
            # S/A ratio mode: rolling window
            self.sa_rolling_window.append(sa_ratio)
            if len(self.sa_rolling_window) > self.stability_window:
                self.sa_rolling_window.pop(0)
            self.stability_streak = len(self.sa_rolling_window)

        else:  # average mode
            self.ssi_rolling_window.append(coherence)
            if len(self.ssi_rolling_window) > self.stability_window:
                self.ssi_rolling_window.pop(0)
            self.stability_streak = len(self.ssi_rolling_window)

    def get_saturation_thaw_alpha(self, global_step: int) -> float:
        """
        Compute the Dampened Thaw alpha for newly sensory layers (6, 7, 8).

        During thaw, α ramps from saturation_thaw_start (0.3) to saturation_thaw_end (0.7)
        over saturation_thaw_steps (100) steps.
        """
        if self.saturation_thaw_step is None:
            return self.saturation_thaw_start

        steps_since_thaw = global_step - self.saturation_thaw_step
        if steps_since_thaw >= self.saturation_thaw_steps:
            return self.saturation_thaw_end

        # Linear ramp
        progress = steps_since_thaw / self.saturation_thaw_steps
        alpha = self.saturation_thaw_start + progress * (self.saturation_thaw_end - self.saturation_thaw_start)
        return alpha

    def _log_integration_tax(self, current_ppl: float, global_step: int):
        """
        Log the Integration Tax: PPL difference after relaxation.

        This measures the "cost" of adding new sensory layers.
        Called for the first N steps after relaxation.
        """
        if self.integration_tax_logged:
            return

        self.post_relaxation_ppl_samples.append(current_ppl)

        if len(self.post_relaxation_ppl_samples) >= self.integration_tax_sample_count:
            # Calculate Integration Tax
            avg_post_ppl = sum(self.post_relaxation_ppl_samples) / len(self.post_relaxation_ppl_samples)
            ppl_delta = avg_post_ppl - self.pre_relaxation_ppl
            ppl_percent = (ppl_delta / self.pre_relaxation_ppl) * 100

            # Log the Jolt
            print(f"\n  ╔══════════════════════════════════════════════════════════════╗")
            print(f"  ║  📊 INTEGRATION TAX REPORT (Jolt Log)                        ║")
            print(f"  ╠══════════════════════════════════════════════════════════════╣")
            print(f"  ║  Pre-Relaxation PPL:  {self.pre_relaxation_ppl:>10.2f}                        ║")
            print(f"  ║  Post-Relaxation PPL: {avg_post_ppl:>10.2f} (avg over {self.integration_tax_sample_count} steps)        ║")
            print(f"  ║  ─────────────────────────────────────────────────────────── ║")
            print(f"  ║  Integration Tax:     {ppl_delta:>+10.2f} ({ppl_percent:+.1f}%)                   ║")
            print(f"  ║                                                              ║")
            if ppl_percent <= 5.0:
                print(f"  ║  Status: ✅ SMOOTH INTEGRATION (Tax < 5%)                   ║")
            elif ppl_percent <= 15.0:
                print(f"  ║  Status: ⚠️  MODERATE TAX (5-15%) - Thaw in progress        ║")
            else:
                print(f"  ║  Status: 🔥 HIGH TAX (>15%) - Monitor for Viparyaya         ║")
            print(f"  ╚══════════════════════════════════════════════════════════════╝\n")

            self.integration_tax_logged = True

            # Store in telemetry
            self.transitions[-1]["integration_tax"] = {
                "pre_ppl": self.pre_relaxation_ppl,
                "post_ppl": avg_post_ppl,
                "delta": ppl_delta,
                "percent": ppl_percent,
            }

    def update(
        self,
        guna_coherence: float,
        s_drift_ema: float,
        val_ppl: float,
        global_step: int,
        sa_ratio: float = None,
        entropy: float = None,
        sensory_flow: float = None,
    ) -> Tuple[bool, str]:
        """
        Update controller state based on current metrics.

        Returns:
            (state_changed, action): Whether state changed and what action to take
            action can be: "NONE", "RELAX", "RECOVER", "RESUME"

        [S5] Entropy Gate:
            Relaxation is blocked if entropy > entropy_gate_threshold (0.50).
            This prevents the model from gaining sensory freedom while confused.

        Sovereign Saturation Gate:
            Triggers relaxation when coherence >= 0.74 AND sensory flow derivative
            is flat for 50 steps (sensory layers saturated).
        """
        stability_index = self.compute_stability_index(guna_coherence, s_drift_ema)

        # Track entropy for gating
        self.last_entropy = entropy

        # Track history
        self.stability_history.append({
            "step": global_step,
            "stability": stability_index,
            "gc": guna_coherence,
            "drift": s_drift_ema,
            "ppl": val_ppl,
            "state": self.state,
            "sa_ratio": sa_ratio,
            "entropy": entropy,
        })
        if len(self.stability_history) > self.max_history:
            self.stability_history = self.stability_history[-self.max_history:]

        action = "NONE"

        # State machine
        if self.state == self.STATE_AUTHORITY:
            # Check for force relaxation at specific step (bypasses all checks)
            force_triggered = False
            if (self.force_relaxation_step is not None and
                global_step >= self.force_relaxation_step and
                not self.force_relaxation_triggered):
                force_triggered = True
                self.force_relaxation_triggered = True
                print(f"\n  ⚡ [FORCE RELAXATION] Step {global_step} >= {self.force_relaxation_step}")
                print(f"      Triggering 9:3 → 6:6 transition (bypassing stability check)")

            # Sovereign Saturation Gate: Check if sensory layers are saturated
            saturation_triggered = False
            if not force_triggered and sensory_flow is not None:
                saturation_triggered = self._check_saturation_gate(
                    coherence=guna_coherence,
                    sensory_flow=sensory_flow,
                    global_step=global_step,
                )
                if saturation_triggered:
                    print(f"\n  --> [RELAXATION] SATURATION REACHED. PIVOTING TO 6:6.")
                    print(f"      Coherence: {guna_coherence:.3f} >= {self.saturation_coherence_threshold}")
                    print(f"      Sensory Flow: {sensory_flow:.3f} (flat for {self.saturation_patience} steps)")
                    print(f"      Dampened Thaw: α {self.saturation_thaw_start}→{self.saturation_thaw_end} over {self.saturation_thaw_steps} steps")

            # Check if we should trigger relaxation (mode-dependent)
            stability_ready = self._check_relaxation_ready(stability_index, sa_ratio=sa_ratio)

            # [S5] Entropy Gate: Block relaxation if entropy too high (skipped for force/saturation trigger)
            entropy_clear = True
            if not force_triggered and not saturation_triggered and entropy is not None and entropy > self.entropy_gate_threshold:
                entropy_clear = False
                if stability_ready and not self.entropy_gate_blocked:
                    # Log that we're blocking due to entropy
                    print(f"\n  🔒 [S5 ENTROPY GATE] Relaxation BLOCKED - Ent:{entropy:.2f} > {self.entropy_gate_threshold}")
                    print(f"      Model must achieve clarity (Ent < {self.entropy_gate_threshold}) before 6:6 thaw")
                    self.entropy_gate_blocked = True
            else:
                self.entropy_gate_blocked = False

            if force_triggered or saturation_triggered or (stability_ready and entropy_clear):
                # Ready to relax!
                self.state = self.STATE_RELAXING
                self.pre_relaxation_ppl = val_ppl
                self.relaxation_step = global_step
                action = "RELAX"

                # Determine trigger mode for logging
                if force_triggered:
                    trigger_mode = "FORCED"
                elif saturation_triggered:
                    trigger_mode = "SATURATION"
                else:
                    trigger_mode = self.mode

                self.transitions.append({
                    "step": global_step,
                    "from": "AUTHORITY",
                    "to": "BALANCED",
                    "stability": stability_index,
                    "ppl": val_ppl,
                    "mode": trigger_mode,
                    "forced": force_triggered,
                    "saturation": saturation_triggered,
                })

        elif self.state == self.STATE_RELAXING:
            # Transition in progress, move to balanced
            self.state = self.STATE_BALANCED
            self.current_split = self.balanced_split
            # Reset Integration Tax tracking for new relaxation
            self.integration_tax_logged = False
            self.post_relaxation_ppl_samples = []

        elif self.state == self.STATE_BALANCED:
            # Update Guna-Lock status (release after guna_lock_steps)
            self.update_guna_lock(global_step)

            # Track Integration Tax for first N steps
            if not self.integration_tax_logged:
                self._log_integration_tax(val_ppl, global_step)

            # Monitor for PPL spike (Viparyaya trigger)
            if self.pre_relaxation_ppl is not None:
                ppl_increase = (val_ppl - self.pre_relaxation_ppl) / self.pre_relaxation_ppl
                if ppl_increase > self.ppl_spike_threshold:
                    # PPL spiked! Trigger Viparyaya recovery
                    self.state = self.STATE_RECOVERY
                    self.recovery_start_step = global_step
                    action = "RECOVER"
                    self.transitions.append({
                        "step": global_step,
                        "from": "BALANCED",
                        "to": "RECOVERY",
                        "ppl_increase": ppl_increase,
                        "ppl": val_ppl,
                    })
                    print(f"\n  ⚠️ [DynamicRelaxation] ERROR STATE TRIGGERED!")
                    print(f"    PPL spike: {ppl_increase*100:.1f}% (threshold: {self.ppl_spike_threshold*100:.0f}%)")
                    print(f"    Reverting to {self.authority_split[0]}:{self.authority_split[1]} for {self.recovery_steps} steps")

        elif self.state == self.STATE_RECOVERY:
            # Check if recovery period is complete
            steps_in_recovery = global_step - self.recovery_start_step
            if steps_in_recovery >= self.recovery_steps:
                # Resume monitoring for re-relaxation
                self.state = self.STATE_AUTHORITY
                self.stability_streak = 0
                self.pre_relaxation_ppl = None
                action = "RESUME"
                self.transitions.append({
                    "step": global_step,
                    "from": "RECOVERY",
                    "to": "AUTHORITY",
                    "stability": stability_index,
                })
                print(f"\n  ✓ [DynamicRelaxation] Recovery complete. Resuming Authority phase.")

        return (action != "NONE"), action

    def execute_relaxation(self, current_step: int = 0):
        """
        Execute the 9:3 → 6:6 transition with Dampened Thaw and Weight Transfer.

        The newly added sensory layers (6-8) start with very low α (0.05)
        and ramp up slowly to prevent Rajasic override.

        Weight Transfer Process:
        1. Capture weights from Layers 6, 7, 8 (StateDeltaPhaseBlocks)
        2. Transfer to new QuadraticAttentionWithPhaseBias blocks
        3. Re-anchor R-Signal to Layer 5 (new Witness)
        4. Activate Guna-Lock: freeze W_q, W_k for 50 steps

        Phase Attention Protection:
        During Thaw, Phase-Attention weights in Authority layers receive
        extra gradient dampening to maintain stability of the complex O(n)
        attention mechanism.
        """
        print(f"\n  ⚡ [DynamicRelaxation] RELAXATION: {self.authority_split} → {self.balanced_split}")

        # =====================================================================
        # WEIGHT TRANSFER: State-Inference + 48D Anchor + Guna-Lock
        # =====================================================================
        if self.weight_transfer is not None and self.enable_weight_transfer:
            print(f"\n  📤 [WeightTransfer] Beginning weight transfer...")

            # Step 1: Capture weights from Layers 6, 7, 8 (before they become Sensory)
            self.weight_transfer.capture_state()

            # Step 2: Get the new Quadratic layers (will be created after reconfigure)
            # For now, we capture the layers that will become Sensory
            layers = self.weight_transfer._get_model_layers()
            if layers is not None:
                # Layers 6, 7, 8 in the original indexing become Sensory layers
                new_sensory_layers = []
                for idx in self.weight_transfer.transferred_layers:
                    if idx < len(layers):
                        new_sensory_layers.append(layers[idx])

                # Step 3: Transfer weights (State-Inference)
                # Initialize Q, K from V to preserve learned attention patterns
                self.weight_transfer.transfer_weights(
                    new_layers=new_sensory_layers,
                    r_signal_dim=48,  # Standard R-Signal dimension
                )

                # Step 4: Re-anchor R-Signal to Layer 5 (new Witness)
                if self.weight_transfer.anchor_layer_idx < len(layers):
                    new_witness = layers[self.weight_transfer.anchor_layer_idx]
                    self.weight_transfer.anchor_r_signal(new_witness)

                # Step 5: Activate Guna-Lock (freeze W_q, W_k for 50 steps)
                self.weight_transfer.activate_guna_lock(current_step)

        # Enable Thaw mode for Phase Attention protection
        self.gradient_scaler.set_thaw_mode(True)

        # Reconfigure the gradient scaler
        self.gradient_scaler.reconfigure(
            new_authority_layers=self.balanced_split[0],
            new_sensory_layers=self.balanced_split[1],
            new_alpha_min=self.thaw_alpha_start,  # Start very low for dampened thaw
            new_alpha_max=self.balanced_alpha_max,
            new_warmup_steps=self.thaw_warmup_steps,
        )

        self.current_split = self.balanced_split
        print(f"    Dampened Thaw: α = {self.thaw_alpha_start} → {self.balanced_alpha_max} over {self.thaw_warmup_steps} steps")
        print(f"    Phase Attention: Protected during Thaw")
        if self.weight_transfer is not None:
            print(f"    Guna-Lock: W_q, W_k frozen for {self.guna_lock_steps} steps")

    def execute_recovery(self):
        """
        Execute Viparyaya recovery: revert to 9:3 split.

        This 're-stiffens' the model by returning to Authority-heavy configuration.
        Also releases Guna-Lock if active, as the layer structure is changing.
        """
        print(f"\n  🔄 [DynamicRelaxation] ERROR RECOVERY: Reverting to {self.authority_split}")

        # Release Guna-Lock if active (layer structure is changing)
        if self.weight_transfer is not None and self.weight_transfer.guna_lock_active:
            self.weight_transfer.release_guna_lock()
            print("    Guna-Lock released due to recovery")

        # Disable Thaw mode - Phase Attention can learn normally in Authority mode
        self.gradient_scaler.set_thaw_mode(False)

        # Reconfigure back to authority-heavy split
        self.gradient_scaler.reconfigure(
            new_authority_layers=self.authority_split[0],
            new_sensory_layers=self.authority_split[1],
            new_alpha_min=0.1,  # Heavy dampening
            new_alpha_max=self.authority_alpha_max,
            new_warmup_steps=100,  # Quick stabilization
        )

        self.current_split = self.authority_split

    def update_guna_lock(self, current_step: int) -> bool:
        """
        Update Guna-Lock status. Call this each training step after relaxation.

        Returns True if Guna-Lock was just released.
        """
        if self.weight_transfer is None:
            return False

        released = self.weight_transfer.update_guna_lock(current_step)
        if released:
            print(f"\n  🔓 [DynamicRelaxation] Guna-Lock released at step {current_step}")
            print("    W_q, W_k now trainable")
        return released

    def is_guna_locked(self) -> bool:
        """Check if Guna-Lock is currently active."""
        if self.weight_transfer is None:
            return False
        return self.weight_transfer.guna_lock_active

    def get_status_string(self) -> str:
        """Get formatted status string for logging."""
        split_str = f"{self.current_split[0]}:{self.current_split[1]}"
        streak_str = f"{self.stability_streak}/{self.stability_window}" if self.state == self.STATE_AUTHORITY else "—"
        lock_str = " 🔒" if self.is_guna_locked() else ""

        # V9.5.0 Dynamic Streak progress (if enabled and not yet triggered)
        sat_str = ""
        if self.enable_saturation_gate and self.state == self.STATE_AUTHORITY:
            if self.saturation_triggered:
                sat_str = " 🚀FLIP"
            elif self.metabolic_step_counter > 0:
                # Show dynamic target: 50 (escape) or 500 (sattvic)
                mode = "⚡" if self._current_target_streak == 50 else "🧘"
                sat_str = f" {mode}Met:{self.metabolic_step_counter}/{self._current_target_streak}"

        if self.state == self.STATE_RECOVERY:
            return f"Split:{split_str} State:RECOVERY Streak:{streak_str}{lock_str}"
        elif self.state == self.STATE_BALANCED:
            thaw_str = ""
            if self.saturation_thaw_step is not None:
                thaw_str = " (Thaw)"
            return f"Split:{split_str} State:BALANCED ✓{lock_str}{thaw_str}"
        else:
            return f"Split:{split_str} State:{self.state} Streak:{streak_str}{sat_str}{lock_str}"

    def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry data for logging/visualization."""
        recent_stability = [h["stability"] for h in self.stability_history[-100:]]
        avg_stability = sum(recent_stability) / len(recent_stability) if recent_stability else 0.0

        telemetry = {
            "state": self.state,
            "current_split": f"{self.current_split[0]}:{self.current_split[1]}",
            "stability_streak": self.stability_streak,
            "avg_stability_100": avg_stability,
            "transitions": len(self.transitions),
            "is_balanced": self.state == self.STATE_BALANCED,
            "guna_lock_active": self.is_guna_locked(),
        }

        # Add weight transfer status if available
        if self.weight_transfer is not None:
            wt_status = self.weight_transfer.get_status()
            telemetry["weight_transfer"] = wt_status

        return telemetry

    def get_state(self) -> Dict[str, Any]:
        """Get full state for checkpointing."""
        state = {
            "state": self.state,
            "current_split": self.current_split,
            "stability_streak": self.stability_streak,
            "ssi_rolling_window": list(self.ssi_rolling_window),
            "pre_relaxation_ppl": self.pre_relaxation_ppl,
            "relaxation_step": self.relaxation_step,
            "recovery_start_step": self.recovery_start_step,
            "integration_tax_logged": self.integration_tax_logged,
            "transitions": self.transitions,
        }

        # Add weight transfer state
        if self.weight_transfer is not None:
            state["weight_transfer"] = {
                "guna_lock_active": self.weight_transfer.guna_lock_active,
                "guna_lock_start_step": self.weight_transfer.guna_lock_start_step,
            }

        return state

    def set_state(self, state: Dict[str, Any]):
        """Restore state from checkpoint."""
        self.state = state.get("state", self.STATE_AUTHORITY)
        self.current_split = state.get("current_split", self.authority_split)
        self.stability_streak = state.get("stability_streak", 0)
        self.ssi_rolling_window = state.get("ssi_rolling_window", [])
        self.pre_relaxation_ppl = state.get("pre_relaxation_ppl", None)
        self.relaxation_step = state.get("relaxation_step", None)
        self.recovery_start_step = state.get("recovery_start_step", None)
        self.integration_tax_logged = state.get("integration_tax_logged", False)
        self.transitions = state.get("transitions", [])

        # Restore weight transfer state
        if self.weight_transfer is not None and "weight_transfer" in state:
            wt_state = state["weight_transfer"]
            self.weight_transfer.guna_lock_active = wt_state.get("guna_lock_active", False)
            self.weight_transfer.guna_lock_start_step = wt_state.get("guna_lock_start_step", None)

