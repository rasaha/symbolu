"""Static phonological feature chart (Stage A static data).

These are PROVISIONAL structural coordinates, NOT validated as the "true" varna
operators and NOT claimed to carry meaning. They are standard articulatory
descriptors (place/frontness, manner/openness, voicing, sonority/height),
normalized to [-1, 1], embedded here so Stage A has zero dependency on any
meaning-carrying module.

k = 4 feature factors, mapped one-to-one onto the 4 pre-registered generators in
operators.py:
    f0 place_frontness   -> G_A  (factor-1 slot rotation)
    f1 manner_openness    -> G_B  (factor-2 slot rotation)
    f2 voicing            -> G_C  (coupling generator)
    f3 sonority_height    -> G_D  (coupling generator)

The (G_A, G_B) pair COMMUTES (disjoint factors); the coupling generators do not.
This bakes the factorization hypothesis into the operators *precisely so it can
be tested against nulls* (see STRUCTURAL_V1_FACTORIZATION_METRIC.md). The baked-in
structure is acknowledged and is NOT itself evidence.
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np

# Feature names, in generator order. Frozen.
FEATURE_NAMES: Tuple[str, ...] = (
    "place_frontness",
    "manner_openness",
    "voicing",
    "sonority_height",
)
K = len(FEATURE_NAMES)

# Static chart: unit -> (place_frontness, manner_openness, voicing, sonority_height).
# Values are hand-set normalized articulatory coordinates in [-1, 1]. Frozen before
# any run. Order of dict insertion is the frozen unit order.
#
#   place_frontness: labial/front (-1) ... velar/back (+1)
#   manner_openness:  stop (-1) ... fricative ... approximant ... open vowel (+1)
#   voicing:          voiceless (-1) ... voiced (+1)
#   sonority_height:  low sonority/low (-1) ... high sonority/high (+1)
_CHART = {
    # consonants
    "p": (-1.0, -1.0, -1.0, -0.8),
    "b": (-1.0, -1.0, +1.0, -0.6),
    "t": (-0.2, -1.0, -1.0, -0.8),
    "d": (-0.2, -1.0, +1.0, -0.6),
    "k": (+1.0, -1.0, -1.0, -0.8),
    "g": (+1.0, -1.0, +1.0, -0.6),
    "s": (-0.2, +0.2, -1.0, -0.1),
    "z": (-0.2, +0.2, +1.0, +0.1),
    "m": (-1.0, +0.4, +1.0, +0.3),
    "n": (-0.2, +0.4, +1.0, +0.3),
    "r": (-0.1, +0.7, +1.0, +0.6),
    "l": (-0.3, +0.7, +1.0, +0.6),
    # vowels
    "a": (+0.6, +1.0, +1.0, +1.0),
    "i": (-0.9, +0.8, +1.0, +1.0),
}

UNITS: Tuple[str, ...] = tuple(_CHART.keys())
N_UNITS = len(UNITS)


def feature_matrix() -> np.ndarray:
    """Return the (N_UNITS x K) feature matrix in frozen unit order."""
    F = np.array([_CHART[u] for u in UNITS], dtype=np.float64)
    if F.shape != (N_UNITS, K):
        raise ValueError(f"feature matrix shape {F.shape} != ({N_UNITS},{K})")
    if not np.all(np.isfinite(F)):
        raise ValueError("non-finite feature values in chart")
    if np.abs(F).max() > 1.0 + 1e-12:
        raise ValueError("feature values must lie in [-1, 1]")
    return F


def unit_index(unit: str) -> int:
    return UNITS.index(unit)


def decompose(text: str) -> Tuple[List[int], List[str]]:
    """Map text to a sequence of unit indices using ONLY chart units.

    Surfaces every drop as an explicit warning. NO silent neutral fallback: a
    character absent from the chart is reported, never coerced to a default unit.
    Returns (indices, warnings).
    """
    warnings: List[str] = []
    idx: List[int] = []
    for ch in text.lower():
        if ch in _CHART:
            idx.append(unit_index(ch))
        elif ch.isspace():
            continue
        else:
            warnings.append(f"unit not in chart, dropped: {ch!r}")
    if not idx:
        warnings.append("empty unit sequence after decomposition (no chart units)")
    return idx, warnings
