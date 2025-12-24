"""
Ontological Engine Module
=========================

A learnable 144-dimensional ontological engine for text analysis.
- 12D Ontological Layers (Potential → Absolving)
- 132D Bhava (11 pairs × 12 sub-layers)

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
    NUM_LAYERS,
    NUM_BHAVA_PAIRS,
    SUB_LAYERS_PER_PAIR,
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
    from symbolu.ontological.multi_domain_trainer import (
        MultiDomainTrainer,
        MultiDomainConfig,
        train_multi_domain,
    )
    from symbolu.ontological.evidential_engine import (
        EvidentialOntologicalEngine,
        EvidentialTrainer,
        EvidentialConfig,
        EvidentialHead,
    )
    from symbolu.ontological.unified_engine import (
        UnifiedOntologicalEngine,
        UnifiedTrainer,
        UnifiedConfig,
    )
    from symbolu.ontological.semantic_bhava import (
        SemanticBhavaLayer,
        AstrologicalOntologicalEngine,
        PLANETARY_MAP,
        ASPECTS,
        BHAVA_PAIRS,
        SUB_LAYER_NAMES,
        get_aspect_between,
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
from symbolu.ontological.multi_domain_dataset import (
    MultiDomainDataset,
    DomainSample,
    create_multi_domain_dataset,
)

__all__ = [
    # Types (12D)
    "OntologicalConfig",
    "OntologicalVector",
    "TrainingExample",
    "TrainingBatch",
    "LAYER_NAMES",
    "LAYER_INDEX",
    "NUM_LAYERS",
    "NUM_BHAVA_PAIRS",
    "SUB_LAYERS_PER_PAIR",
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
    # Multi-domain (12 layers)
    "MultiDomainDataset",
    "DomainSample",
    "create_multi_domain_dataset",
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
        # Multi-domain trainer
        "MultiDomainTrainer",
        "MultiDomainConfig",
        "train_multi_domain",
        # Evidential (Bayesian uncertainty)
        "EvidentialOntologicalEngine",
        "EvidentialTrainer",
        "EvidentialConfig",
        "EvidentialHead",
        # Unified (all features combined)
        "UnifiedOntologicalEngine",
        "UnifiedTrainer",
        "UnifiedConfig",
        # Semantic Bhava (astrological) - 12D
        "SemanticBhavaLayer",
        "AstrologicalOntologicalEngine",
        "PLANETARY_MAP",
        "ASPECTS",
        "BHAVA_PAIRS",
        "SUB_LAYER_NAMES",
        "get_aspect_between",
    ])
