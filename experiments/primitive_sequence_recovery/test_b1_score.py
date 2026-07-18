"""Tests for the B1 scorer — synthetic judge/truth data, NO MODEL, NO real files.

Verifies: choice->A-win via truth; median-majority across judges; item-clustered aggregation feeding
the FROZEN bootstrap/Holm/apply_verdict; and each verdict branch (beats-all, no-signal,
dictionary-dominates, random-matches). Primary/privative kept separate.

    python3 experiments/primitive_sequence_recovery/test_b1_score.py
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import b1_dry_run_harness as B    # noqa: E402
import run_b1_score as S          # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _synth(awin_by_ctrl, n_words=10, n_tasks=4, stratum="primary"):
    """Build (choices, kept, truth) where every A-vs-c packet yields A-win == awin_by_ctrl[c]
    (1 -> A-side chosen, 0 -> control-side, 0.5 -> tie), identically across all three judges."""
    words = (B.PRIMARY_WORDS if stratum == "primary" else B.PRIVATIVE_WORDS)[:n_words]
    tasks = list(B.TASKS)[:n_tasks]
    truth, choices, idx = {}, {j: {} for j in S.JUDGE_SLUGS}, 0
    for w in words:
        for t in tasks:
            for c in B.CO_PRIMARIES:
                did = f"P{idx:05d}"
                idx += 1
                truth[did] = {"control": c, "key_word": w, "task": t, "model": "m", "seed": "1",
                              "stratum": stratum, "truth": {"Output 1": "A", "Output 2": c}}
                v = awin_by_ctrl[c]
                ch = "output_1_better" if v == 1 else ("output_2_better" if v == 0 else "tie_no_preference")
                for j in S.JUDGE_SLUGS:
                    choices[j][did] = ch
    return choices, list(S.JUDGE_SLUGS), truth


def _verdict(awin_by_ctrl):
    choices, kept, truth = _synth(awin_by_ctrl)
    agg, _flag, _n = S.aggregate(choices, kept, truth, "primary")
    per = S.score_stratum(agg)
    return B.apply_verdict({c: per[c] for c in B.CO_PRIMARIES})


def test_a_win_mapping():
    _check("out1=A -> 1", S.a_win("output_1_better", {"Output 1": "A", "Output 2": "D"}) == 1.0)
    _check("out2 chosen but A is out1 -> 0", S.a_win("output_2_better", {"Output 1": "A", "Output 2": "D"}) == 0.0)
    _check("out2=A chosen -> 1", S.a_win("output_2_better", {"Output 1": "D", "Output 2": "A"}) == 1.0)
    _check("tie -> 0.5", S.a_win("tie_no_preference", {"Output 1": "A", "Output 2": "D"}) == 0.5)
    _check("both_bad -> 0.5", S.a_win("both_bad", {"Output 1": "A", "Output 2": "D"}) == 0.5)


def test_median_majority():
    import statistics
    _check("median [1,1,0]=1 (2 judges say A)", statistics.median([1.0, 1.0, 0.0]) == 1.0)
    _check("median [1,0,0]=0", statistics.median([1.0, 0.0, 0.0]) == 0.0)
    _check("median [1,0.5,0]=0.5 (split)", statistics.median([1.0, 0.5, 0.0]) == 0.5)


def test_verdict_beats_all():
    _check("A beats all five -> LIMITED_GENERATION_UTILITY",
           _verdict({"D": 1, "R": 1, "S": 1, "C": 1, "X": 1}) == "LIMITED_GENERATION_UTILITY")


def test_verdict_no_signal():
    _check("all ties -> NO_SIGNAL",
           _verdict({"D": 0.5, "R": 0.5, "S": 0.5, "C": 0.5, "X": 0.5}) == "NO_SIGNAL")
    _check("beats only X -> NO_SIGNAL",
           _verdict({"D": 0.5, "R": 0.5, "S": 0.5, "C": 0.5, "X": 1}) == "NO_SIGNAL")


def test_verdict_dictionary_dominates():
    _check("beats R/S/C/X but not D -> DICTIONARY_DOMINATES",
           _verdict({"D": 0.5, "R": 1, "S": 1, "C": 1, "X": 1}) == "DICTIONARY_DOMINATES")


def test_verdict_random_or_scrambled_matches():
    _check("beats D/C/X but R ties -> RANDOM_OR_SCRAMBLED_MATCHES",
           _verdict({"D": 1, "R": 0.5, "S": 1, "C": 1, "X": 1}) == "RANDOM_OR_SCRAMBLED_MATCHES")


def test_verdict_surface_structure_explains():
    _check("beats D/R/S/X but C ties -> SURFACE_STRUCTURE_EXPLAINS",
           _verdict({"D": 1, "R": 1, "S": 1, "C": 0.5, "X": 1}) == "SURFACE_STRUCTURE_EXPLAINS")


def test_invalid_posthoc_flag_short_circuits():
    choices, kept, truth = _synth({"D": 1, "R": 1, "S": 1, "C": 1, "X": 1})
    agg, _f, _n = S.aggregate(choices, kept, truth, "primary")
    per = S.score_stratum(agg)
    _check("invalid_posthoc flag -> INVALID_POSTHOC",
           B.apply_verdict({c: per[c] for c in B.CO_PRIMARIES}, flags={"invalid_posthoc": True})
           == "INVALID_POSTHOC")


def test_primary_and_privative_separated():
    choices, kept, truth = _synth({"D": 1, "R": 1, "S": 1, "C": 1, "X": 1}, stratum="primary")
    cp, kp, tp = _synth({"D": 0.5, "R": 0.5, "S": 0.5, "C": 0.5, "X": 0.5}, stratum="privative")
    # merge into one truth/choices to prove aggregate() filters by stratum
    truth.update(tp)
    for j in choices:
        choices[j].update(cp[j])
    agg_p, _f, _n = S.aggregate(choices, kept, truth, "primary")
    agg_v, _f2, _n2 = S.aggregate(choices, kept, truth, "privative")
    _check("primary items only primary words", all(agg_p[c]["n_items"] > 0 for c in B.CO_PRIMARIES))
    _check("privative aggregated separately", all(agg_v[c]["n_items"] > 0 for c in B.CO_PRIMARIES))
    perp = S.score_stratum(agg_p)
    _check("primary verdict beats-all", B.apply_verdict({c: perp[c] for c in B.CO_PRIMARIES})
           == "LIMITED_GENERATION_UTILITY")


def test_no_model_imported():
    _check("no torch/transformers imported by scorer",
           not any(m in sys.modules for m in ("torch", "transformers", "vllm")))


def main():
    print("test_b1_score — scorer tests (synthetic, no model, no real files)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll B1 scorer tests passed (frozen stats reused; verdict branches verified).")


if __name__ == "__main__":
    main()
