"""Exploratory Track C — static-embedding semantic realizer (INFRASTRUCTURE).

Track C is EXPLORATORY. It is NOT Track B, NOT confirmatory, and can NEVER emit
ONTOLOGICAL_SIGNAL. Its only question: do frozen semantic realizers extract any recoverable
signal from the realized primitive sequences *beyond the lexical baselines*?

Design: static word embeddings (deterministic lookup + cosine). Deterministic, offline,
hash-pinned, minimal deps (numpy only). No sampling, no network, no auto-download, no LLM,
no framework nondeterminism. Implements the existing `Realizer` interface (baseline_realizer).

This module contains only machinery. It computes NO real result unless a caller supplies a
real, hash-verified vector asset — which is not obtainable in the firewalled build
environment (see TRACK_C_RUN_REPORT.md). Stage A is never imported.
"""
from __future__ import annotations

import hashlib
import json
import pathlib

import numpy as np

_HERE = pathlib.Path(__file__).resolve().parent
_FROZEN = _HERE / "frozen"

import sys
sys.path.insert(0, str(_HERE))
from baseline_realizer import Realizer, tokenize_ordered  # noqa: E402

# labels this module may emit — ONTOLOGICAL_SIGNAL is deliberately absent
ENGINE_LABELS = ("ENGINE_REALIZATION_SIGNAL", "NO_SIGNAL", "REALIZER_DEPENDENT", "INCONCLUSIVE")


# ----------------------------------------------------------------- asset loader --
def sha256_file(path) -> str:
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def load_vectors(path, expected_sha256: str | None = None, vocab: set | None = None) -> dict:
    """Load a static word-embedding text file: `token v1 v2 ... vd` per line.

    - Hash-pinned: if `expected_sha256` is given it MUST match the on-disk file, else raises.
    - Offline only: reads a local file; never downloads. Missing file -> FileNotFoundError.
    - `vocab` (optional) restricts loading to those tokens (a vocabulary slice).
    Returns {token: unit-normalized np.ndarray(float64)}.
    """
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"vector asset not found: {path} (no auto-download; provide a hash-pinned asset)")
    if expected_sha256 is not None:
        actual = sha256_file(path)
        if actual != expected_sha256:
            raise ValueError(f"asset sha256 mismatch: expected {expected_sha256}, got {actual}")
    vecs: dict = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split(" ")
            if len(parts) < 3:
                continue
            tok = parts[0]
            if vocab is not None and tok not in vocab:
                continue
            v = np.asarray(parts[1:], dtype=np.float64)
            n = np.linalg.norm(v)
            vecs[tok] = v / n if n > 0 else v
    return vecs


# --------------------------------------------------------------- the realizer ----
class StaticEmbeddingRealizer(Realizer):
    """Mean-pooled static-embedding realizer. Deterministic; cosine similarity.

    Encoding: tokenize content -> look up unit token vectors -> mean-pool -> unit-normalize.
    Out-of-vocabulary tokens are skipped; an all-OOV / empty encoding is the zero vector
    (similarity 0). NOTE (limitation): mean-pool is ORDER-INSENSITIVE — this realizer probes
    the *semantic* gain over the lexical baselines, not order (order is a separate axis).
    """

    realizer_type = "static_embedding_meanpool"
    deterministic = True
    offline = True

    def __init__(self, atom_content: dict, vectors: dict):
        self._atom_content = dict(atom_content)
        self._vec = vectors
        self._dim = len(next(iter(vectors.values()))) if vectors else 0

    @classmethod
    def from_frozen(cls, realization_filename: str, vectors: dict, frozen_dir=_FROZEN):
        rec = json.loads(
            (pathlib.Path(frozen_dir) / realization_filename).read_text(encoding="utf-8"))
        return cls(rec["atom_content"], vectors)

    def _embed_tokens(self, tokens) -> np.ndarray:
        rows = [self._vec[t] for t in tokens if t in self._vec]
        if not rows:
            return np.zeros(self._dim, dtype=np.float64)
        v = np.mean(rows, axis=0)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def encode_sequence(self, atom_ids) -> np.ndarray:
        toks = []
        for a in atom_ids:
            toks.extend(tokenize_ordered(self._atom_content[a]))
        return self._embed_tokens(toks)

    def encode_candidate(self, meaning_ref) -> np.ndarray:
        return self._embed_tokens(tokenize_ordered(meaning_ref))

    def similarity(self, encoded_query, encoded_candidate) -> float:
        return float(np.dot(encoded_query, encoded_candidate))  # unit vectors -> cosine


# --------------------------------------------------------------- ranking + null --
def rank(realizer: Realizer, atom_ids, candidate_refs: dict):
    """Deterministic ranking: desc similarity, ties broken by candidate_id ascending."""
    q = realizer.encode_sequence(atom_ids)
    scored = [(cid, realizer.similarity(q, realizer.encode_candidate(ref)))
              for cid, ref in candidate_refs.items()]
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored


def _mrr_top1(realizer, word_atoms, refs, distractors, words):
    rr_sum, top1 = 0.0, 0
    for w in words:
        cand_ids = distractors[w]
        cand_refs = {c: refs[c] for c in cand_ids}
        order = [cid for cid, _ in rank(realizer, word_atoms[w], cand_refs)]
        r = order.index(w) + 1
        rr_sum += 1.0 / r
        top1 += int(r == 1)
    n = len(words)
    return rr_sum / n, top1 / n


def _scramble_atom_content(atom_content: dict, rng: np.random.Generator) -> dict:
    """Assignment-scramble null: permute which gloss attaches to which atom (query side only)."""
    keys = list(atom_content)
    vals = [atom_content[k] for k in keys]
    perm = rng.permutation(len(vals))
    return {keys[i]: vals[perm[i]] for i in range(len(keys))}


def decide_engine(delta: float, scramble_pct: float,
                  delta_threshold: float = 0.02, pct_gate: float = 0.95) -> str:
    """Per-engine exploratory label. NEVER ONTOLOGICAL_SIGNAL."""
    if delta > delta_threshold and scramble_pct >= pct_gate:
        return "ENGINE_REALIZATION_SIGNAL"
    return "NO_SIGNAL"


def decide_across_engines(labels) -> str:
    """Across ≥2 independent engines: disagreement -> REALIZER_DEPENDENT."""
    labels = list(labels)
    if not labels:
        return "INCONCLUSIVE"
    pos = [x == "ENGINE_REALIZATION_SIGNAL" for x in labels]
    if all(pos):
        return "ENGINE_REALIZATION_SIGNAL"
    if any(pos):
        return "REALIZER_DEPENDENT"
    return "NO_SIGNAL"


def compute_exploratory_metrics(atom_content, word_atoms, refs, distractors, vectors,
                                words=None, n_scram=1000, seed=0,
                                delta_threshold=0.02, pct_gate=0.95) -> dict:
    """EXPLORATORY Track-C metrics for one realization. Returns MRR/Top1/scramble-delta and an
    ENGINE_* label. Requires a real vector asset to be meaningful; with synthetic vectors it
    validates the machinery only. NEVER returns ONTOLOGICAL_SIGNAL.
    """
    if words is None:
        words = sorted(word_atoms)
    real = StaticEmbeddingRealizer(atom_content, vectors)
    mrr_real, top1_real = _mrr_top1(real, word_atoms, refs, distractors, words)

    rng = np.random.default_rng(seed)
    scram = np.empty(n_scram, dtype=np.float64)
    for i in range(n_scram):
        sc = StaticEmbeddingRealizer(_scramble_atom_content(atom_content, rng), vectors)
        scram[i], _ = _mrr_top1(sc, word_atoms, refs, distractors, words)
    mrr_scram_mean = float(scram.mean())
    delta = mrr_real - mrr_scram_mean
    scramble_pct = float(np.mean(scram < mrr_real))
    return {
        "track": "C_exploratory",
        "realizer_type": real.realizer_type,
        "n_words": len(words),
        "mrr_real": mrr_real,
        "top1_real": top1_real,
        "mrr_scram_mean": mrr_scram_mean,
        "delta": delta,
        "scramble_pct": scramble_pct,
        "n_scram": n_scram,
        "label": decide_engine(delta, scramble_pct, delta_threshold, pct_gate),
    }


# ------------------------------------------------- frozen-artifact load helpers --
def load_frozen_corpus(frozen_dir=_FROZEN, realization_id="en_gloss"):
    """Load (atom_content, word_atoms, refs, distractors, active_words) from frozen artifacts.
    Load-only; runs no scoring. Used by a real Track-C run once a vector asset is available.
    """
    fd = pathlib.Path(frozen_dir)
    tau = json.loads((fd / "assignment.json").read_text(encoding="utf-8"))["tau"]
    wl = json.loads((fd / "word_list.json").read_text(encoding="utf-8"))["words"]
    mr = json.loads((fd / "meaning_reference.json").read_text(encoding="utf-8"))["meanings"]
    dz = json.loads((fd / "distractors.json").read_text(encoding="utf-8"))["assignments"]
    rmap = {"en_gloss": "realization_en_gloss.json",
            "sa_term": "realization_sa_term.json",
            "concept_id": "realization_concept_id.json"}
    rec = json.loads((fd / rmap[realization_id]).read_text(encoding="utf-8"))
    atom_content = rec["atom_content"]
    word_atoms = {w["word_id"]: [tau[v] for v in w["varna_sequence"]] for w in wl}
    refs = {m["word_id"]: m["realization_specific_reference"][realization_id] for m in mr}
    active = sorted(w["word_id"] for w in wl if not w["exclude_flag"])
    return atom_content, word_atoms, refs, dz, active
