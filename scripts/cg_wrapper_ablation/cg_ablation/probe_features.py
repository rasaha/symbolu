"""Feature-group -> probe-feature-set assembly for the Bhava/ontology probe.

The extractor saves one feature dict per example (named arrays). These mappings turn those into
the named feature matrices the trainer evaluates. Keeping the mapping in one place makes the
"hidden_only is the control" contract explicit and testable.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np

# probe feature set -> ordered list of saved feature keys to concatenate.
# Naming follows docs/STL_CSR_REFACTOR_PLAN.md (CSR = Context x Semantic x Resonance):
#   state_bhava (state[0:12], learned summary)  vs  phoneme_bhava (vowel cognitive mode, Resonance)
#   vritti_consonant (consonant motion, Resonance) ; context_r_ctx ; semantic ; hidden baseline.
FEATURE_SETS: Dict[str, List[str]] = {
    # --- legacy bhava-only probe sets (UNCHANGED keys so the existing report keeps working) ---
    "bhava_only": ["bhava", "bhava_entropy"],
    "cg_state_32d": ["state32"],
    "delta_bhava_only": ["delta_bhava", "delta_bhava_norm"],
    "hidden_only": ["hidden_pooled"],                        # generic strong baseline/control
    "hidden_plus_bhava": ["hidden_pooled", "bhava"],
    "hidden_plus_cg_state": ["hidden_pooled", "state32"],
    # --- STL/CSR static probe sets (corrected naming) ---
    "state_bhava_only": ["state_bhava", "state_bhava_entropy"],
    "state_32d": ["state32"],
    "phoneme_bhava_only": ["phoneme_bhava"],                 # R: vowel -> cognitive mode
    "vritti_consonant_only": ["vritti_consonant"],           # R: consonant -> motion
    "resonance_combined": ["resonance_combined"],            # R: 12D varna affinity
    "phoneme_bhava_plus_vritti": ["phoneme_bhava", "vritti_consonant"],
    "context_r_ctx_only": ["context_r_ctx"],                 # C: contextual CSR (16D)
    "semantic_only": ["semantic"],                           # S: referential embedding/ontology
    "state_bhava_plus_resonance": ["state_bhava", "resonance_combined"],
    "csr_static": ["context_r_ctx", "semantic", "resonance_combined"],   # C x S x R
    "state_bhava_plus_csr": ["state_bhava", "context_r_ctx", "semantic", "resonance_combined"],
    "hidden_plus_state_bhava": ["hidden_pooled", "state_bhava"],
    "hidden_plus_csr": ["hidden_pooled", "context_r_ctx", "semantic", "resonance_combined"],
    "hidden_plus_state_bhava_plus_csr":
        ["hidden_pooled", "state_bhava", "context_r_ctx", "semantic", "resonance_combined"],
}

# The separable CSR/Resonance component keys (audit: phoneme-Bhava + Vritti + contextual).
CSR_PART_KEYS: List[str] = ["context_r_ctx", "semantic", "resonance_combined",
                            "phoneme_bhava", "vritti_consonant"]

# The reference/control every Bhava set is compared against.
CONTROL_SET = "hidden_only"

# High-dim feature keys that must be PCA-reduced PER GROUP (before concatenation) so they don't
# swamp the low-dim Bhava/CSR features in combined sets. 'semantic' (pooled embeddings) is high-dim.
HIDDEN_KEYS = frozenset({"hidden_pooled", "hidden_last", "semantic"})


def group_arrays_for_set(arrays: Dict[str, np.ndarray], set_name: str, idxs) -> Dict[str, np.ndarray]:
    """Return {key: array[idxs]} for the keys composing a feature set (for evaluate_groups)."""
    out = {}
    for k in FEATURE_SETS[set_name]:
        a = np.asarray(arrays[k], dtype=float)
        if a.ndim == 1:
            a = a.reshape(-1, 1)
        out[k] = a[idxs]
    return out


def _as_vec(v) -> np.ndarray:
    a = np.atleast_1d(np.asarray(v, dtype=float)).ravel()
    return a


def build_matrix(feature_rows: Sequence[Dict], set_name: str) -> np.ndarray:
    """Stack the named feature set into an [N, D] matrix. Skips sets whose keys are absent."""
    keys = FEATURE_SETS[set_name]
    rows = []
    for fr in feature_rows:
        parts = [_as_vec(fr[k]) for k in keys]
        rows.append(np.concatenate(parts))
    return np.vstack(rows)


def available_sets(feature_rows: Sequence[Dict]) -> List[str]:
    """Which feature sets are fully present in the saved features (e.g. hidden may be omitted)."""
    if not feature_rows:
        return []
    have = set(feature_rows[0].keys())
    return [s for s, keys in FEATURE_SETS.items() if all(k in have for k in keys)]


def build_matrix_from_arrays(arrays: Dict[str, np.ndarray], set_name: str) -> np.ndarray:
    """Stack a named feature set from a dict of [N, d_key] arrays (the NPZ layout)."""
    keys = FEATURE_SETS[set_name]
    parts = []
    for k in keys:
        a = np.asarray(arrays[k], dtype=float)
        if a.ndim == 1:
            a = a.reshape(-1, 1)
        parts.append(a)
    return np.hstack(parts)


def available_sets_arrays(arrays: Dict[str, np.ndarray]) -> List[str]:
    have = set(arrays.keys())
    return [s for s, keys in FEATURE_SETS.items() if all(k in have for k in keys)]

