"""Tests for the B1 DRY-RUN / MOCK harness — proves NO real model call, NO real scoring, NO files.

Verifies: dry-run never calls a real model (and refuses a real adapter); full 3,600-row expansion
(2,880 primary + 720 privative); judge packets hide arm labels / conditioning / model / seed / the
internal packet id; randomization is deterministic from seed; the aggregator produces the five
co-primary A-vs-D/R/S/C/X comparisons; the clustered bootstrap is deterministic; Holm-Bonferroni is
correct; every verdict label (kill + the single positive) applies correctly; no ML libs; no files.

    python3 experiments/primitive_sequence_recovery/test_b1_dry_run_harness.py
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import b1_dry_run_harness as B   # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


# ---------------------------------------------------------------- no real model -------------------
def test_no_real_model_call():
    rows = B.expand_rows()[:12]
    mock = B.MockModelAdapter()
    outs = B.run_generation(rows, mock, dry_run=True)
    _check("mock adapter is not real", mock.is_real is False)
    _check("mock produced one output per row", len(outs) == len(rows))
    _check("mock call_count == rows", mock.call_count == len(rows))
    _check("all outputs marked mock", all(o.mock for o in outs))
    _check("no output text looks like a real completion",
           all(o.output_text.startswith("MOCK_DRY_RUN_OUTPUT") for o in outs))
    # a real adapter must be refused, and its generate() must raise
    real = B.RealModelAdapter()
    try:
        B.run_generation(rows, real, dry_run=True)
        _check("real adapter refused by runner", False)
    except RuntimeError:
        _check("real adapter refused by runner", True)
    try:
        real.generate("x", B.DECODE, 1)
        _check("RealModelAdapter.generate raises", False)
    except RuntimeError:
        _check("RealModelAdapter.generate raises", True)


def test_full_expansion_counts():
    rows = B.expand_rows()
    prim = sum(1 for r in rows if r.stratum == "primary")
    priv = sum(1 for r in rows if r.stratum == "privative")
    _check("primary rows == 20*6*6*2*2 == 2880", prim == 2880)
    _check("privative rows == 5*6*6*2*2 == 720", priv == 720)
    _check("total rows == 3600", len(rows) == 3600)
    _check("row ids unique", len({r.row_id for r in rows}) == 3600)


# ---------------------------------------------------------------- blinding ------------------------
def _small_packets(a_win_prob=0.5):
    rows = [r for r in B.expand_rows() if r.key_word in ("grief", "amoral")]
    outs = B.run_generation(rows, B.MockModelAdapter(), dry_run=True)
    packets = B.build_judge_packets(outs, rand_seed=40411)
    return outs, packets


def test_judge_packets_hide_arm_labels():
    _outs, packets = _small_packets()
    for p in packets:
        view = json.dumps(B.judge_view(p))
        # no arm code / comparison label / self-label in what the judge sees
        for bad in ("A_vs_", "control", "arm ", '"A"', '"R"', '"S"', '"C"', '"X"', '"D"'):
            _check(f"judge view hides {bad!r}", bad not in view)
        _check("judge view has no internal packet_id", p.packet_id not in view)
        _check("judge view uses neutral display id", p.display_id in view)
        # outputs are neutrally labelled
        ids = [o["id"] for o in B.judge_view(p)["outputs"]]
        _check("neutral output ids only", ids == ["Output 1", "Output 2"])


def test_judge_packets_hide_conditioning_model_seed():
    _outs, packets = _small_packets()
    for p in packets:
        view = json.dumps(B.judge_view(p))
        _check("judge view hides conditioning marker", "MOCK " not in view and "conditioning" not in view)
        _check("judge view hides model id", "MOCK_MODEL" not in view)
        for seed in B.SEEDS:
            _check(f"judge view hides seed {seed}", str(seed) not in view)
        _check("judge view has no truth map", "truth" not in view)


def test_randomization_deterministic_from_seed():
    outs = B.run_generation([r for r in B.expand_rows() if r.key_word == "grief"],
                            B.MockModelAdapter(), dry_run=True)
    p1 = B.build_judge_packets(outs, rand_seed=999)
    p2 = B.build_judge_packets(outs, rand_seed=999)
    sig = lambda ps: [(p.packet_id, tuple(p.truth[o["id"]] for o in p.outputs)) for p in ps]
    _check("same seed -> identical packet order + left/right assignment", sig(p1) == sig(p2))
    p3 = B.build_judge_packets(outs, rand_seed=1000)
    _check("different seed -> at least one different left/right assignment", sig(p1) != sig(p3))


# ---------------------------------------------------------------- scoring -------------------------
def test_aggregate_computes_five_coprimaries():
    outs = B.run_generation([r for r in B.expand_rows() if r.key_word in ("grief", "river", "ocean")],
                            B.MockModelAdapter(), dry_run=True)
    packets = B.build_judge_packets(outs, rand_seed=1)
    resp = B.mock_judge(packets, rand_seed=2, a_win_prob=0.5)
    agg = B.aggregate_pairwise(packets, resp)
    _check("aggregate has exactly the five co-primaries", set(agg) == set(B.CO_PRIMARIES))
    for c in B.CO_PRIMARIES:
        _check(f"A_vs_{c} has item scores", agg[c]["n_items"] > 0)
        _check(f"A_vs_{c} win_rate in [0,1]", 0.0 <= agg[c]["win_rate"] <= 1.0)


def test_a_always_wins_and_loses_scores():
    outs = B.run_generation([r for r in B.expand_rows() if r.key_word in ("grief", "river")],
                            B.MockModelAdapter(), dry_run=True)
    packets = B.build_judge_packets(outs, rand_seed=1)
    win = B.aggregate_pairwise(packets, B.mock_judge(packets, 2, a_win_prob=1.0))
    lose = B.aggregate_pairwise(packets, B.mock_judge(packets, 2, a_win_prob=0.0))
    _check("A always chosen -> win_rate 1.0 for all controls",
           all(win[c]["win_rate"] == 1.0 for c in B.CO_PRIMARIES))
    _check("A never chosen -> win_rate 0.0 for all controls",
           all(lose[c]["win_rate"] == 0.0 for c in B.CO_PRIMARIES))


def test_clustered_bootstrap_deterministic():
    scores = [0.6, 0.7, 0.55, 0.8, 0.65, 0.5, 0.9, 0.6]
    a = B.clustered_bootstrap_ci(scores, n_boot=500, seed=7)
    b = B.clustered_bootstrap_ci(scores, n_boot=500, seed=7)
    _check("same seed -> identical CI (deterministic)", a == b)
    mean, lo, hi, p = a
    _check("CI ordered lo<=mean<=hi", lo <= mean <= hi)
    _check("p in [0,1]", 0.0 <= p <= 1.0)


def test_holm_bonferroni():
    # classic Holm example
    res = B.holm_bonferroni({"a": 0.01, "b": 0.04, "c": 0.03}, alpha=0.05)
    _check("smallest p adjusted by m=3", abs(res["a"][0] - 0.03) < 1e-9 and res["a"][1] is True)
    _check("monotone non-decreasing adjusted p", res["a"][0] <= res["b"][0] and res["c"][0] <= res["b"][0])
    all_small = B.holm_bonferroni({"a": 0.001, "b": 0.002}, alpha=0.05)
    _check("all tiny p -> all reject", all(v[1] for v in all_small.values()))
    none = B.holm_bonferroni({"a": 0.9, "b": 0.8}, alpha=0.05)
    _check("all large p -> none reject", not any(v[1] for v in none.values()))


# ---------------------------------------------------------------- verdict labels ------------------
def _beat(c):
    return {"ci_lo": 0.60, "holm_reject": True}


def _miss(c):
    return {"ci_lo": 0.50, "holm_reject": False}


def test_kill_and_positive_labels_apply():
    beats_all = {c: _beat(c) for c in B.CO_PRIMARIES}
    _check("beats all five -> LIMITED_GENERATION_UTILITY",
           B.apply_verdict(beats_all) == "LIMITED_GENERATION_UTILITY")

    d = dict(beats_all); d["D"] = _miss("D")
    _check("fails D -> DICTIONARY_DOMINATES", B.apply_verdict(d) == "DICTIONARY_DOMINATES")

    r = dict(beats_all); r["R"] = _miss("R")
    _check("fails R -> RANDOM_OR_SCRAMBLED_MATCHES", B.apply_verdict(r) == "RANDOM_OR_SCRAMBLED_MATCHES")
    s = dict(beats_all); s["S"] = _miss("S")
    _check("fails S -> RANDOM_OR_SCRAMBLED_MATCHES", B.apply_verdict(s) == "RANDOM_OR_SCRAMBLED_MATCHES")

    cc = dict(beats_all); cc["C"] = _miss("C")
    _check("fails C -> SURFACE_STRUCTURE_EXPLAINS", B.apply_verdict(cc) == "SURFACE_STRUCTURE_EXPLAINS")

    none = {c: _miss(c) for c in B.CO_PRIMARIES}
    _check("beats nothing -> NO_SIGNAL", B.apply_verdict(none) == "NO_SIGNAL")
    only_x = {c: _miss(c) for c in B.CO_PRIMARIES}; only_x["X"] = _beat("X")
    _check("beats only X -> NO_SIGNAL", B.apply_verdict(only_x) == "NO_SIGNAL")

    # flags take precedence
    _check("invalid posthoc flag -> INVALID_POSTHOC",
           B.apply_verdict(beats_all, {"invalid_posthoc": True}) == "INVALID_POSTHOC")
    _check("leakage flag -> LEAKAGE_FAIL",
           B.apply_verdict(beats_all, {"leakage_fail": True}) == "LEAKAGE_FAIL")
    _check("correctness flag -> CORRECTNESS_DEGRADED",
           B.apply_verdict(beats_all, {"correctness_degraded": True}) == "CORRECTNESS_DEGRADED")
    _check("robustness flag -> NOT_ROBUST",
           B.apply_verdict(beats_all, {"not_robust": True}) == "NOT_ROBUST")


def test_end_to_end_dry_run_directions():
    lose = B.dry_run(a_win_prob=0.0, n_boot=200, verbose=False)
    win = B.dry_run(a_win_prob=1.0, n_boot=200, verbose=False)
    _check("dry-run expands 3600 rows", lose["rows"] == 3600 and win["rows"] == 3600)
    _check("dry-run does 3600 mock generations", lose["mock_generations"] == 3600)
    _check("dry-run leak-clean", lose["leak_hits"] == 0 and win["leak_hits"] == 0)
    _check("dry-run builds 3000 judge packets", lose["judge_packets"] == 3000)
    _check("A always loses -> a kill label",
           lose["verdict_MOCK"] in ("NO_SIGNAL", "DICTIONARY_DOMINATES"))
    _check("A always wins -> LIMITED_GENERATION_UTILITY (mock)",
           win["verdict_MOCK"] == "LIMITED_GENERATION_UTILITY")
    _check("no real model called", lose["no_real_model_called"] and win["no_real_model_called"])
    _check("no files written", lose["no_files_written"] and win["no_files_written"])


# ---------------------------------------------------------------- leak scanner --------------------
def test_leak_scanner_flags_and_clean():
    _check("clean mock output has no leak", B.leak_scan("MOCK_DRY_RUN_OUTPUT #1 | fine") == [])
    _check("ontology phrase flagged", "ontology" in B.leak_scan("this proves the ontology of sound"))
    _check("rescue word flagged", "rescue" in B.leak_scan("a Track G rescue and rescue"))


# ---------------------------------------------------------------- hygiene -------------------------
def test_no_ml_libs_and_no_files():
    _check("no torch/transformers/openai/anthropic imported",
           not any(m in sys.modules for m in ("torch", "transformers", "openai", "anthropic")))
    before = {p.name for p in HERE.iterdir()}
    B.dry_run(a_win_prob=0.5, n_boot=100, verbose=False)
    _check("dry_run writes no files", {p.name for p in HERE.iterdir()} == before)


def main():
    print("b1_dry_run_harness — MOCK-ONLY pipeline tests (no real model, no real scoring, no files)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll B1 dry-run harness tests passed.")


if __name__ == "__main__":
    main()
