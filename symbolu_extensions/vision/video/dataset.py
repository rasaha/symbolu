"""
Dataset loaders for Phase-Quad Video Generator training.

Supports loading video-text pairs from various sources:
- Local directories (videos + captions)
- HuggingFace video datasets
- Synthetic data for testing

Requirements:
    pip install datasets pillow decord av
"""

import os
import json
import random
from pathlib import Path
from typing import Optional, List, Tuple, Callable, Dict, Any

import torch
from torch import Tensor
from torch.utils.data import Dataset, DataLoader

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import torchvision.transforms as T
    HAS_TORCHVISION = True
except ImportError:
    HAS_TORCHVISION = False


def get_video_transforms(
    image_size: int = 256,
    center_crop: bool = True,
) -> Callable:
    """
    Get standard video frame transforms for training.

    Args:
        image_size: Target frame size (square).
        center_crop: Whether to center crop.

    Returns:
        Transform function.
    """
    if not HAS_TORCHVISION:
        raise ImportError("torchvision required. Install with: pip install torchvision")

    transforms = [
        T.Resize(image_size, interpolation=T.InterpolationMode.BILINEAR),
    ]

    if center_crop:
        transforms.append(T.CenterCrop(image_size))
    else:
        transforms.append(T.RandomCrop(image_size))

    transforms.extend([
        T.ToTensor(),
        T.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),  # -> [-1, 1]
    ])

    return T.Compose(transforms)


def load_video_frames(
    video_path: str,
    num_frames: int = 16,
    sample_rate: int = 1,
    start_frame: int = 0,
) -> List["Image.Image"]:
    """
    Load frames from a video file.

    Tries decord first, falls back to PyAV.

    Args:
        video_path: Path to video file.
        num_frames: Number of frames to extract.
        sample_rate: Sample every N frames.
        start_frame: Starting frame index.

    Returns:
        List of PIL Images.
    """
    try:
        # Try decord first (faster)
        import decord
        decord.bridge.set_bridge("torch")

        vr = decord.VideoReader(video_path)
        total_frames = len(vr)

        # Calculate frame indices
        indices = []
        for i in range(num_frames):
            frame_idx = start_frame + i * sample_rate
            if frame_idx >= total_frames:
                frame_idx = total_frames - 1
            indices.append(frame_idx)

        frames = vr.get_batch(indices).numpy()
        return [Image.fromarray(f) for f in frames]

    except ImportError:
        pass

    try:
        # Fall back to PyAV
        import av

        container = av.open(video_path)
        stream = container.streams.video[0]

        frames = []
        frame_count = 0
        target_count = 0

        for frame in container.decode(stream):
            if frame_count >= start_frame + target_count * sample_rate:
                img = frame.to_image()
                frames.append(img)
                target_count += 1
                if target_count >= num_frames:
                    break
            frame_count += 1

        container.close()

        # Pad if needed
        while len(frames) < num_frames:
            frames.append(frames[-1] if frames else Image.new("RGB", (256, 256)))

        return frames

    except ImportError:
        raise ImportError(
            "Video reading requires decord or av. "
            "Install with: pip install decord or pip install av"
        )


class LocalVideoTextDataset(Dataset):
    """
    Load video-text pairs from a local directory.

    Expected structure:
        data_dir/
            videos/
                video_001.mp4
                video_002.mp4
                ...
            captions/
                video_001.txt
                video_002.txt
                ...

    Or with metadata.json:
        data_dir/
            videos/
                ...
            metadata.json  # {"video_001.mp4": "caption text", ...}

    Args:
        data_dir: Root directory.
        num_frames: Number of frames per video.
        image_size: Target frame size.
        sample_rate: Sample every N frames.
        transform: Optional custom transform.
        max_samples: Maximum samples to load.
    """

    def __init__(
        self,
        data_dir: str,
        num_frames: int = 16,
        image_size: int = 256,
        sample_rate: int = 1,
        transform: Optional[Callable] = None,
        max_samples: Optional[int] = None,
    ):
        self.data_dir = Path(data_dir)
        self.num_frames = num_frames
        self.image_size = image_size
        self.sample_rate = sample_rate
        self.transform = transform or get_video_transforms(image_size)

        self.samples = self._find_samples()

        if max_samples is not None:
            self.samples = self.samples[:max_samples]

        print(f"Loaded {len(self.samples)} video-text pairs from {data_dir}")

    def _find_samples(self) -> List[Tuple[Path, str]]:
        """Find all video-caption pairs."""
        samples = []
        videos_dir = self.data_dir / "videos"
        captions_dir = self.data_dir / "captions"
        metadata_file = self.data_dir / "metadata.json"

        video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)

            for video_name, caption in metadata.items():
                video_path = videos_dir / video_name
                if video_path.exists():
                    samples.append((video_path, caption))

        elif captions_dir.exists():
            for video_path in videos_dir.iterdir():
                if video_path.suffix.lower() not in video_extensions:
                    continue

                caption_path = captions_dir / f"{video_path.stem}.txt"
                if caption_path.exists():
                    with open(caption_path) as f:
                        caption = f.read().strip()
                    samples.append((video_path, caption))

        else:
            # Flat structure
            for video_path in self.data_dir.iterdir():
                if video_path.suffix.lower() not in video_extensions:
                    continue

                caption_path = video_path.with_suffix(".txt")
                if caption_path.exists():
                    with open(caption_path) as f:
                        caption = f.read().strip()
                    samples.append((video_path, caption))

        return samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        video_path, caption = self.samples[idx]

        # Load video frames
        frames = load_video_frames(
            str(video_path),
            num_frames=self.num_frames,
            sample_rate=self.sample_rate,
        )

        # Transform each frame
        frames = torch.stack([self.transform(f) for f in frames])  # [T, C, H, W]

        return {
            "video": frames,  # [T, C, H, W]
            "caption": caption,
            "video_path": str(video_path),
        }


class HuggingFaceVideoDataset(Dataset):
    """
    Load video-text pairs from a HuggingFace dataset.

    Supports datasets like:
    - "webvid" (WebVid-10M)
    - "HuggingFaceM4/webvid"
    - Custom video datasets

    Args:
        dataset_name: HuggingFace dataset name.
        split: Dataset split.
        video_column: Column name for videos.
        caption_column: Column name for captions.
        num_frames: Number of frames per video.
        image_size: Target frame size.
        sample_rate: Sample every N frames.
        max_samples: Maximum samples to use.
    """

    def __init__(
        self,
        dataset_name: str,
        split: str = "train",
        video_column: str = "video",
        caption_column: str = "text",
        num_frames: int = 16,
        image_size: int = 256,
        sample_rate: int = 1,
        max_samples: Optional[int] = None,
    ):
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError("datasets required. Install with: pip install datasets")

        self.video_column = video_column
        self.caption_column = caption_column
        self.num_frames = num_frames
        self.sample_rate = sample_rate
        self.transform = get_video_transforms(image_size)

        print(f"Loading dataset {dataset_name}...")
        self.dataset = load_dataset(dataset_name, split=split)

        if max_samples is not None:
            self.dataset = self.dataset.select(range(min(max_samples, len(self.dataset))))

        # Auto-detect columns
        if len(self.dataset) > 0:
            sample = self.dataset[0]
            if caption_column not in sample:
                for candidate in ["text", "caption", "description", "prompt"]:
                    if candidate in sample:
                        print(f"Using caption column: {candidate}")
                        self.caption_column = candidate
                        break

        print(f"Loaded {len(self.dataset)} samples")

    def __len__(self) -> int:
        return len(self.dataset)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        item = self.dataset[idx]

        # Get video (may be path, URL, or frames)
        video = item[self.video_column]

        if isinstance(video, str):
            # Path or URL
            frames = load_video_frames(
                video,
                num_frames=self.num_frames,
                sample_rate=self.sample_rate,
            )
        elif isinstance(video, list):
            # Already frames
            frames = [Image.fromarray(f) if not isinstance(f, Image.Image) else f for f in video]
            # Sample frames
            if len(frames) > self.num_frames:
                indices = [i * len(frames) // self.num_frames for i in range(self.num_frames)]
                frames = [frames[i] for i in indices]
            elif len(frames) < self.num_frames:
                # Pad
                while len(frames) < self.num_frames:
                    frames.append(frames[-1])
        else:
            raise ValueError(f"Unsupported video format: {type(video)}")

        # Transform frames
        frames = torch.stack([self.transform(f) for f in frames])

        # Get caption
        caption = item.get(self.caption_column, "a video")
        if caption is None:
            caption = "a video"
        elif isinstance(caption, list):
            caption = random.choice(caption) if caption else "a video"

        return {
            "video": frames,
            "caption": caption,
        }


class SyntheticVideoDataset(Dataset):
    """
    Synthetic dataset for testing video training loop.

    Generates random video frames with simple captions.

    Args:
        num_samples: Number of synthetic videos.
        num_frames: Frames per video.
        image_size: Frame size.
    """

    def __init__(
        self,
        num_samples: int = 500,
        num_frames: int = 16,
        image_size: int = 256,
    ):
        self.num_samples = num_samples
        self.num_frames = num_frames
        self.image_size = image_size

        self.captions = [
            f"A synthetic video clip {i % 10} with motion pattern {i % 5}"
            for i in range(num_samples)
        ]

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        # Generate deterministic random video with temporal coherence
        torch.manual_seed(idx)

        # Create base frame
        base = torch.randn(3, self.image_size, self.image_size)

        # Add temporal variation
        frames = []
        for t in range(self.num_frames):
            # Add smooth temporal variation
            temporal_noise = torch.randn(3, self.image_size, self.image_size) * 0.1
            frame = torch.tanh(base + temporal_noise * (t / self.num_frames))
            frames.append(frame)

        video = torch.stack(frames)  # [T, C, H, W]

        return {
            "video": video,
            "caption": self.captions[idx],
        }


def create_video_dataloader(
    dataset: Dataset,
    batch_size: int = 2,
    shuffle: bool = True,
    num_workers: int = 4,
    pin_memory: bool = True,
) -> DataLoader:
    """
    Create a DataLoader for video training.

    Args:
        dataset: Video dataset.
        batch_size: Batch size (smaller for video due to memory).
        shuffle: Whether to shuffle.
        num_workers: Data loading workers.
        pin_memory: Pin memory for GPU.

    Returns:
        DataLoader instance.
    """

    def collate_fn(batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Custom collate for video-text batches."""
        videos = torch.stack([item["video"] for item in batch])  # [B, T, C, H, W]
        captions = [item["caption"] for item in batch]

        return {
            "videos": videos,
            "captions": captions,
        }

    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=pin_memory,
        collate_fn=collate_fn,
        drop_last=True,
    )


def get_video_dataset(
    dataset_type: str,
    **kwargs,
) -> Dataset:
    """
    Factory function to create video datasets.

    Args:
        dataset_type: One of "local", "huggingface", "synthetic".
        **kwargs: Arguments for dataset constructor.

    Returns:
        Dataset instance.
    """
    if dataset_type == "local":
        return LocalVideoTextDataset(**kwargs)
    elif dataset_type == "huggingface":
        return HuggingFaceVideoDataset(**kwargs)
    elif dataset_type == "synthetic":
        return SyntheticVideoDataset(**kwargs)
    else:
        raise ValueError(f"Unknown dataset type: {dataset_type}")
