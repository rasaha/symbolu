#!/usr/bin/env python3
"""
SymbolU V9.3.5-PID Training Script
===================================

Phase Attention Transformer with Authority PID Controller.

The PID controller replaces ad-hoc threshold-based authority management
with a proper control-theoretic approach:

- P (Proportional): Immediate response to current system stress
- I (Integral): Memory of accumulated stress over time
- D (Derivative): Anticipation of stress trends

The controller outputs a single Authority Factor A in [0.7, 1.0] that
modulates how aggressive training is allowed to be.

Key insight: "Authority is earned, not assumed"
- Fast systems (O(n^2) Quadratic, O(n) Phase) vote into authority
- Slow O(1) controller arbitrates based on evidence (Val PPL, Coherence)
- Trust is lost instantly (exp decay) but earned slowly (hysteretic recovery)

Usage:
------
python train_pid.py \
    --model_type hybrid \
    --model_size medium \
    --dataset wikitext103 \
    --learning_rate 4e-5 \
    --checkpoint_dir checkpoints_pid \
    --memory_guard \
    --trinity
"""

import os
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import sys
import math
import time
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torch.optim import AdamW
from torch.optim.lr_scheduler import LambdaLR
from torch.amp import autocast
from torch.cuda.amp import GradScaler

# Enable TF32 and cuDNN optimizations
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.benchmark = True

# SymbolU imports
from symbolu.phase_transformer import PhaseTransformer, HybridPhaseTransformer, TransformerConfig

# Import core components from existing train.py
from train import (
    TrainingConfig,
    TrainingState,
    MemoryGuard,
    Lookahead,
    PPLGuard,
    EntropyTracker,
    TextDataset,
    create_model,
    create_dataloaders,
    count_parameters,
    setup_logging,
    save_checkpoint,
    save_checkpoint_light,
    load_checkpoint,
    cleanup_old_checkpoints,
    evaluate,
    train_step,
    update_alpha_schedule,
    create_scheduler,
    trigger_handshake,
)

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


# =============================================================================
# AUTHORITY PID CONTROLLER
# =============================================================================

@dataclass
class AuthorityPIDConfig:
    """Configuration for the Authority PID Controller."""

    # Coherence band thresholds
    C_low: float = 0.70    # Below this = max coherence penalty
    C_high: float = 0.78   # Above this = no coherence penalty

    # PPL velocity processing
    V_dead: float = 30.0   # Deadband - ignore noise below this
    V_scale: float = 300.0 # Typical "bad" velocity for normalization

    # Error signal weights
    w_ppl: float = 0.65    # Weight for PPL velocity component
    w_coh: float = 0.35    # Weight for coherence component

    # PID gains (conservative for noisy validation)
    Kp: float = 0.20       # Proportional gain
    Ki: float = 0.03       # Integral gain (very slow)
    Kd: float = 0.12       # Derivative gain (predictive)

    # Integral anti-windup
    I_max: float = 10.0    # Maximum integral accumulation

    # Authority bounds
    A_min: float = 0.70    # Minimum authority factor (floor)
    A_max: float = 1.00    # Maximum authority factor (ceiling)

    # Recovery settings
    recovery_streak: int = 2        # Good evals needed before recovery
    recovery_step: float = 0.02     # Authority restoration per good eval
    recovery_e_threshold: float = 0.2  # Error must be below this for recovery


# =============================================================================
# EMERGENCY PD CONTROLLER (Alternative - More Aggressive)
# =============================================================================

@dataclass
class EmergencyPDConfig:
    """Configuration for Emergency PD Controller (no Integral term)."""

    # Coherence target (primary signal)
    target_coh: float = 0.76   # "Gold standard" coherence

    # PPL baseline for normalization
    base_ppl: float = 1080.0   # Starting PPL for velocity normalization

    # PD gains (VIOLENT for crisis response - high sensitivity)
    Kp: float = 2.5            # High sensitivity to coherence loss
    Kd: float = 0.5            # Sensitivity to PPL acceleration

    # Decay multiplier
    decay_factor: float = 1.2  # Multiplier in exp(-decay_factor * u)

    # Authority bounds (allow very hard cuts during crisis)
    A_min: float = 0.25        # Floor at 0.25x LR (violent defense)
    A_max: float = 1.00        # Maximum authority

    # Smoothing (optional but recommended)
    use_smoothing: bool = True  # Use MA3 for PPL velocity


class EmergencyPD:
    """
    Emergency PD Controller for Crisis Response.

    No Integral term = no windup risk during massive errors.
    Coherence as primary signal = more stable than PPL.
    Aggressive gains = fast response to divergence.

    Use this when the model is in crisis (PPL exploding, coherence tanking).
    """

    def __init__(self, config: EmergencyPDConfig = None):
        self.config = config or EmergencyPDConfig()

        # Controller state
        self.A = 1.0
        self.last_ppl = self.config.base_ppl
        self.last_coh = 0.80

        # History for smoothing
        self.ppl_history: List[float] = []
        self.coh_history: List[float] = []

        # Telemetry
        self.last_e_p = 0.0  # Coherence error
        self.last_e_d = 0.0  # PPL velocity error
        self.last_u = 0.0    # Control signal
        self.last_v = 0.0    # Raw PPL velocity

    def update(self, val_ppl: float, coherence: float) -> float:
        """
        Update authority factor based on current metrics.

        Args:
            val_ppl: Current validation perplexity
            coherence: Current coherence metric

        Returns:
            A: Updated authority factor
        """
        cfg = self.config

        # Track history
        self.ppl_history.append(val_ppl)
        self.coh_history.append(coherence)
        if len(self.ppl_history) > 10:
            self.ppl_history = self.ppl_history[-10:]
        if len(self.coh_history) > 10:
            self.coh_history = self.coh_history[-10:]

        # =====================================================================
        # PROPORTIONAL: Coherence Error (primary signal)
        # =====================================================================
        # If coh=0.65 and target=0.76, e_p = 0.11
        e_p = max(0, cfg.target_coh - coherence)
        self.last_e_p = e_p

        # =====================================================================
        # DERIVATIVE: PPL Velocity (brake signal)
        # =====================================================================
        if cfg.use_smoothing and len(self.ppl_history) >= 3:
            # MA3 smoothing for noisy validation
            if len(self.ppl_history) >= 6:
                ppl_ma3 = sum(self.ppl_history[-3:]) / 3
                ppl_prev3 = sum(self.ppl_history[-6:-3]) / 3
                v = ppl_ma3 - ppl_prev3
            else:
                # Not enough history, use simple delta
                v = val_ppl - self.last_ppl
        else:
            # Raw step-to-step velocity
            v = val_ppl - self.last_ppl

        self.last_v = v
        self.last_ppl = val_ppl

        # Normalize by base PPL for scale invariance
        e_d = max(0, v / cfg.base_ppl)
        self.last_e_d = e_d

        # =====================================================================
        # CONTROL SIGNAL (PD only, no I)
        # =====================================================================
        u = (cfg.Kp * e_p) + (cfg.Kd * e_d)
        self.last_u = u

        # =====================================================================
        # AUTHORITY UPDATE (Aggressive Exponential Decay)
        # =====================================================================
        self.A = math.exp(-cfg.decay_factor * u)
        self.A = max(cfg.A_min, min(cfg.A_max, self.A))

        # =====================================================================
        # RECOVERY (Simple: if both signals healthy, slowly restore)
        # =====================================================================
        if e_p < 0.02 and e_d < 0.01 and self.A < 0.95:
            # Both signals healthy, restore slowly
            self.A = min(cfg.A_max, self.A + 0.03)

        return self.A

    def get_status_icon(self) -> str:
        """Get status icon based on authority level."""
        if self.A > 0.90:
            return "🟢"  # Healthy
        elif self.A > 0.60:
            return "🟡"  # Braking
        else:
            return "🔴"  # Emergency

    def get_status_string(self) -> str:
        """Get formatted status string for logging."""
        icon = self.get_status_icon()
        status = ""
        if self.A < 0.60:
            status = " [EMERGENCY]"
        elif self.A < 0.90:
            status = " [BRAKING]"

        return (
            f"PD {icon} | A: {self.A:.3f} | "
            f"Coh_err: {self.last_e_p:.3f} | PPL_vel: {self.last_v:+.1f}{status}"
        )

    def get_detailed_status(self) -> str:
        """Get detailed telemetry for debugging."""
        return (
            f"  e_p={self.last_e_p:.4f} e_d={self.last_e_d:.4f} | "
            f"u={self.last_u:.4f}"
        )


# =============================================================================
# AUTHORITY PID v2 (Google's Control-Systems Architecture)
# =============================================================================

@dataclass
class AuthorityPIDv2Config:
    """
    Configuration for Authority PID v2 - Clean Control-Systems Design.

    Key insight from Google:
    - PPL velocity is the PRIMARY PID signal (causal, monotonic, continuous)
    - Coherence is ONLY a supervisory gate (not in PID math)
    - Final authority = min(coh_gate, ppl_pid_factor) -- OR logic
    """

    # PPL velocity processing (PRIMARY PID SIGNAL)
    V_dead: float = 20.0     # Deadband - ignore noise below this
    V_scale: float = 200.0   # Normalization scale for velocity
    base_ppl: float = 1000.0 # Reference PPL for scale invariance

    # PID gains on PPL velocity
    Kp: float = 0.25         # Proportional: current velocity stress
    Ki: float = 0.02         # Integral: accumulated velocity stress
    Kd: float = 0.15         # Derivative: velocity acceleration

    # Integral anti-windup
    I_max: float = 5.0       # Maximum integral accumulation

    # Coherence gate (SUPERVISORY ONLY - not in PID)
    C_floor: float = 0.68    # Below this = minimum gate (0.5)
    C_good: float = 0.76     # Above this = full gate (1.0)
    gate_min: float = 0.5    # Minimum coherence gate value

    # Authority bounds
    A_min: float = 0.30      # Floor (allows aggressive cuts)
    A_max: float = 1.00      # Ceiling

    # Recovery settings
    recovery_streak: int = 3       # Good evals before recovery
    recovery_step: float = 0.02    # Restoration per good eval


class AuthorityPIDv2:
    """
    PID v2: Clean Control-Systems Architecture (per Google's recommendation).

    Key principles:
    1. PPL velocity is the ONLY PID input (causal, monotonic)
    2. Coherence is a supervisory gate (not in PID math)
    3. Final: authority = min(coh_gate, ppl_pid_factor)

    Why this is better:
    - PPL velocity directly measures divergence rate
    - Coherence is non-monotonic (can drop during correct learning)
    - PID requires causal signals; LR→PPL is direct, LR→Coh is indirect
    """

    def __init__(self, config: AuthorityPIDv2Config = None):
        self.config = config or AuthorityPIDv2Config()

        # PID state (on PPL velocity)
        self.A_ppl = 1.0       # Authority from PID loop
        self.I = 0.0           # Integral accumulator
        self.v_prev = 0.0      # Previous velocity (for D term)
        self.good_streak = 0   # Consecutive good evals

        # History for smoothing
        self.ppl_history: List[float] = []
        self.coh_history: List[float] = []

        # Final combined authority
        self.A = 1.0

        # Telemetry
        self.last_v = 0.0      # PPL velocity
        self.last_v_norm = 0.0 # Normalized velocity
        self.last_a = 0.0      # Acceleration
        self.last_P = 0.0
        self.last_I = 0.0
        self.last_D = 0.0
        self.last_u = 0.0
        self.last_coh_gate = 1.0
        self.last_e_p = 0.0    # For compatibility

    def update(self, val_ppl: float, coherence: float) -> float:
        """
        Update authority factor using PPL-primary PID with coherence gate.
        """
        cfg = self.config

        # Track history
        self.ppl_history.append(val_ppl)
        self.coh_history.append(coherence)
        if len(self.ppl_history) > 10:
            self.ppl_history = self.ppl_history[-10:]
        if len(self.coh_history) > 10:
            self.coh_history = self.coh_history[-10:]

        # Need at least 6 evals for MA3 smoothing
        if len(self.ppl_history) < 6:
            return self.A

        # =====================================================================
        # PRIMARY PID LOOP: PPL VELOCITY (Percentage-based for scale invariance)
        # =====================================================================

        # MA3 smoothed velocity as PERCENTAGE change
        ppl_ma3 = sum(self.ppl_history[-3:]) / 3
        ppl_prev3 = sum(self.ppl_history[-6:-3]) / 3
        v_pct = (ppl_ma3 - ppl_prev3) / ppl_prev3 * 100  # % change
        self.last_v = v_pct  # Now in percentage units

        # Normalize: 5% velocity increase = 1.0 error unit
        # Deadband at 1% to ignore noise
        if v_pct <= 1.0:  # 1% deadband
            v_norm = 0.0
        else:
            v_norm = min(1.0, (v_pct - 1.0) / 5.0)  # 5% scale
        self.last_v_norm = v_norm

        # Acceleration (derivative of velocity in % units)
        a = v_pct - self.v_prev
        self.v_prev = v_pct
        self.last_a = a

        # ----- P term: Current velocity stress -----
        P = v_norm
        self.last_P = P

        # ----- I term: Accumulated velocity stress (with anti-windup) -----
        self.I = max(0.0, min(cfg.I_max, self.I + v_norm))
        self.last_I = self.I

        # ----- D term: Velocity acceleration (predictive) -----
        # Positive acceleration = situation getting worse faster
        # Normalize: 5% acceleration = 1.0 D term
        D = max(0, a / 5.0)
        self.last_D = D

        # ----- Control signal -----
        u = cfg.Kp * P + cfg.Ki * self.I + cfg.Kd * D
        self.last_u = u

        # ----- PID Authority Factor -----
        # Exponential decay based on control signal
        self.A_ppl = math.exp(-u)
        self.A_ppl = max(cfg.A_min, min(cfg.A_max, self.A_ppl))

        # =====================================================================
        # SUPERVISORY GATE: COHERENCE (NOT in PID math)
        # =====================================================================

        # Simple linear interpolation for coherence gate
        if coherence >= cfg.C_good:
            coh_gate = 1.0
        elif coherence <= cfg.C_floor:
            coh_gate = cfg.gate_min
        else:
            # Linear interpolation between floor and good
            coh_gate = cfg.gate_min + (1.0 - cfg.gate_min) * (
                (coherence - cfg.C_floor) / (cfg.C_good - cfg.C_floor)
            )
        self.last_coh_gate = coh_gate
        self.last_e_p = max(0, cfg.C_good - coherence)  # For compatibility

        # =====================================================================
        # COMBINE: OR logic with min()
        # =====================================================================
        # Either bad PPL OR bad coherence triggers reduction
        self.A = min(coh_gate, self.A_ppl)

        # =====================================================================
        # RECOVERY (Both signals must be healthy)
        # =====================================================================
        ppl_healthy = v_pct < -2.0 and v_norm == 0  # PPL dropping >2%, no stress
        coh_healthy = coherence > cfg.C_good

        if ppl_healthy and coh_healthy:
            self.good_streak += 1
            # Slowly restore integral
            self.I = max(0.0, self.I - 0.1)
        else:
            self.good_streak = 0

        # Restore authority if streak is good
        if self.good_streak >= cfg.recovery_streak and self.A < 0.95:
            self.A = min(cfg.A_max, self.A + cfg.recovery_step)

        return self.A

    def get_status_icon(self) -> str:
        if self.A > 0.85:
            return "🟢"
        elif self.A > 0.50:
            return "🟡"
        else:
            return "🔴"

    def get_status_string(self) -> str:
        icon = self.get_status_icon()
        recovery_tag = " [RECOVERING]" if self.good_streak >= 1 else ""
        # Show which signal is limiting: the one with lower value
        limiter = "PPL" if self.A_ppl <= self.last_coh_gate else "COH"
        return (
            f"GOV {icon} | Brake(PPL): {self.A_ppl:.2f} | Gate(Coh): {self.last_coh_gate:.2f} | "
            f"Final_A: {self.A:.2f} [{limiter}] | vel: {self.last_v:+.1f}%{recovery_tag}"
        )

    def get_detailed_status(self) -> str:
        return (
            f"  v_norm={self.last_v_norm:.3f} a={self.last_a:+.1f} | "
            f"P={self.last_P:.3f} I={self.last_I:.3f} D={self.last_D:.3f} | "
            f"u={self.last_u:.3f}"
        )


class AuthorityPID:
    """
    PID-based Authority Controller for Phase Attention Training.

    NOTE: This is the original v1 implementation that mixes coherence into PID.
    Prefer AuthorityPIDv2 which follows proper control-systems architecture.

    This controller operates on the evaluation cadence (every 100 steps),
    providing slow, bounded adjustments to the authority cap based on
    system health metrics (Val PPL velocity and Coherence).

    The controller outputs a single scalar A in [A_min, 1.0] that modulates
    the effective authority cap:

        effective_cap = base_cap * A

    where base_cap = 0.3 + 0.7 * alpha_phase
    """

    def __init__(self, config: AuthorityPIDConfig = None):
        self.config = config or AuthorityPIDConfig()

        # Controller state
        self.A = 1.0           # Current authority factor
        self.I = 0.0           # Integral accumulator
        self.e_prev = 0.0      # Previous error (for derivative)
        self.good_streak = 0   # Consecutive "good" evaluations

        # History for smoothing
        self.ppl_history: List[float] = []
        self.coh_history: List[float] = []

        # Telemetry (for logging)
        self.last_e = 0.0      # Last error signal
        self.last_e_p = 0.0    # Last PPL error component
        self.last_e_c = 0.0    # Last coherence error component
        self.last_v = 0.0      # Last PPL velocity
        self.last_P = 0.0      # Last P term
        self.last_I = 0.0      # Last I term
        self.last_D = 0.0      # Last D term
        self.last_u = 0.0      # Last control signal

    def update(self, val_ppl: float, coherence: float) -> float:
        """
        Update the authority factor based on current metrics.

        Args:
            val_ppl: Current validation perplexity
            coherence: Current coherence metric

        Returns:
            A: Updated authority factor in [A_min, 1.0]
        """
        cfg = self.config

        # Track history
        self.ppl_history.append(val_ppl)
        self.coh_history.append(coherence)

        # Keep last 10 for smoothing
        if len(self.ppl_history) > 10:
            self.ppl_history = self.ppl_history[-10:]
        if len(self.coh_history) > 10:
            self.coh_history = self.coh_history[-10:]

        # Need at least 6 evals for smoothed comparison
        if len(self.ppl_history) < 6:
            return self.A

        # =====================================================================
        # COMPUTE ERROR SIGNALS
        # =====================================================================

        # PPL velocity: MA3 vs prev MA3
        ppl_ma3 = sum(self.ppl_history[-3:]) / 3
        ppl_prev3 = sum(self.ppl_history[-6:-3]) / 3
        v = ppl_ma3 - ppl_prev3  # Positive = worsening
        self.last_v = v

        # PPL error: normalize velocity with deadband
        if v <= cfg.V_dead:
            e_p = 0.0
        else:
            e_p = min(1.0, (v - cfg.V_dead) / cfg.V_scale)
        self.last_e_p = e_p

        # Coherence error: linear interpolation in band
        if coherence >= cfg.C_high:
            e_c = 0.0
        elif coherence <= cfg.C_low:
            e_c = 1.0
        else:
            e_c = (cfg.C_high - coherence) / (cfg.C_high - cfg.C_low)
        self.last_e_c = e_c

        # Combined error (weighted sum)
        e = cfg.w_ppl * e_p + cfg.w_coh * e_c
        self.last_e = e

        # =====================================================================
        # PID CONTROLLER
        # =====================================================================

        # Proportional
        P = e
        self.last_P = P

        # Integral with anti-windup
        self.I = max(0.0, min(cfg.I_max, self.I + e))
        self.last_I = self.I

        # Derivative
        D = e - self.e_prev
        self.e_prev = e
        self.last_D = D

        # Control signal
        u = cfg.Kp * P + cfg.Ki * self.I + cfg.Kd * D
        self.last_u = u

        # =====================================================================
        # AUTHORITY UPDATE (Multiplicative Decay)
        # =====================================================================

        # Apply exponential decay: higher u = more authority reduction
        self.A = max(cfg.A_min, min(cfg.A_max, self.A * math.exp(-u)))

        # =====================================================================
        # RECOVERY GATE (Hysteretic)
        # =====================================================================

        # Check for recovery conditions
        coh_rising = (len(self.coh_history) >= 2 and
                      self.coh_history[-1] > self.coh_history[-2])

        if v < -20 and coherence > cfg.C_low and e < cfg.recovery_e_threshold:
            self.good_streak += 1
        else:
            self.good_streak = 0

        # Restore authority slowly if conditions are met
        if self.good_streak >= cfg.recovery_streak and coh_rising:
            self.A = min(cfg.A_max, self.A + cfg.recovery_step)

        return self.A

    def get_status_icon(self) -> str:
        """Get status icon based on current pressure."""
        if self.last_e < 0.2:
            return "🟢"  # Healthy
        elif self.last_e < 0.5:
            return "🟡"  # Friction
        else:
            return "🔴"  # Crisis

    def get_status_string(self) -> str:
        """Get formatted status string for logging."""
        icon = self.get_status_icon()
        recovery_tag = " [RECOVERING]" if self.good_streak >= 1 else ""

        return (
            f"PID {icon} | Pressure: {self.last_e:.3f} | A: {self.A:.3f} | "
            f"PPL_vel: {self.last_v:+.1f} | Streak: {self.good_streak}{recovery_tag}"
        )

    def get_detailed_status(self) -> str:
        """Get detailed PID telemetry for debugging."""
        return (
            f"  e_ppl={self.last_e_p:.3f} e_coh={self.last_e_c:.3f} | "
            f"P={self.last_P:.3f} I={self.last_I:.3f} D={self.last_D:.3f} | "
            f"u={self.last_u:.3f}"
        )


# =============================================================================
# PID-ENABLED OPTIMIZER CREATION
# =============================================================================

def create_optimizer_with_groups(model: nn.Module, config: TrainingConfig) -> AdamW:
    """
    Create AdamW optimizer with three-tier LLRD (Layer-wise Learning Rate Decay).

    Groups:
    - Stable: MLP, embeddings, norms (1.0x LR)
    - Local Attention: Q, K, V projections for local attention (attn_cooling_factor x LR)
    - Phase Attention: Phase attention parameters (phase_cooling_factor x LR)
    """
    # Separate parameters into groups
    stable_params = []
    local_attn_params = []
    phase_attn_params = []

    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue

        if 'phase_attn' in name or 'phase_attention' in name:
            phase_attn_params.append(param)
        elif 'local_attn' in name or 'local_attention' in name or 'attn' in name:
            local_attn_params.append(param)
        else:
            stable_params.append(param)

    param_groups = [
        {
            'params': stable_params,
            'lr': config.learning_rate,
            'name': 'stable'
        },
        {
            'params': local_attn_params,
            'lr': config.learning_rate * config.attn_cooling_factor,
            'name': 'local_attn'
        },
        {
            'params': phase_attn_params,
            'lr': config.learning_rate * config.phase_cooling_factor,
            'name': 'phase_attn'
        }
    ]

    # Filter empty groups
    param_groups = [g for g in param_groups if len(g['params']) > 0]

    optimizer = AdamW(
        param_groups,
        lr=config.learning_rate,
        betas=(config.beta1, config.beta2),
        eps=config.eps,
        weight_decay=config.weight_decay
    )

    return optimizer


# =============================================================================
# MAIN TRAINING FUNCTION WITH PID
# =============================================================================

def train_with_pid(config: TrainingConfig, controller_type: str = "pidv2",
                   pd_config: EmergencyPDConfig = None,
                   pid_config: AuthorityPIDConfig = None,
                   pidv2_config: AuthorityPIDv2Config = None):
    """Main training function with Authority Controller (PIDv2, PID, or Emergency PD)."""

    # Setup logging
    logger = setup_logging(config)

    # Device setup
    if config.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(config.device)

    logger.info(f"Using device: {device}")
    if device.type == "cuda":
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA version: {torch.version.cuda}")

    # Seed for reproducibility
    torch.manual_seed(config.seed)
    if device.type == "cuda":
        torch.cuda.manual_seed(config.seed)

    # Create checkpoint directory
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

    # Create optimizer with LLRD groups
    optimizer = create_optimizer_with_groups(model, config)

    # Log optimizer groups
    logger.info("Two-Tier LLRD Optimizer Groups:")
    for group in optimizer.param_groups:
        name = group.get('name', 'unnamed')
        num_params = sum(p.numel() for p in group['params'])
        lr = group['lr']
        logger.info(f"  {name}: {num_params/1e6:.1f}M params @ LR {lr:.2e}")

    # Wrap with Lookahead if enabled
    if config.trinity_enabled and config.lookahead_enabled:
        optimizer = Lookahead(optimizer, k=config.lookahead_k, alpha=config.lookahead_alpha)
        logger.info(f"Lookahead enabled: k={config.lookahead_k}, alpha={config.lookahead_alpha}")

    # Create scheduler
    scheduler = create_scheduler(optimizer, config)

    # Mixed precision scaler
    scaler = None
    if config.mixed_precision == "fp16" and device.type == "cuda":
        scaler = GradScaler()
        logger.info("Using FP16 mixed precision with GradScaler")
    elif config.mixed_precision == "bf16" and device.type == "cuda":
        logger.info("Using BF16 mixed precision (native)")

    # Initialize training state
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

    # Initialize MemoryGuard
    memory_guard = MemoryGuard(config, config.batch_size, config.gradient_accumulation)
    if config.memory_guard_enabled:
        logger.info(f"MemoryGuard ENABLED: target={config.vram_target_gb}GB")

    # Initialize PPL-Guard
    ppl_guard = None
    if config.trinity_enabled and config.ppl_guard_enabled:
        ppl_guard = PPLGuard(config.ppl_velocity_threshold)

    # =========================================================================
    # INITIALIZE AUTHORITY CONTROLLER (PIDv2, PID legacy, or Emergency PD)
    # =========================================================================
    if controller_type == "emergency_pd":
        # Emergency PD mode - more aggressive, no Integral term
        if pd_config is None:
            pd_config = EmergencyPDConfig()
        authority_controller = EmergencyPD(pd_config)
        controller_name = "EMERGENCY PD"

        logger.info("=" * 60)
        logger.info("V9.3.6: EMERGENCY PD CONTROLLER ENABLED")
        logger.info(f"  Gains: Kp={pd_config.Kp} (Coh), Kd={pd_config.Kd} (PPL vel)")
        logger.info(f"  Target coherence: {pd_config.target_coh}")
        logger.info(f"  Base PPL: {pd_config.base_ppl}")
        logger.info(f"  Decay factor: {pd_config.decay_factor}")
        logger.info(f"  Authority floor: {pd_config.A_min}")
        logger.info("  Mode: AGGRESSIVE (no Integral, coherence-primary)")
        logger.info("=" * 60)

    elif controller_type == "pidv2":
        # PIDv2 mode - Clean control-systems architecture (RECOMMENDED)
        if pidv2_config is None:
            pidv2_config = AuthorityPIDv2Config()
        authority_controller = AuthorityPIDv2(pidv2_config)
        controller_name = "PIDv2"

        logger.info("=" * 60)
        logger.info("V9.4.0: PIDv2 CONTROLLER (Control-Systems Design)")
        logger.info("  Architecture: PPL velocity drives PID; Coherence gates authority")
        logger.info(f"  PID Gains: Kp={pidv2_config.Kp}, Ki={pidv2_config.Ki}, Kd={pidv2_config.Kd}")
        logger.info(f"  Coherence gate: [{pidv2_config.C_floor}, {pidv2_config.C_good}]")
        logger.info(f"  PPL deadband: {pidv2_config.V_dead}, scale: {pidv2_config.V_scale}")
        logger.info(f"  Authority floor: {pidv2_config.A_min}")
        logger.info("  Key insight: PPL velocity is causal; Coherence is non-monotonic")
        logger.info("=" * 60)

    else:  # pid (legacy)
        # Legacy PID mode - mixes coherence into PID (not recommended)
        if pid_config is None:
            pid_config = AuthorityPIDConfig()
        authority_controller = AuthorityPID(pid_config)
        controller_name = "PID (legacy)"

        logger.info("=" * 60)
        logger.info("V9.3.5-PID: LEGACY AUTHORITY PID CONTROLLER")
        logger.info("  WARNING: This mixes coherence into PID - use PIDv2 instead!")
        logger.info(f"  Gains: Kp={pid_config.Kp}, Ki={pid_config.Ki}, Kd={pid_config.Kd}")
        logger.info(f"  Coherence band: [{pid_config.C_low}, {pid_config.C_high}]")
        logger.info(f"  PPL deadband: {pid_config.V_dead}, scale: {pid_config.V_scale}")
        logger.info(f"  Authority floor: {pid_config.A_min}")
        logger.info("=" * 60)

    # Initialize TensorBoard
    tb_writer = None
    if config.tensorboard and TENSORBOARD_AVAILABLE:
        tb_log_dir = checkpoint_dir / "logs"
        tb_writer = SummaryWriter(log_dir=str(tb_log_dir))
        logger.info(f"TensorBoard logging to {tb_log_dir}")

    # Initialize Wandb
    if config.wandb and WANDB_AVAILABLE:
        wandb.init(
            project=config.wandb_project,
            name=config.wandb_run or f"pid_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            config=asdict(config)
        )
        logger.info("Wandb initialized")

    # =========================================================================
    # TRAINING LOOP
    # =========================================================================

    logger.info("=" * 60)
    logger.info("Starting training with PID Authority Controller")
    logger.info("=" * 60)

    model.train()
    accumulation_step = 0
    running_loss = 0.0
    step_start_time = time.time()
    handshake_triggered = False
    agc_threshold = config.agc_threshold if config.trinity_enabled else None

    # Infinite data iterator
    def infinite_loader(loader):
        while True:
            for batch in loader:
                yield batch
            state.epoch += 1

    train_iter = infinite_loader(train_loader)

    while state.step < config.max_steps:
        batch = next(train_iter)
        batch = tuple(t.to(device) for t in batch)

        # Forward/backward pass
        metrics = train_step(
            model, batch, optimizer, scheduler, config, state, scaler,
            agc_threshold=agc_threshold
        )

        if metrics is None:
            continue

        # =====================================================================
        # COMPUTE LR WITH PID AUTHORITY
        # =====================================================================

        # Get base LR from scheduler
        base_lr = scheduler.get_last_lr()[0]

        # Compute alpha phase
        if config.alpha_warmup_steps > 0:
            alpha_frac = min(1.0, state.step / config.alpha_warmup_steps)
            current_alpha = config.alpha_phase_start + alpha_frac * (config.alpha_phase_end - config.alpha_phase_start)
        else:
            current_alpha = config.alpha_phase_end

        # Compute base authority cap
        base_authority_cap = 0.3 + 0.7 * current_alpha

        # Apply PID authority factor
        effective_authority_cap = base_authority_cap * authority_controller.A

        # Compute effective LR cap
        effective_lr_cap = config.learning_rate * effective_authority_cap

        # Apply cap to base_lr
        if base_lr > effective_lr_cap:
            base_lr = effective_lr_cap

        # Compute phase LR multiplier
        if state.step < config.phase_delay_steps:
            phase_lr_mult = 0.0
        else:
            ramp_progress = min(1.0, (state.step - config.phase_delay_steps) / config.phase_ramp_steps)
            phase_lr_mult = config.phase_cooling_factor * ramp_progress

        # Update optimizer LRs
        combined_lr_scale = state.lr_scale * memory_guard.lr_scale

        for param_group in optimizer.param_groups:
            group_name = param_group.get('name', '')

            if 'phase_attn' in group_name:
                param_group['lr'] = memory_guard.get_phase_lr(base_lr * state.lr_scale, phase_lr_mult)
            elif 'local_attn' in group_name:
                param_group['lr'] = base_lr * config.attn_cooling_factor * combined_lr_scale
            else:
                param_group['lr'] = base_lr * combined_lr_scale

        # Update running loss
        accumulation_step += 1
        running_loss += metrics["loss"]
        state.total_tokens += batch[0].numel()

        # =====================================================================
        # STEP LOGGING
        # =====================================================================

        if accumulation_step % config.gradient_accumulation == 0:
            state.step += 1
            avg_loss = running_loss / config.gradient_accumulation
            state.train_losses.append(avg_loss)
            running_loss = 0.0

            # Update alpha schedule
            current_alpha = update_alpha_schedule(model, state.step, config)

            # Periodic logging
            if state.step % config.log_every == 0:
                elapsed = time.time() - step_start_time
                tokens_per_sec = (config.batch_size * config.max_seq_len * config.log_every) / elapsed
                step_start_time = time.time()

                # Get LRs for logging
                stable_lr = base_lr * combined_lr_scale
                local_lr = stable_lr * config.attn_cooling_factor
                phase_lr = stable_lr * phase_lr_mult

                # Phase status
                if state.step < config.phase_delay_steps:
                    phase_status = "FROZEN"
                else:
                    ramp_pct = min(100, int(100 * (state.step - config.phase_delay_steps) / config.phase_ramp_steps))
                    phase_status = f"{ramp_pct}%"

                # Build log message
                log_msg = (
                    f"Step {state.step:>6} | "
                    f"Loss: {avg_loss:.4f} | "
                    f"PPL: {math.exp(avg_loss):.2f} | "
                    f"LR: {stable_lr:.2e} | "
                    f"Tok/s: {tokens_per_sec:.0f}"
                )

                # Add coherence if available
                if config.use_coherence_loss and "coherence" in metrics:
                    log_msg += f" | Coh: {metrics['coherence']:.3f}"

                # Add alpha and PID authority
                log_msg += f" | α: {current_alpha:.2f} | A: {authority_controller.A:.2f}"

                # Add GATED indicator
                remaining = max(0, config.alpha_warmup_steps - state.step)
                if remaining > 0:
                    log_msg += f" | 🔓GATED({remaining})"

                logger.info(log_msg)

                # TensorBoard logging
                if tb_writer is not None:
                    tb_writer.add_scalar("train/loss", avg_loss, state.step)
                    tb_writer.add_scalar("train/perplexity", math.exp(avg_loss), state.step)
                    tb_writer.add_scalar("train/learning_rate", stable_lr, state.step)
                    tb_writer.add_scalar("train/alpha_phase", current_alpha, state.step)
                    tb_writer.add_scalar("ctrl/authority_A", authority_controller.A, state.step)
                    if config.use_coherence_loss:
                        tb_writer.add_scalar("train/coherence", metrics.get("coherence", 0), state.step)

                # Wandb logging
                if config.wandb and WANDB_AVAILABLE:
                    wandb.log({
                        "train/loss": avg_loss,
                        "train/perplexity": math.exp(avg_loss),
                        "train/learning_rate": stable_lr,
                        "train/alpha_phase": current_alpha,
                        "ctrl/authority_A": authority_controller.A,
                    }, step=state.step)

            # =================================================================
            # EVALUATION WITH PID UPDATE
            # =================================================================

            if state.step % config.eval_every == 0:
                logger.info("Evaluating...")
                val_metrics = evaluate(model, val_loader, config, device)

                current_val_ppl = val_metrics['val_perplexity']
                current_coh = metrics.get('coherence', 0.75)

                logger.info(
                    f"  Val Loss: {val_metrics['val_loss']:.4f} | "
                    f"Val PPL: {current_val_ppl:.2f}"
                )

                # =============================================================
                # PID CONTROLLER UPDATE
                # =============================================================

                old_A = authority_controller.A
                new_A = authority_controller.update(current_val_ppl, current_coh)

                # Log PID status
                logger.info(f"  {authority_controller.get_status_string()}")

                # Log detailed PID if authority changed significantly
                if abs(new_A - old_A) > 0.01:
                    logger.info(f"  {authority_controller.get_detailed_status()}")

                # TensorBoard controller metrics
                if tb_writer is not None:
                    tb_writer.add_scalar("ctrl/authority_A", new_A, state.step)
                    tb_writer.add_scalar("ctrl/e_p", authority_controller.last_e_p, state.step)
                    tb_writer.add_scalar("ctrl/ppl_velocity", authority_controller.last_v, state.step)
                    tb_writer.add_scalar("ctrl/control_signal_u", authority_controller.last_u, state.step)
                    tb_writer.add_scalar("val/perplexity", current_val_ppl, state.step)
                    tb_writer.add_scalar("val/loss", val_metrics['val_loss'], state.step)

                    # PID-specific metrics
                    if hasattr(authority_controller, 'last_e'):
                        tb_writer.add_scalar("ctrl/pressure_e", authority_controller.last_e, state.step)
                    if hasattr(authority_controller, 'last_e_c'):
                        tb_writer.add_scalar("ctrl/e_coh", authority_controller.last_e_c, state.step)
                    if hasattr(authority_controller, 'last_I'):
                        tb_writer.add_scalar("ctrl/integral_I", authority_controller.last_I, state.step)
                    # PD-specific metrics
                    if hasattr(authority_controller, 'last_e_d'):
                        tb_writer.add_scalar("ctrl/e_d", authority_controller.last_e_d, state.step)

                # PPL-Guard check (if enabled)
                if config.trinity_enabled and ppl_guard is not None:
                    triggered, new_agc = ppl_guard.check(
                        current_val_ppl, current_coh, state.step, logger
                    )
                    if triggered:
                        agc_threshold = new_agc
                        config.agc_threshold = new_agc

                # Save lightweight checkpoint
                eval_ckpt_path = checkpoint_dir / f"step_{state.step}.pt"
                if not eval_ckpt_path.exists():
                    save_checkpoint_light(model, state, config, str(eval_ckpt_path))
                    cleanup_old_checkpoints(checkpoint_dir, keep_last=5)

                # Save best model
                if val_metrics['val_loss'] < state.best_val_loss:
                    state.best_val_loss = val_metrics['val_loss']
                    best_path = checkpoint_dir / "best.pt"
                    save_checkpoint(
                        model, optimizer, scheduler, scaler, state, config,
                        str(best_path)
                    )
                    logger.info(f"  📦 New best! Saved to {best_path}")

            # =================================================================
            # V9.3 HANDSHAKE TRIGGER
            # =================================================================

            if (config.trinity_enabled and
                config.handshake_spike_enabled and
                not handshake_triggered and
                state.step == config.phase_delay_steps + 1):

                optimizer = trigger_handshake(model, config, optimizer, device, logger)
                handshake_triggered = True

            # =================================================================
            # PERIODIC CHECKPOINTING
            # =================================================================

            if state.step % config.save_every == 0:
                ckpt_path = checkpoint_dir / f"checkpoint_step_{state.step}.pt"
                save_checkpoint(
                    model, optimizer, scheduler, scaler, state, config,
                    str(ckpt_path)
                )
                logger.info(f"Checkpoint saved to {ckpt_path}")

    # =========================================================================
    # TRAINING COMPLETE
    # =========================================================================

    logger.info("=" * 60)
    logger.info("Training complete!")
    logger.info(f"  Final step: {state.step}")
    logger.info(f"  Best val loss: {state.best_val_loss:.4f}")
    logger.info(f"  Final {controller_name} Authority: {authority_controller.A:.3f}")
    logger.info("=" * 60)

    # Cleanup
    if tb_writer is not None:
        tb_writer.close()
    if config.wandb and WANDB_AVAILABLE:
        wandb.finish()

    return state


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Parse arguments and start training."""

    parser = argparse.ArgumentParser(
        description="SymbolU V9.3.5-PID Training",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Model configuration
    parser.add_argument("--model_size", type=str, default="medium",
                       choices=["tiny", "small", "medium", "large", "xl", "7b"],
                       help="Model size preset")
    parser.add_argument("--model_type", type=str, default="hybrid",
                       choices=["phase", "hybrid"],
                       help="Model type: phase (O(n)) or hybrid (local + phase)")

    # Dataset
    parser.add_argument("--dataset", type=str, default="wikitext103",
                       choices=["c4", "wikitext103", "wikitext2", "custom"],
                       help="Dataset to use")
    parser.add_argument("--dataset_path", type=str, default=None,
                       help="Path to custom dataset")

    # Training hyperparameters
    parser.add_argument("--learning_rate", type=float, default=4e-5,
                       help="Base learning rate")
    parser.add_argument("--batch_size", type=int, default=32,
                       help="Batch size per device")
    parser.add_argument("--gradient_accumulation", type=int, default=2,
                       help="Gradient accumulation steps")
    parser.add_argument("--max_steps", type=int, default=50000,
                       help="Maximum training steps")
    parser.add_argument("--warmup_steps", type=int, default=3000,
                       help="LR warmup steps")

    # Phase training schedule
    parser.add_argument("--alpha_warmup_steps", type=int, default=10000,
                       help="Steps to ramp alpha_phase from start to end")
    parser.add_argument("--phase_delay_steps", type=int, default=0,
                       help="Steps before Phase LR starts")
    parser.add_argument("--phase_ramp_steps", type=int, default=7000,
                       help="Steps to ramp Phase LR to full")

    # Checkpointing
    parser.add_argument("--checkpoint_dir", type=str, default="checkpoints_pid",
                       help="Directory for checkpoints")
    parser.add_argument("--resume", type=str, default=None,
                       help="Path to checkpoint to resume from")
    parser.add_argument("--resume_weights_only", action="store_true",
                       help="Only load model weights, reset optimizer")
    parser.add_argument("--eval_every", type=int, default=100,
                       help="Evaluate every N steps")
    parser.add_argument("--save_every", type=int, default=5000,
                       help="Save checkpoint every N steps")
    parser.add_argument("--log_every", type=int, default=10,
                       help="Log every N steps")

    # Features
    parser.add_argument("--memory_guard", action="store_true",
                       help="Enable MemoryGuard dynamic batch scaling")
    parser.add_argument("--trinity", action="store_true",
                       help="Enable V9.3 Trinity optimization (AGC, Lookahead, PPL-Guard)")

    # Logging
    parser.add_argument("--wandb", action="store_true",
                       help="Enable Weights & Biases logging")
    parser.add_argument("--wandb_project", type=str, default="symbolu-pid",
                       help="W&B project name")
    parser.add_argument("--wandb_run", type=str, default=None,
                       help="W&B run name")
    parser.add_argument("--tensorboard", action="store_true", default=True,
                       help="Enable TensorBoard logging")

    # Controller selection
    parser.add_argument("--controller", type=str, default="pidv2",
                       choices=["pid", "pidv2", "emergency_pd"],
                       help="Controller type: pidv2 (recommended), pid (legacy), emergency_pd (crisis)")
    parser.add_argument("--use_emergency_pd", action="store_true",
                       help="DEPRECATED: Use --controller emergency_pd instead")

    # PIDv2 Controller settings (RECOMMENDED - follows control-systems theory)
    parser.add_argument("--pidv2_kp", type=float, default=0.25,
                       help="PIDv2 proportional gain on PPL velocity")
    parser.add_argument("--pidv2_ki", type=float, default=0.02,
                       help="PIDv2 integral gain on PPL velocity")
    parser.add_argument("--pidv2_kd", type=float, default=0.15,
                       help="PIDv2 derivative gain (velocity acceleration)")
    parser.add_argument("--pidv2_a_min", type=float, default=0.30,
                       help="PIDv2 minimum authority factor")
    parser.add_argument("--pidv2_c_floor", type=float, default=0.68,
                       help="PIDv2 coherence floor for gate")
    parser.add_argument("--pidv2_c_good", type=float, default=0.76,
                       help="PIDv2 coherence threshold for full authority")

    # Legacy PID Controller settings (mixes coherence into PID - not recommended)
    parser.add_argument("--pid_kp", type=float, default=0.20,
                       help="PID proportional gain (legacy)")
    parser.add_argument("--pid_ki", type=float, default=0.03,
                       help="PID integral gain (legacy)")
    parser.add_argument("--pid_kd", type=float, default=0.12,
                       help="PID derivative gain (legacy)")
    parser.add_argument("--pid_a_min", type=float, default=0.70,
                       help="PID minimum authority factor (legacy)")

    # Emergency PD settings (VIOLENT crisis response - coherence primary)
    parser.add_argument("--pd_kp", type=float, default=2.5,
                       help="Emergency PD proportional gain on coherence")
    parser.add_argument("--pd_kd", type=float, default=0.5,
                       help="Emergency PD derivative gain on PPL velocity")
    parser.add_argument("--pd_a_min", type=float, default=0.25,
                       help="Emergency PD minimum authority factor")
    parser.add_argument("--pd_target_coh", type=float, default=0.76,
                       help="Emergency PD target coherence")

    args = parser.parse_args()

    # Build config from args
    config = TrainingConfig(
        model_size=args.model_size,
        model_type=args.model_type,
        dataset=args.dataset,
        dataset_path=args.dataset_path,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        gradient_accumulation=args.gradient_accumulation,
        max_steps=args.max_steps,
        warmup_steps=args.warmup_steps,
        alpha_warmup_steps=args.alpha_warmup_steps,
        phase_delay_steps=args.phase_delay_steps,
        phase_ramp_steps=args.phase_ramp_steps,
        checkpoint_dir=args.checkpoint_dir,
        resume=args.resume,
        resume_weights_only=args.resume_weights_only,
        eval_every=args.eval_every,
        save_every=args.save_every,
        log_every=args.log_every,
        memory_guard_enabled=args.memory_guard,
        trinity_enabled=args.trinity,
        wandb=args.wandb,
        wandb_project=args.wandb_project,
        wandb_run=args.wandb_run,
        tensorboard=args.tensorboard,
    )

    # Determine controller type (--use_emergency_pd overrides --controller for backwards compat)
    if args.use_emergency_pd:
        controller_type = "emergency_pd"
    else:
        controller_type = args.controller

    # Build controller configuration based on type
    pd_config = None
    pid_config = None
    pidv2_config = None

    if controller_type == "emergency_pd":
        pd_config = EmergencyPDConfig(
            target_coh=args.pd_target_coh,
            Kp=args.pd_kp,
            Kd=args.pd_kd,
            A_min=args.pd_a_min,
        )
        controller_mode = "EMERGENCY PD"
    elif controller_type == "pidv2":
        pidv2_config = AuthorityPIDv2Config(
            Kp=args.pidv2_kp,
            Ki=args.pidv2_ki,
            Kd=args.pidv2_kd,
            A_min=args.pidv2_a_min,
            C_floor=args.pidv2_c_floor,
            C_good=args.pidv2_c_good,
        )
        controller_mode = "PIDv2"
    else:  # pid (legacy)
        pid_config = AuthorityPIDConfig(
            Kp=args.pid_kp,
            Ki=args.pid_ki,
            Kd=args.pid_kd,
            A_min=args.pid_a_min,
        )
        controller_mode = "PID (legacy)"

    # Print banner
    print("=" * 70)
    if controller_type == "emergency_pd":
        print("  SYMBOLU V9.3.6 - EMERGENCY PD TRAINING")
        print("  Phase Attention Transformer with Emergency PD Controller")
    elif controller_type == "pidv2":
        print("  SYMBOLU V9.4.0 - PIDv2 TRAINING (Control-Systems Design)")
        print("  Phase Attention Transformer with PPL-Primary PID + Coherence Gate")
    else:
        print("  SYMBOLU V9.3.5-PID TRAINING (LEGACY)")
        print("  Phase Attention Transformer with Authority PID Controller")
    print("=" * 70)
    print()
    print(f"  Model: {args.model_size}")
    print(f"  Dataset: {args.dataset}")
    print(f"  Max steps: {args.max_steps:,}")
    print(f"  Batch size: {args.batch_size} x {args.gradient_accumulation} accumulation")
    print(f"  Learning rate: {args.learning_rate}")
    print()
    if controller_type == "emergency_pd":
        print(f"  Controller: EMERGENCY PD (Coherence-primary, no Integral)")
        print(f"  PD Gains: Kp={args.pd_kp} (Coh), Kd={args.pd_kd} (PPL vel)")
        print(f"  Target Coherence: {args.pd_target_coh}")
        print(f"  Authority floor: {args.pd_a_min}")
    elif controller_type == "pidv2":
        print(f"  Controller: PIDv2 (PPL-Primary PID + Coherence Gate)")
        print(f"  PID Gains: Kp={args.pidv2_kp}, Ki={args.pidv2_ki}, Kd={args.pidv2_kd} (on PPL velocity)")
        print(f"  Coherence Gate: [{args.pidv2_c_floor}, {args.pidv2_c_good}]")
        print(f"  Authority floor: {args.pidv2_a_min}")
        print("  Architecture: PPL velocity drives PID; Coherence only gates authority")
    else:
        print(f"  Controller: Full PID (legacy - mixes coherence into PID)")
        print(f"  PID Gains: Kp={args.pid_kp}, Ki={args.pid_ki}, Kd={args.pid_kd}")
        print(f"  Authority floor: {args.pid_a_min}")
    print()

    # Run training
    try:
        train_with_pid(
            config,
            controller_type=controller_type,
            pd_config=pd_config,
            pid_config=pid_config,
            pidv2_config=pidv2_config,
        )
    except KeyboardInterrupt:
        print("\nTraining interrupted by user")
    except Exception as e:
        print(f"\nTraining failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
