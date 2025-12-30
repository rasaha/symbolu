#!/usr/bin/env python3
"""
Training Configuration Optimizer
=================================

Automatically determines optimal training parameters based on:
- GPU type and VRAM
- Target context length
- Model size
- Dataset choice

Usage:
    python optimize_training.py --target_context 1024
    python optimize_training.py --target_context 131072 --model_size large
    python optimize_training.py --auto  # Auto-detect best config for your GPU

Output: Ready-to-run training command with optimal parameters.
"""

import argparse
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

# Try to import torch for GPU detection
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


@dataclass
class GPUInfo:
    """GPU specifications."""
    name: str
    vram_gb: float
    compute_capability: Tuple[int, int]
    supports_bf16: bool
    supports_flash: bool


@dataclass
class TrainingConfig:
    """Optimized training configuration."""
    model_size: str
    model_type: str
    dataset: str
    max_seq_len: int
    batch_size: int
    gradient_accumulation: int
    learning_rate: float
    warmup_steps: int
    max_steps: int
    eval_every: int
    log_every: int
    save_every: int
    mixed_precision: str
    gradient_checkpointing: bool
    chunk_size: int
    local_layers: int
    window_size: int
    checkpoint_dir: str

    # Computed
    effective_batch_tokens: int = 0
    estimated_vram_gb: float = 0
    estimated_time_hours: float = 0


# Model size configurations
MODEL_CONFIGS = {
    "tiny": {"params_m": 10, "embed": 256, "layers": 4, "vram_per_1k": 0.5},
    "small": {"params_m": 56, "embed": 512, "layers": 8, "vram_per_1k": 1.2},
    "medium": {"params_m": 143, "embed": 768, "layers": 12, "vram_per_1k": 2.5},
    "large": {"params_m": 350, "embed": 1024, "layers": 24, "vram_per_1k": 5.0},
    "xl": {"params_m": 1300, "embed": 2048, "layers": 24, "vram_per_1k": 12.0},
}

# GPU profiles
GPU_PROFILES = {
    "A100-80GB": {"vram": 80, "bf16": True, "flash": True, "bandwidth": 2000},
    "A100-40GB": {"vram": 40, "bf16": True, "flash": True, "bandwidth": 1555},
    "H100": {"vram": 80, "bf16": True, "flash": True, "bandwidth": 3350},
    "A6000": {"vram": 48, "bf16": True, "flash": True, "bandwidth": 768},
    "RTX 4090": {"vram": 24, "bf16": True, "flash": True, "bandwidth": 1008},
    "RTX 3090": {"vram": 24, "bf16": False, "flash": False, "bandwidth": 936},
    "V100-32GB": {"vram": 32, "bf16": False, "flash": False, "bandwidth": 900},
    "V100-16GB": {"vram": 16, "bf16": False, "flash": False, "bandwidth": 900},
    "T4": {"vram": 16, "bf16": False, "flash": False, "bandwidth": 300},
}

# Dataset recommendations by context length
DATASET_BY_CONTEXT = {
    1024: ("wikitext103", "~100K sequences"),
    2048: ("wikitext103", "~50K sequences"),
    4096: ("wikitext103", "~25K sequences"),
    8192: ("wikitext103", "~12K sequences"),
    16384: ("c4", "WikiText-103 too small"),
    32768: ("c4", "Need streaming dataset"),
    65536: ("c4", "Need streaming dataset"),
    131072: ("c4", "Need streaming dataset"),
}


def detect_gpu() -> Optional[GPUInfo]:
    """Detect GPU and return specifications."""
    if not TORCH_AVAILABLE:
        return None

    if not torch.cuda.is_available():
        return None

    device = torch.cuda.current_device()
    name = torch.cuda.get_device_name(device)
    vram_bytes = torch.cuda.get_device_properties(device).total_memory
    vram_gb = vram_bytes / (1024**3)

    cc = torch.cuda.get_device_capability(device)
    supports_bf16 = cc[0] >= 8  # Ampere+
    supports_flash = cc[0] >= 8 and cc[1] >= 0

    return GPUInfo(
        name=name,
        vram_gb=vram_gb,
        compute_capability=cc,
        supports_bf16=supports_bf16,
        supports_flash=supports_flash,
    )


def estimate_vram(
    model_size: str,
    seq_len: int,
    batch_size: int,
    gradient_checkpointing: bool = False,
) -> float:
    """Estimate VRAM usage in GB."""
    config = MODEL_CONFIGS[model_size]

    # Base model memory
    model_vram = config["params_m"] * 4 / 1000  # FP32 params in GB

    # Activation memory (rough estimate)
    # Scales with batch_size * seq_len * embed_dim * layers
    activation_factor = 1.0 if gradient_checkpointing else 3.0
    activation_vram = (
        batch_size * seq_len * config["embed"] * config["layers"]
        * 4 / (1024**3) * activation_factor
    )

    # Optimizer states (AdamW: 2x model size)
    optimizer_vram = model_vram * 2

    # Gradients
    gradient_vram = model_vram

    # Total with 20% buffer
    total = (model_vram + activation_vram + optimizer_vram + gradient_vram) * 1.2

    return total


def find_optimal_batch_size(
    model_size: str,
    seq_len: int,
    vram_gb: float,
    gradient_checkpointing: bool = False,
) -> Tuple[int, int]:
    """Find optimal batch_size and gradient_accumulation."""

    # Target effective batch size (in sequences)
    target_effective_batch = 64

    # Try decreasing batch sizes
    for batch_size in [128, 64, 32, 16, 8, 4, 2, 1]:
        estimated_vram = estimate_vram(
            model_size, seq_len, batch_size, gradient_checkpointing
        )

        if estimated_vram < vram_gb * 0.85:  # Leave 15% headroom
            grad_accum = max(1, target_effective_batch // batch_size)
            return batch_size, grad_accum

    # Fallback: batch_size=1 with high accumulation
    return 1, target_effective_batch


def get_optimal_config(
    target_context: int,
    model_size: str = "medium",
    gpu_info: Optional[GPUInfo] = None,
) -> TrainingConfig:
    """Generate optimal training configuration."""

    # Get GPU info
    if gpu_info is None:
        gpu_info = detect_gpu()

    if gpu_info is None:
        # Default to A100-80GB assumptions
        vram_gb = 80
        supports_bf16 = True
    else:
        vram_gb = gpu_info.vram_gb
        supports_bf16 = gpu_info.supports_bf16

    # Determine if gradient checkpointing needed
    gradient_checkpointing = (
        target_context >= 8192 or
        model_size in ["large", "xl"] or
        vram_gb < 40
    )

    # Find optimal batch size
    batch_size, grad_accum = find_optimal_batch_size(
        model_size, target_context, vram_gb, gradient_checkpointing
    )

    # Determine chunk size for ultra-long contexts
    chunk_size = 0
    if target_context >= 65536:
        chunk_size = 4096
    elif target_context >= 32768:
        chunk_size = 8192

    # Dataset selection
    dataset_info = DATASET_BY_CONTEXT.get(
        target_context,
        ("c4", "Large context requires C4")
    )
    dataset = dataset_info[0]

    # Learning rate scaling
    # Larger effective batch = can use higher LR
    effective_batch = batch_size * grad_accum
    base_lr = 3e-4
    lr_scale = min(2.0, (effective_batch / 32) ** 0.5)
    learning_rate = base_lr * lr_scale

    # Scale down LR for longer contexts (more gradient noise)
    if target_context >= 32768:
        learning_rate *= 0.5
    if target_context >= 65536:
        learning_rate *= 0.5

    # Warmup and total steps
    warmup_steps = min(2000, max(200, target_context // 10))

    # More steps needed for longer contexts
    base_steps = 20000
    context_multiplier = max(1.0, (target_context / 1024) ** 0.5)
    max_steps = int(base_steps * context_multiplier)

    # Eval and logging frequency
    eval_every = max(500, max_steps // 40)
    log_every = max(50, max_steps // 400)
    save_every = max(2000, max_steps // 10)

    # Local attention settings (for hybrid)
    local_layers = 4
    window_size = min(512, target_context // 4)

    # Mixed precision
    mixed_precision = "bf16" if supports_bf16 else "fp16"

    # Checkpoint directory
    checkpoint_dir = f"checkpoints_{target_context // 1024}k_{model_size}"

    config = TrainingConfig(
        model_size=model_size,
        model_type="hybrid",
        dataset=dataset,
        max_seq_len=target_context,
        batch_size=batch_size,
        gradient_accumulation=grad_accum,
        learning_rate=learning_rate,
        warmup_steps=warmup_steps,
        max_steps=max_steps,
        eval_every=eval_every,
        log_every=log_every,
        save_every=save_every,
        mixed_precision=mixed_precision,
        gradient_checkpointing=gradient_checkpointing,
        chunk_size=chunk_size,
        local_layers=local_layers,
        window_size=window_size,
        checkpoint_dir=checkpoint_dir,
    )

    # Compute derived values
    config.effective_batch_tokens = batch_size * grad_accum * target_context
    config.estimated_vram_gb = estimate_vram(
        model_size, target_context, batch_size, gradient_checkpointing
    )

    # Rough time estimate (assuming ~40K tok/s on A100)
    total_tokens = config.effective_batch_tokens * max_steps
    tok_per_sec = 40000 * (80 / max(vram_gb, 40))  # Scale by VRAM
    config.estimated_time_hours = total_tokens / tok_per_sec / 3600

    return config


def config_to_command(config: TrainingConfig) -> str:
    """Convert config to training command."""
    cmd_parts = [
        "python train.py",
        f"    --model_size {config.model_size}",
        f"    --model_type {config.model_type}",
        f"    --dataset {config.dataset}",
        f"    --max_seq_len {config.max_seq_len}",
        f"    --batch_size {config.batch_size}",
        f"    --gradient_accumulation {config.gradient_accumulation}",
        f"    --learning_rate {config.learning_rate:.1e}",
        f"    --warmup_steps {config.warmup_steps}",
        f"    --max_steps {config.max_steps}",
        f"    --eval_every {config.eval_every}",
        f"    --log_every {config.log_every}",
        f"    --save_every {config.save_every}",
        f"    --mixed_precision {config.mixed_precision}",
        f"    --local_layers {config.local_layers}",
        f"    --window_size {config.window_size}",
        f"    --checkpoint_dir {config.checkpoint_dir}",
    ]

    if config.gradient_checkpointing:
        cmd_parts.append("    --gradient_checkpointing")

    if config.chunk_size > 0:
        cmd_parts.append(f"    --chunk_size {config.chunk_size}")

    return " \\\n".join(cmd_parts)


def print_config_summary(config: TrainingConfig, gpu_info: Optional[GPUInfo] = None):
    """Print configuration summary."""
    print("\n" + "=" * 70)
    print("   OPTIMIZED TRAINING CONFIGURATION")
    print("=" * 70)

    if gpu_info:
        print(f"\n  GPU Detected: {gpu_info.name}")
        print(f"  VRAM: {gpu_info.vram_gb:.1f} GB")
        print(f"  BF16 Support: {'Yes' if gpu_info.supports_bf16 else 'No'}")

    print(f"\n  Target Context: {config.max_seq_len:,} tokens")
    print(f"  Model: {config.model_size} ({MODEL_CONFIGS[config.model_size]['params_m']}M params)")
    print(f"  Dataset: {config.dataset}")

    print(f"\n  Batch Configuration:")
    print(f"    Batch Size: {config.batch_size}")
    print(f"    Gradient Accumulation: {config.gradient_accumulation}")
    print(f"    Effective Batch: {config.batch_size * config.gradient_accumulation} sequences")
    print(f"    Tokens per Step: {config.effective_batch_tokens:,}")

    print(f"\n  Training Schedule:")
    print(f"    Learning Rate: {config.learning_rate:.1e}")
    print(f"    Warmup Steps: {config.warmup_steps:,}")
    print(f"    Max Steps: {config.max_steps:,}")
    print(f"    Total Tokens: {config.effective_batch_tokens * config.max_steps:,}")

    print(f"\n  Memory Optimization:")
    print(f"    Gradient Checkpointing: {'Yes' if config.gradient_checkpointing else 'No'}")
    print(f"    Chunk Size: {config.chunk_size if config.chunk_size > 0 else 'Disabled'}")
    print(f"    Estimated VRAM: {config.estimated_vram_gb:.1f} GB")

    print(f"\n  Estimated Training Time: {config.estimated_time_hours:.1f} hours")

    # Dataset recommendation
    dataset_info = DATASET_BY_CONTEXT.get(config.max_seq_len, ("c4", ""))
    if dataset_info[1]:
        print(f"\n  Dataset Note: {dataset_info[1]}")

    print("\n" + "=" * 70)
    print("   TRAINING COMMAND")
    print("=" * 70 + "\n")
    print(config_to_command(config))
    print()


def generate_all_configs():
    """Generate configs for all standard context lengths."""
    gpu_info = detect_gpu()

    print("\n" + "=" * 70)
    print("   ALL OPTIMIZED CONFIGURATIONS")
    print("=" * 70)

    if gpu_info:
        print(f"\n  GPU: {gpu_info.name} ({gpu_info.vram_gb:.1f} GB)")

    contexts = [1024, 2048, 4096, 8192, 32768, 65536, 131072]

    for ctx in contexts:
        config = get_optimal_config(ctx, "medium", gpu_info)

        print(f"\n  {'='*60}")
        print(f"  Context: {ctx:,} tokens")
        print(f"  {'='*60}")
        print(f"  Dataset: {config.dataset}")
        print(f"  Batch: {config.batch_size} x {config.gradient_accumulation}")
        print(f"  LR: {config.learning_rate:.1e}")
        print(f"  Steps: {config.max_steps:,}")
        print(f"  VRAM: ~{config.estimated_vram_gb:.1f} GB")
        print(f"  Time: ~{config.estimated_time_hours:.1f} hours")
        print(f"\n  Command:")
        print(f"  {config_to_command(config).replace(chr(10), ' ')[:100]}...")


def main():
    parser = argparse.ArgumentParser(
        description="Optimize training configuration based on system specs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--target_context", type=int, default=1024,
        help="Target context length (default: 1024)"
    )
    parser.add_argument(
        "--model_size", type=str, default="medium",
        choices=["tiny", "small", "medium", "large", "xl"],
        help="Model size (default: medium)"
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Auto-detect GPU and show all recommended configs"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Generate configs for all context lengths"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Save command to shell script"
    )

    args = parser.parse_args()

    # Detect GPU
    gpu_info = detect_gpu()

    if args.all:
        generate_all_configs()
        return

    # Generate config
    config = get_optimal_config(args.target_context, args.model_size, gpu_info)

    # Print summary
    print_config_summary(config, gpu_info)

    # Save to script if requested
    if args.output:
        with open(args.output, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Optimized training for {args.target_context} context\n")
            f.write(f"# Generated by optimize_training.py\n\n")
            f.write("export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True\n")
            f.write("export TOKENIZERS_PARALLELISM=false\n\n")
            f.write(config_to_command(config) + "\n")
        print(f"  Saved to: {args.output}")
        print(f"  Run with: bash {args.output}\n")


if __name__ == "__main__":
    main()
