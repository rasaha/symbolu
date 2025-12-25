"""
Ontological Engine Module
=========================

A learnable 156-dimensional ontological engine for text analysis.
- 12D Ontological Layers (Potential → Absolving)
- 144D Bhava Inter-Layer Relationships (12×12 matrix)

Engine Configuration:
    from symbolu.ontological import config, EngineSwitch

    # Switch engines (only one active at a time)
    config.set_engine(EngineSwitch.SYMBOLU12_LLM_BHAVA)

    # Or use profile
    config.set_profile("generative")  # enterprise, hybrid, generative, cpu, edge

    # Get engine and analyze
    engine = config.get_engine()
    result = engine.analyze("What is consciousness?")

Available Engines:
    - MINILM_V2: Enterprise RAG (default)
    - SYMBOLU12_HYBRID: MiniLM + SymbolU12 layers
    - SYMBOLU12_LLM_BHAVA: Full generative with Bhava
    - SYMBOLU12_OPTIMIZED_BHAVA: CPU-friendly
    - SYMBOLU12_TINY_BHAVA: Edge devices
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

# Engine Configuration (switch between engines)
from symbolu.ontological.config import (
    config,
    EngineSwitch,
    get_engine,
    set_engine,
    set_profile,
    analyze,
    ENGINE_PROFILES,
)

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
    # Engine Configuration (switch between engines)
    "config",
    "EngineSwitch",
    "get_engine",
    "set_engine",
    "set_profile",
    "analyze",
    "ENGINE_PROFILES",
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
