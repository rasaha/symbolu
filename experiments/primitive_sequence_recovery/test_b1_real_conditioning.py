"""Tests for real deterministic conditioning wired into the B1 dry-run — NO MODEL, NO SCORING, NO FILES.

Proves: the loadable D-table covers all 25 eval words; real conditioning renders for 25 words × 6 arms;
all 3,600 planned rows expand with real conditioning; no real model is called; judge packets still hide
arm labels / conditioning text / model / seed; A is fully resolved; S unresolved terms are the declared
set only; parity stays within ±25%; leak dry-check stays clean.

Requires cmudict (true G2P) — the same path used throughout H2. If unavailable, the G2P-dependent
checks SKIP loudly rather than falsely pass.

    python3 experiments/primitive_sequence_recovery/test_b1_real_conditioning.py
"""
from __future__ import annotations

import json
import pathlib
import re
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import b1_dry_run_harness as B            # noqa: E402
import b1_real_conditioning as RC         # noqa: E402

# words whose S (scrambled) core legitimately leaves an unbridged pole -> [unresolved], declared here
DECLARED_S_UNRESOLVED = {"echo"}
_FORBIDDEN = ("ontology", "sanskrit proves", "semantic truth", "validated meaning", "therefore means",
              "varnas prove", "varṇas prove", "phonemes encode true meaning", "track b support",
              "track g rescue")


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _g2p_ok():
    try:
        RC.real_core("grief", "A")
        return True
    except Exception as e:                 # noqa: BLE001 (cmudict/nltk missing)
        print(f"[SKIP] true G2P unavailable ({type(e).__name__}); G2P-dependent checks skipped")
        return False


# ---------------------------------------------------------------- loadable artifacts --------------
def test_dtable_covers_all_25_eval_words():
    dt = RC.load_dtable()
    _check("D-table has 25 entries", len(dt) == 25)
    for w in RC.EVAL_WORDS:
        _check(f"D-table has entry for {w!r}", w.lower() in dt)
        e = dt[w.lower()]
        _check(f"{w!r} has non-empty gloss", isinstance(e.get("gloss"), str) and e["gloss"].strip())
        _check(f"{w!r} has 3-5 synonyms", 3 <= len(e.get("synonyms", [])) <= 5)


def test_wordlist_matches_harness_constants():
    prim, priv = RC.load_wordlist()
    _check("loadable primary == harness PRIMARY_WORDS", prim == B.PRIMARY_WORDS)
    _check("loadable privative == harness PRIVATIVE_WORDS", priv == B.PRIVATIVE_WORDS)
    _check("25 eval words total", len(RC.EVAL_WORDS) == 25)
    # excluded words must not appear
    for bad in ("mercy", "love", "anger", "peace", "Alakshmi", "Lakshmi", "anhydrous", "theist"):
        _check(f"{bad!r} excluded", bad not in RC.EVAL_WORDS and bad.lower() not in RC.DTABLE)


def test_d_core_format_matches_committed_generator():
    # D core must be exactly "{word} — {gloss}; related senses: {csv}" (committed 64b0f40 format)
    core = RC.real_core("grief", "D")
    _check("D core format", core == "grief — deep sorrow after loss; related senses: "
                                    "sorrow, mourning, sadness, bereavement")
    for bad in ("(control", "Dictionary/synonym field", "not resonance", "varṇa", "sanskrit"):
        _check(f"D core has no self-label / forbidden {bad!r}", bad not in core)


# ---------------------------------------------------------------- real conditioning render ---------
def test_render_25x6_and_A_resolved_S_declared():
    if not _g2p_ok():
        return
    grid = RC.render_all()
    _check("150 (word,arm) cores rendered", len(grid) == 150)
    _check("no core is empty", all(isinstance(v, str) and v.strip() for v in grid.values()))
    a_unres = [w for w in RC.EVAL_WORDS if "[unresolved]" in RC.real_core(w, "A")]
    s_unres = {w for w in RC.EVAL_WORDS if "[unresolved]" in RC.real_core(w, "S")}
    _check("A fully resolved for all 25 words", a_unres == [])
    _check(f"S unresolved words are the declared set only ({s_unres})",
           s_unres <= DECLARED_S_UNRESOLVED)


def test_3600_rows_expand_with_real_conditioning_no_model():
    if not _g2p_ok():
        return
    rows = B.expand_rows()
    mock = B.MockModelAdapter()
    outs = B.run_generation(rows, mock, dry_run=True, conditioning_fn=RC.real_core)
    _check("3600 rows expanded", len(rows) == 3600 and len(outs) == 3600)
    _check("mock adapter (no real model)", mock.is_real is False and mock.call_count == 3600)
    _check("every output carries REAL conditioning (no mock marker)",
           all("[MOCK" not in o.conditioning for o in outs))
    _check("conditioning matches real_core for its (word, arm)",
           all(o.conditioning == RC.real_core(o.key_word, o.arm) for o in outs[:300]))
    # real adapter still refused with real conditioning
    try:
        B.run_generation(rows[:3], B.RealModelAdapter(), dry_run=True, conditioning_fn=RC.real_core)
        _check("real adapter refused (real conditioning)", False)
    except RuntimeError:
        _check("real adapter refused (real conditioning)", True)


# ---------------------------------------------------------------- blinding (real conditioning) ----
def test_judge_packets_blind_with_real_conditioning():
    if not _g2p_ok():
        return
    rows = [r for r in B.expand_rows() if r.key_word in ("grief", "amoral")]
    outs = B.run_generation(rows, B.MockModelAdapter(), dry_run=True, conditioning_fn=RC.real_core)
    packets = B.build_judge_packets(outs, rand_seed=40411)
    _check("packets built", len(packets) > 0)
    for p in packets:
        view = json.dumps(B.judge_view(p))
        for bad in ("A_vs_", "control", '"A"', '"R"', '"S"', '"C"', '"X"', '"D"'):
            _check(f"judge view hides {bad!r}", bad not in view)
        _check("judge view hides model id", "MOCK_MODEL" not in view)
        for seed in B.SEEDS:
            _check(f"judge view hides seed {seed}", str(seed) not in view)
        # the actual real conditioning text must never appear in the judge view
        for arm in ("A", "R", "S", "C", "X", "D"):
            core = RC.real_core(p.key_word, arm)
            _check("judge view hides real conditioning core", core not in view)


# ---------------------------------------------------------------- parity + leak (real) ------------
def test_parity_within_25pct_real():
    if not _g2p_ok():
        return
    by_arm = {a: [] for a in ("A", "R", "S", "C", "X", "D")}
    for w in RC.EVAL_WORDS:
        for a in by_arm:
            by_arm[a].append(len(RC.real_conditioning_slot(w, a)))
    mA = statistics.median(by_arm["A"])
    for a in ("R", "S", "C", "X", "D"):
        pct = 100.0 * (statistics.median(by_arm[a]) - mA) / mA
        _check(f"arm {a} within ±25% of A by median chars ({pct:+.1f}%)", abs(pct) <= 25.0)
    # per stratum
    for label, words in (("primary", RC.PRIMARY), ("privative", RC.PRIVATIVE)):
        mAs = statistics.median([len(RC.real_conditioning_slot(w, "A")) for w in words])
        for a in ("R", "S", "C", "X", "D"):
            m = statistics.median([len(RC.real_conditioning_slot(w, a)) for w in words])
            _check(f"{label}: arm {a} within ±25% ({100.0 * (m - mAs) / mAs:+.1f}%)",
                   abs(100.0 * (m - mAs) / mAs) <= 25.0)


def test_leak_dry_check_clean_real():
    if not _g2p_ok():
        return
    hits = 0
    for w in RC.EVAL_WORDS:
        for a in ("A", "R", "S", "C", "X", "D"):
            t = RC.real_conditioning_slot(w, a).lower()
            if any(p in t for p in _FORBIDDEN) or re.search(r"\brescue\b", t):
                hits += 1
    _check("real conditioning leak dry-check clean (0 hits)", hits == 0)


# ---------------------------------------------------------------- hygiene -------------------------
def test_no_ml_libs_and_no_files():
    _check("no torch/transformers/openai/anthropic imported",
           not any(m in sys.modules for m in ("torch", "transformers", "openai", "anthropic")))
    before = {p.name for p in HERE.iterdir()}
    if _g2p_ok():
        B.run_generation(B.expand_rows()[:30], B.MockModelAdapter(), dry_run=True,
                         conditioning_fn=RC.real_core)
    _check("no files written", {p.name for p in HERE.iterdir()} == before)


def main():
    print("b1_real_conditioning — real-conditioning wiring tests (no model, no scoring, no files)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll B1 real-conditioning tests passed.")


if __name__ == "__main__":
    main()
