"""
Sovereign-1 Architecture Implementation
========================================

This package implements the Sovereign-1 specification for cognitive state
management in transformer models.

Architecture Overview:
---------------------
1. SovereignTransformer: Hybrid O(n²)/O(n) architecture with PID Governor
2. SovereignObserver: Computes 128-D state delta (Guna + S + R + C signals)
3. SovereignLoss: Decomposed loss preventing Signal Washing
4. PIDGovernor: Control-theoretic gating with Vritti tuning
5. SovereignGunaComputer: Shannon entropy-based cognitive dynamics
6. SovereignRouter: Dynamic nexus selection (Virtual Nexus)
7. SovereignMonitor: Real-time telemetry dashboard
8. InoculationTrainer: Self-supervised state learning

State Layout (128D):
-------------------
- Guna[0:16]: Cognitive dynamics (Sattva, Rajas, Tamas)
- S-Signal[16:48]: Referent/semantic class (from WORD_TO_REFERENT)
- R-Signal[48:96]: Ontological state (12 Bhavas × 4 dims)
- C-Signal[96:128]: Phonemic features (deterministic hash)

Phase 1 (Complete):
- SovereignLoss: Decomposed state friction
- SovereignObserver: State delta computation
- BhavaTransitionPrior: Ontological transition validation

Phase 2 (Complete):
- PIDGovernor: Vritti-based control
- SovereignTransformer: Hybrid architecture with virtual nexus
- SovereignGunaComputer: Hardened entropy/variance/similarity
- DeterministicPhonemeEncoder: Hash-based C-Signal
- ReferentLookup: WORD_TO_REFERENT integration for S-Signal

Phase 3 (Complete):
- SovereignRouter: Dynamic nexus selection based on ontology
- SovereignMonitor: Real-time state telemetry
- COGNADE Export: Hardware bridge for PA-VPU

Phase 4 (Complete):
- InoculationTrainer: Self-supervised state learning with alpha decay
- BankDisambiguationTest: Homonym disambiguation validation
- AuthorityStressTest: PID Governor stress verification

Reference: docs/hardware/SOVEREIGN_1_DESIGN_IMPLEMENTATION.md
"""

# Phase 1: Core loss and observer
from symbolu.sovereign.loss import (
    SovereignLoss,
    SovereignLossConfig,
    LegacyLossAdapter,
)

from symbolu.sovereign.observer import (
    SovereignObserver,
    BhavaTransitionPrior,
    DeterministicPhonemeEncoder,
    ReferentLookup,
)

# Phase 2: Engine modules
from symbolu.sovereign.pid_governor import (
    PIDGovernor,
    PIDGovernorConfig,
    EmergencyBrake,
)

from symbolu.sovereign.guna import (
    SovereignGunaComputer,
    GunaMonitor,
)

from symbolu.sovereign.transformer import (
    SovereignTransformer,
    SovereignTransformerConfig,
    AmbidextrousLayer,
)

# Phase 3: Transmission & Dashboard
from symbolu.sovereign.router import (
    SovereignRouter,
    SovereignRoutingDecision,
    NexusMode,
    ONTOLOGY_TO_NEXUS,
    get_optimal_nexus,
    is_logic_heavy,
    is_memory_heavy,
)

from symbolu.sovereign.telemetry import (
    SovereignMonitor,
    SovereignProfiler,
    StateSnapshot,
    create_monitor,
)

from symbolu.sovereign.cognade_export import (
    generate_header,
    generate_phoneme_impl,
    serialize_referent_table,
    pack_state_to_binary,
    unpack_binary_to_state,
    export_cognade_sdk,
)

# Phase 4: Training & Validation
from symbolu.sovereign.training import (
    InoculationTrainer,
    InoculationConfig,
    AlphaScheduler,
    create_inoculation_trainer,
    BankDisambiguationTest,
    HomonymTestSuite,
    DisambiguationResult,
    run_bank_test,
    AuthorityStressTest,
    StressTestResult,
    run_stress_test,
)

# V9.8.0: Sovereign Reasoning Kernel (SRK)
from symbolu.sovereign.reasoning_kernel import (
    SRKConfig,
    SovereignReasoningKernel,
    SovereignEmbedding,
    IsomorphicMappingRouter,
    OntologicalBridge,
    WitnessArbitrator,
    SynthesisGate,
    VrittiGate,
    KoshaShiftController,
    MaunaProtocol,
    PhaseExtractionHook,
    SOVEREIGN_STATE_DIM,
    BHAVA_NAMES,
    KOSHA_NAMES,
    VRITTI_NAMES,
    GUNA_NAMES,
    create_logic_templates,
)

# V9.8.0: Sovereign Loss Functions
from symbolu.sovereign.sovereign_loss import (
    SovereignLossConfig as SRKLossConfig,
    SovereignLoss as SRKLoss,
    SovereignAnnealer,
    TeleologicalOptimizer,
    BackwardScoreCalculator,
    ForwardScoreCalculator,
    PhaseCoherenceCalculator,
)

__all__ = [
    # Phase 1: Loss
    'SovereignLoss',
    'SovereignLossConfig',
    'LegacyLossAdapter',

    # Phase 1: Observer
    'SovereignObserver',
    'BhavaTransitionPrior',

    # Phase 2: Observer enhancements
    'DeterministicPhonemeEncoder',
    'ReferentLookup',

    # Phase 2: PID Governor
    'PIDGovernor',
    'PIDGovernorConfig',
    'EmergencyBrake',

    # Phase 2: Guna Computer
    'SovereignGunaComputer',
    'GunaMonitor',

    # Phase 2: Transformer
    'SovereignTransformer',
    'SovereignTransformerConfig',
    'AmbidextrousLayer',

    # Phase 3: Router (Transmission)
    'SovereignRouter',
    'SovereignRoutingDecision',
    'NexusMode',
    'ONTOLOGY_TO_NEXUS',
    'get_optimal_nexus',
    'is_logic_heavy',
    'is_memory_heavy',

    # Phase 3: Telemetry (Dashboard)
    'SovereignMonitor',
    'SovereignProfiler',
    'StateSnapshot',
    'create_monitor',

    # Phase 3: COGNADE Export (Hardware Bridge)
    'generate_header',
    'generate_phoneme_impl',
    'serialize_referent_table',
    'pack_state_to_binary',
    'unpack_binary_to_state',
    'export_cognade_sdk',

    # Phase 4: Training (Inoculation)
    'InoculationTrainer',
    'InoculationConfig',
    'AlphaScheduler',
    'create_inoculation_trainer',

    # Phase 4: Validation
    'BankDisambiguationTest',
    'HomonymTestSuite',
    'DisambiguationResult',
    'run_bank_test',

    # Phase 4: Stress Testing
    'AuthorityStressTest',
    'StressTestResult',
    'run_stress_test',

    # V9.8.0: Sovereign Reasoning Kernel (SRK)
    'SRKConfig',
    'SovereignReasoningKernel',
    'SovereignEmbedding',
    'IsomorphicMappingRouter',
    'OntologicalBridge',
    'WitnessArbitrator',
    'SynthesisGate',
    'VrittiGate',
    'KoshaShiftController',
    'MaunaProtocol',
    'PhaseExtractionHook',
    'SOVEREIGN_STATE_DIM',
    'BHAVA_NAMES',
    'KOSHA_NAMES',
    'VRITTI_NAMES',
    'GUNA_NAMES',
    'create_logic_templates',

    # V9.8.0: Sovereign Loss Functions
    'SRKLossConfig',
    'SRKLoss',
    'SovereignAnnealer',
    'TeleologicalOptimizer',
    'BackwardScoreCalculator',
    'ForwardScoreCalculator',
    'PhaseCoherenceCalculator',
]

__version__ = '9.8.0'
