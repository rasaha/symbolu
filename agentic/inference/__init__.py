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

Public API Policy
-----------------
``__all__`` reflects the **supported top-level API** — symbols with
at least one confirmed ``from agentic.inference import X`` external
caller. Additional symbols remain importable via the package (and
via direct submodule imports) for backward compatibility, but they
are not considered part of the stable top-level surface. Prefer
submodule imports for those, e.g.::

    from agentic.inference.generation_tracer import MistralCGGenerationTracer
    from agentic.inference.logit_modulation import LogitModulator
    from agentic.inference.perspective_synthesizer import PerspectiveSynthesizer

This narrower ``__all__`` does not remove any names — everything
previously accessible remains accessible. It only documents which
symbols the package owner commits to maintaining as a top-level
entry point.

Author: Sovereign-1 Training Initiative
Date: January 2026
Version: 2.1.0 (Phase 5 - V10.0 Binding Cache Support; narrowed public API)
"""

# =============================================================================
# Top-level public API (in __all__)
# =============================================================================
from .evolutionary_inference import EvolutionaryInferenceEngine
from .csr_inference import CSRInferenceGuard
from .metacognitive_monitor import InferenceMetacognition
from .guna_inference import InferenceGunas
from .layer_config import LayerInferenceConfig, ArchitectureMode
from .manager import InferenceManager, InferenceMode, InferenceManagerConfig
from .binding_cache_inference import BindingCacheInferenceEngine
from .ontological_binding_cache_inference import OntologicalBindingCacheInferenceEngine
from .sovereign_state_monitor import SovereignStateMonitor

# =============================================================================
# Submodule-level public (kept importable here for backward compatibility,
# but not listed in __all__; prefer direct submodule imports for these).
# =============================================================================
from .sovereign_scorer import SovereignInferenceScorer
from .checkpoint_utils import load_inference_engine, InferenceCheckpointLoader
from .binding_cache_inference import (
    BindingCacheInferenceConfig,
    IntentPhaseInferenceModule,
    BindingSalienceController,
)
from .ontological_binding_cache_inference import (
    OntologicalBindingCacheInferenceConfig,
)
from .sovereign_state_monitor import (
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
from .generation_tracer import (
    GenerationTracer,
    BindingCacheTracerMixin,
    CTMPlusTracerMixin,
    MistralCGGenerationTracer,
    BaselineStatisticsAnalyzer,
)
from .coherence_aware_decoder import (
    CoherenceAwareDecoder,
    CoherenceDecoderConfig,
)
from .interpretive_conditioner import (
    InterpretiveConditioner,
    InterpretiveConditionerConfig,
    InterpretiveStateBuilder,
    BhavaVectorCompressor,
)
from .unified_coherence_controller import (
    UnifiedCoherenceController,
    UnifiedCoherenceConfig,
)
from .semantic_coherence_integration import (
    SemanticCoherenceIntegration,
    SemanticCoherenceConfig,
)
from .experiential_state import (
    ExperientialStateModule,
    ExperientialStateConfig,
)
from .polarity_encoding import (
    PolarityGate,
    PolarityEncodingConfig,
)
from .phase_coherence_signal import (
    PhaseCoherenceExtractor,
    PhaseCoherenceAggregator,
    PhaseCoherenceProjection,
    PhaseCoherenceConfig,
)
from .signal_reconciliation import (
    reconcile_signals,
    ReconciliationResult,
    GunaSnapshot,
    VrittiSnapshot,
)
from .diagnostic_hooks import (
    InferenceDiagnosticHooks,
    DiagnosticHooksConfig,
    DiagnosticSnapshot,
)

# =============================================================================
# __all__ — narrowed to symbols with confirmed external top-level callers.
# =============================================================================
__all__ = [
    # Core engines
    "EvolutionaryInferenceEngine",
    "CSRInferenceGuard",
    "InferenceManager",
    "InferenceMode",
    "InferenceManagerConfig",
    # Monitoring
    "InferenceMetacognition",
    "InferenceGunas",
    # Configuration
    "LayerInferenceConfig",
    "ArchitectureMode",
    # V10.0 Binding Cache Engines (Phase 5)
    "BindingCacheInferenceEngine",
    "OntologicalBindingCacheInferenceEngine",
    # V10.0 Sovereign State Monitor (Phase 5)
    "SovereignStateMonitor",
]

__version__ = "2.1.0"
