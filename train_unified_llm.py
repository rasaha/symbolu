#!/usr/bin/env python3
"""
Unified LLM Training Script
============================

Train SymbolU models with support for:
1. SymbolU12 with Bhava (standard attention + 12D ontological + 144D bhava)
2. Phase Attention (O(n) complexity)
3. Hybrid (Local + Phase attention)

This script unifies all architectures under a single training interface.

Usage:
------
    # Train SymbolU12 with Bhava (standard attention + ontological)
    python train_unified_llm.py --model_type ontological --model_size small \
        --dataset wikitext103 --max_steps 1000

    # Train Phase model (O(n) attention)
    python train_unified_llm.py --model_type phase --model_size small \
        --dataset wikitext103 --max_steps 1000

    # Train Hybrid model (Local + Phase)
    python train_unified_llm.py --model_type hybrid --model_size small \
        --dataset wikitext103 --max_steps 1000 --local_backend unfold

    # Long context training (16K/32K)
    python train_unified_llm.py --model_type ontological --model_size small \
        --max_seq_len 16384 --gradient_checkpointing --batch_size 1

Author: SymbolU Team
Date: December 2025
"""

import argparse
import json
import logging
import math
import os
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
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        pin_memory=True,
        drop_last=True,
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
            gradient_checkpointing=config.gradient_checkpointing,
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
            gradient_checkpointing=config.gradient_checkpointing,
        )

    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    return model.to(device)


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
    """Main training loop."""

    # Setup
    torch.manual_seed(config.seed)

    # Device
    if config.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(config.device)

    print(f"\n{'='*70}")
    print("   UNIFIED SYMBOLU LLM TRAINING")
    print(f"{'='*70}")
    print(f"\n  Model Type: {config.model_type.upper()}")
    print(f"  Model Size: {config.model_size}")
    print(f"  Max Seq Len: {config.max_seq_len:,}")
    print(f"  Dataset: {config.dataset}")
    print(f"  Device: {device}")
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
    train_losses = []

    # Checkpoint directory
    ckpt_dir = Path(config.checkpoint_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    with open(ckpt_dir / "config.json", "w") as f:
        json.dump(asdict(config), f, indent=2)

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
            else:
                # Phase or Hybrid
                logits = model(x)
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

                print(log_msg)
                step_start_time = time.time()

            # Evaluation
            if global_step % config.eval_every == 0:
                val_loss, val_metrics = evaluate(model, val_loader, device, config, autocast_dtype)
                print(f"  --> Val Loss: {val_loss:.4f} | Val PPL: {val_metrics['ppl']:.2f}")

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

    # Final save
    save_checkpoint(model, optimizer, scheduler, global_step, best_val_loss,
                   ckpt_dir / "final.pt")

    print(f"\n{'='*70}")
    print("   TRAINING COMPLETE")
    print(f"{'='*70}")
    print(f"  Total Steps: {global_step:,}")
    print(f"  Best Val Loss: {best_val_loss:.4f}")
    print(f"  Best Val PPL: {math.exp(best_val_loss):.2f}")
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
                else:
                    logits = model(x)
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
                       choices=["ontological", "phase", "hybrid"],
                       help="Model architecture type")
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

    args = parser.parse_args()

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
    )

    # Train
    train(config)


if __name__ == "__main__":
    main()
