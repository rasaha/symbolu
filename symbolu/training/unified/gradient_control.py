"""
Gradient control utilities for unified LLM training.

Contains HierarchicalGradientScaler for Formula [1331] gradient dampening
and WeightTransfer for 9:3 -> 6:6 dynamic relaxation weight management.
"""

import collections
import torch
import torch.nn as nn
from typing import Dict, List, Optional, Any, Tuple

from symbolu.training.unified.utilities import SOVEREIGN_R_MATRIX


class HierarchicalGradientScaler:
    """
    Implements Formula [1331]: Gradient dampening for 9:3 layer split.

    Prevents 3 Quadratic (Sensory) layers from becoming too Rajasic
    by scaling their gradients relative to the 9 Authority layers.

    Architecture:
        Layers 0-8:  Authority (State-Delta) - Full gradients (α = 1.0)
        Layers 9-11: Sensory (Quadratic)     - Dampened gradients (α = 0.1→0.5)

    Phase Attention Protection:
        During 'Thaw' (9:3 → 6:6 transition), Phase-Attention weights in Authority
        layers receive EXTRA protection via reduced gradient scaling (α_phase = 0.5).
        This ensures the complex O(n) attention matrices (W_phase, W_amp) remain
        stable while the Sensory layers are being relaxed.

    The warmup schedule allows Authority layers to establish stable
    ontological foundations before Sensory layers begin contributing.
    """

    # Parameter name patterns for Phase Attention weights (need protection during Thaw)
    PHASE_ATTENTION_PATTERNS = [
        'W_phase', 'W_amp', 'phase_proj', 'phase_embed', 'amp_gate',
        'attn.W_phase', 'attn.W_amp', 'attn.phase',  # Nested patterns
    ]

    def __init__(
        self,
        model: nn.Module,
        authority_layers: int = 9,      # Layers 0-8
        sensory_layers: int = 3,        # Layers 9-11
        alpha_sens_min: float = 0.1,    # Heavy dampening at start
        alpha_sens_max: float = 0.5,    # Moderate dampening after warmup
        warmup_steps: int = 500,        # Ramp period
        layer_attr: str = "blocks",     # Attribute name for layers
        alpha_phase_protection: float = 0.5,  # Protection factor for Phase Attention weights
        protect_phase_during_thaw: bool = True,  # Enable Phase Attention protection
        # V9.6.8: Layer-wise alpha dampening (Gemini recommendation)
        enable_layerwise_alpha: bool = False,  # Enable per-layer alpha scaling
        alpha_output_scale: float = 0.5,       # Scale for output layers (last 3 sensory)
        alpha_reasoning_scale: float = 1.0,    # Scale for reasoning layers (first 3 sensory)
        authority_floor: float = 1.0,          # Alpha floor for authority layers (1.0 = full gradients)
    ):
        self.model = model
        self.authority_layers = authority_layers
        self.sensory_layers = sensory_layers
        self.alpha_sens_min = alpha_sens_min
        self.alpha_sens_max = alpha_sens_max
        self.warmup_steps = warmup_steps
        self.layer_attr = layer_attr
        self.alpha_phase_protection = alpha_phase_protection
        self.protect_phase_during_thaw = protect_phase_during_thaw
        # V9.6.8: Layer-wise alpha
        self.enable_layerwise_alpha = enable_layerwise_alpha
        self.alpha_output_scale = alpha_output_scale
        self.alpha_reasoning_scale = alpha_reasoning_scale
        self.authority_floor = authority_floor

        self.current_step = 0
        self.hooks = []
        self.hooks_registered = False  # Track if hooks are active
        self.in_thaw_mode = False  # Set to True during 9:3 → 6:6 transition

        # Use bounded deques to prevent memory accumulation over long training
        self._authority_grad_norms = collections.deque(maxlen=1000)
        self._sensory_grad_norms = collections.deque(maxlen=1000)
        self._phase_grad_norms = collections.deque(maxlen=1000)  # Track Phase Attention grads

        # V9.6.0 FIX: EMA authority norm for backward-pass ordering
        # Problem: In backward pass, sensory hooks fire BEFORE authority hooks (layers 11→0)
        # So sensory hooks can't use current step's authority norm - it doesn't exist yet.
        # Solution: Use EMA of authority norm that persists across steps.
        self._ema_authority_norm = 1.0  # Initialize to 1.0, will be updated each step
        self._ema_alpha = 0.1  # EMA decay factor (0.1 = slow adaptation, stable)

        self.gradient_stats = {
            "authority_grad_norm": 0.0,
            "sensory_grad_norm": 0.0,
            "phase_grad_norm": 0.0,
            "sensory_scale": alpha_sens_min,
            "sensory_authority_ratio": 0.0,
            "dynamic_scale_factor": 1.0,  # V9.6.0: Dynamic normalization factor
            "ema_authority_norm": 1.0,  # V9.6.0: Track EMA for debugging
        }

        # Register hooks
        self._register_hooks()

    def _is_phase_attention_param(self, param_name: str) -> bool:
        """Check if parameter is a Phase Attention weight that needs protection."""
        for pattern in self.PHASE_ATTENTION_PATTERNS:
            if pattern in param_name:
                return True
        return False

    def set_thaw_mode(self, in_thaw: bool):
        """Enable/disable Thaw mode for Phase Attention protection."""
        self.in_thaw_mode = in_thaw
        if in_thaw:
            print(f"  [Formula 1331] Thaw mode ENABLED - Phase Attention weights protected (α={self.alpha_phase_protection})")

    def _get_layers(self) -> nn.ModuleList:
        """Get the layer ModuleList from model."""
        all_layers = []

        # SymbolU12 special case: layers_1_8 + individual layers (witness, unifying, etc.)
        if hasattr(self.model, 'layers_1_8'):
            layers_1_8 = getattr(self.model, 'layers_1_8')
            if isinstance(layers_1_8, nn.ModuleList):
                all_layers.extend(list(layers_1_8))

            # Collect individual layers in order (witness, unifying, integration, absolving)
            for layer_name in ['witness_layer', 'unifying_layer', 'integration_layer', 'absolving_layer']:
                if hasattr(self.model, layer_name):
                    layer = getattr(self.model, layer_name)
                    if layer is not None:
                        all_layers.append(layer)

            if len(all_layers) >= 12:
                return nn.ModuleList(all_layers)

        # Try common attribute names
        for attr in [self.layer_attr, "layers", "blocks", "transformer.blocks", "model.layers"]:
            if "." in attr:
                # Handle nested attributes
                obj = self.model
                for part in attr.split("."):
                    obj = getattr(obj, part, None)
                    if obj is None:
                        break
                if obj is not None and isinstance(obj, nn.ModuleList):
                    return obj
            elif hasattr(self.model, attr):
                layers = getattr(self.model, attr)
                if isinstance(layers, nn.ModuleList):
                    return layers

        # Fallback: collect all named children that look like layers
        layer_modules = []
        for name, module in self.model.named_children():
            if 'layer' in name.lower() or 'block' in name.lower():
                if isinstance(module, nn.ModuleList):
                    all_layers.extend(list(module))
                else:
                    layer_modules.append(module)

        if all_layers:
            all_layers.extend(layer_modules)
            return nn.ModuleList(all_layers)

        if layer_modules:
            return nn.ModuleList(layer_modules)

        raise ValueError(f"Could not find layers in model. Tried: {self.layer_attr}")

    def _compute_alpha_sens(self) -> float:
        """Compute current sensory gradient scale based on warmup progress."""
        if self.current_step >= self.warmup_steps:
            return self.alpha_sens_max

        # Linear ramp from min to max
        progress = self.current_step / self.warmup_steps
        alpha = self.alpha_sens_min + (self.alpha_sens_max - self.alpha_sens_min) * progress

        return alpha

    def _create_grad_hook(self, layer_idx: int, is_sensory: bool, param_name: str = ""):
        """
        Create a gradient scaling hook for a specific layer parameter.

        V9.6.0 FIX: Dynamic Normalization (The 58x Overwrite Bug Fix)

        Previous bug: Static scaling (grad * alpha) allowed high-magnitude Sanskrit/Sensory
        gradients to overwrite English/Authority gradients. Even with alpha=0.1, if
        sensory_norm=58 and authority_norm=1, the result was 5.8x overwrite.

        Fix: Normalize sensory gradients to match authority magnitude BEFORE applying alpha.
        scale_factor = authority_norm / sensory_norm
        balanced_grad = grad * scale_factor  (now same magnitude as authority)
        final_grad = balanced_grad * alpha   (THEN apply mixing ratio)

        V9.6.8: Layer-wise Alpha Dampening (Gemini recommendation)
        Output layers (9-11) should be more stable than reasoning layers (6-8).
        - Reasoning layers (first half of sensory): alpha × alpha_reasoning_scale
        - Output layers (last half of sensory): alpha × alpha_output_scale

        Phase Attention Protection:
        During Thaw mode, Phase Attention weights (W_phase, W_amp, etc.) in Authority
        layers receive extra gradient dampening to maintain stability of the complex
        O(n) attention mechanism while Sensory layers are being relaxed.
        """
        is_phase_param = self._is_phase_attention_param(param_name)
        total_layers = self.authority_layers + self.sensory_layers
        sensory_start = self.authority_layers

        def hook(grad):
            if grad is None:
                return grad

            if is_sensory:
                # V9.6.0: Dynamic Normalization with EMA fix
                # Step 1: Get current sensory gradient norm
                sensory_norm = grad.norm().item()
                self._sensory_grad_norms.append(sensory_norm)

                # Step 2: Use EMA authority norm (persists across steps)
                # CRITICAL: In backward pass, sensory hooks fire BEFORE authority hooks
                # So we can't use current step's authority norms - they don't exist yet.
                # EMA provides stable reference from previous steps.
                authority_norm = self._ema_authority_norm

                # Step 3: Compute dynamic scale factor to match magnitudes
                if sensory_norm > 1e-8:  # Avoid division by zero
                    scale_factor = authority_norm / sensory_norm
                    # Clamp scale factor to prevent extreme scaling
                    scale_factor = max(0.01, min(scale_factor, 100.0))
                else:
                    scale_factor = 1.0

                # Step 4: Apply mixing ratio alpha AFTER normalization
                alpha = self._compute_alpha_sens()

                # V9.6.8: Layer-wise alpha dampening
                # Output layers (later in sensory range) should be more stable
                if self.enable_layerwise_alpha:
                    # Determine if this is a "reasoning" or "output" layer
                    # For 6:6 split: layers 6-8 are reasoning, 9-11 are output
                    # For 9:3 split: layers 9-10 are reasoning, 11 is output
                    sensory_midpoint = sensory_start + (self.sensory_layers // 2)
                    if layer_idx < sensory_midpoint:
                        # Reasoning layers (first half of sensory): more expressive
                        alpha = alpha * self.alpha_reasoning_scale
                    else:
                        # Output layers (last half of sensory): more stable
                        alpha = alpha * self.alpha_output_scale

                # balanced_grad has same magnitude as authority gradients
                # final_grad = balanced_grad * alpha = exact alpha% contribution
                scaled_grad = grad * scale_factor * alpha

                # Track stats
                self.gradient_stats["sensory_scale"] = alpha
                self.gradient_stats["sensory_authority_ratio"] = sensory_norm / authority_norm if authority_norm > 1e-8 else 0.0
                self.gradient_stats["dynamic_scale_factor"] = scale_factor

                return scaled_grad
            else:
                # Authority layers
                grad_norm = grad.norm().item()

                # Special handling for Phase Attention weights during Thaw
                if is_phase_param and self.in_thaw_mode and self.protect_phase_during_thaw:
                    # Apply protection factor to Phase Attention weights
                    # This prevents the complex attention matrices from destabilizing
                    # during the 9:3 → 6:6 transition
                    scaled_grad = grad * self.alpha_phase_protection
                    self._phase_grad_norms.append(grad_norm)
                    return scaled_grad

                # Normal authority layers - apply authority_floor dampening
                # authority_floor=1.0 means full gradients, 0.3 means 30% of gradients
                self._authority_grad_norms.append(grad_norm)
                if self.authority_floor < 1.0:
                    return grad * self.authority_floor
                return grad

        return hook

    def _register_hooks(self):
        """Register gradient hooks on all layer parameters."""
        try:
            layers = self._get_layers()
        except ValueError as e:
            print(f"  [Formula 1331] Warning: {e}")
            print(f"  [Formula 1331] Gradient scaling disabled - could not find layers")
            self.hooks_registered = False
            return

        total_layers = len(layers)

        # Determine sensory layer indices (last N in 9:3 split)
        sensory_start = max(0, total_layers - self.sensory_layers)

        print(f"\n  [Formula 1331] Hierarchical Gradient Scaler ENABLED:")
        print(f"    Total layers detected: {total_layers}")
        print(f"    Authority layers: 0-{sensory_start - 1} (α = 1.0)")
        print(f"    Sensory layers: {sensory_start}-{total_layers - 1} (α = {self.alpha_sens_min}→{self.alpha_sens_max})")
        print(f"    Warmup: {self.warmup_steps} steps")
        if self.protect_phase_during_thaw:
            print(f"    Phase Attention Protection: ENABLED (α_phase = {self.alpha_phase_protection} during Thaw)")

        hook_count = 0
        phase_param_count = 0
        for layer_idx, layer in enumerate(layers):
            is_sensory = layer_idx >= sensory_start

            for name, param in layer.named_parameters():
                if param.requires_grad:
                    # Pass parameter name for Phase Attention identification
                    hook = param.register_hook(self._create_grad_hook(layer_idx, is_sensory, name))
                    self.hooks.append(hook)
                    hook_count += 1

                    # Count Phase Attention parameters
                    if not is_sensory and self._is_phase_attention_param(name):
                        phase_param_count += 1

        print(f"    Registered {hook_count} gradient hooks")
        if phase_param_count > 0:
            print(f"    Phase Attention parameters detected: {phase_param_count}")
        self.hooks_registered = True

    def step(self, global_step: Optional[int] = None) -> dict:
        """
        Update current step, compute metrics, and reset gradient accumulators.

        Args:
            global_step: Optional step to set. If not provided, increments internal counter.

        Returns:
            Dict with gradient metrics (s_grad_norm, a_grad_norm, s_a_ratio, alpha_sens, phase_grad_norm)
        """
        if global_step is not None:
            self.current_step = global_step
        else:
            self.current_step += 1

        # Compute accumulated norms from deques
        a_norm = sum(self._authority_grad_norms) if self._authority_grad_norms else 0.0
        s_norm = sum(self._sensory_grad_norms) if self._sensory_grad_norms else 0.0
        p_norm = sum(self._phase_grad_norms) if self._phase_grad_norms else 0.0
        s_a_ratio = s_norm / a_norm if a_norm > 0 else 0.0

        # V9.6.0 FIX: Update EMA authority norm for next step's sensory hooks
        # This is the key fix for backward-pass ordering: we update the EMA AFTER
        # the backward pass completes, so it's available for the NEXT step's sensory hooks.
        if self._authority_grad_norms:
            current_a_mean = a_norm / len(self._authority_grad_norms)
            # EMA update: new = alpha * current + (1 - alpha) * old
            self._ema_authority_norm = (
                self._ema_alpha * current_a_mean +
                (1 - self._ema_alpha) * self._ema_authority_norm
            )

        # Clamp S/A ratio to prevent extreme imbalance at startup
        # Healthy range is 0.3-0.7, warn if outside 0.1-10.0
        s_a_ratio_clamped = max(0.01, min(100.0, s_a_ratio))
        # V9.5.3: Removed emergency damping override - trust configured alpha_sens_initial
        # The old code forcibly set alpha_sens_min=0.005 when S/A>10 in first 100 steps,
        # which defeated the purpose of setting alpha_sens_initial=0.05

        self.gradient_stats["authority_grad_norm"] = a_norm
        self.gradient_stats["sensory_grad_norm"] = s_norm
        self.gradient_stats["phase_grad_norm"] = p_norm
        self.gradient_stats["sensory_authority_ratio"] = s_a_ratio_clamped
        self.gradient_stats["sensory_scale"] = self._compute_alpha_sens()
        self.gradient_stats["ema_authority_norm"] = self._ema_authority_norm  # V9.6.0

        # Prepare metrics for return
        metrics = {
            "s_grad_norm": s_norm,
            "a_grad_norm": a_norm,
            "phase_grad_norm": p_norm,
            "s_a_ratio": s_a_ratio_clamped,
            "s_a_ratio_raw": s_a_ratio,  # Keep raw for debugging
            "alpha_sens": self._compute_alpha_sens(),
            "step": self.current_step,
            "in_thaw_mode": self.in_thaw_mode,
            "dynamic_scale_factor": self.gradient_stats.get("dynamic_scale_factor", 1.0),  # V9.6.0
            "ema_authority_norm": self._ema_authority_norm,  # V9.6.0
        }

        # Clear deques for next step
        self._authority_grad_norms.clear()
        self._sensory_grad_norms.clear()
        self._phase_grad_norms.clear()

        return metrics

    def get_stats(self) -> dict:
        """Get gradient statistics for logging."""
        return self.gradient_stats.copy()

    def get_state(self) -> dict:
        """Get full state for checkpointing."""
        return {
            "authority_layers": self.authority_layers,
            "sensory_layers": self.sensory_layers,
            "alpha_sens_min": self.alpha_sens_min,
            "alpha_sens_max": self.alpha_sens_max,
            "warmup_steps": self.warmup_steps,
            "current_step": self.current_step,
            "gradient_stats": self.gradient_stats.copy(),
            # Phase Attention protection state
            "alpha_phase_protection": self.alpha_phase_protection,
            "protect_phase_during_thaw": self.protect_phase_during_thaw,
            "in_thaw_mode": self.in_thaw_mode,
        }

    def set_state(self, state: dict):
        """Restore state from checkpoint."""
        self.authority_layers = state.get("authority_layers", self.authority_layers)
        self.sensory_layers = state.get("sensory_layers", self.sensory_layers)
        self.alpha_sens_min = state.get("alpha_sens_min", self.alpha_sens_min)
        self.alpha_sens_max = state.get("alpha_sens_max", self.alpha_sens_max)
        self.warmup_steps = state.get("warmup_steps", self.warmup_steps)
        self.current_step = state.get("current_step", self.current_step)
        if "gradient_stats" in state:
            self.gradient_stats.update(state["gradient_stats"])
        # Phase Attention protection state
        self.alpha_phase_protection = state.get("alpha_phase_protection", self.alpha_phase_protection)
        self.protect_phase_during_thaw = state.get("protect_phase_during_thaw", self.protect_phase_during_thaw)
        self.in_thaw_mode = state.get("in_thaw_mode", self.in_thaw_mode)

    def get_status_string(self) -> str:
        """Get human-readable status string for logging."""
        s_a_ratio = self.gradient_stats.get("sensory_authority_ratio", 0.0)
        alpha = self._compute_alpha_sens()
        return (
            f"HGS: S/A={s_a_ratio:.3f} | "
            f"α_sens={alpha:.2f} | "
            f"split={self.authority_layers}:{self.sensory_layers}"
        )

    def clip_grad_norm_by_layer(self, max_norm: float = 1.0) -> Tuple[float, float]:
        """
        Clip gradients separately for authority and sensory layer groups.

        This respects the 9:3 design intent by preventing cross-contamination
        of gradient norms between layer types.

        Args:
            max_norm: Maximum gradient norm for each layer group.

        Returns:
            Tuple of (authority_grad_norm, sensory_grad_norm) after clipping.
        """
        try:
            layers = self._get_layers()
        except ValueError:
            return 0.0, 0.0

        total_layers = len(layers)
        sensory_start = max(0, total_layers - self.sensory_layers)

        # Collect parameters by layer type
        auth_params = []
        sens_params = []

        for layer_idx, layer in enumerate(layers):
            is_sensory = layer_idx >= sensory_start
            for param in layer.parameters():
                if param.requires_grad and param.grad is not None:
                    if is_sensory:
                        sens_params.append(param)
                    else:
                        auth_params.append(param)

        # Clip each group separately
        auth_norm = 0.0
        sens_norm = 0.0

        if auth_params:
            auth_norm = torch.nn.utils.clip_grad_norm_(auth_params, max_norm).item()

        if sens_params:
            sens_norm = torch.nn.utils.clip_grad_norm_(sens_params, max_norm).item()

        return auth_norm, sens_norm

    def remove_hooks(self):
        """Remove all registered hooks."""
        for hook in self.hooks:
            hook.remove()
        self.hooks = []
        print("  [Formula 1331] Gradient hooks removed")

    def reconfigure(
        self,
        new_authority_layers: int,
        new_sensory_layers: int,
        new_alpha_min: float = None,
        new_alpha_max: float = None,
        new_warmup_steps: int = 100,
        alpha_range: tuple = None,  # V9.9.3: Alternative to separate min/max
    ):
        """
        Reconfigure the scaler for a new split configuration.
        Used for dynamic 9:3 → 6:6 transitions and Inverted Curriculum evolution.

        Args:
            new_authority_layers: New count of authority layers
            new_sensory_layers: New count of sensory layers
            new_alpha_min: Minimum alpha for sensory (or use alpha_range)
            new_alpha_max: Maximum alpha for sensory (or use alpha_range)
            new_warmup_steps: Steps for warmup ramp
            alpha_range: Alternative tuple (min, max) for alpha values
        """
        # V9.9.3: Handle alpha_range tuple format
        if alpha_range is not None:
            new_alpha_min, new_alpha_max = alpha_range
        elif new_alpha_min is None or new_alpha_max is None:
            # Use current values if not specified
            new_alpha_min = new_alpha_min or self.alpha_sens_min
            new_alpha_max = new_alpha_max or self.alpha_sens_max

        # Remove existing hooks
        self.remove_hooks()

        # Update configuration
        self.authority_layers = new_authority_layers
        self.sensory_layers = new_sensory_layers
        self.alpha_sens_min = new_alpha_min
        self.alpha_sens_max = new_alpha_max
        self.warmup_steps = new_warmup_steps
        self.current_step = 0  # Reset warmup counter

        # Re-register hooks with new configuration
        self._register_hooks()

        print(f"  [Formula 1331] Reconfigured: {new_authority_layers}:{new_sensory_layers} split")
        print(f"    New α range: {new_alpha_min} → {new_alpha_max} over {new_warmup_steps} steps")


class WeightTransfer:
    """
    Manages weight transfer during 9:3 → 6:6 dynamic relaxation.

    When the relaxation trigger fires, this class:
    1. Captures weights from Layers 6, 7, 8 (StateDeltaPhaseBlocks)
    2. Initializes new QuadraticAttentionWithPhaseBias blocks using pre-trained weights
    3. Re-anchors R_to_phase_bias projection to Layer 5 (new Witness)
    4. Implements Guna-Lock: freezes W_q, W_k for first 50 steps post-swap

    Weight Mapping (StateDeltaPhaseBlock → QuadraticAttentionWithPhaseBias):
        Phase Attention v_proj → Quadratic v_proj
        Phase Attention out_proj → Quadratic out_proj
        norm1 → norm1
        ffn → ffn
        norm2 → norm2
        r_signal_proj → r_to_phase_bias (dimension-adjusted)

    Guna-Lock prevents 'Rajasic' noise from destroying inherited ontological logic
    by freezing query/key matrices while allowing values and phase-bias to train.
    """

    def __init__(
        self,
        model: nn.Module,
        guna_lock_steps: int = 50,       # Steps to freeze W_q/W_k post-swap
        anchor_layer_idx: int = 5,        # New Witness layer index after 6:6
        transferred_layers: Tuple[int, int, int] = (6, 7, 8),  # Layers to transfer
    ):
        self.model = model
        self.guna_lock_steps = guna_lock_steps
        self.anchor_layer_idx = anchor_layer_idx
        self.transferred_layers = transferred_layers

        # State tracking
        self.captured_weights = {}
        self.captured_r_anchor = None
        self.guna_lock_active = False
        self.guna_lock_start_step = None
        self.frozen_params = []

        # Track new Quadratic layers for Guna-Lock
        self.new_quadratic_layers = []

    def capture_state(self) -> Dict[str, Any]:
        """
        Capture current weights from Layers 6, 7, 8 (StateDeltaPhaseBlocks).

        Returns dict with captured weight tensors for each layer.
        """
        self.captured_weights = {}

        # Get the layers from model
        layers = self._get_model_layers()
        if layers is None:
            print("  ⚠️  [WeightTransfer] Could not find model layers")
            return {}

        for layer_idx in self.transferred_layers:
            if layer_idx >= len(layers):
                continue

            layer = layers[layer_idx]
            layer_weights = {}

            # Capture attention weights
            if hasattr(layer, 'attn'):
                attn = layer.attn
                # PhaseAttentionLayer weights
                if hasattr(attn, 'v_proj'):
                    layer_weights['v_proj'] = attn.v_proj.weight.data.clone()
                    if attn.v_proj.bias is not None:
                        layer_weights['v_proj_bias'] = attn.v_proj.bias.data.clone()
                if hasattr(attn, 'out_proj'):
                    layer_weights['out_proj'] = attn.out_proj.weight.data.clone()
                    if attn.out_proj.bias is not None:
                        layer_weights['out_proj_bias'] = attn.out_proj.bias.data.clone()
                # Phase-specific weights for reference
                if hasattr(attn, 'W_phase'):
                    layer_weights['W_phase'] = attn.W_phase.weight.data.clone()
                if hasattr(attn, 'W_amp'):
                    layer_weights['W_amp'] = attn.W_amp.weight.data.clone()

            # Capture norm1
            if hasattr(layer, 'norm1'):
                layer_weights['norm1_weight'] = layer.norm1.weight.data.clone()
                layer_weights['norm1_bias'] = layer.norm1.bias.data.clone()

            # Capture FFN
            if hasattr(layer, 'ffn'):
                ffn = layer.ffn
                if isinstance(ffn, nn.Sequential):
                    for i, module in enumerate(ffn):
                        if isinstance(module, nn.Linear):
                            layer_weights[f'ffn_{i}_weight'] = module.weight.data.clone()
                            if module.bias is not None:
                                layer_weights[f'ffn_{i}_bias'] = module.bias.data.clone()

            # Capture norm2
            if hasattr(layer, 'norm2'):
                layer_weights['norm2_weight'] = layer.norm2.weight.data.clone()
                layer_weights['norm2_bias'] = layer.norm2.bias.data.clone()

            # Capture R-Signal projection (for re-anchoring)
            if hasattr(layer, 'r_signal_proj'):
                layer_weights['r_signal_proj'] = layer.r_signal_proj.weight.data.clone()
                if layer.r_signal_proj.bias is not None:
                    layer_weights['r_signal_proj_bias'] = layer.r_signal_proj.bias.data.clone()

            self.captured_weights[layer_idx] = layer_weights

        # Capture the R-Signal anchor from the new Witness (Layer 5 in 6:6)
        if self.anchor_layer_idx < len(layers):
            anchor_layer = layers[self.anchor_layer_idx]
            if hasattr(anchor_layer, 'r_signal_proj'):
                self.captured_r_anchor = {
                    'weight': anchor_layer.r_signal_proj.weight.data.clone(),
                    'bias': anchor_layer.r_signal_proj.bias.data.clone() if anchor_layer.r_signal_proj.bias is not None else None
                }

        print(f"  📦 [WeightTransfer] Captured weights from layers {self.transferred_layers}")
        print(f"    R-Signal anchor captured from layer {self.anchor_layer_idx}")

        return self.captured_weights

    def transfer_weights(
        self,
        new_layers: List[nn.Module],
        r_signal_dim: int = 48,
    ) -> bool:
        """
        Transfer captured weights to new QuadraticAttentionWithPhaseBias blocks.

        Args:
            new_layers: List of new QuadraticAttentionWithPhaseBias modules
            r_signal_dim: Dimension of R-Signal for phase bias

        Returns:
            True if transfer successful
        """
        if not self.captured_weights:
            print("  ⚠️  [WeightTransfer] No weights captured, skipping transfer")
            return False

        self.new_quadratic_layers = new_layers

        for i, new_layer in enumerate(new_layers):
            layer_idx = self.transferred_layers[i] if i < len(self.transferred_layers) else None
            if layer_idx is None or layer_idx not in self.captured_weights:
                continue

            weights = self.captured_weights[layer_idx]

            # Transfer v_proj
            if 'v_proj' in weights and hasattr(new_layer, 'v_proj'):
                new_layer.v_proj.weight.data.copy_(weights['v_proj'])
                if 'v_proj_bias' in weights and new_layer.v_proj.bias is not None:
                    new_layer.v_proj.bias.data.copy_(weights['v_proj_bias'])

            # Transfer out_proj
            if 'out_proj' in weights and hasattr(new_layer, 'out_proj'):
                new_layer.out_proj.weight.data.copy_(weights['out_proj'])
                if 'out_proj_bias' in weights and new_layer.out_proj.bias is not None:
                    new_layer.out_proj.bias.data.copy_(weights['out_proj_bias'])

            # Initialize Q, K from V (State-Inference: inherit value-based attention)
            # This preserves the learned "what to attend to" logic
            if 'v_proj' in weights:
                if hasattr(new_layer, 'q_proj'):
                    new_layer.q_proj.weight.data.copy_(weights['v_proj'])
                    if 'v_proj_bias' in weights and new_layer.q_proj.bias is not None:
                        new_layer.q_proj.bias.data.copy_(weights['v_proj_bias'])
                if hasattr(new_layer, 'k_proj'):
                    new_layer.k_proj.weight.data.copy_(weights['v_proj'])
                    if 'v_proj_bias' in weights and new_layer.k_proj.bias is not None:
                        new_layer.k_proj.bias.data.copy_(weights['v_proj_bias'])

            # Transfer norm1
            if 'norm1_weight' in weights and hasattr(new_layer, 'norm1'):
                new_layer.norm1.weight.data.copy_(weights['norm1_weight'])
                new_layer.norm1.bias.data.copy_(weights['norm1_bias'])

            # Transfer FFN
            if hasattr(new_layer, 'ffn') and isinstance(new_layer.ffn, nn.Sequential):
                for j, module in enumerate(new_layer.ffn):
                    if isinstance(module, nn.Linear):
                        weight_key = f'ffn_{j}_weight'
                        bias_key = f'ffn_{j}_bias'
                        if weight_key in weights:
                            module.weight.data.copy_(weights[weight_key])
                        if bias_key in weights and module.bias is not None:
                            module.bias.data.copy_(weights[bias_key])

            # Transfer norm2
            if 'norm2_weight' in weights and hasattr(new_layer, 'norm2'):
                new_layer.norm2.weight.data.copy_(weights['norm2_weight'])
                new_layer.norm2.bias.data.copy_(weights['norm2_bias'])

            # Initialize r_to_phase_bias from r_signal_proj (48D Anchor)
            if 'r_signal_proj' in weights and hasattr(new_layer, 'r_to_phase_bias'):
                # r_signal_proj: [embed_dim, r_signal_dim]
                # r_to_phase_bias: Sequential([Linear(r_signal_dim, embed_dim), Tanh])
                for module in new_layer.r_to_phase_bias:
                    if isinstance(module, nn.Linear):
                        # Transpose to match dimensions: [r_signal_dim, embed_dim] → [embed_dim, r_signal_dim]
                        source_weight = weights['r_signal_proj']
                        if source_weight.shape[0] == module.weight.shape[1]:
                            # Direct transpose copy
                            module.weight.data.copy_(source_weight.T)
                        else:
                            # Dimension mismatch, initialize with scaled version
                            nn.init.xavier_uniform_(module.weight)
                            # Scale down for stability
                            module.weight.data *= 0.1
                        break

        print(f"  ✓ [WeightTransfer] Transferred weights to {len(new_layers)} new layers")
        return True

    def anchor_r_signal(self, new_witness_layer: nn.Module) -> bool:
        """
        Re-anchor R_to_phase_bias projection to Layer 5 (new Witness).

        The 48D R-Signal anchor ensures continuity of the Authority → Sensory
        nerve signal after the layer split changes.
        """
        if self.captured_r_anchor is None:
            print("  ⚠️  [WeightTransfer] No R-Signal anchor captured")
            return False

        # Update the new witness layer's R-Signal projection
        if hasattr(new_witness_layer, 'r_signal_proj'):
            new_witness_layer.r_signal_proj.weight.data.copy_(self.captured_r_anchor['weight'])
            if self.captured_r_anchor['bias'] is not None and new_witness_layer.r_signal_proj.bias is not None:
                new_witness_layer.r_signal_proj.bias.data.copy_(self.captured_r_anchor['bias'])

        # Also update witness_r_proj in the main model if it exists
        if hasattr(self.model, 'witness_r_proj'):
            if self.model.witness_r_proj.weight.shape == self.captured_r_anchor['weight'].shape:
                self.model.witness_r_proj.weight.data.copy_(self.captured_r_anchor['weight'])
                if self.captured_r_anchor['bias'] is not None and self.model.witness_r_proj.bias is not None:
                    self.model.witness_r_proj.bias.data.copy_(self.captured_r_anchor['bias'])

        print(f"  ⚓ [WeightTransfer] R-Signal anchored to layer {self.anchor_layer_idx}")
        return True

    def activate_guna_lock(self, current_step: int):
        """
        Activate Guna-Lock: freeze W_q and W_k matrices of new layers.

        For the first 50 steps post-swap, only W_v and Phase-Bias can train.
        This prevents 'Rajasic' noise from destroying inherited logic.
        """
        self.guna_lock_active = True
        self.guna_lock_start_step = current_step
        self.frozen_params = []

        for layer in self.new_quadratic_layers:
            # Freeze Q and K projections
            if hasattr(layer, 'q_proj'):
                layer.q_proj.weight.requires_grad = False
                if layer.q_proj.bias is not None:
                    layer.q_proj.bias.requires_grad = False
                self.frozen_params.append(layer.q_proj)

            if hasattr(layer, 'k_proj'):
                layer.k_proj.weight.requires_grad = False
                if layer.k_proj.bias is not None:
                    layer.k_proj.bias.requires_grad = False
                self.frozen_params.append(layer.k_proj)

        print(f"  🔒 [WeightTransfer] Guna-Lock ACTIVATED at step {current_step}")
        print(f"    Frozen: W_q, W_k for {len(self.new_quadratic_layers)} layers")
        print(f"    Active: W_v, Phase-Bias, FFN")
        print(f"    Duration: {self.guna_lock_steps} steps")

    def update_guna_lock(self, current_step: int) -> bool:
        """
        Check and update Guna-Lock status.

        Returns True if lock was just released.
        """
        if not self.guna_lock_active:
            return False

        if self.guna_lock_start_step is None:
            return False

        elapsed = current_step - self.guna_lock_start_step

        if elapsed >= self.guna_lock_steps:
            # Release the lock
            return self.release_guna_lock()

        return False

    def release_guna_lock(self) -> bool:
        """
        Release Guna-Lock: unfreeze W_q and W_k matrices.

        Called automatically after guna_lock_steps or manually for early release.
        """
        if not self.guna_lock_active:
            return False

        for layer in self.new_quadratic_layers:
            if hasattr(layer, 'q_proj'):
                layer.q_proj.weight.requires_grad = True
                if layer.q_proj.bias is not None:
                    layer.q_proj.bias.requires_grad = True

            if hasattr(layer, 'k_proj'):
                layer.k_proj.weight.requires_grad = True
                if layer.k_proj.bias is not None:
                    layer.k_proj.bias.requires_grad = True

        self.guna_lock_active = False
        self.frozen_params = []

        print(f"  🔓 [WeightTransfer] Guna-Lock RELEASED")
        print(f"    All parameters now trainable")
        return True

    def _get_model_layers(self) -> Optional[nn.ModuleList]:
        """Get the layer ModuleList from model."""
        # SymbolU12 special case
        if hasattr(self.model, 'layers_1_8'):
            layers = list(self.model.layers_1_8)
            # Add witness, unifying, integration, absolving
            for layer_name in ['witness_layer', 'unifying_layer', 'integration_layer', 'absolving_layer']:
                if hasattr(self.model, layer_name):
                    layer = getattr(self.model, layer_name)
                    if layer is not None:
                        layers.append(layer)
            return nn.ModuleList(layers)

        # Try common attribute names
        for attr in ['layers', 'blocks', 'transformer.blocks']:
            if hasattr(self.model, attr):
                layers = getattr(self.model, attr)
                if isinstance(layers, nn.ModuleList):
                    return layers

        return None

    def get_status(self) -> Dict[str, Any]:
        """Get current status of weight transfer and Guna-Lock."""
        return {
            "weights_captured": bool(self.captured_weights),
            "layers_captured": list(self.captured_weights.keys()),
            "r_anchor_captured": self.captured_r_anchor is not None,
            "guna_lock_active": self.guna_lock_active,
            "guna_lock_start_step": self.guna_lock_start_step,
            "guna_lock_remaining": (
                self.guna_lock_steps - (self.guna_lock_start_step or 0)
                if self.guna_lock_active else 0
            ),
            "new_layers_count": len(self.new_quadratic_layers),
        }
