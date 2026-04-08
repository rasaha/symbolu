"""
Symbol-U Formulas Module — Core/Substrate Utilities
====================================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CORE/SUBSTRATE LAYER                                   ║
║                                                                                ║
║  This module is part of the Core/Substrate layer.                              ║
║  It is NOT a pipeline phase and has no authority over intent, regime,          ║
║  semantics, or delivery.                                                       ║
║                                                                                ║
║  All formulas herein are:                                                      ║
║    • Deterministic (same inputs → same outputs)                                ║
║    • Stateless (no persistent state)                                           ║
║    • Non-authoritative (cannot influence governance decisions)                 ║
║    • Zero-LLM (no language model calls)                                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This module provides Core/Substrate utilities for:
- Foundational temporal math formulas (resonance computation)
- Acoustic-symbolic tokenization (acoustic unit mapping, vṛtti assignment)

HISTORICAL NOTE:
    Docstrings in this module may reference "Phase 1", "Phase 8", etc.
    These are HISTORICAL DEVELOPMENT LABELS, not pipeline execution phases.
    All formula files are Core/Substrate utilities regardless of their
    historical phase label.

    Correct interpretation:
    - "Phase 1" label → Core/Substrate utility introduced during early development
    - "Phase 8" label → Observability metric introduced during Phase 8 development
    - These do NOT correspond to authoritative pipeline phases (PO1, P6, P7, etc.)

Acoustic-symbolic modules transform raw input into acoustic-symbolic units using
purely deterministic, non-semantic, language-agnostic rules. They compute and
measure signals but do NOT interpret meaning, infer intent, or affect delivery.
"""

from symbolu_core.formulas.resonance_formulas import (
    compute_smi,
    compute_delta_smi,
    compute_bhava_gap,
    compute_tension_corridor,
)

# Core/Substrate: Acoustic-Symbolic Tokenization (historical "Phase 1" label)
from symbolu_core.formulas.acoustic_unit_mapper import (
    AcousticUnit,
    SoundClass,
    VowelHeight,
    VowelBackness,
    map_acoustic_units,
    get_acoustic_signature,
    count_syllable_nuclei,
)

from symbolu_core.formulas.vritti_mapper import (
    AcousticVritti,
    VrittiType,
    assign_vritti,
    assign_vritti_sequence,
    get_vritti_distribution,
    get_dominant_vritti,
    get_vritti_signature,
)

from symbolu_core.formulas.phase1_snapshot import (
    Phase1Snapshot,
    Phase1Metadata,
    create_phase1_snapshot,
    create_empty_snapshot,
    validate_phase1_snapshot,
    assert_no_semantic_leakage,
    PHASE_ID,
    PHASE_NAME,
    PHASE_VERSION,
)

__all__ = [
    # Resonance formulas
    "compute_smi",
    "compute_delta_smi",
    "compute_bhava_gap",
    "compute_tension_corridor",
    # Core/Substrate: Acoustic Unit Mapper
    "AcousticUnit",
    "SoundClass",
    "VowelHeight",
    "VowelBackness",
    "map_acoustic_units",
    "get_acoustic_signature",
    "count_syllable_nuclei",
    # Core/Substrate: Vṛtti Mapper
    "AcousticVritti",
    "VrittiType",
    "assign_vritti",
    "assign_vritti_sequence",
    "get_vritti_distribution",
    "get_dominant_vritti",
    "get_vritti_signature",
    # Core/Substrate: Snapshot Contract
    "Phase1Snapshot",
    "Phase1Metadata",
    "create_phase1_snapshot",
    "create_empty_snapshot",
    "validate_phase1_snapshot",
    "assert_no_semantic_leakage",
    "PHASE_ID",
    "PHASE_NAME",
    "PHASE_VERSION",
]
