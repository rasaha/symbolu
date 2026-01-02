#!/usr/bin/env python3
"""
Unified LLM Training Script V9.4.4
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
    )
    from train import cleanup_old_checkpoints
    PIDV2_AVAILABLE = True
except ImportError as e:
    PIDV2_AVAILABLE = False
    print(f"Warning: PIDv2 controller not available: {e}")


# =============================================================================
# PERFORMANCE OPTIMIZATIONS
# =============================================================================
# TF32 for faster matrix multiplications on Ampere+ GPUs (A100, H100)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# cuDNN autotuning for optimal convolution algorithms
torch.backends.cudnn.benchmark = True


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

        # Create SymbolU12 Gen 2 (Hierarchical Complex Bhava)
        gen2_config = SymbolU12Gen2Config(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            num_heads=preset["num_heads"],
            num_layers=preset["num_layers"],
            complex_dim=64,  # Complex embedding dimension
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            ffn_mult=preset["ff_dim"] / preset["embed_dim"],
        )

        model = SymbolU12Gen2(gen2_config)
        print(f"\n  [Gen 2] Hierarchical Complex Bhava enabled")
        print(f"  [Gen 2] Complex dim: {gen2_config.complex_dim}")
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
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute loss for ontological model.

    Includes:
    - Language modeling loss (cross-entropy)
    - Bhava relationship consistency loss
    - Global coherence regularization
    - Entropy regularization
    """
    metrics = {}

    # 1. Language modeling loss
    logits = outputs["logits"]
    B, N, V = logits.shape
    lm_loss = F.cross_entropy(
        logits.view(-1, V),
        targets.view(-1),
        ignore_index=-100,
    )
    metrics["lm_loss"] = lm_loss.item()
    metrics["ppl"] = math.exp(min(lm_loss.item(), 20))

    # 2. Bhava relationship consistency loss
    # Encourage smooth relationship matrix (adjacent layers should be similar)
    if "relationship_matrix" in outputs:
        rel_matrix = outputs["relationship_matrix"]  # [B, 12, 12]
        # Smoothness: penalize large differences between adjacent relationships
        rel_diff = (rel_matrix[:, 1:, :] - rel_matrix[:, :-1, :]).abs().mean()
        bhava_loss = rel_diff
        metrics["bhava_loss"] = bhava_loss.item()
    else:
        bhava_loss = torch.tensor(0.0, device=logits.device)

    # 3. Global coherence regularization
    # Encourage high coherence (penalize low coherence)
    if "global_coherence" in outputs:
        coherence = outputs["global_coherence"].mean()
        coherence_loss = 1.0 - coherence  # Higher coherence = lower loss
        metrics["coherence"] = coherence.item()
        metrics["coherence_loss"] = coherence_loss.item()
    else:
        coherence_loss = torch.tensor(0.0, device=logits.device)

    # 4. Entropy regularization for ontological probabilities
    if "ontological_probs" in outputs:
        probs = outputs["ontological_probs"]  # [B, 12]
        # Encourage some entropy (not too certain, not too uncertain)
        entropy = -(probs * (probs + 1e-8).log()).sum(dim=-1).mean()
        target_entropy = 1.5  # ~4-5 active layers
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

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    tokenizer.model_max_length = int(1e12)

    # Load data
    train_loader, val_loader = load_data(config, tokenizer)

    # Create model
    model = create_model(config, device)
    num_params = sum(p.numel() for p in model.parameters())
    print(f"\n  Model Parameters: {num_params:,} ({num_params/1e6:.1f}M)")

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
                loss, metrics = compute_ontological_loss(outputs, y, config)
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

            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)

            if scaler is not None:
                scaler.step(optimizer)
                scaler.update()
            else:
                optimizer.step()

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

                # Add Gen 2 hierarchical metrics
                if config.model_type == "gen2":
                    if "coherence" in metrics:
                        log_msg += f" | Coh: {metrics['coherence']:.3f}"
                    if "level_3_coh" in metrics:
                        log_msg += f" | L3: {metrics['level_3_coh']:.2f}"

                # Add alpha for phase/hybrid models
                if config.model_type in ("phase", "hybrid"):
                    log_msg += f" | α_phase: {current_alpha:.2f}"

                print(log_msg)
                step_start_time = time.time()

            # Evaluation
            if global_step % config.eval_every == 0:
                val_loss, val_metrics = evaluate(model, val_loader, device, config, autocast_dtype)
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

                    # Apply authority factor to learning rate
                    for pg in optimizer.param_groups:
                        pg['lr'] *= new_A

                    # TensorBoard logging
                    if tb_writer is not None:
                        tb_writer.add_scalar("ctrl/authority_A", new_A, global_step)
                        tb_writer.add_scalar("ctrl/ppl_velocity", authority_controller.last_v, global_step)
                        if hasattr(authority_controller, 'last_Kp'):
                            tb_writer.add_scalar("ctrl/dynamic_Kp", authority_controller.last_Kp, global_step)
                else:
                    print(f"  --> Val Loss: {val_loss:.4f} | Val PPL: {val_ppl:.2f}")

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

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    save_checkpoint(model, optimizer, scheduler, global_step, best_val_loss,
                                   ckpt_dir / "best.pt")
                    print(f"  --> New best! Saved to {ckpt_dir / 'best.pt'}")

                model.train()

            # Save checkpoint
            if global_step % config.save_every == 0:
                save_checkpoint(model, optimizer, scheduler, global_step, best_val_loss,
                               ckpt_dir / f"step_{global_step}.pt")
                # Cleanup old checkpoints (keep last 5)
                if PIDV2_AVAILABLE:
                    cleanup_old_checkpoints(ckpt_dir, keep_last=5)

    # Final save
    save_checkpoint(model, optimizer, scheduler, global_step, best_val_loss,
                   ckpt_dir / "final.pt")

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
                    loss, metrics = compute_ontological_loss(outputs, y, config)
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
):
    """Save training checkpoint."""
    torch.save({
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "step": step,
        "best_val_loss": best_val_loss,
    }, path)


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
    )

    # Train
    train(config)


if __name__ == "__main__":
    main()
