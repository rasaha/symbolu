"""
Learnable 10D Ontological Engine
================================

A neural network-based engine that learns to map text to interpretable
10-dimensional ontological vectors. Each dimension corresponds to a
fundamental ontological layer:

    O1_THINKING      - Contemplation, philosophy, reflection
    O2_FORMING       - Structure, creation, art, creativity
    O3_ACTING        - Procedures, commands, action
    O4_TAGGING       - Emotional tagging/classification
    O5_DIRECTING     - Guidance, instruction, leadership
    O6_REASONING     - Logic, analysis, problem-solving
    O7_PURPOSING     - Goals, intention, purposefulness
    O8_META_OBSERVING - Meta-awareness, observation
    O9_UNIFYING      - Integration, synthesis, unity
    O10_ABSOLVING    - Resolution, completion, transcendence

Unlike the deterministic STL (Symbolic Transformer Logic), this engine:
- LEARNS from large data via gradient descent
- Has millions of trainable parameters
- Improves reasoning and creativity through training
- Maintains interpretable 10D output

Architecture (Option B - Hybrid):
    Text → Encoder (DistilBERT) → Hidden Layers → 10D Output → Task Heads

Key Features:
- Skip connections (ResNet-style) for gradient flow
- Multi-task heads for reasoning and creativity
- Ontological loss with purity penalties
- Dimension-specific supervision
"""

from symbolu.ontological.types import (
    OntologicalConfig,
    OntologicalVector,
    TrainingExample,
    TrainingBatch,
    LAYER_NAMES,
    LAYER_DESCRIPTIONS,
)
from symbolu.ontological.engine import OntologicalEngine, create_engine
from symbolu.ontological.losses import OntologicalLoss, CombinedLoss
from symbolu.ontological.heads import ReasoningHead, CreativityHead, MultiTaskHead
from symbolu.ontological.bhava import (
    BhavaComputer90,
    FullOntologicalVector100,
    BhavaVector90,
    BHAVA_NAMES_90,
    BHAVA_SUBLAYER_NAMES,
    summarize_bhava_structure,
)
from symbolu.ontological.trainer import OntologicalTrainer, TrainerConfig
from symbolu.ontological.encoder import (
    TextEncoder,
    HashEncoder,
    HybridEncoder,
    get_encoder,
)
from symbolu.ontological.data_loader import (
    RAGDataLoader,
    SyntheticDataGenerator,
    MixedDataLoader,
)

# PyTorch components (optional)
try:
    from symbolu.ontological.pytorch_engine import PyTorchOntologicalEngine
    from symbolu.ontological.pytorch_trainer import PyTorchTrainer, train_from_rag
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
except ImportError:
    PYTORCH_AVAILABLE = False

__all__ = [
    # Types
    "OntologicalConfig",
    "OntologicalVector",
    "TrainingExample",
    "TrainingBatch",
    "LAYER_NAMES",
    "LAYER_DESCRIPTIONS",
    # Engine
    "OntologicalEngine",
    "create_engine",
    # Losses
    "OntologicalLoss",
    "CombinedLoss",
    # Heads
    "ReasoningHead",
    "CreativityHead",
    "MultiTaskHead",
    # Bhava (90D relational)
    "BhavaComputer90",
    "FullOntologicalVector100",
    "BhavaVector90",
    "BHAVA_NAMES_90",
    "BHAVA_SUBLAYER_NAMES",
    "summarize_bhava_structure",
    # Training (basic)
    "OntologicalTrainer",
    "TrainerConfig",
    # Encoders
    "TextEncoder",
    "HashEncoder",
    "HybridEncoder",
    "get_encoder",
    # Data loaders
    "RAGDataLoader",
    "SyntheticDataGenerator",
    "MixedDataLoader",
    # PyTorch (optional)
    "PYTORCH_AVAILABLE",
]

# Add PyTorch exports if available
if PYTORCH_AVAILABLE:
    __all__.extend([
        "PyTorchOntologicalEngine",
        "PyTorchTrainer",
        "train_from_rag",
        # Contrastive training
        "ContrastiveTrainer",
        "ContrastiveConfig",
        "train_contrastive",
        # Domain datasets
        "GSM8KDataset",
        "ROCStoriesDataset",
        "ContrastiveDataset",
        "create_contrastive_dataset",
    ])
