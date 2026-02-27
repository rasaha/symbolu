"""
symbolu.training.unified - Modular training components extracted from train_unified_llm.py

This package provides the core training infrastructure organized into focused modules:

- utilities: Tokenizers, CSR helpers, R-Matrix constants
- config: UnifiedTrainingConfig dataclass, model presets, SRK builders
- data: Dataset classes and data loading utilities
- vram_manager: VRAM monitoring and automatic batch sizing
- diagnostics: Kosha, CSR, Ontological, and Sovereign diagnostic functions
- ontological_flow: Ontological/Evolutionary bridges, flow networks, EI engine
- gradient_control: Hierarchical gradient scaling and weight transfer
- training_state: Training state tracking, Guna analysis, Sattvic braking
- scheduling: Phase controllers, warmup schedulers, PPL curriculum, RSS
- curriculum: PPL-gated curriculum, sequence length, inverted layer evolution
"""

# --- utilities ---
from symbolu.training.unified.utilities import (
    _SimpleByteTokenizer,
    CSR_STOPWORDS,
    WholeWordCSRHelper,
    calculate_sparse_csr_loss,
    SOVEREIGN_R_MATRIX,
    VRTTI_NAMES,
    ONTOLOGICAL_LAYER_NAMES,
    get_layer_vrtti_weights,
    get_pramana_weights,
    get_layer_gradient_scale,
    get_dominant_vrtti,
)

# --- config ---
from symbolu.training.unified.config import (
    UnifiedTrainingConfig,
    MODEL_PRESETS,
    build_srk_config_from_legacy,
    build_srk_loss_config,
)

# --- data ---
from symbolu.training.unified.data import (
    TextDataset,
    FineWebStreamingDataset,
    cache_validation_batches,
    load_data,
)

# --- vram_manager ---
from symbolu.training.unified.vram_manager import (
    VRAMGovernor,
    AutoBatchSizer,
)

# --- diagnostics ---
from symbolu.training.unified.diagnostics import (
    compute_kosha_vritti_diagnostics,
    format_kosha_vritti_diagnostics,
    compute_csr_diagnostics,
    format_csr_diagnostics,
    compute_onto_bridge_diagnostics,
    format_onto_bridge_diagnostics,
    compute_sovereign_state_diagnostics,
    format_sovereign_state_diagnostics,
    compute_evolutionary_flow_diagnostics,
    format_evolutionary_flow_diagnostics,
    print_comprehensive_diagnostics,
)

# --- ontological_flow ---
from symbolu.training.unified.ontological_flow import (
    OntologicalBridge,
    create_ontological_bridge,
    compute_rmatrix_loss_weight,
    EvolutionaryBridge,
    ToroidalConsistencyLoss,
    MetacognitiveTracker,
    EvolutionaryGate,
    EvolutionaryFlowNetwork,
    EvolutionaryFlowLoss,
    HiddenStateExtractor,
    EvolutionaryIntelligenceEngine,
)

# --- gradient_control ---
from symbolu.training.unified.gradient_control import (
    HierarchicalGradientScaler,
    WeightTransfer,
)

# --- training_state ---
from symbolu.training.unified.training_state import (
    TrainingStateTracker,
    GradNormEMA,
    TrainingGunas,
    SattvicBrake,
)

# --- scheduling ---
from symbolu.training.unified.scheduling import (
    SovereignPhaseController,
    DynamicWindowScheduler,
    AdaptiveTrainingController,
    AdaptiveWarmupScheduler,
    PPLAlphaCurriculum,
    ResonanceStateScheduler,
    update_alpha_schedule,
)

# --- curriculum ---
from symbolu.training.unified.curriculum import (
    CurriculumController,
    SequenceLengthCurriculum,
    ReadinessIndex,
    dampen_layer_momentum,
    on_seq_len_transition,
    should_sync_curriculum_update,
    ThreePhaseCurriculum,
    PerLayerPhaseController,
    InvertedLayerCurriculumController,
)

__all__ = [
    # utilities
    "_SimpleByteTokenizer",
    "CSR_STOPWORDS",
    "WholeWordCSRHelper",
    "calculate_sparse_csr_loss",
    "SOVEREIGN_R_MATRIX",
    "VRTTI_NAMES",
    "ONTOLOGICAL_LAYER_NAMES",
    "get_layer_vrtti_weights",
    "get_pramana_weights",
    "get_layer_gradient_scale",
    "get_dominant_vrtti",
    # config
    "UnifiedTrainingConfig",
    "MODEL_PRESETS",
    "build_srk_config_from_legacy",
    "build_srk_loss_config",
    # data
    "TextDataset",
    "FineWebStreamingDataset",
    "cache_validation_batches",
    "load_data",
    # vram_manager
    "VRAMGovernor",
    "AutoBatchSizer",
    # diagnostics
    "compute_kosha_vritti_diagnostics",
    "format_kosha_vritti_diagnostics",
    "compute_csr_diagnostics",
    "format_csr_diagnostics",
    "compute_onto_bridge_diagnostics",
    "format_onto_bridge_diagnostics",
    "compute_sovereign_state_diagnostics",
    "format_sovereign_state_diagnostics",
    "compute_evolutionary_flow_diagnostics",
    "format_evolutionary_flow_diagnostics",
    "print_comprehensive_diagnostics",
    # ontological_flow
    "OntologicalBridge",
    "create_ontological_bridge",
    "compute_rmatrix_loss_weight",
    "EvolutionaryBridge",
    "ToroidalConsistencyLoss",
    "MetacognitiveTracker",
    "EvolutionaryGate",
    "EvolutionaryFlowNetwork",
    "EvolutionaryFlowLoss",
    "HiddenStateExtractor",
    "EvolutionaryIntelligenceEngine",
    # gradient_control
    "HierarchicalGradientScaler",
    "WeightTransfer",
    # training_state
    "TrainingStateTracker",
    "GradNormEMA",
    "TrainingGunas",
    "SattvicBrake",
    # scheduling
    "SovereignPhaseController",
    "DynamicWindowScheduler",
    "AdaptiveTrainingController",
    "AdaptiveWarmupScheduler",
    "PPLAlphaCurriculum",
    "ResonanceStateScheduler",
    "update_alpha_schedule",
    # curriculum
    "CurriculumController",
    "SequenceLengthCurriculum",
    "ReadinessIndex",
    "dampen_layer_momentum",
    "on_seq_len_transition",
    "should_sync_curriculum_update",
    "ThreePhaseCurriculum",
    "PerLayerPhaseController",
    "InvertedLayerCurriculumController",
]
