#!/usr/bin/env python3
"""
SymbolU LLM Training Script
============================

Production training script for Phase Attention Transformer with O(n) complexity.

Features:
- Dataset support: C4, WikiText-103, WikiText-2, or custom
- AdamW optimizer with cosine LR schedule and warmup
- Gradient clipping and accumulation
- Mixed precision (FP16/BF16) training
- Checkpointing with resume support
- Wandb/TensorBoard logging
- Multi-GPU support via DDP
- Evaluation with perplexity tracking

Usage:
------
# Quick test (small model, WikiText-2)
python train.py --model_size tiny --dataset wikitext2 --max_steps 1000

# Train 50M model on C4
python train.py --model_size small --dataset c4 --max_steps 100000

# Train 100M model on RunPod A100
python train.py --model_size medium --dataset c4 --batch_size 32 --gradient_accumulation 4

# Resume from checkpoint
python train.py --resume checkpoints/latest.pt

# With wandb logging
python train.py --wandb --wandb_project symbolu --wandb_run phase_attention_50m

Model Sizes:
- tiny: 10M params (embed=256, layers=4, heads=4)  - for testing
- small: 50M params (embed=512, layers=8, heads=8)  - validation
- medium: 100M params (embed=768, layers=12, heads=12)  - target
- large: 350M params (embed=1024, layers=24, heads=16)  - scale test
- xl: 1.3B params (embed=2048, layers=24, heads=16)  - large scale
- 7b: 7B params (embed=4096, layers=32, heads=32)  - production scale

7B Training (requires A100 80GB):
python train.py --model_size 7b --dataset c4 --batch_size 1 --gradient_accumulation 64 --gradient_checkpointing --max_seq_len 2048
"""

import os
import collections

# Set CUDA memory and tokenizer environment variables before importing torch
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import sys
import math
import time
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, LambdaLR
from torch.amp import autocast
from torch.cuda.amp import GradScaler

# =============================================================================
# PERFORMANCE: Enable hardware acceleration features
# =============================================================================
# TF32: Use TensorFloat-32 on Ampere+ GPUs (A100, H100, B200)
# Provides 2-3x speedup for FP32 math with minimal accuracy loss
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# cuDNN Benchmark: Auto-tune convolution algorithms for faster execution
# Small overhead on first batch, then faster for rest of training
torch.backends.cudnn.benchmark = True

# SymbolU imports
from symbolu.phase_transformer import PhaseTransformer, HybridPhaseTransformer, TransformerConfig

# Optional imports
try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False

try:
    from torch.utils.tensorboard import SummaryWriter
    TENSORBOARD_AVAILABLE = True
except ImportError:
    TENSORBOARD_AVAILABLE = False

try:
    from datasets import load_dataset
    from transformers import AutoTokenizer
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    print("Warning: HuggingFace datasets/transformers not installed.")
    print("Install with: pip install datasets transformers")

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


# =============================================================================
# CONSTANTS
# =============================================================================

# Entropy constants for coherence loss (S3, S5, S8-S9)
# These control the semantic entropy regularization behavior
ENTROPY_MAX = 10.8          # log(50257) - maximum possible entropy for GPT-2 vocab
ENTROPY_TARGET = 4.0        # Target entropy for moderate confidence
ENTROPY_UPDATE_THRESHOLD = 6.0  # Entropy above this triggers update gate


class EntropyTracker:
    """
    Tracks entropy across training steps for stability loss (S8-S9).

    Encapsulates the previously global _prev_entropy state and provides
    helper methods for computing update gates and stability losses.
    """

    def __init__(self):
        self.prev_entropy: Optional[torch.Tensor] = None

    def compute_coherence_terms(
        self,
        entropy: torch.Tensor,
        device: torch.device,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Dict[str, float]]:
        """
        Compute entropy loss, update gate, and stability loss.

        Returns:
            L_entropy: Entropy regularization loss
            update_gate: Gate for scaling coherence loss (0-1)
            L_stability: Stability loss penalizing entropy spikes
            metrics: Dict with entropy, update_gate, entropy_change
        """
        metrics = {}

        # Entropy loss - target moderate confidence
        L_entropy = (entropy - ENTROPY_TARGET).pow(2)
        metrics["entropy"] = entropy.item()

        # Update gate: high when entropy is high (uncertain/changing context)
        update_gate = torch.sigmoid((entropy - ENTROPY_UPDATE_THRESHOLD) * 2.0)

        # Stability loss from entropy change
        if self.prev_entropy is not None:
            entropy_change = entropy - self.prev_entropy
            # Combine with entropy spike detection
            change_gate = torch.sigmoid(entropy_change * 5.0)
            update_gate = torch.max(update_gate, change_gate * 0.5)
            # Penalize entropy increases (dH/dt > 0 violates S8)
            L_stability = F.relu(entropy_change)
            metrics["entropy_change"] = entropy_change.item()
        else:
            L_stability = torch.tensor(0.0, device=device)
            metrics["entropy_change"] = 0.0

        metrics["update_gate"] = update_gate.item()

        # Update state for next step
        self.prev_entropy = entropy.detach()

        return L_entropy, update_gate, L_stability, metrics

    def reset(self):
        """Reset tracker state (e.g., at start of new epoch)."""
        self.prev_entropy = None


# Global entropy tracker instance
_entropy_tracker = EntropyTracker()


class MemoryGuard:
    """
    V9.2 Dynamic VRAM-based batch scaling with state preservation.

    Monitors GPU memory and adjusts batch_size/gradient_accumulation to:
    - Downshift at step 3000 (Phase handshake) to prevent OOM
    - Ramp up ("Crank") after step 10000 to maximize throughput

    Key design decisions:
    - Preserves effective_batch when downshifting (batch/2, accum*2)
    - Doubles effective_batch when cranking (for faster convergence)
    - Caps Phase LR at 1e-5 during crank to prevent angular instability
    - Uses sqrt scaling for Quadratic LR when effective batch doubles
    """

    def __init__(
        self,
        config: 'TrainingConfig',
        initial_batch_size: int,
        initial_accum: int,
    ):
        self.config = config
        self.batch_size = initial_batch_size
        self.accum = initial_accum
        self.effective_batch = initial_batch_size * initial_accum
        self.lr_scale = 1.0  # Multiplier for base LR (sqrt scaling on crank)
        self.cranked = False  # Only crank once
        self.global_data_idx = 0  # Track position in dataset

    def get_vram_gb(self) -> float:
        """Get current reserved VRAM in GB."""
        if not torch.cuda.is_available():
            return 0.0
        return torch.cuda.memory_reserved() / (1024**3)

    def check_and_adjust(
        self,
        step: int,
        logger: Optional[logging.Logger] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check VRAM and adjust batch parameters if needed.

        Returns:
            (changed: bool, action: str or None)
            - changed: True if batch_size/accum were modified
            - action: "downshift", "crank", or None
        """
        if not self.config.memory_guard_enabled:
            return False, None

        vram_gb = self.get_vram_gb()

        # 1. PROACTIVE HANDSHAKE DOWNSHIFT (step 2999 or 3000)
        # Preemptively reduce batch size before Phase unfreezes
        if step in (self.config.phase_delay_steps - 1, self.config.phase_delay_steps):
            if self.batch_size > self.config.min_batch_size:
                return self._downshift(step, vram_gb, "handshake", logger)

        # 2. EMERGENCY DOWNSHIFT (VRAM pressure)
        if vram_gb > self.config.vram_emergency_gb:
            if self.batch_size > self.config.min_batch_size:
                return self._downshift(step, vram_gb, "emergency", logger)

        # 3. THE CRANK (ramp up after stability)
        if (step >= self.config.crank_step and
            not self.cranked and
            vram_gb < self.config.vram_underutil_gb and
            self.batch_size < self.config.max_batch_size):
            return self._crank(step, vram_gb, logger)

        return False, None

    def _downshift(
        self,
        step: int,
        vram_gb: float,
        reason: str,
        logger: Optional[logging.Logger] = None,
    ) -> Tuple[bool, str]:
        """Reduce batch size, increase accumulation to maintain effective batch."""
        old_bs = self.batch_size
        self.batch_size = max(self.config.min_batch_size, self.batch_size // 2)
        self.accum = self.accum * 2
        # Effective batch stays the same

        if logger:
            logger.info(
                f"🔧 [Step {step}] DOWNSHIFT ({reason}): "
                f"Batch {old_bs}→{self.batch_size}, Accum→{self.accum} "
                f"(Eff={self.effective_batch}) | VRAM: {vram_gb:.1f}GB"
            )

        torch.cuda.empty_cache()
        return True, "downshift"

    def _crank(
        self,
        step: int,
        vram_gb: float,
        logger: Optional[logging.Logger] = None,
    ) -> Tuple[bool, str]:
        """Increase batch size to maximize throughput (effective batch doubles)."""
        old_bs = self.batch_size
        old_eff = self.effective_batch

        self.batch_size = min(self.config.max_batch_size, self.batch_size * 2)
        # Accum stays same - effective batch doubles
        self.effective_batch = self.batch_size * self.accum

        # Apply sqrt scaling to LR (quadratic layers only, Phase is capped)
        self.lr_scale = 1.414  # sqrt(2)
        self.cranked = True

        if logger:
            logger.info(
                f"🚀 [Step {step}] CRANK: "
                f"Batch {old_bs}→{self.batch_size}, Eff {old_eff}→{self.effective_batch} "
                f"| LR×{self.lr_scale:.3f} (Phase capped at {self.config.phase_lr_cap:.1e}) "
                f"| VRAM: {vram_gb:.1f}GB"
            )

        torch.cuda.empty_cache()
        return True, "crank"

    def update_data_position(self, batches_processed: int):
        """Track position in dataset for state-preserving restarts."""
        self.global_data_idx += batches_processed * self.batch_size

    def get_phase_lr(self, base_lr: float, phase_mult: float) -> float:
        """
        Get Phase LR with crank cap applied.

        During crank, Quadratic layers get lr_scale boost but Phase is capped
        to prevent angular instability in the rotation layers.
        """
        if self.cranked:
            # Phase LR is capped regardless of lr_scale
            return min(base_lr * phase_mult * self.lr_scale, self.config.phase_lr_cap)
        return base_lr * phase_mult


# =============================================================================
# V9.3 TRINITY OPTIMIZATION COMPONENTS
# =============================================================================

class Lookahead(torch.optim.Optimizer):
    """
    V9.3 Lookahead Optimizer wrapper.

    Maintains "slow" weights that follow "fast" weights at a distance.
    Acts as a low-pass filter to smooth out training vibrations.

    Paper: "Lookahead Optimizer: k steps forward, 1 step back" (Zhang et al., 2019)

    Args:
        base_optimizer: The inner optimizer (e.g., AdamW)
        k: Number of fast steps before slow weight update (default: 5)
        alpha: Interpolation factor for slow weights (default: 0.5)
    """

    def __init__(self, base_optimizer, k=5, alpha=0.5):
        self.base_optimizer = base_optimizer
        self.k = k
        self.alpha = alpha
        self._step_count = 0

        # Cache slow weights
        self.slow_weights = []
        for group in base_optimizer.param_groups:
            slow_group = []
            for p in group['params']:
                if p.requires_grad:
                    slow_group.append(p.data.clone())
                else:
                    slow_group.append(None)
            self.slow_weights.append(slow_group)

    @property
    def param_groups(self):
        return self.base_optimizer.param_groups

    def state_dict(self):
        return {
            'base': self.base_optimizer.state_dict(),
            'slow_weights': self.slow_weights,
            'step_count': self._step_count
        }

    def load_state_dict(self, state_dict):
        self.base_optimizer.load_state_dict(state_dict['base'])
        self.slow_weights = state_dict.get('slow_weights', self.slow_weights)
        self._step_count = state_dict.get('step_count', 0)

    def zero_grad(self):
        self.base_optimizer.zero_grad()

    def step(self, closure=None):
        # Fast step
        loss = self.base_optimizer.step(closure)
        self._step_count += 1

        # Slow step every k iterations
        if self._step_count % self.k == 0:
            for group_idx, group in enumerate(self.base_optimizer.param_groups):
                for param_idx, p in enumerate(group['params']):
                    if p.requires_grad and self.slow_weights[group_idx][param_idx] is not None:
                        slow = self.slow_weights[group_idx][param_idx]
                        # Interpolate: slow = slow + alpha * (fast - slow)
                        slow.add_(p.data - slow, alpha=self.alpha)
                        # Update fast weights to slow position
                        p.data.copy_(slow)

        return loss

    def sync_slow_weights(self):
        """Force sync slow weights to current fast weights."""
        for group_idx, group in enumerate(self.base_optimizer.param_groups):
            for param_idx, p in enumerate(group['params']):
                if p.requires_grad and self.slow_weights[group_idx][param_idx] is not None:
                    self.slow_weights[group_idx][param_idx].copy_(p.data)


def apply_agc(model: nn.Module, threshold: float = 0.01, eps: float = 1e-3) -> Dict[str, float]:
    """
    V9.3 Per-Layer Adaptive Gradient Clipping (AGC).

    Clips gradients based on the ratio of gradient norm to weight norm per parameter.
    This allows healthy layers to learn while throttling exploding gradients.

    Args:
        model: The model with computed gradients
        threshold: Maximum allowed grad_norm / weight_norm ratio
        eps: Small constant to avoid division by zero

    Returns:
        Dict with clipping statistics (for logging GSS)
    """
    stats = {
        'total_params': 0,
        'clipped_params': 0,
        'max_ratio': 0.0,
        'phase_max_ratio': 0.0,
    }

    for name, p in model.named_parameters():
        if p.grad is None:
            continue

        stats['total_params'] += 1

        # Compute norms
        p_norm = torch.norm(p.data).clamp(min=eps)
        g_norm = torch.norm(p.grad.data)

        # Compute ratio (Gradient Spike Score per param)
        ratio = (g_norm / p_norm).item()
        stats['max_ratio'] = max(stats['max_ratio'], ratio)

        # Track Phase-specific ratio
        if 'phase' in name.lower():
            stats['phase_max_ratio'] = max(stats['phase_max_ratio'], ratio)

        # Clip if ratio exceeds threshold
        max_grad = p_norm * threshold
        if g_norm > max_grad:
            p.grad.data.mul_(max_grad / (g_norm + 1e-6))
            stats['clipped_params'] += 1

    return stats


class PPLGuard:
    """
    V9.3 PPL-Guard: Monitors Val PPL velocity alongside coherence.

    When both Val PPL is spiking AND coherence is dropping, this indicates
    the model is "accelerating into a wall" and needs intervention.
    """

    def __init__(
        self,
        ppl_velocity_threshold: float = 50.0,
        coherence_threshold: float = 0.700,
        agc_tighten_factor: float = 0.5,  # Multiply AGC threshold by this when triggered
    ):
        self.ppl_velocity_threshold = ppl_velocity_threshold
        self.coherence_threshold = coherence_threshold
        self.agc_tighten_factor = agc_tighten_factor
        self.last_val_ppl = None
        self.triggered = False
        self.trigger_step = None

    def check(
        self,
        val_ppl: float,
        coherence: float,
        step: int,
        logger: Optional[logging.Logger] = None,
    ) -> Tuple[bool, float]:
        """
        Check if PPL-Guard should trigger.

        Returns:
            (triggered: bool, recommended_agc_threshold: float)
        """
        if self.last_val_ppl is None:
            self.last_val_ppl = val_ppl
            return False, 0.01  # Default AGC threshold

        ppl_velocity = val_ppl - self.last_val_ppl
        self.last_val_ppl = val_ppl

        # Check dual-threat condition
        if ppl_velocity > self.ppl_velocity_threshold and coherence < self.coherence_threshold:
            if not self.triggered:
                self.triggered = True
                self.trigger_step = step
                if logger:
                    logger.warning(
                        f"🔥 [Step {step}] PPL-Guard TRIGGERED: "
                        f"Val PPL Δ={ppl_velocity:.0f} > {self.ppl_velocity_threshold:.0f}, "
                        f"Coh={coherence:.3f} < {self.coherence_threshold:.3f} - Tightening AGC"
                    )
            # Return tightened AGC threshold
            return True, 0.01 * self.agc_tighten_factor

        return False, 0.01  # Normal AGC threshold


def trigger_handshake(
    model: nn.Module,
    config: 'TrainingConfig',
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    logger: Optional[logging.Logger] = None,
) -> torch.optim.Optimizer:
    """
    V9.3 Handshake Trigger: Rebuilds optimizer at step 3001 for Phase unfreeze.

    This function:
    1. Ensures all parameters have requires_grad=True
    2. Rebuilds optimizer with WD exclusion groups
    3. Applies Handshake Spike LR (6e-5 Quad, 2e-5 Phase)
    4. Wraps in Lookahead

    Args:
        model: The model
        config: Training config
        optimizer: Current optimizer (will be replaced)
        device: Training device
        logger: Optional logger

    Returns:
        New optimizer wrapped in Lookahead
    """
    if logger:
        logger.info("🚀 [V9.3] HANDSHAKE TRIGGER: Unfreezing Phase & Applying Spike LR...")

    # 1. Ensure all parameters can receive gradients
    unfrozen_count = 0
    for p in model.parameters():
        if not p.requires_grad:
            p.requires_grad = True
            unfrozen_count += 1

    if logger and unfrozen_count > 0:
        logger.info(f"   Unfroze {unfrozen_count} parameters")

    # 2. Group parameters with WD exclusion
    decay_params = []
    no_decay_params = []
    phase_params = []

    no_decay_keywords = ["bias", "LayerNorm", "norm", "ln_"]
    phase_keywords = ["phase", "Phase"]

    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue

        # Check if this is a Phase parameter
        is_phase = any(kw in name for kw in phase_keywords)
        # Check if this should have no weight decay
        is_no_decay = any(kw in name for kw in no_decay_keywords)

        if is_phase:
            phase_params.append(p)
        elif is_no_decay:
            no_decay_params.append(p)
        else:
            decay_params.append(p)

    # 3. Build optimizer groups with Handshake Spike LRs
    handshake_quad_lr = config.learning_rate * 1.5  # 4e-5 -> 6e-5
    handshake_phase_lr = 2e-5  # Spike for fast integration

    param_groups = [
        {
            "params": decay_params,
            "lr": handshake_quad_lr,
            "weight_decay": config.weight_decay,
            "name": "stable_wd"
        },
        {
            "params": no_decay_params,
            "lr": handshake_quad_lr,
            "weight_decay": 0.0,
            "name": "stable_no_wd"
        },
        {
            "params": phase_params,
            "lr": handshake_phase_lr,
            "weight_decay": 0.0,  # No WD for Phase (angular params)
            "name": "phase_attn"
        },
    ]

    if logger:
        logger.info(f"   Quad LR: {handshake_quad_lr:.2e} (1.5x spike)")
        logger.info(f"   Phase LR: {handshake_phase_lr:.2e} (fast integration)")
        logger.info(f"   Params: {len(decay_params)} decay, {len(no_decay_params)} no-decay, {len(phase_params)} phase")

    # 4. Create new AdamW optimizer
    new_optimizer = AdamW(
        param_groups,
        betas=(config.beta1, config.beta2),
        eps=config.eps,
    )

    # 5. Wrap in Lookahead for stability
    lookahead_optimizer = Lookahead(new_optimizer, k=5, alpha=0.5)

    if logger:
        logger.info("   Wrapped in Lookahead (k=5, α=0.5)")
        logger.info("🚀 Handshake complete - Phase layers now training!")

    return lookahead_optimizer


class MetricsLogger:
    """
    Unified logging to wandb and TensorBoard.

    Reduces duplicated logging code throughout the training loop.
    """

    def __init__(
        self,
        config: 'TrainingConfig',
        tb_writer: Optional['SummaryWriter'] = None
    ):
        self.config = config
        self.tb_writer = tb_writer
        self.wandb_enabled = config.wandb and WANDB_AVAILABLE

    def log(self, metrics: Dict[str, float], step: int, prefix: str = "train"):
        """
        Log metrics to wandb and TensorBoard.

        Args:
            metrics: Dict of metric name -> value
            step: Current training step
            prefix: Prefix for metric names (e.g., "train", "val")
        """
        # Wandb logging
        if self.wandb_enabled:
            wandb_metrics = {f"{prefix}/{k}": v for k, v in metrics.items()}
            wandb.log(wandb_metrics, step=step)

        # TensorBoard logging
        if self.tb_writer is not None:
            for name, value in metrics.items():
                self.tb_writer.add_scalar(f"{prefix}/{name}", value, step)

    def close(self):
        """Clean up logging resources."""
        if self.wandb_enabled:
            wandb.finish()
        if self.tb_writer is not None:
            self.tb_writer.close()


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TrainingConfig:
    """Complete training configuration."""

    # Model architecture
    model_size: str = "small"  # tiny, small, medium, large
    model_type: str = "phase"  # phase, hybrid
    vocab_size: int = 50257  # GPT-2 vocab size
    max_seq_len: int = 1024
    dropout: float = 0.1

    # Phase-specific parameters
    sync_steps: int = 3
    sync_lr: float = 0.1

    # Hybrid-specific parameters
    # NOTE: Updated defaults based on diagnostic findings:
    # - 6/6 split works better than 4/8 for semantic feature extraction
    # - Higher alpha_phase (0.6) forces the model to use long-range attention
    # - Gate init changed to 0.95 to preserve memory (learn to forget, not remember)
    local_layers: int = 6  # Number of early layers with local attention only (was 4)
    window_size: int = 256  # Local attention window size
    local_backend: str = "auto"  # LocalAttention backend: auto, flash, sdpa, unfold
    alpha_local: float = 0.4  # Weight for local attention in hybrid layers (was 0.8)
    alpha_phase: float = 0.6  # Weight for phase attention in hybrid layers (was 0.2)

    # Alpha FADE-IN schedule: "Training Wheels" for hybrid stability
    # Start with phase OFF (0.0), gradually fade in to target (0.6)
    # This forces Quadratic layers to learn basic patterns first,
    # then Phase layers join in for long-range structure
    alpha_phase_start: float = 0.0   # Initial: Phase attention OFF (training wheels)
    alpha_phase_end: float = 0.6     # Final: Full phase attention
    alpha_warmup_steps: int = 10000  # Steps to fade in phase attention (V8: extended runway)

    # Training hyperparameters
    batch_size: int = 16
    gradient_accumulation: int = 1
    max_steps: int = 100000
    warmup_steps: int = 2000

    # Optimizer
    learning_rate: float = 3e-4
    weight_decay: float = 0.1
    beta1: float = 0.9
    beta2: float = 0.95
    eps: float = 1e-8
    max_grad_norm: float = 1.0

    # LLRD: Layer-wise Learning Rate Decay (Attention Cooling)
    # The Q, K, V projections in attention are sensitive to high LR (softmax saturation).
    # Apply a "cooling factor" to attention params while keeping phase/MLP at full LR.
    # 0.5 is balanced; use 0.3 for "safety first" during instability
    attn_cooling_factor: float = 1.0  # Local/Quadratic attention LR multiplier (baseline, full LR)
    phase_cooling_factor: float = 0.25  # Phase attention MAX LR multiplier (V9: 0.25x = 1e-5 at base 4e-5)

    # V9: Delayed Phase LR - Phase layers frozen until Quadratic builds foundation
    phase_delay_steps: int = 3000  # Steps before Phase LR starts (frozen at 0)
    phase_ramp_steps: int = 7000   # Steps to ramp Phase LR from 0 to phase_cooling_factor

    # V9.2: MemoryGuard - Dynamic VRAM-based batch scaling
    # Automatically adjusts batch_size/gradient_accumulation based on GPU memory pressure
    # - Downshift at step 3000 (Phase handshake) or when VRAM > emergency threshold
    # - Ramp up ("Crank") after step 10000 when VRAM is underutilized
    memory_guard_enabled: bool = False  # Enable dynamic batch scaling
    vram_target_gb: float = 72.0  # Target VRAM usage for optimal throughput
    vram_emergency_gb: float = 77.0  # Emergency downshift threshold (near OOM)
    vram_underutil_gb: float = 55.0  # VRAM below this triggers ramp-up
    vram_check_interval: int = 100  # Check VRAM every N steps
    min_batch_size: int = 8  # Minimum batch size floor
    max_batch_size: int = 64  # Maximum batch size ceiling
    crank_step: int = 10000  # Step after which ramp-up is allowed
    phase_lr_cap: float = 1e-5  # Maximum Phase LR during "crank" (prevents angular instability)

    # V9.2.1: Coherence-based LR freeze - abort warmup if model loses coherence
    coherence_freeze_enabled: bool = True  # Enable coherence monitoring
    coherence_freeze_threshold: float = 0.700  # Freeze LR if coherence drops below this
    coherence_warning_threshold: float = 0.750  # Log warning when coherence drops below this

    # V9.3: Trinity Optimization - AGC, Lookahead, PPL-Guard, Handshake
    trinity_enabled: bool = False  # Enable V9.3 Trinity optimization suite
    agc_enabled: bool = True  # Enable Adaptive Gradient Clipping
    agc_threshold: float = 0.01  # Max grad_norm / weight_norm ratio
    lookahead_enabled: bool = True  # Enable Lookahead optimizer wrapper
    lookahead_k: int = 5  # Steps between slow weight updates
    lookahead_alpha: float = 0.5  # Interpolation factor for slow weights
    ppl_guard_enabled: bool = True  # Enable PPL-Guard monitoring
    ppl_velocity_threshold: float = 50.0  # PPL jump that triggers guard
    handshake_spike_enabled: bool = True  # Enable LR spike at handshake
    handshake_spike_factor: float = 1.5  # Multiply base LR by this at handshake
    handshake_phase_lr: float = 2e-5  # Phase LR during handshake spike
    handshake_duration: int = 500  # Steps to maintain spike (3001-3500)

    # V9.3.2: Recovery Mode - active LR reduction when frozen but still degrading
    recovery_mode_enabled: bool = True  # Enable recovery mode after freeze
    recovery_ppl_threshold: float = 0.05  # 5% PPL rise triggers LR cut
    recovery_lr_cut_factor: float = 0.5  # Cut LR by 50% each time
    recovery_max_cuts: int = 3  # Maximum number of LR cuts before giving up
    recovery_exit_coh: float = 0.720  # Exit recovery when coherence > this
    recovery_exit_ppl_drops: int = 2  # AND PPL drops for this many consecutive evals

    # Learning rate schedule
    lr_scheduler: str = "cosine"  # cosine, linear, constant
    min_lr_ratio: float = 0.1  # minimum LR as ratio of peak

    # Mixed precision
    mixed_precision: str = "bf16"  # none, fp16, bf16

    # Gradient checkpointing (for large models)
    gradient_checkpointing: bool = False  # Enable to reduce memory at cost of speed

    # Chunked processing (for ultra-long sequences like 10M tokens)
    chunk_size: int = 0  # 0 = disabled, otherwise process sequence in chunks of this size

    # Checkpointing
    checkpoint_dir: str = "checkpoints"
    save_every: int = 5000
    eval_every: int = 100
    log_every: int = 100

    # Dataset
    dataset: str = "wikitext2"  # c4, wikitext103, wikitext2, custom
    dataset_path: Optional[str] = None  # for custom datasets
    tokenizer: str = "gpt2"  # gpt2, tiktoken, custom

    # Evaluation
    # eval_samples = max sequences to evaluate (NOT tokens)
    # With batch_size=32, eval_samples=256 means 8 batches = 256K tokens
    # WikiText-103 val set is only 248K tokens (~7 batches), so 256 uses full set
    # For larger datasets (C4), keep this reasonable to avoid slow evals
    eval_samples: int = 256  # ~8 batches = 256K tokens at batch_size=32, seq_len=1024

    # Logging
    wandb: bool = False
    wandb_project: str = "symbolu"
    wandb_run: Optional[str] = None
    tensorboard: bool = False

    # Hardware
    device: str = "auto"  # auto, cuda, cpu
    num_workers: int = 4
    pin_memory: bool = True

    # Performance
    use_compile: bool = False  # Use torch.compile for 10-30% speedup (requires PyTorch 2.0+)
    compile_mode: str = "reduce-overhead"  # default, reduce-overhead, max-autotune

    # Resume
    resume: Optional[str] = None
    resume_weights_only: bool = False  # Only load model weights, skip optimizer state

    # Coherence Loss (S3, S1-S2, S8-S9)
    use_coherence_loss: bool = True  # Enable coherence-enhanced training
    lambda_entropy: float = 0.01     # S5: Semantic entropy weight
    lambda_coherence: float = 0.01   # S1-S2: Layer coherence weight
    lambda_stability: float = 0.001  # S8-S9: Stability constraint weight

    # Loss Type (memory-efficient options for long context)
    loss_type: str = "cross_entropy"  # cross_entropy, contrastive, infonce, state_delta
    num_negatives: int = 1024         # Number of negative samples for contrastive
    contrastive_margin: float = 1.0   # Margin for hinge loss
    contrastive_temperature: float = 0.1  # Temperature for InfoNCE

    # State-Centric Training (for 10M+ context - NO LM head required!)
    lambda_delta: float = 1.0         # State delta prediction weight
    lambda_entropy_state: float = 0.1 # Entropy change weight
    lambda_constraint: float = 0.1    # Constraint satisfaction weight
    target_entropy_rate: float = 0.5  # Target entropy rate

    # Chunked LM Head (for ultra-long contexts 1M+)
    lm_head_chunk_size: int = 0  # 0 = disabled, >0 = chunk size for LM head processing
    # Recommended: 8192 for 1M context, 4096 for 5M context

    # Seed
    seed: int = 42

    # Quality Sampling (periodic generation to monitor training quality)
    sample_every: int = 500  # Generate samples every N steps (0 = disabled)
    sample_prompts: tuple = (
        "The history of the Roman Empire began when",
        "In computer science, algorithms are",
        "The weather today is expected to be",
    )


# Model size presets
MODEL_PRESETS = {
    "tiny": {
        "embed_dim": 256,
        "num_layers": 4,
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
        "num_layers": 24,
        "num_heads": 16,
        "ff_dim": 4096,
    },
    "xl": {
        "embed_dim": 2048,
        "num_layers": 24,
        "num_heads": 16,
        "ff_dim": 8192,
    },
    "7b": {
        "embed_dim": 4096,
        "num_layers": 32,
        "num_heads": 32,
        "ff_dim": 11008,  # LLaMA-style: ~2.7x hidden dim
        "use_gqa": True,
        "num_kv_heads": 8,  # Grouped Query Attention: 32/8 = 4 groups
    },
}


# =============================================================================
# LOGGING
# =============================================================================

def setup_logging(config: TrainingConfig) -> logging.Logger:
    """Set up logging configuration."""
    log_dir = Path(config.checkpoint_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"train_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )

    logger = logging.getLogger("train")
    return logger


# =============================================================================
# DATASET
# =============================================================================

class TextDataset(Dataset):
    """Dataset for language modeling."""

    def __init__(
        self,
        tokens: torch.Tensor,
        seq_len: int,
    ):
        self.tokens = tokens
        self.seq_len = seq_len
        self.num_samples = len(tokens) // seq_len

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        start = idx * self.seq_len
        end = start + self.seq_len + 1
        chunk = self.tokens[start:end]

        x = chunk[:-1]  # Input
        y = chunk[1:]   # Target (shifted by 1)

        return x, y


def load_tokenizer(config: TrainingConfig):
    """Load tokenizer based on configuration."""
    if config.tokenizer == "tiktoken" and TIKTOKEN_AVAILABLE:
        enc = tiktoken.get_encoding("gpt2")
        return enc
    elif config.tokenizer == "gpt2" and HF_AVAILABLE:
        tokenizer = AutoTokenizer.from_pretrained("gpt2")
        # Suppress length warning - we handle chunking in TextDataset
        tokenizer.model_max_length = int(1e12)
        return tokenizer
    else:
        raise ValueError(f"Tokenizer {config.tokenizer} not available")


def tokenize_text(text: str, tokenizer) -> torch.Tensor:
    """Tokenize text using the appropriate tokenizer."""
    # Check if it's a tiktoken encoder (has 'encode_ordinary' method)
    if TIKTOKEN_AVAILABLE and hasattr(tokenizer, 'encode_ordinary'):
        # tiktoken
        tokens = tokenizer.encode(text, allowed_special={'<|endoftext|>'})
    else:
        # HuggingFace tokenizer
        tokens = tokenizer.encode(text)

    return torch.tensor(tokens, dtype=torch.long)


def load_dataset_tokens(config: TrainingConfig, split: str = "train") -> torch.Tensor:
    """Load and tokenize dataset."""
    if not HF_AVAILABLE:
        raise ImportError("datasets library required. Install: pip install datasets")

    print(f"Loading {config.dataset} dataset ({split} split)...")

    # Load tokenizer
    tokenizer = load_tokenizer(config)

    # Load dataset
    if config.dataset == "c4":
        # Use allenai/c4 (the newer supported version)
        dataset = load_dataset("allenai/c4", "en", split=split, streaming=True, trust_remote_code=True)
        # Stream and tokenize (limit for memory)
        all_tokens = []
        max_tokens = 50_000_000 if split == "train" else 1_000_000

        for item in dataset:
            tokens = tokenize_text(item["text"], tokenizer)
            all_tokens.append(tokens)
            if sum(len(t) for t in all_tokens) >= max_tokens:
                break

        tokens = torch.cat(all_tokens)

    elif config.dataset == "wikitext103":
        dataset = load_dataset("wikitext", "wikitext-103-v1", split=split)
        text = "\n".join(dataset["text"])
        tokens = tokenize_text(text, tokenizer)

    elif config.dataset == "wikitext2":
        dataset = load_dataset("wikitext", "wikitext-2-v1", split=split)
        text = "\n".join(dataset["text"])
        tokens = tokenize_text(text, tokenizer)

    elif config.dataset == "custom" and config.dataset_path:
        with open(config.dataset_path, 'r') as f:
            text = f.read()
        tokens = tokenize_text(text, tokenizer)

    else:
        raise ValueError(f"Unknown dataset: {config.dataset}")

    print(f"Loaded {len(tokens):,} tokens")
    return tokens


def create_dataloaders(
    config: TrainingConfig,
) -> Tuple[DataLoader, DataLoader, TextDataset]:
    """Create train and validation dataloaders.

    Returns:
        train_loader, val_loader, train_dataset
        (train_dataset is returned for V9.2 MemoryGuard dynamic rebuilding)
    """

    # Load tokens
    train_tokens = load_dataset_tokens(config, "train")
    val_tokens = load_dataset_tokens(config, "validation" if config.dataset != "c4" else "validation")

    # Create datasets
    train_dataset = TextDataset(train_tokens, config.max_seq_len)
    val_dataset = TextDataset(val_tokens, config.max_seq_len)

    # Create dataloaders with performance optimizations
    # - prefetch_factor: Prefetch 2 batches per worker to hide data loading latency
    # - persistent_workers: Keep workers alive between epochs (avoids respawn overhead)
    dataloader_kwargs = dict(
        num_workers=config.num_workers,
        pin_memory=config.pin_memory,
        drop_last=True,
        prefetch_factor=2 if config.num_workers > 0 else None,
        persistent_workers=config.num_workers > 0,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        **dataloader_kwargs,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        **dataloader_kwargs,
    )

    return train_loader, val_loader, train_dataset


def rebuild_train_loader(
    train_dataset: TextDataset,
    config: TrainingConfig,
    new_batch_size: int,
    start_idx: int = 0,
) -> DataLoader:
    """
    V9.2: Rebuild train DataLoader with new batch size from a specific position.

    Used by MemoryGuard when dynamically adjusting batch_size during training.
    The start_idx allows resuming from where we left off in the dataset.
    """
    # Create a subset starting from start_idx
    if start_idx > 0 and start_idx < len(train_dataset):
        # Wrap indices to handle epoch boundaries
        indices = list(range(start_idx, len(train_dataset)))
        subset = torch.utils.data.Subset(train_dataset, indices)
    else:
        subset = train_dataset

    dataloader_kwargs = dict(
        num_workers=config.num_workers,
        pin_memory=config.pin_memory,
        drop_last=True,
        prefetch_factor=2 if config.num_workers > 0 else None,
        persistent_workers=config.num_workers > 0,
    )

    return DataLoader(
        subset,
        batch_size=new_batch_size,
        shuffle=False,  # Don't shuffle when resuming mid-epoch
        **dataloader_kwargs,
    )


# =============================================================================
# MODEL
# =============================================================================

def create_model(config: TrainingConfig) -> nn.Module:
    """Create PhaseTransformer or HybridPhaseTransformer model based on configuration."""

    # Get model preset
    if config.model_size not in MODEL_PRESETS:
        raise ValueError(f"Unknown model size: {config.model_size}")

    preset = MODEL_PRESETS[config.model_size]

    # Base model kwargs
    model_kwargs = dict(
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

    # Create model based on type
    if config.model_type == "hybrid":
        # Add hybrid-specific parameters
        model_kwargs.update(
            local_layers=config.local_layers,
            window_size=config.window_size,
            local_backend=config.local_backend,
            alpha_local=config.alpha_local,
            alpha_phase=config.alpha_phase,
        )
        model = HybridPhaseTransformer(**model_kwargs)
    else:
        # Default: pure phase attention
        model = PhaseTransformer(**model_kwargs)

    # Enable gradient checkpointing for large models
    if config.gradient_checkpointing:
        if hasattr(model, 'gradient_checkpointing_enable'):
            model.gradient_checkpointing_enable()
        else:
            # Manual gradient checkpointing support
            for module in model.modules():
                if hasattr(module, 'gradient_checkpointing'):
                    module.gradient_checkpointing = True

    return model


def count_parameters(model: nn.Module) -> int:
    """Count trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def update_alpha_schedule(
    model: nn.Module,
    step: int,
    config: TrainingConfig,
) -> float:
    """
    Update alpha_phase across all layers based on training progress.

    "Training Wheels" FADE-IN schedule (per ChatGPT/Google analysis):
    - Start with phase attention OFF (0.0) to let Quadratic layers learn first
    - Gradually fade in phase attention to target (0.6) over alpha_warmup_steps
    - This prevents "representation shear" where Phase distorts the residual stream
      before Quadratic layers have learned stable manifolds

    The Coherence (Coh) metric should stay stable or improve with this schedule.
    If Coh drops rapidly, phase is interfering too early.
    """
    # Calculate current alpha based on linear FADE-IN
    if step >= config.alpha_warmup_steps:
        current_alpha = config.alpha_phase_end
    else:
        frac = step / config.alpha_warmup_steps
        # Linear interpolation: 0.0 → 0.6 over warmup steps
        current_alpha = config.alpha_phase_start + frac * (config.alpha_phase_end - config.alpha_phase_start)

    # Update all attention layers that have alpha_phase
    for module in model.modules():
        if hasattr(module, 'alpha_phase'):
            with torch.no_grad():
                if hasattr(module.alpha_phase, 'fill_'):
                    module.alpha_phase.fill_(current_alpha)
                else:
                    module.alpha_phase = current_alpha

            # Also update alpha_local if present (hybrid layers)
            if hasattr(module, 'alpha_local'):
                with torch.no_grad():
                    if hasattr(module.alpha_local, 'fill_'):
                        module.alpha_local.fill_(1.0 - current_alpha)
                    else:
                        module.alpha_local = 1.0 - current_alpha

    return current_alpha


# =============================================================================
# GRADIENT DIAGNOSTICS
# =============================================================================

def compute_tier_gradient_norms(model: nn.Module) -> dict:
    """
    Compute gradient norms per tier to verify all layers are learning.

    Returns dict with:
    - stable_grad_norm: Gradient norm for MLP/embed params
    - local_attn_grad_norm: Gradient norm for Quadratic attention params
    - phase_attn_grad_norm: Gradient norm for Phase attention params
    - stable_grad_max: Max gradient in stable tier
    - local_attn_grad_max: Max gradient in local tier
    - phase_attn_grad_max: Max gradient in phase tier

    If a tier has grad_norm ≈ 0, those layers are NOT learning.
    """
    ATTN_PATTERNS = ["q_proj", "k_proj", "v_proj", "o_proj", "out_proj"]

    stable_grads = []
    local_attn_grads = []
    phase_attn_grads = []

    for name, param in model.named_parameters():
        if param.grad is None:
            continue

        grad_norm = param.grad.data.norm(2).item()
        name_lower = name.lower()

        # Classify into tier
        is_attn = any(pattern in name_lower for pattern in ATTN_PATTERNS)

        if not is_attn:
            stable_grads.append(grad_norm)
        elif 'phase_attn' in name_lower or 'phase_attention' in name_lower:
            phase_attn_grads.append(grad_norm)
        else:
            local_attn_grads.append(grad_norm)

    def safe_stats(grads):
        if not grads:
            return 0.0, 0.0
        total_norm = (sum(g**2 for g in grads)) ** 0.5
        max_norm = max(grads)
        return total_norm, max_norm

    stable_norm, stable_max = safe_stats(stable_grads)
    local_norm, local_max = safe_stats(local_attn_grads)
    phase_norm, phase_max = safe_stats(phase_attn_grads)

    return {
        'stable_grad_norm': stable_norm,
        'local_attn_grad_norm': local_norm,
        'phase_attn_grad_norm': phase_norm,
        'stable_grad_max': stable_max,
        'local_attn_grad_max': local_max,
        'phase_attn_grad_max': phase_max,
        'stable_param_count': len(stable_grads),
        'local_attn_param_count': len(local_attn_grads),
        'phase_attn_param_count': len(phase_attn_grads),
    }


def log_tier_gradients(model: nn.Module, step: int, logger) -> None:
    """Log gradient norms per tier to verify learning health. (Legacy - computes at call time)"""
    stats = compute_tier_gradient_norms(model)
    log_tier_gradients_from_metrics(stats, step, logger)


def log_tier_gradients_from_metrics(stats: dict, step: int, logger) -> None:
    """Log gradient norms per tier using pre-computed stats from train_step."""
    # Format: show norm and whether tier is "alive" (learning)
    def status(norm):
        if norm < 1e-8:
            return "❌ DEAD"
        elif norm < 1e-5:
            return "⚠️ WEAK"
        else:
            return "✅"

    logger.info(f"  📊 Gradient Health @ Step {step}:")
    logger.info(f"     Stable ({stats['stable_param_count']} params):     "
                f"norm={stats['stable_grad_norm']:.2e} {status(stats['stable_grad_norm'])}")
    logger.info(f"     Local Attn ({stats['local_attn_param_count']} params): "
                f"norm={stats['local_attn_grad_norm']:.2e} {status(stats['local_attn_grad_norm'])}")
    logger.info(f"     Phase Attn ({stats['phase_attn_param_count']} params): "
                f"norm={stats['phase_attn_grad_norm']:.2e} {status(stats['phase_attn_grad_norm'])}")


# =============================================================================
# OPTIMIZER & SCHEDULER
# =============================================================================

def create_optimizer(model: nn.Module, config: TrainingConfig) -> AdamW:
    """
    Create AdamW optimizer with TWO-TIER LLRD (Layer-wise Learning Rate Decay).

    Separates parameters into 6 groups for hybrid Local+Phase architecture:
    1. Stable params with decay (embeddings, MLP, non-attention params) - FULL LR (1.0x)
    2. Stable params without decay (bias, norm) - FULL LR (1.0x)
    3. Local/Quadratic attention params with decay - BASELINE LR (1.0x)
    4. Local/Quadratic attention params without decay - BASELINE LR (1.0x)
    5. Phase attention params with decay - STRONG cooling (0.2x)
    6. Phase attention params without decay - STRONG cooling (0.2x)

    The Two-Tier approach recognizes that:
    - Local/Quadratic (O(n²)) layers are the "heavy lifters" - stable, can handle full LR
    - Phase (O(n)) layers are "precision rotators" - sensitive, need strong cooling
    """

    # Attention parameter patterns
    ATTN_PATTERNS = ["q_proj", "k_proj", "v_proj", "o_proj", "out_proj"]

    def get_param_tier(name: str) -> str:
        """
        Classify parameter into tier: 'stable', 'local_attn', or 'phase_attn'.
        """
        name_lower = name.lower()

        # Check if it's an attention parameter
        is_attn = any(pattern in name_lower for pattern in ATTN_PATTERNS)
        if not is_attn:
            return 'stable'

        # Distinguish between local_attn and phase_attn
        if 'phase_attn' in name_lower or 'phase_attention' in name_lower:
            return 'phase_attn'
        elif 'local_attn' in name_lower or 'local_attention' in name_lower:
            return 'local_attn'
        else:
            # Default attention params (e.g., in non-hybrid models) get local tier
            return 'local_attn'

    def is_no_decay_param(name: str) -> bool:
        """Check if parameter should skip weight decay."""
        return 'bias' in name or 'norm' in name or 'embed' in name

    # Separate into 6 groups
    stable_decay_params = []
    stable_no_decay_params = []
    local_attn_decay_params = []
    local_attn_no_decay_params = []
    phase_attn_decay_params = []
    phase_attn_no_decay_params = []

    # Track parameter counts for logging
    stable_param_count = 0
    local_attn_param_count = 0
    phase_attn_param_count = 0

    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue

        num_params = param.numel()
        tier = get_param_tier(name)
        no_decay = is_no_decay_param(name)

        if tier == 'stable':
            stable_param_count += num_params
            if no_decay:
                stable_no_decay_params.append(param)
            else:
                stable_decay_params.append(param)
        elif tier == 'local_attn':
            local_attn_param_count += num_params
            if no_decay:
                local_attn_no_decay_params.append(param)
            else:
                local_attn_decay_params.append(param)
        else:  # phase_attn
            phase_attn_param_count += num_params
            if no_decay:
                phase_attn_no_decay_params.append(param)
            else:
                phase_attn_decay_params.append(param)

    # Compute LRs for each tier
    base_lr = config.learning_rate
    local_lr = base_lr * config.attn_cooling_factor    # Mild cooling (0.5x)
    phase_lr = base_lr * config.phase_cooling_factor   # Strong cooling (0.2x)

    param_groups = [
        {
            "params": stable_decay_params,
            "lr": base_lr,
            "weight_decay": config.weight_decay,
            "name": "stable_context",
        },
        {
            "params": stable_no_decay_params,
            "lr": base_lr,
            "weight_decay": 0.0,
            "name": "stable_no_decay",
        },
        {
            "params": local_attn_decay_params,
            "lr": local_lr,
            "weight_decay": config.weight_decay,
            "name": "local_attn",
        },
        {
            "params": local_attn_no_decay_params,
            "lr": local_lr,
            "weight_decay": 0.0,
            "name": "local_attn_no_decay",
        },
        {
            "params": phase_attn_decay_params,
            "lr": phase_lr,
            "weight_decay": config.weight_decay,
            "name": "phase_attn",
        },
        {
            "params": phase_attn_no_decay_params,
            "lr": phase_lr,
            "weight_decay": 0.0,
            "name": "phase_attn_no_decay",
        },
    ]

    # Filter out empty groups
    param_groups = [g for g in param_groups if len(g["params"]) > 0]

    optimizer = AdamW(
        param_groups,
        lr=config.learning_rate,  # Default LR (overridden by group-specific LR)
        betas=(config.beta1, config.beta2),
        eps=config.eps,
    )

    # Log the Two-Tier LLRD configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Two-Tier LLRD Optimizer Groups:")
    logger.info(f"  Stable (MLP/embed): {stable_param_count/1e6:.1f}M params @ LR {base_lr:.2e} (1.0x)")
    logger.info(f"  Local Attention:    {local_attn_param_count/1e6:.1f}M params @ LR {local_lr:.2e} ({config.attn_cooling_factor}x)")
    logger.info(f"  Phase Attention:    {phase_attn_param_count/1e6:.1f}M params @ LR {phase_lr:.2e} ({config.phase_cooling_factor}x)")

    return optimizer


def create_scheduler(
    optimizer: AdamW,
    config: TrainingConfig,
) -> LambdaLR:
    """Create learning rate scheduler with warmup."""

    def lr_lambda(step: int) -> float:
        # Warmup phase
        if step < config.warmup_steps:
            return step / max(1, config.warmup_steps)

        # Post-warmup: cosine decay
        progress = (step - config.warmup_steps) / max(1, config.max_steps - config.warmup_steps)

        if config.lr_scheduler == "cosine":
            # Cosine decay to min_lr_ratio
            return config.min_lr_ratio + (1 - config.min_lr_ratio) * 0.5 * (1 + math.cos(math.pi * progress))
        elif config.lr_scheduler == "linear":
            # Linear decay to min_lr_ratio
            return config.min_lr_ratio + (1 - config.min_lr_ratio) * (1 - progress)
        else:
            # Constant
            return 1.0

    scheduler = LambdaLR(optimizer, lr_lambda)
    return scheduler


# =============================================================================
# TRAINING
# =============================================================================

@dataclass
class TrainingState:
    """Training state for checkpointing."""
    step: int = 0
    epoch: int = 0
    best_val_loss: float = float('inf')
    total_tokens: int = 0
    train_losses: list = field(default_factory=list)
    ppl_history: list = field(default_factory=list)  # Track PPL for trend detection
    trend_patience: int = 0  # Patience counter for trend-based interventions
    ema_ppl: float = 0.0  # Exponential moving average of PPL (smooths noise)
    # V9.3.5: PPL-Ratchet LR control - smoothed, multi-eval signal
    ppl_lr_factor: float = 1.0  # LR factor based on PPL trend (ratchets down on rise)
    val_ppl_history: list = field(default_factory=list)  # Track Val PPL for smoothed velocity
    coh_history: list = field(default_factory=list)  # Track coherence for recovery check


def compute_semantic_entropy(logits: torch.Tensor, max_positions: int = 1024) -> torch.Tensor:
    """
    Compute semantic entropy (Formula S5) using LogSumExp - NO SOFTMAX.

    Memory-efficient formula:
        H ≈ logsumexp(logits) - mean(logits)

    This avoids creating O(B·T·V) probability tensors entirely.
    At 1M context with V=50K: saves ~200GB of memory.

    The approximation uses the fact that:
        H = logsumexp(logits) - Σ p_i · logits_i
        ≈ logsumexp(logits) - E[logits]  (when distribution is peaked)
    """
    B, N, V = logits.shape

    # Sample positions if sequence is too long
    if N > max_positions:
        indices = torch.linspace(0, N - 1, max_positions, dtype=torch.long, device=logits.device)
        logits = logits[:, indices, :]  # (B, max_positions, V)

    # LogSumExp entropy: O(B·T) memory, NOT O(B·T·V)
    # logsumexp gives log(Σ exp(logits)) = log(Z) where Z is partition function
    lse = torch.logsumexp(logits, dim=-1)  # (B, T) - no V dimension!

    # Approximate expected logit using max (mode of distribution)
    # This avoids computing full softmax
    max_logits, _ = logits.max(dim=-1)  # (B, T)

    # Entropy ≈ log(Z) - mode_logit
    # For peaked distributions, this is a good approximation
    entropy = lse - max_logits

    return entropy.mean()


def compute_semantic_entropy_exact(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """
    Compute exact cross-entropy based entropy using targets - NO SOFTMAX.

    Formula: H = logsumexp(logits) - logits[target]

    This is the exact entropy contribution at the target position,
    computed without materializing the full probability distribution.

    Memory: O(B·T) not O(B·T·V)
    """
    B, N, V = logits.shape

    # logsumexp over vocabulary
    lse = torch.logsumexp(logits, dim=-1)  # (B, N)

    # Get logit at target position
    target_logits = torch.gather(logits, dim=-1, index=targets.unsqueeze(-1)).squeeze(-1)  # (B, N)

    # Entropy = log(Z) - logit[target] = -log(p[target])
    entropy = lse - target_logits

    return entropy.mean()


def compute_layer_coherence(hidden_states: list) -> torch.Tensor:
    """
    Compute cross-layer coherence (Formulas S1-S2).

    C_global = Σᵢⱼ Corr(Lᵢ, Lⱼ)

    Higher coherence = layers are aligned in their representations.
    """
    if not hidden_states or len(hidden_states) < 2:
        return torch.tensor(0.0)

    coherence = 0.0
    count = 0

    for i in range(len(hidden_states) - 1):
        # Cosine similarity between adjacent layers (Formula S4)
        h_i = hidden_states[i].mean(dim=1)  # [B, D]
        h_j = hidden_states[i + 1].mean(dim=1)  # [B, D]

        cos_sim = F.cosine_similarity(h_i, h_j, dim=-1).mean()
        coherence += cos_sim
        count += 1

    return coherence / max(count, 1)


def compute_contrastive_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    num_negatives: int = 1024,
    margin: float = 1.0,
) -> torch.Tensor:
    """
    Compute contrastive loss - NO SOFTMAX, NO NORMALIZATION.

    Instead of cross-entropy over full vocabulary:
    - Score correct token higher than sampled negatives
    - Memory scales with num_negatives, NOT vocabulary size

    Loss = max(0, margin - score_pos + score_neg)

    Memory: O(B·T·num_negatives) instead of O(B·T·V)
    At 1M context: ~8GB instead of ~200GB

    Benefits:
    - Removes softmax normalization bottleneck
    - Works especially well with phase memory models
    - Scales to arbitrary vocabulary sizes
    """
    B, N, V = logits.shape
    device = logits.device

    # Get positive scores (score at target position)
    # Shape: (B, N)
    pos_scores = torch.gather(logits, dim=-1, index=targets.unsqueeze(-1)).squeeze(-1)

    # Sample random negatives
    # Shape: (B, N, num_negatives)
    neg_indices = torch.randint(0, V, (B, N, num_negatives), device=device)

    # Gather negative scores efficiently
    # Reshape logits for gathering: (B*N, V)
    logits_flat = logits.view(B * N, V)
    neg_indices_flat = neg_indices.view(B * N, num_negatives)

    # Gather: (B*N, num_negatives)
    neg_scores_flat = torch.gather(logits_flat, dim=-1, index=neg_indices_flat)

    # Reshape back: (B, N, num_negatives)
    neg_scores = neg_scores_flat.view(B, N, num_negatives)

    # Margin-based hinge loss: max(0, margin - pos + neg)
    # We want pos_score > neg_score + margin
    # Shape: (B, N, num_negatives)
    losses = F.relu(margin - pos_scores.unsqueeze(-1) + neg_scores)

    # Average over negatives, then over sequence and batch
    return losses.mean()


def compute_infonce_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    temperature: float = 0.1,
    num_negatives: int = 1024,
) -> torch.Tensor:
    """
    Compute InfoNCE contrastive loss - efficient alternative to cross-entropy.

    InfoNCE: -log(exp(pos/τ) / (exp(pos/τ) + Σ exp(neg/τ)))

    This is like cross-entropy but only over (1 + num_negatives) classes
    instead of full vocabulary.

    Memory: O(B·T·num_negatives) instead of O(B·T·V)
    """
    B, N, V = logits.shape
    device = logits.device

    # Get positive scores
    pos_scores = torch.gather(logits, dim=-1, index=targets.unsqueeze(-1)).squeeze(-1)
    pos_scores = pos_scores / temperature  # (B, N)

    # Sample negatives
    neg_indices = torch.randint(0, V, (B, N, num_negatives), device=device)

    # Gather negative scores efficiently
    logits_flat = logits.view(B * N, V)
    neg_indices_flat = neg_indices.view(B * N, num_negatives)
    neg_scores_flat = torch.gather(logits_flat, dim=-1, index=neg_indices_flat)
    neg_scores = neg_scores_flat.view(B, N, num_negatives) / temperature

    # InfoNCE: log(exp(pos) / (exp(pos) + sum(exp(neg))))
    # = pos - logsumexp([pos, neg1, neg2, ...])
    all_scores = torch.cat([pos_scores.unsqueeze(-1), neg_scores], dim=-1)  # (B, N, 1+num_neg)
    log_denominator = torch.logsumexp(all_scores, dim=-1)  # (B, N)

    # Loss = -log(p_pos) = log_denom - pos
    loss = log_denominator - pos_scores

    return loss.mean()


def compute_state_centric_loss(
    model: PhaseTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    lambda_delta: float = 1.0,
    lambda_entropy: float = 0.1,
    lambda_constraint: float = 0.1,
    target_entropy_rate: float = 0.5,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    State-centric training loss - NO TOKEN PREDICTION (no LM head).

    Instead of:
        hidden → LM head (50K dim) → CE loss  [O(B·T·V) memory = 200GB at 1M]

    We use:
        hidden → state_delta_predictor (768 dim) → state losses  [O(B·T·d) = 3GB at 1M]

    Training signals:
    1. State delta prediction: predict h[t+1] - h[t]
    2. Entropy change: smooth information flow
    3. Constraint satisfaction: bounded norms, diversity, smoothness

    Memory savings: 50K/768 = ~65x reduction per position
    At 1M context: 200GB → 3GB

    This enables training at 10M+ context without ANY vocabulary projection.
    Tokens become a projection for inference, not the training objective.

    Args:
        model: PhaseTransformer or HybridPhaseTransformer with state_delta_predictor
        batch: (input_ids, target_ids) - targets not used for state-centric training
        device: torch device
        lambda_delta: Weight for state delta prediction loss
        lambda_entropy: Weight for entropy change loss
        lambda_constraint: Weight for constraint satisfaction loss
        target_entropy_rate: Target rate of entropy change

    Returns:
        loss: Combined state-centric loss
        metrics: Dict with all loss components
    """
    from symbolu.phase_transformer import (
        compute_entropy_change_loss,
        compute_constraint_satisfaction_loss,
    )

    x, _ = batch  # y (targets) not needed for state-centric training
    x = x.to(device)

    # Get hidden states (no LM head projection!)
    hidden_states = model.forward_hidden(x)  # [B, T, embed_dim]

    # 1. State delta prediction loss
    delta_loss, delta_metrics = model.state_delta_predictor.compute_loss(hidden_states)

    # 2. Entropy change loss (information flow regularization)
    entropy_loss, entropy_metrics = compute_entropy_change_loss(
        hidden_states, target_entropy_rate=target_entropy_rate
    )

    # 3. Constraint satisfaction loss
    constraint_loss, constraint_metrics = compute_constraint_satisfaction_loss(hidden_states)

    # Combined loss
    total_loss = (
        lambda_delta * delta_loss +
        lambda_entropy * entropy_loss +
        lambda_constraint * constraint_loss
    )

    # Compile metrics
    metrics = {
        'loss': total_loss.item(),
        'delta_loss': delta_loss.item(),
        'entropy_loss': entropy_loss.item(),
        'constraint_loss': constraint_loss.item(),
        **{k: v.item() if torch.is_tensor(v) else v for k, v in delta_metrics.items()},
        **{k: v.item() if torch.is_tensor(v) else v for k, v in entropy_metrics.items()},
        **{k: v.item() if torch.is_tensor(v) else v for k, v in constraint_metrics.items()},
    }

    return total_loss, metrics


def compute_loss_streaming(
    model: PhaseTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    chunk_size: int,
    use_coherence_loss: bool = True,
    lambda_entropy: float = 0.01,
    lambda_coherence: float = 0.01,
    lambda_stability: float = 0.001,
    use_aux_reconstruction: bool = True,
    lambda_aux: float = 0.1,
) -> Tuple[None, Dict[str, float]]:
    """
    Compute loss with STREAMING chunked forward pass for ultra-long sequences (10M+ tokens).

    Key innovations:
    1. Phase contexts accumulated across chunks for true global context
    2. Per-chunk backward passes (like gradient accumulation) to avoid OOM
    3. Memory stays O(chunk_size) regardless of total sequence length
    4. AUXILIARY RECONSTRUCTION LOSS: Forces model to keep early chunk info
       high-fidelity in the streaming state by predicting early phase signatures
       from later chunks. This creates gradient signal across chunks!

    Returns None for loss (gradients already accumulated), metrics dict.
    """
    x, y = batch
    x = x.to(device)
    y = y.to(device)

    B, N = x.shape
    num_chunks = (N + chunk_size - 1) // chunk_size

    total_loss = 0.0  # Track for metrics only (not tensor)
    total_aux_loss = 0.0
    total_tokens = 0
    last_entropy = 0.0
    last_coherence = 0.0

    # Initialize streaming phase contexts (empty list signals streaming mode)
    phase_contexts = []

    # Store early chunk hidden state signatures for auxiliary reconstruction
    # This is the "memory" that later chunks must learn to reconstruct
    early_chunk_signatures = []  # List of (chunk_idx, signature_tensor)
    signature_sample_rate = max(1, num_chunks // 10)  # Sample ~10 early chunks

    for i in range(num_chunks):
        start = i * chunk_size
        end = min((i + 1) * chunk_size, N)

        x_chunk = x[:, start:end]
        y_chunk = y[:, start:end]

        # Forward pass with streaming phase context
        output = model(
            x_chunk,
            return_hidden=True,
            phase_contexts=phase_contexts,
            position_offset=start,
        )

        logits = output['logits']
        hidden_states = output.get('hidden_states', [])

        # =====================================================================
        # AUXILIARY RECONSTRUCTION LOSS
        # Store early chunk signatures, reconstruct in later chunks
        # =====================================================================
        aux_loss = torch.tensor(0.0, device=device)

        if use_aux_reconstruction and hidden_states:
            # Get current chunk's hidden state signature (mean over sequence)
            current_signature = hidden_states[-1].mean(dim=1)  # [B, D]

            # Store signatures from early chunks (first 30% of sequence)
            if i < num_chunks * 0.3 and i % signature_sample_rate == 0:
                early_chunk_signatures.append((i, current_signature.detach()))

            # In later chunks (after 50%), try to reconstruct early signatures
            # from the current accumulated phase context
            if i > num_chunks * 0.5 and early_chunk_signatures:
                # Pick a random early signature to reconstruct
                target_idx = i % len(early_chunk_signatures)
                _, target_signature = early_chunk_signatures[target_idx]

                # The model must predict early chunk info from current state
                # Use cosine similarity loss (1 - cos_sim)
                cos_sim = F.cosine_similarity(
                    current_signature, target_signature, dim=-1
                ).mean()
                aux_loss = (1.0 - cos_sim) * lambda_aux

        # Update phase contexts for next chunk - DETACH to break gradient chain
        new_contexts = output.get('phase_contexts', [])
        phase_contexts = []
        for ctx in new_contexts:
            detached_ctx = {}
            for k, v in ctx.items():
                if isinstance(v, torch.Tensor):
                    detached_ctx[k] = v.detach()
                else:
                    detached_ctx[k] = v
            phase_contexts.append(detached_ctx)

        # Compute chunk loss
        B_c, N_c, V = logits.shape
        chunk_tokens = B_c * N_c
        chunk_loss = F.cross_entropy(
            logits.view(B_c * N_c, V),
            y_chunk.view(B_c * N_c),
            ignore_index=-100,
            reduction='mean'
        )

        # Combined loss: task + auxiliary reconstruction
        combined_loss = chunk_loss + aux_loss

        # Per-chunk backward - gradients accumulate (like gradient accumulation)
        scaled_loss = combined_loss / num_chunks
        scaled_loss.backward()

        # Track metrics (no grad)
        total_loss += chunk_loss.item() * chunk_tokens
        total_aux_loss += aux_loss.item() if isinstance(aux_loss, torch.Tensor) else aux_loss
        total_tokens += chunk_tokens

        # Metrics from last chunk
        if i == num_chunks - 1 and use_coherence_loss:
            with torch.no_grad():
                last_entropy = compute_semantic_entropy(logits).item()
                last_coherence = compute_layer_coherence(hidden_states).item() if hidden_states else 0

        # Free memory immediately
        del output, logits, hidden_states, chunk_loss, scaled_loss, aux_loss, combined_loss
        if device.type == 'cuda':
            torch.cuda.empty_cache()

    # Average loss for metrics
    avg_loss = total_loss / total_tokens if total_tokens > 0 else 0.0
    avg_aux_loss = total_aux_loss / num_chunks if num_chunks > 0 else 0.0

    metrics = {
        "loss": avg_loss,
        "perplexity": math.exp(avg_loss) if avg_loss < 20 else float('inf'),
        "num_chunks": num_chunks,
        "streaming": True,
        "entropy": last_entropy,
        "coherence": last_coherence,
        "aux_recon_loss": avg_aux_loss,  # Track reconstruction quality
    }

    # Return None - gradients already accumulated via per-chunk backward
    return None, metrics


def compute_loss(
    model: PhaseTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    use_coherence_loss: bool = True,
    lambda_entropy: float = 0.01,
    lambda_coherence: float = 0.01,
    lambda_stability: float = 0.001,
    loss_type: str = "cross_entropy",  # cross_entropy, contrastive, infonce
    num_negatives: int = 1024,  # for contrastive losses
    contrastive_margin: float = 1.0,  # for hinge loss
    contrastive_temperature: float = 0.1,  # for infonce
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute enhanced loss with coherence formulas (S3, S1-S2, S8-S9).

    L_coherence = L_task + λ_e·L_entropy + λ_c·L_coherence + λ_s·L_stability

    Loss types:
    - cross_entropy: Standard fused CE (O(B·T) memory via fusion)
    - contrastive: Margin-based hinge loss (O(B·T·num_neg) memory)
    - infonce: InfoNCE contrastive (O(B·T·num_neg) memory)

    For 1M context with V=50K:
    - cross_entropy: ~8GB (fused, no explicit softmax)
    - contrastive/infonce: ~8GB with num_neg=1024

    Where:
    - L_task: Task loss (CE or contrastive)
    - L_entropy: Semantic entropy via LogSumExp (S5) - NO SOFTMAX
    - L_coherence: Layer coherence (S1-S2)
    - L_stability: Entropy stability (S8)
    """
    x, y = batch
    x = x.to(device)
    y = y.to(device)

    # Forward pass with hidden states for layer coherence
    output = model(x, return_hidden=True)
    logits = output['logits']
    hidden_states = output.get('hidden_states', [])

    B, N, V = logits.shape

    # Compute task loss based on loss_type
    if loss_type == "contrastive":
        # Margin-based contrastive loss - O(B·T·num_neg) memory
        L_task = compute_contrastive_loss(
            logits, y,
            num_negatives=num_negatives,
            margin=contrastive_margin
        )
    elif loss_type == "infonce":
        # InfoNCE contrastive loss - O(B·T·num_neg) memory
        L_task = compute_infonce_loss(
            logits, y,
            temperature=contrastive_temperature,
            num_negatives=num_negatives
        )
    else:
        # Standard fused cross-entropy - O(B·T) memory (fused kernel)
        L_task = F.cross_entropy(
            logits.view(B * N, V),
            y.view(B * N),
            ignore_index=-100,
        )

    metrics = {
        "loss": L_task.item(),
        "perplexity": torch.exp(L_task).item(),
    }

    if use_coherence_loss:
        # Compute semantic entropy
        entropy = compute_semantic_entropy(logits)

        # Use entropy tracker for update gate and stability (S5, S8-S9)
        L_entropy, update_gate, L_stability, entropy_metrics = _entropy_tracker.compute_coherence_terms(
            entropy, device
        )
        metrics.update(entropy_metrics)

        # Reduce coherence loss during updates
        coherence_scale = 1.0 - update_gate

        # S1-S2: Layer Coherence - maximize cross-layer alignment
        if hidden_states:
            coherence = compute_layer_coherence(hidden_states)
            L_coherence_term = 1.0 - coherence  # Penalize low coherence
            metrics["coherence"] = coherence.item()
        else:
            L_coherence_term = torch.tensor(0.0, device=device)
            metrics["coherence"] = 0.0

        # Combined Coherence Loss (S3) with conditional gating
        loss = (L_task +
                lambda_entropy * L_entropy +
                lambda_coherence * coherence_scale * L_coherence_term +
                lambda_stability * coherence_scale * L_stability)

        metrics["loss_total"] = loss.item()
    else:
        loss = L_task

    return loss, metrics


def compute_loss_chunked_lm_head(
    model: PhaseTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    lm_head_chunk_size: int = 8192,
    use_coherence_loss: bool = True,
    lambda_entropy: float = 0.01,
    lambda_coherence: float = 0.01,
    lambda_stability: float = 0.001,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute loss with CHUNKED LM head processing for ultra-long contexts.

    For 5M context with V=50K:
    - Standard: lm_head creates (1, 5M, 50K) = 1TB tensor = OOM
    - Chunked: Process 8K tokens at a time = 1.6GB per chunk = fits in memory

    Memory breakdown per chunk (8K tokens, 50K vocab):
    - Hidden states chunk: 8K × 256 = 2MB
    - Logits chunk: 8K × 50K × 2 = 800MB (bf16)
    - Cross-entropy: fused, no extra memory
    - Total: ~1GB per chunk, easily fits

    This enables training on sequences up to 5M+ tokens on B200 (192GB).

    Args:
        model: PhaseTransformer or HybridPhaseTransformer (must have forward_hidden method)
        batch: (input_ids, targets) tuple
        device: torch device
        lm_head_chunk_size: tokens per chunk for LM head processing (default 8192)
        use_coherence_loss: whether to compute coherence losses
        lambda_*: loss weights
    """
    x, y = batch
    x = x.to(device)
    y = y.to(device)

    B, N = x.shape

    # Forward pass to get hidden states ONLY (no LM head yet)
    # This is memory-efficient: hidden is (B, N, embed_dim)
    # For 5M context with embed_dim=256: only 5GB (vs 1TB for full logits)
    hidden = model.forward_hidden(x)  # (B, N, embed_dim)

    # Get hidden states for coherence loss (if available)
    hidden_states = []
    if use_coherence_loss and hasattr(model, 'blocks'):
        # Re-run to get intermediate hidden states for coherence
        # This is a tradeoff: memory vs accuracy
        # For now, we skip layer coherence in chunked mode
        pass

    # Process LM head and cross-entropy in chunks
    total_loss = torch.tensor(0.0, device=device)
    total_tokens = 0
    entropy_sum = torch.tensor(0.0, device=device)
    entropy_samples = 0

    for chunk_start in range(0, N, lm_head_chunk_size):
        chunk_end = min(chunk_start + lm_head_chunk_size, N)
        chunk_size = chunk_end - chunk_start

        # Extract chunk of hidden states
        hidden_chunk = hidden[:, chunk_start:chunk_end, :]  # (B, chunk_size, embed_dim)

        # Compute logits for this chunk only
        chunk_logits = model.lm_head(hidden_chunk)  # (B, chunk_size, V)

        # Get targets for this chunk
        chunk_targets = y[:, chunk_start:chunk_end]  # (B, chunk_size)

        # Compute cross-entropy for this chunk (fused, memory-efficient)
        B_chunk, N_chunk, V = chunk_logits.shape
        chunk_loss = F.cross_entropy(
            chunk_logits.view(B_chunk * N_chunk, V),
            chunk_targets.view(B_chunk * N_chunk),
            ignore_index=-100,
            reduction='sum'  # Sum, then normalize later
        )

        # Count valid tokens (not -100)
        valid_tokens = (chunk_targets != -100).sum()
        total_loss = total_loss + chunk_loss
        total_tokens += valid_tokens

        # Sample entropy from a subset of positions in this chunk
        if use_coherence_loss:
            # Use LogSumExp entropy on a sample of positions
            sample_size = min(256, N_chunk)
            if N_chunk > sample_size:
                sample_indices = torch.randperm(N_chunk, device=device)[:sample_size]
                sampled_logits = chunk_logits[:, sample_indices, :]
            else:
                sampled_logits = chunk_logits

            # LogSumExp entropy (no softmax!)
            lse = torch.logsumexp(sampled_logits, dim=-1)  # (B, sample_size)
            max_logits, _ = sampled_logits.max(dim=-1)
            chunk_entropy = (lse - max_logits).mean()

            entropy_sum = entropy_sum + chunk_entropy * sample_size
            entropy_samples += sample_size

        # Explicitly delete chunk tensors to free memory immediately
        del chunk_logits, hidden_chunk

    # Normalize loss by total tokens
    if total_tokens > 0:
        L_task = total_loss / total_tokens
    else:
        L_task = total_loss

    metrics = {
        "loss": L_task.item(),
        "perplexity": torch.exp(L_task).item(),
    }

    if use_coherence_loss:
        # Compute entropy from samples
        if entropy_samples > 0:
            entropy = entropy_sum / entropy_samples
        else:
            entropy = torch.tensor(ENTROPY_TARGET, device=device)

        # Use entropy tracker for update gate and stability (S5, S8-S9)
        L_entropy, update_gate, L_stability, entropy_metrics = _entropy_tracker.compute_coherence_terms(
            entropy, device
        )
        metrics.update(entropy_metrics)

        coherence_scale = 1.0 - update_gate

        # Skip layer coherence in chunked mode (would require re-running forward)
        metrics["coherence"] = 0.0

        # Combined loss
        loss = (L_task +
                lambda_entropy * L_entropy +
                lambda_stability * coherence_scale * L_stability)

        metrics["loss_total"] = loss.item()
    else:
        loss = L_task

    return loss, metrics


def train_step(
    model: PhaseTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    optimizer: AdamW,
    scheduler: LambdaLR,
    scaler: Optional[GradScaler],
    config: TrainingConfig,
    device: torch.device,
    accumulation_step: int,
) -> Dict[str, float]:
    """Single training step with gradient accumulation and coherence loss."""

    # Mixed precision context
    use_amp = config.mixed_precision != "none" and device.type == "cuda"
    dtype = torch.bfloat16 if config.mixed_precision == "bf16" else torch.float16

    # Forward pass with coherence loss (S3, S1-S2, S8-S9)
    with autocast(device_type='cuda', enabled=use_amp, dtype=dtype):
        # State-centric training: NO LM head, predict state deltas instead
        if config.loss_type == "state_delta":
            loss, metrics = compute_state_centric_loss(
                model, batch, device,
                lambda_delta=config.lambda_delta,
                lambda_entropy=config.lambda_entropy_state,
                lambda_constraint=config.lambda_constraint,
                target_entropy_rate=config.target_entropy_rate,
            )
            loss = loss / config.gradient_accumulation

            # Backward pass
            if scaler is not None:
                scaler.scale(loss).backward()
            else:
                loss.backward()
        # Use streaming chunked processing for ultra-long sequences
        elif config.chunk_size > 0:
            # Streaming mode: backward already done per-chunk, returns None for loss
            loss, metrics = compute_loss_streaming(
                model, batch, device,
                chunk_size=config.chunk_size,
                use_coherence_loss=config.use_coherence_loss,
                lambda_entropy=config.lambda_entropy,
                lambda_coherence=config.lambda_coherence,
                lambda_stability=config.lambda_stability,
            )
            # loss is None - gradients already accumulated in compute_loss_streaming
        else:
            loss, metrics = compute_loss(
                model, batch, device,
                use_coherence_loss=config.use_coherence_loss,
                lambda_entropy=config.lambda_entropy,
                lambda_coherence=config.lambda_coherence,
                lambda_stability=config.lambda_stability,
                loss_type=config.loss_type,
                num_negatives=config.num_negatives,
                contrastive_margin=config.contrastive_margin,
                contrastive_temperature=config.contrastive_temperature,
            )
            loss = loss / config.gradient_accumulation

            # Backward pass (only for non-chunked mode)
            if scaler is not None:
                scaler.scale(loss).backward()
            else:
                loss.backward()

    # Gradient step (after accumulation)
    if (accumulation_step + 1) % config.gradient_accumulation == 0:
        if scaler is not None:
            scaler.unscale_(optimizer)

        # V9.3: Apply Adaptive Gradient Clipping (before optimizer.step)
        # AGC clips based on grad_norm / weight_norm ratio per parameter
        agc_stats = None
        if config.trinity_enabled and config.agc_enabled:
            agc_stats = apply_agc(model, threshold=config.agc_threshold)
            metrics['agc_clipped'] = agc_stats['clipped_params']
            metrics['agc_max_ratio'] = agc_stats['max_ratio']
            metrics['agc_phase_ratio'] = agc_stats['phase_max_ratio']

        if scaler is not None:
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
        else:
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            optimizer.step()

        # Capture gradient norms BEFORE zeroing (for diagnostics)
        grad_stats = compute_tier_gradient_norms(model)
        metrics.update(grad_stats)

        # V9.4.5: Friction Monitor - Gradient Alignment between Quadratic and Phase layers
        # Detects when the two halves of the 6/6 hybrid model are "fighting"
        try:
            from train_pid import measure_friction
            fric_align, fric_dom = measure_friction(model, local_layers=6)
            metrics['friction_alignment'] = fric_align
            metrics['friction_dominance'] = fric_dom
        except ImportError:
            pass  # Friction monitor not available

        scheduler.step()
        optimizer.zero_grad()

    return metrics


@torch.no_grad()
def evaluate(
    model: PhaseTransformer,
    val_loader: DataLoader,
    config: TrainingConfig,
    device: torch.device,
) -> Dict[str, float]:
    """
    Evaluate model on validation set.

    For small validation sets (like WikiText-103 with only 7 batches),
    we use ALL available batches to maximize signal quality.
    The noise comes from the inherent size of the dataset, not our sampling.
    """
    model.eval()

    total_loss = 0.0
    total_tokens = 0
    num_batches = 0

    # Use ALL validation batches for maximum signal (don't limit with eval_samples)
    # Small val sets need every batch to reduce noise
    for batch in val_loader:
        loss, _ = compute_loss(model, batch, device)
        total_loss += loss.item()
        total_tokens += batch[0].numel()
        num_batches += 1

    avg_loss = total_loss / max(1, num_batches)
    perplexity = math.exp(avg_loss)

    model.train()

    return {
        "val_loss": avg_loss,
        "val_perplexity": perplexity,
        "val_tokens": total_tokens,
    }


@torch.no_grad()
def generate_sample(
    model: PhaseTransformer,
    tokenizer,
    prompt: str,
    device: torch.device,
    max_new_tokens: int = 50,
    temperature: float = 0.8,
    top_p: float = 0.9,
) -> str:
    """
    Generate text from a prompt for quality monitoring.

    Uses nucleus (top-p) sampling with temperature for diverse outputs.
    """
    model.eval()

    # Encode prompt
    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)

    # Generate tokens one by one
    generated = input_ids.clone()

    for _ in range(max_new_tokens):
        # Forward pass
        outputs = model(generated)

        # Handle different output formats
        if isinstance(outputs, dict):
            logits = outputs['logits']
        elif isinstance(outputs, torch.Tensor):
            logits = outputs
        else:
            logits = outputs[0]

        # Get next token logits
        next_logits = logits[:, -1, :] / temperature

        # Top-p (nucleus) sampling
        sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
        cumsum = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

        # Remove tokens with cumulative probability above threshold
        sorted_indices_to_remove = cumsum > top_p
        sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].clone()
        sorted_indices_to_remove[:, 0] = False

        # Set removed tokens to -inf
        indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
        next_logits[indices_to_remove] = float('-inf')

        # Sample
        probs = F.softmax(next_logits, dim=-1)
        next_token = torch.multinomial(probs, num_samples=1)

        # Append and check for EOS
        generated = torch.cat([generated, next_token], dim=1)

        # Stop on common end tokens
        if next_token.item() in [tokenizer.eos_token_id, tokenizer.encode('\n')[0]]:
            break

    # Decode only the generated part
    generated_text = tokenizer.decode(generated[0, input_ids.shape[1]:], skip_special_tokens=True)

    model.train()
    return generated_text


def run_quality_samples(
    model: PhaseTransformer,
    tokenizer,
    config: TrainingConfig,
    device: torch.device,
    step: int,
    logger,
):
    """
    Generate sample outputs to monitor training quality.

    This provides a qualitative check that the model is learning
    meaningful language patterns, not just minimizing perplexity.
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"  📝 QUALITY SAMPLES (Step {step})")
    logger.info("=" * 60)

    for prompt in config.sample_prompts:
        try:
            generated = generate_sample(
                model, tokenizer, prompt, device,
                max_new_tokens=50,
                temperature=0.8,
                top_p=0.9,
            )
            # Clean up and truncate for display
            generated = generated.strip().replace('\n', ' ')[:200]
            logger.info(f"  Prompt: \"{prompt}\"")
            logger.info(f"  Output: \"{generated}\"")
            logger.info("")
        except Exception as e:
            logger.warning(f"  Sampling failed for prompt '{prompt[:30]}...': {e}")

    logger.info("=" * 60)
    logger.info("")


def save_checkpoint(
    model: PhaseTransformer,
    optimizer: AdamW,
    scheduler: LambdaLR,
    scaler: Optional[GradScaler],
    state: TrainingState,
    config: TrainingConfig,
    path: str,
):
    """Save training checkpoint."""
    checkpoint = {
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "state": asdict(state),
        "config": asdict(config),
    }

    if scaler is not None:
        checkpoint["scaler"] = scaler.state_dict()

    torch.save(checkpoint, path)


def save_checkpoint_light(
    model: PhaseTransformer,
    state: TrainingState,
    config: TrainingConfig,
    path: str,
):
    """
    Save lightweight checkpoint (model only, no optimizer).

    Used for eval-interval checkpoints to save disk space.
    A 145M model saves ~550MB vs ~1.6GB with optimizer state.
    """
    checkpoint = {
        "model": model.state_dict(),
        "state": asdict(state),
        "config": asdict(config),
    }
    torch.save(checkpoint, path)


def cleanup_old_checkpoints(checkpoint_dir: Path, keep_last: int = 5):
    """
    Remove old step checkpoints, keeping only the last N.

    This prevents disk space exhaustion when saving at every eval interval.
    Handles both patterns: step_*.pt and checkpoint_step_*.pt
    Always preserves: best.pt, latest.pt, final.pt
    """
    import re

    # Find all step checkpoint files (both naming patterns)
    step_files = []
    for f in checkpoint_dir.glob("*step_*.pt"):
        # Match both: step_1000.pt and checkpoint_step_1000.pt
        match = re.search(r"step_(\d+)\.pt$", f.name)
        if match:
            step_num = int(match.group(1))
            step_files.append((step_num, f))

    # Sort by step number
    step_files.sort(key=lambda x: x[0])

    # Remove all but the last N
    if len(step_files) > keep_last:
        files_to_remove = step_files[:-keep_last]
        for step_num, filepath in files_to_remove:
            try:
                filepath.unlink()
            except OSError:
                pass  # Ignore errors (file might be in use)


def load_checkpoint(
    path: str,
    model: PhaseTransformer,
    optimizer: AdamW,
    scheduler: LambdaLR,
    scaler: Optional[GradScaler],
    device: torch.device,
    weights_only: bool = False,
) -> TrainingState:
    """Load training checkpoint.

    Args:
        weights_only: If True, only load model weights, skip optimizer/scheduler state.
                     Useful when resuming with different optimizer config (e.g., Lookahead).
    """
    checkpoint = torch.load(path, map_location=device)

    model.load_state_dict(checkpoint["model"])

    if not weights_only:
        try:
            optimizer.load_state_dict(checkpoint["optimizer"])
            scheduler.load_state_dict(checkpoint["scheduler"])
            if scaler is not None and "scaler" in checkpoint:
                scaler.load_state_dict(checkpoint["scaler"])
        except (KeyError, ValueError) as e:
            import logging
            logging.warning(f"Could not load optimizer/scheduler state: {e}. Starting fresh optimizer.")

    state = TrainingState(**checkpoint["state"])

    return state


# =============================================================================
# MAIN TRAINING LOOP
# =============================================================================

def train(config: TrainingConfig):
    """Main training function."""

    # Setup
    logger = setup_logging(config)

    # Device
    if config.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(config.device)

    logger.info(f"Using device: {device}")

    if device.type == "cuda":
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA version: {torch.version.cuda}")

    # Seed
    torch.manual_seed(config.seed)
    if device.type == "cuda":
        torch.cuda.manual_seed(config.seed)

    # Create directories
    checkpoint_dir = Path(config.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    config_path = checkpoint_dir / "config.json"
    with open(config_path, 'w') as f:
        json.dump(asdict(config), f, indent=2)
    logger.info(f"Config saved to {config_path}")

    # Create model
    logger.info(f"Creating {config.model_size} model...")
    model = create_model(config)
    model = model.to(device)

    num_params = count_parameters(model)
    logger.info(f"Model parameters: {num_params:,} ({num_params/1e6:.1f}M)")

    # torch.compile for 10-30% speedup (PyTorch 2.0+)
    if config.use_compile:
        try:
            logger.info(f"Compiling model with mode='{config.compile_mode}'...")
            model = torch.compile(model, mode=config.compile_mode)
            logger.info("Model compiled successfully")
        except Exception as e:
            logger.warning(f"torch.compile failed (requires PyTorch 2.0+): {e}")

    # Create optimizer and scheduler
    optimizer = create_optimizer(model, config)
    scheduler = create_scheduler(optimizer, config)

    # Mixed precision scaler
    scaler = None
    if config.mixed_precision == "fp16" and device.type == "cuda":
        scaler = GradScaler()
        logger.info("Using FP16 mixed precision with GradScaler")
    elif config.mixed_precision == "bf16" and device.type == "cuda":
        logger.info("Using BF16 mixed precision (native)")

    # Training state
    state = TrainingState()

    # Resume from checkpoint
    if config.resume:
        logger.info(f"Resuming from {config.resume}")
        state = load_checkpoint(
            config.resume, model, optimizer, scheduler, scaler, device,
            weights_only=config.resume_weights_only
        )
        if config.resume_weights_only:
            logger.info(f"Resumed model weights at step {state.step} (optimizer reset)")
        else:
            logger.info(f"Resumed at step {state.step}")

    # Create dataloaders
    logger.info("Loading dataset...")
    train_loader, val_loader, train_dataset = create_dataloaders(config)
    logger.info(f"Train batches: {len(train_loader):,}")

    # V9.2: Initialize MemoryGuard for dynamic batch scaling
    memory_guard = MemoryGuard(config, config.batch_size, config.gradient_accumulation)
    if config.memory_guard_enabled:
        logger.info(f"MemoryGuard ENABLED: target={config.vram_target_gb}GB, "
                    f"emergency={config.vram_emergency_gb}GB, crank@{config.crank_step}")

    # V9.3: Initialize Trinity components
    ppl_guard = None
    agc_threshold = config.agc_threshold
    handshake_triggered = False

    if config.trinity_enabled:
        logger.info("=" * 60)
        logger.info("V9.3 TRINITY OPTIMIZATION ENABLED")
        logger.info(f"  AGC: threshold={config.agc_threshold}")
        logger.info(f"  Lookahead: k={config.lookahead_k}, α={config.lookahead_alpha}")
        logger.info(f"  PPL-Guard: velocity_threshold={config.ppl_velocity_threshold}")
        logger.info(f"  Handshake Spike: {config.handshake_spike_factor}x LR at step {config.phase_delay_steps + 1}")
        if config.recovery_mode_enabled:
            logger.info(f"  V9.3.2 Recovery: cut={config.recovery_lr_cut_factor}x on PPL>{config.recovery_ppl_threshold*100:.0f}%, max_cuts={config.recovery_max_cuts}")
        logger.info(f"  V9.3.3 GATED: Freeze/Cut/Recovery disabled until step {config.alpha_warmup_steps}")
        logger.info(f"  V9.3.4 Authority LR: cap=0.3+0.7*α (30%→100% as α ramps)")
        logger.info("=" * 60)

        # Initialize PPL-Guard
        if config.ppl_guard_enabled:
            ppl_guard = PPLGuard(
                ppl_velocity_threshold=config.ppl_velocity_threshold,
                coherence_threshold=config.coherence_warning_threshold,
            )

    val_batches = len(val_loader)
    val_tokens = val_batches * config.batch_size * config.max_seq_len
    logger.info(f"Val batches: {val_batches:,} ({val_tokens/1000:.0f}K tokens)")
    if val_batches < 20:
        logger.warning(f"  ⚠️ Small validation set! Only {val_batches} batches - metrics will be noisy.")
        logger.warning(f"     Spike detection requires 2 consecutive regressions to reduce false alarms.")

    # Load tokenizer for quality sampling
    tokenizer = load_tokenizer(config) if config.sample_every > 0 else None

    # Wandb
    if config.wandb and WANDB_AVAILABLE:
        wandb.init(
            project=config.wandb_project,
            name=config.wandb_run or f"phase_{config.model_size}_{datetime.now().strftime('%Y%m%d_%H%M')}",
            config=asdict(config),
        )
        logger.info("Wandb initialized")

    # TensorBoard
    tb_writer = None
    if config.tensorboard and TENSORBOARD_AVAILABLE:
        tb_dir = checkpoint_dir / "tensorboard"
        tb_writer = SummaryWriter(tb_dir)
        logger.info(f"TensorBoard logging to {tb_dir}")

    # Training loop
    logger.info("=" * 60)
    logger.info("Starting training")
    if config.chunk_size > 0:
        num_chunks = (config.max_seq_len + config.chunk_size - 1) // config.chunk_size
        logger.info(f"CHUNKED MODE: {config.max_seq_len:,} tokens in {num_chunks} chunks of {config.chunk_size:,}")
    logger.info("=" * 60)

    model.train()
    train_iter = iter(train_loader)
    start_time = time.time()
    step_start_time = time.time()

    accumulation_step = 0
    running_loss = 0.0

    # Initialize lr_scale if not present (for backwards compatibility)
    if not hasattr(state, 'lr_scale'):
        state.lr_scale = 1.0

    while state.step < config.max_steps:
        # Get batch (handle epoch boundaries)
        try:
            batch = next(train_iter)
        except StopIteration:
            state.epoch += 1
            train_iter = iter(train_loader)
            batch = next(train_iter)

        # Training step
        metrics = train_step(
            model, batch, optimizer, scheduler, scaler,
            config, device, accumulation_step
        )

        # Apply persistent lr_scale after scheduler updates LR
        # V9.1 Two-Tier LLRD with DELAYED Phase LR + DYNAMIC CLUTCH:
        # - Stable/Local: normal LR from step 0
        # - Phase: frozen (LR=0) until phase_delay_steps, then ramps with stability brake
        base_lr = scheduler.get_last_lr()[0]

        # V9.1 Dynamic Clutch: Compute stability brake based on loss trend
        # If loss spikes > 2%, slow down Phase engagement
        if not hasattr(state, 'last_step_loss'):
            state.last_step_loss = metrics["loss"]
        loss_ratio = metrics["loss"] / max(state.last_step_loss, 1e-8)
        stability_brake = 0.5 if loss_ratio > 1.02 else 1.0
        state.last_step_loss = metrics["loss"]

        # Compute dynamic Phase LR multiplier (V9: delayed start + slow ramp)
        if state.step < config.phase_delay_steps:
            # Phase frozen - no weight updates
            phase_lr_mult = 0.0
            stability_brake = 1.0  # Not applicable during freeze
        else:
            # Ramp from 0 to phase_cooling_factor over phase_ramp_steps
            ramp_progress = min(1.0, (state.step - config.phase_delay_steps) / config.phase_ramp_steps)
            # Apply stability brake to slow engagement if loss is spiking
            phase_lr_mult = config.phase_cooling_factor * ramp_progress * stability_brake

        # V9.2: Combine state.lr_scale with memory_guard.lr_scale (crank multiplier)
        combined_lr_scale = state.lr_scale * memory_guard.lr_scale

        # V9.2.1: Enforce LR freeze if coherence dropped below threshold
        # Cap base_lr at frozen value to abort warmup
        if hasattr(state, 'lr_frozen') and state.lr_frozen and state.lr_frozen_value is not None:
            base_lr = min(base_lr, state.lr_frozen_value)

        # V9.3.1: Enforce Safety Brake - hold LR steady during PPL spike
        # Brake is softer than freeze - allows LR to drop but not increase
        if hasattr(state, 'lr_braked') and state.lr_braked and state.lr_brake_value is not None:
            base_lr = min(base_lr, state.lr_brake_value)

        # V9.3.4: Authority-weighted LR cap during alpha warmup
        # Don't inject full LR until Phase has sufficient authority to stabilize
        # This prevents "coupled-geometry overshoot" where Quad moves too fast for Phase
        if state.step < config.alpha_warmup_steps:
            # Compute current alpha (same formula as update_alpha_schedule)
            alpha_frac = state.step / config.alpha_warmup_steps
            current_alpha_for_cap = config.alpha_phase_start + alpha_frac * (config.alpha_phase_end - config.alpha_phase_start)

            # LR cap scales with alpha: at α=0 → 30% LR, at α=1 → 100% LR
            # This is "torque limiting during clutch engagement"
            authority_cap = 0.3 + 0.7 * current_alpha_for_cap

            # V9.3.5: Coherence OR PPL-Ratchet adjustment (whichever is worse)
            # Either signal being bad should cap LR - use min() for OR logic

            # Coherence factor (discrete thresholds per ChatGPT spec)
            current_coh = metrics.get('coherence', 1.0)
            if current_coh < 0.70:
                coh_factor = 0.8
            elif current_coh < 0.72:
                coh_factor = 0.9
            else:
                coh_factor = 1.0

            # Take minimum (most conservative) - OR logic
            # If coherence bad OR PPL rising → use the worse factor
            combined_factor = min(coh_factor, state.ppl_lr_factor)
            authority_cap *= combined_factor

            effective_lr_cap = config.learning_rate * authority_cap

            if base_lr > effective_lr_cap:
                base_lr = effective_lr_cap

        for param_group in optimizer.param_groups:
            group_name = param_group.get('name', '')
            # Three tiers: stable (1.0x), local_attn (1.0x), phase_attn (delayed ramp with clutch)
            if 'phase_attn' in group_name:
                # V9.2: Use MemoryGuard's phase LR with cap during crank
                param_group['lr'] = memory_guard.get_phase_lr(base_lr * state.lr_scale, phase_lr_mult)
            elif 'local_attn' in group_name:
                param_group['lr'] = base_lr * config.attn_cooling_factor * combined_lr_scale
            else:
                param_group['lr'] = base_lr * combined_lr_scale

        accumulation_step += 1
        running_loss += metrics["loss"]
        state.total_tokens += batch[0].numel()

        # Update step counter after gradient accumulation
        if accumulation_step % config.gradient_accumulation == 0:
            state.step += 1
            avg_loss = running_loss / config.gradient_accumulation
            state.train_losses.append(avg_loss)
            running_loss = 0.0

            # Update alpha schedule (decay from 0.6 to 0.4 for Phase Attention)
            current_alpha = update_alpha_schedule(model, state.step, config)

            # V9.3: Handshake Trigger at step phase_delay_steps + 1 (e.g., step 3001)
            # Rebuilds optimizer with WD exclusion, Lookahead, and Spike LR
            if (config.trinity_enabled and
                config.handshake_spike_enabled and
                not handshake_triggered and
                state.step == config.phase_delay_steps + 1):

                optimizer = trigger_handshake(model, config, optimizer, device, logger)
                handshake_triggered = True

                # Update scheduler reference if needed (Lookahead wraps the optimizer)
                # The LR is now managed by the new optimizer groups

            # V9.3: End Handshake Spike after duration (e.g., step 3500)
            # Drop LR back to normal levels
            if (config.trinity_enabled and
                handshake_triggered and
                state.step == config.phase_delay_steps + 1 + config.handshake_duration):

                # Reduce LR back from spike
                for param_group in optimizer.param_groups:
                    if 'phase' in param_group.get('name', ''):
                        param_group['lr'] = config.phase_lr_cap  # Back to 1e-5
                    else:
                        param_group['lr'] = config.learning_rate  # Back to 4e-5

                logger.info(f"🔧 [Step {state.step}] Handshake Spike ended - LR normalized")

            # V9.2: MemoryGuard check at configured interval
            if state.step % config.vram_check_interval == 0:
                changed, action = memory_guard.check_and_adjust(state.step, logger)
                if changed:
                    # Rebuild DataLoader with new batch size
                    # Track position: accumulation_step counts batches processed
                    memory_guard.update_data_position(accumulation_step)
                    train_loader = rebuild_train_loader(
                        train_dataset, config,
                        memory_guard.batch_size,
                        memory_guard.global_data_idx % len(train_dataset)
                    )
                    train_iter = iter(train_loader)
                    accumulation_step = 0
                    # Update config for logging (batch_size used in throughput calc)
                    config.batch_size = memory_guard.batch_size
                    config.gradient_accumulation = memory_guard.accum

            # Logging
            if state.step % config.log_every == 0:
                elapsed = time.time() - step_start_time
                tokens_per_sec = (config.log_every * config.batch_size * config.max_seq_len * config.gradient_accumulation) / elapsed
                base_lr = scheduler.get_last_lr()[0]

                # V9.3.2: Apply frozen LR cap for accurate logging
                if hasattr(state, 'lr_frozen') and state.lr_frozen and state.lr_frozen_value is not None:
                    base_lr = min(base_lr, state.lr_frozen_value)

                # V9.3.5: Apply authority-weighted LR cap with coherence OR PPL-Ratchet for logging
                if state.step < config.alpha_warmup_steps:
                    alpha_frac = state.step / config.alpha_warmup_steps
                    current_alpha_for_cap = config.alpha_phase_start + alpha_frac * (config.alpha_phase_end - config.alpha_phase_start)
                    authority_cap = 0.3 + 0.7 * current_alpha_for_cap

                    # V9.3.5: Coherence OR PPL-Ratchet - use min() for OR logic
                    current_coh_for_log = metrics.get('coherence', 1.0)
                    if current_coh_for_log < 0.70:
                        coh_factor = 0.8
                    elif current_coh_for_log < 0.72:
                        coh_factor = 0.9
                    else:
                        coh_factor = 1.0

                    combined_factor = min(coh_factor, state.ppl_lr_factor)
                    authority_cap *= combined_factor

                    effective_lr_cap = config.learning_rate * authority_cap
                    base_lr = min(base_lr, effective_lr_cap)

                # V9: Compute dynamic Phase LR for logging
                # V9.1: Recompute stability brake for logging
                if hasattr(state, 'last_step_loss') and state.step > 0:
                    loss_ratio = avg_loss / max(state.last_step_loss, 1e-8)
                    log_stability_brake = 0.5 if loss_ratio > 1.02 else 1.0
                else:
                    log_stability_brake = 1.0

                if state.step < config.phase_delay_steps:
                    phase_lr_mult = 0.0
                    phase_status = "FROZEN"
                else:
                    ramp_progress = min(1.0, (state.step - config.phase_delay_steps) / config.phase_ramp_steps)
                    phase_lr_mult = config.phase_cooling_factor * ramp_progress * log_stability_brake
                    if log_stability_brake < 1.0:
                        phase_status = f"{ramp_progress*100:.0f}%🔧"  # Clutch engaged
                    else:
                        phase_status = f"{ramp_progress*100:.0f}%"

                stable_lr = base_lr * state.lr_scale
                local_lr = stable_lr * config.attn_cooling_factor
                phase_lr = stable_lr * phase_lr_mult

                # Build log message with coherence metrics if available
                log_msg = (
                    f"Step {state.step:>6} | "
                    f"Loss: {avg_loss:.4f} | "
                    f"PPL: {math.exp(avg_loss):.2f} | "
                    f"LR: {stable_lr:.2e} | "
                    f"Tok/s: {tokens_per_sec:.0f}"
                )

                # Show lr_scale and tier LRs if not at defaults
                if state.lr_scale < 0.99:
                    log_msg += f" | LR_scale: {state.lr_scale:.2f}"
                # Show local/phase LRs (V9: Phase shows FROZEN or ramp %)
                log_msg += f" | Local: {local_lr:.1e} | Phase: {phase_lr:.1e} ({phase_status})"

                # Add coherence metrics if enabled (S3, S1-S2, S5)
                if config.use_coherence_loss and "entropy" in metrics:
                    ent_val = metrics.get('entropy', 0)
                    log_msg += f" | Ent: {ent_val:.2f}"
                    log_msg += f" | Coh: {metrics.get('coherence', 0):.3f}"

                    # Mode collapse warning: entropy dropping too low means model is
                    # getting stuck on predictable patterns instead of learning
                    if ent_val < 1.5:
                        log_msg += " ⚠️ LOW_ENT"
                    elif ent_val < 2.0:
                        log_msg += " (ent↓)"

                # Add GPU memory usage for scaling experiments
                if device.type == "cuda":
                    mem_used = torch.cuda.max_memory_allocated() / (1024**3)  # GB
                    log_msg += f" | VRAM: {mem_used:.1f}GB"

                # Add alpha phase value (shows decay progress)
                log_msg += f" | α_phase: {current_alpha:.2f}"

                # V9.3: Add GSS (Gradient Spike Score) when Trinity is enabled
                if config.trinity_enabled and 'agc_max_ratio' in metrics:
                    gss = metrics.get('agc_max_ratio', 0)
                    clipped = metrics.get('agc_clipped', 0)
                    if clipped > 0:
                        log_msg += f" | GSS: {gss:.3f}⚡{clipped}"
                    else:
                        log_msg += f" | GSS: {gss:.3f}"

                # V9.3.2/V9.3.3: Show intervention status
                if getattr(state, 'recovery_active', False):
                    log_msg += f" | 🔻RECOVERY(cuts={state.recovery_lr_cuts})"
                elif getattr(state, 'lr_frozen', False):
                    log_msg += " | 🧊FROZEN"
                elif state.step < config.alpha_warmup_steps:
                    # V9.3.3: Show that interventions are gated during alpha ramp
                    remaining = config.alpha_warmup_steps - state.step
                    log_msg += f" | 🔓GATED({remaining})"

                # V9.3.5: Show PPL-Ratchet factor when not at 1.0
                if state.ppl_lr_factor < 0.99:
                    log_msg += f" | 🎚️PPL-R: {state.ppl_lr_factor:.2f}"

                logger.info(log_msg)

                # Wandb logging
                if config.wandb and WANDB_AVAILABLE:
                    log_dict = {
                        "train/loss": avg_loss,
                        "train/perplexity": math.exp(avg_loss),
                        "train/learning_rate": stable_lr,
                        "train/local_attn_lr": local_lr,
                        "train/phase_attn_lr": phase_lr,
                        "train/lr_scale": state.lr_scale,
                        "train/ppl_lr_factor": state.ppl_lr_factor,  # V9.3.5
                        "train/tokens_per_sec": tokens_per_sec,
                        "train/total_tokens": state.total_tokens,
                        "train/epoch": state.epoch,
                        "train/alpha_phase": current_alpha,
                    }
                    # Add coherence metrics
                    if config.use_coherence_loss:
                        log_dict.update({
                            "train/entropy": metrics.get("entropy", 0),
                            "train/coherence": metrics.get("coherence", 0),
                            "train/entropy_change": metrics.get("entropy_change", 0),
                        })
                    wandb.log(log_dict, step=state.step)

                # TensorBoard logging
                if tb_writer is not None:
                    tb_writer.add_scalar("train/loss", avg_loss, state.step)
                    tb_writer.add_scalar("train/perplexity", math.exp(avg_loss), state.step)
                    tb_writer.add_scalar("train/learning_rate", stable_lr, state.step)
                    tb_writer.add_scalar("train/local_attn_lr", local_lr, state.step)
                    tb_writer.add_scalar("train/phase_attn_lr", phase_lr, state.step)
                    tb_writer.add_scalar("train/lr_scale", state.lr_scale, state.step)
                    tb_writer.add_scalar("train/ppl_lr_factor", state.ppl_lr_factor, state.step)  # V9.3.5
                    tb_writer.add_scalar("train/tokens_per_sec", tokens_per_sec, state.step)
                    # Add coherence metrics
                    if config.use_coherence_loss:
                        tb_writer.add_scalar("train/entropy", metrics.get("entropy", 0), state.step)
                        tb_writer.add_scalar("train/coherence", metrics.get("coherence", 0), state.step)

                # Note: step_start_time reset moved to after eval/checkpoint blocks
                # to exclude non-training time from throughput calculation

                # V9.2.1: Coherence-based LR freeze
                # V9.3.3: GATED until alpha_warmup_steps - during ramp, Coh drops are normal migration
                if config.coherence_freeze_enabled and config.use_coherence_loss:
                    current_coh = metrics.get('coherence', 1.0)

                    # Initialize freeze state if not present
                    if not hasattr(state, 'lr_frozen'):
                        state.lr_frozen = False
                        state.lr_frozen_at_step = None
                        state.lr_frozen_value = None

                    # V9.3.3: Only allow freeze AFTER alpha warmup complete
                    # During ramp (0-10000), Coh drops are coordinate drift, not divergence
                    interventions_enabled = state.step >= config.alpha_warmup_steps

                    # Check for freeze condition (only after alpha warmup)
                    if (interventions_enabled and
                        not state.lr_frozen and
                        current_coh < config.coherence_freeze_threshold):

                        # Freeze LR at current value
                        state.lr_frozen = True
                        state.lr_frozen_at_step = state.step
                        state.lr_frozen_value = stable_lr

                        logger.warning(
                            f"🧊 [Step {state.step}] LR FROZEN: Coherence {current_coh:.3f} < {config.coherence_freeze_threshold:.3f} threshold. "
                            f"LR locked at {stable_lr:.2e}"
                        )

                    # Warning when approaching threshold (logging only, no intervention)
                    elif (current_coh < config.coherence_warning_threshold and
                          state.step % 100 == 0):
                        gated_msg = " [GATED - interventions disabled during alpha ramp]" if not interventions_enabled else ""
                        logger.warning(
                            f"⚠️ [Step {state.step}] Coherence LOW: {current_coh:.3f} (freeze threshold: {config.coherence_freeze_threshold:.3f}){gated_msg}"
                        )

            # Evaluation
            if state.step % config.eval_every == 0:
                logger.info("Evaluating...")
                val_metrics = evaluate(model, val_loader, config, device)

                logger.info(
                    f"  Val Loss: {val_metrics['val_loss']:.4f} | "
                    f"Val PPL: {val_metrics['val_perplexity']:.2f}"
                )

                # =================================================================
                # V9.3.5: PPL-RATCHET LR CONTROL (Smoothed, Multi-Eval)
                # Use 3-eval moving average and velocity to detect "not improving".
                # With only 7 val batches, single evals are noisy - need smoothing.
                #
                # Trigger conditions (after 6 evals):
                #   - 3 consecutive PPL rises, OR
                #   - Positive velocity: mean(last 3) > mean(prev 3)
                #
                # Action: Gentle reduction with floor at 0.7
                # =================================================================
                current_val_ppl = val_metrics['val_perplexity']
                current_coh_eval = metrics.get('coherence', 1.0)

                # Track PPL and coherence history (keep last 10 for smoothing)
                state.val_ppl_history.append(current_val_ppl)
                if len(state.val_ppl_history) > 10:
                    state.val_ppl_history = state.val_ppl_history[-10:]

                state.coh_history.append(current_coh_eval)
                if len(state.coh_history) > 10:
                    state.coh_history = state.coh_history[-10:]

                # Need at least 6 evals for smoothed comparison
                # Also gate by α_phase >= 0.05 - don't penalize before Phase has signal
                alpha_frac = state.step / config.alpha_warmup_steps if config.alpha_warmup_steps > 0 else 1.0
                current_alpha = config.alpha_phase_start + alpha_frac * (config.alpha_phase_end - config.alpha_phase_start)

                if len(state.val_ppl_history) >= 6 and current_alpha >= 0.05:
                    # Compute 3-eval moving averages
                    ppl_ma3 = sum(state.val_ppl_history[-3:]) / 3  # Last 3
                    ppl_prev3 = sum(state.val_ppl_history[-6:-3]) / 3  # Previous 3
                    ppl_vel = ppl_ma3 - ppl_prev3  # Positive = worsening

                    # Check for 3 consecutive rises (very robust for noisy val)
                    h = state.val_ppl_history
                    three_consecutive_rises = (len(h) >= 3 and
                                               h[-1] > h[-2] > h[-3])

                    # Check for coherence rising over last 2 evals (for recovery)
                    ch = state.coh_history
                    coh_rising = (len(ch) >= 2 and ch[-1] > ch[-2])

                    old_factor = state.ppl_lr_factor

                    if three_consecutive_rises or ppl_vel > 50:
                        # PPL persistently worsening - reduce LR factor
                        # Gentle reduction: velocity-proportional with floor
                        if ppl_vel > 0:
                            # ppl_vel of 150 → full penalty (0.7), 50 → partial
                            reduction = min(0.3, ppl_vel / 500)  # Max 30% reduction
                            state.ppl_lr_factor = max(0.7, state.ppl_lr_factor - reduction)
                        else:
                            # 3 consecutive rises but negative velocity (edge case)
                            state.ppl_lr_factor = max(0.7, state.ppl_lr_factor * 0.9)

                        trigger = "3↑" if three_consecutive_rises else f"vel={ppl_vel:.0f}"
                        logger.warning(
                            f"📉 [Step {state.step}] PPL-RATCHET: {trigger} | "
                            f"MA3: {ppl_prev3:.1f} → {ppl_ma3:.1f} | "
                            f"LR factor: {old_factor:.2f} → {state.ppl_lr_factor:.2f}"
                        )

                    elif ppl_vel < -20 and coh_rising:
                        # Recovery: PPL improving AND coherence rising
                        state.ppl_lr_factor = min(1.0, state.ppl_lr_factor + 0.05)

                        if old_factor < 0.99:
                            logger.info(
                                f"📈 [Step {state.step}] PPL-RATCHET: Recovering (vel={ppl_vel:.0f}, coh↑) | "
                                f"MA3: {ppl_prev3:.1f} → {ppl_ma3:.1f} | "
                                f"LR factor: {old_factor:.2f} → {state.ppl_lr_factor:.2f}"
                            )

                # V9.3: PPL-Guard check - tighten AGC if PPL velocity + low coherence
                if config.trinity_enabled and ppl_guard is not None:
                    current_coh = metrics.get('coherence', 1.0)
                    triggered, new_agc_threshold = ppl_guard.check(
                        val_metrics['val_perplexity'],
                        current_coh,
                        state.step,
                        logger
                    )
                    if triggered:
                        agc_threshold = new_agc_threshold
                        # Update config for train_step
                        config.agc_threshold = new_agc_threshold

                        # V9.3.1: When PPL-Guard triggers, also reduce Lookahead alpha
                        # Lower alpha = trust slow weights more = smoother recovery
                        if config.lookahead_enabled and hasattr(optimizer, 'alpha'):
                            old_alpha = optimizer.alpha
                            optimizer.alpha = 0.3
                            logger.info(f"   Lookahead α: {old_alpha} → 0.3 for stability")

                    # V9.3 / V9.3.1: PPL-based LR intervention
                    # V9.3.3: GATED until alpha_warmup_steps - PPL rises during ramp are normal
                    # Two-tier response based on PPL velocity + coherence
                    interventions_enabled = state.step >= config.alpha_warmup_steps

                    if (ppl_guard.last_val_ppl is not None and
                        not getattr(state, 'lr_frozen', False)):

                        ppl_velocity = val_metrics['val_perplexity'] - ppl_guard.last_val_ppl

                        # V9.3.1 Tier 1: SAFETY BRAKE (PPL Δ > 200 + Coh < 0.700)
                        # V9.3.3: Only after alpha warmup
                        if interventions_enabled and ppl_velocity > 200 and current_coh < 0.700:
                            if not hasattr(state, 'lr_braked'):
                                state.lr_braked = False
                                state.lr_brake_value = None

                            if not state.lr_braked:
                                state.lr_braked = True
                                state.lr_brake_value = scheduler.get_last_lr()[0]
                                logger.warning(
                                    f"🛑 [Step {state.step}] SAFETY BRAKE: "
                                    f"Val PPL Δ={ppl_velocity:.0f} > 200 AND Coh={current_coh:.3f} < 0.700. "
                                    f"LR held at {state.lr_brake_value:.2e} until stabilization"
                                )

                        # V9.3 Tier 2: EMERGENCY FREEZE (PPL Δ > 500 + Coh < 0.700)
                        # V9.3.3: Only after alpha warmup
                        if interventions_enabled and ppl_velocity > 500 and current_coh < 0.700:
                            # Initialize freeze state if not present
                            if not hasattr(state, 'lr_frozen'):
                                state.lr_frozen = False
                                state.lr_frozen_at_step = None
                                state.lr_frozen_value = None

                            state.lr_frozen = True
                            state.lr_frozen_at_step = state.step
                            state.lr_frozen_value = scheduler.get_last_lr()[0]

                            logger.warning(
                                f"🧊🔥 [Step {state.step}] EMERGENCY LR FREEZE: "
                                f"Val PPL Δ={ppl_velocity:.0f} > 500 AND Coh={current_coh:.3f} < 0.700. "
                                f"LR locked at {state.lr_frozen_value:.2e}"
                            )

                # =================================================================
                # V9.3.2: RECOVERY MODE - Active LR reduction when frozen but degrading
                # If LR is frozen but PPL keeps rising, the frozen LR is still too high.
                # We actively cut LR by 50% each time PPL rises > 5% from freeze point.
                # Exit recovery when Coh > 0.720 AND PPL drops for 2 consecutive evals.
                # =================================================================
                if config.recovery_mode_enabled and getattr(state, 'lr_frozen', False):
                    current_ppl = val_metrics['val_perplexity']
                    current_coh = metrics.get('coherence', 1.0)

                    # Initialize recovery state if not present
                    if not hasattr(state, 'recovery_active'):
                        state.recovery_active = False
                        state.recovery_ppl_at_freeze = None
                        state.recovery_lr_cuts = 0
                        state.recovery_last_ppl = None
                        state.recovery_consecutive_drops = 0

                    # Record PPL at freeze point if not set
                    if state.recovery_ppl_at_freeze is None:
                        state.recovery_ppl_at_freeze = current_ppl
                        state.recovery_last_ppl = current_ppl
                        logger.info(f"📍 [Step {state.step}] Recovery baseline set: PPL={current_ppl:.2f}")

                    # Save previous PPL before any updates (fixes bug where cut check saw updated value)
                    previous_ppl = state.recovery_last_ppl

                    # Check for recovery exit conditions
                    if state.recovery_active:
                        if current_ppl < previous_ppl:
                            state.recovery_consecutive_drops += 1
                        else:
                            state.recovery_consecutive_drops = 0

                        # Exit recovery if coherence recovered AND PPL dropping steadily
                        if (current_coh > config.recovery_exit_coh and
                            state.recovery_consecutive_drops >= config.recovery_exit_ppl_drops):
                            state.recovery_active = False
                            logger.info(
                                f"✅ [Step {state.step}] RECOVERY EXIT: "
                                f"Coh={current_coh:.3f} > {config.recovery_exit_coh:.3f} AND "
                                f"{state.recovery_consecutive_drops} consecutive PPL drops. "
                                f"LR stabilized at {state.lr_frozen_value:.2e} after {state.recovery_lr_cuts} cuts"
                            )

                    # Check if we need to cut LR further (PPL still rising from baseline)
                    ppl_rise_ratio = (current_ppl - state.recovery_ppl_at_freeze) / state.recovery_ppl_at_freeze

                    # If PPL rose > threshold from baseline, cut LR
                    if ppl_rise_ratio > config.recovery_ppl_threshold:
                        if state.recovery_lr_cuts < config.recovery_max_cuts:
                            old_lr = state.lr_frozen_value
                            state.lr_frozen_value *= config.recovery_lr_cut_factor
                            state.recovery_lr_cuts += 1
                            state.recovery_active = True
                            state.recovery_ppl_at_freeze = current_ppl  # Reset baseline after cut
                            state.recovery_consecutive_drops = 0  # Reset drop counter

                            logger.warning(
                                f"🔻 [Step {state.step}] RECOVERY CUT #{state.recovery_lr_cuts}: "
                                f"PPL rose {ppl_rise_ratio*100:.1f}% > {config.recovery_ppl_threshold*100:.0f}% threshold. "
                                f"LR: {old_lr:.2e} → {state.lr_frozen_value:.2e} "
                                f"(Coh={current_coh:.3f}, baseline reset)"
                            )
                        elif not getattr(state, 'recovery_exhausted_logged', False):
                            state.recovery_exhausted_logged = True
                            logger.error(
                                f"❌ [Step {state.step}] RECOVERY EXHAUSTED: "
                                f"Max {config.recovery_max_cuts} LR cuts reached but PPL still rising. "
                                f"Consider V9.4 Elastic Handshake or restart from earlier checkpoint."
                            )

                    # Update last PPL for next iteration
                    state.recovery_last_ppl = current_ppl

                # Save lightweight checkpoint at every eval for backtracking support
                # Uses model-only saves (~550MB vs ~1.6GB) to prevent disk exhaustion
                eval_ckpt_path = checkpoint_dir / f"step_{state.step}.pt"
                if not eval_ckpt_path.exists():
                    save_checkpoint_light(
                        model, state, config,
                        str(eval_ckpt_path)
                    )
                    # Clean up old eval checkpoints, keep last 5 for backtracking
                    cleanup_old_checkpoints(checkpoint_dir, keep_last=5)

                # =================================================================
                # SPIKE DETECTION using LOSS DELTA (not PPL ratio)
                # Per ChatGPT's analysis: PPL ratios are too sensitive (exponential)
                # Loss deltas are more stable and require consecutive regressions
                # =================================================================

                # Initialize state variables (backwards compatibility)
                if not hasattr(state, 'best_loss'):
                    state.best_loss = float('inf')
                if not hasattr(state, 'best_ppl'):
                    state.best_ppl = float('inf')
                if not hasattr(state, 'spike_count'):
                    state.spike_count = 0
                if not hasattr(state, 'lr_scale'):
                    state.lr_scale = 1.0
                if not hasattr(state, 'consecutive_regressions'):
                    state.consecutive_regressions = 0
                if not hasattr(state, 'loss_history'):
                    state.loss_history = []

                current_loss = val_metrics['val_loss']
                current_ppl = val_metrics['val_perplexity']

                # Track loss history for trend detection
                state.loss_history.append(current_loss)
                if len(state.loss_history) > 10:
                    state.loss_history = state.loss_history[-10:]

                # Check for new best
                if current_loss < state.best_loss:
                    state.best_loss = current_loss
                    state.best_ppl = current_ppl
                    state.consecutive_regressions = 0  # Reset on improvement
                elif state.step >= config.alpha_warmup_steps:
                    # =================================================================
                    # V8 "LET IT COOK" STRATEGY:
                    # Control logic DISABLED during alpha warmup phase.
                    #
                    # During alpha fade-in (0→0.6), the loss landscape is shifting as
                    # Phase layers gradually take over from Quadratic layers. This
                    # causes normal "coordinate drift" jitter that looks like spikes.
                    #
                    # Intervening during this phase causes:
                    # - LR collapse (repeated 0.8x/0.85x scaling)
                    # - Momentum destruction (repeated resets)
                    # - Degenerate patterns ("ssssss", "the the the")
                    #
                    # After alpha is stable (step >= alpha_warmup_steps), control
                    # logic re-enables for genuine instability detection.
                    # =================================================================
                    #
                    # LOSS-BASED SPIKE DETECTION with CONSECUTIVE REGRESSION REQUIREMENT
                    # - Use absolute loss delta (not PPL ratio)
                    # - Require 2 consecutive regressions before backtracking
                    # - This prevents thrashing on validation noise
                    # =================================================================

                    MIN_LR_SCALE = 0.1
                    loss_delta = current_loss - state.best_loss

                    # Track consecutive regressions
                    if loss_delta > 0.05:  # Any significant regression
                        state.consecutive_regressions += 1
                    else:
                        state.consecutive_regressions = max(0, state.consecutive_regressions - 1)

                    # Only act after 2 consecutive regressions (prevents noise-triggered rollback)
                    if state.consecutive_regressions >= 2:
                        if loss_delta > 0.25:
                            # MAJOR SPIKE: loss increased by >0.25 for 2+ consecutive evals
                            state.spike_count += 1
                            old_scale = state.lr_scale
                            state.lr_scale = max(MIN_LR_SCALE, state.lr_scale * 0.8)

                            best_ckpt = checkpoint_dir / "best.pt"
                            if best_ckpt.exists():
                                logger.info(f"  🔄 MAJOR SPIKE! Backtracking to best checkpoint...")
                                ckpt = torch.load(best_ckpt, map_location=device, weights_only=False)
                                model.load_state_dict(ckpt['model'])

                            optimizer.state = collections.defaultdict(dict)
                            state.consecutive_regressions = 0  # Reset after action

                            logger.info(f"  🚨 MAJOR loss spike (Δ={loss_delta:.3f} > 0.25)! Backtrack + LR: {old_scale:.3f} → {state.lr_scale:.3f}")

                        elif loss_delta > 0.15:
                            # MODERATE SPIKE: loss increased by >0.15 for 2+ consecutive evals
                            state.spike_count += 1
                            old_scale = state.lr_scale
                            state.lr_scale = max(MIN_LR_SCALE, state.lr_scale * 0.85)

                            # Find oldest step checkpoint
                            backtrack_ckpt = None
                            for f in sorted(checkpoint_dir.glob("step_*.pt")):
                                backtrack_ckpt = f
                                break

                            if backtrack_ckpt and backtrack_ckpt.exists():
                                logger.info(f"  🔄 MODERATE SPIKE! Backtracking to {backtrack_ckpt.name}...")
                                ckpt = torch.load(backtrack_ckpt, map_location=device, weights_only=False)
                                model.load_state_dict(ckpt['model'])
                            elif (checkpoint_dir / "best.pt").exists():
                                logger.info(f"  🔄 MODERATE SPIKE! Backtracking to best checkpoint...")
                                ckpt = torch.load(checkpoint_dir / "best.pt", map_location=device, weights_only=False)
                                model.load_state_dict(ckpt['model'])

                            optimizer.state = collections.defaultdict(dict)
                            state.consecutive_regressions = 0

                            logger.info(f"  ⚠️ Loss spike (Δ={loss_delta:.3f} > 0.15)! Backtrack + LR: {old_scale:.3f} → {state.lr_scale:.3f}")

                    # =================================================================
                    # TREND-BASED GENTLE LR ADJUSTMENT (single regression warning)
                    # =================================================================
                    elif len(state.loss_history) >= 3:
                        # Initialize patience if not present
                        if not hasattr(state, 'trend_patience'):
                            state.trend_patience = 0

                        # Compute rate of change over last 3 evals (using LOSS, not PPL)
                        loss_delta_1 = state.loss_history[-1] - state.loss_history[-2]
                        loss_delta_2 = state.loss_history[-2] - state.loss_history[-3]

                        # Check if loss is increasing (positive deltas)
                        if loss_delta_1 > 0.02:  # Small threshold to ignore noise
                            # Is it accelerating?
                            is_accelerating = loss_delta_1 > (1.2 * loss_delta_2) and loss_delta_2 > 0

                            # Determine if this is a concerning trend
                            is_concerning = loss_delta_1 > 0.05 or is_accelerating

                            if is_concerning:
                                state.trend_patience += 1
                            else:
                                state.trend_patience = 0

                            # TWO-TIER RESPONSE based on patience
                            if state.trend_patience >= 2:
                                # AGGRESSIVE: Confirmed trend (2 consecutive bad evals)
                                old_scale = state.lr_scale
                                state.lr_scale = max(MIN_LR_SCALE, state.lr_scale * 0.92)
                                optimizer.state = collections.defaultdict(dict)

                                logger.info(
                                    f"  📈 Loss trend CONFIRMED: Δ=[{loss_delta_2:+.3f}, {loss_delta_1:+.3f}]. "
                                    f"LR: {old_scale:.3f} → {state.lr_scale:.3f} + momentum reset"
                                )
                                state.trend_patience = 0

                            elif state.trend_patience == 1:
                                # GENTLE: First warning, small nudge
                                old_scale = state.lr_scale
                                state.lr_scale = max(MIN_LR_SCALE, state.lr_scale * 0.98)

                                logger.info(
                                    f"  📊 Loss watching: Δ=[{loss_delta_2:+.3f}, {loss_delta_1:+.3f}]. "
                                    f"LR: {old_scale:.3f} → {state.lr_scale:.3f} (gentle)"
                                )
                        else:
                            # Loss stable or decreasing - reset patience
                            state.trend_patience = 0
                else:
                    # =================================================================
                    # ALPHA WARMUP PHASE: Observation only, no intervention
                    # During this phase, we just watch and log without taking action.
                    # The model is migrating from Quadratic to hybrid representation.
                    # =================================================================
                    loss_delta = current_loss - state.best_loss
                    steps_remaining = config.alpha_warmup_steps - state.step
                    if loss_delta > 0.15:
                        # Would have been a spike, but we're in observation mode
                        logger.info(
                            f"  🔍 [OBSERVE] Loss Δ={loss_delta:.3f} (would trigger control). "
                            f"Alpha warmup: {steps_remaining} steps remaining. Letting it cook..."
                        )

                # Track best
                if val_metrics['val_loss'] < state.best_val_loss:
                    state.best_val_loss = val_metrics['val_loss']
                    best_path = checkpoint_dir / "best.pt"
                    save_checkpoint(
                        model, optimizer, scheduler, scaler, state, config,
                        str(best_path)
                    )
                    logger.info(f"  New best! Saved to {best_path}")

                # Wandb logging
                if config.wandb and WANDB_AVAILABLE:
                    wandb.log({
                        "val/loss": val_metrics['val_loss'],
                        "val/perplexity": val_metrics['val_perplexity'],
                        "val/best_loss": state.best_val_loss,
                    }, step=state.step)

                # TensorBoard logging
                if tb_writer is not None:
                    tb_writer.add_scalar("val/loss", val_metrics['val_loss'], state.step)
                    tb_writer.add_scalar("val/perplexity", val_metrics['val_perplexity'], state.step)

            # Checkpointing
            if state.step % config.save_every == 0:
                ckpt_path = checkpoint_dir / f"step_{state.step}.pt"
                save_checkpoint(
                    model, optimizer, scheduler, scaler, state, config,
                    str(ckpt_path)
                )
                logger.info(f"Checkpoint saved to {ckpt_path}")

                # Also save as latest
                latest_path = checkpoint_dir / "latest.pt"
                save_checkpoint(
                    model, optimizer, scheduler, scaler, state, config,
                    str(latest_path)
                )

            # Quality sampling - generate text to monitor training progress
            if config.sample_every > 0 and state.step % config.sample_every == 0 and tokenizer is not None:
                run_quality_samples(model, tokenizer, config, device, state.step, logger)

            # Gradient health check - verify all tiers are learning
            # Uses gradient stats captured in train_step BEFORE optimizer.zero_grad()
            if config.sample_every > 0 and state.step % config.sample_every == 0:
                if 'stable_grad_norm' in metrics:
                    log_tier_gradients_from_metrics(metrics, state.step, logger)
                else:
                    logger.info(f"  📊 Gradient stats not available (check gradient_accumulation)")

            # Reset throughput timer AFTER eval/checkpoint to exclude their time
            if state.step % config.log_every == 0:
                step_start_time = time.time()

    # Final save
    final_path = checkpoint_dir / "final.pt"
    save_checkpoint(
        model, optimizer, scheduler, scaler, state, config,
        str(final_path)
    )

    # Summary
    total_time = time.time() - start_time
    logger.info("=" * 60)
    logger.info("Training Complete!")
    logger.info("=" * 60)
    logger.info(f"Total steps: {state.step:,}")
    logger.info(f"Total tokens: {state.total_tokens:,}")
    logger.info(f"Total time: {total_time/3600:.2f} hours")
    logger.info(f"Avg tokens/sec: {state.total_tokens/total_time:.0f}")
    logger.info(f"Best val loss: {state.best_val_loss:.4f}")
    logger.info(f"Best val PPL: {math.exp(state.best_val_loss):.2f}")
    logger.info(f"Final checkpoint: {final_path}")

    # Cleanup
    if config.wandb and WANDB_AVAILABLE:
        wandb.finish()

    if tb_writer is not None:
        tb_writer.close()

    return state


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> TrainingConfig:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Train SymbolU Phase Transformer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Model
    parser.add_argument("--model_size", type=str, default="small",
                       choices=["tiny", "small", "medium", "large", "xl", "7b"],
                       help="Model size preset")
    parser.add_argument("--model_type", type=str, default="phase",
                       choices=["phase", "hybrid"],
                       help="Model type: phase (pure O(n)) or hybrid (local + phase)")
    parser.add_argument("--vocab_size", type=int, default=50257,
                       help="Vocabulary size")
    parser.add_argument("--max_seq_len", type=int, default=1024,
                       help="Maximum sequence length")
    parser.add_argument("--dropout", type=float, default=0.1,
                       help="Dropout rate")

    # Phase parameters
    parser.add_argument("--sync_steps", type=int, default=3,
                       help="Phase synchronization steps")
    parser.add_argument("--sync_lr", type=float, default=0.1,
                       help="Phase synchronization learning rate")

    # Hybrid parameters (updated defaults for better long-range retrieval)
    parser.add_argument("--local_layers", type=int, default=6,
                       help="Number of early layers with local attention only (was 4, now 6)")
    parser.add_argument("--window_size", type=int, default=256,
                       help="Local attention window size (hybrid mode)")
    parser.add_argument("--local_backend", type=str, default="auto",
                       choices=["auto", "flash", "sdpa", "unfold"],
                       help="LocalAttention backend: flash (fastest), sdpa, unfold (fallback)")
    parser.add_argument("--alpha_local", type=float, default=0.4,
                       help="Weight for local attention in hybrid layers (was 0.8, now 0.4)")
    parser.add_argument("--alpha_phase", type=float, default=0.6,
                       help="Weight for phase attention in hybrid layers (was 0.2, now 0.6)")

    # Alpha FADE-IN schedule ("Training Wheels" for hybrid stability)
    parser.add_argument("--alpha_phase_start", type=float, default=0.0,
                       help="Initial alpha_phase (0.0 = phase OFF, training wheels)")
    parser.add_argument("--alpha_phase_end", type=float, default=0.6,
                       help="Final alpha_phase after fade-in")
    parser.add_argument("--alpha_warmup_steps", type=int, default=10000,
                       help="Steps to fade in phase attention (0→0.6)")

    # Training
    parser.add_argument("--batch_size", type=int, default=16,
                       help="Batch size per GPU")
    parser.add_argument("--gradient_accumulation", type=int, default=1,
                       help="Gradient accumulation steps")
    parser.add_argument("--max_steps", type=int, default=100000,
                       help="Maximum training steps")
    parser.add_argument("--warmup_steps", type=int, default=2000,
                       help="Learning rate warmup steps")

    # Optimizer
    parser.add_argument("--learning_rate", type=float, default=3e-4,
                       help="Peak learning rate")
    parser.add_argument("--weight_decay", type=float, default=0.1,
                       help="Weight decay")
    parser.add_argument("--max_grad_norm", type=float, default=1.0,
                       help="Gradient clipping norm")
    parser.add_argument("--attn_cooling_factor", type=float, default=1.0,
                       help="Local/Quadratic attention LR multiplier (1.0 = baseline, full LR)")
    parser.add_argument("--phase_cooling_factor", type=float, default=0.25,
                       help="Phase attention MAX LR multiplier (V9: 0.25x = 1e-5 at base 4e-5)")
    parser.add_argument("--phase_delay_steps", type=int, default=3000,
                       help="V9: Steps before Phase LR starts (frozen at 0)")
    parser.add_argument("--phase_ramp_steps", type=int, default=7000,
                       help="V9: Steps to ramp Phase LR from 0 to phase_cooling_factor")

    # V9.2: MemoryGuard - Dynamic batch scaling
    parser.add_argument("--memory_guard", action="store_true",
                       help="V9.2: Enable dynamic VRAM-based batch scaling")
    parser.add_argument("--vram_target_gb", type=float, default=72.0,
                       help="V9.2: Target VRAM usage in GB")
    parser.add_argument("--vram_emergency_gb", type=float, default=77.0,
                       help="V9.2: Emergency downshift threshold in GB")
    parser.add_argument("--vram_underutil_gb", type=float, default=55.0,
                       help="V9.2: VRAM below this triggers ramp-up")
    parser.add_argument("--vram_check_interval", type=int, default=100,
                       help="V9.2: Check VRAM every N steps")
    parser.add_argument("--min_batch_size", type=int, default=8,
                       help="V9.2: Minimum batch size floor")
    parser.add_argument("--max_batch_size", type=int, default=64,
                       help="V9.2: Maximum batch size ceiling")
    parser.add_argument("--crank_step", type=int, default=10000,
                       help="V9.2: Step after which ramp-up is allowed")
    parser.add_argument("--phase_lr_cap", type=float, default=1e-5,
                       help="V9.2: Maximum Phase LR during crank")

    # V9.2.1: Coherence-based LR freeze
    parser.add_argument("--no_coherence_freeze", action="store_true",
                       help="V9.2.1: Disable coherence-based LR freeze")
    parser.add_argument("--coherence_freeze_threshold", type=float, default=0.700,
                       help="V9.2.1: Freeze LR if coherence drops below this")
    parser.add_argument("--coherence_warning_threshold", type=float, default=0.750,
                       help="V9.2.1: Warn when coherence drops below this")

    # V9.3: Trinity Optimization
    parser.add_argument("--trinity", action="store_true",
                       help="V9.3: Enable Trinity optimization (AGC + Lookahead + PPL-Guard + Handshake)")
    parser.add_argument("--agc_threshold", type=float, default=0.01,
                       help="V9.3: AGC max grad/weight ratio threshold")
    parser.add_argument("--lookahead_k", type=int, default=5,
                       help="V9.3: Lookahead slow weight update interval")
    parser.add_argument("--lookahead_alpha", type=float, default=0.5,
                       help="V9.3: Lookahead interpolation factor")
    parser.add_argument("--ppl_velocity_threshold", type=float, default=50.0,
                       help="V9.3: PPL-Guard velocity threshold")
    parser.add_argument("--handshake_spike_factor", type=float, default=1.5,
                       help="V9.3: LR multiplier during handshake spike")
    parser.add_argument("--handshake_phase_lr", type=float, default=2e-5,
                       help="V9.3: Phase LR during handshake spike")
    parser.add_argument("--handshake_duration", type=int, default=500,
                       help="V9.3: Duration of handshake spike in steps")

    # V9.3.2: Recovery Mode
    parser.add_argument("--no_recovery_mode", action="store_true",
                       help="V9.3.2: Disable recovery mode (active LR cuts when frozen)")
    parser.add_argument("--recovery_ppl_threshold", type=float, default=0.05,
                       help="V9.3.2: PPL rise ratio that triggers LR cut (default: 5%%)")
    parser.add_argument("--recovery_lr_cut_factor", type=float, default=0.5,
                       help="V9.3.2: LR multiplier on each recovery cut (default: 0.5 = 50%% cut)")
    parser.add_argument("--recovery_max_cuts", type=int, default=3,
                       help="V9.3.2: Maximum number of LR cuts before giving up")

    # LR schedule
    parser.add_argument("--lr_scheduler", type=str, default="cosine",
                       choices=["cosine", "linear", "constant"],
                       help="Learning rate scheduler")
    parser.add_argument("--min_lr_ratio", type=float, default=0.1,
                       help="Minimum LR as ratio of peak")

    # Mixed precision
    parser.add_argument("--mixed_precision", type=str, default="bf16",
                       choices=["none", "fp16", "bf16"],
                       help="Mixed precision training")

    # Gradient checkpointing
    parser.add_argument("--gradient_checkpointing", action="store_true",
                       help="Enable gradient checkpointing (saves memory, slower)")

    # Chunked processing for ultra-long sequences
    parser.add_argument("--chunk_size", type=int, default=0,
                       help="Process sequence in chunks of this size (0=disabled). "
                            "Enables 10M+ token sequences on limited VRAM.")

    # Checkpointing
    parser.add_argument("--checkpoint_dir", type=str, default="checkpoints",
                       help="Checkpoint directory")
    parser.add_argument("--save_every", type=int, default=5000,
                       help="Save checkpoint every N steps")
    parser.add_argument("--eval_every", type=int, default=100,
                       help="Evaluate every N steps")
    parser.add_argument("--log_every", type=int, default=100,
                       help="Log every N steps")
    parser.add_argument("--sample_every", type=int, default=500,
                       help="Generate quality samples every N steps (0 = disabled)")

    # Dataset
    parser.add_argument("--dataset", type=str, default="wikitext2",
                       choices=["c4", "wikitext103", "wikitext2", "custom"],
                       help="Dataset to train on")
    parser.add_argument("--dataset_path", type=str, default=None,
                       help="Path to custom dataset")
    parser.add_argument("--tokenizer", type=str, default="gpt2",
                       choices=["gpt2", "tiktoken"],
                       help="Tokenizer to use")

    # Evaluation
    parser.add_argument("--eval_samples", type=int, default=256,
                       help="Max sequences to evaluate (256 = ~8 batches = 256K tokens)")

    # Logging
    parser.add_argument("--wandb", action="store_true",
                       help="Enable Wandb logging")
    parser.add_argument("--wandb_project", type=str, default="symbolu",
                       help="Wandb project name")
    parser.add_argument("--wandb_run", type=str, default=None,
                       help="Wandb run name")
    parser.add_argument("--tensorboard", action="store_true",
                       help="Enable TensorBoard logging")

    # Hardware
    parser.add_argument("--device", type=str, default="auto",
                       choices=["auto", "cuda", "cpu"],
                       help="Device to use")
    parser.add_argument("--num_workers", type=int, default=4,
                       help="DataLoader workers")

    # Performance
    parser.add_argument("--compile", action="store_true", dest="use_compile",
                       help="Use torch.compile for 10-30%% speedup (PyTorch 2.0+)")
    parser.add_argument("--compile_mode", type=str, default="reduce-overhead",
                       choices=["default", "reduce-overhead", "max-autotune"],
                       help="torch.compile mode: default, reduce-overhead (faster), max-autotune (best)")

    # Resume
    parser.add_argument("--resume", type=str, default=None,
                       help="Resume from checkpoint")
    parser.add_argument("--resume_weights_only", action="store_true",
                       help="Only load model weights, skip optimizer/scheduler state (useful after config changes)")

    # Coherence Loss (S3, S1-S2, S8-S9)
    parser.add_argument("--use_coherence_loss", action="store_true", default=True,
                       help="Enable coherence-enhanced training (S3, S1-S2, S8-S9)")
    parser.add_argument("--no_coherence_loss", action="store_false", dest="use_coherence_loss",
                       help="Disable coherence loss")
    parser.add_argument("--lambda_entropy", type=float, default=0.01,
                       help="S5: Semantic entropy weight")
    parser.add_argument("--lambda_coherence", type=float, default=0.01,
                       help="S1-S2: Layer coherence weight")
    parser.add_argument("--lambda_stability", type=float, default=0.001,
                       help="S8-S9: Stability constraint weight")

    # Loss Type (memory-efficient options for 1M+ context)
    parser.add_argument("--loss_type", type=str, default="cross_entropy",
                       choices=["cross_entropy", "contrastive", "infonce", "state_delta"],
                       help="Loss type: cross_entropy (fused), contrastive (hinge), infonce (NCE), state_delta (no LM head)")
    parser.add_argument("--num_negatives", type=int, default=1024,
                       help="Number of negative samples for contrastive losses")
    parser.add_argument("--contrastive_margin", type=float, default=1.0,
                       help="Margin for contrastive hinge loss")
    parser.add_argument("--contrastive_temperature", type=float, default=0.1,
                       help="Temperature for InfoNCE loss")

    # State-Centric Training (for 10M+ context - NO LM head required!)
    parser.add_argument("--lambda_delta", type=float, default=1.0,
                       help="Weight for state delta prediction loss (state_delta mode)")
    parser.add_argument("--lambda_entropy_state", type=float, default=0.1,
                       help="Weight for entropy change loss (state_delta mode)")
    parser.add_argument("--lambda_constraint", type=float, default=0.1,
                       help="Weight for constraint satisfaction loss (state_delta mode)")
    parser.add_argument("--target_entropy_rate", type=float, default=0.5,
                       help="Target rate of entropy change for state-centric training")

    # Chunked LM Head (for ultra-long contexts)
    parser.add_argument("--lm_head_chunk_size", type=int, default=0,
                       help="Chunk size for LM head processing. 0=disabled. "
                            "Recommended: 8192 for 1M context, 4096 for 5M context. "
                            "Enables training on sequences up to 5M+ tokens.")

    # Seed
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed")

    args = parser.parse_args()

    # V9.2: Map --memory_guard flag to memory_guard_enabled
    args.memory_guard_enabled = getattr(args, 'memory_guard', False)

    # V9.2.1: Map --no_coherence_freeze to coherence_freeze_enabled (inverted)
    args.coherence_freeze_enabled = not getattr(args, 'no_coherence_freeze', False)

    # V9.3: Map --trinity flag to trinity_enabled and set sub-flags
    args.trinity_enabled = getattr(args, 'trinity', False)
    if args.trinity_enabled:
        # When Trinity is enabled, enable all sub-components
        args.agc_enabled = True
        args.lookahead_enabled = True
        args.ppl_guard_enabled = True
        args.handshake_spike_enabled = True
    else:
        # Default sub-component states when Trinity is disabled
        args.agc_enabled = False
        args.lookahead_enabled = False
        args.ppl_guard_enabled = False
        args.handshake_spike_enabled = False

    # V9.3.2: Map --no_recovery_mode to recovery_mode_enabled (inverted)
    args.recovery_mode_enabled = not getattr(args, 'no_recovery_mode', False)

    # Remove CLI-only flags that don't exist in TrainingConfig
    args_dict = vars(args)
    for cli_only_arg in ['memory_guard', 'no_coherence_freeze', 'trinity', 'no_recovery_mode']:
        args_dict.pop(cli_only_arg, None)

    # Create config from args
    config = TrainingConfig(**args_dict)

    return config


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    config = parse_args()

    # Get estimated parameter count
    preset = MODEL_PRESETS.get(config.model_size, {})
    embed = preset.get("embed_dim", 512)
    layers = preset.get("num_layers", 8)
    ff = preset.get("ff_dim", 2048)
    est_params = (embed * config.vocab_size +  # Embeddings
                  layers * (4 * embed * embed + 2 * embed * ff) +  # Attention + FFN
                  embed * config.vocab_size)  # Output projection
    est_params_str = f"{est_params/1e9:.1f}B" if est_params > 1e9 else f"{est_params/1e6:.0f}M"

    print("\n" + "=" * 70)
    print("  SYMBOLU LLM TRAINING")
    print("  Phase Attention Transformer with O(n) Complexity")
    print("=" * 70)
    print(f"\n  Model: {config.model_size} (~{est_params_str} params)")
    print(f"  Dataset: {config.dataset}")
    print(f"  Max steps: {config.max_steps:,}")
    print(f"  Batch size: {config.batch_size} x {config.gradient_accumulation} accumulation")
    print(f"  Effective batch: {config.batch_size * config.gradient_accumulation * config.max_seq_len:,} tokens")
    print(f"  Learning rate: {config.learning_rate}")
    if config.attn_cooling_factor < 1.0:
        print(f"  LLRD Cooling: Attention @ {config.attn_cooling_factor}x ({config.learning_rate * config.attn_cooling_factor:.2e})")
    print(f"  Mixed precision: {config.mixed_precision}")
    print(f"  Loss type: {config.loss_type}", end="")
    if config.loss_type in ("contrastive", "infonce"):
        print(f" (num_neg={config.num_negatives})")
    elif config.loss_type == "state_delta":
        print(f" (NO LM HEAD - 65x memory savings!)")
        print(f"  State-centric training: λ_delta={config.lambda_delta}, λ_entropy={config.lambda_entropy_state}, λ_constraint={config.lambda_constraint}")
    else:
        print(" (fused)")
    if config.gradient_checkpointing:
        print(f"  Gradient checkpointing: ENABLED (saves memory)")
    if preset.get("use_gqa"):
        print(f"  Grouped Query Attention: {preset['num_heads']} heads, {preset.get('num_kv_heads', 8)} KV heads")
    print()

    try:
        train(config)
    except KeyboardInterrupt:
        print("\nTraining interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nTraining failed: {e}")
        raise
