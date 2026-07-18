"""Phonetic-feature scaffold → dissimilarity matrix P (PREREG §5).

P is the **independent yardstick**: an articulatory-feature representation of each
varṇa that contains NO table information. The real B0 run freezes a public feature
library (PanPhon / IPA feature tables, §17). Here we provide:

  - load_feature_matrix(keys): use PanPhon if importable; else a clearly-labelled
    FROZEN MOCK feature table (scaffolding stand-in — NOT the frozen real artifact).
  - dissimilarity(features, metric): build P (hamming primary, cosine sensitivity).

The mock exists only so the plumbing has shapes to move; every statistical test in
this package runs on purpose-built synthetic matrices, not on the mock. No fit, no
verdict, no semantic claim.
"""
from __future__ import annotations

import numpy as np

from control import PLACE, MANNER

# place ordinal: front → back (articulatory frontness), a finer axis than the C grid
_PLACE_ORD = {"labial": 0, "dental": 1, "retroflex": 2, "palatal": 3, "velar": 4,
              "semivowel": 2, "sibilant": 2, "aspirate": 5, "conjunct": 4}

# --- FROZEN MOCK feature table (scaffolding ONLY; real run uses PanPhon/IPA) ---
# Binary/ordinal articulatory features finer than the coarse C classes, so the
# scaffold's P has structure beyond C (lets the partial-Mantel plumbing exercise).
_FEATURE_NAMES = ["place_ord", "voiced", "aspirated", "nasal",
                  "continuant", "sibilant", "approximant", "retroflex"]


def _mock_features_for(key: str) -> list[float]:
    place, manner = PLACE[key], MANNER[key]
    voiced = manner in ("stop3", "stop4", "nasal", "approximant") or key in ("ha",)
    aspirated = manner in ("stop2", "stop4") or key == "ha"
    nasal = manner == "nasal"
    sibilant = manner == "sibilant"
    approximant = manner == "approximant"
    continuant = manner in ("sibilant", "approximant", "aspirate")
    retroflex = place == "retroflex" or key in ("ra", "ssa")
    return [float(_PLACE_ORD[place]), float(voiced), float(aspirated), float(nasal),
            float(continuant), float(sibilant), float(approximant), float(retroflex)]


def load_feature_matrix(keys):
    """Return (features [n × f], feature_names, source).

    Tries PanPhon (real articulatory features over a frozen IAST→IPA map); falls
    back to the FROZEN MOCK table. The real run pins source='panphon' and freezes
    the version (§17); 'mock' is scaffolding only and must never set a verdict.
    """
    try:
        import panphon  # noqa: F401  (optional; absent in this sandbox)
    except Exception:
        feats = np.array([_mock_features_for(k) for k in keys], float)
        return feats, list(_FEATURE_NAMES), "mock"
    # Real-library path is intentionally left as a frozen interface: the IAST→IPA
    # mapping and PanPhon feature set are frozen at §17, not improvised here.
    raise NotImplementedError(
        "PanPhon present but the frozen IAST→IPA mapping is a §17 artifact; "
        "supply it via the approved run config, not the scaffold.")


def dissimilarity(features: np.ndarray, metric: str = "hamming") -> np.ndarray:
    """Varṇa×varṇa dissimilarity P from a feature matrix.

    metric='hamming': mean per-feature absolute difference (primary).
    metric='cosine' : 1 − cosine similarity of feature rows (sensitivity).
    """
    X = np.asarray(features, float)
    n = X.shape[0]
    P = np.zeros((n, n), float)
    if metric == "hamming":
        for i in range(n):
            for j in range(n):
                if i != j:
                    P[i, j] = float(np.mean(np.abs(X[i] - X[j])))
    elif metric == "cosine":
        norm = np.linalg.norm(X, axis=1)
        norm[norm == 0] = 1.0
        U = X / norm[:, None]
        P = 1.0 - U @ U.T
        np.fill_diagonal(P, 0.0)
    else:
        raise ValueError(f"unknown metric {metric!r}")
    return P
