"""
Benchmark: Rectification Gap (Issue 1).

Validates that applying (cos+1)/2 rectification to C' = C * S produces
correct [0,1] bounded outputs and prevents gradient inversions in the
diffusion injection pathway.

Patent requirement:
    C+ = (cos+1)/2,  S+ = (cos+1)/2,  C' = C+ * S+
    All values in [0,1], no negative coherence signals.

Tests:
    1. Raw cosine C*S can produce negative values (proves the problem)
    2. Rectified C+*S+ is always in [0,1]
    3. Discrimination power preserved after rectification
    4. Gradient direction correctness (positive coherence = attraction)
"""

import sys
import time
import torch
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class RectificationResult:
    raw_min: float
    raw_max: float
    raw_mean: float
    raw_negative_pct: float
    rect_min: float
    rect_max: float
    rect_mean: float
    rect_negative_pct: float
    discrimination_raw: float
    discrimination_rect: float
    gradient_sign_correct: bool
    elapsed_ms: float


def compute_raw_coherence(
    features_a: torch.Tensor, features_b: torch.Tensor
) -> torch.Tensor:
    """Raw cosine C*S without rectification (existing codebase behavior)."""
    # Semantic similarity (raw cosine, [-1, 1])
    a_norm = F.normalize(features_a, dim=-1)
    b_norm = F.normalize(features_b, dim=-1)
    S = (a_norm * b_norm).sum(dim=-1)

    # Phase correlation (raw, [-1, 1])
    D = features_a.shape[-1]
    half = D // 2
    a_re, a_im = features_a[..., :half], features_a[..., half:2*half]
    b_re, b_im = features_b[..., :half], features_b[..., half:2*half]
    cross_re = a_re * b_re + a_im * b_im
    a_mag = torch.sqrt(a_re**2 + a_im**2 + 1e-8)
    b_mag = torch.sqrt(b_re**2 + b_im**2 + 1e-8)
    C = (cross_re / (a_mag * b_mag + 1e-8)).mean(dim=-1)

    return C * S  # Can be negative


def compute_rectified_coherence(
    features_a: torch.Tensor, features_b: torch.Tensor
) -> torch.Tensor:
    """Rectified C+ * S+ per patent D1-D3."""
    from symbolu_extensions.vision.video.fscsv_wrapper import (
        compute_phase_correlation,
        compute_semantic_similarity,
    )
    C_plus = compute_phase_correlation(features_a, features_b)
    S_plus = compute_semantic_similarity(features_a, features_b)
    return C_plus * S_plus


def run_benchmark(
    device: str = "cpu",
    n_samples: int = 1000,
    feature_dim: int = 256,
    seed: int = 42,
) -> RectificationResult:
    """Run rectification benchmark."""
    torch.manual_seed(seed)
    start = time.time()

    # Generate test data: similar pairs (coherent) and random pairs
    base = torch.randn(n_samples, feature_dim, device=device)
    noise_small = torch.randn_like(base) * 0.3
    noise_large = torch.randn_like(base) * 2.0

    similar_a = base
    similar_b = base + noise_small
    random_a = base
    random_b = torch.randn_like(base)
    adversarial_b = -base + noise_small  # Opposite direction

    # Combine all pairs
    all_a = torch.cat([similar_a, random_a, base], dim=0)
    all_b = torch.cat([similar_b, random_b, adversarial_b], dim=0)

    # Raw coherence
    raw = compute_raw_coherence(all_a, all_b)
    raw_neg_pct = (raw < 0).float().mean().item() * 100

    # Rectified coherence
    rect = compute_rectified_coherence(all_a, all_b)
    rect_neg_pct = (rect < 0).float().mean().item() * 100

    # Discrimination: ratio of coherent-pair score to random-pair score
    raw_coherent = compute_raw_coherence(similar_a, similar_b).mean().item()
    raw_random = compute_raw_coherence(random_a, random_b).mean().item()
    rect_coherent = compute_rectified_coherence(similar_a, similar_b).mean().item()
    rect_random = compute_rectified_coherence(random_a, random_b).mean().item()

    disc_raw = raw_coherent / max(abs(raw_random), 1e-8)
    disc_rect = rect_coherent / max(abs(rect_random), 1e-8)

    # Gradient sign test: increasing coherence should push frames together
    # Coherent pair should have higher C' than random pair
    gradient_correct = (rect_coherent > rect_random) and (rect.min().item() >= 0.0)

    elapsed = (time.time() - start) * 1000

    return RectificationResult(
        raw_min=raw.min().item(),
        raw_max=raw.max().item(),
        raw_mean=raw.mean().item(),
        raw_negative_pct=raw_neg_pct,
        rect_min=rect.min().item(),
        rect_max=rect.max().item(),
        rect_mean=rect.mean().item(),
        rect_negative_pct=rect_neg_pct,
        discrimination_raw=disc_raw,
        discrimination_rect=disc_rect,
        gradient_sign_correct=gradient_correct,
        elapsed_ms=elapsed,
    )


def print_results(result: RectificationResult):
    print("=" * 60)
    print("  BENCHMARK: Rectification Gap (Issue 1)")
    print("=" * 60)
    print()
    print("  Raw Cosine C*S (unrectified):")
    print(f"    Range: [{result.raw_min:.4f}, {result.raw_max:.4f}]")
    print(f"    Mean:  {result.raw_mean:.4f}")
    print(f"    Negative values: {result.raw_negative_pct:.1f}%")
    print()
    print("  Rectified C+ * S+ (patent D1-D3):")
    print(f"    Range: [{result.rect_min:.4f}, {result.rect_max:.4f}]")
    print(f"    Mean:  {result.rect_mean:.4f}")
    print(f"    Negative values: {result.rect_negative_pct:.1f}%")
    print()
    print("  Discrimination Power:")
    print(f"    Raw:       {result.discrimination_raw:.2f}x (coherent/random)")
    print(f"    Rectified: {result.discrimination_rect:.2f}x (coherent/random)")
    print()
    status = "PASS" if result.gradient_sign_correct else "FAIL"
    symbol = "\u2705" if result.gradient_sign_correct else "\u274c"
    print(f"  Gradient Direction: {symbol} {status}")
    print()

    # Overall verdict
    issues = []
    if result.raw_negative_pct > 0:
        issues.append(f"Raw produces {result.raw_negative_pct:.1f}% negative values (EXPECTED)")
    if result.rect_negative_pct > 0:
        issues.append(f"RECTIFIED has {result.rect_negative_pct:.1f}% negative values (BUG)")
    if not result.gradient_sign_correct:
        issues.append("Gradient sign incorrect (BUG)")
    if result.discrimination_rect < 1.1:
        issues.append(f"Weak discrimination ({result.discrimination_rect:.2f}x)")

    passed = result.rect_negative_pct == 0 and result.gradient_sign_correct
    verdict = "PASS" if passed else "FAIL"
    print(f"  VERDICT: {verdict}")
    for issue in issues:
        print(f"    - {issue}")
    print(f"  Time: {result.elapsed_ms:.1f}ms")
    print()
    return passed


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    result = run_benchmark(device=device)
    passed = print_results(result)
    sys.exit(0 if passed else 1)
