"""
symbolu.training.unified - Modular training components extracted from train_unified_llm.py

This package provides the core training infrastructure organized into focused modules:

- utilities: Tokenizers, CSR helpers, R-Matrix constants
- config: UnifiedTrainingConfig dataclass, model presets, SRK builders
- data: Dataset classes and data loading utilities
- vram_manager: VRAM monitoring and automatic batch sizing
- diagnostics: Kosha, CSR, Ontological, and Sovereign diagnostic functions
- ontological_flow: Ontological/Evolutionary bridges, flow networks
- intelligence_engine: MetacognitiveTracker, HiddenStateExtractor, EI engine
- gradient_control: Hierarchical gradient scaling and weight transfer
- training_state: Training state tracking, Guna analysis, Sattvic braking
- phase_controllers: Sovereign Phase Controller, Adaptive Training Controller
- scheduling: Window schedulers, warmup schedulers, PPL curriculum, RSS
- curriculum: PPL-gated curriculum, sequence length, inverted layer evolution
- relaxation: 9:3 -> 6:6 split transition controller
- evaluation: LRA validator, phase rotation testing, generation, ReadinessIndex
- losses: Ontological, sovereign, and phase loss computation
- control_plane: Architecture health checking and diagnostic probe hooks
- checkpointing: Checkpoint save/load with split-file support
- model_factory: Model creation factory, PerLayerPhaseController
"""

# --- utilities ---
from symbolu_training.training.unified.utilities import (
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
from symbolu_training.training.unified.config import (
    UnifiedTrainingConfig,
    MODEL_PRESETS,
    build_srk_config_from_legacy,
    build_srk_loss_config,
)

# --- data ---
from symbolu_training.training.unified.data import (
    TextDataset,
    FineWebStreamingDataset,
    cache_validation_batches,
    load_data,
)

# --- vram_manager ---
from symbolu_training.training.unified.vram_manager import (
    VRAMGovernor,
    AutoBatchSizer,
)

# --- diagnostics ---
from symbolu_training.training.unified.diagnostics import (
    compute_layer_gradient_norm,
    apply_kosha_phase_steering,
    compute_kosha_steering_stats,
    compute_kosha_vritti_diagnostics,
    format_kosha_diagnostic,
    compute_csr_diagnostics,
    format_csr_diagnostic,
    compute_onto_bridge_diagnostics,
    format_onto_bridge_diagnostic,
    compute_sovereign_state_diagnostics,
    format_sovereign_state_diagnostic,
)

# --- ontological_flow ---
from symbolu_training.training.unified.ontological_flow import (
    OntologicalBridge,
    create_ontological_bridge,
    compute_rmatrix_loss_weight,
    EvolutionaryBridge,
    ToroidalConsistencyLoss,
    EvolutionaryGate,
    EvolutionaryFlowNetwork,
    EvolutionaryFlowLoss,
)

# --- intelligence_engine ---
from symbolu_training.training.unified.intelligence_engine import (
    MetacognitiveTracker,
    HiddenStateExtractor,
    EvolutionaryIntelligenceEngine,
)

# --- gradient_control ---
from symbolu_training.training.unified.gradient_control import (
    HierarchicalGradientScaler,
    WeightTransfer,
)

# --- training_state ---
from symbolu_training.training.unified.training_state import (
    TrainingStateTracker,
    GradNormEMA,
    TrainingGunas,
    SattvicBrake,
)

# --- phase_controllers ---
from symbolu_training.training.unified.phase_controllers import (
    SovereignPhaseController,
    AdaptiveTrainingController,
    AdaptiveSlotLRController,
)

# --- scheduling ---
from symbolu_training.training.unified.scheduling import (
    DynamicWindowScheduler,
    AdaptiveWarmupScheduler,
    PPLAlphaCurriculum,
    ResonanceStateScheduler,
    update_alpha_schedule,
)

# --- curriculum ---
from symbolu_training.training.unified.curriculum import (
    CurriculumController,
    SequenceLengthCurriculum,
    dampen_layer_momentum,
    on_seq_len_transition,
    should_sync_curriculum_update,
    ThreePhaseCurriculum,
    InvertedLayerCurriculumController,
)

# --- relaxation ---
from symbolu_training.training.unified.relaxation import (
    DynamicRelaxationController,
)

# --- evaluation ---
from symbolu_training.training.unified.evaluation import (
    LRAValidator,
    run_phase_rotation_test,
    print_phase_rotation_results,
    generate_sample,
    compute_sample_metrics,
    run_quality_samples,
    run_factual_eval,
    ReadinessIndex,
)

# --- losses ---
from symbolu_training.training.unified.losses import (
    compute_ontological_loss,
    _build_sovereign_state,
    forward_chunked,
    compute_phase_loss,
)

# --- control_plane ---
from symbolu_training.training.unified.control_plane import (
    ArchitectureHealthReport,
    run_architecture_health_check,
    check_quad_utilization,
    LightweightProbeHooks,
)

# --- checkpointing ---
from symbolu_training.training.unified.checkpointing import (
    save_checkpoint,
    load_checkpoint,
)

# --- model_factory ---
from symbolu_training.training.unified.model_factory import (
    create_model,
    PerLayerPhaseController,
)

# Mistral CG wrapper (optional — requires transformers)
try:
    from symbolu_training.training.unified.mistral_wrapper import MistralCGWrapper
except ImportError:
    pass

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
    "compute_layer_gradient_norm",
    "apply_kosha_phase_steering",
    "compute_kosha_steering_stats",
    "compute_kosha_vritti_diagnostics",
    "format_kosha_diagnostic",
    "compute_csr_diagnostics",
    "format_csr_diagnostic",
    "compute_onto_bridge_diagnostics",
    "format_onto_bridge_diagnostic",
    "compute_sovereign_state_diagnostics",
    "format_sovereign_state_diagnostic",
    # ontological_flow
    "OntologicalBridge",
    "create_ontological_bridge",
    "compute_rmatrix_loss_weight",
    "EvolutionaryBridge",
    "ToroidalConsistencyLoss",
    "EvolutionaryGate",
    "EvolutionaryFlowNetwork",
    "EvolutionaryFlowLoss",
    # intelligence_engine
    "MetacognitiveTracker",
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
    # phase_controllers
    "SovereignPhaseController",
    "AdaptiveTrainingController",
    "AdaptiveSlotLRController",
    # scheduling
    "DynamicWindowScheduler",
    "AdaptiveWarmupScheduler",
    "PPLAlphaCurriculum",
    "ResonanceStateScheduler",
    "update_alpha_schedule",
    # curriculum
    "CurriculumController",
    "SequenceLengthCurriculum",
    "dampen_layer_momentum",
    "on_seq_len_transition",
    "should_sync_curriculum_update",
    "ThreePhaseCurriculum",
    "InvertedLayerCurriculumController",
    # relaxation
    "DynamicRelaxationController",
    # evaluation
    "LRAValidator",
    "run_phase_rotation_test",
    "print_phase_rotation_results",
    "generate_sample",
    "compute_sample_metrics",
    "run_quality_samples",
    "run_factual_eval",
    "ReadinessIndex",
    # losses
    "compute_ontological_loss",
    "_build_sovereign_state",
    "forward_chunked",
    "compute_phase_loss",
    # control_plane
    "ArchitectureHealthReport",
    "run_architecture_health_check",
    "check_quad_utilization",
    "LightweightProbeHooks",
    # checkpointing
    "save_checkpoint",
    "load_checkpoint",
    # model_factory
    "create_model",
    "PerLayerPhaseController",
    # model_factory (cont.)
    # Note: train(), evaluate(), main() are in symbolu.training.unified.train
    # They are NOT imported here to avoid circular imports (train.py imports from this package).
    # Use: from symbolu_training.training.unified.train import train, evaluate, main
]
