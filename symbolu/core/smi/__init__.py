"""
SMI (Semantic Mismatch Index) Module
====================================

The SMI module computes the distance between inner acoustic meaning (kosha)
and outer semantic meaning (ontology) for text analysis.

Core Components:
- SMIEngine: Main computation engine for SMI scores
- VrittiMapper: Maps syllables to vritti distributions (5D)
- AcousticMapper: Maps consonants to acoustic features
- AspectMapper: Maps words to aspect distributions (10D)

Key Concepts:
- Kosha (5 layers): Inner consciousness depth (ANNAMAYA → ANANDAMAYA)
- Ontology (10 layers): Outer manifestation breadth (Execution → Universal)
- Vritti (5 modes): Consciousness states (pramana, viparyaya, vikalpa, smrti, nidra)
- SMI: Normalized distance between kosha and ontology layers

Usage:
    from symbolu.core.smi import SMIEngine, compute_smi

    engine = SMIEngine()
    result = engine.compute("hello world")
    print(result.smi)  # 0.0 - 1.0

    # Quick computation
    smi = compute_smi("hello world")
"""

from symbolu.core.smi.smi_engine import (
    SMIEngine,
    compute_smi,
    analyze_word,
    extract_consonant,
    extract_vowel,
    syllabify,
    get_kosha_level,
    get_ontology_level,
    compute_vritti_distribution,
)

from symbolu.core.smi.vritti_mapping import (
    VrittiMapper,
    VrittiDistributionResult,
    VrittiType,
    VRITTI_ORDER,
    VRITTI_DESCRIPTIONS,
    map_syllable_to_vritti,
    aggregate_vritti_distributions,
)

from symbolu.core.smi.acoustic_mapper import (
    AcousticMapper,
    AcousticFeatures,
    ArticulationType,
    VoicingType,
    PlaceOfArticulation,
    CONSONANT_FEATURES,
    get_consonant_features,
    compute_word_acoustic_signature,
)

from symbolu.core.smi.aspect_mapping import (
    AspectMapper,
    AspectDistributionResult,
    AspectType,
    ASPECT_ORDER,
    VRITTI_ASPECT_COUPLING_MATRIX,
    map_word_to_aspect,
    apply_vritti_aspect_coupling,
)

__all__ = [
    # SMI Engine
    "SMIEngine",
    "compute_smi",
    "analyze_word",
    "extract_consonant",
    "extract_vowel",
    "syllabify",
    "get_kosha_level",
    "get_ontology_level",
    "compute_vritti_distribution",
    # Vritti Mapping
    "VrittiMapper",
    "VrittiDistributionResult",
    "VrittiType",
    "VRITTI_ORDER",
    "VRITTI_DESCRIPTIONS",
    "map_syllable_to_vritti",
    "aggregate_vritti_distributions",
    # Acoustic Mapping
    "AcousticMapper",
    "AcousticFeatures",
    "ArticulationType",
    "VoicingType",
    "PlaceOfArticulation",
    "CONSONANT_FEATURES",
    "get_consonant_features",
    "compute_word_acoustic_signature",
    # Aspect Mapping
    "AspectMapper",
    "AspectDistributionResult",
    "AspectType",
    "ASPECT_ORDER",
    "VRITTI_ASPECT_COUPLING_MATRIX",
    "map_word_to_aspect",
    "apply_vritti_aspect_coupling",
]
