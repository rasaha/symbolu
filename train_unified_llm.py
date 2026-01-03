#!/usr/bin/env python3
"""
Unified LLM Training Script V9.4.5
===================================

Train SymbolU models with support for:
1. SymbolU12 with Bhava (standard attention + 12D ontological + 144D bhava)
2. Phase Attention (O(n) complexity)
3. Hybrid (Local + Phase attention)
4. Gen 2: Hierarchical Complex Bhava (3-tier phase rotation)

Now includes PIDv2 Governor from train_pid.py:
- Dynamic SNR-Adjusted Kp
- Semantic Validation (W_s weight)
- Handshake D-term Dampening
- Stress Test Framework
- V9.4.5: Friction Controller with Corrective Actions

Usage:
------
    # Train SymbolU12 with Bhava (standard attention + ontological)
    python train_unified_llm.py --model_type ontological --model_size small \
        --dataset wikitext103 --max_steps 1000

    # Train Phase model (O(n) attention)
    python train_unified_llm.py --model_type phase --model_size small \
        --dataset wikitext103 --max_steps 1000

    # Train Hybrid model (Local + Phase) with PIDv2 Governor
    python train_unified_llm.py --model_type hybrid --model_size small \
        --dataset wikitext103 --max_steps 1000 --controller pidv2

    # Train Gen 2 model (Hierarchical Complex Bhava)
    python train_unified_llm.py --model_type gen2 --model_size small \
        --dataset wikitext103 --max_steps 1000

    # Long context training (16K/32K)
    python train_unified_llm.py --model_type gen2 --model_size small \
        --max_seq_len 16384 --gradient_checkpointing --batch_size 1

    # Stress Test (Trial by Fire)
    python train_unified_llm.py --stress_test --resume checkpoints/best.pt

Author: SymbolU Team
Date: December 2025
"""

import argparse
import collections
import json
import logging
import math
import os
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR

# Hugging Face imports
try:
    from transformers import AutoTokenizer
    from datasets import load_dataset
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

# TensorBoard
try:
    from torch.utils.tensorboard import SummaryWriter
    TENSORBOARD_AVAILABLE = True
except ImportError:
    TENSORBOARD_AVAILABLE = False

# Local imports
sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import (
    PhaseTransformer,
    HybridPhaseTransformer,
)

# Import ontological models
try:
    from symbolu.ontological.symbolu12_bhava import (
        SymbolU12LLMWithBhava,
        SymbolU12OptimizedWithBhava,
        SymbolU12BhavaConfig,
    )
    from symbolu.ontological.bhava_relationships import (
        BHAVA_SIGNIFICANCES,
        get_relationship_meaning,
    )
    ONTOLOGICAL_AVAILABLE = True
except ImportError as e:
    ONTOLOGICAL_AVAILABLE = False
    print(f"Warning: Ontological models not available: {e}")

# Import Sovereign-1 components
try:
    from symbolu.sovereign import SovereignLoss, SovereignObserver
    from symbolu.sovereign.loss import LegacyLossAdapter
    SOVEREIGN_AVAILABLE = True
except ImportError as e:
    SOVEREIGN_AVAILABLE = False
    print(f"Warning: Sovereign-1 modules not available: {e}")

# Import Gen 2 models (Hierarchical Complex Bhava)
try:
    from symbolu.ontological.symbolu12_gen2 import (
        SymbolU12Gen2,
        SymbolU12Gen2Config,
        create_symbolu12_gen2_small,
        create_symbolu12_gen2_medium,
        create_symbolu12_gen2_large,
    )
    GEN2_AVAILABLE = True
except ImportError as e:
    GEN2_AVAILABLE = False
    print(f"Warning: Gen 2 models not available: {e}")

# Import PIDv2 Governor from train_pid.py
try:
    from train_pid import (
        AuthorityPIDv2,
        AuthorityPIDv2Config,
        EmergencyPD,
        EmergencyPDConfig,
        compute_semantic_ppl,
        measure_friction,  # V9.4.5: Friction Monitor
        FrictionController,  # V9.4.5: Friction Controller with Corrective Actions
        FrictionControllerConfig,
    )
    from train import cleanup_old_checkpoints
    PIDV2_AVAILABLE = True
except ImportError as e:
    PIDV2_AVAILABLE = False
    print(f"Warning: PIDv2 controller not available: {e}")

# Import utilities from hierarchical_gradient_scaler module
# Note: Main classes (HierarchicalGradientScaler, DynamicRelaxationController) are
# defined locally below for direct integration with training loop
try:
    from symbolu.sovereign.hierarchical_gradient_scaler import compute_s_drift
    COMPUTE_S_DRIFT_AVAILABLE = True
except ImportError:
    COMPUTE_S_DRIFT_AVAILABLE = False
    compute_s_drift = None


# =============================================================================
# PERFORMANCE OPTIMIZATIONS
# =============================================================================
# TF32 for faster matrix multiplications on Ampere+ GPUs (A100, H100)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# cuDNN autotuning for optimal convolution algorithms
torch.backends.cudnn.benchmark = True


# =============================================================================
# FORMULA [1331]: HIERARCHICAL GRADIENT SCALING FOR 9:3 SPLIT
# =============================================================================

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

        self.current_step = 0
        self.hooks = []
        self.hooks_registered = False  # Track if hooks are active
        self.in_thaw_mode = False  # Set to True during 9:3 → 6:6 transition

        # Use bounded deques to prevent memory accumulation over long training
        self._authority_grad_norms = collections.deque(maxlen=1000)
        self._sensory_grad_norms = collections.deque(maxlen=1000)
        self._phase_grad_norms = collections.deque(maxlen=1000)  # Track Phase Attention grads

        self.gradient_stats = {
            "authority_grad_norm": 0.0,
            "sensory_grad_norm": 0.0,
            "phase_grad_norm": 0.0,
            "sensory_scale": alpha_sens_min,
            "sensory_authority_ratio": 0.0,
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

        Phase Attention Protection:
        During Thaw mode, Phase Attention weights (W_phase, W_amp, etc.) in Authority
        layers receive extra gradient dampening to maintain stability of the complex
        O(n) attention mechanism while Sensory layers are being relaxed.
        """
        is_phase_param = self._is_phase_attention_param(param_name)

        def hook(grad):
            if grad is None:
                return grad

            if is_sensory:
                # Apply dampening to sensory layers
                alpha = self._compute_alpha_sens()
                scaled_grad = grad * alpha

                # Track stats using bounded deques
                self._sensory_grad_norms.append(grad.norm().item())
                self.gradient_stats["sensory_scale"] = alpha

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

                # Normal authority layers get full gradient
                self._authority_grad_norms.append(grad_norm)
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

        self.gradient_stats["authority_grad_norm"] = a_norm
        self.gradient_stats["sensory_grad_norm"] = s_norm
        self.gradient_stats["phase_grad_norm"] = p_norm
        self.gradient_stats["sensory_authority_ratio"] = s_a_ratio
        self.gradient_stats["sensory_scale"] = self._compute_alpha_sens()

        # Prepare metrics for return
        metrics = {
            "s_grad_norm": s_norm,
            "a_grad_norm": a_norm,
            "phase_grad_norm": p_norm,
            "s_a_ratio": s_a_ratio,
            "alpha_sens": self._compute_alpha_sens(),
            "step": self.current_step,
            "in_thaw_mode": self.in_thaw_mode,
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
        new_alpha_min: float,
        new_alpha_max: float,
        new_warmup_steps: int,
    ):
        """
        Reconfigure the scaler for a new split configuration.
        Used for dynamic 9:3 → 6:6 transitions.
        """
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


# =============================================================================
# WEIGHT TRANSFER FOR 9:3 → 6:6 TRANSITION
# =============================================================================

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


# =============================================================================
# DYNAMIC RELAXATION CONTROLLER: 9:3 → 6:6 TRANSITION
# =============================================================================

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
        stability_window: int = 500,        # Steps for stability check
        mode: str = "consecutive",          # "consecutive" or "average"
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
    ):
        self.gradient_scaler = gradient_scaler
        self.model = model

        # Thresholds
        self.stability_threshold = stability_threshold
        self.stability_window = stability_window
        self.mode = mode.lower()
        self.ppl_spike_threshold = ppl_spike_threshold
        self.recovery_steps = recovery_steps

        # Validate mode
        if self.mode not in ("consecutive", "average"):
            raise ValueError(f"relaxation_mode must be 'consecutive' or 'average', got '{mode}'")

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

    def _check_relaxation_ready(self, stability_index: float) -> bool:
        """
        Check if relaxation should trigger based on current mode.

        Modes:
        - consecutive: Requires SSI >= threshold for N consecutive steps
        - average: Requires average SSI >= threshold over rolling N-step window
        """
        if self.mode == "consecutive":
            # Consecutive mode: reset on any dip
            if stability_index >= self.stability_threshold:
                self.stability_streak += 1
                return self.stability_streak >= self.stability_window
            else:
                self.stability_streak = 0
                return False

        else:  # average mode
            # Average mode: rolling window mean
            self.ssi_rolling_window.append(stability_index)
            if len(self.ssi_rolling_window) > self.stability_window:
                self.ssi_rolling_window.pop(0)

            if len(self.ssi_rolling_window) >= self.stability_window:
                avg_ssi = sum(self.ssi_rolling_window) / len(self.ssi_rolling_window)
                return avg_ssi >= self.stability_threshold

            return False

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
    ) -> Tuple[bool, str]:
        """
        Update controller state based on current metrics.

        Returns:
            (state_changed, action): Whether state changed and what action to take
            action can be: "NONE", "RELAX", "RECOVER", "RESUME"
        """
        stability_index = self.compute_stability_index(guna_coherence, s_drift_ema)

        # Track history
        self.stability_history.append({
            "step": global_step,
            "stability": stability_index,
            "gc": guna_coherence,
            "drift": s_drift_ema,
            "ppl": val_ppl,
            "state": self.state,
        })
        if len(self.stability_history) > self.max_history:
            self.stability_history = self.stability_history[-self.max_history:]

        action = "NONE"

        # State machine
        if self.state == self.STATE_AUTHORITY:
            # Check if we should trigger relaxation (mode-dependent)
            if self._check_relaxation_ready(stability_index):
                # Ready to relax!
                self.state = self.STATE_RELAXING
                self.pre_relaxation_ppl = val_ppl
                self.relaxation_step = global_step
                action = "RELAX"
                self.transitions.append({
                    "step": global_step,
                    "from": "AUTHORITY",
                    "to": "BALANCED",
                    "stability": stability_index,
                    "ppl": val_ppl,
                    "mode": self.mode,
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
                    print(f"\n  ⚠️ [DynamicRelaxation] VIPARYAYA TRIGGERED!")
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
        print(f"\n  🔄 [DynamicRelaxation] VIPARYAYA RECOVERY: Reverting to {self.authority_split}")

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

        if self.state == self.STATE_RECOVERY:
            return f"Split:{split_str} State:RECOVERY Streak:{streak_str}{lock_str}"
        elif self.state == self.STATE_BALANCED:
            return f"Split:{split_str} State:BALANCED ✓{lock_str}"
        else:
            return f"Split:{split_str} State:{self.state} Streak:{streak_str}{lock_str}"

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


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class UnifiedTrainingConfig:
    """Unified training configuration for all model types."""

    # Model architecture
    model_type: str = "ontological"  # ontological, phase, hybrid
    model_size: str = "small"  # tiny, small, medium, large
    vocab_size: int = 50257
    max_seq_len: int = 2048
    dropout: float = 0.1

    # Phase-specific parameters
    sync_steps: int = 3
    sync_lr: float = 0.1

    # Hybrid-specific parameters
    local_layers: int = 4
    window_size: int = 256
    local_backend: str = "auto"
    alpha_local: float = 0.8
    alpha_phase: float = 0.2

    # Alpha decay schedule (for phase/hybrid attention)
    alpha_phase_start: float = 0.6
    alpha_phase_end: float = 0.4
    alpha_decay_steps: int = 10000

    # Ontological-specific parameters
    bhava_embed_dim: int = 128
    num_drishti_heads: int = 4

    # Training hyperparameters
    batch_size: int = 8
    gradient_accumulation: int = 1
    max_steps: int = 10000
    warmup_steps: int = 500

    # Optimizer
    learning_rate: float = 3e-4
    weight_decay: float = 0.1
    beta1: float = 0.9
    beta2: float = 0.95
    max_grad_norm: float = 1.0
    use_per_layer_clipping: bool = False  # Clip auth/sens layers separately

    # Mixed precision
    mixed_precision: str = "bf16"

    # Gradient checkpointing
    gradient_checkpointing: bool = False

    # Checkpointing
    checkpoint_dir: str = "checkpoints_unified"
    save_every: int = 1000
    eval_every: int = 100
    log_every: int = 10

    # Dataset
    dataset: str = "wikitext103"
    tokenizer: str = "gpt2"

    # Loss weights for ontological model
    lambda_lm: float = 1.0        # Language modeling loss
    lambda_bhava: float = 0.1     # Bhava relationship consistency
    lambda_coherence: float = 0.05  # Global coherence
    lambda_entropy: float = 0.01  # Entropy regularization

    # Sovereign-1 loss configuration (hardened decomposed loss)
    use_sovereign_loss: bool = True  # Enable Sovereign-1 decomposed loss
    sovereign_weight_guna: float = 1.0   # Guna signal weight
    sovereign_weight_s: float = 2.0      # S-Signal (referent) weight
    sovereign_weight_r: float = 5.0      # R-Signal (ontology) weight - CRITICAL
    sovereign_weight_c: float = 0.5      # C-Signal (phoneme) weight

    # Coherence loss (for phase/hybrid)
    use_coherence_loss: bool = False
    no_coherence_loss: bool = False  # CLI flag to disable

    # PIDv2 Controller settings (V9.4.4)
    controller: str = "none"  # none, pidv2, emergency_pd
    pidv2_kp_min: float = 0.10
    pidv2_kp_max: float = 0.30
    pidv2_kp_sensitivity: float = 5.0
    pidv2_ki: float = 0.02
    pidv2_kd: float = 0.10
    pidv2_a_min: float = 0.30
    pidv2_c_floor: float = 0.68
    pidv2_c_good: float = 0.76
    pidv2_w_s: float = 0.30  # Semantic weight
    pidv2_semantic_scale: float = 50.0
    pidv2_handshake_dampen: bool = True

    # Phase ramp settings (for handshake dampening)
    phase_delay_steps: int = 0
    phase_ramp_steps: int = 7000

    # Formula [1331]: 9:3 Hierarchical Split Configuration
    use_9_3_split: bool = False           # Enable 9:3 Authority/Sensory gradient scaling
    authority_layers: int = 9             # Number of Authority (State-Delta) layers
    sensory_layers: int = 3               # Number of Sensory (Quadratic) layers
    alpha_sens_initial: float = 0.1       # Initial sensory gradient multiplier (heavy dampening)
    alpha_sens_max: float = 0.7           # Maximum sensory gradient (after warmup/relaxation)
    gradient_warmup_steps: int = 500      # Steps to ramp α_sens from initial to max

    # Dynamic Relaxation: 9:3 → 6:6 transition
    enable_dynamic_relaxation: bool = False  # Enable automatic 9:3 → 6:6 transition
    relaxation_mode: str = "average"         # "consecutive" or "average"
    relaxation_stability_threshold: float = 0.78  # StabilityIndex threshold
    relaxation_stability_window: int = 500   # Steps for stability check (rolling window)
    relaxation_streak_target: int = 5        # Consecutive stable evals (for consecutive mode)
    relaxation_target_authority: int = 6     # Target authority layers after relaxation
    relaxation_target_sensory: int = 6       # Target sensory layers after relaxation
    relaxation_thaw_alpha: float = 0.05      # Dampened Thaw starting α for new sensory layers
    relaxation_thaw_steps: int = 500         # Steps for Dampened Thaw warmup
    relaxation_ppl_spike_threshold: float = 0.20  # PPL spike % to trigger Viparyaya
    relaxation_recovery_steps: int = 100     # Steps to stay in recovery mode

    # Resume checkpoint
    resume: str = ""
    resume_weights_only: bool = False

    # TensorBoard
    tensorboard: bool = True

    # Hardware
    device: str = "auto"
    num_workers: int = 4

    # Seed
    seed: int = 42


# Model size presets
MODEL_PRESETS = {
    "tiny": {
        "embed_dim": 256,
        "num_layers": 6,
        "num_heads": 4,
        "ff_dim": 1024,
    },
    "small": {
        "embed_dim": 512,
        "num_layers": 8,
        "num_heads": 8,
        "ff_dim": 2048,
    },
    "medium": {
        "embed_dim": 768,
        "num_layers": 12,
        "num_heads": 12,
        "ff_dim": 3072,
    },
    "large": {
        "embed_dim": 1024,
        "num_layers": 16,
        "num_heads": 16,
        "ff_dim": 4096,
    },
}


# =============================================================================
# DATASET
# =============================================================================

class TextDataset(Dataset):
    """Dataset for language modeling."""

    def __init__(self, tokens: torch.Tensor, seq_len: int):
        self.tokens = tokens
        self.seq_len = seq_len
        self.num_samples = len(tokens) // seq_len

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        start = idx * self.seq_len
        end = start + self.seq_len + 1
        chunk = self.tokens[start:end]
        return chunk[:-1], chunk[1:]


def load_data(config: UnifiedTrainingConfig, tokenizer) -> Tuple[DataLoader, DataLoader]:
    """Load and tokenize dataset."""
    print(f"Loading {config.dataset} dataset...")

    if config.dataset == "wikitext103":
        ds = load_dataset("wikitext", "wikitext-103-v1")
    elif config.dataset == "wikitext2":
        ds = load_dataset("wikitext", "wikitext-2-v1")
    else:
        raise ValueError(f"Unknown dataset: {config.dataset}")

    def tokenize(split):
        text = "\n".join(ds[split]["text"])
        if hasattr(tokenizer, "encode"):
            tokens = tokenizer.encode(text)
        else:
            tokens = tokenizer(text)["input_ids"]
        return torch.tensor(tokens, dtype=torch.long)

    train_tokens = tokenize("train")
    val_tokens = tokenize("validation")

    print(f"Loaded {len(train_tokens):,} train tokens, {len(val_tokens):,} val tokens")

    train_dataset = TextDataset(train_tokens, config.max_seq_len)
    val_dataset = TextDataset(val_tokens, config.max_seq_len)

    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        pin_memory=True,
        drop_last=True,
        prefetch_factor=2 if config.num_workers > 0 else None,
        persistent_workers=config.num_workers > 0,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        pin_memory=True,
        drop_last=True,
        prefetch_factor=2 if config.num_workers > 0 else None,
        persistent_workers=config.num_workers > 0,
    )

    return train_loader, val_loader


# =============================================================================
# MODEL CREATION
# =============================================================================

def create_model(config: UnifiedTrainingConfig, device: torch.device) -> nn.Module:
    """Create model based on configuration."""
    preset = MODEL_PRESETS[config.model_size]

    if config.model_type == "ontological":
        if not ONTOLOGICAL_AVAILABLE:
            raise ImportError("Ontological models not available. Check imports.")

        # Create SymbolU12 with Bhava
        bhava_config = SymbolU12BhavaConfig(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            max_seq_len=config.max_seq_len,
            num_heads=preset["num_heads"],
            bhava_embed_dim=config.bhava_embed_dim,
            num_drishti_heads=config.num_drishti_heads,
        )

        model = SymbolU12LLMWithBhava(bhava_config)

        # Enable gradient checkpointing if requested
        if config.gradient_checkpointing:
            # Apply gradient checkpointing to transformer layers
            for name, module in model.named_modules():
                if hasattr(module, 'gradient_checkpointing'):
                    module.gradient_checkpointing = True

    elif config.model_type == "phase":
        model = PhaseTransformer(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            sync_steps=config.sync_steps,
            sync_lr=config.sync_lr,
        )

    elif config.model_type == "hybrid":
        model = HybridPhaseTransformer(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            local_layers=config.local_layers,
            window_size=config.window_size,
            local_backend=config.local_backend,
            alpha_local=config.alpha_local,
            alpha_phase=config.alpha_phase,
        )

    elif config.model_type == "gen2":
        if not GEN2_AVAILABLE:
            raise ImportError("Gen 2 models not available. Check imports.")

        # Determine num_layers: use 12 for 9:3 split, otherwise preset
        # 9:3 split requires exactly (authority_layers + sensory_layers) = 12 layers
        if config.use_9_3_split:
            gen2_num_layers = config.authority_layers + config.sensory_layers
        else:
            gen2_num_layers = preset["num_layers"]

        # Create SymbolU12 Gen 2 (Hierarchical Complex Bhava)
        gen2_config = SymbolU12Gen2Config(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            num_heads=preset["num_heads"],
            num_layers=gen2_num_layers,
            complex_dim=64,  # Complex embedding dimension
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            ffn_mult=preset["ff_dim"] / preset["embed_dim"],
        )

        model = SymbolU12Gen2(gen2_config)
        print(f"\n  [Gen 2] Hierarchical Complex Bhava enabled")
        print(f"  [Gen 2] Complex dim: {gen2_config.complex_dim}")
        print(f"  [Gen 2] Num layers: {gen2_num_layers} (9:3 split: {config.use_9_3_split})")
        print(f"  [Gen 2] Hierarchy: 3-tier phase rotation")

    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    # Enable gradient checkpointing after model creation
    if config.gradient_checkpointing:
        if hasattr(model, 'gradient_checkpointing_enable'):
            model.gradient_checkpointing_enable()
        else:
            for module in model.modules():
                if hasattr(module, 'gradient_checkpointing'):
                    module.gradient_checkpointing = True

    return model.to(device)


def update_alpha_schedule(model: nn.Module, step: int, config: UnifiedTrainingConfig) -> float:
    """
    Update alpha_phase for HybridAttentionLayer modules based on decay schedule.

    Returns current alpha_phase value.
    """
    if config.model_type not in ("phase", "hybrid"):
        return config.alpha_phase  # No decay for ontological

    # Calculate current alpha based on linear decay
    if step >= config.alpha_decay_steps:
        current_alpha = config.alpha_phase_end
    else:
        frac = step / config.alpha_decay_steps
        current_alpha = config.alpha_phase_start + frac * (config.alpha_phase_end - config.alpha_phase_start)

    # Update all HybridAttentionLayer modules
    for module in model.modules():
        if hasattr(module, 'alpha_phase') and isinstance(module.alpha_phase, nn.Parameter):
            module.alpha_phase.data.fill_(current_alpha)
            if hasattr(module, 'alpha_local'):
                module.alpha_local.data.fill_(1.0 - current_alpha)

    return current_alpha


# =============================================================================
# LOSS FUNCTIONS
# =============================================================================

def compute_ontological_loss(
    outputs: Dict[str, torch.Tensor],
    targets: torch.Tensor,
    config: UnifiedTrainingConfig,
    sovereign_loss: Optional['SovereignLoss'] = None,
    epoch: int = 0,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute loss for ontological model.

    If use_sovereign_loss is enabled, uses the Sovereign-1 hardened loss with:
    - Decomposed state friction (prevents Signal Washing)
    - Weighted signals (prioritizes R-Signal over C-Signal)
    - Bhava transition penalty

    Otherwise falls back to legacy loss:
    - Language modeling loss (cross-entropy)
    - Bhava relationship consistency loss
    - Global coherence regularization
    - Entropy regularization
    """
    metrics = {}
    logits = outputs["logits"]
    B, N, V = logits.shape

    # 1. Language modeling loss (always computed)
    lm_loss = F.cross_entropy(
        logits.view(-1, V),
        targets.view(-1),
        ignore_index=-100,
    )
    metrics["lm_loss"] = lm_loss.item()
    metrics["ppl"] = math.exp(min(lm_loss.item(), 20))

    # Use Sovereign-1 loss if available and enabled
    if config.use_sovereign_loss and sovereign_loss is not None and SOVEREIGN_AVAILABLE:
        # Build state from outputs
        onto_probs = outputs.get('ontological_probs', torch.zeros(B, 12, device=logits.device))
        bhava_vec = outputs.get('bhava_vector', torch.zeros(B, 144, device=logits.device))
        coherence = outputs.get('global_coherence', torch.ones(B, device=logits.device))

        # Construct 128D predicted state
        predicted_state = _build_sovereign_state(onto_probs, bhava_vec, coherence)
        # Target state (self-supervised: predict next state)
        target_state = torch.zeros_like(predicted_state)

        # Compute Sovereign loss
        total_loss, sov_metrics = sovereign_loss(
            logits, targets, predicted_state, target_state, epoch=epoch
        )

        # Merge metrics
        metrics.update({
            "total_loss": total_loss.item(),
            "sovereign_friction": sov_metrics.get("loss_friction", 0),
            "sovereign_transition": sov_metrics.get("loss_transition", 0),
            "onto_phoneme_ratio": sov_metrics.get("ontology_to_phoneme_ratio", 0),
            "meaning_fraction": sov_metrics.get("meaning_fraction", 0),
            "signal_washing": sov_metrics.get("signal_washing", False),
            "semantic_healthy": sov_metrics.get("semantic_healthy", False),
        })

        # Add coherence from outputs if available
        if "global_coherence" in outputs:
            metrics["coherence"] = outputs["global_coherence"].mean().item()

        return total_loss, metrics

    # Legacy loss computation (fallback)
    # 2. Bhava relationship consistency loss
    if "relationship_matrix" in outputs:
        rel_matrix = outputs["relationship_matrix"]  # [B, 12, 12]
        rel_diff = (rel_matrix[:, 1:, :] - rel_matrix[:, :-1, :]).abs().mean()
        bhava_loss = rel_diff
        metrics["bhava_loss"] = bhava_loss.item()
    else:
        bhava_loss = torch.tensor(0.0, device=logits.device)

    # 3. Global coherence regularization
    if "global_coherence" in outputs:
        coherence = outputs["global_coherence"].mean()
        coherence_loss = 1.0 - coherence
        metrics["coherence"] = coherence.item()
        metrics["coherence_loss"] = coherence_loss.item()
    else:
        coherence_loss = torch.tensor(0.0, device=logits.device)

    # 4. Entropy regularization
    if "ontological_probs" in outputs:
        probs = outputs["ontological_probs"]
        entropy = -(probs * (probs + 1e-8).log()).sum(dim=-1).mean()
        target_entropy = 1.5
        entropy_loss = (entropy - target_entropy).abs()
        metrics["onto_entropy"] = entropy.item()
    else:
        entropy_loss = torch.tensor(0.0, device=logits.device)

    # Combine losses
    total_loss = (
        config.lambda_lm * lm_loss +
        config.lambda_bhava * bhava_loss +
        config.lambda_coherence * coherence_loss +
        config.lambda_entropy * entropy_loss
    )

    metrics["total_loss"] = total_loss.item()

    return total_loss, metrics


def _build_sovereign_state(
    onto_probs: torch.Tensor,  # [B, 12]
    bhava_vec: torch.Tensor,   # [B, 144]
    coherence: torch.Tensor,   # [B]
) -> torch.Tensor:
    """Build 128D Sovereign state from ontological outputs."""
    B = onto_probs.shape[0]
    device = onto_probs.device

    # Guna [16]: Derived from coherence
    guna = coherence.unsqueeze(-1).expand(-1, 16)

    # S-Signal [32]: First 32 dims of bhava
    s_signal = bhava_vec[:, :32] if bhava_vec.shape[1] >= 32 else F.pad(bhava_vec, (0, 32 - bhava_vec.shape[1]))

    # R-Signal [48]: Ontology (12) expanded + bhava subset
    r_onto = F.pad(onto_probs, (0, 36))  # 12 -> 48
    if bhava_vec.shape[1] >= 80:
        bhava_r = bhava_vec[:, 32:80]  # 48 dims
    elif bhava_vec.shape[1] > 32:
        bhava_r = F.pad(bhava_vec[:, 32:], (0, 80 - bhava_vec.shape[1]))  # Pad to 48
    else:
        bhava_r = torch.zeros(B, 48, device=device)
    r_signal = r_onto + bhava_r * 0.1

    # C-Signal [32]: Remaining bhava or zeros
    if bhava_vec.shape[1] >= 112:
        c_signal = bhava_vec[:, 80:112]  # 32 dims
    elif bhava_vec.shape[1] > 80:
        c_signal = F.pad(bhava_vec[:, 80:], (0, 112 - bhava_vec.shape[1]))  # Pad to 32
    else:
        c_signal = torch.zeros(B, 32, device=device)

    return torch.cat([guna, s_signal, r_signal, c_signal], dim=-1)


def compute_phase_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    config: UnifiedTrainingConfig,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """Compute loss for phase/hybrid models."""
    B, N, V = logits.shape

    lm_loss = F.cross_entropy(
        logits.view(-1, V),
        targets.view(-1),
        ignore_index=-100,
    )

    metrics = {
        "lm_loss": lm_loss.item(),
        "ppl": math.exp(min(lm_loss.item(), 20)),
        "total_loss": lm_loss.item(),
    }

    return lm_loss, metrics


# =============================================================================
# TRAINING LOOP
# =============================================================================

def train(config: UnifiedTrainingConfig):
    """Main training loop with optional PIDv2 Governor."""

    # Setup
    torch.manual_seed(config.seed)

    # Device
    if config.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(config.device)

    print(f"\n{'='*70}")
    print("   UNIFIED SYMBOLU LLM TRAINING V9.4.4")
    print(f"{'='*70}")
    print(f"\n  Model Type: {config.model_type.upper()}")
    print(f"  Model Size: {config.model_size}")
    print(f"  Max Seq Len: {config.max_seq_len:,}")
    print(f"  Dataset: {config.dataset}")
    print(f"  Device: {device}")
    print(f"  Controller: {config.controller.upper() if config.controller != 'none' else 'None'}")
    print(f"  Gradient Checkpointing: {config.gradient_checkpointing}")
    print(f"  Mixed Precision: {config.mixed_precision}")
    print(f"  9:3 Hierarchical Split: {'ENABLED' if config.use_9_3_split else 'Disabled'}")
    if config.enable_dynamic_relaxation:
        print(f"  Dynamic Relaxation: ENABLED ({config.authority_layers}:{config.sensory_layers} → {config.relaxation_target_authority}:{config.relaxation_target_sensory})")
        print(f"    Stability Threshold: {config.relaxation_stability_threshold} for {config.relaxation_stability_window} steps")

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    tokenizer.model_max_length = int(1e12)

    # Load data
    train_loader, val_loader = load_data(config, tokenizer)

    # Create model
    model = create_model(config, device)
    num_params = sum(p.numel() for p in model.parameters())
    print(f"\n  Model Parameters: {num_params:,} ({num_params/1e6:.1f}M)")

    # Initialize Sovereign-1 loss if available and enabled
    sovereign_loss = None
    if config.use_sovereign_loss and SOVEREIGN_AVAILABLE:
        from symbolu.sovereign.loss import SovereignLoss, SovereignLossConfig
        sov_config = SovereignLossConfig(
            weight_guna=config.sovereign_weight_guna,
            weight_s=config.sovereign_weight_s,
            weight_r=config.sovereign_weight_r,
            weight_c=config.sovereign_weight_c,
        )
        sovereign_loss = SovereignLoss(config=sov_config).to(device)
        print(f"  Sovereign-1 Loss: ENABLED (R-weight={config.sovereign_weight_r})")
    else:
        print(f"  Sovereign-1 Loss: Disabled (using legacy loss)")

    # Optimizer
    optimizer = AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
        betas=(config.beta1, config.beta2),
    )

    # Scheduler
    scheduler = CosineAnnealingLR(
        optimizer,
        T_max=config.max_steps - config.warmup_steps,
        eta_min=config.learning_rate * 0.1,
    )

    # Formula [1331]: 9:3 Hierarchical Gradient Scaling
    gradient_scaler_hgs = None
    if config.use_9_3_split:
        gradient_scaler_hgs = HierarchicalGradientScaler(
            model=model,
            authority_layers=config.authority_layers,
            sensory_layers=config.sensory_layers,
            alpha_sens_min=config.alpha_sens_initial,
            alpha_sens_max=config.alpha_sens_max,
            warmup_steps=config.gradient_warmup_steps,
            layer_attr="blocks",  # Common attribute name for transformer layers
        )
        # Validate layer count matches configuration
        expected_layers = config.authority_layers + config.sensory_layers
        try:
            found_layers = len(gradient_scaler_hgs._get_layers())
            if found_layers < expected_layers:
                print(f"  ⚠️  WARNING: Found {found_layers} layers but 9:3 split expects {expected_layers}")
                print(f"      This may cause incorrect gradient scaling behavior!")
            else:
                print(f"  ✓ Layer count validation passed: {found_layers} layers for {config.authority_layers}:{config.sensory_layers} split")
        except Exception as e:
            print(f"  ⚠️  Could not validate layer count: {e}")

    # Dynamic Relaxation Controller: 9:3 → 6:6 transition
    relaxation_controller = None
    if config.enable_dynamic_relaxation and gradient_scaler_hgs is not None:
        relaxation_controller = DynamicRelaxationController(
            gradient_scaler=gradient_scaler_hgs,
            model=model,
            stability_threshold=config.relaxation_stability_threshold,
            stability_window=config.relaxation_stability_window,
            mode=config.relaxation_mode,
            authority_split=(config.authority_layers, config.sensory_layers),
            balanced_split=(config.relaxation_target_authority, config.relaxation_target_sensory),
            authority_alpha_max=config.alpha_sens_max,
            balanced_alpha_max=config.alpha_sens_max,  # Same ceiling for balanced phase
            thaw_alpha_start=config.relaxation_thaw_alpha,
            thaw_warmup_steps=config.relaxation_thaw_steps,
            ppl_spike_threshold=config.relaxation_ppl_spike_threshold,
            recovery_steps=config.relaxation_recovery_steps,
        )

    # Mixed precision
    scaler = torch.cuda.amp.GradScaler() if config.mixed_precision != "none" else None
    autocast_dtype = torch.bfloat16 if config.mixed_precision == "bf16" else torch.float16

    # Training state
    global_step = 0
    best_val_loss = float("inf")
    best_ppl = float("inf")
    spike_count = 0
    train_losses = []

    # Checkpoint directory
    ckpt_dir = Path(config.checkpoint_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    with open(ckpt_dir / "config.json", "w") as f:
        json.dump(asdict(config), f, indent=2)

    # Initialize PIDv2 Controller (V9.4.4)
    authority_controller = None
    if config.controller == "pidv2" and PIDV2_AVAILABLE:
        pidv2_config = AuthorityPIDv2Config(
            Kp_min=config.pidv2_kp_min,
            Kp_max=config.pidv2_kp_max,
            Kp_sensitivity=config.pidv2_kp_sensitivity,
            Ki=config.pidv2_ki,
            Kd=config.pidv2_kd,
            A_min=config.pidv2_a_min,
            C_floor=config.pidv2_c_floor,
            C_good=config.pidv2_c_good,
            W_s=config.pidv2_w_s,
            semantic_ppl_scale=config.pidv2_semantic_scale,
            handshake_Kd_dampen=config.pidv2_handshake_dampen,
        )
        authority_controller = AuthorityPIDv2(pidv2_config)
        print(f"\n  PIDv2 Governor ENABLED")
        print(f"    Dynamic Kp: [{config.pidv2_kp_min}, {config.pidv2_kp_max}]")
        print(f"    Semantic Weight (W_s): {config.pidv2_w_s:.0%}")
        print(f"    Authority floor: {config.pidv2_a_min}")
    elif config.controller == "emergency_pd" and PIDV2_AVAILABLE:
        pd_config = EmergencyPDConfig(A_min=0.25)
        authority_controller = EmergencyPD(pd_config)
        print(f"\n  Emergency PD Controller ENABLED")
    elif config.controller != "none":
        print(f"\n  Warning: Controller '{config.controller}' not available")

    # V9.4.5: Initialize Friction Controller with Corrective Actions
    friction_controller = None
    if PIDV2_AVAILABLE and config.model_type == "hybrid":
        friction_controller = FrictionController(FrictionControllerConfig())
        print(f"\n  V9.4.5: Friction Controller ENABLED")
        print(f"    Alignment thresholds: warn={friction_controller.config.align_warning}, crit={friction_controller.config.align_critical}")
        print(f"    Dominance range: [{friction_controller.config.dom_low}, {friction_controller.config.dom_high}]")

    # Track previous state for S-drift computation
    previous_state = None
    current_s_drift = 0.0

    # TensorBoard
    tb_writer = None
    if config.tensorboard and TENSORBOARD_AVAILABLE:
        tb_log_dir = ckpt_dir / "logs"
        tb_writer = SummaryWriter(log_dir=str(tb_log_dir))
        print(f"  TensorBoard: {tb_log_dir}")

    print(f"\n{'='*70}")
    print("   STARTING TRAINING")
    print(f"{'='*70}\n")

    model.train()
    train_iter = iter(train_loader)
    step_start_time = time.time()
    running_loss = 0.0
    accumulation_step = 0

    while global_step < config.max_steps:
        # Get batch
        try:
            x, y = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            x, y = next(train_iter)

        x, y = x.to(device), y.to(device)

        # Forward pass
        with torch.cuda.amp.autocast(dtype=autocast_dtype):
            if config.model_type == "ontological":
                outputs = model(x)
                loss, metrics = compute_ontological_loss(
                    outputs, y, config,
                    sovereign_loss=sovereign_loss,
                    epoch=global_step // len(train_loader),
                )
            elif config.model_type == "gen2":
                outputs = model(x, labels=y)
                loss = outputs['loss']
                metrics = {
                    'coherence': outputs['coherence'].mean().item(),
                    'level_1_coh': outputs['level_coherences'][:, 0].mean().item(),
                    'level_2_coh': outputs['level_coherences'][:, 1].mean().item(),
                    'level_3_coh': outputs['level_coherences'][:, 2].mean().item(),
                }
            else:
                # Phase or Hybrid - handle both tensor and dict returns
                output = model(x)
                if isinstance(output, dict):
                    logits = output.get('logits', output.get('output', output.get('last_hidden_state')))
                else:
                    logits = output
                loss, metrics = compute_phase_loss(logits, y, config)

            # Scale for gradient accumulation
            loss = loss / config.gradient_accumulation

        # Backward pass
        if scaler is not None:
            scaler.scale(loss).backward()
        else:
            loss.backward()

        running_loss += loss.item() * config.gradient_accumulation
        accumulation_step += 1

        # Update weights
        if accumulation_step % config.gradient_accumulation == 0:
            if scaler is not None:
                scaler.unscale_(optimizer)

            # Note: Gradient scaling via hooks happens automatically during backward()
            # We'll call step() after optimizer.step() to update warmup schedule

            # Gradient clipping: per-layer or global
            if config.use_per_layer_clipping and gradient_scaler_hgs is not None:
                # Clip authority and sensory layers separately to respect 9:3 design
                gradient_scaler_hgs.clip_grad_norm_by_layer(config.max_grad_norm)
            else:
                torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)

            if scaler is not None:
                scaler.step(optimizer)
                scaler.update()
            else:
                optimizer.step()

            # Formula [1331] 9:3 Split: Update gradient scaler warmup schedule
            hgs_metrics = {}
            if gradient_scaler_hgs is not None:
                hgs_metrics = gradient_scaler_hgs.step()

            # V9.4.5: Measure friction and apply corrective actions
            friction_alignment = 0.0
            friction_dominance = 1.0
            friction_penalty = 1.0
            if PIDV2_AVAILABLE and global_step % 10 == 0:  # Every 10 steps to save compute
                try:
                    friction_alignment, friction_dominance = measure_friction(model, local_layers=6)
                    # Update friction controller with corrective actions
                    if friction_controller is not None:
                        friction_penalty = friction_controller.update(friction_alignment, friction_dominance)
                except Exception as e:
                    if global_step % 100 == 0:  # Log warning every 100 steps to avoid spam
                        print(f"  Warning: Friction measurement failed at step {global_step}: {e}")

            optimizer.zero_grad()

            # Update scheduler after warmup
            if global_step >= config.warmup_steps:
                scheduler.step()

            # Update alpha schedule for phase/hybrid models
            current_alpha = update_alpha_schedule(model, global_step, config)

            global_step += 1
            avg_loss = running_loss / config.gradient_accumulation
            train_losses.append(avg_loss)
            running_loss = 0.0

            # Periodic CUDA memory cleanup to prevent fragmentation
            if device.type == "cuda" and global_step % 500 == 0:
                torch.cuda.empty_cache()

            # Logging
            if global_step % config.log_every == 0:
                elapsed = time.time() - step_start_time
                tokens_per_sec = (
                    config.log_every * config.batch_size * config.max_seq_len *
                    config.gradient_accumulation
                ) / elapsed
                lr = optimizer.param_groups[0]["lr"]

                # Memory usage
                if device.type == "cuda":
                    mem_used = torch.cuda.max_memory_allocated() / (1024**3)
                    mem_str = f" | VRAM: {mem_used:.1f}GB"
                else:
                    mem_str = ""

                # Log message
                log_msg = (
                    f"Step {global_step:>6} | "
                    f"Loss: {avg_loss:.4f} | "
                    f"PPL: {metrics['ppl']:.2f} | "
                    f"LR: {lr:.2e} | "
                    f"Tok/s: {tokens_per_sec:.0f}{mem_str}"
                )

                # Add ontological metrics
                if config.model_type == "ontological":
                    if "coherence" in metrics:
                        log_msg += f" | Coh: {metrics['coherence']:.3f}"
                    if "onto_entropy" in metrics:
                        log_msg += f" | Ent: {metrics['onto_entropy']:.2f}"
                    # Sovereign-1 metrics
                    if "onto_phoneme_ratio" in metrics and metrics["onto_phoneme_ratio"] > 0:
                        ratio = metrics["onto_phoneme_ratio"]
                        health = "OK" if metrics.get("semantic_healthy") else "WARN"
                        log_msg += f" | R/C: {ratio:.2f} [{health}]"

                # Add Gen 2 hierarchical metrics
                if config.model_type == "gen2":
                    if "coherence" in metrics:
                        log_msg += f" | Coh: {metrics['coherence']:.3f}"
                    if "level_3_coh" in metrics:
                        log_msg += f" | L3: {metrics['level_3_coh']:.2f}"

                # Add alpha for phase/hybrid models
                if config.model_type in ("phase", "hybrid"):
                    log_msg += f" | α_phase: {current_alpha:.2f}"

                # V9.4.5: Add friction metrics (for 6/6 hybrid architecture)
                if friction_alignment != 0.0 or friction_dominance != 1.0:
                    # Color-code alignment
                    if friction_alignment > 0.1:
                        align_ind = "+"  # Synergy
                    elif friction_alignment < -0.1:
                        align_ind = "!"  # Friction
                    else:
                        align_ind = "~"  # Neutral
                    log_msg += f" | Align:{friction_alignment:+.2f}{align_ind} Dom:{friction_dominance:.2f}"

                # Formula [1331]: 9:3 Split metrics
                if hgs_metrics:
                    s_a_ratio = hgs_metrics.get("s_a_ratio", 0.0)
                    alpha_sens = hgs_metrics.get("alpha_sens", 0.0)
                    # Color-code S/A ratio (< 0.5 is good, Authority dominating)
                    if s_a_ratio < 0.3:
                        sa_ind = "+"  # Authority strongly dominant
                    elif s_a_ratio < 0.5:
                        sa_ind = "~"  # Balanced
                    else:
                        sa_ind = "!"  # Sensory may be overriding
                    log_msg += f" | S/A:{s_a_ratio:.2f}{sa_ind} α_s:{alpha_sens:.2f}"

                print(log_msg)
                step_start_time = time.time()

            # Evaluation
            if global_step % config.eval_every == 0:
                val_loss, val_metrics = evaluate(
                    model, val_loader, device, config, autocast_dtype,
                    sovereign_loss=sovereign_loss,
                )
                val_ppl = val_metrics['ppl']
                current_coh = val_metrics.get('coherence', 0.75)

                # PIDv2 Controller Update (V9.4.4)
                if authority_controller is not None:
                    old_A = authority_controller.A
                    new_A = authority_controller.update(
                        val_ppl, current_coh,
                        step=global_step,
                        phase_ramp_steps=config.phase_ramp_steps,
                    )
                    print(f"  --> Val Loss: {val_loss:.4f} | Val PPL: {val_ppl:.2f} | {authority_controller.get_status_string()}")

                    # V9.4.5: Log Friction Controller status (with corrective actions)
                    if friction_controller is not None:
                        print(f"  --> {friction_controller.get_status_string()}")
                        if friction_controller.correction_active:
                            print(f"  ⚠️ FRICTION CORRECTION: LR reduced by {(1-friction_controller.friction_penalty)*100:.0f}%")

                    # Apply authority factor AND friction penalty to learning rate
                    effective_factor = new_A * friction_penalty
                    for pg in optimizer.param_groups:
                        pg['lr'] *= effective_factor

                    # TensorBoard logging
                    if tb_writer is not None:
                        tb_writer.add_scalar("ctrl/authority_A", new_A, global_step)
                        tb_writer.add_scalar("ctrl/ppl_velocity", authority_controller.last_v, global_step)
                        if hasattr(authority_controller, 'last_Kp'):
                            tb_writer.add_scalar("ctrl/dynamic_Kp", authority_controller.last_Kp, global_step)
                        # V9.4.5: Friction Controller metrics (with corrective actions)
                        if friction_controller is not None:
                            tb_writer.add_scalar("fric/alignment", friction_controller.align_ema, global_step)
                            tb_writer.add_scalar("fric/dominance", friction_controller.dom_ema, global_step)
                            tb_writer.add_scalar("fric/penalty", friction_controller.friction_penalty, global_step)
                            tb_writer.add_scalar("fric/correction_active", 1.0 if friction_controller.correction_active else 0.0, global_step)
                        elif friction_alignment != 0.0:
                            # Legacy: raw metrics without controller
                            tb_writer.add_scalar("ctrl/friction_alignment", friction_alignment, global_step)
                            tb_writer.add_scalar("ctrl/friction_dominance", friction_dominance, global_step)
                else:
                    print(f"  --> Val Loss: {val_loss:.4f} | Val PPL: {val_ppl:.2f}")

                # Dynamic Relaxation Controller Update
                if relaxation_controller is not None:
                    # Get Guna Coherence from metrics (or default)
                    guna_coherence = val_metrics.get('coherence', 0.75)

                    # Get S-Drift EMA from metrics (or estimate from PPL stability)
                    # If not available, estimate from recent PPL variance
                    s_drift_ema = val_metrics.get('s_drift_ema', 0.3)
                    if 's_drift_ema' not in val_metrics:
                        # Fallback: estimate drift from PPL stability
                        # Lower PPL variance = lower drift
                        recent_losses = train_losses[-50:] if len(train_losses) >= 50 else train_losses
                        if len(recent_losses) > 1:
                            loss_std = torch.tensor(recent_losses).std().item()
                            s_drift_ema = min(1.0, loss_std * 2.0)  # Scale to [0, 1]
                        else:
                            s_drift_ema = 0.5

                    # Update relaxation controller
                    state_changed, action = relaxation_controller.update(
                        guna_coherence=guna_coherence,
                        s_drift_ema=s_drift_ema,
                        val_ppl=val_ppl,
                        global_step=global_step,
                    )

                    # Execute actions
                    if action == "RELAX":
                        relaxation_controller.execute_relaxation()
                        print(f"  🎯 StabilityIndex achieved! Transitioning to balanced mode.")
                    elif action == "RECOVER":
                        relaxation_controller.execute_recovery()

                    # Log status
                    print(f"  --> [Relaxation] {relaxation_controller.get_status_string()}")

                    # TensorBoard logging for relaxation
                    if tb_writer is not None:
                        stability = relaxation_controller.compute_stability_index(guna_coherence, s_drift_ema)
                        tb_writer.add_scalar("relax/stability_index", stability, global_step)
                        tb_writer.add_scalar("relax/stability_streak", relaxation_controller.stability_streak, global_step)
                        tb_writer.add_scalar("relax/is_balanced", 1.0 if relaxation_controller.state == "BALANCED" else 0.0, global_step)
                        tb_writer.add_scalar("relax/guna_coherence", guna_coherence, global_step)
                        tb_writer.add_scalar("relax/s_drift_ema", s_drift_ema, global_step)

                    # Adaptive LR on PPL spike (only if no PIDv2)
                    if val_ppl < best_ppl:
                        best_ppl = val_ppl
                    elif global_step > config.warmup_steps:
                        if val_ppl > best_ppl * 1.5:
                            spike_count += 1
                            old_lr = optimizer.param_groups[0]['lr']
                            new_lr = old_lr * 0.7
                            for pg in optimizer.param_groups:
                                pg['lr'] = new_lr
                            print(f"  ⚠️ PPL spike! LR: {old_lr:.2e} → {new_lr:.2e}")

                # TensorBoard val metrics
                if tb_writer is not None:
                    tb_writer.add_scalar("val/loss", val_loss, global_step)
                    tb_writer.add_scalar("val/ppl", val_ppl, global_step)

                # Log HGS status (only if relaxation controller not active, to avoid duplicate logging)
                if gradient_scaler_hgs is not None and relaxation_controller is None:
                    print(f"  --> {gradient_scaler_hgs.get_status_string()}")

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    save_checkpoint(
                        model, optimizer, scheduler, global_step, best_val_loss,
                        ckpt_dir / "best.pt",
                        hgs_state=gradient_scaler_hgs.get_state() if gradient_scaler_hgs else None,
                        drc_state=relaxation_controller.get_state() if relaxation_controller else None,
                    )
                    print(f"  --> New best! Saved to {ckpt_dir / 'best.pt'}")

                model.train()

            # Save checkpoint
            if global_step % config.save_every == 0:
                save_checkpoint(
                    model, optimizer, scheduler, global_step, best_val_loss,
                    ckpt_dir / f"step_{global_step}.pt",
                    hgs_state=gradient_scaler_hgs.get_state() if gradient_scaler_hgs else None,
                    drc_state=relaxation_controller.get_state() if relaxation_controller else None,
                )
                # Cleanup old checkpoints (keep last 5)
                if PIDV2_AVAILABLE:
                    cleanup_old_checkpoints(ckpt_dir, keep_last=5)

    # Final save
    save_checkpoint(
        model, optimizer, scheduler, global_step, best_val_loss,
        ckpt_dir / "final.pt",
        hgs_state=gradient_scaler_hgs.get_state() if gradient_scaler_hgs else None,
        drc_state=relaxation_controller.get_state() if relaxation_controller else None,
    )

    # Close TensorBoard
    if tb_writer is not None:
        tb_writer.close()

    print(f"\n{'='*70}")
    print("   TRAINING COMPLETE")
    print(f"{'='*70}")
    print(f"  Total Steps: {global_step:,}")
    print(f"  Best Val Loss: {best_val_loss:.4f}")
    print(f"  Best Val PPL: {math.exp(best_val_loss):.2f}")
    if authority_controller is not None:
        print(f"  Final Authority: {authority_controller.A:.3f}")
    print(f"  Final Checkpoint: {ckpt_dir / 'final.pt'}")


def evaluate(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    config: UnifiedTrainingConfig,
    autocast_dtype: torch.dtype,
    sovereign_loss: Optional['SovereignLoss'] = None,
) -> Tuple[float, Dict[str, float]]:
    """Evaluate model on validation set."""
    model.eval()
    total_loss = 0.0
    total_batches = 0

    with torch.no_grad():
        for x, y in val_loader:
            x, y = x.to(device), y.to(device)

            with torch.cuda.amp.autocast(dtype=autocast_dtype):
                if config.model_type == "ontological":
                    outputs = model(x)
                    loss, metrics = compute_ontological_loss(
                        outputs, y, config,
                        sovereign_loss=sovereign_loss,
                    )
                elif config.model_type == "gen2":
                    outputs = model(x, labels=y)
                    loss = outputs['loss']
                    metrics = {'coherence': outputs['coherence'].mean().item()}
                else:
                    # Phase or Hybrid - handle both tensor and dict returns
                    output = model(x)
                    if isinstance(output, dict):
                        logits = output.get('logits', output.get('output', output.get('last_hidden_state')))
                    else:
                        logits = output
                    loss, metrics = compute_phase_loss(logits, y, config)

            total_loss += loss.item()
            total_batches += 1

            if total_batches >= 50:  # Limit eval batches
                break

    avg_loss = total_loss / total_batches
    return avg_loss, {"ppl": math.exp(min(avg_loss, 20))}


def save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: torch.optim.lr_scheduler._LRScheduler,
    step: int,
    best_val_loss: float,
    path: Path,
    hgs_state: Optional[dict] = None,
    drc_state: Optional[dict] = None,
):
    """Save training checkpoint with optional HGS/DRC state."""
    checkpoint = {
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "step": step,
        "best_val_loss": best_val_loss,
        "rng_state": torch.get_rng_state(),
    }

    # Add CUDA RNG state if available
    if torch.cuda.is_available():
        checkpoint["cuda_rng_state"] = torch.cuda.get_rng_state()

    # Add HGS state if provided
    if hgs_state is not None:
        checkpoint["hgs_state"] = hgs_state

    # Add DRC state if provided
    if drc_state is not None:
        checkpoint["drc_state"] = drc_state

    torch.save(checkpoint, path)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified SymbolU LLM Training",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Model
    parser.add_argument("--model_type", type=str, default="ontological",
                       choices=["ontological", "phase", "hybrid", "gen2"],
                       help="Model architecture type (gen2 = hierarchical complex Bhava)")
    parser.add_argument("--model_size", type=str, default="small",
                       choices=["tiny", "small", "medium", "large"],
                       help="Model size preset")
    parser.add_argument("--max_seq_len", type=int, default=2048,
                       help="Maximum sequence length")

    # Training
    parser.add_argument("--batch_size", type=int, default=8,
                       help="Batch size per GPU")
    parser.add_argument("--gradient_accumulation", type=int, default=1,
                       help="Gradient accumulation steps")
    parser.add_argument("--max_steps", type=int, default=10000,
                       help="Maximum training steps")
    parser.add_argument("--learning_rate", type=float, default=3e-4,
                       help="Peak learning rate")
    parser.add_argument("--use_per_layer_clipping", action="store_true",
                       help="Clip authority/sensory gradients separately (respects 9:3 design)")

    # Dataset
    parser.add_argument("--dataset", type=str, default="wikitext103",
                       choices=["wikitext103", "wikitext2"],
                       help="Training dataset")

    # Memory optimization
    parser.add_argument("--gradient_checkpointing", action="store_true",
                       help="Enable gradient checkpointing")
    parser.add_argument("--mixed_precision", type=str, default="bf16",
                       choices=["none", "fp16", "bf16"],
                       help="Mixed precision training")

    # Hybrid-specific
    parser.add_argument("--local_backend", type=str, default="auto",
                       choices=["auto", "flash", "sdpa", "unfold"],
                       help="LocalAttention backend")
    parser.add_argument("--window_size", type=int, default=256,
                       help="Local attention window size")
    parser.add_argument("--local_layers", type=int, default=4,
                       help="Number of local-only attention layers (hybrid mode)")
    parser.add_argument("--alpha_local", type=float, default=0.8,
                       help="Weight for local attention in hybrid layers")
    parser.add_argument("--alpha_phase", type=float, default=0.2,
                       help="Weight for phase attention in hybrid layers")

    # Alpha decay schedule (for phase/hybrid attention)
    parser.add_argument("--alpha_phase_start", type=float, default=0.6,
                       help="Initial alpha_phase value (decays over time)")
    parser.add_argument("--alpha_phase_end", type=float, default=0.4,
                       help="Final alpha_phase value after decay")
    parser.add_argument("--alpha_decay_steps", type=int, default=10000,
                       help="Steps over which alpha_phase decays from start to end")

    # Ontological-specific
    parser.add_argument("--lambda_bhava", type=float, default=0.1,
                       help="Bhava relationship loss weight")
    parser.add_argument("--lambda_coherence", type=float, default=0.05,
                       help="Coherence loss weight")

    # Logging
    parser.add_argument("--log_every", type=int, default=10,
                       help="Log every N steps")
    parser.add_argument("--eval_every", type=int, default=100,
                       help="Evaluate every N steps")
    parser.add_argument("--save_every", type=int, default=1000,
                       help="Save checkpoint every N steps")
    parser.add_argument("--checkpoint_dir", type=str, default="checkpoints_unified",
                       help="Checkpoint directory")

    # Other
    parser.add_argument("--no_coherence_loss", action="store_true",
                       help="Disable coherence loss")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed")

    # Resume
    parser.add_argument("--resume", type=str, default="",
                       help="Path to checkpoint to resume from")
    parser.add_argument("--resume_weights_only", action="store_true",
                       help="Only load model weights, reset optimizer")

    # PIDv2 Controller (V9.4.4)
    parser.add_argument("--controller", type=str, default="none",
                       choices=["none", "pidv2", "emergency_pd"],
                       help="Authority controller: none, pidv2, emergency_pd")
    parser.add_argument("--pidv2_kp_min", type=float, default=0.10,
                       help="PIDv2 minimum Kp (when noisy)")
    parser.add_argument("--pidv2_kp_max", type=float, default=0.30,
                       help="PIDv2 maximum Kp (when clean)")
    parser.add_argument("--pidv2_kp_sensitivity", type=float, default=5.0,
                       help="PIDv2 volatility sensitivity")
    parser.add_argument("--pidv2_ki", type=float, default=0.02,
                       help="PIDv2 integral gain")
    parser.add_argument("--pidv2_kd", type=float, default=0.10,
                       help="PIDv2 derivative gain")
    parser.add_argument("--pidv2_a_min", type=float, default=0.30,
                       help="PIDv2 minimum authority factor")
    parser.add_argument("--pidv2_w_s", type=float, default=0.30,
                       help="Semantic weight (0.30 = 30%% prompt-based)")
    parser.add_argument("--phase_ramp_steps", type=int, default=7000,
                       help="Steps for phase LR ramp (handshake dampening)")
    parser.add_argument("--tensorboard", action="store_true", default=True,
                       help="Enable TensorBoard logging")
    parser.add_argument("--no_tensorboard", action="store_true",
                       help="Disable TensorBoard logging")

    # Formula [1331]: 9:3 Hierarchical Split
    parser.add_argument("--use_9_3_split", action="store_true",
                       help="Enable 9:3 Authority/Sensory gradient scaling")
    parser.add_argument("--authority_layers", type=int, default=9,
                       help="Number of Authority (State-Delta) layers")
    parser.add_argument("--sensory_layers", type=int, default=3,
                       help="Number of Sensory (Quadratic) layers")
    parser.add_argument("--alpha_sens_initial", type=float, default=0.1,
                       help="Initial sensory gradient scale (heavy dampening at start)")
    parser.add_argument("--alpha_sens_max", type=float, default=0.7,
                       help="Maximum sensory gradient scale (after warmup/relaxation)")
    parser.add_argument("--gradient_warmup_steps", type=int, default=500,
                       help="Steps to ramp sensory gradient scale from initial to max")

    # Dynamic Relaxation: 9:3 → 6:6 transition
    parser.add_argument("--enable_dynamic_relaxation", action="store_true",
                       help="Enable automatic 9:3 → 6:6 split transition based on stability")
    parser.add_argument("--relaxation_mode", type=str, default="average",
                       choices=["consecutive", "average"],
                       help="Stability check mode: 'consecutive' (reset on dip) or 'average' (rolling mean)")
    parser.add_argument("--relaxation_stability_threshold", type=float, default=0.78,
                       help="StabilityIndex threshold to trigger relaxation")
    parser.add_argument("--relaxation_stability_window", type=int, default=500,
                       help="Rolling window size for stability check")
    parser.add_argument("--relaxation_streak_target", type=int, default=5,
                       help="Consecutive stable evals for 'consecutive' mode")
    parser.add_argument("--relaxation_target_authority", type=int, default=6,
                       help="Target authority layers after relaxation")
    parser.add_argument("--relaxation_target_sensory", type=int, default=6,
                       help="Target sensory layers after relaxation")
    parser.add_argument("--relaxation_thaw_alpha", type=float, default=0.05,
                       help="Dampened Thaw starting α for new sensory layers")
    parser.add_argument("--relaxation_thaw_steps", type=int, default=500,
                       help="Steps to ramp new sensory layers during Dampened Thaw")
    parser.add_argument("--relaxation_ppl_spike_threshold", type=float, default=0.20,
                       help="PPL increase %% to trigger Viparyaya recovery")
    parser.add_argument("--relaxation_recovery_steps", type=int, default=100,
                       help="Steps to stay in Viparyaya recovery before resuming")

    # Stress Test (V9.4.4)
    parser.add_argument("--stress_test", action="store_true",
                       help="Run stress test instead of training")
    parser.add_argument("--stress_start", type=int, default=1000,
                       help="Step to start corruption")
    parser.add_argument("--stress_duration", type=int, default=200,
                       help="Steps to inject corruption")
    parser.add_argument("--corruption_rate", type=float, default=0.10,
                       help="Probability of corrupting each batch")
    parser.add_argument("--corruption_mode", type=str, default="noise",
                       choices=["noise", "label_flip", "repeat"],
                       help="Type of corruption")

    args = parser.parse_args()

    # Handle stress test redirect
    if args.stress_test:
        print("=" * 70)
        print("  STRESS TEST MODE - Redirecting to stress_test.py")
        print("=" * 70)
        import subprocess
        stress_cmd = [
            sys.executable, "stress_test.py",
            "--resume", args.resume or "",
            "--stress_start", str(args.stress_start),
            "--stress_duration", str(args.stress_duration),
            "--corruption_rate", str(args.corruption_rate),
            "--corruption_mode", args.corruption_mode,
            "--checkpoint_dir", args.checkpoint_dir + "_stress_test",
        ]
        print(f"\nRunning: {' '.join(stress_cmd)}\n")
        result = subprocess.run(stress_cmd)
        sys.exit(result.returncode)

    # Create config
    config = UnifiedTrainingConfig(
        model_type=args.model_type,
        model_size=args.model_size,
        max_seq_len=args.max_seq_len,
        batch_size=args.batch_size,
        gradient_accumulation=args.gradient_accumulation,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        dataset=args.dataset,
        gradient_checkpointing=args.gradient_checkpointing,
        mixed_precision=args.mixed_precision,
        local_backend=args.local_backend,
        window_size=args.window_size,
        lambda_bhava=args.lambda_bhava,
        lambda_coherence=args.lambda_coherence,
        log_every=args.log_every,
        eval_every=args.eval_every,
        save_every=args.save_every,
        checkpoint_dir=args.checkpoint_dir,
        no_coherence_loss=args.no_coherence_loss,
        seed=args.seed,
        # PIDv2 Controller settings
        controller=args.controller,
        pidv2_kp_min=args.pidv2_kp_min,
        pidv2_kp_max=args.pidv2_kp_max,
        pidv2_kp_sensitivity=args.pidv2_kp_sensitivity,
        pidv2_ki=args.pidv2_ki,
        pidv2_kd=args.pidv2_kd,
        pidv2_a_min=args.pidv2_a_min,
        pidv2_w_s=args.pidv2_w_s,
        phase_ramp_steps=args.phase_ramp_steps,
        tensorboard=args.tensorboard and not args.no_tensorboard,
        resume=args.resume,
        resume_weights_only=args.resume_weights_only,
        # Formula [1331]: 9:3 Hierarchical Split
        use_9_3_split=args.use_9_3_split,
        authority_layers=args.authority_layers,
        sensory_layers=args.sensory_layers,
        alpha_sens_initial=args.alpha_sens_initial,
        alpha_sens_max=args.alpha_sens_max,
        gradient_warmup_steps=args.gradient_warmup_steps,
        use_per_layer_clipping=args.use_per_layer_clipping,
        # Dynamic Relaxation: 9:3 → 6:6 transition
        enable_dynamic_relaxation=args.enable_dynamic_relaxation,
        relaxation_mode=args.relaxation_mode,
        relaxation_stability_threshold=args.relaxation_stability_threshold,
        relaxation_stability_window=args.relaxation_stability_window,
        relaxation_streak_target=args.relaxation_streak_target,
        relaxation_target_authority=args.relaxation_target_authority,
        relaxation_target_sensory=args.relaxation_target_sensory,
        relaxation_thaw_alpha=args.relaxation_thaw_alpha,
        relaxation_thaw_steps=args.relaxation_thaw_steps,
        relaxation_ppl_spike_threshold=args.relaxation_ppl_spike_threshold,
        relaxation_recovery_steps=args.relaxation_recovery_steps,
    )

    # Train
    train(config)


if __name__ == "__main__":
    main()
