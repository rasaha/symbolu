"""Tests for the Phase-2 order-sensitive baseline realizer (normalized LCS).

Prove: order-sensitivity (distinguishes reversed sequences where the bag baseline does not);
deterministic outputs; stable tie-breaking; no network; no external model/neural libs; runner
still NOT_RUN; manifest still NOT_READY; Stage A not imported. No experiment is run, no corpus
metric/null is computed, nothing is written.

    python3 experiments/primitive_sequence_recovery/test_order_sensitive_realizer.py
"""
from __future__ import annotations

import json
import pathlib
import socket
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import baseline_realizer as B      # noqa: E402
import manifest as MF              # noqa: E402
import run_primitive_recovery as RUN  # noqa: E402

_FROZEN = _HERE / "frozen"


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


# ---- LCS + encoding --------------------------------------------------------------
def test_lcs_known_values():
    _check("lcs: abc vs abc = 3", B._lcs_len(("a", "b", "c"), ("a", "b", "c")) == 3)
    _check("lcs: order matters (abc vs cba = 1)", B._lcs_len(("a", "b", "c"), ("c", "b", "a")) == 1)
    _check("lcs: subsequence (axbyc vs abc = 3)",
           B._lcs_len(("a", "x", "b", "y", "c"), ("a", "b", "c")) == 3)
    _check("lcs: empty = 0", B._lcs_len((), ("a",)) == 0)


def test_encode_sequence_is_ordered_tuple():
    r = B.OrderSensitiveLexicalRealizer({"a0": "alpha", "a1": "beta"})
    _check("encode: returns an ordered tuple", r.encode_sequence(["a0", "a1"]) == ("alpha", "beta"))
    _check("encode: reversed atoms -> reversed tokens",
           r.encode_sequence(["a1", "a0"]) == ("beta", "alpha"))


def test_similarity_bounded_and_deterministic():
    r = B.OrderSensitiveLexicalRealizer({})
    _check("sim: identical = 1.0", abs(r.similarity(("a", "b"), ("a", "b")) - 1.0) < 1e-12)
    _check("sim: order break (ab vs ba) = 0.5", abs(r.similarity(("a", "b"), ("b", "a")) - 0.5) < 1e-12)
    _check("sim: empty/empty = 0.0", r.similarity((), ()) == 0.0)


# ---- the key property: order-sensitive distinguishes what the bag baseline cannot -
def test_order_sensitive_distinguishes_reversed_where_bag_does_not():
    atoms = {"a0": "alpha", "a1": "beta", "a2": "gamma"}
    order_r = B.OrderSensitiveLexicalRealizer(atoms)
    bag_r = B.LexicalOverlapRealizer(atoms)
    fwd, rev = ["a0", "a1", "a2"], ["a2", "a1", "a0"]
    cands = {"cAB": "alpha beta", "cBA": "beta alpha"}

    order_fwd = B.rank(order_r, fwd, cands)
    order_rev = B.rank(order_r, rev, cands)
    _check("order: forward ranks 'alpha beta' target first", order_fwd[0][0] == "cAB")
    _check("order: reversed ranks 'beta alpha' target first", order_rev[0][0] == "cBA")
    _check("order: reversing the sequence changes the ranking", order_fwd != order_rev)

    bag_fwd = B.rank(bag_r, fwd, cands)
    bag_rev = B.rank(bag_r, rev, cands)
    _check("bag: reversing does NOT change the ranking (order-blind)", bag_fwd == bag_rev)
    _check("bag: both candidates tie (identical token set)", bag_fwd[0][1] == bag_fwd[1][1])


# ---- determinism / tie-break / no randomness -------------------------------------
def test_identical_input_identical_ranking():
    r = B.OrderSensitiveLexicalRealizer({"a0": "river water", "a1": "cool"})
    cands = {"wT": "water", "wD1": "fire", "wD2": "earth"}
    _check("order: identical input -> identical ranking",
           B.rank(r, ["a0", "a1"], cands) == B.rank(r, ["a0", "a1"], cands))


def test_stable_tiebreak_no_hidden_randomness():
    r = B.OrderSensitiveLexicalRealizer({"a0": "zzz qqq"})   # no overlap -> all ties
    cands = {"wC": "anger", "wA": "water", "wB": "fire"}
    ranked = [c for c, _ in B.rank(r, ["a0"], cands)]
    _check("order: ties broken by id ascending", ranked == ["wA", "wB", "wC"])
    _check("order: stable across 50 repeats",
           all([c for c, _ in B.rank(r, ["a0"], cands)] == ranked for _ in range(50)))


def test_no_network_used_during_ranking():
    r = B.OrderSensitiveLexicalRealizer({"a0": "alpha beta"})
    cands = {"wT": "alpha beta", "wD": "gamma"}
    saved = socket.socket
    socket.socket = _boom
    try:
        out = B.rank(r, ["a0"], cands)
    finally:
        socket.socket = saved
    _check("network: ranking works with sockets disabled", out[0][0] == "wT")


def _boom(*a, **k):
    raise AssertionError("network access attempted")


def test_no_external_model_or_neural_libs_imported():
    banned = {"torch", "tensorflow", "sentence_transformers", "transformers",
              "gensim", "nltk", "sklearn", "spacy", "fasttext", "numpy"}
    present = banned & set(sys.modules)
    _check(f"no external model/neural libs imported (found {present})", not present)


# ---- artifact-based smoke test (load-only; NOT the experiment) -------------------
def test_artifact_based_smoke():
    r = B.OrderSensitiveLexicalRealizer.from_frozen(_FROZEN)
    word_atoms = B.load_word_atoms(_FROZEN)
    refs = B.load_en_meaning_refs(_FROZEN)
    distractors = json.loads((_FROZEN / "distractors.json").read_text(encoding="utf-8"))
    wl = json.loads((_FROZEN / "word_list.json").read_text(encoding="utf-8"))["words"]
    wid = next(w["word_id"] for w in wl if not w["exclude_flag"])
    cand_ids = distractors["assignments"][wid]
    cand_refs = {c: refs[c] for c in cand_ids}
    ranked = B.rank(r, word_atoms[wid], cand_refs)
    _check("artifact: ranking is a permutation of the K candidates",
           sorted(c for c, _ in ranked) == sorted(cand_ids))
    _check("artifact: reproducible", B.rank(r, word_atoms[wid], cand_refs) == ranked)
    _check("artifact: all similarities are floats in [0,1]",
           all(isinstance(s, float) and 0.0 <= s <= 1.0 for _, s in ranked))


# ---- guardrails ------------------------------------------------------------------
def test_runner_still_not_run():
    res = RUN.run()
    _check("runner: NOT_RUN", res["status"] == "NOT_RUN")
    _check("runner: no result", res["result"] is None)


def test_manifest_still_not_ready():
    _check("manifest: readiness NOT_READY", MF.check_readiness(_FROZEN)["status"] == "NOT_READY")
    man = json.loads((_FROZEN / "manifest.json").read_text(encoding="utf-8"))
    _check("manifest: declared status NOT_READY", man["status"] == "NOT_READY")


def test_phase1_realizer_untouched():
    _check("phase1: LexicalOverlapRealizer still present", hasattr(B, "LexicalOverlapRealizer"))
    _check("phase1: still Jaccard (bag) type",
           B.LexicalOverlapRealizer.realizer_type == "lexical_overlap_jaccard_en")


def test_stage_a_not_imported():
    _check("Stage A not imported", not any(m.startswith("symbolu_neural") for m in sys.modules))


def main():
    print("order_sensitive_realizer — Phase-2 LCS tests (no experiment, no result)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll order_sensitive_realizer tests passed.")


if __name__ == "__main__":
    main()
