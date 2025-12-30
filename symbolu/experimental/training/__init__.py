"""
SymbolU12 Sattva-1 Training Module
===================================

Modular training infrastructure for the Sattva-1 protocol.

This module implements Google's Axiomatic Hardening proposal:
- Phase-Lock Trace constraint (τ ≥ 0.75)
- 3-tier Axiom Compliance Loss
- 50-paradox curriculum with synthesis engine
- R2H (Refusal-to-Hallucinate) evaluation
- IQ/InQ dual validation framework

Training Phases:
    Phase 1: Supervised Bhava Mapping
        - Standard NLL + ontological δ-loss
        - Bhava contrastive learning
        - τ_min = 0.50 (lenient)

    Phase 2: Adversarial RLHF
        - Paradox curriculum introduction
        - R_internal frozen, R_external trained
        - τ_min = 0.70 (moderate)

    Phase 3: Identity Freezing
        - All R matrices frozen
        - Only soft parameters adapt
        - τ_min = 0.75 (strict)

Hyperparameters (Google's recommendations):
    λ = 7.5 (Axiom loss weight)
    α = 0.85 (Decay baseline)
    T_ax = 0.2 (Axiom activation temperature)
    κ = 0.7 (Smṛti persistence)
    τ = 0.75 (Phase-Lock threshold)
    τ_critical = 0.30 (Epistemic death threshold)

Usage:
    from symbolu.experimental.training import (
        create_sattva1_trainer,
        Sattva1TrainingLoss,
        ParadoxSynthesizer,
        ValidationHarness,
    )

    # Create trainer
    trainer = create_sattva1_trainer(model, optimizer, config)

    # Train
    trainer.train()

    # Validate
    harness = ValidationHarness()
    report = harness.validate(model, generate_fn, forward_fn)

    print(f"Certified: {report.certified}")
"""

# Loss Functions
from .losses import (
    AxiomComplianceLoss,
    BhavaContrastiveLoss,
    EpistemicDecayLoss,
    SmritiPersistenceLoss,
    Sattva1TrainingLoss,
)

# Curriculum & Paradoxes
from .curriculum import (
    # Data structures
    Paradox,
    ParadoxCategory,
    ExpectedBhava,
    ParadoxSample,
    R2HResult,
    # Library
    PARADOX_LIBRARY,
    PARADOX_BY_ID,
    PARADOXES_BY_CATEGORY,
    # Evaluators
    R2HEvaluator,
    # Datasets
    ParadoxDataset,
    EpistemicGapDataset,
    # Scheduler
    CurriculumScheduler,
    CurriculumState,
)

# Paradox Synthesis
from .synthesis import (
    SynthesisStrategy,
    SynthesizedParadox,
    ParadoxSynthesizer,
    generate_training_corpus,
    generate_validation_set,
    create_curriculum_batches,
)

# Trainer
from .sattva1_trainer import (
    Sattva1TrainerConfig,
    TrainingPhase,
    PhaseConfig,
    Sattva1Trainer,
    create_sattva1_trainer,
)

# Monitoring Utilities
from .utils import (
    TraceSnapshot,
    TraceMonitor,
    DeterminantMonitor,
    EntropySentinel,
    R2HCheckpoint,
    R2HProgressTracker,
    Sattva1Monitor,
)

# Validation Framework
from .validation import (
    ValidationMode,
    IQResult,
    InQResult,
    ValidationReport,
    IQValidator,
    InQValidator,
    ValidationHarness,
    StressTest,
)


__all__ = [
    # === Loss Functions ===
    'AxiomComplianceLoss',
    'BhavaContrastiveLoss',
    'EpistemicDecayLoss',
    'SmritiPersistenceLoss',
    'Sattva1TrainingLoss',

    # === Curriculum & Paradoxes ===
    'Paradox',
    'ParadoxCategory',
    'ExpectedBhava',
    'ParadoxSample',
    'R2HResult',
    'PARADOX_LIBRARY',
    'PARADOX_BY_ID',
    'PARADOXES_BY_CATEGORY',
    'R2HEvaluator',
    'ParadoxDataset',
    'EpistemicGapDataset',
    'CurriculumScheduler',
    'CurriculumState',

    # === Paradox Synthesis ===
    'SynthesisStrategy',
    'SynthesizedParadox',
    'ParadoxSynthesizer',
    'generate_training_corpus',
    'generate_validation_set',
    'create_curriculum_batches',

    # === Trainer ===
    'Sattva1TrainerConfig',
    'TrainingPhase',
    'PhaseConfig',
    'Sattva1Trainer',
    'create_sattva1_trainer',

    # === Monitoring ===
    'TraceSnapshot',
    'TraceMonitor',
    'DeterminantMonitor',
    'EntropySentinel',
    'R2HCheckpoint',
    'R2HProgressTracker',
    'Sattva1Monitor',

    # === Validation ===
    'ValidationMode',
    'IQResult',
    'InQResult',
    'ValidationReport',
    'IQValidator',
    'InQValidator',
    'ValidationHarness',
    'StressTest',
]
