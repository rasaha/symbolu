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

# GPU profiles (comprehensive list)
GPU_PROFILES = {
    # Blackwell (2024+)
    "B200": {"vram": 192, "bf16": True, "flash": True, "fp8": True, "bandwidth": 8000, "tflops_bf16": 2250},
    "B100": {"vram": 192, "bf16": True, "flash": True, "fp8": True, "bandwidth": 8000, "tflops_bf16": 1800},
    "GB200": {"vram": 384, "bf16": True, "flash": True, "fp8": True, "bandwidth": 16000, "tflops_bf16": 4500},

    # Hopper (2023+)
    "H200": {"vram": 141, "bf16": True, "flash": True, "fp8": True, "bandwidth": 4800, "tflops_bf16": 990},
    "H100-SXM": {"vram": 80, "bf16": True, "flash": True, "fp8": True, "bandwidth": 3350, "tflops_bf16": 990},
    "H100-PCIe": {"vram": 80, "bf16": True, "flash": True, "fp8": True, "bandwidth": 2000, "tflops_bf16": 760},
    "H100-NVL": {"vram": 188, "bf16": True, "flash": True, "fp8": True, "bandwidth": 7800, "tflops_bf16": 1980},

    # Ampere (2020+)
    "A100-80GB-SXM": {"vram": 80, "bf16": True, "flash": True, "fp8": False, "bandwidth": 2039, "tflops_bf16": 312},
    "A100-80GB-PCIe": {"vram": 80, "bf16": True, "flash": True, "fp8": False, "bandwidth": 1935, "tflops_bf16": 312},
    "A100-40GB": {"vram": 40, "bf16": True, "flash": True, "fp8": False, "bandwidth": 1555, "tflops_bf16": 312},
    "A6000": {"vram": 48, "bf16": True, "flash": True, "fp8": False, "bandwidth": 768, "tflops_bf16": 155},
    "A40": {"vram": 48, "bf16": True, "flash": True, "fp8": False, "bandwidth": 696, "tflops_bf16": 150},
    "A30": {"vram": 24, "bf16": True, "flash": True, "fp8": False, "bandwidth": 933, "tflops_bf16": 165},
    "A10": {"vram": 24, "bf16": True, "flash": True, "fp8": False, "bandwidth": 600, "tflops_bf16": 125},

    # Ada Lovelace (Consumer)
    "RTX 4090": {"vram": 24, "bf16": True, "flash": True, "fp8": False, "bandwidth": 1008, "tflops_bf16": 165},
    "RTX 4080": {"vram": 16, "bf16": True, "flash": True, "fp8": False, "bandwidth": 717, "tflops_bf16": 97},
    "RTX 4070Ti": {"vram": 12, "bf16": True, "flash": True, "fp8": False, "bandwidth": 504, "tflops_bf16": 80},

    # Ampere (Consumer)
    "RTX 3090": {"vram": 24, "bf16": False, "flash": False, "fp8": False, "bandwidth": 936, "tflops_bf16": 71},
    "RTX 3080": {"vram": 10, "bf16": False, "flash": False, "fp8": False, "bandwidth": 760, "tflops_bf16": 60},

    # Volta
    "V100-32GB": {"vram": 32, "bf16": False, "flash": False, "fp8": False, "bandwidth": 900, "tflops_bf16": 28},
    "V100-16GB": {"vram": 16, "bf16": False, "flash": False, "fp8": False, "bandwidth": 900, "tflops_bf16": 28},

    # Turing
    "T4": {"vram": 16, "bf16": False, "flash": False, "fp8": False, "bandwidth": 300, "tflops_bf16": 8},

    # Multi-GPU configurations
    "2xH100": {"vram": 160, "bf16": True, "flash": True, "fp8": True, "bandwidth": 6700, "tflops_bf16": 1980},
    "4xA100-80GB": {"vram": 320, "bf16": True, "flash": True, "fp8": False, "bandwidth": 8000, "tflops_bf16": 1248},
    "8xA100-80GB": {"vram": 640, "bf16": True, "flash": True, "fp8": False, "bandwidth": 16000, "tflops_bf16": 2496},
    "8xH100": {"vram": 640, "bf16": True, "flash": True, "fp8": True, "bandwidth": 26800, "tflops_bf16": 7920},
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


def interactive_mode():
    """Interactive mode to gather system parameters and generate optimal config."""

    print("\n" + "=" * 70)
    print("   TRAINING CONFIGURATION OPTIMIZER - Interactive Mode")
    print("=" * 70)

    # Step 1: GPU Selection
    print("\n  Step 1: Select your GPU")
    print("  " + "-" * 40)

    gpu_categories = {
        "1": ("Blackwell (Latest)", ["B200", "B100", "GB200"]),
        "2": ("Hopper", ["H200", "H100-SXM", "H100-PCIe", "H100-NVL"]),
        "3": ("Ampere Datacenter", ["A100-80GB-SXM", "A100-80GB-PCIe", "A100-40GB", "A6000", "A40", "A30", "A10"]),
        "4": ("Consumer (Ada/Ampere)", ["RTX 4090", "RTX 4080", "RTX 4070Ti", "RTX 3090", "RTX 3080"]),
        "5": ("Older/Other", ["V100-32GB", "V100-16GB", "T4"]),
        "6": ("Multi-GPU", ["2xH100", "4xA100-80GB", "8xA100-80GB", "8xH100"]),
        "7": ("Custom", []),
    }

    for key, (name, _) in gpu_categories.items():
        print(f"    [{key}] {name}")

    category_choice = input("\n  Select category [1-7]: ").strip()

    if category_choice == "7":
        # Custom GPU
        gpu_name = input("  Enter GPU name: ").strip()
        vram_gb = float(input("  Enter VRAM (GB): ").strip())
        bf16 = input("  Supports BF16? [y/n]: ").strip().lower() == 'y'
        flash = input("  Supports Flash Attention? [y/n]: ").strip().lower() == 'y'
        fp8 = input("  Supports FP8? [y/n]: ").strip().lower() == 'y'
        bandwidth = float(input("  Memory bandwidth (GB/s, estimate if unknown): ").strip() or "1000")
        tflops = float(input("  BF16 TFLOPS (estimate if unknown): ").strip() or "100")

        gpu_profile = {
            "vram": vram_gb,
            "bf16": bf16,
            "flash": flash,
            "fp8": fp8,
            "bandwidth": bandwidth,
            "tflops_bf16": tflops
        }
    else:
        _, gpu_list = gpu_categories.get(category_choice, ("", []))
        if not gpu_list:
            print("  Invalid selection, using A100-80GB-PCIe")
            gpu_name = "A100-80GB-PCIe"
        else:
            print(f"\n  Available GPUs:")
            for i, gpu in enumerate(gpu_list, 1):
                profile = GPU_PROFILES[gpu]
                print(f"    [{i}] {gpu}: {profile['vram']}GB VRAM, {profile['tflops_bf16']} TFLOPS")

            gpu_choice = int(input(f"\n  Select GPU [1-{len(gpu_list)}]: ").strip() or "1") - 1
            gpu_name = gpu_list[min(gpu_choice, len(gpu_list) - 1)]

        gpu_profile = GPU_PROFILES[gpu_name]

    print(f"\n  Selected: {gpu_name}")
    print(f"    VRAM: {gpu_profile['vram']} GB")
    print(f"    BF16: {'Yes' if gpu_profile['bf16'] else 'No'}")
    print(f"    FP8: {'Yes' if gpu_profile.get('fp8', False) else 'No'}")

    # Step 2: Context Length
    print("\n  Step 2: Select target context length")
    print("  " + "-" * 40)

    context_options = [
        ("1", 1024, "Short - Fast training, good for testing"),
        ("2", 2048, "Standard - Good balance"),
        ("3", 4096, "Medium - Typical LLM context"),
        ("4", 8192, "Long - Extended context"),
        ("5", 16384, "Very Long - Requires more VRAM"),
        ("6", 32768, "Ultra Long - 32K context"),
        ("7", 65536, "Extreme - 64K context"),
        ("8", 131072, "Maximum - 128K context"),
        ("9", 0, "Custom length"),
    ]

    for key, length, desc in context_options:
        if length > 0:
            print(f"    [{key}] {length:,} tokens - {desc}")
        else:
            print(f"    [{key}] Custom")

    ctx_choice = input("\n  Select context length [1-9]: ").strip() or "1"

    if ctx_choice == "9":
        target_context = int(input("  Enter custom context length: ").strip())
    else:
        idx = int(ctx_choice) - 1
        target_context = context_options[min(idx, len(context_options) - 1)][1]
        if target_context == 0:
            target_context = int(input("  Enter custom context length: ").strip())

    print(f"\n  Selected context: {target_context:,} tokens")

    # Step 3: Model Size
    print("\n  Step 3: Select model size")
    print("  " + "-" * 40)

    model_options = [
        ("1", "tiny", "10M params - Testing only"),
        ("2", "small", "56M params - Quick experiments"),
        ("3", "medium", "143M params - Good balance (recommended)"),
        ("4", "large", "350M params - Better quality"),
        ("5", "xl", "1.3B params - High quality, slow"),
    ]

    for key, size, desc in model_options:
        print(f"    [{key}] {size}: {desc}")

    model_choice = input("\n  Select model size [1-5]: ").strip() or "3"
    model_size = model_options[min(int(model_choice) - 1, len(model_options) - 1)][1]

    print(f"\n  Selected model: {model_size}")

    # Step 4: Training Goal
    print("\n  Step 4: Training goal")
    print("  " + "-" * 40)

    goal_options = [
        ("1", "fast", "Fast convergence - Higher LR, fewer steps"),
        ("2", "balanced", "Balanced - Good quality, reasonable time"),
        ("3", "quality", "Best quality - Lower LR, more steps"),
        ("4", "niah", "NIAH optimized - Retrieval-focused training"),
    ]

    for key, goal, desc in goal_options:
        print(f"    [{key}] {desc}")

    goal_choice = input("\n  Select goal [1-4]: ").strip() or "2"
    goal = goal_options[min(int(goal_choice) - 1, len(goal_options) - 1)][1]

    # Step 5: Dataset
    print("\n  Step 5: Dataset")
    print("  " + "-" * 40)

    recommended_dataset = DATASET_BY_CONTEXT.get(target_context, ("c4", ""))[0]
    print(f"  Recommended for {target_context:,} context: {recommended_dataset}")

    dataset_options = [
        ("1", "wikitext103", "WikiText-103 (103M tokens) - Good for ≤8K context"),
        ("2", "wikitext2", "WikiText-2 (2M tokens) - Quick testing only"),
        ("3", "c4", "C4 (300B+ tokens) - Best for >8K context"),
        ("4", "custom", "Custom dataset path"),
    ]

    for key, ds, desc in dataset_options:
        marker = " (recommended)" if ds == recommended_dataset else ""
        print(f"    [{key}] {desc}{marker}")

    ds_choice = input(f"\n  Select dataset [1-4, default={recommended_dataset}]: ").strip()

    if ds_choice == "4":
        dataset = "custom"
        dataset_path = input("  Enter dataset path: ").strip()
    elif ds_choice:
        dataset = dataset_options[min(int(ds_choice) - 1, len(dataset_options) - 1)][1]
        dataset_path = None
    else:
        dataset = recommended_dataset
        dataset_path = None

    # Create GPU info object
    gpu_info = GPUInfo(
        name=gpu_name,
        vram_gb=gpu_profile["vram"],
        compute_capability=(9, 0) if gpu_profile.get("fp8") else (8, 0) if gpu_profile["bf16"] else (7, 0),
        supports_bf16=gpu_profile["bf16"],
        supports_flash=gpu_profile["flash"],
    )

    # Generate optimized config
    config = get_optimal_config(target_context, model_size, gpu_info)

    # Override dataset if different from default
    config.dataset = dataset

    # Apply goal-specific adjustments
    if goal == "fast":
        config.learning_rate *= 1.5
        config.max_steps = int(config.max_steps * 0.6)
        config.warmup_steps = int(config.warmup_steps * 0.5)
    elif goal == "quality":
        config.learning_rate *= 0.7
        config.max_steps = int(config.max_steps * 1.5)
    elif goal == "niah":
        config.local_layers = min(6, config.local_layers + 2)  # More local layers for retrieval
        config.window_size = min(1024, config.window_size * 2)

    # Recalculate estimates based on actual GPU
    tflops = gpu_profile.get("tflops_bf16", 100)
    base_tflops = 312  # A100 baseline
    speed_factor = tflops / base_tflops
    config.estimated_time_hours /= speed_factor

    # Print summary
    print("\n")
    print_config_summary(config, gpu_info)

    # Ask to save
    save_choice = input("  Save to shell script? [y/N]: ").strip().lower()
    if save_choice == 'y':
        output_file = f"train_{target_context // 1024}k_{model_size}.sh"
        output_file = input(f"  Filename [{output_file}]: ").strip() or output_file

        with open(output_file, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Optimized training for {target_context:,} context on {gpu_name}\n")
            f.write(f"# Generated by optimize_training.py\n")
            f.write(f"# Estimated time: {config.estimated_time_hours:.1f} hours\n\n")
            f.write("export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True\n")
            f.write("export TOKENIZERS_PARALLELISM=false\n\n")
            f.write(config_to_command(config) + "\n")

        print(f"\n  Saved to: {output_file}")
        print(f"  Run with: bash {output_file}")

    return config


def main():
    parser = argparse.ArgumentParser(
        description="Optimize training configuration based on system specs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--target_context", type=int, default=None,
        help="Target context length"
    )
    parser.add_argument(
        "--model_size", type=str, default="medium",
        choices=["tiny", "small", "medium", "large", "xl"],
        help="Model size (default: medium)"
    )
    parser.add_argument(
        "--gpu", type=str, default=None,
        choices=list(GPU_PROFILES.keys()),
        help="GPU type (if not auto-detecting)"
    )
    parser.add_argument(
        "--vram", type=float, default=None,
        help="Override VRAM in GB"
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Auto-detect GPU and generate config"
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Interactive mode - asks for all parameters"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Generate configs for all context lengths"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Save command to shell script"
    )
    parser.add_argument(
        "--list-gpus", action="store_true",
        help="List all supported GPU profiles"
    )

    args = parser.parse_args()

    # List GPUs
    if args.list_gpus:
        print("\n  Supported GPU Profiles:")
        print("  " + "-" * 60)
        for name, profile in sorted(GPU_PROFILES.items(), key=lambda x: -x[1]["vram"]):
            print(f"    {name:20} {profile['vram']:4}GB  {profile['tflops_bf16']:5} TFLOPS  "
                  f"BF16:{profile['bf16']}  FP8:{profile.get('fp8', False)}")
        return

    # Interactive mode
    if args.interactive or (args.target_context is None and not args.auto and not args.all):
        interactive_mode()
        return

    # Detect or use specified GPU
    if args.gpu:
        profile = GPU_PROFILES[args.gpu]
        gpu_info = GPUInfo(
            name=args.gpu,
            vram_gb=args.vram or profile["vram"],
            compute_capability=(9, 0) if profile.get("fp8") else (8, 0) if profile["bf16"] else (7, 0),
            supports_bf16=profile["bf16"],
            supports_flash=profile["flash"],
        )
    else:
        gpu_info = detect_gpu()
        if args.vram and gpu_info:
            gpu_info.vram_gb = args.vram

    if args.all:
        generate_all_configs()
        return

    # Generate config
    target_context = args.target_context or 1024
    config = get_optimal_config(target_context, args.model_size, gpu_info)

    # Print summary
    print_config_summary(config, gpu_info)

    # Save to script if requested
    if args.output:
        with open(args.output, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Optimized training for {target_context} context\n")
            f.write(f"# Generated by optimize_training.py\n\n")
            f.write("export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True\n")
            f.write("export TOKENIZERS_PARALLELISM=false\n\n")
            f.write(config_to_command(config) + "\n")
        print(f"  Saved to: {args.output}")
        print(f"  Run with: bash {args.output}\n")


if __name__ == "__main__":
    main()
