"""Tests for the exploratory Track-C static-embedding semantic realizer.

Uses only SYNTHETIC vector fixtures (no real model, no real asset, no network). Proves the
machinery: deterministic ranking; planted-signal -> ENGINE_REALIZATION_SIGNAL; noise ->
NO_SIGNAL; hash-pinned loader; no auto-download; no hidden randomness; ONTOLOGICAL_SIGNAL is
never emitted; runner still NOT_RUN; manifest still NOT_READY; Stage A not imported.

    python3 experiments/primitive_sequence_recovery/test_semantic_realizer.py
"""
from __future__ import annotations

import json
import pathlib
import socket
import sys
import tempfile

import numpy as np

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import semantic_realizer as SR      # noqa: E402
import manifest as MF               # noqa: E402
import run_primitive_recovery as RUN  # noqa: E402

_FROZEN = _HERE / "frozen"


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _basis_vectors(tokens):
    """Orthonormal one-hot vectors, one per token (deterministic)."""
    toks = sorted(tokens)
    d = len(toks)
    return {t: np.eye(d)[i] for i, t in enumerate(toks)}


# ---- realizer basics --------------------------------------------------------------
def test_encode_and_cosine():
    vec = _basis_vectors(["water", "fire", "wet"])
    r = SR.StaticEmbeddingRealizer({"a0": "water wet", "a1": "fire"}, vec)
    q = r.encode_sequence(["a0"])
    _check("encode: unit norm", abs(np.linalg.norm(q) - 1.0) < 1e-9)
    _check("cosine: identical text -> ~1",
           abs(r.similarity(r.encode_candidate("water"), r.encode_candidate("water")) - 1.0) < 1e-9)
    _check("cosine: disjoint -> 0",
           abs(r.similarity(r.encode_candidate("water"), r.encode_candidate("fire"))) < 1e-9)


def test_oov_is_zero_vector_deterministic():
    r = SR.StaticEmbeddingRealizer({"a0": "totallyunknowntoken"}, _basis_vectors(["water"]))
    q = r.encode_sequence(["a0"])
    _check("oov: all-OOV -> zero vector", float(np.linalg.norm(q)) == 0.0)
    _check("oov: zero-vector similarity is 0", r.similarity(q, r.encode_candidate("water")) == 0.0)


def test_deterministic_ranking():
    vec = _basis_vectors(["water", "fire", "earth"])
    r = SR.StaticEmbeddingRealizer({"a0": "water"}, vec)
    cands = {"wT": "water", "wD1": "fire", "wD2": "earth"}
    _check("rank: deterministic across calls",
           SR.rank(r, ["a0"], cands) == SR.rank(r, ["a0"], cands))
    _check("rank: correct target first", SR.rank(r, ["a0"], cands)[0][0] == "wT")


# ---- planted signal vs noise (machinery, NOT theory) ------------------------------
def _synthetic_corpus():
    # 6 words, each meaning a distinct basis token; each word's single atom glosses that token.
    meanings = ["water", "fire", "earth", "air", "stone", "light"]
    vec = _basis_vectors(meanings)
    atoms = {f"atom_{i:02d}": meanings[i] for i in range(len(meanings))}   # atom -> its meaning word
    word_atoms = {f"w{i}": [f"atom_{i:02d}"] for i in range(len(meanings))}
    refs = {f"w{i}": meanings[i] for i in range(len(meanings))}
    # each word's candidate set = all words (K=6), true target included once
    dz = {f"w{i}": [f"w{j}" for j in range(len(meanings))] for i in range(len(meanings))}
    return atoms, word_atoms, refs, dz, vec


def test_planted_signal_yields_engine_signal():
    atoms, word_atoms, refs, dz, vec = _synthetic_corpus()
    m = SR.compute_exploratory_metrics(atoms, word_atoms, refs, dz, vec, n_scram=60, seed=1)
    _check("planted: real MRR == 1.0", abs(m["mrr_real"] - 1.0) < 1e-9)
    _check("planted: delta > 0", m["delta"] > 0.1)
    _check("planted: clears scramble gate", m["scramble_pct"] >= 0.95)
    _check("planted: label ENGINE_REALIZATION_SIGNAL", m["label"] == "ENGINE_REALIZATION_SIGNAL")
    _check("planted: NEVER ontological", m["label"] != "ONTOLOGICAL_SIGNAL")


def test_noise_yields_no_signal():
    atoms, word_atoms, refs, dz, vec = _synthetic_corpus()
    # break the mapping: every atom glosses the SAME token -> queries carry no word info
    noise_atoms = {k: "water" for k in atoms}
    m = SR.compute_exploratory_metrics(noise_atoms, word_atoms, refs, dz, vec, n_scram=60, seed=2)
    _check("noise: does not clear gate", m["scramble_pct"] < 0.95)
    _check("noise: label NO_SIGNAL", m["label"] == "NO_SIGNAL")


def test_decision_never_emits_ontological():
    for d, p in [(0.5, 1.0), (0.0, 0.0), (0.03, 0.96), (0.01, 0.99)]:
        _check(f"decide_engine({d},{p}) in allowed labels",
               SR.decide_engine(d, p) in SR.ENGINE_LABELS)
    _check("across-engines disagreement -> REALIZER_DEPENDENT",
           SR.decide_across_engines(["ENGINE_REALIZATION_SIGNAL", "NO_SIGNAL"]) == "REALIZER_DEPENDENT")
    _check("ONTOLOGICAL_SIGNAL not a Track-C label", "ONTOLOGICAL_SIGNAL" not in SR.ENGINE_LABELS)


# ---- asset loader: hash pin + no auto-download ------------------------------------
def test_loader_hash_pin_and_offline():
    with tempfile.TemporaryDirectory() as t:
        p = pathlib.Path(t) / "vecs.txt"
        p.write_text("water 1 0 0\nfire 0 1 0\n", encoding="utf-8")
        good = SR.sha256_file(p)
        v = SR.load_vectors(p, expected_sha256=good)
        _check("loader: loads 2 tokens", set(v) == {"water", "fire"})
        _check("loader: vectors unit-normalized", abs(np.linalg.norm(v["water"]) - 1.0) < 1e-9)
        raised = False
        try:
            SR.load_vectors(p, expected_sha256="0" * 64)
        except ValueError:
            raised = True
        _check("loader: rejects wrong sha256", raised)
        missing = False
        try:
            SR.load_vectors(pathlib.Path(t) / "nope.txt")
        except FileNotFoundError:
            missing = True
        _check("loader: missing file raises (no auto-download)", missing)


def test_no_network_during_scoring():
    atoms, word_atoms, refs, dz, vec = _synthetic_corpus()
    saved = socket.socket
    socket.socket = _boom
    try:
        m = SR.compute_exploratory_metrics(atoms, word_atoms, refs, dz, vec, n_scram=20, seed=3)
    finally:
        socket.socket = saved
    _check("network: scoring works with sockets disabled", m["mrr_real"] > 0)


def _boom(*a, **k):
    raise AssertionError("network access attempted")


def test_no_neural_or_llm_libs_imported():
    banned = {"torch", "tensorflow", "sentence_transformers", "transformers",
              "gensim", "nltk", "fasttext", "spacy", "huggingface_hub"}
    present = banned & set(sys.modules)
    _check(f"no neural/LLM libs imported (found {present})", not present)


# ---- frozen artifacts load-only (no real vectors -> OOV, no fabricated metrics) ---
def test_frozen_load_only_and_oov():
    atom_content, word_atoms, refs, dz, active = SR.load_frozen_corpus(_FROZEN, "en_gloss")
    _check("frozen: 107 active words", len(active) == 107)
    _check("frozen: every active word has atoms", all(word_atoms[w] for w in active))
    # with an empty vector table, real encodings are zero (no fabricated semantics)
    r = SR.StaticEmbeddingRealizer(atom_content, {})
    q = r.encode_sequence(word_atoms[active[0]])
    _check("frozen: no real vectors -> zero encoding (honest OOV, not fabricated)",
           float(np.linalg.norm(q)) == 0.0)


# ---- guardrails ------------------------------------------------------------------
def test_runner_still_not_run():
    _check("runner: NOT_RUN", RUN.run()["status"] == "NOT_RUN")


def test_manifest_still_not_ready():
    _check("manifest: NOT_READY", MF.check_readiness(_FROZEN)["status"] == "NOT_READY")
    man = json.loads((_FROZEN / "manifest.json").read_text(encoding="utf-8"))
    _check("manifest: declared NOT_READY", man["status"] == "NOT_READY")


def test_stage_a_not_imported():
    _check("Stage A not imported", not any(m.startswith("symbolu_neural") for m in sys.modules))


def main():
    print("semantic_realizer — exploratory Track-C tests (synthetic vectors; no real result)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll semantic_realizer (Track C) tests passed.")


if __name__ == "__main__":
    main()
