#!/usr/bin/env python3
"""
Benchmark: TBPTT vs Standard Training — Memory, Speed & Compute Efficiency
===========================================================================

Measures real GPU memory, wall-clock time, and compute efficiency for:
  1. Standard forward/backward (full sequence)
  2. TBPTT chunked forward+backward

Metrics reported:
  - Peak GPU memory (MB)
  - Wall-clock time per step (ms)
  - Tokens/second throughput
  - GPU utilization % (CUDA only)
  - Memory saved (%)
  - Compute efficiency ratio

Modes:
  - Single-config: benchmark one batch size (default)
  - Batch sweep (--batch_sweep): compare multiple batch sizes to show
    how TBPTT memory savings enable larger batches → higher throughput

Usage:
    # Quick test (CPU, small model):
    python scripts/benchmark_tbptt_memory.py

    # GPU benchmark (recommended):
    python scripts/benchmark_tbptt_memory.py --device cuda

    # Custom sequence lengths:
    python scripts/benchmark_tbptt_memory.py --device cuda --seq_lengths 512 1024 2048 4096

    # Custom chunk size:
    python scripts/benchmark_tbptt_memory.py --device cuda --chunk_size 256

    # Batch sweep — shows compute savings from larger batches:
    python scripts/benchmark_tbptt_memory.py --device cuda --batch_sweep 1 2 4 8 16 --seq_lengths 1024

    # GPU benchmark with utilization tracking:
    python scripts/benchmark_tbptt_memory.py --device cuda --track_utilization
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


# ---------------------------------------------------------------------------
# GPU monitoring helpers
# ---------------------------------------------------------------------------

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


def get_gpu_utilization():
    """Get GPU compute utilization % via nvidia-ml-py (pynvml)."""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        pynvml.nvmlShutdown()
        return util.gpu  # percent 0-100
    except Exception:
        return None


def sample_gpu_utilization_during(fn, sample_interval=0.01):
    """Run *fn* and sample GPU utilization in a background thread.

    Returns (fn_result, avg_utilization%).  If pynvml is unavailable the
    utilization will be None.
    """
    import threading

    samples = []
    stop_event = threading.Event()

    def _sampler():
        while not stop_event.is_set():
            u = get_gpu_utilization()
            if u is not None:
                samples.append(u)
            time.sleep(sample_interval)

    t = threading.Thread(target=_sampler, daemon=True)
    t.start()
    result = fn()
    stop_event.set()
    t.join(timeout=1.0)

    avg_util = sum(samples) / len(samples) if samples else None
    return result, avg_util


# ---------------------------------------------------------------------------
# Loss function
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Benchmark runners
# ---------------------------------------------------------------------------

def benchmark_standard(model, input_ids, targets, device,
                       warmup=1, runs=3, track_utilization=False):
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
    util_samples = []
    for _ in range(runs):
        model.zero_grad()
        if device.type == 'cuda':
            torch.cuda.synchronize()

        def _step():
            t0 = time.perf_counter()
            out = model(input_ids)
            loss_val, m = simple_loss_fn(out['logits'], targets)
            loss_val.backward()
            if device.type == 'cuda':
                torch.cuda.synchronize()
            t1 = time.perf_counter()
            return t1 - t0, m

        if track_utilization and device.type == 'cuda':
            (elapsed, metrics), util = sample_gpu_utilization_during(
                lambda: _step()
            )
            if util is not None:
                util_samples.append(util)
        else:
            elapsed, metrics = _step()

        times.append(elapsed)

    peak_mem = get_peak_gpu_memory_mb()
    avg_time = sum(times) / len(times)
    avg_util = sum(util_samples) / len(util_samples) if util_samples else None
    return peak_mem, avg_time, metrics, avg_util


def benchmark_tbptt(model, input_ids, targets, chunk_size, device,
                    warmup=1, runs=3, track_utilization=False):
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
    util_samples = []
    for _ in range(runs):
        model.zero_grad()
        if device.type == 'cuda':
            torch.cuda.synchronize()

        def _step():
            t0 = time.perf_counter()
            res = forward_chunked_tbptt(
                model, input_ids, targets, chunk_size, simple_loss_fn
            )
            if device.type == 'cuda':
                torch.cuda.synchronize()
            t1 = time.perf_counter()
            return t1 - t0, res['metrics']

        if track_utilization and device.type == 'cuda':
            (elapsed, metrics), util = sample_gpu_utilization_during(
                lambda: _step()
            )
            if util is not None:
                util_samples.append(util)
        else:
            elapsed, metrics = _step()

        times.append(elapsed)

    peak_mem = get_peak_gpu_memory_mb()
    avg_time = sum(times) / len(times)
    avg_util = sum(util_samples) / len(util_samples) if util_samples else None
    return peak_mem, avg_time, metrics, avg_util


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_mem(v):
    return "OOM" if v == float('inf') else f"{v:.1f}"


def _fmt_time(v):
    return "OOM" if v == float('inf') else f"{v * 1000:.1f}"


def _fmt_tps(v):
    if v is None or v == float('inf'):
        return "N/A"
    if v >= 1e6:
        return f"{v / 1e6:.2f}M"
    if v >= 1e3:
        return f"{v / 1e3:.1f}K"
    return f"{v:.0f}"


def _fmt_util(v):
    return "N/A" if v is None else f"{v:.0f}%"


def _fmt_pct(v):
    return "N/A" if v is None else f"{v:+.1f}%"


# ---------------------------------------------------------------------------
# Main benchmark: per-sequence-length comparison
# ---------------------------------------------------------------------------

def run_benchmark(args):
    device = torch.device(args.device)
    print(f"Device: {device}")
    if device.type == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        total_mem_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"GPU Memory: {total_mem_gb:.1f} GB")

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
    if args.track_utilization:
        print("GPU utilization tracking: enabled")
    print()

    # Header
    cols = (f"{'Seq Len':>8} | {'Mode':>12} | {'Peak Mem':>10} | "
            f"{'Time (ms)':>10} | {'Tok/s':>10} | ")
    if args.track_utilization:
        cols += f"{'GPU Util':>9} | "
    cols += f"{'Loss':>8} | {'Mem Saved':>10} | {'Speed':>10}"
    print(cols)
    print("-" * len(cols))

    # Collect results for summary
    all_results = []

    for seq_len in args.seq_lengths:
        torch.manual_seed(42)
        input_ids = torch.randint(
            0, args.vocab_size, (args.batch_size, seq_len), device=device
        )
        targets = torch.randint(
            0, args.vocab_size, (args.batch_size, seq_len), device=device
        )
        total_tokens = args.batch_size * seq_len

        # --- Standard ---
        model.train()
        gc.collect()
        if device.type == 'cuda':
            torch.cuda.empty_cache()
        try:
            std_mem, std_time, std_metrics, std_util = benchmark_standard(
                model, input_ids, targets, device,
                warmup=1, runs=args.runs,
                track_utilization=args.track_utilization,
            )
            std_tps = total_tokens / std_time
        except RuntimeError as e:
            if "out of memory" in str(e):
                std_mem, std_time = float('inf'), float('inf')
                std_metrics = {'lm_loss': 0}
                std_util = None
                std_tps = None
                if device.type == 'cuda':
                    torch.cuda.empty_cache()
            else:
                raise

        row = (f"{seq_len:>8} | {'Standard':>12} | "
               f"{_fmt_mem(std_mem):>10} | "
               f"{_fmt_time(std_time):>10} | "
               f"{_fmt_tps(std_tps):>10} | ")
        if args.track_utilization:
            row += f"{_fmt_util(std_util):>9} | "
        row += f"{std_metrics.get('lm_loss', 0):>8.3f} | {'baseline':>10} | {'baseline':>10}"
        print(row)

        # --- TBPTT ---
        gc.collect()
        if device.type == 'cuda':
            torch.cuda.empty_cache()
        try:
            tbptt_mem, tbptt_time, tbptt_metrics, tbptt_util = benchmark_tbptt(
                model, input_ids, targets, args.chunk_size, device,
                warmup=1, runs=args.runs,
                track_utilization=args.track_utilization,
            )
            tbptt_tps = total_tokens / tbptt_time
        except RuntimeError as e:
            if "out of memory" in str(e):
                tbptt_mem, tbptt_time = float('inf'), float('inf')
                tbptt_metrics = {'lm_loss': 0}
                tbptt_util = None
                tbptt_tps = None
                if device.type == 'cuda':
                    torch.cuda.empty_cache()
            else:
                raise

        # Compute deltas
        if std_mem > 0 and std_mem != float('inf') and tbptt_mem != float('inf'):
            mem_saved = (1 - tbptt_mem / std_mem) * 100
        else:
            mem_saved = None

        if (std_tps is not None and tbptt_tps is not None
                and std_tps > 0 and std_tps != float('inf')):
            speed_delta = (tbptt_tps / std_tps - 1) * 100
        else:
            speed_delta = None

        row = (f"{seq_len:>8} | {'TBPTT':>12} | "
               f"{_fmt_mem(tbptt_mem):>10} | "
               f"{_fmt_time(tbptt_time):>10} | "
               f"{_fmt_tps(tbptt_tps):>10} | ")
        if args.track_utilization:
            row += f"{_fmt_util(tbptt_util):>9} | "
        row += (f"{tbptt_metrics.get('lm_loss', 0):>8.3f} | "
                f"{_fmt_pct(mem_saved):>10} | "
                f"{_fmt_pct(speed_delta):>10}")
        print(row)
        print()

        all_results.append({
            'seq_len': seq_len,
            'std_mem': std_mem, 'std_time': std_time,
            'std_tps': std_tps, 'std_util': std_util,
            'tbptt_mem': tbptt_mem, 'tbptt_time': tbptt_time,
            'tbptt_tps': tbptt_tps, 'tbptt_util': tbptt_util,
            'mem_saved': mem_saved, 'speed_delta': speed_delta,
        })

    # --- Summary ---
    _print_summary(all_results, args)


# ---------------------------------------------------------------------------
# Batch sweep: shows how TBPTT enables larger batches → more throughput
# ---------------------------------------------------------------------------

def run_batch_sweep(args):
    device = torch.device(args.device)
    print(f"Device: {device}")
    if device.type == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        total_mem_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"GPU Memory: {total_mem_gb:.1f} GB")

    seq_len = args.seq_lengths[0]  # use first seq_len for sweep

    model = HybridPhaseTransformer(
        vocab_size=args.vocab_size,
        embed_dim=args.embed_dim,
        num_layers=args.num_layers,
        num_heads=args.num_heads,
        local_layers=args.local_layers,
        window_size=args.window_size,
        max_seq_len=seq_len + 64,
        dropout=0.0,
    ).to(device)

    param_count = sum(p.numel() for p in model.parameters())
    print(f"Model: {param_count / 1e6:.1f}M parameters")
    print(f"Sequence length: {seq_len}")
    print(f"Chunk size: {args.chunk_size}")
    print()

    print(f"{'Batch':>6} | {'Mode':>12} | {'Peak Mem':>10} | "
          f"{'Time (ms)':>10} | {'Tok/s':>10} | {'Status':>8}")
    print("-" * 75)

    std_results = []
    tbptt_results = []

    for bs in args.batch_sweep:
        torch.manual_seed(42)
        input_ids = torch.randint(0, args.vocab_size, (bs, seq_len), device=device)
        targets = torch.randint(0, args.vocab_size, (bs, seq_len), device=device)
        total_tokens = bs * seq_len

        # Standard
        model.train()
        gc.collect()
        if device.type == 'cuda':
            torch.cuda.empty_cache()
        try:
            std_mem, std_time, _, _ = benchmark_standard(
                model, input_ids, targets, device, warmup=1, runs=args.runs
            )
            std_tps = total_tokens / std_time
            status = "OK"
        except RuntimeError as e:
            if "out of memory" in str(e):
                std_mem, std_time, std_tps = float('inf'), float('inf'), None
                status = "OOM"
                if device.type == 'cuda':
                    torch.cuda.empty_cache()
            else:
                raise

        print(f"{bs:>6} | {'Standard':>12} | "
              f"{_fmt_mem(std_mem):>10} | "
              f"{_fmt_time(std_time):>10} | "
              f"{_fmt_tps(std_tps):>10} | "
              f"{status:>8}")
        std_results.append({'bs': bs, 'mem': std_mem, 'tps': std_tps, 'status': status})

        # TBPTT
        gc.collect()
        if device.type == 'cuda':
            torch.cuda.empty_cache()
        try:
            tbptt_mem, tbptt_time, _, _ = benchmark_tbptt(
                model, input_ids, targets, args.chunk_size, device,
                warmup=1, runs=args.runs
            )
            tbptt_tps = total_tokens / tbptt_time
            status = "OK"
        except RuntimeError as e:
            if "out of memory" in str(e):
                tbptt_mem, tbptt_time, tbptt_tps = float('inf'), float('inf'), None
                status = "OOM"
                if device.type == 'cuda':
                    torch.cuda.empty_cache()
            else:
                raise

        print(f"{bs:>6} | {'TBPTT':>12} | "
              f"{_fmt_mem(tbptt_mem):>10} | "
              f"{_fmt_time(tbptt_time):>10} | "
              f"{_fmt_tps(tbptt_tps):>10} | "
              f"{status:>8}")
        tbptt_results.append({'bs': bs, 'mem': tbptt_mem, 'tps': tbptt_tps, 'status': status})
        print()

    # Sweep summary
    _print_batch_sweep_summary(std_results, tbptt_results, seq_len, args)


# ---------------------------------------------------------------------------
# Summary printers
# ---------------------------------------------------------------------------

def _print_summary(results, args):
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    valid = [r for r in results
             if r['std_mem'] != float('inf') and r['tbptt_mem'] != float('inf')]

    if valid:
        avg_mem_saved = sum(r['mem_saved'] for r in valid if r['mem_saved'] is not None)
        n_mem = sum(1 for r in valid if r['mem_saved'] is not None)
        if n_mem:
            print(f"  Avg memory saved:   {avg_mem_saved / n_mem:+.1f}%")

        avg_speed = sum(r['speed_delta'] for r in valid if r['speed_delta'] is not None)
        n_speed = sum(1 for r in valid if r['speed_delta'] is not None)
        if n_speed:
            print(f"  Avg speed delta:    {avg_speed / n_speed:+.1f}%  "
                  "(negative = TBPTT overhead at same batch size)")

    # Check OOM cases
    oom_std = [r for r in results if r['std_mem'] == float('inf')]
    oom_tbptt = [r for r in results if r['tbptt_mem'] == float('inf')]
    if oom_std and not oom_tbptt:
        rescued = [r['seq_len'] for r in results
                   if r['std_mem'] == float('inf') and r['tbptt_mem'] != float('inf')]
        if rescued:
            print(f"  TBPTT rescued OOM at seq_lengths: {rescued}")
            print("  -> Standard OOM'd, TBPTT fits = infinite compute savings!")

    print()
    print("KEY:")
    print("  Peak Mem  = peak GPU memory during forward+backward (lower is better)")
    print("  Time      = wall-clock time per step (lower is better)")
    print("  Tok/s     = tokens processed per second (higher is better)")
    if args.track_utilization:
        print("  GPU Util  = average GPU compute utilization during step")
    print("  Mem Saved = % memory reduction from Standard to TBPTT")
    print("  Speed     = % throughput change (tok/s) from Standard to TBPTT")
    print()
    print("EXPECTED at same batch size:")
    print("  - TBPTT saves memory at cost of ~10-20% speed")
    print("  - Memory savings grow with seq_len / chunk_size ratio")
    print()
    print("REAL WIN: use --batch_sweep to see how freed memory enables")
    print("  larger batches → higher throughput → fewer GPUs needed")


def _print_batch_sweep_summary(std_results, tbptt_results, seq_len, args):
    print("=" * 80)
    print(f"BATCH SWEEP SUMMARY  (seq_len={seq_len}, chunk={args.chunk_size})")
    print("=" * 80)

    # Find max batch that fits for each mode
    max_std = max((r['bs'] for r in std_results if r['status'] == 'OK'), default=0)
    max_tbptt = max((r['bs'] for r in tbptt_results if r['status'] == 'OK'), default=0)

    best_std_tps = max((r['tps'] for r in std_results
                        if r['tps'] is not None), default=0)
    best_tbptt_tps = max((r['tps'] for r in tbptt_results
                          if r['tps'] is not None), default=0)

    print(f"  Max batch (Standard): {max_std}")
    print(f"  Max batch (TBPTT):    {max_tbptt}")
    if max_std > 0 and max_tbptt > max_std:
        print(f"  -> TBPTT fits {max_tbptt / max_std:.1f}x larger batch!")

    print()
    print(f"  Peak throughput (Standard): {_fmt_tps(best_std_tps)} tok/s  (BS={max_std})")
    print(f"  Peak throughput (TBPTT):    {_fmt_tps(best_tbptt_tps)} tok/s  (BS={max_tbptt})")

    if best_std_tps and best_tbptt_tps and best_std_tps > 0:
        speedup = best_tbptt_tps / best_std_tps
        print(f"  -> Effective speedup: {speedup:.2f}x")
        if speedup > 1:
            gpu_equiv = 1.0 / speedup
            print(f"  -> Equivalent GPU savings: {(1 - gpu_equiv) * 100:.0f}% fewer GPUs needed")
    print()
    print("INTERPRETATION:")
    print("  At the SAME batch size, TBPTT is slightly slower (chunking overhead).")
    print("  But TBPTT fits LARGER batches → higher total throughput → fewer GPUs.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark TBPTT vs Standard Training — Memory, Speed & Compute",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--device", default="cpu", help="Device (cpu or cuda)")
    parser.add_argument("--vocab_size", type=int, default=256, help="Vocabulary size")
    parser.add_argument("--embed_dim", type=int, default=128, help="Embedding dimension")
    parser.add_argument("--num_layers", type=int, default=4, help="Number of layers")
    parser.add_argument("--num_heads", type=int, default=4, help="Number of attention heads")
    parser.add_argument("--local_layers", type=int, default=2,
                        help="Number of local-only layers")
    parser.add_argument("--window_size", type=int, default=64, help="Local attention window")
    parser.add_argument("--batch_size", type=int, default=2, help="Batch size")
    parser.add_argument("--chunk_size", type=int, default=256, help="TBPTT chunk size")
    parser.add_argument("--seq_lengths", type=int, nargs="+",
                        default=[256, 512, 1024, 2048],
                        help="Sequence lengths to benchmark")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs to average")
    parser.add_argument("--batch_sweep", type=int, nargs="+", default=None,
                        help="Batch sizes to sweep (enables batch sweep mode). "
                             "Example: --batch_sweep 1 2 4 8 16")
    parser.add_argument("--track_utilization", action="store_true",
                        help="Sample GPU utilization %% via pynvml (requires nvidia-ml-py)")
    args = parser.parse_args()

    if args.batch_sweep:
        run_batch_sweep(args)
    else:
        run_benchmark(args)


if __name__ == "__main__":
    main()
