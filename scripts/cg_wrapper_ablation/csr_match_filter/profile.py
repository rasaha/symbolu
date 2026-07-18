"""profile.py — phoneme/varna → 12D ontological realization profile (drives C and R).

`compute_12d_profile(term)` is deterministic from the term's letters (a g2p-free, varna-flavoured
seed mapping). The output is a phonemic-ontological *realization* — NOT the meaning. It is only ever
used for C (allowance) and R (realization). Meaning is confirmed separately by the non-phonemic S
firewall (semantic.py). If the real varna pipeline is importable it is preferred; otherwise this
built-in table runs (CPU-only, no torch).

IMPORTANT — THIS IS NOT A BHAVA LATENT VECTOR. The 12D output here is a deterministic
phonemic/orthographic realization profile computed from the term's *letters*. It is NOT a hidden-state
"Bhava" latent vector, NOT a learned probe direction, and NOT derived from any model activation. The
varna→bhava-flavoured naming (and the layer names in registry.py) describes a phonemic ontology, not a
latent Bhava read. Any hidden-state / learned-Bhava work belongs to Phase 4 (not built, not
runtime-active). See docs/CSR_MATCH_FILTER_PHASE4_HIDDEN_STATE_PROBE.md §"Current Bhava wiring status".
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .registry import LAYER_INDEX, LAYERS_12

# Seed letter → (layer, weight) map, grouped by rough articulation, loosely echoing varna→bhava.
# Illustrative defaults: tuned for coverage, not for any single term's "meaning".
_L = LAYER_INDEX
_LETTER_MAP: Dict[str, List[Tuple[int, float]]] = {
    # vowels — openness / potentiality / cognition / witness
    "a": [(_L["Potential"], 1.0), (_L["Cognition"], 0.6), (_L["Witness"], 0.5)],
    "e": [(_L["Cognition"], 1.0), (_L["Reasoning"], 0.6), (_L["Unifying"], 0.4)],
    "i": [(_L["Identity"], 0.7), (_L["Cognition"], 0.8), (_L["Integration"], 0.5)],
    "o": [(_L["Potential"], 0.7), (_L["Cognition"], 0.8), (_L["Purpose"], 0.6), (_L["Unifying"], 0.5),
          (_L["Integration"], 0.4)],
    "u": [(_L["Unifying"], 1.0), (_L["Integration"], 0.6), (_L["Absolving"], 0.5)],
    "y": [(_L["Witness"], 0.7), (_L["Purpose"], 0.6), (_L["Absolving"], 0.5)],
    # velar / hard plosives — execution / agency / structure (+ cognition for soft 'c')
    "k": [(_L["Execution"], 1.0), (_L["Agency"], 0.7), (_L["Structure"], 0.5)],
    "c": [(_L["Execution"], 0.8), (_L["Agency"], 0.5), (_L["Cognition"], 0.6), (_L["Reasoning"], 0.4)],
    "g": [(_L["Execution"], 0.8), (_L["Agency"], 0.7), (_L["Potential"], 0.4)],
    "q": [(_L["Execution"], 0.8), (_L["Structure"], 0.6)],
    # dental / alveolar stops — structure / identity / execution / purpose (+ light cognition)
    "t": [(_L["Structure"], 1.0), (_L["Identity"], 0.6), (_L["Execution"], 0.6), (_L["Purpose"], 0.5),
          (_L["Cognition"], 0.4)],
    "d": [(_L["Structure"], 0.9), (_L["Identity"], 0.7), (_L["Execution"], 0.5), (_L["Integration"], 0.5),
          (_L["Reasoning"], 0.4)],
    "n": [(_L["Identity"], 0.8), (_L["Integration"], 0.6), (_L["Unifying"], 0.5)],
    # labials — identity / potential / integration
    "p": [(_L["Identity"], 0.8), (_L["Purpose"], 0.6), (_L["Structure"], 0.5)],
    "b": [(_L["Identity"], 0.7), (_L["Potential"], 0.6), (_L["Integration"], 0.5)],
    "m": [(_L["Integration"], 0.9), (_L["Unifying"], 0.7), (_L["Witness"], 0.5)],
    # liquids — reasoning / unifying / integration
    "r": [(_L["Reasoning"], 1.0), (_L["Purpose"], 0.6), (_L["Integration"], 0.6), (_L["Unifying"], 0.4)],
    "l": [(_L["Unifying"], 0.9), (_L["Reasoning"], 0.6), (_L["Integration"], 0.5)],
    # sibilants / fricatives — cognition / reasoning / witness / purpose
    "s": [(_L["Cognition"], 0.9), (_L["Reasoning"], 0.7), (_L["Witness"], 0.5)],
    "z": [(_L["Cognition"], 0.7), (_L["Reasoning"], 0.6)],
    "f": [(_L["Purpose"], 0.8), (_L["Cognition"], 0.6)],
    "v": [(_L["Purpose"], 0.7), (_L["Reasoning"], 0.6), (_L["Integration"], 0.4)],
    "h": [(_L["Purpose"], 0.8), (_L["Witness"], 0.7), (_L["Absolving"], 0.6)],
    "w": [(_L["Unifying"], 0.7), (_L["Witness"], 0.6), (_L["Potential"], 0.5)],
    "j": [(_L["Reasoning"], 0.7), (_L["Cognition"], 0.6), (_L["Agency"], 0.4)],
    "x": [(_L["Structure"], 0.7), (_L["Reasoning"], 0.5)],
}


def _try_varna_profile(term: str):
    """Prefer the real varna pipeline if importable; return a length-12 vector or None."""
    try:
        import varna_mapping as VM  # noqa: F401
        # The real pipeline maps phonemes → varna → 12D. If the project exposes a direct helper we
        # use it; otherwise we fall back to the built-in table (kept deterministic + CPU-only).
        fn = getattr(VM, "term_to_12d", None)
        if callable(fn):
            vec = np.asarray(fn(term), dtype=float)
            if vec.shape == (12,):
                return vec
    except Exception:
        pass
    return None


# every ontological layer carries some baseline presence — a realization profile should never have a
# hard zero (that would read as "this layer does not exist for the word"). The floor lifts the dominant
# range into ~[FLOOR, 1.0], matching a fully-populated 12D affinity.
PROFILE_FLOOR = 0.45


def compute_12d_profile(term: str, floor: float = PROFILE_FLOOR) -> np.ndarray:
    """Deterministic phonemic-ontological realization profile for `term`, in [floor, 1.0] per layer.

    NOT the meaning of the term — only its realization profile, consumed by C and R. Every layer is
    populated (no hard zeros): affinity = floor + (1-floor) · (raw / max(raw)).
    """
    real = _try_varna_profile(term)
    if real is not None:
        raw = np.clip(real, 0.0, None)
    else:
        raw = np.zeros(12, dtype=float)
        for ch in term.lower():
            for layer, w in _LETTER_MAP.get(ch, []):
                raw[layer] += w
    if raw.max() <= 0:
        return np.full(12, floor, dtype=float)
    return floor + (1.0 - floor) * (raw / raw.max())   # filled affinity in [floor, 1.0]


def compute_12d_profile_dict(term: str) -> Dict[str, float]:
    """Named {layer: affinity} view of the realization profile (for tracing/inspection)."""
    return {name: round(float(v), 3) for name, v in zip(LAYERS_12, compute_12d_profile(term))}


def dominant_layers(vec: np.ndarray, k: int = 3) -> List[str]:
    order = np.argsort(-vec)[:k]
    return [LAYERS_12[i] for i in order]
