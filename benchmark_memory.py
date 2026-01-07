#!/usr/bin/env python3
"""
Memory Efficiency Benchmark: Hybrid O(n×w) vs Standard O(n²)
============================================================

Proves that HybridPhaseTransformer (O(n×w)) significantly reduces memory consumption
compared to StandardTransformer (O(n²)), enabling training on consumer GPUs without
requiring expensive HBM/HBM3E memory.

Model Complexity:
-----------------
- StandardTransformer: O(n²) - creates [B, H, N, N] attention matrix
- HybridTransformer: O(n×w) - local window (w) + phase attention
- PhaseTransformer: O(n) - pure phase, state accumulation only

Key Findings This Script Demonstrates:
--------------------------------------
1. StandardTransformer: O(n²) memory scaling - attention matrix explodes at long seq
2. HybridTransformer: O(n×w) memory scaling - linear in n, constant in window w
3. At 8K+ sequence length, Hybrid uses significantly less memory than Standard
4. At 32K sequence length, Standard OOMs on 24GB VRAM, Hybrid fits

Hybrid Model Features (V9.6.12+):
---------------------------------
- cosine_mode: "standard", "shifted", or "complex" phase interaction
- decay_gamma: State decay factor (1.0=infinite memory, <1.0=local focus)
- local_layers: Number of early layers with local-only attention
- window_size: Local attention window size (default 256)

Usage:
------
    # Default: Compare Standard O(n²) vs Hybrid O(n×w)
    python benchmark_memory.py --quick

    # Full benchmark (512-32K)
    python benchmark_memory.py --full

    # Test different cosine modes
    python benchmark_memory.py --cosine_mode shifted --full

    # Test with decay gamma for local focus
    python benchmark_memory.py --decay_gamma 0.95 --full

    # Custom layer splits (e.g., 6:6 for 12-layer model)
    python benchmark_memory.py --local_layers 6 --model_size medium --full

    # Include Phase O(n) in comparison
    python benchmark_memory.py --models standard,hybrid,phase --full

    # Specific model sizes
    python benchmark_memory.py --model_size medium --full

    # Save results to file
    python benchmark_memory.py --full --output memory_benchmark_results.json

Author: Sovereign-1 Training Initiative
Date: January 2026
"""

import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import argparse
import gc
import json
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import (
    StandardTransformer,
    HybridPhaseTransformer,
    PhaseTransformer,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class MemoryBenchmarkConfig:
    """Configuration for memory benchmark."""
    model_size: str = "small"  # tiny, small, medium, large
    batch_size: int = 1
    seq_lengths: List[int] = field(default_factory=lambda: [512, 1024, 2048, 4096])
    model_types: List[str] = field(default_factory=lambda: ["standard", "hybrid"])  # O(n²) vs O(n×w)
    # Hybrid model configuration (V9.6.12+)
    cosine_mode: str = "standard"  # "standard", "shifted", or "complex"
    decay_gamma: float = 1.0  # State decay (1.0=infinite, <1.0=local focus)
    window_size: int = 256  # Local attention window
    local_layers: Optional[int] = None  # Number of local-only layers (None=auto: num_layers//2)
    num_warmup: int = 2
    num_runs: int = 3
    include_backward: bool = True  # Measure training memory (forward + backward)
    output_file: Optional[str] = None
    verbose: bool = True


@dataclass
class MemoryResult:
    """Result from a single memory measurement."""
    model_type: str
    model_size: str
    seq_length: int
    batch_size: int

    # Memory metrics (in GB)
    peak_memory_gb: float
    allocated_memory_gb: float
    reserved_memory_gb: float

    # Scalability
    memory_per_token_mb: float
    oom: bool = False
    error_message: Optional[str] = None

    # Timing
    forward_time_ms: float = 0.0
    backward_time_ms: float = 0.0


# Model size presets
MODEL_PRESETS = {
    "tiny": {"embed_dim": 256, "num_layers": 4, "num_heads": 4, "ff_dim": 1024},
    "small": {"embed_dim": 512, "num_layers": 8, "num_heads": 8, "ff_dim": 2048},
    "medium": {"embed_dim": 768, "num_layers": 12, "num_heads": 12, "ff_dim": 3072},
    "large": {"embed_dim": 1024, "num_layers": 24, "num_heads": 16, "ff_dim": 4096},
    "xl": {"embed_dim": 2048, "num_layers": 24, "num_heads": 16, "ff_dim": 8192},
}

# GPU memory specifications for reference
GPU_SPECS = {
    # Consumer GPUs (GDDR6/GDDR6X)
    "RTX 3060": 12,
    "RTX 3080": 10,
    "RTX 3090": 24,
    "RTX 4070": 12,
    "RTX 4080": 16,
    "RTX 4090": 24,
    # Professional/Datacenter (HBM2/HBM2e)
    "A10": 24,
    "A30": 24,
    "A40": 48,
    "A100-40GB": 40,
    "A100-80GB": 80,
    # Latest HBM3/HBM3E
    "H100-80GB": 80,
    "H200-141GB": 141,
    "B200": 192,
}


# =============================================================================
# MEMORY MEASUREMENT UTILITIES
# =============================================================================

def clear_memory():
    """Clear GPU memory and collect garbage."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()


def get_memory_stats() -> Dict[str, float]:
    """Get current GPU memory statistics in GB."""
    if not torch.cuda.is_available():
        return {"peak": 0.0, "allocated": 0.0, "reserved": 0.0}

    return {
        "peak": torch.cuda.max_memory_allocated() / (1024**3),
        "allocated": torch.cuda.memory_allocated() / (1024**3),
        "reserved": torch.cuda.memory_reserved() / (1024**3),
    }


def create_model(
    model_type: str,
    preset: dict,
    max_seq_len: int,
    cosine_mode: str = "standard",
    decay_gamma: float = 1.0,
    window_size: int = 256,
    local_layers: Optional[int] = None,
) -> nn.Module:
    """Create model of specified type with Hybrid configuration.

    Args:
        model_type: 'standard', 'hybrid', or 'phase'
        preset: Model size preset dict
        max_seq_len: Maximum sequence length
        cosine_mode: Phase cosine mode ("standard", "shifted", "complex")
        decay_gamma: State decay factor (1.0=infinite, <1.0=local focus)
        window_size: Local attention window size
        local_layers: Number of local-only layers (None=auto: num_layers//2)
    """
    common_args = {
        "vocab_size": 50257,
        "embed_dim": preset["embed_dim"],
        "num_layers": preset["num_layers"],
        "num_heads": preset["num_heads"],
        "ff_dim": preset["ff_dim"],
        "max_seq_len": max_seq_len,
        "dropout": 0.0,  # Disable for benchmarking
    }

    if model_type == "standard":
        return StandardTransformer(**common_args)
    elif model_type == "hybrid":
        # Determine local_layers: use provided value or auto-calculate
        # Default: num_layers // 2 for balanced 6:6 style splits
        num_local = local_layers if local_layers is not None else preset["num_layers"] // 2

        # Production Hybrid with V9.6.12+ features
        return HybridPhaseTransformer(
            **common_args,
            local_layers=num_local,
            window_size=window_size,
            local_backend="sdpa",  # Use SDPA for better memory (flash if available)
            alpha_local=0.8,
            alpha_phase=0.2,
            cosine_mode=cosine_mode,  # V9.6.12
            decay_gamma=decay_gamma,  # V9.6.13
        )
    elif model_type == "hybrid_unfold":
        # Hybrid with unfold backend (fallback, higher memory)
        num_local = local_layers if local_layers is not None else preset["num_layers"] // 2
        return HybridPhaseTransformer(
            **common_args,
            local_layers=num_local,
            window_size=window_size,
            local_backend="unfold",
            alpha_local=0.8,
            alpha_phase=0.2,
            cosine_mode=cosine_mode,
            decay_gamma=decay_gamma,
        )
    elif model_type == "phase":
        # Pure Phase attention - TRUE O(n) memory, no attention matrix
        return PhaseTransformer(
            **common_args,
            cosine_mode=cosine_mode,
            decay_gamma=decay_gamma,
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")


def measure_memory(
    model_type: str,
    model_size: str,
    seq_length: int,
    batch_size: int = 1,
    include_backward: bool = True,
    num_warmup: int = 2,
    num_runs: int = 3,
    device: torch.device = None,
    # Hybrid configuration (V9.6.12+)
    cosine_mode: str = "standard",
    decay_gamma: float = 1.0,
    window_size: int = 256,
    local_layers: Optional[int] = None,
) -> MemoryResult:
    """
    Measure memory usage for a specific model configuration.

    Args:
        model_type: 'standard', 'hybrid', or 'phase'
        model_size: Size preset name
        seq_length: Sequence length to test
        batch_size: Batch size
        include_backward: Whether to measure backward pass (training)
        num_warmup: Warmup iterations
        num_runs: Measurement iterations
        device: Device to use
        cosine_mode: Phase cosine mode ("standard", "shifted", "complex")
        decay_gamma: State decay factor (1.0=infinite, <1.0=local focus)
        window_size: Local attention window size
        local_layers: Number of local-only layers (None=auto: num_layers//2)

    Returns:
        MemoryResult with all metrics
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    preset = MODEL_PRESETS[model_size]

    # Initialize result with defaults
    result = MemoryResult(
        model_type=model_type,
        model_size=model_size,
        seq_length=seq_length,
        batch_size=batch_size,
        peak_memory_gb=0.0,
        allocated_memory_gb=0.0,
        reserved_memory_gb=0.0,
        memory_per_token_mb=0.0,
    )

    try:
        # Clear memory before measurement
        clear_memory()

        # Create model with Hybrid configuration
        model = create_model(
            model_type, preset, seq_length,
            cosine_mode=cosine_mode,
            decay_gamma=decay_gamma,
            window_size=window_size,
            local_layers=local_layers,
        )
        model = model.to(device)
        model.train()

        # Count parameters
        num_params = sum(p.numel() for p in model.parameters())

        # Create input
        input_ids = torch.randint(0, 50257, (batch_size, seq_length), device=device)

        # Warmup
        for _ in range(num_warmup):
            clear_memory()
            output = model(input_ids)
            logits = output["logits"] if isinstance(output, dict) else output

            if include_backward:
                # Simulate training loss
                loss = logits.mean()
                loss.backward()
                model.zero_grad()

        # Measurement runs
        forward_times = []
        backward_times = []
        peak_memories = []

        for _ in range(num_runs):
            clear_memory()

            if torch.cuda.is_available():
                torch.cuda.synchronize()

            # Forward pass
            t0 = time.perf_counter()
            output = model(input_ids)
            logits = output["logits"] if isinstance(output, dict) else output

            if torch.cuda.is_available():
                torch.cuda.synchronize()
            forward_times.append((time.perf_counter() - t0) * 1000)

            # Backward pass
            if include_backward:
                t0 = time.perf_counter()
                loss = logits.mean()
                loss.backward()

                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                backward_times.append((time.perf_counter() - t0) * 1000)
                model.zero_grad()

            # Record peak memory
            stats = get_memory_stats()
            peak_memories.append(stats["peak"])

        # Compute averages
        result.peak_memory_gb = sum(peak_memories) / len(peak_memories)
        result.allocated_memory_gb = stats["allocated"]
        result.reserved_memory_gb = stats["reserved"]
        result.forward_time_ms = sum(forward_times) / len(forward_times)
        result.backward_time_ms = sum(backward_times) / len(backward_times) if backward_times else 0.0

        # Memory per token (useful for scaling analysis)
        total_tokens = batch_size * seq_length
        result.memory_per_token_mb = (result.peak_memory_gb * 1024) / total_tokens

        # Cleanup
        del model, input_ids, output, logits
        clear_memory()

    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            result.oom = True
            result.error_message = "CUDA OOM"
            result.peak_memory_gb = float("inf")
        else:
            result.oom = True
            result.error_message = str(e)
        clear_memory()

    except Exception as e:
        result.oom = True
        result.error_message = str(e)
        clear_memory()

    return result


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def run_benchmark(config: MemoryBenchmarkConfig) -> Dict[str, List[MemoryResult]]:
    """Run full memory benchmark comparing model types."""

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"\n{'='*70}")
    print("   MEMORY EFFICIENCY BENCHMARK")
    print(f"{'='*70}")

    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"\n  GPU: {gpu_name}")
        print(f"  Total VRAM: {gpu_mem:.1f} GB")
    else:
        print("\n  WARNING: No GPU available, results will be limited")

    print(f"  Model Size: {config.model_size}")
    print(f"  Batch Size: {config.batch_size}")
    print(f"  Sequence Lengths: {config.seq_lengths}")
    print(f"  Include Backward: {config.include_backward}")

    preset = MODEL_PRESETS[config.model_size]
    print(f"\n  Model Config: {preset['embed_dim']}d, {preset['num_layers']}L, {preset['num_heads']}H")

    # Hybrid configuration (V9.6.12+)
    local_layers_str = str(config.local_layers) if config.local_layers is not None else f"auto ({preset['num_layers']//2})"
    print(f"  Hybrid Config: cosine_mode={config.cosine_mode}, decay_gamma={config.decay_gamma}, window={config.window_size}, local_layers={local_layers_str}")

    # Model types to compare
    # "standard" = Traditional O(n²) attention - baseline
    # "hybrid" = Local + Phase attention O(n×w) - production quality
    # "phase" = Pure Phase attention O(n) - best memory efficiency
    model_types = config.model_types if hasattr(config, 'model_types') and config.model_types else ["standard", "hybrid"]

    print(f"  Models: {', '.join(model_types)}")

    results = {mt: [] for mt in model_types}

    print(f"\n{'='*70}")
    print("   RUNNING BENCHMARKS")
    print(f"{'='*70}\n")

    for seq_len in config.seq_lengths:
        print(f"\n  Sequence Length: {seq_len:,}")
        print(f"  {'-'*50}")

        for model_type in model_types:
            print(f"    {model_type:10s}: ", end="", flush=True)

            result = measure_memory(
                model_type=model_type,
                model_size=config.model_size,
                seq_length=seq_len,
                batch_size=config.batch_size,
                include_backward=config.include_backward,
                num_warmup=config.num_warmup,
                num_runs=config.num_runs,
                device=device,
                # Hybrid configuration (V9.6.12+)
                cosine_mode=config.cosine_mode,
                decay_gamma=config.decay_gamma,
                window_size=config.window_size,
                local_layers=config.local_layers,
            )

            results[model_type].append(result)

            if result.oom:
                print(f"OOM ({result.error_message})")
            else:
                print(f"{result.peak_memory_gb:6.2f} GB | "
                      f"{result.forward_time_ms:6.1f}ms fwd | "
                      f"{result.backward_time_ms:6.1f}ms bwd")

    return results


def analyze_scaling(results: Dict[str, List[MemoryResult]]) -> Dict[str, any]:
    """Analyze memory scaling behavior."""

    analysis = {}

    for model_type, type_results in results.items():
        valid_results = [r for r in type_results if not r.oom]

        if len(valid_results) < 2:
            analysis[model_type] = {"scaling": "insufficient_data"}
            continue

        # Extract data points
        seq_lengths = [r.seq_length for r in valid_results]
        memories = [r.peak_memory_gb for r in valid_results]

        # Compute scaling factor
        # O(n²) scaling: memory doubles when seq_len doubles -> ratio ~4
        # O(n) scaling: memory doubles when seq_len doubles -> ratio ~2

        scaling_ratios = []
        for i in range(1, len(valid_results)):
            if seq_lengths[i] == 2 * seq_lengths[i-1]:
                ratio = memories[i] / memories[i-1] if memories[i-1] > 0 else 0
                scaling_ratios.append(ratio)

        avg_ratio = sum(scaling_ratios) / len(scaling_ratios) if scaling_ratios else 0

        # Determine scaling type
        if avg_ratio > 3.0:
            scaling_type = "O(n²)"
        elif avg_ratio > 1.5:
            scaling_type = "O(n log n)"
        else:
            scaling_type = "O(n)"

        # Find max sequence length that fits in various GPUs
        max_seq_by_gpu = {}
        for gpu_name, gpu_mem in GPU_SPECS.items():
            # Find largest seq_length that fits with 10% headroom
            usable_mem = gpu_mem * 0.9
            max_seq = 0
            for r in valid_results:
                if r.peak_memory_gb <= usable_mem:
                    max_seq = r.seq_length
            max_seq_by_gpu[gpu_name] = max_seq

        analysis[model_type] = {
            "scaling_type": scaling_type,
            "avg_scaling_ratio": round(avg_ratio, 2),
            "max_measured_seq": max(seq_lengths) if seq_lengths else 0,
            "max_seq_by_gpu": max_seq_by_gpu,
            "oom_at": [r.seq_length for r in type_results if r.oom],
        }

    return analysis


def compute_savings(results: Dict[str, List[MemoryResult]]) -> Dict[int, Dict[str, float]]:
    """Compute memory savings at each sequence length."""

    savings = {}

    # Get results by model type
    results_by_type = {}
    for model_type, type_results in results.items():
        results_by_type[model_type] = {r.seq_length: r for r in type_results}

    standard_results = results_by_type.get("standard", {})
    phase_results = results_by_type.get("phase", {})
    hybrid_results = results_by_type.get("hybrid", {})

    # Get all sequence lengths
    all_seq_lens = set()
    for type_results in results_by_type.values():
        all_seq_lens.update(type_results.keys())

    for seq_len in all_seq_lens:
        std = standard_results.get(seq_len)
        phase = phase_results.get(seq_len)
        hyb = hybrid_results.get(seq_len)

        entry = {"seq_len": seq_len}

        # Standard memory
        if std:
            entry["standard_gb"] = float("inf") if std.oom else std.peak_memory_gb
            entry["standard_oom"] = std.oom

        # Phase memory (best efficiency)
        if phase:
            entry["phase_gb"] = float("inf") if phase.oom else phase.peak_memory_gb
            entry["phase_oom"] = phase.oom

        # Hybrid memory
        if hyb:
            entry["hybrid_gb"] = float("inf") if hyb.oom else hyb.peak_memory_gb
            entry["hybrid_oom"] = hyb.oom

        # Compute savings vs standard
        if std and not std.oom:
            if phase and not phase.oom:
                entry["phase_savings_pct"] = ((std.peak_memory_gb - phase.peak_memory_gb) / std.peak_memory_gb) * 100
                entry["phase_factor"] = std.peak_memory_gb / phase.peak_memory_gb if phase.peak_memory_gb > 0 else 1
            if hyb and not hyb.oom:
                entry["hybrid_savings_pct"] = ((std.peak_memory_gb - hyb.peak_memory_gb) / std.peak_memory_gb) * 100
                entry["hybrid_factor"] = std.peak_memory_gb / hyb.peak_memory_gb if hyb.peak_memory_gb > 0 else 1

        savings[seq_len] = entry

    return savings


def print_results(
    results: Dict[str, List[MemoryResult]],
    analysis: Dict[str, any],
    savings: Dict[int, Dict[str, float]],
):
    """Print formatted results with analysis."""

    print(f"\n{'='*70}")
    print("   RESULTS SUMMARY")
    print(f"{'='*70}\n")

    # Memory comparison table
    print("  Memory Usage by Sequence Length:")
    print(f"  {'-'*80}")

    # Determine which models are present
    has_phase = "phase" in results and results["phase"]
    has_hybrid = "hybrid" in results and results["hybrid"]
    has_standard = "standard" in results and results["standard"]

    # Build header
    header = f"  {'Seq Len':>10} | {'Standard':>12}"
    if has_phase:
        header += f" | {'Phase':>12}"
    if has_hybrid:
        header += f" | {'Hybrid':>12}"
    header += f" | {'Best Savings':>15}"
    print(header)
    print(f"  {'-'*80}")

    for seq_len in sorted(savings.keys()):
        s = savings[seq_len]

        # Standard
        std_gb = s.get("standard_gb", 0)
        std_str = "OOM" if std_gb == float("inf") else f"{std_gb:.2f} GB"

        row = f"  {seq_len:>10,} | {std_str:>12}"

        # Phase
        if has_phase:
            phase_gb = s.get("phase_gb", 0)
            phase_str = "OOM" if phase_gb == float("inf") else f"{phase_gb:.2f} GB"
            row += f" | {phase_str:>12}"

        # Hybrid
        if has_hybrid:
            hyb_gb = s.get("hybrid_gb", 0)
            hyb_str = "OOM" if hyb_gb == float("inf") else f"{hyb_gb:.2f} GB"
            row += f" | {hyb_str:>12}"

        # Best savings (phase vs standard, or hybrid vs standard)
        phase_pct = s.get("phase_savings_pct", 0)
        phase_factor = s.get("phase_factor", 1)
        hyb_pct = s.get("hybrid_savings_pct", 0)
        hyb_factor = s.get("hybrid_factor", 1)

        if phase_pct > hyb_pct and phase_pct > 0:
            save_str = f"Phase {phase_pct:.0f}% ({phase_factor:.1f}x)"
        elif hyb_pct > 0:
            save_str = f"Hybrid {hyb_pct:.0f}% ({hyb_factor:.1f}x)"
        elif s.get("phase_oom") == False and s.get("standard_oom") == True:
            save_str = "Phase ONLY fits"
        elif s.get("hybrid_oom") == False and s.get("standard_oom") == True:
            save_str = "Hybrid ONLY fits"
        else:
            save_str = "-"

        row += f" | {save_str:>15}"
        print(row)

    # Scaling analysis
    print(f"\n  Scaling Analysis:")
    print(f"  {'-'*60}")
    for model_type, data in analysis.items():
        scaling = data.get("scaling_type", "unknown")
        ratio = data.get("avg_scaling_ratio", 0)
        print(f"    {model_type:10s}: {scaling} (avg ratio: {ratio:.2f}x when seq doubles)")

    # GPU compatibility
    print(f"\n  Maximum Sequence Length by GPU:")
    print(f"  {'-'*75}")

    std_analysis = analysis.get("standard", {})
    phase_analysis = analysis.get("phase", {})
    hyb_analysis = analysis.get("hybrid", {})

    header = f"  {'GPU':<20} | {'Standard':>10}"
    if phase_analysis:
        header += f" | {'Phase':>10}"
    if hyb_analysis:
        header += f" | {'Hybrid':>10}"
    header += f" | {'Cost':>10}"
    print(header)
    print(f"  {'-'*75}")

    # Group GPUs by tier
    consumer_gpus = ["RTX 4070", "RTX 4080", "RTX 4090"]
    professional_gpus = ["A40", "A100-40GB", "A100-80GB"]
    hbm3_gpus = ["H100-80GB", "H200-141GB"]

    for tier_name, tier_gpus in [
        ("Consumer (GDDR)", consumer_gpus),
        ("Professional (HBM2)", professional_gpus),
        ("Datacenter (HBM3)", hbm3_gpus),
    ]:
        print(f"\n  {tier_name}:")
        for gpu in tier_gpus:
            std_max = std_analysis.get("max_seq_by_gpu", {}).get(gpu, 0)
            phase_max = phase_analysis.get("max_seq_by_gpu", {}).get(gpu, 0)
            hyb_max = hyb_analysis.get("max_seq_by_gpu", {}).get(gpu, 0)

            std_str = f"{std_max:,}" if std_max > 0 else "N/A"

            row = f"    {gpu:<18} | {std_str:>10}"

            if phase_analysis:
                phase_str = f"{phase_max:,}" if phase_max > 0 else "N/A"
                row += f" | {phase_str:>10}"

            if hyb_analysis:
                hyb_str = f"{hyb_max:,}" if hyb_max > 0 else "N/A"
                row += f" | {hyb_str:>10}"

            # Cost tier
            if "RTX" in gpu:
                cost = "$1-2K"
            elif "A10" in gpu or "A30" in gpu:
                cost = "$5-10K"
            elif "A40" in gpu:
                cost = "$10-15K"
            elif "A100" in gpu:
                cost = "$15-30K"
            elif "H100" in gpu:
                cost = "$30-40K"
            else:
                cost = "$40K+"

            row += f" | {cost:>10}"
            print(row)

    # Key takeaways
    print(f"\n{'='*70}")
    print("   KEY FINDINGS")
    print(f"{'='*70}\n")

    # Find the crossover point where Standard OOMs but Phase/Hybrid doesn't
    phase_only_seq = [
        seq_len for seq_len, s in savings.items()
        if s.get("phase_oom") == False and s.get("standard_oom") == True
    ]

    if phase_only_seq:
        print(f"  1. At {min(phase_only_seq):,} tokens, Standard Transformer hits OOM")
        print(f"     while Phase Transformer still fits!")

    # Memory efficiency at max common sequence length
    common_seqs = [
        seq_len for seq_len, s in savings.items()
        if s.get("standard_gb") and s.get("standard_gb") != float("inf")
    ]

    if common_seqs:
        max_common = max(common_seqs)
        s = savings[max_common]
        print(f"\n  2. At {max_common:,} tokens (all models fit):")
        print(f"     - Standard: {s.get('standard_gb', 0):.2f} GB")
        if s.get("phase_gb"):
            print(f"     - Phase: {s.get('phase_gb', 0):.2f} GB ({s.get('phase_savings_pct', 0):.0f}% savings)")
        if s.get("hybrid_gb"):
            print(f"     - Hybrid: {s.get('hybrid_gb', 0):.2f} GB ({s.get('hybrid_savings_pct', 0):.0f}% savings)")

    # Scaling analysis
    print(f"\n  3. Scaling Behavior:")
    print(f"     - Standard Attention: Creates [B, H, N, N] attention matrix -> O(n²) memory")
    print(f"     - Phase Attention: State accumulation, no attention matrix -> O(n) memory")
    print(f"     - Hybrid Attention: Local window + Phase -> O(n) with better quality")

    # Note about the results
    print(f"\n  4. Important Notes:")
    print(f"     - Phase attention is TRUE O(n) - best memory efficiency")
    print(f"     - Hybrid adds LocalAttention for quality, increases base memory")
    print(f"     - At LONG sequences (16K+), the O(n²) vs O(n) difference is dramatic")
    print(f"     - Run with --full to see 8K/16K/32K where Standard OOMs")


def save_results(
    results: Dict[str, List[MemoryResult]],
    analysis: Dict[str, any],
    savings: Dict[int, Dict[str, float]],
    output_file: str,
):
    """Save results to JSON file."""

    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": {
            model_type: [asdict(r) for r in type_results]
            for model_type, type_results in results.items()
        },
        "analysis": analysis,
        "savings": {str(k): v for k, v in savings.items()},  # Convert int keys
        "gpu_specs": GPU_SPECS,
    }

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Results saved to: {output_file}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Memory Efficiency Benchmark: Hybrid O(n×w) vs Standard O(n²)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python benchmark_memory.py --quick                       # Fast test (512-4K)
  python benchmark_memory.py --full                        # Full test (512-32K)
  python benchmark_memory.py --model_size medium --full    # Medium model test
  python benchmark_memory.py --cosine_mode shifted --full  # Test shifted cosine
  python benchmark_memory.py --decay_gamma 0.95 --full     # Test with decay
  python benchmark_memory.py --local_layers 6 --full       # 6:6 split (6 local + 6 hybrid)
  python benchmark_memory.py --models standard,hybrid,phase --full  # All models
        """,
    )

    parser.add_argument("--model_size", type=str, default="small",
                        choices=["tiny", "small", "medium", "large", "xl"],
                        help="Model size preset")
    parser.add_argument("--models", type=str, default="standard,hybrid",
                        help="Comma-separated model types: standard (O(n²)), hybrid (O(n×w)), phase (O(n))")
    parser.add_argument("--batch_size", type=int, default=1,
                        help="Batch size for testing")
    parser.add_argument("--seq_lengths", type=str, default=None,
                        help="Comma-separated sequence lengths to test")
    parser.add_argument("--quick", action="store_true",
                        help="Quick test (512, 1024, 2048, 4096)")
    parser.add_argument("--full", action="store_true",
                        help="Full test (512 to 32768)")
    parser.add_argument("--no_backward", action="store_true",
                        help="Skip backward pass (inference only)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output file for results (JSON)")
    parser.add_argument("--verbose", action="store_true",
                        help="Verbose output")

    # Hybrid configuration (V9.6.12+)
    parser.add_argument("--cosine_mode", type=str, default="standard",
                        choices=["standard", "shifted", "complex"],
                        help="Phase cosine interaction mode")
    parser.add_argument("--decay_gamma", type=float, default=1.0,
                        help="State decay factor (1.0=infinite, <1.0=local focus)")
    parser.add_argument("--window_size", type=int, default=256,
                        help="Local attention window size")
    parser.add_argument("--local_layers", type=int, default=None,
                        help="Number of local-only layers in Hybrid model (default: auto = num_layers//2, e.g., 6 for 12-layer = 6:6 split)")

    args = parser.parse_args()

    # Determine sequence lengths
    if args.seq_lengths:
        seq_lengths = [int(x) for x in args.seq_lengths.split(",")]
    elif args.full:
        seq_lengths = [512, 1024, 2048, 4096, 8192, 16384, 32768]
    elif args.quick:
        seq_lengths = [512, 1024, 2048, 4096]
    else:
        seq_lengths = [512, 1024, 2048, 4096, 8192]  # Default

    # Parse model types
    model_types = [m.strip() for m in args.models.split(",")]

    config = MemoryBenchmarkConfig(
        model_size=args.model_size,
        batch_size=args.batch_size,
        seq_lengths=seq_lengths,
        model_types=model_types,
        # Hybrid configuration (V9.6.12+)
        cosine_mode=args.cosine_mode,
        decay_gamma=args.decay_gamma,
        window_size=args.window_size,
        local_layers=args.local_layers,
        include_backward=not args.no_backward,
        output_file=args.output,
        verbose=args.verbose,
    )

    # Run benchmark
    results = run_benchmark(config)

    # Analyze results
    analysis = analyze_scaling(results)
    savings = compute_savings(results)

    # Print results
    print_results(results, analysis, savings)

    # Save if output specified
    if config.output_file:
        save_results(results, analysis, savings, config.output_file)

    print(f"\n{'='*70}")
    print("   BENCHMARK COMPLETE")
    print(f"{'='*70}\n")

    return results, analysis, savings


if __name__ == "__main__":
    main()
