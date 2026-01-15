"""
PhaseAttention Behavioral Probe Suite
======================================

A standalone diagnostic toolkit for testing what PhaseAttention layers learn.

This is a scientific probe for mechanism verification, not a training script.

Components:
-----------
- probe_cases: 15 minimal-pair probes testing relational selectivity
- phase_ablation: Utilities for scrambling/freezing phases
- phase_probe_runner: Main diagnostic script

Usage:
------
    # From command line
    python phase_probe_runner.py --checkpoint checkpoints/best.pt

    # Programmatic usage
    from scripts.phase_probes import (
        MINIMAL_PAIR_PROBES,
        SINGLE_PROBES,
        AblationMode,
        run_ablated_inference,
    )

Probe Categories:
-----------------
1. Role Binding (RB1-RB5): Test pronoun/reference resolution
2. Long-Range Persistence (LP1-LP4): Test entity tracking across filler
3. Semantic Interference (SI1-SI3): Test sense disambiguation
4. Negation/Polarity (NP1-NP3): Test scope and polarity resolution

Key Metrics:
------------
- Margin: logP(correct) - logP(best_wrong)
- Phase Sensitivity: Does ablation hurt margin?
- R_k/R_q: Phase collapse metrics (0=healthy, 1=collapsed)
- Head Redundancy: Inter-head similarity (0=diverse)

Failure Signatures:
------------------
- F1 (Decorative): Delta ~ 0 everywhere -> phase not used
- F2 (Brittle): Scramble breaks everything -> phase over-coupled
- F4 (Amplitude Cheating): High amp-phase corr -> amplitude compensating
"""

# Probe cases (pure data, no dependencies)
from .probe_cases import (
    MinimalPairProbe,
    SingleProbe,
    ProbeCategory,
    MINIMAL_PAIR_PROBES,
    SINGLE_PROBES,
    PROBES_BY_CATEGORY,
    get_probe_by_id,
    get_all_probe_ids,
    construct_qa_prompt,
)

__all__ = [
    # Probe data
    'MinimalPairProbe',
    'SingleProbe',
    'ProbeCategory',
    'MINIMAL_PAIR_PROBES',
    'SINGLE_PROBES',
    'PROBES_BY_CATEGORY',
    'get_probe_by_id',
    'get_all_probe_ids',
    'construct_qa_prompt',
]

# Phase ablation utilities (requires torch)
# Lazy import to avoid hard dependency when just using probe data
try:
    from .phase_ablation import (
        AblationMode,
        AblationResult,
        PhaseAblationHook,
        run_ablated_inference,
        phase_ablation_context,
        apply_phase_ablation_to_model,
        restore_phase_ablation,
    )
    __all__.extend([
        'AblationMode',
        'AblationResult',
        'PhaseAblationHook',
        'run_ablated_inference',
        'phase_ablation_context',
        'apply_phase_ablation_to_model',
        'restore_phase_ablation',
    ])
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
