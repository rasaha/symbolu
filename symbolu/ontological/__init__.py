"""
Ontological Engine Module
=========================

A learnable 100-dimensional ontological engine for text analysis.

Usage:
    from symbolu.ontological import ContrastiveTrainer

    trainer = ContrastiveTrainer()
    trainer.train(epochs=5, use_synthetic=True)
    trainer.benchmark()
"""

from symbolu.ontological.types import (
    OntologicalConfig,
    OntologicalVector,
    TrainingExample,
    TrainingBatch,
    LAYER_NAMES,
    LAYER_INDEX,
    REASONING_LAYERS,
    CREATIVITY_LAYERS,
    TaskType,
)

from symbolu.ontological.encoder import (
    TextEncoder,
    HashEncoder,
    HybridEncoder,
    SentenceTransformerEncoder,
    get_encoder,
    save_model_for_offline,
)

# PyTorch components (optional)
PYTORCH_AVAILABLE = False
try:
    from symbolu.ontological.pytorch_engine import PyTorchOntologicalEngine
    from symbolu.ontological.contrastive_trainer import (
        ContrastiveTrainer,
        ContrastiveConfig,
        train_contrastive,
    )
    from symbolu.ontological.domain_datasets import (
        GSM8KDataset,
        ROCStoriesDataset,
        ContrastiveDataset,
        create_contrastive_dataset,
    )
    PYTORCH_AVAILABLE = True
except ImportError as e:
    print(f"Note: PyTorch components not available: {e}")

# RAG datasets (no dependencies)
from symbolu.ontological.math_rag_dataset import (
    MathRAGDataset,
    MathProblem,
    create_math_rag_dataset,
)
from symbolu.ontological.creative_math_dataset import (
    CreativeMathDataset,
    CreativeMathItem,
    create_creative_math_dataset,
)

__all__ = [
    # Types
    "OntologicalConfig",
    "OntologicalVector",
    "TrainingExample",
    "TrainingBatch",
    "LAYER_NAMES",
    "LAYER_INDEX",
    "REASONING_LAYERS",
    "CREATIVITY_LAYERS",
    "TaskType",
    # Encoders
    "TextEncoder",
    "HashEncoder",
    "HybridEncoder",
    "SentenceTransformerEncoder",
    "get_encoder",
    "save_model_for_offline",
    # PyTorch (optional)
    "PYTORCH_AVAILABLE",
    # RAG datasets
    "MathRAGDataset",
    "MathProblem",
    "create_math_rag_dataset",
    "CreativeMathDataset",
    "CreativeMathItem",
    "create_creative_math_dataset",
]

# Add PyTorch exports if available
if PYTORCH_AVAILABLE:
    __all__.extend([
        "PyTorchOntologicalEngine",
        "ContrastiveTrainer",
        "ContrastiveConfig",
        "train_contrastive",
        "GSM8KDataset",
        "ROCStoriesDataset",
        "ContrastiveDataset",
        "create_contrastive_dataset",
    ])
