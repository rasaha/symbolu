#!/usr/bin/env python3
"""
Benchmark: TBPTT vs Standard Training Memory & Speed
=====================================================

Measures real GPU memory and wall-clock time for:
  1. Standard forward/backward (full sequence)
  2. Chunked forward, single backward (V10.2)
  3. TBPTT chunked forward+backward (V10.7)

Usage:
    # Quick test (CPU, small model):
    python scripts/benchmark_tbptt_memory.py

    # GPU benchmark (recommended):
    python scripts/benchmark_tbptt_memory.py --device cuda

    # Custom sequence lengths:
    python scripts/benchmark_tbptt_memory.py --device cuda --seq_lengths 512 1024 2048 4096

    # Custom chunk size:
    python scripts/benchmark_tbptt_memory.py --device cuda --chunk_size 256
"""

import argparse
import gc
import math
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from symbolu.phase_transformer import (
    HybridPhaseTransformer,
    forward_chunked_tbptt,
)


def get_gpu_memory_mb():
    """Get current GPU memory usage in MB."""
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated() / (1024 * 1024)
    return 0.0


def get_peak_gpu_memory_mb():
    """Get peak GPU memory usage in MB."""
    if torch.cuda.is_available():
        return torch.cuda.max_memory_allocated() / (1024 * 1024)
    return 0.0


def reset_peak_memory():
    """Reset peak memory tracker."""
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def simple_loss_fn(logits, targets):
    """Simple cross-entropy loss."""
    B, N, V = logits.shape
    loss = F.cross_entropy(
        logits.reshape(-1, V),
        targets.reshape(-1),
        ignore_index=-100,
    )
    metrics = {'lm_loss': loss.item(), 'ppl': math.exp(min(loss.item(), 20))}
    return loss, metrics


def benchmark_standard(model, input_ids, targets, device, warmup=1, runs=3):
    """Benchmark standard full-sequence forward/backward."""
    # Warmup
    for _ in range(warmup):
        model.zero_grad()
        out = model(input_ids)
        loss, _ = simple_loss_fn(out['logits'], targets)
        loss.backward()

    gc.collect()
    if device.type == 'cuda':
        torch.cuda.synchronize()
    reset_peak_memory()

    times = []
    for _ in range(runs):
        model.zero_grad()
        if device.type == 'cuda':
            torch.cuda.synchronize()
        t0 = time.perf_counter()

        out = model(input_ids)
        loss, metrics = simple_loss_fn(out['logits'], targets)
        loss.backward()

        if device.type == 'cuda':
            torch.cuda.synchronize()
        t1 = time.perf_counter()
        times.append(t1 - t0)

    peak_mem = get_peak_gpu_memory_mb()
    avg_time = sum(times) / len(times)
    return peak_mem, avg_time, metrics


def benchmark_tbptt(model, input_ids, targets, chunk_size, device, warmup=1, runs=3):
    """Benchmark TBPTT chunked forward/backward."""
    # Warmup
    for _ in range(warmup):
        model.zero_grad()
        forward_chunked_tbptt(model, input_ids, targets, chunk_size, simple_loss_fn)

    gc.collect()
    if device.type == 'cuda':
        torch.cuda.synchronize()
    reset_peak_memory()

    times = []
    for _ in range(runs):
        model.zero_grad()
        if device.type == 'cuda':
            torch.cuda.synchronize()
        t0 = time.perf_counter()

        result = forward_chunked_tbptt(model, input_ids, targets, chunk_size, simple_loss_fn)

        if device.type == 'cuda':
            torch.cuda.synchronize()
        t1 = time.perf_counter()
        times.append(t1 - t0)

    peak_mem = get_peak_gpu_memory_mb()
    avg_time = sum(times) / len(times)
    return peak_mem, avg_time, result['metrics']


def run_benchmark(args):
    device = torch.device(args.device)
    print(f"Device: {device}")
    if device.type == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")

    # Create model
    model = HybridPhaseTransformer(
        vocab_size=args.vocab_size,
        embed_dim=args.embed_dim,
        num_layers=args.num_layers,
        num_heads=args.num_heads,
        local_layers=args.local_layers,
        window_size=args.window_size,
        max_seq_len=max(args.seq_lengths) + 64,
        dropout=0.0,
    ).to(device)

    param_count = sum(p.numel() for p in model.parameters())
    print(f"Model: {param_count / 1e6:.1f}M parameters")
    print(f"  embed_dim={args.embed_dim}, layers={args.num_layers}, "
          f"heads={args.num_heads}, local_layers={args.local_layers}")
    print(f"Chunk size: {args.chunk_size}")
    print(f"Batch size: {args.batch_size}")
    print()

    # Header
    print(f"{'Seq Len':>8} | {'Mode':>12} | {'Peak Mem (MB)':>14} | {'Time (ms)':>10} | {'Loss':>8} | {'Mem Saved':>10}")
    print("-" * 80)

    for seq_len in args.seq_lengths:
        torch.manual_seed(42)
        input_ids = torch.randint(0, args.vocab_size, (args.batch_size, seq_len), device=device)
        targets = torch.randint(0, args.vocab_size, (args.batch_size, seq_len), device=device)

        # Standard
        model.train()
        gc.collect()
        if device.type == 'cuda':
            torch.cuda.empty_cache()
        try:
            std_mem, std_time, std_metrics = benchmark_standard(
                model, input_ids, targets, device, warmup=1, runs=args.runs
            )
        except RuntimeError as e:
            if "out of memory" in str(e):
                std_mem, std_time, std_metrics = float('inf'), float('inf'), {'lm_loss': 0}
                if device.type == 'cuda':
                    torch.cuda.empty_cache()
            else:
                raise

        print(f"{seq_len:>8} | {'Standard':>12} | {std_mem:>14.1f} | {std_time * 1000:>10.1f} | {std_metrics.get('lm_loss', 0):>8.3f} | {'baseline':>10}")

        # TBPTT
        gc.collect()
        if device.type == 'cuda':
            torch.cuda.empty_cache()
        try:
            tbptt_mem, tbptt_time, tbptt_metrics = benchmark_tbptt(
                model, input_ids, targets, args.chunk_size, device, warmup=1, runs=args.runs
            )
        except RuntimeError as e:
            if "out of memory" in str(e):
                tbptt_mem, tbptt_time, tbptt_metrics = float('inf'), float('inf'), {'lm_loss': 0}
                if device.type == 'cuda':
                    torch.cuda.empty_cache()
            else:
                raise

        if std_mem > 0 and std_mem != float('inf') and tbptt_mem != float('inf'):
            mem_saved = (1 - tbptt_mem / std_mem) * 100
            mem_saved_str = f"{mem_saved:>+.1f}%"
        else:
            mem_saved_str = "N/A"

        print(f"{seq_len:>8} | {'TBPTT':>12} | {tbptt_mem:>14.1f} | {tbptt_time * 1000:>10.1f} | {tbptt_metrics.get('lm_loss', 0):>8.3f} | {mem_saved_str:>10}")
        print()

    # Summary
    print("=" * 80)
    print("KEY:")
    print("  Peak Mem = peak GPU memory during forward+backward (lower is better)")
    print("  Time     = wall-clock time per step (lower is better)")
    print("  Mem Saved = % memory reduction from Standard to TBPTT")
    print()
    print("EXPECTED: TBPTT saves memory at cost of ~10-20% more time")
    print("  Memory savings grow with seq_len / chunk_size ratio")


def main():
    parser = argparse.ArgumentParser(description="Benchmark TBPTT vs Standard Training")
    parser.add_argument("--device", default="cpu", help="Device (cpu or cuda)")
    parser.add_argument("--vocab_size", type=int, default=256, help="Vocabulary size")
    parser.add_argument("--embed_dim", type=int, default=128, help="Embedding dimension")
    parser.add_argument("--num_layers", type=int, default=4, help="Number of layers")
    parser.add_argument("--num_heads", type=int, default=4, help="Number of attention heads")
    parser.add_argument("--local_layers", type=int, default=2, help="Number of local-only layers")
    parser.add_argument("--window_size", type=int, default=64, help="Local attention window")
    parser.add_argument("--batch_size", type=int, default=2, help="Batch size")
    parser.add_argument("--chunk_size", type=int, default=256, help="TBPTT chunk size")
    parser.add_argument("--seq_lengths", type=int, nargs="+", default=[256, 512, 1024, 2048],
                       help="Sequence lengths to benchmark")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs to average")
    args = parser.parse_args()
    run_benchmark(args)


if __name__ == "__main__":
    main()
