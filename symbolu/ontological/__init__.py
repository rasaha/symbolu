"""
Ontological Engine Module
=========================

A learnable 100-dimensional ontological engine that trains on large data
to improve reasoning and creativity.

Architecture:
- 10 Core Ontological Layers (O1-O10)
- 90 Bhava Sub-layers (9 pairs × 10 sub-layers)
- DistilBERT encoder for semantic embeddings
- Multi-task learning with contrastive loss

Usage:
    from symbolu.ontological import EnhancedTrainer, train_enhanced_model

    # Quick training
    trainer, results = train_enhanced_model(epochs=10)

    # Analyze text
    result = trainer.analyze("If A implies B, then...")
    print(result["dominant"])  # O6_REASONING
"""

from symbolu.ontological.types import (
    LAYER_NAMES,
    LAYER_INDEX,
    OntologicalConfig,
    OntologicalVector,
    TrainingExample,
)

# Conditionally export PyTorch components
try:
    from symbolu.ontological.enhanced_engine import (
        EnhancedOntologicalEngine,
        MultiTaskLoss,
        MultiTaskHead,
        DistilBERTEncoder,
        create_training_batch,
    )
    from symbolu.ontological.enhanced_trainer import (
        EnhancedTrainer,
        TrainerConfig,
        train_enhanced_model,
        create_curated_dataset,
        DOMAIN_NAMES,
        DOMAIN_TO_IDX,
    )
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

__all__ = [
    # Types
    "LAYER_NAMES",
    "LAYER_INDEX",
    "OntologicalConfig",
    "OntologicalVector",
    "TrainingExample",
    # PyTorch components (if available)
    "EnhancedOntologicalEngine",
    "MultiTaskLoss",
    "MultiTaskHead",
    "DistilBERTEncoder",
    "EnhancedTrainer",
    "TrainerConfig",
    "train_enhanced_model",
    "create_curated_dataset",
    "DOMAIN_NAMES",
    "DOMAIN_TO_IDX",
    "PYTORCH_AVAILABLE",
]
