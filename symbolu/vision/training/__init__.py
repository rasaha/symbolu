"""
Training utilities for Phase-Quad Image Generator.

This package contains:
- TemperatureSchedule: Temperature scheduling for gate warming
- PhaseQuadDiffusionTrainer: Main training loop
- ReplaceabilityTester: Ablation testing for component contribution
"""

from symbolu.vision.training.temperature_schedule import (
    TemperatureSchedule,
    LinearSchedule,
    CosineSchedule,
)
from symbolu.vision.training.diffusion_trainer import (
    PhaseQuadDiffusionTrainer,
    TrainingStep,
)
from symbolu.vision.training.replaceability_tester import (
    ReplaceabilityTester,
    AblationResult,
)

__all__ = [
    "TemperatureSchedule",
    "LinearSchedule",
    "CosineSchedule",
    "PhaseQuadDiffusionTrainer",
    "TrainingStep",
    "ReplaceabilityTester",
    "AblationResult",
]
