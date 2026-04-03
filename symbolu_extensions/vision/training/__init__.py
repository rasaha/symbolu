"""
Training utilities for Phase-Quad Image Generator.

This package contains:
- TemperatureSchedule: Temperature scheduling for gate warming
- PhaseQuadDiffusionTrainer: Main training loop
- ReplaceabilityTester: Ablation testing for component contribution
- DiffusionTrainer: Full training pipeline with pretrained VAE/CLIP
- Dataset utilities: Loading image-text pairs for training
"""

from symbolu_extensions.vision.training.temperature_schedule import (
    TemperatureSchedule,
    LinearSchedule,
    CosineSchedule,
)
from symbolu_extensions.vision.training.diffusion_trainer import (
    PhaseQuadDiffusionTrainer,
    TrainingStep,
)
from symbolu_extensions.vision.training.replaceability_tester import (
    ReplaceabilityTester,
    AblationResult,
)
from symbolu_extensions.vision.training.dataset import (
    LocalImageTextDataset,
    HuggingFaceDataset,
    SyntheticDataset,
    create_dataloader,
    get_dataset,
)
from symbolu_extensions.vision.training.train import (
    DiffusionTrainer,
    train,
)

__all__ = [
    # Temperature scheduling
    "TemperatureSchedule",
    "LinearSchedule",
    "CosineSchedule",
    # Core training
    "PhaseQuadDiffusionTrainer",
    "TrainingStep",
    "DiffusionTrainer",
    "train",
    # Ablation
    "ReplaceabilityTester",
    "AblationResult",
    # Datasets
    "LocalImageTextDataset",
    "HuggingFaceDataset",
    "SyntheticDataset",
    "create_dataloader",
    "get_dataset",
]
