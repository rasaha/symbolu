"""
Hierarchical Gradient Scaler - Formula [1331] 9:3 Split
========================================================

Implements gradient scaling based on Authority/Sensory layer partitioning.
This prevents sensory over-dampening (S/A ratio = 0.00 issue) by ensuring
sensory layers receive adequate gradient flow.

Key Concepts:
- Authority Layers (0-8): Focus on R-Signal (ontological meaning) - α = 1.0
- Sensory Layers (9-11): Focus on S-Signal (referent grounding) - α = 0.1 → 0.7
- 9:3 Split: 9 authority layers : 3 sensory layers (initial)
- Dynamic Relaxation: Transition from 9:3 → 6:6 as training stabilizes

Uses register_hook on parameters to ensure gradients are scaled BEFORE
the optimizer sees them. This is more robust than post-hoc scaling.

Reference: Patent Formula [1331]
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from collections import deque
import math
import re

import torch
import torch.nn as nn


@dataclass
class HierarchicalGradientScalerConfig:
    """Configuration for Hierarchical Gradient Scaler."""

    # Layer split configuration
    total_layers: int = 12
    authority_layers: int = 9  # Layers 0-8 focusing on R-Signal
    sensory_layers: int = 3    # Layers 9-11 focusing on S-Signal

    # Gradient scaling factors
    alpha_auth: float = 1.0    # Authority gradient multiplier (fixed)
    alpha_sens_initial: float = 0.1   # Initial sensory gradient multiplier
    alpha_sens_max: float = 0.7       # Maximum sensory gradient (after warmup)

    # Warmup schedule
    warmup_steps: int = 500    # Steps to ramp alpha_sens from initial to max

    # Layer naming patterns (regex)
    layer_pattern: str = r'layers\.(\d+)'  # Pattern to extract layer index

    # Signal dimensions in 128D header
    s_signal_start: int = 16   # S-Signal dims 16-47 (32D)
    s_signal_end: int = 48
    r_signal_start: int = 48   # R-Signal dims 48-95 (48D)
    r_signal_end: int = 96


class HierarchicalGradientScaler:
    """
    Formula [1331] - 9:3 Hierarchical Gradient Scaling with Gradient Hooks.

    Uses register_hook to apply gradient scaling BEFORE optimizer.step().
    This ensures proper gradient flow based on layer type:

    Authority Layers (0 to authority_layers-1):
        - α = 1.0 (full learning speed)
        - Focus on R-Signal (ontological meaning)
        - Learn "what things mean"

    Sensory Layers (authority_layers to total_layers-1):
        - α = 0.1 initially, ramping to 0.7 over warmup_steps
        - Focus on S-Signal (referent grounding)
        - Learn "what things are"
    """

    def __init__(
        self,
        model: nn.Module,
        config: Optional[HierarchicalGradientScalerConfig] = None,
    ):
        self.config = config or HierarchicalGradientScalerConfig()
        self.model = model
        self.current_step = 0

        # Current alpha values per layer type
        self.alpha_auth = self.config.alpha_auth
        self.alpha_sens = self.config.alpha_sens_initial

        # Metrics tracking
        self.authority_grad_norms: List[float] = []
        self.sensory_grad_norms: List[float] = []

        # Gradient hooks (stored to prevent garbage collection)
        self._hooks: List[torch.utils.hooks.RemovableHandle] = []

        # Layer classification cache
        self._layer_types: Dict[str, str] = {}

        # Register gradient hooks
        self._register_hooks()

    def _get_layer_type(self, param_name: str) -> str:
        """
        Determine if a parameter belongs to authority or sensory layers.

        Returns: "authority", "sensory", or "other"
        """
        if param_name in self._layer_types:
            return self._layer_types[param_name]

        # Extract layer index from name
        match = re.search(self.config.layer_pattern, param_name)

        if match:
            layer_idx = int(match.group(1))
            if layer_idx < self.config.authority_layers:
                layer_type = "authority"
            else:
                layer_type = "sensory"
        elif "embed" in param_name.lower() or "token" in param_name.lower():
            # Embedding layers = sensory (grounding)
            layer_type = "sensory"
        elif "head" in param_name.lower() or "lm_head" in param_name.lower():
            # Output heads = authority (meaning)
            layer_type = "authority"
        else:
            layer_type = "other"

        self._layer_types[param_name] = layer_type
        return layer_type

    def _make_hook(self, param_name: str) -> Callable:
        """Create a gradient hook that scales gradients based on layer type."""
        layer_type = self._get_layer_type(param_name)

        def hook(grad: torch.Tensor) -> torch.Tensor:
            if layer_type == "authority":
                alpha = self.alpha_auth
                self.authority_grad_norms.append(grad.norm().item())
            elif layer_type == "sensory":
                alpha = self.alpha_sens
                self.sensory_grad_norms.append(grad.norm().item())
            else:
                alpha = 1.0  # No scaling for "other"

            return grad * alpha

        return hook

    def _register_hooks(self):
        """Register gradient hooks on all model parameters."""
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                hook = self._make_hook(name)
                handle = param.register_hook(hook)
                self._hooks.append(handle)

    def remove_hooks(self):
        """Remove all registered gradient hooks."""
        for handle in self._hooks:
            handle.remove()
        self._hooks.clear()

    def step(self) -> Dict[str, float]:
        """
        Update the scaler state after each training step.

        Should be called AFTER optimizer.step() to update warmup schedule.

        Returns:
            Dict with gradient metrics (s_grad_norm, a_grad_norm, s_a_ratio)
        """
        self.current_step += 1

        # Update alpha_sens based on warmup schedule
        if self.current_step <= self.config.warmup_steps:
            progress = self.current_step / self.config.warmup_steps
            self.alpha_sens = (
                self.config.alpha_sens_initial +
                progress * (self.config.alpha_sens_max - self.config.alpha_sens_initial)
            )
        else:
            self.alpha_sens = self.config.alpha_sens_max

        # Compute metrics
        s_norm = sum(self.sensory_grad_norms) / len(self.sensory_grad_norms) if self.sensory_grad_norms else 0.0
        a_norm = sum(self.authority_grad_norms) / len(self.authority_grad_norms) if self.authority_grad_norms else 1.0
        s_a_ratio = s_norm / a_norm if a_norm > 0 else 0.0

        metrics = {
            "s_grad_norm": s_norm,
            "a_grad_norm": a_norm,
            "s_a_ratio": s_a_ratio,
            "alpha_sens": self.alpha_sens,
            "step": self.current_step,
        }

        # Clear for next step
        self.authority_grad_norms.clear()
        self.sensory_grad_norms.clear()

        return metrics

    def reconfigure_layers(
        self,
        new_authority_layers: int,
        new_sensory_layers: int,
        thaw_alpha: float = 0.05,
    ):
        """
        Reconfigure the layer boundary (e.g., 9:3 → 6:6).

        The newly "unlocked" layers (previously authority, now sensory)
        undergo a "Dampened Thaw" starting at thaw_alpha.

        Args:
            new_authority_layers: New number of authority layers
            new_sensory_layers: New number of sensory layers
            thaw_alpha: Initial alpha for newly thawed layers
        """
        old_authority = self.config.authority_layers

        # Update config
        self.config.authority_layers = new_authority_layers
        self.config.sensory_layers = new_sensory_layers

        # Reset alpha_sens for dampened thaw of newly relaxed layers
        self.alpha_sens = thaw_alpha
        self.config.alpha_sens_initial = thaw_alpha

        # Clear layer type cache to force re-classification
        self._layer_types.clear()

        # Re-register hooks with new classification
        self.remove_hooks()
        self._register_hooks()

    def get_status_string(self) -> str:
        """Get human-readable status string."""
        s_norm = sum(self.sensory_grad_norms) / len(self.sensory_grad_norms) if self.sensory_grad_norms else 0.0
        a_norm = sum(self.authority_grad_norms) / len(self.authority_grad_norms) if self.authority_grad_norms else 1.0
        s_a_ratio = s_norm / a_norm if a_norm > 0 else 0.0

        return (
            f"HGS: S/A={s_a_ratio:.3f} | "
            f"α_sens={self.alpha_sens:.2f} | "
            f"split={self.config.authority_layers}:{self.config.sensory_layers}"
        )


@dataclass
class DynamicRelaxationConfig:
    """Configuration for Dynamic Relaxation Controller."""

    # Stability thresholds
    stability_threshold: float = 0.78  # StabilityIndex >= this to trigger relaxation
    window_size: int = 500  # Rolling window for average mode

    # Mode
    mode: str = "average"  # "consecutive" or "average"
    consecutive_target: int = 5  # For consecutive mode

    # Target layer distribution (9:3 → 6:6)
    initial_authority: int = 9
    initial_sensory: int = 3
    target_authority: int = 6
    target_sensory: int = 6

    # Dampened Thaw for newly relaxed layers
    thaw_alpha_initial: float = 0.05  # Starting alpha for thawed layers
    thaw_alpha_max: float = 0.7       # Target alpha for thawed layers
    thaw_ramp_steps: int = 500        # Steps to ramp thawed layers

    # Safety valve thresholds
    ppl_spike_threshold: float = 0.20  # 20% PPL increase triggers Viparyaya
    guna_coherence_weight: float = 0.70
    s_drift_weight: float = 0.30

    # Viparyaya (correction) mode
    viparyaya_cooldown: int = 100  # Steps to wait after reset


class DynamicRelaxationController:
    """
    Dynamic Relaxation Controller for 9:3 → 6:6 Transition.

    Monitors training stability and triggers layer boundary shift when stable.

    StabilityIndex (SSI) = 0.7 * GC + 0.3 * (1 - Drift)

    Where:
        - GC: Guna Coherence (from dims 0-15 of header)
        - Drift: S-Signal drift magnitude

    Average Mode:
        - Maintains a 500-step rolling window of SSI
        - When window average >= 0.78, trigger relaxation
        - Newly relaxed layers undergo "Dampened Thaw"
    """

    def __init__(
        self,
        gradient_scaler: HierarchicalGradientScaler,
        config: Optional[DynamicRelaxationConfig] = None,
    ):
        self.config = config or DynamicRelaxationConfig()
        self.gradient_scaler = gradient_scaler

        # State tracking
        self.stability_window: deque = deque(maxlen=self.config.window_size)
        self.ppl_history: deque = deque(maxlen=100)
        self.consecutive_count = 0
        self.relaxation_triggered = False
        self.thaw_step = 0

        # Viparyaya state
        self.viparyaya_active = False
        self.viparyaya_countdown = 0

        # Jolt Log for pre/post relaxation PPL
        self.jolt_log: List[Dict] = []

        # Current boundary
        self.current_authority = self.config.initial_authority
        self.current_sensory = self.config.initial_sensory

    def compute_stability_index(
        self,
        guna_coherence: float,
        s_drift: float,
    ) -> float:
        """
        Compute StabilityIndex (SSI) from Guna Coherence and S-Signal drift.

        SSI = 0.7 * GC + 0.3 * (1 - Drift)

        Args:
            guna_coherence: Current Guna Coherence (0-1)
            s_drift: Current S-Signal drift magnitude (clamped to 0-1)

        Returns:
            StabilityIndex in range [0, 1]
        """
        drift_clamped = min(1.0, max(0.0, s_drift))

        stability = (
            self.config.guna_coherence_weight * guna_coherence +
            self.config.s_drift_weight * (1.0 - drift_clamped)
        )

        return stability

    def check_ppl_spike(self, current_ppl: float) -> bool:
        """Check for PPL spike that triggers Viparyaya safety valve."""
        if len(self.ppl_history) < 10:
            return False

        recent_min = min(list(self.ppl_history)[-10:])
        ppl_increase = (current_ppl - recent_min) / recent_min if recent_min > 0 else 0

        return ppl_increase > self.config.ppl_spike_threshold

    def update(
        self,
        guna_coherence: float,
        s_drift: float,
        current_ppl: float,
        step: int,
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Update controller state and potentially trigger relaxation.

        Args:
            guna_coherence: Current Guna Coherence (from training metrics)
            s_drift: Current S-Signal drift
            current_ppl: Current perplexity
            step: Current training step

        Returns:
            Tuple of (relaxed_this_step, metrics_dict)
        """
        self.ppl_history.append(current_ppl)

        # Check for PPL spike (Viparyaya safety valve)
        if self.check_ppl_spike(current_ppl) and not self.viparyaya_active:
            return self._trigger_viparyaya(current_ppl, step)

        # Handle Viparyaya cooldown
        if self.viparyaya_active:
            self.viparyaya_countdown -= 1
            if self.viparyaya_countdown <= 0:
                self.viparyaya_active = False
            return False, self._get_metrics()

        # If already relaxed, handle thaw progression
        if self.relaxation_triggered:
            self.thaw_step += 1
            if self.thaw_step <= self.config.thaw_ramp_steps:
                progress = self.thaw_step / self.config.thaw_ramp_steps
                new_alpha = (
                    self.config.thaw_alpha_initial +
                    progress * (self.config.thaw_alpha_max - self.config.thaw_alpha_initial)
                )
                self.gradient_scaler.alpha_sens = new_alpha

            return False, self._get_metrics()

        # Compute stability
        ssi = self.compute_stability_index(guna_coherence, s_drift)
        self.stability_window.append(ssi)

        # Check if ready to relax based on mode
        can_relax = False

        if self.config.mode == "average":
            if len(self.stability_window) >= self.config.window_size:
                window_avg = sum(self.stability_window) / len(self.stability_window)
                can_relax = window_avg >= self.config.stability_threshold

        else:  # "consecutive" mode
            if ssi >= self.config.stability_threshold:
                self.consecutive_count += 1
            else:
                self.consecutive_count = 0

            can_relax = self.consecutive_count >= self.config.consecutive_target

        # Trigger relaxation if ready
        if can_relax and not self.relaxation_triggered:
            return self._do_relaxation(current_ppl, step)

        return False, self._get_metrics()

    def _do_relaxation(self, pre_ppl: float, step: int) -> Tuple[bool, Dict[str, float]]:
        """Perform the 9:3 → 6:6 boundary shift."""
        self.relaxation_triggered = True
        self.thaw_step = 0

        # Log the jolt
        self.jolt_log.append({
            "step": step,
            "event": "relaxation",
            "pre_ppl": pre_ppl,
            "post_ppl": None,
            "old_split": f"{self.current_authority}:{self.current_sensory}",
            "new_split": f"{self.config.target_authority}:{self.config.target_sensory}",
        })

        # Reconfigure the gradient scaler
        self.gradient_scaler.reconfigure_layers(
            new_authority_layers=self.config.target_authority,
            new_sensory_layers=self.config.target_sensory,
            thaw_alpha=self.config.thaw_alpha_initial,
        )

        self.current_authority = self.config.target_authority
        self.current_sensory = self.config.target_sensory

        print(f"\n  🔄 RELAXATION TRIGGERED: {self.config.initial_authority}:{self.config.initial_sensory} → {self.config.target_authority}:{self.config.target_sensory}")
        print(f"     Dampened Thaw: α={self.config.thaw_alpha_initial} → {self.config.thaw_alpha_max} over {self.config.thaw_ramp_steps} steps")

        return True, self._get_metrics()

    def _trigger_viparyaya(self, current_ppl: float, step: int) -> Tuple[bool, Dict[str, float]]:
        """Trigger Viparyaya safety valve on PPL spike."""
        self.viparyaya_active = True
        self.viparyaya_countdown = self.config.viparyaya_cooldown

        # Log the viparyaya event
        self.jolt_log.append({
            "step": step,
            "event": "viparyaya",
            "ppl_spike": current_ppl,
        })

        print(f"\n  ⚠️ VIPARYAYA TRIGGERED: PPL spike detected ({current_ppl:.1f})")
        print(f"     Cooling down for {self.config.viparyaya_cooldown} steps")

        return False, self._get_metrics()

    def _get_metrics(self) -> Dict[str, float]:
        """Get current controller metrics."""
        window_avg = sum(self.stability_window) / len(self.stability_window) if self.stability_window else 0.0

        return {
            "stability_index": self.stability_window[-1] if self.stability_window else 0.0,
            "stability_avg": window_avg,
            "window_size": len(self.stability_window),
            "relaxation_triggered": 1.0 if self.relaxation_triggered else 0.0,
            "thaw_progress": self.thaw_step / self.config.thaw_ramp_steps if self.relaxation_triggered else 0.0,
            "alpha_sens": self.gradient_scaler.alpha_sens,
            "authority_layers": self.current_authority,
            "sensory_layers": self.current_sensory,
            "viparyaya_active": 1.0 if self.viparyaya_active else 0.0,
        }

    def update_post_ppl(self, post_ppl: float):
        """Update the post-relaxation PPL in the jolt log."""
        if self.jolt_log and self.jolt_log[-1].get("post_ppl") is None:
            self.jolt_log[-1]["post_ppl"] = post_ppl

    def get_jolt_summary(self) -> str:
        """Get human-readable jolt log summary."""
        if not self.jolt_log:
            return "No relaxation events yet"

        lines = ["Jolt Log:"]
        for entry in self.jolt_log[-5:]:
            if entry.get("event") == "viparyaya":
                lines.append(f"  [{entry['step']}] VIPARYAYA: PPL={entry['ppl_spike']:.1f}")
            else:
                post = entry.get('post_ppl', '?')
                post_str = f"{post:.1f}" if isinstance(post, float) else str(post)
                lines.append(
                    f"  [{entry['step']}] Relax: {entry['old_split']} → {entry['new_split']} | "
                    f"PPL {entry['pre_ppl']:.1f} → {post_str}"
                )

        return "\n".join(lines)

    def get_status_string(self) -> str:
        """Get human-readable status string."""
        metrics = self._get_metrics()

        status = (
            f"DRC: SSI_avg={metrics['stability_avg']:.2f} | "
            f"Split={self.current_authority}:{self.current_sensory}"
        )

        if self.relaxation_triggered:
            status += f" | Thaw={metrics['thaw_progress']*100:.0f}%"

        if self.viparyaya_active:
            status += f" | VIPARYAYA({self.viparyaya_countdown})"

        return status


def compute_s_drift(
    current_state: torch.Tensor,
    previous_state: torch.Tensor,
    s_start: int = 16,
    s_end: int = 48,
) -> float:
    """
    Compute S-Signal drift between states.

    Args:
        current_state: [B, 128] current state tensor
        previous_state: [B, 128] previous state tensor
        s_start: Start index of S-Signal (default 16)
        s_end: End index of S-Signal (default 48)

    Returns:
        Mean drift magnitude (scalar)
    """
    s_current = current_state[:, s_start:s_end]
    s_previous = previous_state[:, s_start:s_end]

    drift = (s_current - s_previous).abs().mean()
    return drift.item()


# Legacy compatibility: HierarchicalGradientScalerConfig without model
@dataclass
class HierarchicalGradientScalerConfigLegacy:
    """Legacy configuration (for backward compatibility)."""
    total_layers: int = 12
    authority_layers: int = 9
    sensory_layers: int = 3
    alpha_auth: float = 1.0
    alpha_sens: float = 0.3
    alpha_sens_max: float = 0.7
    authority_prefix: str = "transformer.layers"
    sensory_prefix: str = "transformer.layers"
    s_signal_start: int = 16
    s_signal_end: int = 48
    r_signal_start: int = 48
    r_signal_end: int = 96
