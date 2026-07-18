"""Tests for Track G varṇa-derived polarity — the real A vector is DERIVED, not hand-authored.

Proves: A is deterministically derived from the frozen varṇa table + varṇa sequence; the smoke
boundaries contain no per-word A override (they equal the derivation); R = sign-flip(A); B =
seeded-scramble(A); a missing varṇa-table entry fails loudly; the table is flagged researcher-
authored / high-DOF / not-ontological. No LLM, no scoring, no model calls.

    python3 experiments/primitive_sequence_recovery/test_track_g_derive.py
"""
from __future__ import annotations

import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import track_g_derive as D          # noqa: E402

_TABLE = _HERE / "track_g_varna_polarity_table.json"
_AXES = _HERE / "track_g_polarity_axes.json"
_WORDS = _HERE / "track_g_smoke_words.jsonl"
_BOUNDS = _HERE / "track_g_smoke_boundaries.jsonl"
_ASSIGN = _HERE / "track_g_polarity_assignments.jsonl"
_SEEDS = _HERE / "track_g_smoke_seeds.json"


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


TABLE = D.load_table(_TABLE)
AX = D.axis_order(_AXES)
POLES = D.axis_poles(_AXES)
WORDS = {w["word_id"]: w for w in (json.loads(l) for l in _WORDS.read_text().splitlines() if l.strip())}
BOUNDS = {b["case_id"]: b for b in (json.loads(l) for l in _BOUNDS.read_text().splitlines() if l.strip())}
SCRAMBLE_SEED = json.loads(_SEEDS.read_text())["seeds"]["scramble"]


def test_table_covers_all_34_varnas_and_is_flagged():
    tau = json.loads((_HERE / "frozen/assignment.json").read_text())["tau"]
    _check("table covers all 34 frozen varṇas", set(TABLE["varnas"]) == set(tau))
    _check("table flagged researcher-authored",
           TABLE["authoring_status"] == "researcher_authored_candidate_representation")
    _check("table flagged unvalidated", TABLE["validation_status"] == "unvalidated")
    _check("table flagged high-DOF", TABLE["degrees_of_freedom"] == "high_degrees_of_freedom")
    _check("table flagged not-ontological", TABLE["evidence_status"] == "not_ontological_evidence")


def test_derive_is_deterministic():
    seq = WORDS["g000"]["dev_varna_sequence"]
    _check("derive_A deterministic", D.derive_A(seq, TABLE, AX) == D.derive_A(seq, TABLE, AX))


def test_A_is_derived_not_overridden():
    for cid, b in BOUNDS.items():
        seq = WORDS[cid.split("-")[0]]["dev_varna_sequence"]
        A = D.derive_A(seq, TABLE, AX)
        _check(f"{cid}: stored A == derived A (no per-word override)", b["dev_polarity_real_derived"] == A)
        _check(f"{cid}: real desc == describe(derived A)",
               b["polarity_real_desc"].endswith(D.describe(A, POLES)))


def test_R_flips_and_B_scrambles_derived_A():
    for cid, b in BOUNDS.items():
        seq = WORDS[cid.split("-")[0]]["dev_varna_sequence"]
        A = D.derive_A(seq, TABLE, AX)
        _check(f"{cid}: R == sign-flip(A)", b["dev_polarity_random_flip"] == D.random_flip(A))
        _check(f"{cid}: B == scramble(A, seed)",
               b["dev_polarity_scrambled"] == D.scramble(A, SCRAMBLE_SEED, cid))
        # R genuinely inverts every non-zero sign
        _check(f"{cid}: R inverts non-zero signs",
               all(b["dev_polarity_random_flip"][ax] == -A[ax] for ax in AX))


def test_missing_varna_entry_fails_loudly():
    try:
        D.derive_A(["not_a_real_varna_id"], TABLE, AX)
    except KeyError:
        _check("missing varṇa -> KeyError", True); return
    _check("missing varṇa -> KeyError", False)


def test_assignments_do_not_author_A():
    asg = [json.loads(l) for l in _ASSIGN.read_text().splitlines() if l.strip()]
    for a in asg:
        _check(f"{a['case_id']}: assignment does not author A", a.get("a_vector_authored_here") is False)
        _check(f"{a['case_id']}: no A/polarity vector field in assignment",
               not any(k in a for k in ("polarity_real", "dev_polarity_real", "a_vector", "axis_signs")))
        _check(f"{a['case_id']}: keeps frozen pre-registration",
               a.get("assigned_before_scoring") is True and a.get("frozen") is True)


def test_no_llm_libs():
    _check("no LLM/ML libs imported",
           not any(m in sys.modules for m in ("torch", "transformers", "openai", "anthropic")))


def main():
    print("track_g_derive — varṇa-derived polarity tests (no LLM, no scoring)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Track G derivation tests passed.")


if __name__ == "__main__":
    main()
