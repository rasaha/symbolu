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

from symbolu.training.schemas import (
    QueryIntentPair,
    ParaphrasePair,
    TrainingDataset,
    IntentLabel,
)

__all__ = [
    "QueryIntentPair",
    "ParaphrasePair",
    "TrainingDataset",
    "IntentLabel",
]
