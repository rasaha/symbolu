"""
Experiment Pack v1 - Phoneme-Only Ontological Routing Validation
================================================================

EXPERIMENT_ONLY = True

WARNING: This file MUST NOT be used as ontology source of truth.
This is experimental validation code, NOT production infrastructure.

AUTHORITATIVE SOURCE:
    - Ontology executor: symbolu.ontology.phase4a
    - Frozen data: docs/data/*.json

This experiment pack validates the hypothesis:
"Phonemes do not carry semantics, but acquire word character through
deterministic ontological routing."

Grounding Requirement:
    - All varna/phoneme mappings MUST come from varna_bridge_map_v1.json
    - NO heuristic phoneme classification (IPA, SoundClass, etc.)
    - Fail closed on unknown varnas/phonemes
"""

EXPERIMENT_ONLY = True

__all__ = [
    "phoneme_only_router",
    "run_experiment_pack_v1",
]
