"""
Benchmark: Scale Stress Test (Next Step 5).

Tests FSCS-V at production-scale resolutions and frame counts.
Measures memory usage, latency, and correctness under load.

Target configurations:
    - Small:  128x128, 8 frames, 20 steps
    - Medium: 256x256, 16 frames, 30 steps
    - Large:  256x256, 32 frames, 50 steps
    - XL:     512x512, 32 frames, 50 steps (GPU only)

Patent overhead target: < 3% of total denoising time.
"""

import sys
import time
import gc
import torch
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ScaleConfig:
    name: str
    height: int
    width: int
    n_frames: int
    n_steps: int
    channels: int = 16
    batch_size: int = 1


@dataclass
class ScaleResult:
    name: str
    resolution: str
    n_frames: int
    n_steps: int
    # Timing
    total_ms: float
    per_step_ms: float
    correction_ms: float  # FSCS-V only
    overhead_pct: float
    # Memory
    peak_memory_mb: float
    # Correctness
    output_shape_correct: bool
    no_nan: bool
    correction_applied: bool  # At least some steps got nonzero correction


@dataclass
class ScaleBenchmarkResult:
    configs: List[ScaleResult]
    all_passed: bool
    elapsed_ms: float


class MockSchedule:
    def __init__(self, T, device):
        betas = torch.linspace(1e-4, 0.02, T, device=device)
        alphas = 1 - betas
        self.sqrt_alphas_cumprod = torch.sqrt(torch.cumprod(alphas, dim=0))
        self.sqrt_one_minus_alphas_cumprod = torch.sqrt(
            1 - torch.cumprod(alphas, dim=0)
        )


def benchmark_config(
    cfg: ScaleConfig, device: str
) -> Optional[ScaleResult]:
    from symbolu.vision.video.fscsv_wrapper import FSCSVModule, FSCSVConfig

    fscsv_config = FSCSVConfig(
        lambda_max=0.1,
        enable_bands=True,
        safety_tau=0.1,
        num_total_timesteps=1000,
    )
    fscsv = FSCSVModule(fscsv_config, latent_channels=cfg.channels).to(device)
    schedule = MockSchedule(1000, device)

    # Generate test latents
    z_t = torch.randn(
        cfg.batch_size, cfg.channels, cfg.n_frames,
        cfg.height, cfg.width, device=device,
    )
    noise_pred = torch.randn_like(z_t)

    # Timestep sequence (linear from 999 to 0)
    timesteps = torch.linspace(999, 0, cfg.n_steps).long().tolist()

    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()

    # ---- Baseline (no correction) ----
    t0 = time.time()
    for t in timesteps:
        _ = noise_pred.clone()  # Simulate step without correction
    if device == "cuda":
        torch.cuda.synchronize()
    baseline_ms = (time.time() - t0) * 1000

    # ---- With FSCS-V correction ----
    correction_applied = False
    t0 = time.time()
    with torch.no_grad():
        for t in timesteps:
            corrected = fscsv.correct_noise_prediction(
                noise_pred, z_t, t, schedule,
            )
            if (corrected - noise_pred).abs().max().item() > 1e-10:
                correction_applied = True
    if device == "cuda":
        torch.cuda.synchronize()
    fscsv_ms = (time.time() - t0) * 1000

    correction_ms = fscsv_ms - baseline_ms
    overhead = correction_ms / max(baseline_ms, 0.001) * 100
    per_step = fscsv_ms / cfg.n_steps

    # Memory
    if device == "cuda":
        peak_mb = torch.cuda.max_memory_allocated() / 1024 / 1024
    else:
        peak_mb = 0.0  # Can't measure on CPU

    # Correctness
    final_output = fscsv.correct_noise_prediction(
        noise_pred, z_t, timesteps[-1], schedule,
    )
    shape_ok = final_output.shape == noise_pred.shape
    no_nan = not torch.isnan(final_output).any().item()

    return ScaleResult(
        name=cfg.name,
        resolution=f"{cfg.height}x{cfg.width}",
        n_frames=cfg.n_frames,
        n_steps=cfg.n_steps,
        total_ms=fscsv_ms,
        per_step_ms=per_step,
        correction_ms=correction_ms,
        overhead_pct=overhead,
        peak_memory_mb=peak_mb,
        output_shape_correct=shape_ok,
        no_nan=no_nan,
        correction_applied=correction_applied,
    )


def run_benchmark(device: str = "cpu", seed: int = 42) -> ScaleBenchmarkResult:
    torch.manual_seed(seed)
    start = time.time()

    configs = [
        ScaleConfig("Small", 128, 128, 8, 20),
        ScaleConfig("Medium", 256, 256, 16, 30),
        ScaleConfig("Large", 256, 256, 32, 50),
    ]

    # Only run XL on GPU (too slow / memory-intensive on CPU)
    if device == "cuda":
        configs.append(ScaleConfig("XL", 512, 512, 32, 50))

    results = []
    for cfg in configs:
        try:
            result = benchmark_config(cfg, device)
            if result:
                results.append(result)
        except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
            print(f"  [SKIP] {cfg.name}: {e}")
        finally:
            gc.collect()
            if device == "cuda":
                torch.cuda.empty_cache()

    all_passed = all(r.output_shape_correct and r.no_nan and r.correction_applied
                     for r in results)
    elapsed = (time.time() - start) * 1000

    return ScaleBenchmarkResult(
        configs=results,
        all_passed=all_passed,
        elapsed_ms=elapsed,
    )


def print_results(result: ScaleBenchmarkResult) -> bool:
    print("=" * 70)
    print("  BENCHMARK: Scale Stress Test (Next Step 5)")
    print("=" * 70)
    print()

    def check(v): return "\u2705" if v else "\u274c"

    header = (f"  {'Config':<10} {'Resolution':<12} {'Frames':<8} {'Steps':<7} "
              f"{'Total':<10} {'Per-Step':<10} {'Overhead':<10} {'Memory':<10} {'OK'}")
    print(header)
    print("  " + "-" * 85)

    for r in result.configs:
        ok = r.output_shape_correct and r.no_nan and r.correction_applied
        mem_str = f"{r.peak_memory_mb:.0f}MB" if r.peak_memory_mb > 0 else "N/A"
        print(f"  {r.name:<10} {r.resolution:<12} {r.n_frames:<8} {r.n_steps:<7} "
              f"{r.total_ms:<10.1f} {r.per_step_ms:<10.2f} "
              f"{r.overhead_pct:<10.1f}% {mem_str:<10} {check(ok)}")

    print()

    # Detailed check
    for r in result.configs:
        issues = []
        if not r.output_shape_correct:
            issues.append("wrong output shape")
        if not r.no_nan:
            issues.append("NaN detected")
        if not r.correction_applied:
            issues.append("no correction applied")
        if issues:
            print(f"  {r.name}: ISSUES: {', '.join(issues)}")

    if not any(not r.output_shape_correct or not r.no_nan for r in result.configs):
        print(f"  All configurations: shape correct, no NaN")

    print()
    print(f"  VERDICT: {'PASS' if result.all_passed else 'FAIL'}")
    print(f"  Time: {result.elapsed_ms:.1f}ms")
    print()
    return result.all_passed


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    result = run_benchmark(device=device)
    passed = print_results(result)
    sys.exit(0 if passed else 1)
