#!/usr/bin/env python3
"""
Long Range Arena (LRA) Benchmark Training Script
=================================================

Train and evaluate SymbolU models on LRA tasks to demonstrate
long-range dependency learning with O(n) attention.

LRA Tasks:
----------
- listops: Hierarchical math operations (2K tokens)
- text: IMDb sentiment classification (4K tokens)
- retrieval: Document matching (4K tokens)
- image: CIFAR-10 as pixel sequence (1K tokens)
- pathfinder: Path detection (1K tokens)
- pathx: Extended pathfinder (16K tokens) - THE HEADLINE TASK

Usage:
------
    # Quick validation (8K, 2000 steps)
    python train_lra.py --task pathfinder --model_type hybrid \
        --seq_len 8192 --max_steps 2000

    # Headline result (16K Path-X)
    python train_lra.py --task pathx --model_type hybrid \
        --seq_len 16384 --max_steps 5000 --gradient_checkpointing

    # Full benchmark
    python train_lra.py --task pathx --model_type hybrid \
        --seq_len 16384 --max_steps 20000 --gradient_checkpointing

Author: SymbolU Team
Date: December 2025
"""

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, Tuple, List

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, TensorDataset
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

import numpy as np

# Local imports
sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import (
    PhaseTransformer,
    HybridPhaseTransformer,
)


# =============================================================================
# LRA TASK CONFIGURATIONS
# =============================================================================

LRA_TASKS = {
    "listops": {
        "seq_len": 2048,
        "num_classes": 10,
        "vocab_size": 32,
        "description": "Hierarchical math operations",
    },
    "text": {
        "seq_len": 4096,
        "num_classes": 2,
        "vocab_size": 256,  # byte-level
        "description": "IMDb sentiment classification",
    },
    "retrieval": {
        "seq_len": 4096,
        "num_classes": 2,
        "vocab_size": 256,
        "description": "Document matching",
    },
    "image": {
        "seq_len": 1024,
        "num_classes": 10,
        "vocab_size": 256,
        "description": "CIFAR-10 pixel sequence",
    },
    "pathfinder": {
        "seq_len": 1024,
        "num_classes": 2,
        "vocab_size": 256,
        "description": "Path detection in images",
    },
    "pathx": {
        "seq_len": 16384,
        "num_classes": 2,
        "vocab_size": 256,
        "description": "Extended pathfinder (16K) - HARDEST",
    },
}


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class LRAConfig:
    """Configuration for LRA training."""

    # Task
    task: str = "pathfinder"
    seq_len: Optional[int] = None  # Override task default

    # Model
    model_type: str = "hybrid"  # phase, hybrid
    model_size: str = "small"
    embed_dim: int = 256
    num_layers: int = 6
    num_heads: int = 4
    ff_dim: int = 1024
    dropout: float = 0.1

    # Hybrid-specific
    local_layers: int = 2
    window_size: int = 256
    local_backend: str = "unfold"
    alpha_local: float = 0.8
    alpha_phase: float = 0.2

    # Training
    batch_size: int = 32
    gradient_accumulation: int = 1
    max_steps: int = 20000
    warmup_steps: int = 1000
    learning_rate: float = 1e-4
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0

    # Memory
    gradient_checkpointing: bool = False
    mixed_precision: str = "bf16"

    # Logging
    log_every: int = 100
    eval_every: int = 500
    save_every: int = 2000
    checkpoint_dir: str = "checkpoints_lra"

    # Hardware
    device: str = "auto"
    num_workers: int = 4
    seed: int = 42


MODEL_PRESETS = {
    "tiny": {"embed_dim": 128, "num_layers": 4, "num_heads": 2, "ff_dim": 512},
    "small": {"embed_dim": 256, "num_layers": 6, "num_heads": 4, "ff_dim": 1024},
    "medium": {"embed_dim": 512, "num_layers": 8, "num_heads": 8, "ff_dim": 2048},
    "large": {"embed_dim": 768, "num_layers": 12, "num_heads": 12, "ff_dim": 3072},
}


# =============================================================================
# SYNTHETIC LRA DATA GENERATION
# =============================================================================

def generate_pathfinder_data(
    num_samples: int,
    seq_len: int,
    difficulty: str = "medium",
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Generate synthetic Pathfinder-like data.

    Task: Given a sequence representing an image with dots and lines,
    determine if there's a connected path between two marked endpoints.

    This is a simplified version for testing. For full benchmark,
    download actual LRA datasets.
    """
    # Image dimensions (square root of seq_len, approximately)
    img_size = int(np.sqrt(seq_len))
    if img_size * img_size < seq_len:
        img_size += 1

    X = []
    y = []

    for _ in range(num_samples):
        # Create blank image
        img = np.zeros(seq_len, dtype=np.int64)

        # Randomly decide if path exists
        has_path = np.random.rand() > 0.5

        if has_path:
            # Create a path from start to end
            path_len = seq_len // 4
            start = np.random.randint(0, seq_len // 2)

            # Simple path: linear with some noise
            path_positions = []
            pos = start
            for i in range(path_len):
                path_positions.append(pos)
                # Move forward with some variation
                step = np.random.randint(1, 4)
                pos = min(pos + step, seq_len - 1)

            # Mark path
            for p in path_positions:
                img[p] = 128 + np.random.randint(-20, 20)

            # Mark endpoints distinctly
            img[path_positions[0]] = 255
            img[path_positions[-1]] = 255

            label = 1
        else:
            # Create disconnected segments
            for _ in range(3):
                start = np.random.randint(0, seq_len - 50)
                length = np.random.randint(10, 50)
                for i in range(length):
                    if start + i < seq_len:
                        img[start + i] = 128 + np.random.randint(-20, 20)

            # Mark two random points as "endpoints" (not connected)
            p1 = np.random.randint(0, seq_len // 2)
            p2 = np.random.randint(seq_len // 2, seq_len)
            img[p1] = 255
            img[p2] = 255

            label = 0

        # Add noise
        noise_mask = np.random.rand(seq_len) < 0.05
        img[noise_mask] = np.random.randint(0, 64, size=noise_mask.sum())

        X.append(img)
        y.append(label)

    return torch.tensor(np.array(X), dtype=torch.long), torch.tensor(y, dtype=torch.long)


def generate_listops_data(
    num_samples: int,
    seq_len: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Generate synthetic ListOps-like data.

    Task: Evaluate nested mathematical expressions.
    Example: [MAX 2 [MIN 3 4] 5] -> 5

    Simplified version for testing.
    """
    # Vocabulary: digits 0-9, operations (MIN, MAX, MED, SM), brackets, padding
    # 0-9: digits, 10: MIN, 11: MAX, 12: MED, 13: SM, 14: [, 15: ], 16: PAD

    X = []
    y = []

    ops = {10: min, 11: max, 12: lambda x: sorted(x)[len(x)//2] if x else 0}

    for _ in range(num_samples):
        seq = np.full(seq_len, 16, dtype=np.int64)  # PAD

        # Generate a simple expression
        depth = np.random.randint(2, 5)
        expr_tokens = []
        values_stack = []

        def generate_expr(d):
            if d == 0 or np.random.rand() < 0.3:
                # Terminal: digit
                val = np.random.randint(0, 10)
                return [val], val
            else:
                # Non-terminal: operation
                op = np.random.choice([10, 11])  # MIN or MAX
                num_args = np.random.randint(2, 4)

                tokens = [14, op]  # [ OP
                vals = []
                for _ in range(num_args):
                    sub_tokens, sub_val = generate_expr(d - 1)
                    tokens.extend(sub_tokens)
                    vals.append(sub_val)
                tokens.append(15)  # ]

                if op == 10:
                    result = min(vals)
                else:
                    result = max(vals)

                return tokens, result

        tokens, result = generate_expr(depth)

        # Truncate or pad
        if len(tokens) > seq_len:
            tokens = tokens[:seq_len]

        seq[:len(tokens)] = tokens

        X.append(seq)
        y.append(result % 10)  # Class 0-9

    return torch.tensor(np.array(X), dtype=torch.long), torch.tensor(y, dtype=torch.long)


def generate_text_data(
    num_samples: int,
    seq_len: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Generate synthetic text classification data.

    Task: Binary sentiment classification based on keyword patterns.
    Simplified version - actual LRA uses byte-level IMDb.
    """
    # Positive and negative patterns
    positive_words = [ord(c) for c in "goodgreatexcellentamazinglovewonderful"]
    negative_words = [ord(c) for c in "badterribleawfulhateworst"]
    neutral = [ord(c) for c in "thequickbrownfoxjumpsoverthelazydog "]

    X = []
    y = []

    for _ in range(num_samples):
        seq = np.zeros(seq_len, dtype=np.int64)

        # Fill with neutral text
        for i in range(seq_len):
            seq[i] = np.random.choice(neutral)

        # Decide sentiment
        is_positive = np.random.rand() > 0.5

        # Insert sentiment words at random positions
        keywords = positive_words if is_positive else negative_words
        num_insertions = np.random.randint(3, 8)

        for _ in range(num_insertions):
            pos = np.random.randint(0, seq_len - 20)
            word_len = np.random.randint(4, 10)
            for j in range(word_len):
                if pos + j < seq_len:
                    seq[pos + j] = np.random.choice(keywords)

        X.append(seq)
        y.append(1 if is_positive else 0)

    return torch.tensor(np.array(X), dtype=torch.long), torch.tensor(y, dtype=torch.long)


def load_lra_data(
    task: str,
    seq_len: int,
    num_train: int = 50000,
    num_val: int = 5000,
) -> Tuple[DataLoader, DataLoader, int]:
    """
    Load or generate LRA data.

    Returns train_loader, val_loader, num_classes
    """
    task_info = LRA_TASKS[task]
    num_classes = task_info["num_classes"]

    print(f"Generating {task} data (seq_len={seq_len})...")

    if task in ["pathfinder", "pathx"]:
        train_X, train_y = generate_pathfinder_data(num_train, seq_len)
        val_X, val_y = generate_pathfinder_data(num_val, seq_len)
    elif task == "listops":
        train_X, train_y = generate_listops_data(num_train, seq_len)
        val_X, val_y = generate_listops_data(num_val, seq_len)
    elif task == "text":
        train_X, train_y = generate_text_data(num_train, seq_len)
        val_X, val_y = generate_text_data(num_val, seq_len)
    else:
        # Default to pathfinder-style for other tasks
        train_X, train_y = generate_pathfinder_data(num_train, seq_len)
        val_X, val_y = generate_pathfinder_data(num_val, seq_len)

    print(f"  Train: {len(train_X)} samples")
    print(f"  Val: {len(val_X)} samples")
    print(f"  Classes: {num_classes}")

    train_dataset = TensorDataset(train_X, train_y)
    val_dataset = TensorDataset(val_X, val_y)

    train_loader = DataLoader(
        train_dataset,
        batch_size=32,  # Will be overridden
        shuffle=True,
        num_workers=4,
        pin_memory=True,
        drop_last=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=32,
        shuffle=False,
        num_workers=4,
        pin_memory=True,
    )

    return train_loader, val_loader, num_classes


# =============================================================================
# MODEL WITH CLASSIFICATION HEAD
# =============================================================================

class LRAClassifier(nn.Module):
    """
    Wrapper that adds classification head to transformer encoder.
    """

    def __init__(
        self,
        encoder: nn.Module,
        embed_dim: int,
        num_classes: int,
        vocab_size: int,
        pool: str = "mean",  # mean, cls, last
    ):
        super().__init__()
        self.encoder = encoder
        self.pool = pool
        self.num_classes = num_classes

        # Replace embedding if vocab size differs
        if hasattr(encoder, 'embed'):
            old_vocab = encoder.embed.num_embeddings
            if old_vocab != vocab_size:
                encoder.embed = nn.Embedding(vocab_size, embed_dim)

        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(embed_dim, embed_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(embed_dim, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, seq_len] input token ids

        Returns:
            logits: [B, num_classes]
        """
        # Get encoder output
        # For transformers that return logits, we need hidden states
        if hasattr(self.encoder, 'get_hidden_states'):
            hidden = self.encoder.get_hidden_states(x)
        else:
            # Use embedding + layers directly
            B, N = x.shape

            # Embedding
            h = self.encoder.embed(x)
            if hasattr(self.encoder, 'pos_embed'):
                pos = torch.arange(N, device=x.device)
                h = h + self.encoder.pos_embed(pos)

            # Process through layers
            if hasattr(self.encoder, 'layers'):
                for layer in self.encoder.layers:
                    h = layer(h)
            elif hasattr(self.encoder, 'blocks'):
                for block in self.encoder.blocks:
                    h = block(h)

            hidden = h  # [B, N, embed_dim]

        # Pool
        if self.pool == "mean":
            pooled = hidden.mean(dim=1)  # [B, embed_dim]
        elif self.pool == "cls":
            pooled = hidden[:, 0]
        elif self.pool == "last":
            pooled = hidden[:, -1]
        else:
            pooled = hidden.mean(dim=1)

        # Classify
        logits = self.classifier(pooled)

        return logits


def create_lra_model(config: LRAConfig, num_classes: int, vocab_size: int, device: torch.device) -> nn.Module:
    """Create model for LRA task."""

    preset = MODEL_PRESETS.get(config.model_size, MODEL_PRESETS["small"])
    embed_dim = config.embed_dim or preset["embed_dim"]
    num_layers = config.num_layers or preset["num_layers"]
    num_heads = config.num_heads or preset["num_heads"]
    ff_dim = config.ff_dim or preset["ff_dim"]

    seq_len = config.seq_len or LRA_TASKS[config.task]["seq_len"]

    if config.model_type == "phase":
        encoder = PhaseTransformer(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=seq_len,
            dropout=config.dropout,
            gradient_checkpointing=config.gradient_checkpointing,
        )
    elif config.model_type == "hybrid":
        encoder = HybridPhaseTransformer(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=seq_len,
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

    model = LRAClassifier(
        encoder=encoder,
        embed_dim=embed_dim,
        num_classes=num_classes,
        vocab_size=vocab_size,
        pool="mean",
    )

    return model.to(device)


# =============================================================================
# TRAINING
# =============================================================================

def train_lra(config: LRAConfig):
    """Main training loop for LRA."""

    torch.manual_seed(config.seed)
    np.random.seed(config.seed)

    # Device
    if config.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(config.device)

    # Task info
    task_info = LRA_TASKS[config.task]
    seq_len = config.seq_len or task_info["seq_len"]
    vocab_size = task_info["vocab_size"]

    print(f"\n{'='*70}")
    print(f"   LRA BENCHMARK: {config.task.upper()}")
    print(f"{'='*70}")
    print(f"\n  Task: {task_info['description']}")
    print(f"  Sequence Length: {seq_len:,}")
    print(f"  Model: {config.model_type.upper()}")
    print(f"  Device: {device}")
    print(f"  Gradient Checkpointing: {config.gradient_checkpointing}")

    # Load data
    train_loader, val_loader, num_classes = load_lra_data(
        config.task, seq_len,
        num_train=50000, num_val=5000,
    )

    # Override batch size
    train_loader = DataLoader(
        train_loader.dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        pin_memory=True,
        drop_last=True,
    )
    val_loader = DataLoader(
        val_loader.dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        pin_memory=True,
    )

    # Create model
    model = create_lra_model(config, num_classes, vocab_size, device)
    num_params = sum(p.numel() for p in model.parameters())
    print(f"\n  Model Parameters: {num_params:,} ({num_params/1e6:.1f}M)")

    # Optimizer
    optimizer = AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
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

    # Checkpoint directory
    ckpt_dir = Path(config.checkpoint_dir) / config.task
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    with open(ckpt_dir / "config.json", "w") as f:
        json.dump(asdict(config), f, indent=2)

    print(f"\n{'='*70}")
    print("   STARTING TRAINING")
    print(f"{'='*70}\n")

    # Training state
    global_step = 0
    best_val_acc = 0.0
    train_iter = iter(train_loader)

    model.train()
    step_start_time = time.time()
    running_loss = 0.0
    running_correct = 0
    running_total = 0

    while global_step < config.max_steps:
        # Get batch
        try:
            x, y = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            x, y = next(train_iter)

        x, y = x.to(device), y.to(device)

        # Forward
        with torch.cuda.amp.autocast(dtype=autocast_dtype):
            logits = model(x)
            loss = F.cross_entropy(logits, y)

        # Backward
        if scaler is not None:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            optimizer.step()

        optimizer.zero_grad()

        if global_step >= config.warmup_steps:
            scheduler.step()

        # Track metrics
        global_step += 1
        running_loss += loss.item()
        preds = logits.argmax(dim=-1)
        running_correct += (preds == y).sum().item()
        running_total += y.size(0)

        # Logging
        if global_step % config.log_every == 0:
            elapsed = time.time() - step_start_time
            avg_loss = running_loss / config.log_every
            acc = running_correct / running_total * 100
            lr = optimizer.param_groups[0]["lr"]

            # Memory
            if device.type == "cuda":
                mem = torch.cuda.max_memory_allocated() / (1024**3)
                mem_str = f" | VRAM: {mem:.1f}GB"
            else:
                mem_str = ""

            print(f"Step {global_step:>6} | Loss: {avg_loss:.4f} | "
                  f"Acc: {acc:.1f}% | LR: {lr:.2e}{mem_str}")

            running_loss = 0.0
            running_correct = 0
            running_total = 0
            step_start_time = time.time()

        # Evaluation
        if global_step % config.eval_every == 0:
            val_loss, val_acc = evaluate_lra(model, val_loader, device, autocast_dtype)
            print(f"  --> Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.1f}%")

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                torch.save({
                    "model": model.state_dict(),
                    "step": global_step,
                    "val_acc": val_acc,
                }, ckpt_dir / "best.pt")
                print(f"  --> New best! Saved to {ckpt_dir / 'best.pt'}")

            model.train()

        # Save checkpoint
        if global_step % config.save_every == 0:
            torch.save({
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "step": global_step,
            }, ckpt_dir / f"step_{global_step}.pt")

    # Final evaluation
    val_loss, val_acc = evaluate_lra(model, val_loader, device, autocast_dtype)

    print(f"\n{'='*70}")
    print("   TRAINING COMPLETE")
    print(f"{'='*70}")
    print(f"  Task: {config.task}")
    print(f"  Sequence Length: {seq_len:,}")
    print(f"  Total Steps: {global_step:,}")
    print(f"  Best Val Accuracy: {best_val_acc:.1f}%")
    print(f"  Final Val Accuracy: {val_acc:.1f}%")

    # Save final
    torch.save({
        "model": model.state_dict(),
        "step": global_step,
        "val_acc": val_acc,
        "best_val_acc": best_val_acc,
    }, ckpt_dir / "final.pt")

    return best_val_acc


def evaluate_lra(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    autocast_dtype: torch.dtype,
) -> Tuple[float, float]:
    """Evaluate on validation set."""
    model.eval()

    total_loss = 0.0
    total_correct = 0
    total_samples = 0

    with torch.no_grad():
        for x, y in val_loader:
            x, y = x.to(device), y.to(device)

            with torch.cuda.amp.autocast(dtype=autocast_dtype):
                logits = model(x)
                loss = F.cross_entropy(logits, y)

            total_loss += loss.item() * y.size(0)
            preds = logits.argmax(dim=-1)
            total_correct += (preds == y).sum().item()
            total_samples += y.size(0)

    avg_loss = total_loss / total_samples
    accuracy = total_correct / total_samples * 100

    return avg_loss, accuracy


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="LRA Benchmark Training",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Task
    parser.add_argument("--task", type=str, default="pathfinder",
                       choices=list(LRA_TASKS.keys()),
                       help="LRA task")
    parser.add_argument("--seq_len", type=int, default=None,
                       help="Override sequence length")

    # Model
    parser.add_argument("--model_type", type=str, default="hybrid",
                       choices=["phase", "hybrid"],
                       help="Model architecture")
    parser.add_argument("--model_size", type=str, default="small",
                       choices=["tiny", "small", "medium", "large"],
                       help="Model size preset")

    # Training
    parser.add_argument("--batch_size", type=int, default=32,
                       help="Batch size")
    parser.add_argument("--max_steps", type=int, default=20000,
                       help="Maximum training steps")
    parser.add_argument("--learning_rate", type=float, default=1e-4,
                       help="Learning rate")

    # Memory
    parser.add_argument("--gradient_checkpointing", action="store_true",
                       help="Enable gradient checkpointing")
    parser.add_argument("--local_backend", type=str, default="unfold",
                       choices=["auto", "flash", "sdpa", "unfold"],
                       help="LocalAttention backend")
    parser.add_argument("--window_size", type=int, default=256,
                       help="Local attention window size")

    # Logging
    parser.add_argument("--log_every", type=int, default=100,
                       help="Log every N steps")
    parser.add_argument("--eval_every", type=int, default=500,
                       help="Evaluate every N steps")
    parser.add_argument("--checkpoint_dir", type=str, default="checkpoints_lra",
                       help="Checkpoint directory")

    # Other
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    config = LRAConfig(
        task=args.task,
        seq_len=args.seq_len,
        model_type=args.model_type,
        model_size=args.model_size,
        batch_size=args.batch_size,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        gradient_checkpointing=args.gradient_checkpointing,
        local_backend=args.local_backend,
        window_size=args.window_size,
        log_every=args.log_every,
        eval_every=args.eval_every,
        checkpoint_dir=args.checkpoint_dir,
        seed=args.seed,
    )

    train_lra(config)


if __name__ == "__main__":
    main()
