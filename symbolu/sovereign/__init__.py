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

Phase 2 (Current):
- PIDGovernor: Vritti-based control
- SovereignTransformer: Hybrid architecture with virtual nexus
- SovereignGunaComputer: Hardened entropy/variance/similarity
- DeterministicPhonemeEncoder: Hash-based C-Signal
- ReferentLookup: WORD_TO_REFERENT integration for S-Signal

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
]

__version__ = '2.0.0'
