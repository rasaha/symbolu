"""Table-derived dissimilarity matrix T (PREREG §5).

Loads the CURATED varna_lens/lexicon_wordformation.json and builds a varṇa×varṇa
dissimilarity from the table via a pluggable ENCODER:

  - categorical_encoder : REAL mechanical encoding (T_cat sensitivity) — one-hot of
    polarity/axis/element-derived class fields. Deterministic, no fit.
  - embedding_encoder    : PLACEHOLDER/FROZEN interface for the PRIMARY T_embed
    (sentence-embedding of `word_formation_reading`). Requires an approved, frozen
    model supplied via config; the scaffold supplies none and raises.

Also provides the scrambled-table assignment used by matrices.scrambled_null.

Building T is permitted scaffolding (PREREG step 4). Computing T-vs-P alignment on
the real table and emitting a verdict is NOT done here — that is the guarded run.
No semantic claim is made.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

DEFAULT_LEXICON = (Path(__file__).resolve().parents[2] /
                   "varna_lens" / "lexicon_wordformation.json")


def load_table(path=DEFAULT_LEXICON):
    """Return (keys, entries) for the 34 consonants, in file order.

    entries[k] = {reading, polarity, axis, element, varga} (raw strings from the
    curated table; no interpretation, no fit).
    """
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    keys, entries = [], {}
    for k, v in d["consonants"].items():
        keys.append(k)
        entries[k] = {
            "reading": v["word_formation_reading"]["english"],
            "axis": v["word_formation_reading"].get("axis", ""),
            "polarity": v.get("polarity", ""),
            "element": v.get("element", ""),
            "varga": v.get("varga", ""),
        }
    return keys, entries


# ----------------------------------------------------------------- encoders ----
def categorical_encoder(keys, entries) -> np.ndarray:
    """REAL mechanical one-hot encoding (T_cat). [n × categories], no fit.

    Encodes the table's own categorical fields (polarity, axis, varga string). This
    is a frozen sensitivity encoding — deliberately independent of the primary
    embedding encoder so §12 can detect encoding dependence.
    """
    def cats(field):
        vals = sorted({entries[k][field] for k in keys})
        idx = {v: i for i, v in enumerate(vals)}
        return idx
    fields = ["polarity", "axis", "varga"]
    idxs = {f: cats(f) for f in fields}
    width = sum(len(idxs[f]) for f in fields)
    X = np.zeros((len(keys), width), float)
    for r, k in enumerate(keys):
        off = 0
        for f in fields:
            X[r, off + idxs[f][entries[k][f]]] = 1.0
            off += len(idxs[f])
    return X


def embedding_encoder(keys, entries, model=None) -> np.ndarray:
    """PLACEHOLDER for the PRIMARY T_embed (frozen sentence-embedding of readings).

    The real run injects a frozen, approved embedding model via `model` (a callable
    str->vector pinned at §17). The scaffold supplies none, so this raises rather
    than fabricate primary-encoding vectors.
    """
    if model is None:
        raise NotImplementedError(
            "embedding_encoder is the PRIMARY T_embed interface; it requires a "
            "frozen approved model (§17). None supplied — scaffold does not run it.")
    return np.array([model(entries[k]["reading"]) for k in keys], float)


# ----------------------------------------------------------- T from features ---
def table_dissimilarity(X: np.ndarray, metric: str = "cosine") -> np.ndarray:
    """Varṇa×varṇa dissimilarity from an encoded table matrix X [n × d]."""
    X = np.asarray(X, float)
    n = X.shape[0]
    if metric == "cosine":
        norm = np.linalg.norm(X, axis=1)
        norm[norm == 0] = 1.0
        U = X / norm[:, None]
        T = 1.0 - U @ U.T
        np.fill_diagonal(T, 0.0)
        return T
    if metric == "hamming":
        T = np.zeros((n, n), float)
        for i in range(n):
            for j in range(n):
                if i != j:
                    T[i, j] = float(np.mean(np.abs(X[i] - X[j])))
        return T
    raise ValueError(f"unknown metric {metric!r}")


def scramble_builder(X: np.ndarray, metric: str = "cosine"):
    """Return build_T(perm) for matrices.scrambled_null.

    A scramble permutes which varṇa carries which table-entry row; the label *set*
    (the rows of X) is preserved, only their varṇa assignment is shuffled.
    """
    X = np.asarray(X, float)

    def build_T(perm):
        return table_dissimilarity(X[perm], metric=metric)

    return build_T
