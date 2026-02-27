import math
import logging
import torch
import torch.nn as nn
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)



class CurriculumController:
    """
    PPL-Gated Curriculum Learning Controller.

    Automatically introduces auxiliary losses based on validation PPL thresholds.
    This ensures the model learns coherent language generation BEFORE ontological
    constraints are applied.

    Phases:
        1. FOUNDATION (PPL > 30): Pure cross-entropy, no auxiliary losses
        2. REGULARIZATION (PPL 30-15): Light ontological regularization
        3. GROUNDING (PPL 15-10): CSR and ontological bridge
        4. SOVEREIGN (PPL < 10): Full auxiliary stack with balanced weights

    Key Principle: LM loss always remains the dominant signal (≥50% of gradients).

    Usage:
        controller = CurriculumController(config)

        # In training loop:
        weights = controller.get_loss_weights(current_val_ppl)
        loss = weights['lm'] * lm_loss + weights['bhava'] * bhava_loss + ...
    """

    # Phase constants
    PHASE_FOUNDATION = "FOUNDATION"      # Pure LM
    PHASE_REGULARIZATION = "REGULARIZATION"  # Light ontology
    PHASE_GROUNDING = "GROUNDING"        # CSR + Bridge
    PHASE_SOVEREIGN = "SOVEREIGN"        # Full stack

    def __init__(
        self,
        # PPL thresholds for phase transitions
        ppl_regularization: float = 30.0,  # Enter REGULARIZATION when PPL < this
        ppl_grounding: float = 15.0,       # Enter GROUNDING when PPL < this
        ppl_sovereign: float = 10.0,       # Enter SOVEREIGN when PPL < this
        # Stability requirements
        stability_window: int = 5,         # Consecutive evals below threshold
        # Weight configurations per phase
        foundation_weights: Optional[Dict[str, float]] = None,
        regularization_weights: Optional[Dict[str, float]] = None,
        grounding_weights: Optional[Dict[str, float]] = None,
        sovereign_weights: Optional[Dict[str, float]] = None,
        # Hysteresis to prevent oscillation
        hysteresis: float = 1.5,           # Must exceed threshold by this to regress
    ):
        self.ppl_regularization = ppl_regularization
        self.ppl_grounding = ppl_grounding
        self.ppl_sovereign = ppl_sovereign
        self.stability_window = stability_window
        self.hysteresis = hysteresis

        # Current state
        self.current_phase = self.PHASE_FOUNDATION
        self.phase_history: List[Tuple[int, str, float]] = []  # (step, phase, ppl)
        self.ppl_history: List[float] = []
        self.steps_in_phase = 0
        self.phase_locked = False  # Prevent regression once SOVEREIGN reached

        # Default weight configurations - LM always dominant
        # Note: use_sovereign_loss and enable_sovereign_loss control different loss paths:
        # - use_sovereign_loss: Sovereign-1 hardened loss (Priority 2)
        # - enable_sovereign_loss: Sovereign-Lagrangian B1/S3 (Priority 1)
        self.foundation_weights = foundation_weights or {
            'lm': 1.0,
            'bhava': 0.0,
            'coherence': 0.0,
            'b1_lambda': 0.0,
            'mu_s3': 0.0,
            'csr': 0.0,
            'onto_bridge': 0.0,
            'evo': 0.0,
            'toroidal': 0.0,
            'jepa': 0.0,
            'kosha': 0.0,
            'sovereign_r': 0.0,
            'sovereign_s': 0.0,
            'sovereign_c': 0.0,
            'use_sovereign_loss': False,      # Disable Sovereign-1 loss
            'enable_sovereign_loss': False,   # Disable Sovereign-Lagrangian loss
            'enable_srk': False,
            'enable_csr': False,
            'enable_jepa': False,
            'enable_onto_bridge': False,
            'enable_kosha_steering': False,
            'enable_evolutionary_flow': False,
            'enable_toroidal_bridge': False,
        }

        self.regularization_weights = regularization_weights or {
            'lm': 1.0,
            'bhava': 0.01,          # Very light
            'coherence': 0.01,      # Very light
            'b1_lambda': 0.0,
            'mu_s3': 0.0,
            'csr': 0.0,
            'onto_bridge': 0.0,
            'evo': 0.0,
            'toroidal': 0.0,
            'jepa': 0.0,
            'kosha': 0.0,
            'sovereign_r': 0.0,
            'sovereign_s': 0.0,
            'sovereign_c': 0.0,
            'use_sovereign_loss': False,      # Still disabled
            'enable_sovereign_loss': False,
            'enable_srk': False,
            'enable_csr': False,
            'enable_jepa': False,
            'enable_onto_bridge': False,
            'enable_kosha_steering': False,
            'enable_evolutionary_flow': False,
            'enable_toroidal_bridge': False,
        }

        self.grounding_weights = grounding_weights or {
            'lm': 1.0,
            'bhava': 0.02,
            'coherence': 0.02,
            'b1_lambda': 0.0,
            'mu_s3': 0.0,
            'csr': 0.05,            # CSR activated
            'onto_bridge': 0.05,    # Bridge activated
            'evo': 0.0,
            'toroidal': 0.0,
            'jepa': 0.1,            # Light JEPA
            'kosha': 0.0,
            'sovereign_r': 0.0,
            'sovereign_s': 0.0,
            'sovereign_c': 0.0,
            'use_sovereign_loss': False,      # Still disabled until SOVEREIGN
            'enable_sovereign_loss': False,
            'enable_srk': False,
            'enable_csr': True,
            'enable_jepa': True,
            'enable_onto_bridge': True,
            'enable_kosha_steering': False,
            'enable_evolutionary_flow': False,
            'enable_toroidal_bridge': False,
        }

        self.sovereign_weights = sovereign_weights or {
            'lm': 1.0,              # LM stays at 1.0
            'bhava': 0.05,
            'coherence': 0.03,
            'b1_lambda': 0.1,       # Reduced from 0.5
            'mu_s3': 0.05,          # Reduced from 0.2
            'csr': 0.1,
            'onto_bridge': 0.1,
            'evo': 0.05,            # Light EvoFlow
            'toroidal': 0.05,       # Light Toroidal
            'jepa': 0.2,
            'kosha': 0.1,
            'sovereign_r': 0.5,     # Reduced from 5.0!
            'sovereign_s': 0.2,     # Reduced from 2.0
            'sovereign_c': 0.1,     # Reduced from 0.5
            'use_sovereign_loss': True,       # Enable in SOVEREIGN phase
            'enable_sovereign_loss': False,   # Keep B1/S3 off (use Sovereign-1 instead)
            'enable_srk': True,
            'enable_csr': True,
            'enable_jepa': True,
            'enable_onto_bridge': True,
            'enable_kosha_steering': True,
            'enable_evolutionary_flow': True,
            'enable_toroidal_bridge': True,
        }

        # Weight lookup by phase
        self.phase_weights = {
            self.PHASE_FOUNDATION: self.foundation_weights,
            self.PHASE_REGULARIZATION: self.regularization_weights,
            self.PHASE_GROUNDING: self.grounding_weights,
            self.PHASE_SOVEREIGN: self.sovereign_weights,
        }

    def update(self, val_ppl: float, global_step: int) -> Optional[str]:
        """
        Update controller with new validation PPL.

        Args:
            val_ppl: Current validation perplexity
            global_step: Current training step

        Returns:
            Transition message if phase changed, None otherwise
        """
        self.ppl_history.append(val_ppl)
        self.steps_in_phase += 1

        # Keep history bounded
        if len(self.ppl_history) > 100:
            self.ppl_history = self.ppl_history[-100:]

        # Check for phase transition
        old_phase = self.current_phase
        new_phase = self._determine_phase(val_ppl)

        if new_phase != old_phase:
            self.current_phase = new_phase
            self.steps_in_phase = 0
            self.phase_history.append((global_step, new_phase, val_ppl))

            # Lock at SOVEREIGN to prevent regression
            if new_phase == self.PHASE_SOVEREIGN:
                self.phase_locked = True

            return self._get_transition_message(old_phase, new_phase, val_ppl, global_step)

        return None

    def _determine_phase(self, val_ppl: float) -> str:
        """Determine which phase we should be in based on PPL."""
        # If locked at SOVEREIGN, stay there
        if self.phase_locked:
            return self.PHASE_SOVEREIGN

        # Check stability (need consecutive evals below threshold)
        recent_ppls = self.ppl_history[-self.stability_window:]
        if len(recent_ppls) < self.stability_window:
            # Not enough history, stay in current phase
            return self.current_phase

        avg_recent_ppl = sum(recent_ppls) / len(recent_ppls)

        # Forward transitions (improving PPL)
        if avg_recent_ppl < self.ppl_sovereign:
            return self.PHASE_SOVEREIGN
        elif avg_recent_ppl < self.ppl_grounding:
            return self.PHASE_GROUNDING
        elif avg_recent_ppl < self.ppl_regularization:
            return self.PHASE_REGULARIZATION

        # Backward transitions (worsening PPL) - with hysteresis
        if self.current_phase == self.PHASE_SOVEREIGN:
            if avg_recent_ppl > self.ppl_sovereign * self.hysteresis:
                return self.PHASE_GROUNDING
        elif self.current_phase == self.PHASE_GROUNDING:
            if avg_recent_ppl > self.ppl_grounding * self.hysteresis:
                return self.PHASE_REGULARIZATION
        elif self.current_phase == self.PHASE_REGULARIZATION:
            if avg_recent_ppl > self.ppl_regularization * self.hysteresis:
                return self.PHASE_FOUNDATION

        return self.current_phase

    def get_loss_weights(self) -> Dict[str, float]:
        """Get current loss weights based on phase."""
        return self.phase_weights[self.current_phase].copy()

    def get_config_overrides(self) -> Dict[str, Any]:
        """
        Get config overrides to apply for current phase.

        Returns dict that can be used to update training config.
        """
        weights = self.get_loss_weights()
        return {
            'bhava_lambda': weights['bhava'],
            'coherence_lambda': weights['coherence'],
            'b1_lambda': weights['b1_lambda'],
            'mu_s3': weights['mu_s3'],
            'csr_lambda': weights['csr'],
            'onto_bridge_lambda': weights['onto_bridge'],
            'evo_lambda': weights['evo'],
            'toroidal_lambda': weights['toroidal'],
            'jepa_prediction_weight': weights['jepa'],
            'kosha_steering_force': weights['kosha'],
            'sovereign_weight_r': weights['sovereign_r'],
            'sovereign_weight_s': weights['sovereign_s'],
            'sovereign_weight_c': weights['sovereign_c'],
            # Sovereign loss controls (critical for curriculum)
            'use_sovereign_loss': weights['use_sovereign_loss'],
            'enable_sovereign_loss': weights['enable_sovereign_loss'],
            # Boolean enables
            'enable_srk': weights['enable_srk'],
            'enable_csr': weights['enable_csr'],
            'enable_jepa': weights['enable_jepa'],
            'enable_onto_bridge': weights['enable_onto_bridge'],
            'enable_kosha_steering': weights['enable_kosha_steering'],
            'enable_evolutionary_flow': weights['enable_evolutionary_flow'],
            'enable_toroidal_bridge': weights['enable_toroidal_bridge'],
        }

    def should_enable(self, component: str) -> bool:
        """Check if a specific component should be enabled in current phase."""
        weights = self.get_loss_weights()
        enable_key = f'enable_{component}'
        if enable_key in weights:
            return weights[enable_key]
        # Fall back to checking weight > 0
        return weights.get(component, 0.0) > 0.0

    def _get_transition_message(
        self,
        old_phase: str,
        new_phase: str,
        ppl: float,
        step: int
    ) -> str:
        """Generate human-readable transition message."""
        phase_icons = {
            self.PHASE_FOUNDATION: "📚",
            self.PHASE_REGULARIZATION: "🔧",
            self.PHASE_GROUNDING: "🌉",
            self.PHASE_SOVEREIGN: "👑",
        }

        phase_descriptions = {
            self.PHASE_FOUNDATION: "Pure LM (cross-entropy only)",
            self.PHASE_REGULARIZATION: "Light Regularization (bhava + coherence)",
            self.PHASE_GROUNDING: "Structural Grounding (CSR + Bridge + JEPA)",
            self.PHASE_SOVEREIGN: "Full Sovereign (all systems active)",
        }

        icon = phase_icons.get(new_phase, "❓")
        desc = phase_descriptions.get(new_phase, new_phase)
        direction = "↗️" if self._phase_order(new_phase) > self._phase_order(old_phase) else "↘️"

        weights = self.get_loss_weights()
        active = [k for k, v in weights.items() if isinstance(v, bool) and v]

        msg = f"\n{'='*70}\n"
        msg += f"  {icon} [CURRICULUM] Phase Transition {direction}\n"
        msg += f"{'='*70}\n"
        msg += f"  Step {step} | Val PPL: {ppl:.2f}\n"
        msg += f"  {old_phase} → {new_phase}\n"
        msg += f"  {desc}\n"
        if active:
            msg += f"  Active: {', '.join(active)}\n"
        msg += f"{'='*70}\n"

        return msg

    def _phase_order(self, phase: str) -> int:
        """Get numeric order of phase for comparison."""
        order = {
            self.PHASE_FOUNDATION: 0,
            self.PHASE_REGULARIZATION: 1,
            self.PHASE_GROUNDING: 2,
            self.PHASE_SOVEREIGN: 3,
        }
        return order.get(phase, -1)

    def get_status(self) -> Dict[str, Any]:
        """Get current controller status for logging."""
        weights = self.get_loss_weights()
        return {
            'phase': self.current_phase,
            'steps_in_phase': self.steps_in_phase,
            'phase_locked': self.phase_locked,
            'recent_ppl': self.ppl_history[-1] if self.ppl_history else None,
            'avg_recent_ppl': (
                sum(self.ppl_history[-self.stability_window:]) /
                min(len(self.ppl_history), self.stability_window)
                if self.ppl_history else None
            ),
            'thresholds': {
                'regularization': self.ppl_regularization,
                'grounding': self.ppl_grounding,
                'sovereign': self.ppl_sovereign,
            },
            'active_components': [
                k.replace('enable_', '') for k, v in weights.items()
                if isinstance(v, bool) and v
            ],
            'phase_history_count': len(self.phase_history),
        }



class SequenceLengthCurriculum:
    """
    Sequence Length Curriculum Controller.

    Starts training with shorter sequences for faster syntax learning,
    then gradually ramps up to full length for long-range dependencies.

    Benefits:
    - Faster early training (more updates per second with short sequences)
    - Lower VRAM usage initially (allows larger batch sizes)
    - Syntax/grammar learned quickly on short contexts
    - Long-range dependencies introduced gradually

    Modes:
    - linear: seq_len = start + (end - start) * (step / ramp_steps)
    - exponential: seq_len = start * (end / start) ^ (step / ramp_steps)

    PPL Gating (optional):
    - If seq_len_ppl_gate > 0, sequence length only increases when PPL drops
      below the gate threshold. This ensures the model masters current length
      before extending.

    Usage:
        curriculum = SequenceLengthCurriculum(config)

        # In training loop:
        current_seq_len = curriculum.get_seq_len(global_step, current_ppl)

        # Check for transitions:
        if curriculum.should_reload_data():
            dataloader = create_dataloader(seq_len=current_seq_len)
            curriculum.mark_data_reloaded()
    """

    def __init__(
        self,
        seq_len_start: int = 256,
        seq_len_end: int = 1024,
        ramp_steps: int = 5000,
        ramp_mode: str = "linear",
        ppl_gate: float = 0.0,
        reload_threshold: int = 64,  # Reload data if seq_len changes by this much
    ):
        self.seq_len_start = seq_len_start
        self.seq_len_end = seq_len_end
        self.ramp_steps = ramp_steps
        self.ramp_mode = ramp_mode
        self.ppl_gate = ppl_gate
        self.reload_threshold = reload_threshold

        # State
        self.current_seq_len = seq_len_start
        self.last_reload_seq_len = seq_len_start
        self.ppl_gated_step = 0  # Effective step for PPL-gated mode
        self.last_ppl_below_gate = False
        self._needs_reload = False

        # History for logging
        self.seq_len_history: List[Tuple[int, int]] = []  # (step, seq_len)

    def get_seq_len(self, step: int, current_ppl: Optional[float] = None) -> int:
        """
        Get the current sequence length based on step and optionally PPL.

        Args:
            step: Current training step
            current_ppl: Current validation PPL (optional, for PPL-gated mode)

        Returns:
            Current sequence length to use
        """
        if step >= self.ramp_steps:
            # Reached full length
            new_seq_len = self.seq_len_end
        else:
            # Calculate progress
            if self.ppl_gate > 0 and current_ppl is not None:
                # PPL-gated mode: only advance when PPL < gate
                if current_ppl < self.ppl_gate:
                    if not self.last_ppl_below_gate:
                        self.last_ppl_below_gate = True
                    self.ppl_gated_step += 1
                else:
                    self.last_ppl_below_gate = False
                progress = min(1.0, self.ppl_gated_step / self.ramp_steps)
            else:
                # Step-based mode
                progress = min(1.0, step / self.ramp_steps)

            # Calculate new sequence length
            if self.ramp_mode == "exponential":
                # Exponential: faster early growth, slower later
                ratio = self.seq_len_end / self.seq_len_start
                new_seq_len = int(self.seq_len_start * (ratio ** progress))
            else:
                # Linear (default)
                new_seq_len = int(
                    self.seq_len_start + (self.seq_len_end - self.seq_len_start) * progress
                )

        # Round to multiple of 64 for efficiency
        new_seq_len = ((new_seq_len + 63) // 64) * 64
        new_seq_len = min(new_seq_len, self.seq_len_end)
        new_seq_len = max(new_seq_len, self.seq_len_start)

        # Check if we need to reload data
        if abs(new_seq_len - self.last_reload_seq_len) >= self.reload_threshold:
            self._needs_reload = True

        # Update state
        old_seq_len = self.current_seq_len
        self.current_seq_len = new_seq_len

        # Log transitions
        if new_seq_len != old_seq_len:
            self.seq_len_history.append((step, new_seq_len))

        return new_seq_len

    def should_reload_data(self) -> bool:
        """Check if dataloader should be reloaded with new sequence length."""
        return self._needs_reload

    def mark_data_reloaded(self):
        """Mark that data has been reloaded with current sequence length."""
        self._needs_reload = False
        self.last_reload_seq_len = self.current_seq_len

    def get_progress(self) -> float:
        """Get curriculum progress as fraction [0, 1]."""
        return (self.current_seq_len - self.seq_len_start) / max(
            1, self.seq_len_end - self.seq_len_start
        )

    def get_status(self) -> Dict[str, Any]:
        """Get current status for logging."""
        return {
            'current_seq_len': self.current_seq_len,
            'target_seq_len': self.seq_len_end,
            'progress': self.get_progress(),
            'mode': self.ramp_mode,
            'ppl_gated': self.ppl_gate > 0,
            'ppl_gate_threshold': self.ppl_gate if self.ppl_gate > 0 else None,
            'transitions': len(self.seq_len_history),
        }

    def get_transition_message(self, step: int, old_len: int, new_len: int) -> str:
        """Generate human-readable transition message."""
        progress = self.get_progress()
        direction = "↗️" if new_len > old_len else "↘️"

        msg = f"\n{'='*60}\n"
        msg += f"  📏 [SEQ CURRICULUM] Length Transition {direction}\n"
        msg += f"{'='*60}\n"
        msg += f"  Step {step} | {old_len} → {new_len} tokens\n"
        msg += f"  Progress: {progress:.1%} toward {self.seq_len_end}\n"
        msg += f"  Mode: {self.ramp_mode.upper()}"
        if self.ppl_gate > 0:
            msg += f" (PPL-gated < {self.ppl_gate})"
        msg += f"\n{'='*60}\n"

        return msg





def dampen_layer_momentum(
    optimizer: torch.optim.Optimizer,
    model: nn.Module,
    layer_indices: list,
    dampen_factor: float = 0.5,
    verbose: bool = True,
) -> dict:
    """
    Apply momentum dampening to specific layers' optimizer state.

    When a layer transitions from Quadratic to Phase (α reaches 1.0), we dampen
    the optimizer's momentum buffers for that layer's parameters. This allows
    the newly "Phase-engaged" layer to find its own direction without being
    pulled by the "Quadratic ghost" of its past.

    Args:
        optimizer: The optimizer (AdamW expected)
        model: The model to extract layer parameters from
        layer_indices: List of layer indices that completed transition
        dampen_factor: Factor to multiply momentum by (0.5 = 50% decay)
        verbose: Whether to print diagnostic messages

    Returns:
        dict with dampening info
    """
    dampened = {
        'layers_dampened': [],
        'params_affected': 0,
    }

    if not layer_indices:
        return dampened

    # Find parameters for the specified layers
    # This assumes model has a 'transformer' or 'layers' attribute
    layer_params = []
    for name, param in model.named_parameters():
        for layer_idx in layer_indices:
            # Match common naming patterns: layers.N, transformer.h.N, encoder.layer.N
            if (f'layers.{layer_idx}.' in name or
                f'transformer.h.{layer_idx}.' in name or
                f'encoder.layer.{layer_idx}.' in name or
                f'_layers.{layer_idx}.' in name):
                layer_params.append(param)
                break

    # Dampen momentum buffers for these parameters
    for param in layer_params:
        if param in optimizer.state:
            state = optimizer.state[param]
            # AdamW uses 'exp_avg' (first moment) and 'exp_avg_sq' (second moment)
            if 'exp_avg' in state:
                state['exp_avg'].mul_(dampen_factor)
            if 'exp_avg_sq' in state:
                state['exp_avg_sq'].mul_(dampen_factor)
            dampened['params_affected'] += 1

    dampened['layers_dampened'] = layer_indices

    if verbose and dampened['params_affected'] > 0:
        print(f"  🎛️  [MOMENTUM DAMPEN] Applied {dampen_factor:.0%} decay to layers {layer_indices}")
        print(f"     Parameters affected: {dampened['params_affected']}")

    return dampened


def on_seq_len_transition(
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    old_seq_len: int,
    new_seq_len: int,
    grad_accum_counter: int = 0,
    verbose: bool = True,
) -> dict:
    """
    Sovereign Reset Protocol for sequence length transitions.

    Addresses the "Re-Loading Tax" concern: when switching sequence lengths mid-training,
    we need to ensure clean state to prevent:
    - Stale gradient accumulation from old sequence length
    - Memory fragmentation from different tensor shapes

    This follows Gemini's "Soft-Reset" recommendations for robust seq_len transitions.

    Protocol steps:
    1. Zero gradients (set_to_none=True for memory efficiency)
    2. Clear CUDA cache (releases fragmented memory)
    3. Return skip_step flag (caller should skip one training step for VRAM stabilization)

    Args:
        optimizer: The optimizer to clear gradients from
        device: The device (for CUDA cache clearing)
        old_seq_len: Previous sequence length
        new_seq_len: New sequence length
        grad_accum_counter: Current gradient accumulation count (for diagnostics)
        verbose: Whether to print diagnostic messages

    Returns:
        dict with cleared state info and skip_step flag
    """
    result = {
        'gradients_cleared': False,
        'cuda_cache_cleared': False,
        'grad_accum_flushed': grad_accum_counter > 0,
        'old_seq_len': old_seq_len,
        'new_seq_len': new_seq_len,
        'skip_step': True,  # Caller should skip one step for VRAM stabilization
    }

    # 1. Clear optimizer gradients (set_to_none=True for memory efficiency)
    optimizer.zero_grad(set_to_none=True)
    result['gradients_cleared'] = True

    # 2. Clear CUDA cache if on GPU (releases fragmented memory)
    if device.type == "cuda":
        torch.cuda.empty_cache()
        result['cuda_cache_cleared'] = True

    # 3. Log diagnostic info
    if verbose:
        msg_parts = ["  🧹 [SOVEREIGN RESET] Seq transition protocol:"]
        msg_parts.append(f"     Gradients: cleared (set_to_none=True)")
        if result['cuda_cache_cleared']:
            msg_parts.append(f"     CUDA cache: cleared")
        if result['grad_accum_flushed']:
            msg_parts.append(f"     ⚠️  Gradient accum flushed ({grad_accum_counter} steps were pending)")
        msg_parts.append(f"     Next step: SKIP (VRAM stabilization)")
        print("\n".join(msg_parts))

    return result


def should_sync_curriculum_update(step: int, gradient_accumulation: int) -> bool:
    """
    Check if curriculum updates should fire (Sync-Point Evolution).

    Curriculum updates should only happen at the END of a gradient accumulation cycle.
    This ensures the "Old Body" has fully pushed its gradients before transitioning to
    a "New Body" (different split) or "New Environment" (different seq_len).

    Args:
        step: Current accumulation step within the cycle
        gradient_accumulation: Total accumulation steps per cycle

    Returns:
        True if this is a sync point (end of accumulation cycle)
    """
    return (step + 1) % gradient_accumulation == 0



class ThreePhaseCurriculum:
    """
    Generic three-phase curriculum controller for PPL-based engagement.

    Used by CSR (Layer 7), Kosha Gyroscope (Layer 9), and PIDv2 to implement
    smooth engagement/disengagement based on perplexity thresholds.

    INVERTED CURRICULUM: Components activate when model is COMPETENT (low PPL).
    This follows proper curriculum learning where advanced controllers are added
    after basic language modeling is established.

    Phases:
        FOUNDATION (PPL > engage_ppl): Component OFF - learning basics (scale=0.0)
        TRANSITION (disengage_ppl < PPL < engage_ppl): Linear ramp-up
        CONSTRUCTION (PPL < disengage_ppl): Component fully active (scale=1.0)

    Args:
        name: Component name for logging (e.g., "CSR", "Kosha", "PID")
        engage_ppl: PPL threshold below which component starts engaging
        disengage_ppl: PPL threshold below which component is fully active
        rampdown_steps: Steps to ramp up during transition phase
    """

    PHASE_FOUNDATION = "FOUNDATION"
    PHASE_TRANSITION = "TRANSITION"
    PHASE_CONSTRUCTION = "CONSTRUCTION"

    def __init__(
        self,
        name: str,
        engage_ppl: float = 100.0,
        disengage_ppl: float = 30.0,
        rampdown_steps: int = 500,
    ):
        self.name = name
        self.engage_ppl = engage_ppl
        self.disengage_ppl = disengage_ppl
        self.rampdown_steps = rampdown_steps

        # State tracking
        self.phase = self.PHASE_CONSTRUCTION
        self.disengage_step: Optional[int] = None
        self.scale = 1.0
        self.graduated = False
        self._last_log_phase = None  # For change-only logging

    def update(self, val_ppl: float, step: int) -> float:
        """
        Update phase based on current PPL and compute scaling factor.

        INVERTED LOGIC: Lower PPL → Higher controller engagement

        Args:
            val_ppl: Current validation perplexity
            step: Current training step

        Returns:
            scale: Authority scale factor (1.0 = full, 0.0 = off)
        """
        # Already graduated - stay in full construction mode
        if self.graduated:
            self.phase = self.PHASE_CONSTRUCTION
            self.scale = 1.0
            return 1.0

        # Phase 1: FOUNDATION (PPL > engage_ppl) - Component OFF
        # Model is still learning basics, don't interfere
        if val_ppl > self.engage_ppl:
            self.phase = "FOUNDATION"
            self.disengage_step = None  # Reset engagement tracking
            self.scale = 0.0
            self._log_phase_change(step, val_ppl)
            return 0.0

        # Phase 3: CONSTRUCTION (PPL <= disengage_ppl) - Component fully ON
        # Model is competent, apply full controller strength
        if val_ppl <= self.disengage_ppl:
            if self.disengage_step is None:
                # First time entering construction phase
                self.disengage_step = step
                print(f"  🎓 [{self.name}] CONSTRUCTION phase triggered at step {step} "
                      f"(PPL={val_ppl:.1f} ≤ {self.disengage_ppl})")

            self.phase = self.PHASE_CONSTRUCTION
            self.scale = 1.0
            self._log_phase_change(step, val_ppl)
            return 1.0

        # Phase 2: TRANSITION (disengage_ppl < PPL <= engage_ppl) - Ramp up
        # Gradually increase controller strength as PPL improves
        self.phase = self.PHASE_TRANSITION
        self.disengage_step = None  # Reset engagement tracking

        ppl_range = self.engage_ppl - self.disengage_ppl
        if ppl_range > 0:
            # Scale increases as PPL decreases
            # PPL at engage_ppl → scale=0.0, PPL at disengage_ppl → scale=1.0
            progress = (self.engage_ppl - val_ppl) / ppl_range
            self.scale = max(0.0, min(1.0, progress))
        else:
            self.scale = 0.5

        self._log_phase_change(step, val_ppl)
        return self.scale

    def _log_phase_change(self, step: int, val_ppl: float):
        """Log only when phase changes."""
        if self.phase != self._last_log_phase:
            self._last_log_phase = self.phase
            # Only log transitions, not every update
            if self.phase == self.PHASE_TRANSITION:
                print(f"  📐 [{self.name}] Phase: {self.phase} | "
                      f"PPL={val_ppl:.1f} | scale={self.scale:.0%}")

    def get_status(self) -> str:
        """Get human-readable status string."""
        if self.graduated:
            return f"[{self.name}] 🎓 GRADUATED (full construction)"
        elif self.phase == self.PHASE_CONSTRUCTION:
            return f"[{self.name}] 🔧 CONSTRUCTION (scale={self.scale:.0%})"
        elif self.phase == self.PHASE_TRANSITION:
            return f"[{self.name}] 📐 TRANSITION (scale={self.scale:.0%})"
        else:  # FOUNDATION
            return f"[{self.name}] 🌱 FOUNDATION (scale={self.scale:.0%})"

    def get_state(self) -> Dict[str, Any]:
        """Get serializable state for checkpointing."""
        return {
            'phase': self.phase,
            'disengage_step': self.disengage_step,
            'scale': self.scale,
            'graduated': self.graduated,
        }

    def load_state(self, state: Dict[str, Any]):
        """Load state from checkpoint."""
        self.phase = state.get('phase', self.PHASE_CONSTRUCTION)
        self.disengage_step = state.get('disengage_step', None)
        self.scale = state.get('scale', 1.0)
        self.graduated = state.get('graduated', False)




class InvertedLayerCurriculumController:
    """
    V9.9.2: Orchestrates the Inverted Layer Curriculum Evolution.

    Manages split evolution (3:9 → 9:3) with per-layer phase weights and soft
    transitions. Optionally delegates sequence length management to an external
    SequenceLengthCurriculum for sophisticated PPL-gated seq_len progression.

    Responsibilities:
    1. Split evolution: 3:9 → 6:6 → 9:3 (Sensory-first → Authority-later)
    2. Per-layer phase weights (via PerLayerPhaseController)
    3. Soft layer transitions with phase ramp as shock absorber

    Delegation (optional):
    - If seq_len_curriculum is provided, seq_len is delegated to it
    - If not provided, uses fixed default_seq_len

    Benefits of separation:
    - SequenceLengthCurriculum handles: PPL gating, linear/exponential ramp, reload detection
    - InvertedLayerCurriculumController handles: split evolution, layer weights, transitions
    - Both react to PPL but control different aspects

    Example curriculum (splits only):
        Stage 0: 3:9 split | PPL > 300  (start)
        Stage 1: 4:8 split | PPL < 300
        Stage 2: 5:7 split | PPL < 200
        Stage 3: 6:6 split | PPL < 120
        Stage 4: 7:5 split | PPL < 75
        Stage 5: 8:4 split | PPL < 45
        Stage 6: 9:3 split | PPL < 25

    Usage (with delegation):
        seq_curriculum = SequenceLengthCurriculum(seq_len_start=256, seq_len_end=2048, ...)
        split_curriculum = InvertedLayerCurriculumController.from_config(
            config, seq_len_curriculum=seq_curriculum
        )

        # In training loop:
        result = split_curriculum.update(step, current_ppl)
        if result['split_changed']:
            reconfigure_gradient_scaler(result['current_split'])
        # seq_len changes handled by seq_curriculum.should_reload_data()
        split_curriculum.apply_to_model(model)

    Usage (standalone):
        split_curriculum = InvertedLayerCurriculumController(
            stages=[(3,9), (4,8), (5,7), (6,6), (7,5), (8,4), (9,3)],
            ppl_triggers=[300, 200, 120, 75, 45, 25],
            default_seq_len=1024,  # Fixed seq_len
        )
    """

    def __init__(
        self,
        stages: List[Tuple[int, int]],  # [(3, 9), (4, 8), ...] - just splits
        ppl_triggers: List[float],  # PPL thresholds for each transition
        local_layers: int = 4,
        transition_steps: int = 500,  # Steps for soft layer transition
        seq_len_curriculum: Optional['SequenceLengthCurriculum'] = None,  # Optional delegation
        default_seq_len: int = 1024,  # Used when no seq_len_curriculum provided
        # V9.9.4: PPL Stability Check (ChatGPT recommendation)
        ppl_stability_threshold: float = 5.0,  # Max PPL slope for "stable" (lower = stricter)
        stability_required_stages: Optional[List[int]] = None,  # Stages requiring stability [2,3,4]
        # V9.9.8: Explicit per-layer phase weights (Gemini's Tapered Bridge)
        initial_phase_weights: Optional[List[float]] = None,  # Override _split_to_weights if provided
    ):
        """
        Initialize the Inverted Curriculum Controller.

        Args:
            stages: List of (authority, sensory) split tuples, e.g., [(3, 9), (6, 6), (9, 3)]
            ppl_triggers: PPL thresholds for advancing to next stage
            local_layers: Number of local attention layers (no phase component)
            transition_steps: Steps for soft layer transitions
            seq_len_curriculum: Optional SequenceLengthCurriculum for seq_len delegation
            default_seq_len: Fixed seq_len when no curriculum provided
            ppl_stability_threshold: Maximum PPL slope to consider "stable" (V9.9.4)
            stability_required_stages: Which stages require stability check before advancing
        """
        self.stages = stages
        self.ppl_triggers = ppl_triggers
        self.local_layers = local_layers
        self.transition_steps = transition_steps
        self.seq_len_curriculum = seq_len_curriculum
        self.default_seq_len = default_seq_len

        # V9.9.4: PPL Stability (ChatGPT's "Readiness Index")
        self.ppl_stability_threshold = ppl_stability_threshold
        # Default: require stability for middle stages (geometry shift zone)
        self.stability_required_stages = stability_required_stages or [2, 3, 4]

        # V9.9.4: ReadinessIndex for composite stability check
        # Combines PPL velocity + acceleration + internal geometry
        self.readiness_index = ReadinessIndex(
            ppl_velocity_threshold=ppl_stability_threshold,
            ppl_accel_threshold=ppl_stability_threshold / 2,  # Stricter on acceleration
            history_window=10,
            require_geometry_check=True,
        )

        # Current state
        self.current_stage_idx = 0
        self.current_split = stages[0]

        # Per-layer phase controller
        # V9.9.8: Use explicit weights (Gemini's Tapered Bridge) if provided
        if initial_phase_weights is not None:
            initial_weights = initial_phase_weights
            print(f"      Using explicit per-layer phase weights (Tapered Bridge)")
        else:
            initial_weights = self._split_to_weights(self.current_split)
        self.phase_controller = PerLayerPhaseController(
            num_layers=12,
            initial_weights=initial_weights,
            local_layers=local_layers,
        )

        # PPL tracking for smooth triggers (kept for smoothed_ppl calculation)
        self.ppl_history: List[float] = []
        self.ppl_window = 10  # Steps to average PPL

        # Transition tracking
        self.stage_history: List[Dict] = []
        self.last_stage_change_step = 0

        # Print curriculum
        self._print_curriculum()

    def _print_curriculum(self):
        """Print the full curriculum schedule."""
        seq_mode = "DELEGATED" if self.seq_len_curriculum else f"FIXED@{self.default_seq_len}"
        print(f"\n  🎓 [INVERTED CURRICULUM] Schedule (seq_len: {seq_mode}):")
        print(f"      {'Stage':<8} {'Split':<8} {'PPL Trigger':<12}")
        print(f"      {'-'*30}")
        for i, (auth, sens) in enumerate(self.stages):
            trigger = f"< {self.ppl_triggers[i]:.0f}" if i < len(self.ppl_triggers) else "START"
            marker = " ◀" if i == self.current_stage_idx else ""
            print(f"      {i:<8} {auth}:{sens:<5} {trigger:<12}{marker}")
        if self.seq_len_curriculum:
            print(f"\n      Seq Len: Delegated to SequenceLengthCurriculum")
            print(f"      Range: {self.seq_len_curriculum.seq_len_start} → {self.seq_len_curriculum.seq_len_end}")
            print(f"      Mode: {self.seq_len_curriculum.ramp_mode}")
            if self.seq_len_curriculum.ppl_gate > 0:
                print(f"      PPL Gate: < {self.seq_len_curriculum.ppl_gate}")

    def _split_to_weights(self, split: Tuple[int, int]) -> List[float]:
        """
        Convert a split (authority, sensory) to per-layer weights.

        For 12 layers with local_layers=4:
        - Layers 0-3: Local only (weight doesn't matter, but set to 0)
        - Layers 4-11: Hybrid, weight = 1.0 for Authority, 0.0 for Sensory

        Example: split (6, 6) means layers 0-5 are Authority, layers 6-11 are Sensory
        So weights for layers 4-11 would be [1, 1, 0, 0, 0, 0, 0, 0]
        """
        authority_layers, sensory_layers = split
        weights = [0.0] * 12

        for i in range(12):
            if i < authority_layers:
                weights[i] = 1.0  # Authority layer
            else:
                weights[i] = 0.0  # Sensory layer

        return weights

    def _compute_ppl_slope(self) -> float:
        """
        V9.9.4: Compute PPL slope (rate of change) from history.

        Returns the average change per step. Negative = improving, positive = worsening.
        A small absolute value indicates stability (plateauing).

        ChatGPT's insight: "PPL can drop while geometry is still reconfiguring.
        Advancing authority too early can slow fluency."
        """
        if len(self.ppl_history) < 3:
            return float('inf')  # Not enough data, assume unstable

        # Compute differences between consecutive PPL values
        diffs = [self.ppl_history[i+1] - self.ppl_history[i]
                 for i in range(len(self.ppl_history) - 1)]

        # Average slope (negative = improving)
        avg_slope = sum(diffs) / len(diffs)

        return avg_slope

    def _is_ppl_stable(self, next_stage_idx: int) -> Tuple[bool, float, str]:
        """
        V9.9.4: Check if PPL is stable enough to advance to next stage.

        Args:
            next_stage_idx: The stage we would advance to

        Returns:
            Tuple of (is_stable, slope, reason_string)
        """
        slope = self._compute_ppl_slope()

        # Check if this stage requires stability
        if next_stage_idx not in self.stability_required_stages:
            return True, slope, "stability_not_required"

        # Check stability: slope should be small (plateauing)
        # We use absolute value because we care about magnitude, not direction
        abs_slope = abs(slope)

        if abs_slope <= self.ppl_stability_threshold:
            return True, slope, "stable"
        elif slope > 0:
            return False, slope, "ppl_rising"
        else:
            return False, slope, "ppl_dropping_fast"

    def update(
        self,
        step: int,
        current_ppl: Optional[float] = None,
        phase_coherence: Optional[float] = None,
        state_delta_norm: Optional[float] = None,
    ) -> Dict[str, any]:
        """
        Update the curriculum based on current step, PPL, and internal geometry.

        V9.9.4: Now uses composite ReadinessIndex that checks:
        1. ΔPPL → small (velocity collapse)
        2. ΔΔPPL → small (acceleration collapse)
        3. Phase/state metrics stable (geometry settled)

        Args:
            step: Current training step
            current_ppl: Current validation PPL (optional)
            phase_coherence: Phase coherence from SPC diagnostics (0-1)
            state_delta_norm: Magnitude of state-delta from Sovereign State

        Returns:
            Dict with:
                - 'current_stage': Current stage index
                - 'current_split': Current (authority, sensory) split
                - 'current_seq_len': Current sequence length (from delegate or fixed)
                - 'split_changed': Whether split changed this step
                - 'seq_len_changed': Whether seq_len changed (from delegate)
                - 'transitioning_layers': Number of layers currently transitioning
                - 'layer_weights': Current per-layer weights
                - 'readiness_score': Composite readiness score (0-1)
        """
        split_changed = False
        old_split = self.current_split

        # Update PPL history (for smoothed_ppl calculation)
        if current_ppl is not None:
            self.ppl_history.append(current_ppl)
            if len(self.ppl_history) > self.ppl_window:
                self.ppl_history.pop(0)

        # V9.9.4: Update ReadinessIndex with all available metrics
        if current_ppl is not None:
            self.readiness_index.update(
                ppl=current_ppl,
                phase_coherence=phase_coherence,
                state_delta_norm=state_delta_norm,
            )

        # Check for stage advancement (split evolution)
        # V9.9.4: Now uses composite ReadinessIndex for true stability check
        if self.current_stage_idx < len(self.stages) - 1 and current_ppl is not None:
            smoothed_ppl = sum(self.ppl_history) / len(self.ppl_history) if self.ppl_history else current_ppl
            next_trigger = self.ppl_triggers[self.current_stage_idx] if self.current_stage_idx < len(self.ppl_triggers) else float('inf')
            next_stage_idx = self.current_stage_idx + 1

            if smoothed_ppl < next_trigger:
                # V9.9.4: Use composite ReadinessIndex for middle stages
                require_geometry = next_stage_idx in self.stability_required_stages
                is_ready, diagnostics = self.readiness_index.is_ready(require_geometry=require_geometry)

                if is_ready or next_stage_idx not in self.stability_required_stages:
                    # Advance to next stage
                    self.current_stage_idx = next_stage_idx
                    new_split = self.stages[self.current_stage_idx]

                    if new_split != old_split:
                        split_changed = True
                        self._transition_to_split(new_split, step)

                    # V9.9.4: Reset persistence counter for next stage
                    # "Start fresh with stability tracking for the new stage"
                    self.readiness_index.reset_persistence()

                    # Record history with full diagnostics
                    self.stage_history.append({
                        'stage': self.current_stage_idx,
                        'step': step,
                        'ppl': smoothed_ppl,
                        'velocity': diagnostics['ppl_velocity'],
                        'acceleration': diagnostics['ppl_acceleration'],
                        'consecutive_stable': diagnostics.get('consecutive_stable', 0),
                        'reason': diagnostics['reason'],
                        'split': new_split,
                    })
                    self.last_stage_change_step = step

                    # Log with velocity/acceleration info
                    vel = diagnostics['ppl_velocity']
                    acc = diagnostics['ppl_acceleration']
                    consec = diagnostics.get('consecutive_stable', 0)
                    stability_note = f" (Δppl: {vel:+.2f}, ΔΔppl: {acc:+.2f}, consec: {consec})"
                    print(f"\n  🎓 [INVERTED CURRICULUM] Stage {self.current_stage_idx} reached!{stability_note}")
                    print(f"      PPL {smoothed_ppl:.2f} < {next_trigger:.0f}")
                    print(f"      Split: {old_split[0]}:{old_split[1]} → {new_split[0]}:{new_split[1]}")
                    if require_geometry:
                        print(f"      Readiness: {diagnostics['reason']} (geometry checked)")
                else:
                    # V9.9.4: PPL threshold met but not truly settled - wait
                    # Only log occasionally to avoid spam
                    if step % 500 == 0:
                        vel = diagnostics['ppl_velocity']
                        acc = diagnostics['ppl_acceleration']
                        consec = diagnostics.get('consecutive_stable', 0)
                        req_consec = diagnostics.get('required_consecutive', 3)
                        print(f"  ⏳ [INVERTED CURRICULUM] Stage {next_stage_idx} pending: "
                              f"PPL {smoothed_ppl:.1f} < {next_trigger:.0f} but {diagnostics['reason']}")
                        print(f"      Δppl: {vel:+.2f}, ΔΔppl: {acc:+.2f}, stability: {consec}/{req_consec}")

        # Update per-layer phase controller (for soft transitions)
        phase_result = self.phase_controller.update(step)

        # Get seq_len from delegate or use fixed
        if self.seq_len_curriculum is not None:
            current_seq_len = self.seq_len_curriculum.get_seq_len(step, current_ppl)
            seq_len_changed = self.seq_len_curriculum.should_reload_data()
        else:
            current_seq_len = self.default_seq_len
            seq_len_changed = False

        return {
            'current_stage': self.current_stage_idx,
            'current_split': self.current_split,
            'current_seq_len': current_seq_len,
            'split_changed': split_changed,
            'seq_len_changed': seq_len_changed,
            'transitioning_layers': phase_result['active_transitions'],
            'layer_weights': phase_result['weights'],
            'completed_transitions': phase_result['completed'],  # V9.9.3: For momentum dampening
            'readiness_score': self.readiness_index.get_composite_score(),  # V9.9.4: Composite readiness
        }

    def _transition_to_split(self, new_split: Tuple[int, int], step: int):
        """
        Start soft transition to a new split.

        Identifies which layer(s) are changing and starts their transition.
        """
        old_auth, old_sens = self.current_split
        new_auth, new_sens = new_split

        if new_auth > old_auth:
            # Moving from Sensory to Authority (3:9 → 4:8 → 5:7 → ...)
            for layer_idx in range(old_auth, new_auth):
                if layer_idx >= self.local_layers:
                    self.phase_controller.start_transition(
                        layer_idx=layer_idx,
                        target_weight=1.0,  # Becoming Authority
                        duration_steps=self.transition_steps,
                        current_step=step,
                    )
        else:
            # Moving from Authority to Sensory (9:3 → 8:4 → 7:5 → ...)
            for layer_idx in range(new_auth, old_auth):
                if layer_idx >= self.local_layers:
                    self.phase_controller.start_transition(
                        layer_idx=layer_idx,
                        target_weight=0.0,  # Becoming Sensory
                        duration_steps=self.transition_steps,
                        current_step=step,
                    )

        self.current_split = new_split

    def apply_to_model(self, model: nn.Module):
        """Apply current per-layer weights to the model."""
        self.phase_controller.apply_to_model(model)

    def get_status(self) -> Dict[str, any]:
        """Get current curriculum status for logging."""
        status = {
            'stage': self.current_stage_idx,
            'total_stages': len(self.stages),
            'split': f"{self.current_split[0]}:{self.current_split[1]}",
            'smoothed_ppl': sum(self.ppl_history) / len(self.ppl_history) if self.ppl_history else None,
            'next_trigger': self.ppl_triggers[self.current_stage_idx] if self.current_stage_idx < len(self.ppl_triggers) else None,
            'transitioning_layers': len(self.phase_controller.transitions),
            'layer_weights': self.phase_controller.weights[self.local_layers:],
        }
        # Add seq_len info from delegate or fixed
        if self.seq_len_curriculum is not None:
            status['seq_len'] = self.seq_len_curriculum.current_seq_len
            status['seq_len_mode'] = 'delegated'
        else:
            status['seq_len'] = self.default_seq_len
            status['seq_len_mode'] = 'fixed'
        return status

    @classmethod
    def from_config(
        cls,
        config,
        seq_len_curriculum: Optional['SequenceLengthCurriculum'] = None,
    ) -> 'InvertedLayerCurriculumController':
        """
        Create controller from config with optional seq_len delegation.

        Args:
            config: UnifiedTrainingConfig with inverted curriculum settings
            seq_len_curriculum: Optional SequenceLengthCurriculum for seq_len delegation

        Config fields used:
        - inverted_curriculum_stages: "3:9,4:8,5:7,6:6,7:5,8:4,9:3" (splits only)
        - inverted_curriculum_ppl_triggers: "300,200,120,75,45,25"
        - layer_transition_steps: Steps for soft transitions (default: 500)
        - local_layers: Number of local attention layers (default: 4)
        - inverted_curriculum_stability_threshold: Max PPL slope for "stable" (V9.9.4)
        - inverted_curriculum_stability_stages: "2,3,4" - stages requiring stability
        """
        # Parse stages (splits only, no seq_len)
        if hasattr(config, 'inverted_curriculum_stages') and config.inverted_curriculum_stages:
            stages = []
            for stage_str in config.inverted_curriculum_stages.split(','):
                stage_str = stage_str.strip()
                # Support both "3:9" and "3:9@256" formats (ignore @seq_len for backwards compat)
                if '@' in stage_str:
                    stage_str = stage_str.split('@')[0]
                split_parts = stage_str.split(':')
                if len(split_parts) == 2:
                    auth, sens = int(split_parts[0]), int(split_parts[1])
                    stages.append((auth, sens))
        else:
            # Default inverted curriculum (splits only)
            stages = [
                (3, 9),   # Start: Heavy Sensory
                (4, 8),
                (5, 7),
                (6, 6),   # Balanced
                (7, 5),
                (8, 4),
                (9, 3),   # End: Heavy Authority
            ]

        # Parse PPL triggers
        if hasattr(config, 'inverted_curriculum_ppl_triggers') and config.inverted_curriculum_ppl_triggers:
            ppl_triggers = [float(t.strip()) for t in config.inverted_curriculum_ppl_triggers.split(',')]
        else:
            # Default triggers
            ppl_triggers = [300, 200, 120, 75, 45, 25]

        # V9.9.4: Parse stability stages
        stability_stages = None
        if hasattr(config, 'inverted_curriculum_stability_stages') and config.inverted_curriculum_stability_stages:
            stability_stages = [int(s.strip()) for s in config.inverted_curriculum_stability_stages.split(',')]

        # V9.9.8: Parse explicit per-layer phase weights (Gemini's Tapered Bridge)
        initial_phase_weights = None
        if hasattr(config, 'per_layer_phase_weights') and config.per_layer_phase_weights:
            initial_phase_weights = [float(w.strip()) for w in config.per_layer_phase_weights.split(',')]
            print(f"  [TAPERED BRIDGE] Parsed per-layer weights: {initial_phase_weights}")

        return cls(
            stages=stages,
            ppl_triggers=ppl_triggers,
            local_layers=getattr(config, 'local_layers', 4),
            transition_steps=getattr(config, 'layer_transition_steps', 500),
            seq_len_curriculum=seq_len_curriculum,
            default_seq_len=getattr(config, 'max_seq_len', 1024),
            # V9.9.4: PPL Stability Check
            ppl_stability_threshold=getattr(config, 'inverted_curriculum_stability_threshold', 5.0),
            stability_required_stages=stability_stages,
            # V9.9.8: Gemini's Tapered Bridge
            initial_phase_weights=initial_phase_weights,
        )
