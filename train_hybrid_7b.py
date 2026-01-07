#!/usr/bin/env python3
"""
Hybrid 7B Training Script for FineWeb Dataset
==============================================

Optimized for NVIDIA A100 80GB with HybridPhaseTransformer.

Memory Budget (A100 80GB, BF16 + 8-bit Optimizer, seq_len=1024):
- Model weights (BF16): ~14GB
- Optimizer states (8-bit Adam): ~7GB (vs ~28GB with FP32 Adam)
- Gradients (BF16): ~14GB
- Activations (batch=2, checkpointed): ~45GB
- Total: ~80GB -> Batch size 2 on A100 80GB with optimizations

Memory Savings with 8-bit Optimizer:
- FP32 Adam: ~28GB optimizer states -> OOM even with batch=1
- 8-bit Adam: ~7GB optimizer states (75% savings) -> batch=1 fits!

Key Features:
- HybridPhaseTransformer 7B (32 layers, 16:16 split)
- FineWeb dataset streaming from HuggingFace
- Mixed precision (BF16) training
- 8-bit AdamW optimizer (bitsandbytes)
- Gradient checkpointing for memory efficiency
- Gradient accumulation for effective larger batches
- Cosine learning rate schedule with warmup
- Distributed training ready (DDP)

Usage:
    # Single A100 80GB (default: batch=1, 8-bit optimizer required)
    python train_hybrid_7b.py

    # Multi-GPU (4x A100) - can use batch=2 per GPU
    torchrun --nproc_per_node=4 train_hybrid_7b.py --batch_size 2 --gradient_accumulation 4

    # H200 141GB - can try batch=2
    python train_hybrid_7b.py --batch_size 2 --gradient_accumulation 8

Requirements:
    pip install bitsandbytes transformers datasets wandb

Author: Sovereign-1 Training Initiative
Date: January 2026
"""

import os
import sys
import math
import time
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, IterableDataset
from torch.amp import autocast, GradScaler

# Optional: Distributed training
try:
    import torch.distributed as dist
    from torch.nn.parallel import DistributedDataParallel as DDP
    HAS_DISTRIBUTED = True
except ImportError:
    HAS_DISTRIBUTED = False

# Optional: Weights & Biases logging
try:
    import wandb
    HAS_WANDB = True
except ImportError:
    HAS_WANDB = False

sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import HybridPhaseTransformer


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TrainingConfig:
    """Training configuration for Hybrid 7B."""
    # Model architecture (7B scale)
    vocab_size: int = 50257  # GPT-2 tokenizer
    embed_dim: int = 4096
    num_layers: int = 32
    num_heads: int = 32
    ff_dim: int = 11008  # LLaMA style: 2.7x embed_dim
    max_seq_len: int = 1024
    dropout: float = 0.0

    # Hybrid configuration
    local_layers: int = 16  # 16:16 split (balanced)
    window_size: int = 256
    cosine_mode: str = "standard"  # "standard", "shifted", "complex"
    decay_gamma: float = 1.0  # 1.0 = infinite memory
    alpha_local: float = 0.8
    alpha_phase: float = 0.2

    # Training hyperparameters
    batch_size: int = 2  # Per-GPU batch size (2 for A100 80GB with optimizations)
    gradient_accumulation: int = 8  # Effective batch = 2 * 8 = 16
    learning_rate: float = 3e-4
    min_learning_rate: float = 3e-5
    weight_decay: float = 0.1
    beta1: float = 0.9
    beta2: float = 0.95
    grad_clip: float = 1.0

    # Schedule
    warmup_steps: int = 2000
    max_steps: int = 100000

    # Memory optimization
    use_mixed_precision: bool = True
    use_gradient_checkpointing: bool = True
    use_8bit_optimizer: bool = True  # Use bitsandbytes 8-bit AdamW (saves ~75% optimizer memory)
    use_compile: bool = True  # Use torch.compile() for faster training (PyTorch 2.0+)

    # Dataset
    dataset_name: str = "HuggingFaceFW/fineweb"
    dataset_subset: str = "sample-10BT"  # 10B tokens sample

    # Logging & Checkpointing
    log_interval: int = 10
    sample_interval: int = 50  # Generate text samples every N steps
    eval_interval: int = 500
    save_interval: int = 1000
    output_dir: str = "./checkpoints/hybrid_7b"
    wandb_project: str = "hybrid-7b-fineweb"
    wandb_run_name: Optional[str] = None

    # Hardware
    device: str = "cuda"
    seed: int = 42


# =============================================================================
# DATASET
# =============================================================================

class FineWebDataset(IterableDataset):
    """Streaming FineWeb dataset for efficient training."""

    def __init__(
        self,
        tokenizer,
        seq_length: int = 1024,
        dataset_name: str = "HuggingFaceFW/fineweb",
        dataset_subset: str = "sample-10BT",
        split: str = "train",
    ):
        self.tokenizer = tokenizer
        self.seq_length = seq_length
        self.dataset_name = dataset_name
        self.dataset_subset = dataset_subset
        self.split = split

    def __iter__(self):
        from datasets import load_dataset

        # Stream dataset to avoid loading everything into memory
        dataset = load_dataset(
            self.dataset_name,
            name=self.dataset_subset,
            split=self.split,
            streaming=True,
        )

        buffer = []

        for example in dataset:
            # Tokenize text
            text = example.get("text", "")
            if not text:
                continue

            tokens = self.tokenizer.encode(text)
            buffer.extend(tokens)

            # Yield chunks of seq_length + 1 (for input/target)
            while len(buffer) >= self.seq_length + 1:
                chunk = buffer[:self.seq_length + 1]
                buffer = buffer[self.seq_length:]

                input_ids = torch.tensor(chunk[:-1], dtype=torch.long)
                labels = torch.tensor(chunk[1:], dtype=torch.long)

                yield {"input_ids": input_ids, "labels": labels}


def get_tokenizer():
    """Get GPT-2 tokenizer."""
    from transformers import GPT2TokenizerFast
    tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def create_dataloader(config: TrainingConfig, tokenizer, world_size: int = 1, rank: int = 0):
    """Create streaming dataloader for FineWeb."""
    dataset = FineWebDataset(
        tokenizer=tokenizer,
        seq_length=config.max_seq_len,
        dataset_name=config.dataset_name,
        dataset_subset=config.dataset_subset,
    )

    dataloader = DataLoader(
        dataset,
        batch_size=config.batch_size,
        num_workers=4,
        pin_memory=True,
        prefetch_factor=4,
    )

    return dataloader


# =============================================================================
# MODEL
# =============================================================================

def create_model(config: TrainingConfig) -> nn.Module:
    """Create HybridPhaseTransformer 7B model."""
    model = HybridPhaseTransformer(
        vocab_size=config.vocab_size,
        embed_dim=config.embed_dim,
        num_layers=config.num_layers,
        num_heads=config.num_heads,
        ff_dim=config.ff_dim,
        max_seq_len=config.max_seq_len,
        dropout=config.dropout,
        # Hybrid configuration
        local_layers=config.local_layers,
        window_size=config.window_size,
        local_backend="sdpa",  # Use SDPA/Flash attention
        alpha_local=config.alpha_local,
        alpha_phase=config.alpha_phase,
        cosine_mode=config.cosine_mode,
        decay_gamma=config.decay_gamma,
    )

    # Enable gradient checkpointing for memory efficiency
    if config.use_gradient_checkpointing:
        model.gradient_checkpointing_enable()

    return model


def count_parameters(model: nn.Module) -> int:
    """Count trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


@torch.no_grad()
def compute_val_ppl(model, val_dataloader, device, config, num_batches=10):
    """Compute validation perplexity on a few batches."""
    model.eval()
    total_loss = 0.0
    total_tokens = 0

    val_iter = iter(val_dataloader)
    for _ in range(num_batches):
        try:
            batch = next(val_iter)
        except StopIteration:
            val_iter = iter(val_dataloader)
            batch = next(val_iter)

        input_ids = batch["input_ids"].to(device)
        labels = batch["labels"].to(device)

        with autocast('cuda', enabled=config.use_mixed_precision, dtype=torch.bfloat16):
            output = model(input_ids)
            logits = output["logits"] if isinstance(output, dict) else output
            loss = F.cross_entropy(
                logits.view(-1, config.vocab_size),
                labels.view(-1),
                ignore_index=-100,
            )

        total_loss += loss.item() * input_ids.numel()
        total_tokens += input_ids.numel()

    avg_loss = total_loss / total_tokens if total_tokens > 0 else 0
    val_ppl = math.exp(min(avg_loss, 20))

    model.train()
    return val_ppl, avg_loss


@torch.no_grad()
def generate_samples(model, tokenizer, device, config, step, num_samples=3, max_new_tokens=50):
    """Generate text samples to monitor training quality."""
    model.eval()

    prompts = [
        "The meaning of life is",
        "In the year 2050,",
        "Once upon a time",
    ]

    print(f"\n  {'='*60}")
    print(f"  SAMPLES @ Step {step}")
    print(f"  {'='*60}")

    for i, prompt in enumerate(prompts[:num_samples]):
        input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)

        # Simple greedy generation
        generated = input_ids.clone()
        for _ in range(max_new_tokens):
            if generated.shape[1] >= config.max_seq_len:
                break

            with autocast('cuda', enabled=config.use_mixed_precision, dtype=torch.bfloat16):
                output = model(generated)
                logits = output["logits"] if isinstance(output, dict) else output

            # Greedy: take argmax of last token
            next_token = logits[:, -1, :].argmax(dim=-1, keepdim=True)
            generated = torch.cat([generated, next_token], dim=1)

            # Stop at EOS
            if next_token.item() == tokenizer.eos_token_id:
                break

        # Decode and print
        text = tokenizer.decode(generated[0], skip_special_tokens=True)
        print(f"\n  [{i+1}] {text[:200]}{'...' if len(text) > 200 else ''}")

    print(f"\n  {'='*60}\n")
    model.train()


# =============================================================================
# TRAINING UTILITIES
# =============================================================================

def get_lr(step: int, config: TrainingConfig) -> float:
    """Cosine learning rate schedule with warmup."""
    # Warmup
    if step < config.warmup_steps:
        return config.learning_rate * (step / config.warmup_steps)

    # Cosine decay
    decay_steps = config.max_steps - config.warmup_steps
    progress = (step - config.warmup_steps) / decay_steps
    cosine_decay = 0.5 * (1 + math.cos(math.pi * progress))

    return config.min_learning_rate + (config.learning_rate - config.min_learning_rate) * cosine_decay


def setup_distributed():
    """Setup distributed training if available."""
    if not HAS_DISTRIBUTED:
        return 0, 1, False

    if "RANK" in os.environ:
        rank = int(os.environ["RANK"])
        world_size = int(os.environ["WORLD_SIZE"])
        local_rank = int(os.environ["LOCAL_RANK"])

        dist.init_process_group(backend="nccl")
        torch.cuda.set_device(local_rank)

        return rank, world_size, True

    return 0, 1, False


def cleanup_distributed():
    """Cleanup distributed training."""
    if HAS_DISTRIBUTED and dist.is_initialized():
        dist.destroy_process_group()


# =============================================================================
# TRAINING LOOP
# =============================================================================

def train(config: TrainingConfig):
    """Main training function."""

    # Setup distributed
    rank, world_size, is_distributed = setup_distributed()
    is_main = rank == 0

    # Set seed
    torch.manual_seed(config.seed + rank)

    # GPU optimizations for throughput
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True  # Auto-tune convolutions
        torch.set_float32_matmul_precision('medium')  # Faster matmuls with TF32

    # Device
    device = torch.device(config.device if torch.cuda.is_available() else "cpu")

    if is_main:
        print(f"\n{'='*70}")
        print("   HYBRID 7B TRAINING")
        print(f"{'='*70}")
        print(f"\n  Device: {device}")
        if torch.cuda.is_available():
            print(f"  GPU: {torch.cuda.get_device_name()}")
            print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        print(f"  World Size: {world_size}")
        print(f"  Distributed: {is_distributed}")

    # Create output directory
    output_dir = Path(config.output_dir)
    if is_main:
        output_dir.mkdir(parents=True, exist_ok=True)
        # Save config
        with open(output_dir / "config.json", "w") as f:
            json.dump(asdict(config), f, indent=2)

    # Tokenizer
    tokenizer = get_tokenizer()

    # Create model
    if is_main:
        print(f"\n  Creating Hybrid 7B model...")

    model = create_model(config)

    # Convert model to BF16 to save memory (weights: ~28GB FP32 -> ~14GB BF16)
    if config.use_mixed_precision:
        model = model.to(torch.bfloat16)
        if is_main:
            print(f"  Model dtype: BF16 (saves ~50% memory)")

    model = model.to(device)

    num_params = count_parameters(model)
    if is_main:
        print(f"  Parameters: {num_params:,} ({num_params/1e9:.2f}B)")
        print(f"  Layer Split: {config.local_layers}:{config.num_layers - config.local_layers}")
        print(f"  Cosine Mode: {config.cosine_mode}")
        print(f"  Decay Gamma: {config.decay_gamma}")

    # Compile model for faster training (PyTorch 2.0+)
    if config.use_compile:
        if is_main:
            print(f"  Compiling model with torch.compile()...")
        model = torch.compile(model, mode="reduce-overhead")
        if is_main:
            print(f"  torch.compile: ENABLED (faster forward/backward)")

    # Wrap in DDP if distributed
    if is_distributed:
        model = DDP(model, device_ids=[rank])

    # Optimizer (8-bit for memory efficiency)
    if config.use_8bit_optimizer:
        try:
            import bitsandbytes as bnb
            optimizer = bnb.optim.AdamW8bit(
                model.parameters(),
                lr=config.learning_rate,
                betas=(config.beta1, config.beta2),
                weight_decay=config.weight_decay,
            )
            if is_main:
                print(f"  8-bit Optimizer: ENABLED (saves ~75% optimizer memory)")
        except ImportError:
            if is_main:
                print("  WARNING: bitsandbytes not installed, using standard AdamW")
                print("           Install with: pip install bitsandbytes")
            optimizer = torch.optim.AdamW(
                model.parameters(),
                lr=config.learning_rate,
                betas=(config.beta1, config.beta2),
                weight_decay=config.weight_decay,
            )
    else:
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=config.learning_rate,
            betas=(config.beta1, config.beta2),
            weight_decay=config.weight_decay,
        )

    # Mixed precision - GradScaler only needed for FP16, not BF16
    # BF16 has same exponent range as FP32, so no loss scaling needed
    scaler = None  # BF16 doesn't need GradScaler

    # Dataloader (train)
    dataloader = create_dataloader(config, tokenizer, world_size, rank)
    data_iter = iter(dataloader)

    # Validation dataloader (separate stream for val PPL)
    val_dataloader = create_dataloader(config, tokenizer, world_size, rank)  # Uses same streaming, different iterator

    # Initialize wandb
    if is_main and HAS_WANDB and config.wandb_project:
        wandb.init(
            project=config.wandb_project,
            name=config.wandb_run_name,
            config=asdict(config),
        )

    # Training loop
    if is_main:
        print(f"\n{'='*70}")
        print("   TRAINING")
        print(f"{'='*70}")
        print(f"\n  Batch Size: {config.batch_size}")
        print(f"  Gradient Accumulation: {config.gradient_accumulation}")
        print(f"  Effective Batch Size: {config.batch_size * config.gradient_accumulation * world_size}")
        print(f"  Max Steps: {config.max_steps}")
        print(f"  Warmup Steps: {config.warmup_steps}")
        print()

    model.train()
    step = 0
    total_loss = 0.0
    total_tokens = 0
    start_time = time.time()

    while step < config.max_steps:
        optimizer.zero_grad()

        # Gradient accumulation
        for micro_step in range(config.gradient_accumulation):
            try:
                batch = next(data_iter)
            except StopIteration:
                data_iter = iter(dataloader)
                batch = next(data_iter)

            input_ids = batch["input_ids"].to(device)
            labels = batch["labels"].to(device)

            # Forward pass with mixed precision
            with autocast('cuda', enabled=config.use_mixed_precision, dtype=torch.bfloat16):
                output = model(input_ids)
                logits = output["logits"] if isinstance(output, dict) else output

                # Cross-entropy loss
                loss = F.cross_entropy(
                    logits.view(-1, config.vocab_size),
                    labels.view(-1),
                    ignore_index=-100,
                )
                loss = loss / config.gradient_accumulation

            # Backward pass
            if scaler:
                scaler.scale(loss).backward()
            else:
                loss.backward()

            total_loss += loss.item()  # Already divided by gradient_accumulation
            total_tokens += input_ids.numel()

        # Gradient clipping
        if scaler:
            scaler.unscale_(optimizer)

        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip)

        # Update learning rate
        lr = get_lr(step, config)
        for param_group in optimizer.param_groups:
            param_group["lr"] = lr

        # Optimizer step
        if scaler:
            scaler.step(optimizer)
            scaler.update()
        else:
            optimizer.step()

        step += 1

        # Logging with PPL and VRAM
        if step % config.log_interval == 0 and is_main:
            elapsed = time.time() - start_time
            tokens_per_sec = total_tokens / elapsed
            avg_loss = total_loss / config.log_interval
            ppl = math.exp(min(avg_loss, 20))  # Cap to avoid overflow
            vram_gb = torch.cuda.max_memory_allocated() / 1e9 if torch.cuda.is_available() else 0

            print(f"  Step {step:6d} | Loss: {avg_loss:.4f} | PPL: {ppl:.2f} | "
                  f"LR: {lr:.2e} | Grad: {grad_norm:.2f} | Tok/s: {tokens_per_sec:.0f} | VRAM: {vram_gb:.1f}GB")

            if HAS_WANDB and config.wandb_project:
                wandb.log({
                    "loss": avg_loss,
                    "ppl": ppl,
                    "learning_rate": lr,
                    "grad_norm": grad_norm,
                    "tokens_per_second": tokens_per_sec,
                    "vram_gb": vram_gb,
                    "step": step,
                })

            total_loss = 0.0
            total_tokens = 0
            start_time = time.time()

        # Compute validation PPL and generate samples periodically
        if step % config.sample_interval == 0 and is_main:
            val_ppl, val_loss = compute_val_ppl(model, val_dataloader, device, config)
            print(f"\n  VAL PPL: {val_ppl:.2f} | VAL Loss: {val_loss:.4f}")

            if HAS_WANDB and config.wandb_project:
                wandb.log({
                    "val_ppl": val_ppl,
                    "val_loss": val_loss,
                    "step": step,
                })

            generate_samples(model, tokenizer, device, config, step)

        # Save checkpoint
        if step % config.save_interval == 0 and is_main:
            checkpoint_path = output_dir / f"checkpoint_{step}.pt"
            save_model = model.module if is_distributed else model

            torch.save({
                "step": step,
                "model_state_dict": save_model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "config": asdict(config),
            }, checkpoint_path)

            print(f"  Saved checkpoint: {checkpoint_path}")

    # Final save
    if is_main:
        final_path = output_dir / "final_model.pt"
        save_model = model.module if is_distributed else model
        torch.save({
            "step": step,
            "model_state_dict": save_model.state_dict(),
            "config": asdict(config),
        }, final_path)
        print(f"\n  Training complete! Final model: {final_path}")

    # Cleanup
    if HAS_WANDB and is_main:
        wandb.finish()

    cleanup_distributed()


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Train Hybrid 7B on FineWeb")

    # Model
    parser.add_argument("--embed_dim", type=int, default=4096)
    parser.add_argument("--num_layers", type=int, default=32)
    parser.add_argument("--num_heads", type=int, default=32)
    parser.add_argument("--ff_dim", type=int, default=11008)
    parser.add_argument("--max_seq_len", type=int, default=1024)

    # Hybrid config
    parser.add_argument("--local_layers", type=int, default=16,
                        help="Number of local-only layers (16:16 split for 32 layers)")
    parser.add_argument("--window_size", type=int, default=256)
    parser.add_argument("--cosine_mode", type=str, default="standard",
                        choices=["standard", "shifted", "complex"])
    parser.add_argument("--decay_gamma", type=float, default=1.0)

    # Training
    parser.add_argument("--batch_size", type=int, default=2,
                        help="Per-GPU batch size (2-4 for A100 80GB)")
    parser.add_argument("--gradient_accumulation", type=int, default=8,
                        help="Gradient accumulation steps")
    parser.add_argument("--learning_rate", type=float, default=3e-4)
    parser.add_argument("--max_steps", type=int, default=100000)
    parser.add_argument("--warmup_steps", type=int, default=2000)
    parser.add_argument("--grad_clip", type=float, default=1.0)

    # Memory optimization
    parser.add_argument("--no_mixed_precision", action="store_true")
    parser.add_argument("--no_gradient_checkpointing", action="store_true")
    parser.add_argument("--no_8bit_optimizer", action="store_true",
                        help="Disable 8-bit optimizer (requires batch_size=1 on A100 80GB)")
    parser.add_argument("--no_compile", action="store_true",
                        help="Disable torch.compile() (use if seeing compilation errors)")

    # Dataset
    parser.add_argument("--dataset_name", type=str, default="HuggingFaceFW/fineweb")
    parser.add_argument("--dataset_subset", type=str, default="sample-10BT")

    # Output
    parser.add_argument("--output_dir", type=str, default="./checkpoints/hybrid_7b")
    parser.add_argument("--wandb_project", type=str, default="hybrid-7b-fineweb")
    parser.add_argument("--wandb_run_name", type=str, default=None)

    # Other
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    config = TrainingConfig(
        embed_dim=args.embed_dim,
        num_layers=args.num_layers,
        num_heads=args.num_heads,
        ff_dim=args.ff_dim,
        max_seq_len=args.max_seq_len,
        local_layers=args.local_layers,
        window_size=args.window_size,
        cosine_mode=args.cosine_mode,
        decay_gamma=args.decay_gamma,
        batch_size=args.batch_size,
        gradient_accumulation=args.gradient_accumulation,
        learning_rate=args.learning_rate,
        max_steps=args.max_steps,
        warmup_steps=args.warmup_steps,
        grad_clip=args.grad_clip,
        use_mixed_precision=not args.no_mixed_precision,
        use_gradient_checkpointing=not args.no_gradient_checkpointing,
        use_8bit_optimizer=not args.no_8bit_optimizer,
        use_compile=not args.no_compile,
        dataset_name=args.dataset_name,
        dataset_subset=args.dataset_subset,
        output_dir=args.output_dir,
        wandb_project=args.wandb_project,
        wandb_run_name=args.wandb_run_name,
        seed=args.seed,
    )

    train(config)


if __name__ == "__main__":
    main()
