"""Feature-group -> probe-feature-set assembly for the Bhava/ontology probe.

The extractor saves one feature dict per example (named arrays). These mappings turn those into
the named feature matrices the trainer evaluates. Keeping the mapping in one place makes the
"hidden_only is the control" contract explicit and testable.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np

# probe feature set -> ordered list of saved feature keys to concatenate.
FEATURE_SETS: Dict[str, List[str]] = {
    "bhava_only": ["bhava", "bhava_entropy"],
    "cg_state_32d": ["state32"],
    "delta_bhava_only": ["delta_bhava", "delta_bhava_norm"],
    "vowel_bhava": ["vowel_bhava"],                          # B1 Sanskrit-varna sound basis (12-d)
    "csr_contextual": ["csr_contextual"],                    # B2 contextual CSR (16-d)
    "csr_resonance": ["csr_resonance"],                      # B3 resonance summary
    "hidden_only": ["hidden_pooled"],                        # the REQUIRED control
    "hidden_plus_bhava": ["hidden_pooled", "bhava"],
    "hidden_plus_cg_state": ["hidden_pooled", "state32"],
}

# The separable CSR parts (audit: two-part Sanskrit-vowel + contextual, + resonance).
CSR_PART_KEYS: List[str] = ["csr_contextual", "vowel_bhava", "csr_resonance"]

# The reference/control every Bhava set is compared against.
CONTROL_SET = "hidden_only"

# High-dim feature keys that must be PCA-reduced PER GROUP (before concatenation) so they don't
# swamp the low-dim Bhava features in combined sets.
HIDDEN_KEYS = frozenset({"hidden_pooled", "hidden_last"})


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

