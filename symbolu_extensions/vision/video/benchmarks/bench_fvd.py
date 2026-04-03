"""
Benchmark: FVD / Video Quality Evaluation (Next Step 3).

Measures video generation quality using standard metrics:
    1. FVD (Frechet Video Distance) — distribution distance in feature space
    2. Inter-frame consistency (FSCS-V's primary target metric)
    3. Temporal smoothness (L1 frame difference)
    4. Diversity (variance across generations)

Compares baseline (no FSCS-V) vs FSCS-V-corrected generation.

Note: True FVD requires an I3D feature extractor and real reference videos.
This benchmark uses a synthetic proxy (random feature statistics) to
validate the metric computation pipeline. Replace with real I3D features
for production evaluation.
"""

import sys
import time
import torch
import torch.nn.functional as F
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class FVDResult:
    # FVD (lower is better)
    fvd_baseline: float
    fvd_fscsv: float
    fvd_improvement_pct: float
    # Inter-frame consistency (higher is better)
    consistency_baseline: float
    consistency_fscsv: float
    consistency_improvement_pct: float
    # Temporal smoothness (lower is better)
    smoothness_baseline: float
    smoothness_fscsv: float
    # Diversity (should be maintained, not collapsed)
    diversity_baseline: float
    diversity_fscsv: float
    diversity_ratio: float  # fscsv/baseline — should be ~1.0
    # Generation stats
    n_videos: int
    n_frames: int
    resolution: str
    elapsed_ms: float


def compute_fvd(mu1, sigma1, mu2, sigma2) -> float:
    """
    Compute Frechet Video Distance between two feature distributions.

    FVD = ||mu1 - mu2||^2 + Tr(sigma1 + sigma2 - 2*sqrt(sigma1 @ sigma2))

    Uses eigenvalue decomposition for matrix square root stability.
    """
    diff = mu1 - mu2
    fvd = float(np.dot(diff, diff))

    # Matrix square root via eigendecomposition
    product = sigma1 @ sigma2
    eigvals, eigvecs = np.linalg.eigh(product)
    eigvals = np.maximum(eigvals, 0)  # Numerical stability
    sqrt_product = eigvecs @ np.diag(np.sqrt(eigvals)) @ eigvecs.T

    fvd += float(np.trace(sigma1 + sigma2 - 2 * sqrt_product))
    return max(0.0, fvd)


def compute_inter_frame_consistency(video: torch.Tensor) -> float:
    """Mean cosine similarity between adjacent frames."""
    B, C, T, H, W = video.shape
    if T < 2:
        return 1.0
    features = video.mean(dim=(-2, -1))  # [B, C, T]
    prev = F.normalize(features[:, :, :-1], dim=1)
    curr = F.normalize(features[:, :, 1:], dim=1)
    cos_sim = (prev * curr).sum(dim=1)  # [B, T-1]
    return cos_sim.mean().item()


def compute_temporal_smoothness(video: torch.Tensor) -> float:
    """Mean L1 difference between adjacent frames (lower = smoother)."""
    B, C, T, H, W = video.shape
    if T < 2:
        return 0.0
    diffs = (video[:, :, 1:] - video[:, :, :-1]).abs().mean()
    return diffs.item()


def compute_diversity(videos: torch.Tensor) -> float:
    """Variance of global features across videos (higher = more diverse)."""
    features = videos.mean(dim=(-3, -2, -1))  # [B, C]
    return features.var(dim=0).mean().item()


def generate_synthetic_videos(
    n_videos: int, channels: int, n_frames: int,
    height: int, width: int, device: str,
    temporal_coherence: float = 0.0,
) -> torch.Tensor:
    """Generate synthetic videos with controllable temporal coherence."""
    videos = torch.randn(n_videos, channels, n_frames, height, width, device=device)

    if temporal_coherence > 0:
        for t in range(1, n_frames):
            videos[:, :, t] = (
                temporal_coherence * videos[:, :, t - 1] +
                (1 - temporal_coherence) * videos[:, :, t]
            )

    return videos


def run_benchmark(
    device: str = "cpu",
    n_videos: int = 16,
    channels: int = 16,
    n_frames: int = 8,
    height: int = 32,
    width: int = 32,
    feature_dim: int = 64,
    seed: int = 42,
) -> FVDResult:
    from symbolu.vision.video.fscsv_wrapper import FSCSVModule, FSCSVConfig

    torch.manual_seed(seed)
    np.random.seed(seed)
    start = time.time()

    # Generate "real" reference videos (high coherence)
    ref_videos = generate_synthetic_videos(
        n_videos, channels, n_frames, height, width, device,
        temporal_coherence=0.9,
    )

    # Generate baseline (low coherence — simulates uncorrected diffusion)
    baseline_videos = generate_synthetic_videos(
        n_videos, channels, n_frames, height, width, device,
        temporal_coherence=0.3,
    )

    # Apply FSCS-V correction to baseline
    config = FSCSVConfig(lambda_max=0.1, enable_bands=True, safety_tau=0.5)
    fscsv = FSCSVModule(config, latent_channels=channels).to(device)

    # Simulate denoising correction: apply correction at multiple timesteps
    fscsv_videos = baseline_videos.clone()

    # Create a mock noise schedule
    class MockSchedule:
        def __init__(self, T, device):
            betas = torch.linspace(1e-4, 0.02, T, device=device)
            alphas = 1 - betas
            self.sqrt_alphas_cumprod = torch.sqrt(torch.cumprod(alphas, dim=0))
            self.sqrt_one_minus_alphas_cumprod = torch.sqrt(
                1 - torch.cumprod(alphas, dim=0)
            )

    schedule = MockSchedule(1000, device)

    with torch.no_grad():
        # Apply correction at several timesteps (simulating denoising loop)
        for t in [800, 600, 400, 200]:
            noise_pred = torch.randn_like(fscsv_videos) * 0.1
            corrected = fscsv.correct_noise_prediction(
                noise_pred, fscsv_videos, t, schedule,
            )
            # Simulate one denoising step with correction
            fscsv_videos = fscsv_videos - 0.01 * corrected

    # ---- Compute metrics ----

    # Feature extraction (synthetic proxy for I3D)
    # In production, replace with: features = i3d_model(videos)
    def extract_features(videos):
        # Global average pooling per video
        return videos.mean(dim=(-2, -1)).reshape(videos.shape[0], -1)  # [B, C*T]

    ref_features = extract_features(ref_videos).cpu().numpy()
    base_features = extract_features(baseline_videos).cpu().numpy()
    fscsv_features = extract_features(fscsv_videos).cpu().numpy()

    # FVD computation
    ref_mu = ref_features.mean(axis=0)
    ref_sigma = np.cov(ref_features, rowvar=False) + np.eye(ref_features.shape[1]) * 1e-6

    base_mu = base_features.mean(axis=0)
    base_sigma = np.cov(base_features, rowvar=False) + np.eye(base_features.shape[1]) * 1e-6

    fscsv_mu = fscsv_features.mean(axis=0)
    fscsv_sigma = np.cov(fscsv_features, rowvar=False) + np.eye(fscsv_features.shape[1]) * 1e-6

    fvd_base = compute_fvd(ref_mu, ref_sigma, base_mu, base_sigma)
    fvd_fscsv = compute_fvd(ref_mu, ref_sigma, fscsv_mu, fscsv_sigma)
    fvd_improve = (fvd_base - fvd_fscsv) / max(fvd_base, 1e-8) * 100

    # Inter-frame consistency
    cons_base = compute_inter_frame_consistency(baseline_videos)
    cons_fscsv = compute_inter_frame_consistency(fscsv_videos)
    cons_improve = (cons_fscsv - cons_base) / max(abs(cons_base), 1e-8) * 100

    # Temporal smoothness
    smooth_base = compute_temporal_smoothness(baseline_videos)
    smooth_fscsv = compute_temporal_smoothness(fscsv_videos)

    # Diversity
    div_base = compute_diversity(baseline_videos)
    div_fscsv = compute_diversity(fscsv_videos)
    div_ratio = div_fscsv / max(div_base, 1e-8)

    elapsed = (time.time() - start) * 1000

    return FVDResult(
        fvd_baseline=fvd_base,
        fvd_fscsv=fvd_fscsv,
        fvd_improvement_pct=fvd_improve,
        consistency_baseline=cons_base,
        consistency_fscsv=cons_fscsv,
        consistency_improvement_pct=cons_improve,
        smoothness_baseline=smooth_base,
        smoothness_fscsv=smooth_fscsv,
        diversity_baseline=div_base,
        diversity_fscsv=div_fscsv,
        diversity_ratio=div_ratio,
        n_videos=n_videos,
        n_frames=n_frames,
        resolution=f"{height}x{width}",
        elapsed_ms=elapsed,
    )


def print_results(result: FVDResult) -> bool:
    print("=" * 60)
    print("  BENCHMARK: FVD / Video Quality (Next Step 3)")
    print("=" * 60)
    print()
    print(f"  Config: {result.n_videos} videos, {result.n_frames} frames, "
          f"{result.resolution}")
    print()

    def check(v): return "\u2705" if v else "\u274c"

    fvd_better = result.fvd_fscsv < result.fvd_baseline
    print(f"  1. FVD (lower = better):")
    print(f"     Baseline: {result.fvd_baseline:.1f}")
    print(f"     FSCS-V:   {result.fvd_fscsv:.1f}")
    print(f"     Change:   {result.fvd_improvement_pct:+.1f}%  {check(fvd_better)}")
    print()

    cons_better = result.consistency_fscsv > result.consistency_baseline
    print(f"  2. Inter-Frame Consistency (higher = better):")
    print(f"     Baseline: {result.consistency_baseline:.4f}")
    print(f"     FSCS-V:   {result.consistency_fscsv:.4f}")
    print(f"     Change:   {result.consistency_improvement_pct:+.1f}%  {check(cons_better)}")
    print()

    smooth_better = result.smoothness_fscsv <= result.smoothness_baseline
    print(f"  3. Temporal Smoothness (lower = smoother):")
    print(f"     Baseline: {result.smoothness_baseline:.4f}")
    print(f"     FSCS-V:   {result.smoothness_fscsv:.4f}  {check(smooth_better)}")
    print()

    div_preserved = result.diversity_ratio > 0.5
    print(f"  4. Diversity (should be preserved):")
    print(f"     Baseline: {result.diversity_baseline:.4f}")
    print(f"     FSCS-V:   {result.diversity_fscsv:.4f}")
    print(f"     Ratio:    {result.diversity_ratio:.2f}x  {check(div_preserved)}"
          f"  ({'preserved' if div_preserved else 'COLLAPSED'})")
    print()

    print(f"  NOTE: Using synthetic proxy features. For production:")
    print(f"    - Replace with I3D feature extractor for real FVD")
    print(f"    - Evaluate on UCF-101 / WebVid reference sets")
    print()

    passed = cons_better and div_preserved
    print(f"  VERDICT: {'PASS' if passed else 'FAIL'}")
    print(f"  Time: {result.elapsed_ms:.1f}ms")
    print()
    return passed


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    result = run_benchmark(device=device)
    passed = print_results(result)
    sys.exit(0 if passed else 1)
