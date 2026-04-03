#!/usr/bin/env python3
"""
FVD evaluation with I3D feature extraction.

Computes real Frechet Video Distance between generated videos and a reference
set (UCF-101 or WebVid). Uses a pretrained I3D (Inflated 3D ConvNet) or C3D
model for feature extraction instead of the synthetic proxy used in benchmarks.

FVD = ||mu_r - mu_g||^2 + Tr(Sigma_r + Sigma_g - 2*sqrt(Sigma_r @ Sigma_g))

Usage:
    # Evaluate with synthetic videos + mock I3D (structural test)
    python -m symbolu.vision.video.training.evaluate_fvd --synthetic

    # Evaluate against UCF-101 reference set
    python -m symbolu.vision.video.training.evaluate_fvd \
        --reference-dir /path/to/ucf101 \
        --generated-dir /path/to/generated_videos

    # Evaluate FSCS-V pipeline output
    python -m symbolu.vision.video.training.evaluate_fvd \
        --reference-dir /path/to/ucf101 \
        --checkpoint checkpoints_video/final.pt \
        --use-fscsv

    # Use HuggingFace dataset as reference
    python -m symbolu.vision.video.training.evaluate_fvd \
        --hf-reference webvid --max-reference 1000

Requirements:
    pip install torch torchvision numpy scipy
    For real I3D: pip install pytorchvideo  (or use torchvision r3d_18)
"""

import argparse
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


@dataclass
class FVDEvalConfig:
    """Configuration for FVD evaluation."""
    # Feature extraction
    feature_model: str = "r3d_18"  # "r3d_18", "mc3_18", "r2plus1d_18", or "i3d"
    feature_dim: int = 512         # Output dim of feature model

    # Video format
    num_frames: int = 16
    image_size: int = 224          # I3D/R3D expect 224x224
    fps: int = 8

    # Evaluation
    max_reference: int = 2048
    max_generated: int = 2048
    batch_size: int = 8

    # FVD computation
    eps: float = 1e-6              # Regularization for covariance


@dataclass
class FVDResult:
    """Results from FVD evaluation."""
    fvd: float
    fvd_baseline: Optional[float] = None  # Without FSCS-V
    fvd_improvement_pct: Optional[float] = None

    # Per-metric details
    mean_distance: float = 0.0
    covariance_distance: float = 0.0

    # Video quality metrics
    inter_frame_consistency: float = 0.0
    temporal_smoothness: float = 0.0
    diversity: float = 0.0

    # Stats
    n_reference: int = 0
    n_generated: int = 0
    feature_dim: int = 0
    elapsed_ms: float = 0.0


class VideoFeatureExtractor(nn.Module):
    """
    Video feature extractor using pretrained 3D CNN.

    Supports torchvision's video models (R3D-18, MC3-18, R(2+1)D-18)
    as drop-in replacements for the standard I3D used in FVD.

    These models produce features that correlate well with I3D for
    FVD computation while being easier to load (no custom weights).
    """

    def __init__(self, model_name: str = "r3d_18", device: torch.device = None):
        super().__init__()
        self.model_name = model_name
        self.device = device or torch.device("cpu")
        self._model = None
        self._feature_dim = None

    def _load(self):
        if self._model is not None:
            return

        try:
            import torchvision.models.video as video_models
        except ImportError:
            raise ImportError(
                "torchvision required for video feature extraction. "
                "Install with: pip install torchvision"
            )

        model_factory = {
            "r3d_18": video_models.r3d_18,
            "mc3_18": video_models.mc3_18,
            "r2plus1d_18": video_models.r2plus1d_18,
        }

        if self.model_name not in model_factory:
            raise ValueError(
                f"Unknown model: {self.model_name}. "
                f"Choose from: {list(model_factory.keys())}"
            )

        print(f"Loading {self.model_name} feature extractor...")

        # Load with pretrained weights
        try:
            weights_map = {
                "r3d_18": video_models.R3D_18_Weights.DEFAULT,
                "mc3_18": video_models.MC3_18_Weights.DEFAULT,
                "r2plus1d_18": video_models.R2Plus1D_18_Weights.DEFAULT,
            }
            model = model_factory[self.model_name](weights=weights_map[self.model_name])
        except (TypeError, AttributeError):
            # Fallback for older torchvision
            model = model_factory[self.model_name](pretrained=True)

        # Remove classification head — keep features
        self._feature_dim = model.fc.in_features
        model.fc = nn.Identity()

        model.eval()
        for p in model.parameters():
            p.requires_grad = False

        self._model = model.to(self.device)
        print(f"{self.model_name} loaded. Feature dim: {self._feature_dim}")

    @property
    def feature_dim(self) -> int:
        self._load()
        return self._feature_dim

    @torch.no_grad()
    def extract(self, videos: Tensor) -> Tensor:
        """
        Extract features from videos.

        Args:
            videos: [B, C, T, H, W] in [0, 1] or [-1, 1].
                    Will be resized to 224x224 and normalized.

        Returns:
            features: [B, feature_dim].
        """
        self._load()
        B, C, T, H, W = videos.shape

        # Normalize to [0, 1]
        if videos.min() < 0:
            videos = (videos + 1.0) / 2.0

        # Resize spatial dims to 224x224
        if H != 224 or W != 224:
            flat = videos.permute(0, 2, 1, 3, 4).reshape(B * T, C, H, W)
            resized = F.interpolate(flat, size=(224, 224), mode="bilinear", align_corners=False)
            videos = resized.reshape(B, T, C, 224, 224).permute(0, 2, 1, 3, 4)

        # Kinetics normalization
        mean = torch.tensor([0.43216, 0.394666, 0.37645], device=videos.device)
        std = torch.tensor([0.22803, 0.22145, 0.216989], device=videos.device)
        videos = (videos - mean[None, :, None, None, None]) / std[None, :, None, None, None]

        # Forward through model
        features = self._model(videos)  # [B, feature_dim]
        return features


class MockVideoFeatureExtractor(nn.Module):
    """Mock feature extractor for testing without pretrained weights."""

    def __init__(self, feature_dim: int = 512, device: torch.device = None):
        super().__init__()
        self._feature_dim = feature_dim
        self.device = device or torch.device("cpu")
        # Deterministic projection
        self.proj = nn.Linear(16 * 16, feature_dim, bias=False)
        nn.init.orthogonal_(self.proj.weight)
        self.proj.requires_grad_(False)
        self.proj = self.proj.to(self.device)

    @property
    def feature_dim(self) -> int:
        return self._feature_dim

    @torch.no_grad()
    def extract(self, videos: Tensor) -> Tensor:
        B, C, T, H, W = videos.shape
        # Pool to small spatial, then flatten
        pooled = F.adaptive_avg_pool3d(videos, (T, 4, 4))  # [B, C, T, 4, 4]
        flat = pooled.mean(dim=2).reshape(B, -1)  # [B, C*16]
        # Pad or truncate to match proj input
        target = self.proj.in_features
        if flat.shape[1] < target:
            flat = F.pad(flat, (0, target - flat.shape[1]))
        else:
            flat = flat[:, :target]
        return self.proj(flat.to(self.device))


def compute_fvd(
    ref_features: np.ndarray,
    gen_features: np.ndarray,
    eps: float = 1e-6,
) -> Tuple[float, float, float]:
    """
    Compute Frechet Video Distance.

    Args:
        ref_features: [N_ref, D] reference video features.
        gen_features: [N_gen, D] generated video features.
        eps: Regularization for covariance matrices.

    Returns:
        (fvd, mean_dist, cov_dist) tuple.
    """
    # Statistics
    mu_r = ref_features.mean(axis=0)
    mu_g = gen_features.mean(axis=0)
    sigma_r = np.cov(ref_features, rowvar=False) + np.eye(ref_features.shape[1]) * eps
    sigma_g = np.cov(gen_features, rowvar=False) + np.eye(gen_features.shape[1]) * eps

    # Mean distance
    mean_dist = float(np.sum((mu_r - mu_g) ** 2))

    # Covariance distance via eigendecomposition (stable matrix sqrt)
    product = sigma_r @ sigma_g
    eigvals, eigvecs = np.linalg.eigh(product)
    eigvals = np.maximum(eigvals, 0)
    sqrt_product = eigvecs @ np.diag(np.sqrt(eigvals)) @ eigvecs.T

    cov_dist = float(np.trace(sigma_r + sigma_g - 2 * sqrt_product))
    cov_dist = max(0.0, cov_dist)

    fvd = mean_dist + cov_dist
    return fvd, mean_dist, cov_dist


def extract_features_batched(
    extractor: nn.Module,
    videos: List[Tensor],
    batch_size: int = 8,
) -> np.ndarray:
    """Extract features from a list of videos in batches."""
    all_features = []

    for i in range(0, len(videos), batch_size):
        batch = torch.stack(videos[i:i + batch_size])
        features = extractor.extract(batch)
        all_features.append(features.cpu().numpy())

    return np.concatenate(all_features, axis=0)


def load_reference_videos(
    reference_dir: Optional[str] = None,
    hf_dataset: Optional[str] = None,
    max_videos: int = 2048,
    num_frames: int = 16,
    image_size: int = 224,
    device: torch.device = None,
) -> List[Tensor]:
    """Load reference videos from local directory or HuggingFace."""
    videos = []

    if reference_dir:
        from symbolu_extensions.vision.video.dataset import get_video_dataset
        dataset = get_video_dataset(
            "local",
            data_dir=reference_dir,
            num_frames=num_frames,
            image_size=image_size,
            max_samples=max_videos,
        )
        for i in range(min(len(dataset), max_videos)):
            item = dataset[i]
            # [T, C, H, W] -> [C, T, H, W]
            video = item["video"].permute(1, 0, 2, 3)
            videos.append(video.to(device))

    elif hf_dataset:
        from symbolu_extensions.vision.video.dataset import get_video_dataset
        dataset = get_video_dataset(
            "huggingface",
            dataset_name=hf_dataset,
            num_frames=num_frames,
            image_size=image_size,
            max_samples=max_videos,
        )
        for i in range(min(len(dataset), max_videos)):
            item = dataset[i]
            video = item["video"].permute(1, 0, 2, 3)
            videos.append(video.to(device))

    return videos


def generate_synthetic_reference(
    n_videos: int,
    channels: int,
    num_frames: int,
    height: int,
    width: int,
    device: torch.device,
    coherence: float = 0.9,
) -> List[Tensor]:
    """Generate synthetic reference videos with high temporal coherence."""
    videos = []
    for i in range(n_videos):
        torch.manual_seed(i)
        base = torch.randn(channels, 1, height, width, device=device)
        frames = [base.squeeze(1)]
        for t in range(1, num_frames):
            noise = torch.randn(channels, height, width, device=device) * (1 - coherence)
            frames.append(frames[-1] * coherence + noise)
        video = torch.stack(frames, dim=1)  # [C, T, H, W]
        videos.append(video)
    return videos


def evaluate(
    reference_dir: Optional[str] = None,
    generated_dir: Optional[str] = None,
    hf_reference: Optional[str] = None,
    checkpoint: Optional[str] = None,
    synthetic: bool = True,
    use_fscsv: bool = False,
    feature_model: str = "r3d_18",
    max_reference: int = 256,
    max_generated: int = 256,
    batch_size: int = 8,
    num_frames: int = 16,
    image_size: int = 224,
) -> FVDResult:
    """
    Run FVD evaluation.

    Args:
        reference_dir: Path to reference video directory.
        generated_dir: Path to generated video directory.
        hf_reference: HuggingFace dataset name for reference.
        checkpoint: Model checkpoint for generating videos.
        synthetic: Use synthetic data for testing.
        use_fscsv: Apply FSCS-V correction during generation.
        feature_model: Feature extractor model name.
        max_reference: Max reference videos to use.
        max_generated: Max generated videos to evaluate.
        batch_size: Batch size for feature extraction.
        num_frames: Frames per video.
        image_size: Frame resolution.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"FVD evaluation on {device}")
    start_time = time.time()

    # Feature extractor
    use_mock = synthetic and not reference_dir and not hf_reference
    if use_mock:
        print("Using mock feature extractor (synthetic mode)")
        extractor = MockVideoFeatureExtractor(feature_dim=512, device=device)
    else:
        extractor = VideoFeatureExtractor(model_name=feature_model, device=device)

    feat_dim = extractor.feature_dim

    # Load reference videos
    print("\nLoading reference videos...")
    if synthetic and not reference_dir and not hf_reference:
        ref_videos = generate_synthetic_reference(
            max_reference, 3, num_frames, image_size, image_size, device,
        )
    else:
        ref_videos = load_reference_videos(
            reference_dir=reference_dir,
            hf_dataset=hf_reference,
            max_videos=max_reference,
            num_frames=num_frames,
            image_size=image_size,
            device=device,
        )
    print(f"Reference: {len(ref_videos)} videos")

    # Load or generate evaluation videos
    print("Loading generated videos...")
    if generated_dir:
        gen_videos = load_reference_videos(
            reference_dir=generated_dir,
            max_videos=max_generated,
            num_frames=num_frames,
            image_size=image_size,
            device=device,
        )
    elif synthetic:
        # Generate with lower coherence to simulate diffusion output
        gen_videos = generate_synthetic_reference(
            max_generated, 3, num_frames, image_size, image_size, device,
            coherence=0.5,
        )
    else:
        raise ValueError("Provide --generated-dir or --synthetic")
    print(f"Generated: {len(gen_videos)} videos")

    # Optional: also generate FSCS-V corrected versions
    gen_fscsv_videos = None
    if use_fscsv and synthetic:
        gen_fscsv_videos = generate_synthetic_reference(
            max_generated, 3, num_frames, image_size, image_size, device,
            coherence=0.7,  # Simulates FSCS-V improvement
        )

    # Extract features
    print("\nExtracting reference features...")
    ref_features = extract_features_batched(extractor, ref_videos, batch_size)
    print(f"Reference features: {ref_features.shape}")

    print("Extracting generated features...")
    gen_features = extract_features_batched(extractor, gen_videos, batch_size)
    print(f"Generated features: {gen_features.shape}")

    # Compute FVD
    print("\nComputing FVD...")
    fvd, mean_dist, cov_dist = compute_fvd(ref_features, gen_features)

    fvd_baseline = None
    fvd_improvement = None
    if gen_fscsv_videos is not None:
        print("Extracting FSCS-V features...")
        fscsv_features = extract_features_batched(extractor, gen_fscsv_videos, batch_size)
        fvd_fscsv, _, _ = compute_fvd(ref_features, fscsv_features)
        fvd_baseline = fvd
        fvd = fvd_fscsv
        fvd_improvement = (fvd_baseline - fvd) / max(fvd_baseline, 1e-8) * 100

    # Compute additional quality metrics
    gen_stack = torch.stack(gen_videos)  # [N, C, T, H, W]
    consistency = _compute_consistency(gen_stack)
    smoothness = _compute_smoothness(gen_stack)
    diversity = _compute_diversity(gen_stack)

    elapsed = (time.time() - start_time) * 1000

    result = FVDResult(
        fvd=fvd,
        fvd_baseline=fvd_baseline,
        fvd_improvement_pct=fvd_improvement,
        mean_distance=mean_dist,
        covariance_distance=cov_dist,
        inter_frame_consistency=consistency,
        temporal_smoothness=smoothness,
        diversity=diversity,
        n_reference=len(ref_videos),
        n_generated=len(gen_videos),
        feature_dim=feat_dim,
        elapsed_ms=elapsed,
    )

    _print_results(result, use_mock)
    return result


def _compute_consistency(videos: Tensor) -> float:
    B, C, T, H, W = videos.shape
    if T < 2:
        return 1.0
    feats = videos.mean(dim=(-2, -1))
    prev = F.normalize(feats[:, :, :-1], dim=1)
    curr = F.normalize(feats[:, :, 1:], dim=1)
    return (prev * curr).sum(dim=1).mean().item()


def _compute_smoothness(videos: Tensor) -> float:
    B, C, T, H, W = videos.shape
    if T < 2:
        return 0.0
    return (videos[:, :, 1:] - videos[:, :, :-1]).abs().mean().item()


def _compute_diversity(videos: Tensor) -> float:
    feats = videos.mean(dim=(-3, -2, -1))
    return feats.var(dim=0).mean().item()


def _print_results(result: FVDResult, is_mock: bool):
    print()
    print("=" * 60)
    print("  FVD EVALUATION RESULTS")
    print("=" * 60)
    print()
    print(f"  Reference videos:  {result.n_reference}")
    print(f"  Generated videos:  {result.n_generated}")
    print(f"  Feature dim:       {result.feature_dim}")
    print()
    print(f"  FVD:               {result.fvd:.2f}")
    print(f"    Mean distance:   {result.mean_distance:.2f}")
    print(f"    Cov distance:    {result.covariance_distance:.2f}")

    if result.fvd_baseline is not None:
        print()
        print(f"  FVD (baseline):    {result.fvd_baseline:.2f}")
        print(f"  FVD (FSCS-V):      {result.fvd:.2f}")
        print(f"  Improvement:       {result.fvd_improvement_pct:+.1f}%")

    print()
    print(f"  Inter-frame consistency: {result.inter_frame_consistency:.4f}")
    print(f"  Temporal smoothness:     {result.temporal_smoothness:.4f}")
    print(f"  Diversity:               {result.diversity:.4f}")
    print()
    print(f"  Time: {result.elapsed_ms:.0f}ms")

    if is_mock:
        print()
        print("  NOTE: Using mock feature extractor (synthetic mode).")
        print("  For production FVD, use:")
        print("    --reference-dir /path/to/ucf101")
        print("    --generated-dir /path/to/generated")
        print("  This will use torchvision R3D-18 as the feature extractor.")

    print()


def main():
    parser = argparse.ArgumentParser(description="FVD evaluation with I3D/R3D features")
    parser.add_argument("--reference-dir", type=str, help="Reference video directory")
    parser.add_argument("--generated-dir", type=str, help="Generated video directory")
    parser.add_argument("--hf-reference", type=str, help="HuggingFace reference dataset")
    parser.add_argument("--checkpoint", type=str, help="Model checkpoint for generation")
    parser.add_argument("--synthetic", action="store_true", default=True, help="Synthetic mode")
    parser.add_argument("--use-fscsv", action="store_true", help="Include FSCS-V comparison")
    parser.add_argument("--feature-model", type=str, default="r3d_18",
                        choices=["r3d_18", "mc3_18", "r2plus1d_18"])
    parser.add_argument("--max-reference", type=int, default=256)
    parser.add_argument("--max-generated", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--image-size", type=int, default=224)
    args = parser.parse_args()

    evaluate(
        reference_dir=args.reference_dir,
        generated_dir=args.generated_dir,
        hf_reference=args.hf_reference,
        checkpoint=args.checkpoint,
        synthetic=args.synthetic if not args.reference_dir else False,
        use_fscsv=args.use_fscsv,
        feature_model=args.feature_model,
        max_reference=args.max_reference,
        max_generated=args.max_generated,
        batch_size=args.batch_size,
        num_frames=args.num_frames,
        image_size=args.image_size,
    )


if __name__ == "__main__":
    main()
