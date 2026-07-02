"""Tests for the Phase-1 lexical-overlap baseline realizer.

Prove: deterministic outputs; identical input -> identical ranking; no network; no external
model libs; no hidden randomness; runner still NOT_RUN; manifest still NOT_READY; Stage A
untouched. No experiment is run, no corpus metric/null is computed, nothing is written.

    python3 experiments/primitive_sequence_recovery/test_baseline_realizer.py
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


# ---- tokenizer / similarity ------------------------------------------------------
def test_tokenize_deterministic_and_mechanical():
    a = B.tokenize("Hope / forward-grasping DESIRE")
    b = B.tokenize("hope forward grasping desire")
    _check("tokenize: case/punctuation-insensitive, identical", a == b)
    _check("tokenize: expected tokens", a == frozenset({"hope", "forward", "grasping", "desire"}))
    _check("tokenize: drops 1-char tokens", B.tokenize("a bc d") == frozenset({"bc"}))
    _check("tokenize: repeatable", B.tokenize("x1 X1 y") == B.tokenize("x1 x1 y"))


def test_jaccard_known_values():
    r = B.LexicalOverlapRealizer({})
    _check("jaccard: 2/4 = 0.5",
           abs(r.similarity(frozenset("abc"), frozenset("bcd")) - 0.5) < 1e-12)
    _check("jaccard: identical sets = 1.0",
           abs(r.similarity(frozenset("ab"), frozenset("ab")) - 1.0) < 1e-12)
    _check("jaccard: disjoint = 0.0",
           r.similarity(frozenset("ab"), frozenset("cd")) == 0.0)
    _check("jaccard: empty/empty = 0.0",
           r.similarity(frozenset(), frozenset()) == 0.0)


def test_interface_contract():
    r = B.LexicalOverlapRealizer({"a0": "hope"})
    _check("interface: is a Realizer", isinstance(r, B.Realizer))
    for m in ("encode_sequence", "encode_candidate", "similarity"):
        _check(f"interface: has {m}", callable(getattr(r, m)))
    _check("interface: Realizer is abstract (cannot instantiate)",
           _abstract_cannot_instantiate())


def _abstract_cannot_instantiate():
    try:
        B.Realizer()          # type: ignore[abstract]
        return False
    except TypeError:
        return True


def test_encode_sequence_is_order_insensitive_by_design():
    # KNOWN LIMITATION: set encoding => order-insensitive. Documented, not a feature.
    r = B.LexicalOverlapRealizer({"a0": "alpha one", "a1": "beta two"})
    _check("encode: order-insensitive (baseline limitation)",
           r.encode_sequence(["a0", "a1"]) == r.encode_sequence(["a1", "a0"]))


# ---- ranking: mechanism + determinism --------------------------------------------
def test_planted_overlap_ranks_target_first():
    # atom glosses for the query word contain the target meaning token, not the distractors'.
    r = B.LexicalOverlapRealizer({"a0": "river water flow", "a1": "cool wet"})
    cands = {"wT": "water", "wD1": "anger", "wD2": "mountain"}
    ranked = B.rank(r, ["a0", "a1"], cands)
    _check("rank: planted target is first", ranked[0][0] == "wT")
    _check("rank: target similarity > 0", ranked[0][1] > 0.0)


def test_identical_input_identical_ranking():
    r = B.LexicalOverlapRealizer({"a0": "river water", "a1": "cool"})
    cands = {"wT": "water", "wD1": "fire", "wD2": "earth"}
    _check("rank: identical input -> identical ranking",
           B.rank(r, ["a0", "a1"], cands) == B.rank(r, ["a0", "a1"], cands))


def test_deterministic_tiebreak_no_hidden_randomness():
    # all-zero overlap -> pure tie -> deterministic tie-break by candidate_id ascending.
    r = B.LexicalOverlapRealizer({"a0": "zzz qqq"})
    cands = {"wC": "anger", "wA": "water", "wB": "fire"}
    ranked = [c for c, _ in B.rank(r, ["a0"], cands)]
    _check("rank: ties broken by id ascending", ranked == ["wA", "wB", "wC"])
    # repeat many times: never varies (no hidden randomness / set-order leakage)
    _check("rank: stable across 50 repeats",
           all([c for c, _ in B.rank(r, ["a0"], cands)] == ranked for _ in range(50)))


def test_no_network_used_during_ranking():
    r = B.LexicalOverlapRealizer({"a0": "river water"})
    cands = {"wT": "water", "wD": "fire"}
    saved = socket.socket
    socket.socket = _boom            # any network attempt now raises
    try:
        out = B.rank(r, ["a0"], cands)     # must succeed with networking disabled
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


# ---- artifact-based (load-only; not the experiment) ------------------------------
def test_artifact_based_ranking_is_a_deterministic_permutation():
    r = B.LexicalOverlapRealizer.from_frozen(_FROZEN)
    word_atoms = B.load_word_atoms(_FROZEN)
    refs = B.load_en_meaning_refs(_FROZEN)
    distractors = json.loads((_FROZEN / "distractors.json").read_text(encoding="utf-8"))
    wl = json.loads((_FROZEN / "word_list.json").read_text(encoding="utf-8"))["words"]
    wid = next(w["word_id"] for w in wl if not w["exclude_flag"])  # first active word
    cand_ids = distractors["assignments"][wid]
    cand_refs = {c: refs[c] for c in cand_ids}
    ranked = B.rank(r, word_atoms[wid], cand_refs)
    ids = sorted(c for c, _ in ranked)
    _check("artifact: ranking is a permutation of the K candidates", ids == sorted(cand_ids))
    _check("artifact: target present among candidates", wid in cand_ids)
    _check("artifact: reproducible", B.rank(r, word_atoms[wid], cand_refs) == ranked)


# ---- guardrails: nothing enabled / run / touched --------------------------------
def test_runner_still_not_run():
    res = RUN.run()
    _check("runner: NOT_RUN", res["status"] == "NOT_RUN")
    _check("runner: computed False", res["computed"] is False)
    _check("runner: no result", res["result"] is None)


def test_manifest_still_not_ready():
    rd = MF.check_readiness(_FROZEN)
    _check("manifest: readiness NOT_READY", rd["status"] == "NOT_READY")
    man = json.loads((_FROZEN / "manifest.json").read_text(encoding="utf-8"))
    _check("manifest: declared status NOT_READY", man["status"] == "NOT_READY")


def test_stage_a_not_imported():
    _check("Stage A not imported by baseline realizer / gate / runner",
           not any(m.startswith("symbolu_neural") for m in sys.modules))


def main():
    print("baseline_realizer — Phase-1 lexical-overlap tests (no experiment, no result)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll baseline_realizer tests passed.")


if __name__ == "__main__":
    main()
