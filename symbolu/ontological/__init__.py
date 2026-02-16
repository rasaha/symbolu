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
    # Toggle Full LLM (768D) vs Optimized (256D)
    use_full_llm,
    use_optimized,
    use_tiny,
    toggle_llm_mode,
    is_full_llm,
    is_optimized,
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

# RAG Stitching Optimization (Objective Formula)
from symbolu.ontological.stitching_optimization import (
    StitchingOptimizer,
    StitchingConfig,
    StitchingResult,
    RAGSnippet,
    select_optimal_snippets,
    create_rag_snippet,
    compute_redundancy_penalty,
    compute_domain_jump_penalty,
)

# BCVF: Bidirectional Consistency Verification Framework
from symbolu.ontological.bcvf import (
    BCVFVerifier,
    BCVFConfig,
    ConsistencyLagrangian,
    ConsistencyScore,
    ForwardScorer,
    BackwardScorer,
    SemanticEntropyMonitor,
    VerificationResult,
    VerifiedCandidate,
    verify_candidates,
    compute_consistency_lagrangian,
)

# SCC: Semantic Coherence Controller (S1-S3)
from symbolu.ontological.semantic_coherence import (
    SemanticCoherenceController,
    SCCConfig,
    LayerCoherenceResult,
    GlobalCoherenceResult,
    LayerCoherenceComputer,
    GlobalCoherenceComputer,
    compute_coherence,
    is_coherent,
)

# GoalDirNet: Learned Future-Direction Predictor
try:
    from symbolu.ontological.goal_dirnet import (
        GoalDirNet,
        GoalDirNetConfig,
        GoalDirFeatureBuilder,
        GoalDirSample,
        GoalDirEvalResult,
        collect_from_dataset_adapter,
        train_goal_dirnet,
        evaluate_goal_dirnet,
        run_alpha_sweep,
        run_goal_dirnet_pipeline,
        print_goal_dirnet_report,
    )
    GOAL_DIRNET_AVAILABLE = True
except ImportError:
    GOAL_DIRNET_AVAILABLE = False

# USE: Phase-Based Attention (O(n) replacement for O(n²) attention)
from symbolu.ontological.phase_attention import (
    PhaseAttention,
    LinearPhaseAttention,
    PhaseAttentionWrapper,
    PhaseAttentionConfig,
    PhaseEmbedding,
    PhaseSynchronizer,
    PhaseCorrelation,
    replace_attention_with_phase,
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
    # Toggle Full LLM (768D) vs Optimized (256D)
    "use_full_llm",
    "use_optimized",
    "use_tiny",
    "toggle_llm_mode",
    "is_full_llm",
    "is_optimized",
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
    # RAG Stitching Optimization (Objective Formula)
    "StitchingOptimizer",
    "StitchingConfig",
    "StitchingResult",
    "RAGSnippet",
    "select_optimal_snippets",
    "create_rag_snippet",
    "compute_redundancy_penalty",
    "compute_domain_jump_penalty",
    # BCVF: Bidirectional Consistency Verification Framework
    "BCVFVerifier",
    "BCVFConfig",
    "ConsistencyLagrangian",
    "ConsistencyScore",
    "ForwardScorer",
    "BackwardScorer",
    "SemanticEntropyMonitor",
    "VerificationResult",
    "VerifiedCandidate",
    "verify_candidates",
    "compute_consistency_lagrangian",
    # SCC: Semantic Coherence Controller (S1-S3)
    "SemanticCoherenceController",
    "SCCConfig",
    "LayerCoherenceResult",
    "GlobalCoherenceResult",
    "LayerCoherenceComputer",
    "GlobalCoherenceComputer",
    "compute_coherence",
    "is_coherent",
    # GoalDirNet: Learned Future-Direction Predictor
    "GOAL_DIRNET_AVAILABLE",
    # USE: Phase-Based Attention (O(n) replacement)
    "PhaseAttention",
    "LinearPhaseAttention",
    "PhaseAttentionWrapper",
    "PhaseAttentionConfig",
    "PhaseEmbedding",
    "PhaseSynchronizer",
    "PhaseCorrelation",
    "replace_attention_with_phase",
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

# Add GoalDirNet exports if available
if GOAL_DIRNET_AVAILABLE:
    __all__.extend([
        "GoalDirNet",
        "GoalDirNetConfig",
        "GoalDirFeatureBuilder",
        "GoalDirSample",
        "GoalDirEvalResult",
        "collect_from_dataset_adapter",
        "train_goal_dirnet",
        "evaluate_goal_dirnet",
        "run_alpha_sweep",
        "run_goal_dirnet_pipeline",
        "print_goal_dirnet_report",
    ])
