#!/usr/bin/env python3
"""
DeepSpeed TurboQuant + CTM+ Offload Benchmark

Covers five sections:
  1. Compression quality  — MSE, cosine similarity, SNR across bit-widths
  2. Throughput           — compress / decompress GB/s for realistic tensor shapes
  3. Memory ratios        — actual stored vs theoretical packed vs original FP32
  4. Offload pipeline     — end-to-end register → offload → fetch latency
  5. Simulated training   — CTM+ smart eviction + TurboQuant compression over
                            a synthetic forward/backward cycle

Usage:
    python run_turboquant_benchmark.py           # full benchmark
    python run_turboquant_benchmark.py --quick   # smaller workloads
    python run_turboquant_benchmark.py --json results.json
"""

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ctm_plus_deepspeed import (
    CTMDeepSpeedConfig,
    TurboQuantOffloadManager,
    TurboQuantTrainingConfig,
    TurboQuantCompressor,
    create_turboquant_offload_manager,
)
from ctm_plus_deepspeed.offload_manager import TensorLocation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sep(char="=", n=72):
    print(char * n)

def _header(title, char="="):
    _sep(char)
    print(title)
    _sep(char)

def _row(label, *vals, widths=None):
    widths = widths or [28] + [10] * len(vals)
    parts = [f"{label:<{widths[0]}}"] + [
        f"{v:>{widths[i+1]}}" for i, v in enumerate(vals)
    ]
    print("  " + "  ".join(parts))

def _divider(widths=None):
    widths = widths or [28, 10, 10, 10, 10, 10]
    print("  " + "  ".join("-" * w for w in widths))


# ---------------------------------------------------------------------------
# Tensor shapes representative of real model layers
# ---------------------------------------------------------------------------

TENSOR_SHAPES = {
    "small_linear (768×768)":       (768, 768),
    "medium_linear (2048×2048)":    (2048, 2048),
    "large_linear (4096×4096)":     (4096, 4096),
    "attention_proj (4096×128×32)": (4096, 128, 32),   # Q/K/V projection
    "embedding (50257×768)":        (50257, 768),       # GPT-2-scale vocab
}

QUICK_SHAPES = {
    "small_linear (768×768)":       (768, 768),
    "medium_linear (2048×2048)":    (2048, 2048),
}


# ---------------------------------------------------------------------------
# Section 1: Compression quality
# ---------------------------------------------------------------------------

def benchmark_compression_quality(n_samples: int = 200) -> dict:
    _header("SECTION 1: COMPRESSION QUALITY  (MSE / Cosine / SNR per bit-width)")

    configs = [
        ("2-bit (aggressive)", TurboQuantTrainingConfig(angle_bits=2, enable_qjl=True)),
        ("3-bit (standard)",   TurboQuantTrainingConfig.three_bit()),
        ("4-bit (high-qual)",  TurboQuantTrainingConfig.four_bit()),
        ("4-bit lossless",     TurboQuantTrainingConfig.lossless_4bit()),
        ("3-bit no QJL",       TurboQuantTrainingConfig(angle_bits=3, enable_qjl=False)),
    ]

    tensor_types = {
        "gradient":      lambda rng: rng.randn(128).astype(np.float32) * 0.01,
        "adam_momentum": lambda rng: rng.randn(128).astype(np.float32) * 0.1,
        "adam_variance": lambda rng: np.abs(rng.randn(128).astype(np.float32)) * 0.001,
    }

    print(f"\n  Vectors per config / type: {n_samples}")
    print(f"  Segment dim: 128  (all configs)\n")

    widths = [22, 14, 10, 10, 10, 10, 10]
    _row("Config", "Tensor type", "Bits/El", "Compress",
         "Avg MSE", "Avg cos", "SNR dB", widths=widths)
    _divider(widths)

    results = {}
    rng = np.random.RandomState(0)

    for cfg_name, cfg in configs:
        comp = TurboQuantCompressor(cfg)
        for ttype, make_vec in tensor_types.items():
            mses, cosines, snrs = [], [], []
            for _ in range(n_samples):
                v = make_vec(rng)
                buf = comp.compress(v)
                r = comp.decompress(buf).flatten()[:128]
                mse = float(np.mean((v - r) ** 2))
                cos = float(np.dot(v, r) / (np.linalg.norm(v) * np.linalg.norm(r) + 1e-12))
                snr = 10 * math.log10(
                    np.linalg.norm(v) ** 2 / (mse * len(v) + 1e-12)
                ) if mse > 0 else 99.0
                mses.append(mse); cosines.append(cos); snrs.append(snr)

            key = f"{cfg_name}|{ttype}"
            results[key] = dict(
                bits_per_element=cfg.total_bits_per_element,
                compression_ratio=cfg.compression_ratio,
                avg_mse=float(np.mean(mses)),
                avg_cosine=float(np.mean(cosines)),
                avg_snr_db=float(np.mean(snrs)),
            )
            _row(
                cfg_name, ttype,
                f"{cfg.total_bits_per_element:.2f}",
                f"{cfg.compression_ratio:.1f}x",
                f"{np.mean(mses):.5f}",
                f"{np.mean(cosines):.4f}",
                f"{np.mean(snrs):.1f}",
                widths=widths,
            )
        print()

    return results


# ---------------------------------------------------------------------------
# Section 2: Throughput
# ---------------------------------------------------------------------------

def benchmark_throughput(shapes: dict, n_runs: int = 5) -> dict:
    _header("SECTION 2: THROUGHPUT  (compress / decompress GB/s)")

    configs = [
        ("3-bit", TurboQuantTrainingConfig.three_bit()),
        ("4-bit", TurboQuantTrainingConfig.four_bit()),
    ]

    widths = [32, 12, 12, 12, 12, 12]
    _row("Tensor", "Elements", "Size MB", "Config",
         "Compress", "Decompress", widths=widths)
    _divider(widths)

    results = {}
    rng = np.random.RandomState(1)

    for shape_name, shape in shapes.items():
        data = rng.randn(*shape).astype(np.float32)
        size_mb = data.nbytes / 1024 ** 2

        for cfg_name, cfg in configs:
            comp = TurboQuantCompressor(cfg)

            # Warm-up
            buf = comp.compress(data)
            comp.decompress(buf)

            # Compress timing
            t0 = time.perf_counter()
            for _ in range(n_runs):
                buf = comp.compress(data)
            compress_s = (time.perf_counter() - t0) / n_runs
            compress_gbs = (data.nbytes / 1e9) / compress_s

            # Decompress timing
            t0 = time.perf_counter()
            for _ in range(n_runs):
                comp.decompress(buf)
            decompress_s = (time.perf_counter() - t0) / n_runs
            decompress_gbs = (data.nbytes / 1e9) / decompress_s

            key = f"{shape_name}|{cfg_name}"
            results[key] = dict(
                size_mb=size_mb,
                n_elements=data.size,
                compress_gbs=compress_gbs,
                decompress_gbs=decompress_gbs,
            )
            _row(
                shape_name,
                f"{data.size:,}",
                f"{size_mb:.1f}",
                cfg_name,
                f"{compress_gbs:.3f} GB/s",
                f"{decompress_gbs:.3f} GB/s",
                widths=widths,
            )
        print()

    return results


# ---------------------------------------------------------------------------
# Section 3: Memory ratios
# ---------------------------------------------------------------------------

def benchmark_memory_ratios(shapes: dict) -> dict:
    _header("SECTION 3: MEMORY RATIOS  (actual stored vs theoretical packed vs FP32)")

    configs = [
        ("2-bit", TurboQuantTrainingConfig(angle_bits=2, enable_qjl=True)),
        ("3-bit", TurboQuantTrainingConfig.three_bit()),
        ("4-bit", TurboQuantTrainingConfig.four_bit()),
    ]

    widths = [28, 10, 10, 12, 12, 12]
    _row("Tensor", "Config", "FP32 MB",
         "Actual MB", "Actual ratio", "Theory ratio", widths=widths)
    _divider(widths)

    results = {}
    rng = np.random.RandomState(2)

    for shape_name, shape in shapes.items():
        data = rng.randn(*shape).astype(np.float32)
        fp32_mb = data.nbytes / 1024 ** 2

        for cfg_name, cfg in configs:
            comp = TurboQuantCompressor(cfg)
            buf = comp.compress(data)
            actual_mb = buf.actual_stored_bytes / 1024 ** 2
            theory_mb = buf.theoretical_packed_bytes / 1024 ** 2
            actual_ratio = data.nbytes / buf.actual_stored_bytes
            theory_ratio = data.nbytes / buf.theoretical_packed_bytes

            key = f"{shape_name}|{cfg_name}"
            results[key] = dict(
                fp32_mb=fp32_mb,
                actual_mb=actual_mb,
                theory_mb=theory_mb,
                actual_ratio=actual_ratio,
                theory_ratio=theory_ratio,
            )
            _row(
                shape_name, cfg_name,
                f"{fp32_mb:.1f}",
                f"{actual_mb:.1f}",
                f"{actual_ratio:.2f}x",
                f"{theory_ratio:.2f}x",
                widths=widths,
            )
        print()

    print("  Note: 'Actual ratio' = real Python/numpy heap savings (no bit-packing).")
    print("        'Theory ratio' = if angle indices were packed to angle_bits/index.")
    return results


# ---------------------------------------------------------------------------
# Section 4: Offload pipeline latency
# ---------------------------------------------------------------------------

def benchmark_offload_pipeline(shapes: dict, n_runs: int = 10) -> dict:
    _header("SECTION 4: OFFLOAD PIPELINE LATENCY  (register → offload → fetch)")

    widths = [32, 10, 12, 12, 12, 12]
    _row("Tensor", "Config",
         "Offload ms", "Fetch ms", "Total ms", "Bandwidth", widths=widths)
    _divider(widths)

    results = {}
    rng = np.random.RandomState(3)

    for shape_name, shape in shapes.items():
        data = rng.randn(*shape).astype(np.float32)
        size_mb = data.nbytes / 1024 ** 2

        for cfg_name, cfg_mode in [("3-bit TQ", "3bit"), ("4-bit TQ", "4bit"), ("No TQ (raw)", None)]:
            offload_times, fetch_times = [], []

            for _ in range(n_runs):
                manager = TurboQuantOffloadManager.create(
                    gpu_memory_bytes=4 * 1024 ** 3,
                    cpu_memory_bytes=32 * 1024 ** 3,
                    ctm_config=CTMDeepSpeedConfig.for_training(),
                    tq_config=(
                        TurboQuantTrainingConfig.three_bit() if cfg_mode == "3bit"
                        else TurboQuantTrainingConfig.four_bit() if cfg_mode == "4bit"
                        else TurboQuantTrainingConfig(
                            compress_gradients=False,
                            compress_optimizer_states=False,
                        )
                    ),
                )
                tid = "layer.weight.grad"
                manager.register_tensor(tid, tid, data.nbytes, is_gradient=True)

                t0 = time.perf_counter()
                manager.offload(tid, data)
                offload_times.append((time.perf_counter() - t0) * 1000)

                t0 = time.perf_counter()
                manager.fetch(tid)
                fetch_times.append((time.perf_counter() - t0) * 1000)

            avg_off = float(np.mean(offload_times))
            avg_fetch = float(np.mean(fetch_times))
            total_ms = avg_off + avg_fetch
            bw_gbs = (data.nbytes * 2 / 1e9) / (total_ms / 1000)

            key = f"{shape_name}|{cfg_name}"
            results[key] = dict(
                offload_ms=avg_off, fetch_ms=avg_fetch,
                total_ms=total_ms, bandwidth_gbs=bw_gbs,
            )
            _row(
                shape_name, cfg_name,
                f"{avg_off:.1f}",
                f"{avg_fetch:.1f}",
                f"{total_ms:.1f}",
                f"{bw_gbs:.3f} GB/s",
                widths=widths,
            )
        print()

    return results


# ---------------------------------------------------------------------------
# Section 5: Simulated training workload
# ---------------------------------------------------------------------------

@dataclass
class LayerTensors:
    param_id: str
    grad_id: str
    mom_id: str    # Adam first moment
    var_id: str    # Adam second moment
    size_bytes: int


def benchmark_training_simulation(n_layers: int = 8, n_steps: int = 5,
                                   gpu_gb: float = 2.0) -> dict:
    _header("SECTION 5: SIMULATED TRAINING WORKLOAD")
    print(f"\n  Layers: {n_layers}  |  Steps: {n_steps}  |  GPU budget: {gpu_gb} GB")
    print(f"  Tensor shape per layer: (1024, 1024) = 4 MB FP32\n")

    layer_shape = (1024, 1024)
    tensor_bytes = np.prod(layer_shape) * 4  # FP32
    rng = np.random.RandomState(42)

    # Setup: 4 tensors per layer (param, grad, momentum, variance)
    # Total = 4 * n_layers * 4 MB; GPU budget intentionally tight to force offload
    cpu_gb = 32.0

    configs_to_test = [
        ("No compression (raw)",  CTMDeepSpeedConfig.for_training(),
         TurboQuantTrainingConfig(compress_gradients=False, compress_optimizer_states=False)),
        ("3-bit TurboQuant",      CTMDeepSpeedConfig.for_training(),
         TurboQuantTrainingConfig.three_bit()),
        ("4-bit TurboQuant",      CTMDeepSpeedConfig.for_training(),
         TurboQuantTrainingConfig.four_bit()),
    ]

    results = {}

    for run_name, ctm_cfg, tq_cfg in configs_to_test:
        manager = TurboQuantOffloadManager.create(
            gpu_memory_bytes=int(gpu_gb * 1024 ** 3),
            cpu_memory_bytes=int(cpu_gb * 1024 ** 3),
            ctm_config=ctm_cfg,
            tq_config=tq_cfg,
        )

        # Build layer tensor metadata
        layers: List[LayerTensors] = []
        for i in range(n_layers):
            lt = LayerTensors(
                param_id=f"layer_{i}.weight",
                grad_id=f"layer_{i}.weight.grad",
                mom_id=f"layer_{i}.optimizer.mom",
                var_id=f"layer_{i}.optimizer.var",
                size_bytes=int(tensor_bytes),
            )
            layers.append(lt)
            # Parameters start on GPU
            manager.register_tensor(lt.param_id, lt.param_id, lt.size_bytes)
            # Gradients and optimizer states start on CPU (ZeRO-2 style)
            manager.register_tensor(lt.grad_id, lt.grad_id, lt.size_bytes,
                                     is_gradient=True,
                                     initial_location=TensorLocation.CPU)
            manager.register_tensor(lt.mom_id, lt.mom_id, lt.size_bytes,
                                     is_optimizer_state=True,
                                     initial_location=TensorLocation.CPU)
            manager.register_tensor(lt.var_id, lt.var_id, lt.size_bytes,
                                     is_optimizer_state=True,
                                     initial_location=TensorLocation.CPU)

        # Simulate training steps
        total_offload_ms = 0.0
        total_fetch_ms = 0.0
        offload_count = 0
        fetch_count = 0

        for step in range(n_steps):
            # Forward: access params in order (simulate layer-by-layer)
            for lt in layers:
                manager.on_access(lt.param_id, in_compute_graph=True)

            # Backward: access gradients, then offload them
            for lt in layers:
                manager.on_access(lt.grad_id)
                grad_data = rng.randn(*layer_shape).astype(np.float32) * 0.01
                t0 = time.perf_counter()
                manager.offload(lt.grad_id, grad_data)
                total_offload_ms += (time.perf_counter() - t0) * 1000
                offload_count += 1

            # Optimizer step: fetch momentum + variance, update, offload back
            for lt in layers:
                mom_data = rng.randn(*layer_shape).astype(np.float32) * 0.1
                var_data = np.abs(rng.randn(*layer_shape).astype(np.float32)) * 0.001

                t0 = time.perf_counter()
                manager.offload(lt.mom_id, mom_data)
                manager.offload(lt.var_id, var_data)
                total_offload_ms += (time.perf_counter() - t0) * 1000
                offload_count += 2

                # Simulate prefetch for next step
                t0 = time.perf_counter()
                manager.fetch(lt.grad_id)
                manager.fetch(lt.mom_id)
                manager.fetch(lt.var_id)
                total_fetch_ms += (time.perf_counter() - t0) * 1000
                fetch_count += 3

        stats = manager.get_stats()
        tq = stats["turboquant"]
        orig_bytes = tq.get("total_original_bytes", 0)
        actual_bytes = tq.get("total_actual_stored_bytes", 0)
        theory_bytes = tq.get("total_theoretical_packed_bytes", 0)

        actual_ratio = orig_bytes / max(1, actual_bytes)
        theory_ratio = orig_bytes / max(1, theory_bytes)

        results[run_name] = dict(
            total_offload_ms=total_offload_ms,
            total_fetch_ms=total_fetch_ms,
            offload_count=offload_count,
            fetch_count=fetch_count,
            avg_offload_ms=total_offload_ms / max(1, offload_count),
            avg_fetch_ms=total_fetch_ms / max(1, fetch_count),
            actual_compression_ratio=actual_ratio,
            theoretical_compression_ratio=theory_ratio,
            offloads_compressed=tq.get("offloads_compressed", 0),
            offloads_raw=tq.get("offloads_raw", 0),
        )

        print(f"  [{run_name}]")
        print(f"    Offloads: {offload_count:4d}   avg {total_offload_ms/max(1,offload_count):.1f} ms/tensor   total {total_offload_ms:.0f} ms")
        print(f"    Fetches:  {fetch_count:4d}   avg {total_fetch_ms/max(1,fetch_count):.1f} ms/tensor    total {total_fetch_ms:.0f} ms")
        print(f"    Compressed offloads: {tq.get('offloads_compressed', 0)}  Raw: {tq.get('offloads_raw', 0)}")
        if actual_bytes > 0:
            print(f"    Actual compression:      {actual_ratio:.2f}x  ({orig_bytes/1e6:.0f} MB → {actual_bytes/1e6:.0f} MB)")
            print(f"    Theoretical compression: {theory_ratio:.2f}x  ({orig_bytes/1e6:.0f} MB → {theory_bytes/1e6:.0f} MB)")
        print()

    # Summary comparison
    _sep("-")
    print("  SUMMARY COMPARISON")
    _sep("-")
    widths = [26, 12, 12, 12, 12]
    _row("Config", "Total off ms", "Total fetch ms",
         "Actual ratio", "Theory ratio", widths=widths)
    _divider(widths)
    baseline_total = None
    for run_name, r in results.items():
        total = r["total_offload_ms"] + r["total_fetch_ms"]
        if baseline_total is None:
            baseline_total = total
        speedup = baseline_total / max(1, total)
        _row(
            run_name,
            f"{r['total_offload_ms']:.0f}",
            f"{r['total_fetch_ms']:.0f}",
            f"{r['actual_compression_ratio']:.2f}x",
            f"{r['theoretical_compression_ratio']:.2f}x",
            widths=widths,
        )
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="DeepSpeed TurboQuant benchmark")
    parser.add_argument("--quick", action="store_true",
                        help="Smaller workloads for faster runs")
    parser.add_argument("--json", metavar="FILE",
                        help="Write results to JSON file")
    parser.add_argument("--section", type=int, choices=[1,2,3,4,5],
                        help="Run only a specific section")
    args = parser.parse_args()

    shapes = QUICK_SHAPES if args.quick else TENSOR_SHAPES
    n_samples = 50 if args.quick else 200
    n_runs = 3 if args.quick else 10
    n_layers = 4 if args.quick else 8
    n_steps = 2 if args.quick else 5

    print()
    _sep()
    print("  DeepSpeed TurboQuant + CTM+ Benchmark")
    mode = "QUICK" if args.quick else "FULL"
    print(f"  Mode: {mode}  |  Tensor shapes: {len(shapes)}")
    _sep()

    all_results = {}
    run = args.section

    if run is None or run == 1:
        all_results["compression_quality"] = benchmark_compression_quality(n_samples)
    if run is None or run == 2:
        all_results["throughput"] = benchmark_throughput(shapes, n_runs)
    if run is None or run == 3:
        all_results["memory_ratios"] = benchmark_memory_ratios(shapes)
    if run is None or run == 4:
        all_results["offload_pipeline"] = benchmark_offload_pipeline(shapes, n_runs)
    if run is None or run == 5:
        all_results["training_simulation"] = benchmark_training_simulation(
            n_layers=n_layers, n_steps=n_steps,
            gpu_gb=1.0 if args.quick else 2.0,
        )

    _sep()
    print("  Benchmark complete.")
    _sep()

    if args.json:
        with open(args.json, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"  Results written to {args.json}")

    return all_results


if __name__ == "__main__":
    main()
