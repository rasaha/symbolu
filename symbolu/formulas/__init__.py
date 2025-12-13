"""
Symbol-U Formulas Module
========================

Deterministic mathematical formulas for temporal analysis and resonance computation.

This module provides:
- Foundational temporal math formulas (resonance computation)
- Phase 1 Acoustic-Symbolic Tokenization (acoustic unit mapping, vṛtti assignment)

Phase 1 modules transform raw input into acoustic-symbolic units using
purely deterministic, non-semantic, language-agnostic rules.
"""

from symbolu.formulas.resonance_formulas import (
    compute_smi,
    compute_delta_smi,
    compute_bhava_gap,
    compute_tension_corridor,
)

# Phase 1: Acoustic-Symbolic Tokenization
from symbolu.formulas.acoustic_unit_mapper import (
    AcousticUnit,
    SoundClass,
    VowelHeight,
    VowelBackness,
    map_acoustic_units,
    get_acoustic_signature,
    count_syllable_nuclei,
)

from symbolu.formulas.vritti_mapper import (
    AcousticVritti,
    VrittiType,
    assign_vritti,
    assign_vritti_sequence,
    get_vritti_distribution,
    get_dominant_vritti,
    get_vritti_signature,
)

from symbolu.formulas.phase1_snapshot import (
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
    # Phase 1: Acoustic Unit Mapper
    "AcousticUnit",
    "SoundClass",
    "VowelHeight",
    "VowelBackness",
    "map_acoustic_units",
    "get_acoustic_signature",
    "count_syllable_nuclei",
    # Phase 1: Vṛtti Mapper
    "AcousticVritti",
    "VrittiType",
    "assign_vritti",
    "assign_vritti_sequence",
    "get_vritti_distribution",
    "get_dominant_vritti",
    "get_vritti_signature",
    # Phase 1: Snapshot
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
