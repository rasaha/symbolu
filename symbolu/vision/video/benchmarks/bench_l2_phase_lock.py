"""
Benchmark: L2 Phase-Locking vs Cosine Constraint (Issue 6).

Patent requirement:
    ||y_t - y_{t_s}||^2 <= delta^2   (L2 distance bound)

The patent explicitly rejected cosine/directional phase-locking because
"magnitude IS part of what we want to constrain." This benchmark compares:
    1. Cosine-only constraint (existing codebase)
    2. L2 distance constraint (patent requirement)
    3. Combined L2 + cosine (recommended)

Tests:
    - Magnitude drift detection: can each method catch scale changes?
    - Direction drift detection: can each method catch angular changes?
    - Combined drift: realistic identity drift scenario
    - Gradient quality: do corrections point in the right direction?
"""

import sys
import time
import torch
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Tuple


@dataclass
class PhaseLockResult:
    # Magnitude drift detection
    cosine_detects_magnitude: bool
    l2_detects_magnitude: bool
    combined_detects_magnitude: bool
    # Direction drift detection
    cosine_detects_direction: bool
    l2_detects_direction: bool
    combined_detects_direction: bool
    # Combined drift
    cosine_detects_combined: bool
    l2_detects_combined: bool
    combined_detects_combined: bool
    # Gradient quality (L2 only)
    l2_grad_reduces_distance: bool
    # Scores
    cosine_score: int  # out of 3
    l2_score: int
    combined_score: int
    elapsed_ms: float


def cosine_phase_lock_loss(
    current: torch.Tensor, reference: torch.Tensor,
    target_low: float = 0.8, target_high: float = 0.95,
) -> torch.Tensor:
    """Existing cosine-based phase lock (codebase default)."""
    cos_sim = F.cosine_similarity(current, reference, dim=-1)
    # Hinge loss: penalize if similarity drops below target_low
    loss = F.relu(target_low - cos_sim)
    return loss.mean()


def l2_phase_lock_loss(
    current: torch.Tensor, reference: torch.Tensor,
    delta: float = 1.0,
) -> torch.Tensor:
    """Patent-specified L2 distance constraint."""
    dist_sq = ((current - reference) ** 2).sum(dim=-1)
    # Hinge loss: penalize if distance exceeds delta^2
    loss = F.relu(dist_sq - delta ** 2)
    return loss.mean()


def combined_phase_lock_loss(
    current: torch.Tensor, reference: torch.Tensor,
    delta: float = 1.0, target_low: float = 0.8,
    l2_weight: float = 0.5, cos_weight: float = 0.5,
) -> torch.Tensor:
    """Combined L2 + cosine constraint."""
    l2 = l2_phase_lock_loss(current, reference, delta)
    cos = cosine_phase_lock_loss(current, reference, target_low)
    return l2_weight * l2 + cos_weight * cos


def run_benchmark(
    device: str = "cpu",
    feature_dim: int = 256,
    n_frames: int = 32,
    seed: int = 42,
) -> PhaseLockResult:
    torch.manual_seed(seed)
    start = time.time()

    # Reference frame features
    reference = torch.randn(1, feature_dim, device=device)
    reference = reference / reference.norm() * 5.0  # Give it magnitude

    # Test 1: Magnitude drift (scale reference by 2x, keep direction)
    mag_drift = reference * 2.0
    mag_drift_noisy = mag_drift + torch.randn_like(mag_drift) * 0.01

    cos_mag = cosine_phase_lock_loss(mag_drift_noisy, reference).item()
    l2_mag = l2_phase_lock_loss(mag_drift_noisy, reference, delta=1.0).item()
    comb_mag = combined_phase_lock_loss(mag_drift_noisy, reference).item()

    # Cosine should NOT detect magnitude drift (same direction)
    # L2 SHOULD detect it (different magnitude)
    cos_detects_mag = cos_mag > 0.01
    l2_detects_mag = l2_mag > 0.01
    comb_detects_mag = comb_mag > 0.01

    # Test 2: Direction drift (rotate by ~45 degrees, keep magnitude)
    rotation = torch.randn_like(reference)
    rotation = rotation / rotation.norm() * reference.norm()
    dir_drift = F.normalize(reference + rotation * 0.8, dim=-1) * reference.norm()

    cos_dir = cosine_phase_lock_loss(dir_drift, reference).item()
    l2_dir = l2_phase_lock_loss(dir_drift, reference, delta=1.0).item()
    comb_dir = combined_phase_lock_loss(dir_drift, reference).item()

    cos_detects_dir = cos_dir > 0.01
    l2_detects_dir = l2_dir > 0.01
    comb_detects_dir = comb_dir > 0.01

    # Test 3: Combined drift (scale AND rotate — realistic scenario)
    combined_drift = dir_drift * 1.5
    cos_comb = cosine_phase_lock_loss(combined_drift, reference).item()
    l2_comb = l2_phase_lock_loss(combined_drift, reference, delta=1.0).item()
    comb_comb = combined_phase_lock_loss(combined_drift, reference).item()

    cos_detects_comb = cos_comb > 0.01
    l2_detects_comb = l2_comb > 0.01
    comb_detects_comb = comb_comb > 0.01

    # Test 4: Gradient quality for L2
    current = combined_drift.clone().requires_grad_(True)
    loss = l2_phase_lock_loss(current, reference.detach(), delta=1.0)
    loss.backward()
    grad = current.grad

    # Apply gradient step and check if distance decreases
    updated = current.data - 0.1 * grad
    dist_before = (current.data - reference).norm().item()
    dist_after = (updated - reference).norm().item()
    l2_grad_reduces = dist_after < dist_before

    # Scores
    cos_score = sum([cos_detects_mag, cos_detects_dir, cos_detects_comb])
    l2_score = sum([l2_detects_mag, l2_detects_dir, l2_detects_comb])
    combined_score = sum([comb_detects_mag, comb_detects_dir, comb_detects_comb])

    elapsed = (time.time() - start) * 1000

    return PhaseLockResult(
        cosine_detects_magnitude=cos_detects_mag,
        l2_detects_magnitude=l2_detects_mag,
        combined_detects_magnitude=comb_detects_mag,
        cosine_detects_direction=cos_detects_dir,
        l2_detects_direction=l2_detects_dir,
        combined_detects_direction=comb_detects_dir,
        cosine_detects_combined=cos_detects_comb,
        l2_detects_combined=l2_detects_comb,
        combined_detects_combined=comb_detects_comb,
        l2_grad_reduces_distance=l2_grad_reduces,
        cosine_score=cos_score,
        l2_score=l2_score,
        combined_score=combined_score,
        elapsed_ms=elapsed,
    )


def print_results(result: PhaseLockResult) -> bool:
    print("=" * 60)
    print("  BENCHMARK: L2 Phase-Locking (Issue 6)")
    print("=" * 60)
    print()

    def check(v): return "\u2705" if v else "\u274c"

    print("  Drift Detection Matrix:")
    print("  " + "-" * 50)
    print(f"  {'Drift Type':<20} {'Cosine':<10} {'L2':<10} {'Combined':<10}")
    print("  " + "-" * 50)
    print(f"  {'Magnitude (2x)':<20} {check(result.cosine_detects_magnitude):<10} "
          f"{check(result.l2_detects_magnitude):<10} {check(result.combined_detects_magnitude):<10}")
    print(f"  {'Direction (~45deg)':<20} {check(result.cosine_detects_direction):<10} "
          f"{check(result.l2_detects_direction):<10} {check(result.combined_detects_direction):<10}")
    print(f"  {'Combined':<20} {check(result.cosine_detects_combined):<10} "
          f"{check(result.l2_detects_combined):<10} {check(result.combined_detects_combined):<10}")
    print("  " + "-" * 50)
    print(f"  {'Score':<20} {result.cosine_score}/3{'':<6} "
          f"{result.l2_score}/3{'':<6} {result.combined_score}/3")
    print()
    print(f"  L2 Gradient Quality: {check(result.l2_grad_reduces_distance)} "
          f"{'reduces distance' if result.l2_grad_reduces_distance else 'WRONG DIRECTION'}")
    print()

    # Patent requirement: magnitude MUST be constrained
    patent_satisfied = result.l2_detects_magnitude or result.combined_detects_magnitude
    cosine_blind = not result.cosine_detects_magnitude
    print(f"  Patent Analysis:")
    print(f"    Cosine blind to magnitude: {check(cosine_blind)} "
          f"{'Confirmed (matches patent Section 13.2)' if cosine_blind else 'Unexpected'}")
    print(f"    L2 constrains magnitude:   {check(result.l2_detects_magnitude)}")
    print(f"    Combined covers all drift: {check(result.combined_score == 3)}")
    print()

    passed = patent_satisfied and result.l2_grad_reduces_distance
    verdict = "PASS" if passed else "FAIL"
    recommendation = "Combined (L2 + Cosine)" if result.combined_score >= result.l2_score else "L2 only"
    print(f"  VERDICT: {verdict}")
    print(f"  Recommendation: Use {recommendation}")
    print(f"  Time: {result.elapsed_ms:.1f}ms")
    print()
    return passed


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    result = run_benchmark(device=device)
    passed = print_results(result)
    sys.exit(0 if passed else 1)
