"""
Experiment Pack v1 - Phoneme-Only Ontological Routing Validation
================================================================

This experiment pack validates the hypothesis:
"Phonemes do not carry semantics, but acquire word character through
deterministic ontological routing."

Grounding Requirement:
    - All varna/phoneme mappings MUST come from varna_bridge_map_v1.json
    - NO heuristic phoneme classification (IPA, SoundClass, etc.)
    - Fail closed on unknown varnas/phonemes
"""

__all__ = [
    "phoneme_only_router",
    "run_experiment_pack_v1",
]
