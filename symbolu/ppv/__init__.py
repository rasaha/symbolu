"""
PPV - Phonemic Propensity Vectors for Symbol-U
=================================================

PPV provides numeric structural signals derived from phoneme sequences
and phase metadata. PPV is NOT "emotion meaning" - it is purely structural.

Modules:
    ppv_contract_v1: PPV data contract (PPVDim, PPVVector)
    ppv_builder_v1: Deterministic PPV builder

Hard Constraints:
    - PPV is numeric only: ints/bools/tuples; fixed length; no free-form strings
    - PPV is deterministic and hash-stable
    - PPV does NOT introduce "meaning inference"
    - No ML/NLP imports
    - No randomness
    - No time/datetime
"""

from symbolu.ppv.ppv_contract_v1 import (
    # Version
    PPV_CONTRACT_VERSION,
    # Constants
    PPV_DIM_COUNT,
    PPV_DIM_ORDER,
    PPV_VALUE_MIN,
    PPV_VALUE_MAX,
    # Enums
    PPVDim,
    # Dataclasses
    PPVVector,
    # Functions
    create_ppv_vector,
    validate_ppv_invariants_v1,
)

from symbolu.ppv.ppv_builder_v1 import (
    # Version
    PPV_BUILDER_VERSION,
    # Feature table
    PHONEME_FEATURES,
    DEFAULT_PHONEME_FEATURES,
    # Context
    PPVBuildContext,
    # Build functions
    build_ppv_from_context,
    build_ppv_for_artifact,
)


__all__ = [
    # Versions
    "PPV_CONTRACT_VERSION",
    "PPV_BUILDER_VERSION",
    # Constants
    "PPV_DIM_COUNT",
    "PPV_DIM_ORDER",
    "PPV_VALUE_MIN",
    "PPV_VALUE_MAX",
    # Enums
    "PPVDim",
    # Dataclasses
    "PPVVector",
    "PPVBuildContext",
    # Feature table
    "PHONEME_FEATURES",
    "DEFAULT_PHONEME_FEATURES",
    # Functions
    "create_ppv_vector",
    "validate_ppv_invariants_v1",
    "build_ppv_from_context",
    "build_ppv_for_artifact",
]
