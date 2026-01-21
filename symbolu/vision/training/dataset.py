"""
Dataset loaders for Phase-Quad Image Generator training.

Supports loading image-text pairs from various sources:
- Local directories (images + captions)
- HuggingFace datasets
- WebDataset format

Requirements:
    pip install datasets webdataset pillow
"""

import os
import json
import random
from pathlib import Path
from typing import Optional, List, Tuple, Callable, Dict, Any, Union

import torch
from torch import Tensor
from torch.utils.data import Dataset, DataLoader, IterableDataset

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


def get_image_transforms(
    image_size: int = 512,
    center_crop: bool = True,
    random_flip: bool = True,
) -> Callable:
    """
    Get standard image transforms for training.

    Args:
        image_size: Target image size (square).
        center_crop: Whether to center crop (vs random crop).
        random_flip: Whether to apply random horizontal flip.

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

    if random_flip:
        transforms.append(T.RandomHorizontalFlip(p=0.5))

    transforms.extend([
        T.ToTensor(),
        T.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),  # -> [-1, 1]
    ])

    return T.Compose(transforms)


class LocalImageTextDataset(Dataset):
    """
    Load image-text pairs from a local directory.

    Expected structure:
        data_dir/
            images/
                image_001.jpg
                image_002.png
                ...
            captions/
                image_001.txt
                image_002.txt
                ...

    Or with a single metadata file:
        data_dir/
            images/
                ...
            metadata.json  # {"image_001.jpg": "caption text", ...}

    Args:
        data_dir: Root directory containing images and captions.
        image_size: Target image size.
        transform: Optional custom transform.
        max_samples: Maximum number of samples to load.
    """

    def __init__(
        self,
        data_dir: str,
        image_size: int = 512,
        transform: Optional[Callable] = None,
        max_samples: Optional[int] = None,
    ):
        if not HAS_PIL:
            raise ImportError("Pillow required. Install with: pip install Pillow")

        self.data_dir = Path(data_dir)
        self.image_size = image_size
        self.transform = transform or get_image_transforms(image_size)

        # Find images and captions
        self.samples = self._find_samples()

        if max_samples is not None:
            self.samples = self.samples[:max_samples]

        print(f"Loaded {len(self.samples)} image-text pairs from {data_dir}")

    def _find_samples(self) -> List[Tuple[Path, str]]:
        """Find all image-caption pairs."""
        samples = []

        images_dir = self.data_dir / "images"
        captions_dir = self.data_dir / "captions"
        metadata_file = self.data_dir / "metadata.json"

        # Check for metadata.json
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)

            for image_name, caption in metadata.items():
                image_path = images_dir / image_name
                if image_path.exists():
                    samples.append((image_path, caption))

        # Check for captions directory
        elif captions_dir.exists():
            image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

            for image_path in images_dir.iterdir():
                if image_path.suffix.lower() not in image_extensions:
                    continue

                caption_path = captions_dir / f"{image_path.stem}.txt"
                if caption_path.exists():
                    with open(caption_path) as f:
                        caption = f.read().strip()
                    samples.append((image_path, caption))

        # Flat structure with .txt alongside images
        else:
            image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

            for image_path in self.data_dir.iterdir():
                if image_path.suffix.lower() not in image_extensions:
                    continue

                caption_path = image_path.with_suffix(".txt")
                if caption_path.exists():
                    with open(caption_path) as f:
                        caption = f.read().strip()
                    samples.append((image_path, caption))

        return samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        image_path, caption = self.samples[idx]

        # Load and transform image
        image = Image.open(image_path).convert("RGB")
        image = self.transform(image)

        return {
            "image": image,
            "caption": caption,
            "image_path": str(image_path),
        }


class HuggingFaceDataset(Dataset):
    """
    Load image-text pairs from a HuggingFace dataset.

    Supports datasets like:
    - "laion/laion2B-en"
    - "lambdalabs/pokemon-blip-captions"
    - "nlphuji/flickr30k"

    Args:
        dataset_name: HuggingFace dataset name.
        split: Dataset split ("train", "validation", etc.).
        image_column: Column name for images.
        caption_column: Column name for captions.
        image_size: Target image size.
        max_samples: Maximum samples to use.
        streaming: Whether to use streaming mode (for large datasets).
    """

    def __init__(
        self,
        dataset_name: str,
        split: str = "train",
        image_column: str = "image",
        caption_column: str = "text",
        image_size: int = 512,
        max_samples: Optional[int] = None,
        streaming: bool = False,
    ):
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError("datasets required. Install with: pip install datasets")

        if not HAS_PIL:
            raise ImportError("Pillow required. Install with: pip install Pillow")

        self.image_column = image_column
        self.caption_column = caption_column
        self.transform = get_image_transforms(image_size)

        print(f"Loading dataset {dataset_name}...")
        self.dataset = load_dataset(
            dataset_name,
            split=split,
            streaming=streaming,
        )

        if max_samples is not None and not streaming:
            self.dataset = self.dataset.select(range(min(max_samples, len(self.dataset))))

        # Auto-detect caption column if specified one doesn't exist
        if not streaming and len(self.dataset) > 0:
            sample = self.dataset[0]
            if caption_column not in sample:
                # Try common caption column names
                caption_candidates = ["text", "caption", "en_text", "description", "prompt", "label"]
                for candidate in caption_candidates:
                    if candidate in sample:
                        print(f"Caption column '{caption_column}' not found, using '{candidate}'")
                        self.caption_column = candidate
                        break
                else:
                    # Use first string-like column
                    for key, value in sample.items():
                        if isinstance(value, str) and key != image_column:
                            print(f"Caption column '{caption_column}' not found, using '{key}'")
                            self.caption_column = key
                            break

        if not streaming:
            print(f"Loaded {len(self.dataset)} samples")

    def __len__(self) -> int:
        return len(self.dataset)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        item = self.dataset[idx]

        # Get image (may be PIL Image or path)
        image = item[self.image_column]
        if isinstance(image, str):
            image = Image.open(image).convert("RGB")
        elif not isinstance(image, Image.Image):
            image = Image.fromarray(image).convert("RGB")

        image = self.transform(image)

        # Get caption
        caption = item[self.caption_column]
        if isinstance(caption, list):
            caption = random.choice(caption)

        return {
            "image": image,
            "caption": caption,
        }


class SyntheticDataset(Dataset):
    """
    Synthetic dataset for testing training loop.

    Generates random images with simple captions.

    Args:
        num_samples: Number of synthetic samples.
        image_size: Image size.
        latent_channels: VAE latent channels.
    """

    def __init__(
        self,
        num_samples: int = 1000,
        image_size: int = 512,
        latent_channels: int = 4,
    ):
        self.num_samples = num_samples
        self.image_size = image_size
        self.latent_channels = latent_channels

        # Pre-generate captions
        self.captions = [
            f"A synthetic image with pattern {i % 10}"
            for i in range(num_samples)
        ]

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        # Generate deterministic random image
        torch.manual_seed(idx)
        image = torch.randn(3, self.image_size, self.image_size)
        image = torch.tanh(image)  # Normalize to [-1, 1]

        return {
            "image": image,
            "caption": self.captions[idx],
        }


def create_dataloader(
    dataset: Dataset,
    batch_size: int = 4,
    shuffle: bool = True,
    num_workers: int = 4,
    pin_memory: bool = True,
) -> DataLoader:
    """
    Create a DataLoader for training.

    Args:
        dataset: Dataset to load from.
        batch_size: Batch size.
        shuffle: Whether to shuffle.
        num_workers: Number of data loading workers.
        pin_memory: Whether to pin memory for GPU transfer.

    Returns:
        DataLoader instance.
    """

    def collate_fn(batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Custom collate function for image-text batches."""
        images = torch.stack([item["image"] for item in batch])
        captions = [item["caption"] for item in batch]

        return {
            "images": images,
            "captions": captions,
        }

    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=pin_memory,
        collate_fn=collate_fn,
        drop_last=True,  # Important for consistent batch sizes
    )


def get_dataset(
    dataset_type: str,
    **kwargs,
) -> Dataset:
    """
    Factory function to create datasets.

    Args:
        dataset_type: One of "local", "huggingface", "synthetic".
        **kwargs: Arguments passed to dataset constructor.

    Returns:
        Dataset instance.
    """
    if dataset_type == "local":
        return LocalImageTextDataset(**kwargs)
    elif dataset_type == "huggingface":
        return HuggingFaceDataset(**kwargs)
    elif dataset_type == "synthetic":
        return SyntheticDataset(**kwargs)
    else:
        raise ValueError(f"Unknown dataset type: {dataset_type}")
