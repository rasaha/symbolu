"""
Symbol-U Training Module
========================

Training infrastructure for consumer providers.
Includes data generation, validation, and training scripts.

Directory Structure:
    training/
    ├── data/           # Training datasets
    │   ├── raw/        # Raw generated data
    │   └── processed/  # Validated, processed data
    ├── scripts/        # Training scripts
    └── config/         # Training configurations
"""

from symbolu_training.training.schemas import (
    QueryIntentPair,
    ParaphrasePair,
    TrainingDataset,
    IntentLabel,
)
from symbolu_training.training.text_utils import (
    clean_wikitext_artifacts,
    clean_generated_text,
    estimate_token_quality,
)
from symbolu_training.training.trainers.gradient_throttle import GradientNormThrottle

__all__ = [
    "QueryIntentPair",
    "ParaphrasePair",
    "TrainingDataset",
    "IntentLabel",
    "clean_wikitext_artifacts",
    "clean_generated_text",
    "estimate_token_quality",
    "GradientNormThrottle",
]
