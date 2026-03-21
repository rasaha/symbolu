#!/usr/bin/env python3
"""
SymbolU Inference Module
========================

Inference-time components that bridge training capabilities to generation.

This module implements the inference-side equivalents of training components:
- EvolutionaryInferenceEngine: Karma buffer and O12->O1 state persistence
- CSRInferenceGuard: Safety layer with entropy monitoring
- InferenceMetacognition: Real-time generation quality monitoring
- InferenceGunas: Sattva/Rajas/Tamas approximation during generation
- SovereignInferenceScorer: Quality scoring using Sovereign-1 metrics
- LayerInferenceConfig: 6:6 / 9:3 layer configuration for inference

V10.0 Phase 5 additions:
- BindingCacheInferenceEngine: Engine for BindingCacheTransformer
- OntologicalBindingCacheInferenceEngine: Engine for OntologicalBindingCacheTransformer
- SovereignStateMonitor: 32D Sovereign State monitoring and analysis

See docs/INFERENCE_HYBRID_TRANSFORMER_GAPS.md for detailed gap analysis.

Author: Sovereign-1 Training Initiative
Date: January 2026
Version: 2.0.0 (Phase 5 - V10.0 Binding Cache Support)
"""

from .evolutionary_inference import EvolutionaryInferenceEngine
from .csr_inference import CSRInferenceGuard
from .metacognitive_monitor import InferenceMetacognition
from .guna_inference import InferenceGunas
from .sovereign_scorer import SovereignInferenceScorer
from .layer_config import LayerInferenceConfig, ArchitectureMode
from .checkpoint_utils import load_inference_engine, InferenceCheckpointLoader
from .manager import InferenceManager, InferenceMode, InferenceManagerConfig

# V10.0 Phase 5 - Binding Cache Inference Engines
from .binding_cache_inference import (
    BindingCacheInferenceEngine,
    BindingCacheInferenceConfig,
    IntentPhaseInferenceModule,
    BindingSalienceController,
)
from .ontological_binding_cache_inference import (
    OntologicalBindingCacheInferenceEngine,
    OntologicalBindingCacheInferenceConfig,
)
from .sovereign_state_monitor import (
    SovereignStateMonitor,
    SovereignStateMetrics,
    DepthLevel,
    ReliabilityLevel,
    SOVEREIGN_STATE_DIM,
    BHAVA_NAMES,
    KOSHA_NAMES,
    VRITTI_NAMES,
    GUNA_NAMES,
    get_sovereign_state_summary,
)

# Logit Modulation Decoding
from .logit_modulation import (
    LogitModulationConfig,
    LogitModulator,
    ModulationMode,
)
from .retrieval_scorer import (
    RetrievalScorer,
    RetrievalScorerConfig,
    RetrievalStrategy,
)
from .penalty_scorer import (
    PenaltyScorer,
    PenaltyScorerConfig,
)
from .logit_modulation_benchmark import (
    LogitModulationBenchmark,
    BenchmarkMetrics,
    SweepResult,
)

# Appendix F Stage 0: Generation Tracer
from .generation_tracer import (
    GenerationTracer,
    BindingCacheTracerMixin,
    CTMPlusTracerMixin,
    MistralCGGenerationTracer,
    BaselineStatisticsAnalyzer,
)

# Appendix F Stage 1: Coherence-Aware Decoder
from .coherence_aware_decoder import (
    CoherenceAwareDecoder,
    CoherenceDecoderConfig,
)

# Appendix F Stage 2: Interpretive Conditioner
from .interpretive_conditioner import (
    InterpretiveConditioner,
    InterpretiveConditionerConfig,
    InterpretiveStateBuilder,
    BhavaVectorCompressor,
)

# Appendix F Stage 4: Unified Coherence Controller
from .unified_coherence_controller import (
    UnifiedCoherenceController,
    UnifiedCoherenceConfig,
)

# Appendix F Stage 7A: Semantic Coherence Integration
from .semantic_coherence_integration import (
    SemanticCoherenceIntegration,
    SemanticCoherenceConfig,
)

# Appendix F Stage 7C: Experiential State (Dual-Space Architecture)
from .experiential_state import (
    ExperientialStateModule,
    ExperientialStateConfig,
)

# Appendix F Stage 7D: Polarity Encoding (Varna Polarity Gates)
from .polarity_encoding import (
    PolarityGate,
    PolarityEncodingConfig,
)

# Appendix F Stage 7F: Phase Coherence Signal
from .phase_coherence_signal import (
    PhaseCoherenceExtractor,
    PhaseCoherenceAggregator,
    PhaseCoherenceProjection,
    PhaseCoherenceConfig,
)

__all__ = [
    # Core engines (Legacy)
    "EvolutionaryInferenceEngine",
    "CSRInferenceGuard",
    "InferenceManager",
    "InferenceMode",
    "InferenceManagerConfig",

    # Monitoring (Legacy)
    "InferenceMetacognition",
    "InferenceGunas",
    "SovereignInferenceScorer",

    # Configuration
    "LayerInferenceConfig",
    "ArchitectureMode",

    # Utilities
    "load_inference_engine",
    "InferenceCheckpointLoader",

    # V10.0 Binding Cache Engines (Phase 5)
    "BindingCacheInferenceEngine",
    "BindingCacheInferenceConfig",
    "IntentPhaseInferenceModule",
    "BindingSalienceController",
    "OntologicalBindingCacheInferenceEngine",
    "OntologicalBindingCacheInferenceConfig",

    # V10.0 Sovereign State Monitor (Phase 5)
    "SovereignStateMonitor",
    "SovereignStateMetrics",
    "DepthLevel",
    "ReliabilityLevel",
    "SOVEREIGN_STATE_DIM",
    "BHAVA_NAMES",
    "KOSHA_NAMES",
    "VRITTI_NAMES",
    "GUNA_NAMES",
    "get_sovereign_state_summary",

    # Logit Modulation Decoding
    "LogitModulationConfig",
    "LogitModulator",
    "ModulationMode",
    "RetrievalScorer",
    "RetrievalScorerConfig",
    "RetrievalStrategy",
    "PenaltyScorer",
    "PenaltyScorerConfig",
    "LogitModulationBenchmark",
    "BenchmarkMetrics",
    "SweepResult",

    # Appendix F Stage 0: Generation Tracer
    "GenerationTracer",
    "BindingCacheTracerMixin",
    "CTMPlusTracerMixin",
    "MistralCGGenerationTracer",
    "BaselineStatisticsAnalyzer",

    # Appendix F Stage 1: Coherence-Aware Decoder
    "CoherenceAwareDecoder",
    "CoherenceDecoderConfig",

    # Appendix F Stage 2: Interpretive Conditioner
    "InterpretiveConditioner",
    "InterpretiveConditionerConfig",
    "InterpretiveStateBuilder",
    "BhavaVectorCompressor",

    # Appendix F Stage 4: Unified Coherence Controller
    "UnifiedCoherenceController",
    "UnifiedCoherenceConfig",

    # Appendix F Stage 7A: Semantic Coherence Integration
    "SemanticCoherenceIntegration",
    "SemanticCoherenceConfig",

    # Appendix F Stage 7C: Experiential State
    "ExperientialStateModule",
    "ExperientialStateConfig",

    # Appendix F Stage 7D: Polarity Encoding
    "PolarityGate",
    "PolarityEncodingConfig",

    # Appendix F Stage 7F: Phase Coherence Signal
    "PhaseCoherenceExtractor",
    "PhaseCoherenceAggregator",
    "PhaseCoherenceProjection",
    "PhaseCoherenceConfig",
]

__version__ = "2.0.0"
