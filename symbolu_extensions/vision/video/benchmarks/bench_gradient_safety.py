"""
Benchmark: Gradient Safety Bounds (Issue 7).

Validates that coherence gradients are properly bounded relative to
the base denoising prediction.

Patent requirement:
    ||lambda(t) * nabla(C')|| <= tau * ||eps_theta||

Tests:
    1. Bound enforcement: correction norm never exceeds tau * prediction norm
    2. Scaling behavior: correction scales with tau parameter
    3. Extreme conditions: very large coherence gradients get clipped
    4. Zero-crossing: safety bound handles near-zero predictions gracefully
    5. Per-timestep analysis: bound tightness across the denoising trajectory
"""

import sys
import time
import torch
from dataclasses import dataclass
from typing import List


@dataclass
class GradientSafetyResult:
    # Bound enforcement
    bound_violations: int
    total_checks: int
    violation_rate: float
    max_ratio: float  # max(correction_norm / (tau * prediction_norm))
    # Scaling with tau
    tau_01_ratio: float   # mean(correction/prediction) at tau=0.1
    tau_05_ratio: float   # at tau=0.5
    tau_10_ratio: float   # at tau=1.0
    scaling_monotonic: bool
    # Extreme conditions
    extreme_input_clipped: bool
    extreme_output_bounded: bool
    # Zero-crossing
    zero_pred_safe: bool  # No NaN/Inf when prediction ~= 0
    # Per-timestep
    timestep_ratios: List[float]  # correction/prediction at [100, 300, 500, 700, 900]
    elapsed_ms: float


def run_benchmark(
    device: str = "cpu",
    batch_size: int = 4,
    channels: int = 16,
    n_frames: int = 8,
    height: int = 32,
    width: int = 32,
    seed: int = 42,
) -> GradientSafetyResult:
    from symbolu_extensions.vision.video.fscsv_wrapper import (
        GradientSafetyBound, FSCSVModule, FSCSVConfig,
    )

    torch.manual_seed(seed)
    start = time.time()

    shape = (batch_size, channels, n_frames, height, width)

    # ---- Test 1: Bound enforcement ----
    tau = 0.1
    safety = GradientSafetyBound(tau=tau)
    violations = 0
    total = 0
    max_ratio = 0.0

    for _ in range(100):
        # Random coherence gradients of varying magnitude
        grad = torch.randn(*shape, device=device) * torch.rand(1, device=device).item() * 10
        pred = torch.randn(*shape, device=device)

        bounded = safety(grad, pred)
        ratio = bounded.norm().item() / max(tau * pred.norm().item(), 1e-10)

        total += 1
        if ratio > 1.01:  # 1% tolerance for floating point
            violations += 1
        max_ratio = max(max_ratio, ratio)

    violation_rate = violations / total

    # ---- Test 2: Scaling with tau ----
    grad = torch.randn(*shape, device=device) * 5.0  # Large gradient
    pred = torch.randn(*shape, device=device)

    safety_01 = GradientSafetyBound(tau=0.1)
    safety_05 = GradientSafetyBound(tau=0.5)
    safety_10 = GradientSafetyBound(tau=1.0)

    bounded_01 = safety_01(grad, pred)
    bounded_05 = safety_05(grad, pred)
    bounded_10 = safety_10(grad, pred)

    ratio_01 = bounded_01.norm().item() / max(pred.norm().item(), 1e-10)
    ratio_05 = bounded_05.norm().item() / max(pred.norm().item(), 1e-10)
    ratio_10 = bounded_10.norm().item() / max(pred.norm().item(), 1e-10)

    scaling_mono = ratio_01 <= ratio_05 <= ratio_10

    # ---- Test 3: Extreme conditions ----
    extreme_grad = torch.randn(*shape, device=device) * 1000.0  # Huge gradient
    normal_pred = torch.randn(*shape, device=device)

    extreme_bounded = safety(extreme_grad, normal_pred)
    extreme_clipped = extreme_bounded.norm().item() < extreme_grad.norm().item()
    extreme_bounded_ok = extreme_bounded.norm().item() <= tau * normal_pred.norm().item() * 1.01

    # ---- Test 4: Zero-crossing ----
    normal_grad = torch.randn(*shape, device=device)
    zero_pred = torch.zeros(*shape, device=device)
    near_zero_pred = torch.randn(*shape, device=device) * 1e-10

    zero_result = safety(normal_grad, zero_pred)
    near_zero_result = safety(normal_grad, near_zero_pred)

    zero_safe = (not torch.isnan(zero_result).any().item() and
                 not torch.isinf(zero_result).any().item() and
                 not torch.isnan(near_zero_result).any().item() and
                 not torch.isinf(near_zero_result).any().item())

    # ---- Test 5: Per-timestep analysis ----
    config = FSCSVConfig(lambda_max=0.1, enable_bands=True, safety_tau=0.1)
    fscsv = FSCSVModule(config, latent_channels=channels).to(device)

    class MockSchedule:
        def __init__(self, T, device):
            betas = torch.linspace(1e-4, 0.02, T, device=device)
            alphas = 1 - betas
            self.sqrt_alphas_cumprod = torch.sqrt(torch.cumprod(alphas, dim=0))
            self.sqrt_one_minus_alphas_cumprod = torch.sqrt(
                1 - torch.cumprod(alphas, dim=0)
            )

    schedule = MockSchedule(1000, device)

    z_t = torch.randn(*shape, device=device)
    noise_pred = torch.randn(*shape, device=device)

    # Make z_t temporally incoherent to force large corrections
    for t_frame in range(1, n_frames):
        z_t[:, :, t_frame] = torch.randn(
            batch_size, channels, height, width, device=device
        )

    timestep_ratios = []
    test_timesteps = [100, 300, 500, 700, 900]

    with torch.no_grad():
        for t in test_timesteps:
            corrected = fscsv.correct_noise_prediction(
                noise_pred, z_t, t, schedule,
            )
            correction = corrected - noise_pred
            ratio = correction.norm().item() / max(noise_pred.norm().item(), 1e-10)
            timestep_ratios.append(ratio)

    elapsed = (time.time() - start) * 1000

    return GradientSafetyResult(
        bound_violations=violations,
        total_checks=total,
        violation_rate=violation_rate,
        max_ratio=max_ratio,
        tau_01_ratio=ratio_01,
        tau_05_ratio=ratio_05,
        tau_10_ratio=ratio_10,
        scaling_monotonic=scaling_mono,
        extreme_input_clipped=extreme_clipped,
        extreme_output_bounded=extreme_bounded_ok,
        zero_pred_safe=zero_safe,
        timestep_ratios=timestep_ratios,
        elapsed_ms=elapsed,
    )


def print_results(result: GradientSafetyResult) -> bool:
    print("=" * 60)
    print("  BENCHMARK: Gradient Safety Bounds (Issue 7)")
    print("=" * 60)
    print()

    def check(v): return "\u2705" if v else "\u274c"

    no_violations = result.bound_violations == 0
    print(f"  1. Bound Enforcement (tau=0.1):")
    print(f"     Violations:  {result.bound_violations}/{result.total_checks}  "
          f"{check(no_violations)}")
    print(f"     Max ratio:   {result.max_ratio:.4f}  "
          f"(should be <= 1.0)")
    print()

    print(f"  2. Tau Scaling:")
    print(f"     tau=0.1: corr/pred = {result.tau_01_ratio:.4f}")
    print(f"     tau=0.5: corr/pred = {result.tau_05_ratio:.4f}")
    print(f"     tau=1.0: corr/pred = {result.tau_10_ratio:.4f}")
    print(f"     Monotonic: {check(result.scaling_monotonic)}")
    print()

    print(f"  3. Extreme Input (1000x normal gradient):")
    print(f"     Clipped: {check(result.extreme_input_clipped)}")
    print(f"     Bounded: {check(result.extreme_output_bounded)}")
    print()

    print(f"  4. Zero/Near-Zero Prediction:")
    print(f"     Safe (no NaN/Inf): {check(result.zero_pred_safe)}")
    print()

    print(f"  5. Per-Timestep Correction/Prediction Ratio:")
    timesteps = [100, 300, 500, 700, 900]
    for t, ratio in zip(timesteps, result.timestep_ratios):
        bar = "\u2588" * min(40, int(ratio * 400))
        print(f"     t={t:4d}: {ratio:.4f} {bar}")
    print()

    passed = (no_violations and result.scaling_monotonic and
              result.extreme_output_bounded and result.zero_pred_safe)
    print(f"  VERDICT: {'PASS' if passed else 'FAIL'}")
    print(f"  Time: {result.elapsed_ms:.1f}ms")
    print()
    return passed


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    result = run_benchmark(device=device)
    passed = print_results(result)
    sys.exit(0 if passed else 1)
