"""
SymbolU Experimental: Ontological State-Delta Training
=======================================================

This is a separate experimental tier exploring a paradigm shift from
token-centric to meaning-centric training.

Three-Tier Model Hierarchy:
---------------------------
Tier 1: Token-Centric (Standard LLM)
    - cross_entropy, contrastive, infonce losses
    - Predicts: P(token_{t+1} | context)
    - Memory: O(B·T·V) - 200GB at 1M context

Tier 2: State-Delta (Current Implementation)
    - state_delta loss in train.py
    - Predicts: ΔH = H_{t+1} - H_t (hidden space)
    - Memory: O(B·T·d) - 3GB at 1M context
    - 65x reduction, but still opaque

Tier 3: Ontological State-Delta (THIS MODULE - Experimental)
    - Predicts: ΔS = S_{t+1} - S_t (meaning space)
    - States are STRUCTURED: phonemes, ontology, constraints
    - Memory: O(B·T·s) where s << d - ~600MB at 1M context
    - 300x reduction AND interpretable

Key Insight:
-----------
"Traditional LLMs learn what word to say next;
 State-delta training learns how understanding itself should change."

Components:
-----------
- cognitive_state.py: CognitiveState dataclass and operations
- phoneme_encoder.py: Text → phoneme energy distribution
- ontology_mapper.py: Phonemes → Bhava state position
- token_decoder.py: CognitiveState → constrained token projection
- ontological_trainer.py: Training loop for Tier 3
- state_retrieval.py: State trajectory indexing and retrieval

Usage:
------
    from symbolu.experimental import (
        CognitiveState,
        StateDelta,
        StateProjector,
        OntologicalDeltaPredictor,
        PhonemeEncoder,
        OntologyMapper,
        OntologicalPerception,
        ConstrainedTokenDecoder,
        OntologicalGenerator,
        train_ontological,
    )

    # Create perception pipeline
    perception = OntologicalPerception(embed_dim=768)

    # Get cognitive states from hidden
    output = perception(hidden_states)
    cognitive_states = output['full_state']  # [B, T, 124]

    # Train on state deltas (NOT tokens!)
    predictor = OntologicalDeltaPredictor(state_dim=124)
    loss, metrics = predictor.compute_loss(cognitive_states)

    # Decode to tokens only when needed
    decoder = ConstrainedTokenDecoder(state_dim=124, vocab_size=50257)
    tokens, probs = decoder.sample(cognitive_states[:, -1])
"""

# Core state representations
from .cognitive_state import (
    CognitiveState,
    StateDelta,
    StateProjector,
    CognitiveStateProjectorLite,  # Lightweight version (Google's interface)
    OntologicalDeltaPredictor,
    ConstraintMaskGenerator,
)

# Phoneme processing
from .phoneme_encoder import (
    PhonemeEncoder,
    PhonemeDecoder,
    PhonotacticChecker,
    IPA_PHONEMES,
    NUM_PHONEMES,
    simple_g2p,
)

# Ontology mapping
from .ontology_mapper import (
    OntologyMapper,
    OntologicalPerception,
    RhetoricalMarkerDetector,
    BhavaState,
    NUM_BHAVA_STATES,
    BHAVA_TO_IDX,
    IDX_TO_BHAVA,
)

# Token decoding
from .token_decoder import (
    ConstrainedTokenDecoder,
    OntologicalGenerator,
)

# Training
from .ontological_trainer import (
    OntologicalTrainingConfig,
    OntologicalTransformer,
    train_ontological,
    compute_ontological_loss,
)

# Retrieval (State-based RAG)
from .state_retrieval import (
    StateTrajectory,
    RetrievalResult,
    OntologyPatternMatcher,
    StateTrajectoryIndex,
    StateGuidedRetriever,
)

# Unified SymbolU12 (complete integration v2.6/v2.7/v2.8)
from .unified_symbolu12 import (
    UnifiedSymbolU12Config,
    DifferentiableChittaVritti,
    BidirectionalGunaMapper,
    VrittiModulatedAttention,
    VrittiOntologyCoupling,
    UnifiedSymbolU12Complete,
    create_unified_symbolu12,
)

# Hybrid RAG (Token + State-Delta fusion)
from .hybrid_rag_integration import (
    HybridRAGConfig,
    HybridRAGEngine,
    FusionMode,
    create_hybrid_engine,
)

# Cognitive Loss (Chitta Gradient) - Interpretable RLHF
from .cognitive_loss import (
    CognitiveLossFunction,
    DHAValidator,
    CognitiveDiagnosis,
    DiagnosisType,
    create_cognitive_loss,
    diagnose_generation,
    BHAVA_TO_IDEAL_VRITTI,
    HEALTHY_TRANSITIONS,
)

# DHA Expression Controller - User-aware delivery modulation
from .dha_expression import (
    UserStateTracker,
    DHAExpressionModulator,
    DHAExpressionController,
    UserProfile,
    ExpressionStyle,
)

# Phase Alignment - Core Cognade alignment components
from .phase_alignment import (
    OrthogonalityLoss,
    StiefelProjection,
    StiefelOptimizer,
    DualRMatrices,
    PhaseLockConstraint,
    PhaseLockGate,
    ZeroState,
    SmritiPersistenceLoop,
)

# Logic Gates - Nyāya-based inference and axiom enforcement
from .logic_gates import (
    AxiomChecker,
    AxiomType,
    AxiomViolation,
    VyaptiChecker,
    HetvabhasaDetector,
    HetvabhasaType,
    FallacyDetection,
    LogicGate,
)

# Training Curriculum - Phased constraint introduction
from .training_curriculum import (
    CurriculumPhase,
    CurriculumConfig,
    TrainingCurriculum,
    CurriculumLoss,
    CurriculumTrainer,
    ConstraintWarmupScheduler,
)

# Adversarial Hardening - Attack resistance
from .adversarial_hardening import (
    SubspaceAlignment,
    SemanticAxioms,
    BottleneckProjection,
    SocratesTestSuite,
    AdversarialHardening,
)

# Cognade Complete - Fully integrated model
from .cognade_complete import (
    VrittiAdaptiveDecay,
    ConfidenceEntropyCoupling,
    CognadeConfig,
    CognadeComplete,
    create_cognade,
)

# Socrates Probe - Executable adversarial test suite
from .socrates_probe import (
    ProbeDefinition,
    ProbeCategory,
    ProbeResult,
    FullReport,
    PROBE_LIBRARY,
    SocratesProbeRunner,
    TokenAnalyzer,
)

__all__ = [
    # Core
    'CognitiveState',
    'StateDelta',
    'StateProjector',
    'CognitiveStateProjectorLite',
    'OntologicalDeltaPredictor',
    'ConstraintMaskGenerator',
    # Phoneme
    'PhonemeEncoder',
    'PhonemeDecoder',
    'PhonotacticChecker',
    'IPA_PHONEMES',
    'NUM_PHONEMES',
    'simple_g2p',
    # Ontology
    'OntologyMapper',
    'OntologicalPerception',
    'RhetoricalMarkerDetector',
    'BhavaState',
    'NUM_BHAVA_STATES',
    'BHAVA_TO_IDX',
    'IDX_TO_BHAVA',
    # Decoder
    'ConstrainedTokenDecoder',
    'OntologicalGenerator',
    # Training
    'OntologicalTrainingConfig',
    'OntologicalTransformer',
    'train_ontological',
    'compute_ontological_loss',
    # Retrieval
    'StateTrajectory',
    'RetrievalResult',
    'OntologyPatternMatcher',
    'StateTrajectoryIndex',
    'StateGuidedRetriever',
    # Unified SymbolU12 (v2.6/v2.7/v2.8 integration)
    'UnifiedSymbolU12Config',
    'DifferentiableChittaVritti',
    'BidirectionalGunaMapper',
    'VrittiModulatedAttention',
    'VrittiOntologyCoupling',
    'UnifiedSymbolU12Complete',
    'create_unified_symbolu12',
    # Hybrid RAG (Token + State-Delta fusion)
    'HybridRAGConfig',
    'HybridRAGEngine',
    'FusionMode',
    'create_hybrid_engine',
    # Cognitive Loss (Chitta Gradient) - Interpretable RLHF
    'CognitiveLossFunction',
    'DHAValidator',
    'CognitiveDiagnosis',
    'DiagnosisType',
    'create_cognitive_loss',
    'diagnose_generation',
    'BHAVA_TO_IDEAL_VRITTI',
    'HEALTHY_TRANSITIONS',
    # DHA Expression Controller - User-aware delivery modulation
    'UserStateTracker',
    'DHAExpressionModulator',
    'DHAExpressionController',
    'UserProfile',
    'ExpressionStyle',
    # Phase Alignment - Core Cognade alignment
    'OrthogonalityLoss',
    'StiefelProjection',
    'StiefelOptimizer',
    'DualRMatrices',
    'PhaseLockConstraint',
    'PhaseLockGate',
    'ZeroState',
    'SmritiPersistenceLoop',
    # Logic Gates - Nyāya-based inference
    'AxiomChecker',
    'AxiomType',
    'AxiomViolation',
    'VyaptiChecker',
    'HetvabhasaDetector',
    'HetvabhasaType',
    'FallacyDetection',
    'LogicGate',
    # Training Curriculum - Phased constraint introduction
    'CurriculumPhase',
    'CurriculumConfig',
    'TrainingCurriculum',
    'CurriculumLoss',
    'CurriculumTrainer',
    'ConstraintWarmupScheduler',
    # Adversarial Hardening - Attack resistance
    'SubspaceAlignment',
    'SemanticAxioms',
    'BottleneckProjection',
    'SocratesTestSuite',
    'AdversarialHardening',
    # Cognade Complete - Fully integrated model
    'VrittiAdaptiveDecay',
    'ConfidenceEntropyCoupling',
    'CognadeConfig',
    'CognadeComplete',
    'create_cognade',
    # Socrates Probe - Executable adversarial test suite
    'ProbeDefinition',
    'ProbeCategory',
    'ProbeResult',
    'FullReport',
    'PROBE_LIBRARY',
    'SocratesProbeRunner',
    'TokenAnalyzer',
]
