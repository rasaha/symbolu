#!/usr/bin/env python3
"""B1 read-only diagnostic — per-task / per-arm generation-improvement breakdown.

EXPLORATORY, POST-VERDICT. Does NOT change the pre-registered verdict
(RANDOM_OR_SCRAMBLED_MATCHES), does NOT modify any artifact/judge file, does NOT re-judge, does NOT
unblock Track B, and CANNOT claim LIMITED_GENERATION_UTILITY.

Design fact: judges compared **A vs each control** only. There are NO R-vs-X (control-vs-control)
packets, so R_vs_X cannot be measured directly. It is reported as an INFERENCE from A vs R.

Reports, per task T1-T6, primary and privative separately:
  * A vs X, A vs R, A vs D, A vs S, A vs C  (measured, item-clustered win-rate + CI)
  * whether any task shows A uniquely beating R
  * T4 correctness-flag rates per arm
  * inferred R-vs-X lift (from A~=R)

    python3 experiments/primitive_sequence_recovery/run_b1_diagnostic.py
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import b1_dry_run_harness as B     # noqa: E402  frozen stats
import run_b1_score as S           # noqa: E402  reuse load_judges/load_truth/a_win

CONTROLS = ("X", "C", "D", "S", "R")   # order for the table (weak -> strong confound)


def per_task(choices, kept, truth, stratum):
    """{task: {control: (win_rate, ci_lo, ci_hi, n_items)}} — item-clustered by key_word within task."""
    tasks = sorted({m["task"] for m in truth.values()})
    out = {}
    for task in tasks:
        out[task] = {}
        for c in B.CO_PRIMARIES:
            items = {}
            for did, meta in truth.items():
                if meta["stratum"] != stratum or meta["task"] != task or meta["control"] != c:
                    continue
                votes = [S.a_win(choices[j][did], meta["truth"]) for j in kept if did in choices[j]]
                if not votes:
                    continue
                items.setdefault(meta["key_word"], []).append(statistics.median(votes))
            scores = [statistics.mean(v) for v in items.values()]
            if scores:
                m, lo, hi, _p = B.clustered_bootstrap_ci(scores, n_boot=B.BOOTSTRAP["n_boot"],
                                                         seed=B.BOOTSTRAP["seed"])
                out[task][c] = (round(m, 3), round(lo, 3), round(hi, 3), len(scores))
            else:
                out[task][c] = None
    return out


def t4_correctness_by_arm(kept, truth):
    flags = {}
    for slug in kept:
        path = HERE / f"b1_judge_responses_{slug}_{S.JUDGE_TAG}.jsonl"
        for ln in path.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            if r.get("kind") == "real":
                flags.setdefault(r["display_id"], []).append(r.get("correctness_flag", "none"))
    a_prob = a_n = 0
    ctrl = {c: [0, 0] for c in B.CO_PRIMARIES}   # control -> [problem, total]
    for did, meta in truth.items():
        if meta["task"] != "T4":
            continue
        c = meta["control"]
        a_side = "Output 1" if meta["truth"].get("Output 1") == "A" else "Output 2"
        a_key = "output_1_problem" if a_side == "Output 1" else "output_2_problem"
        c_key = "output_2_problem" if a_side == "Output 1" else "output_1_problem"
        for f in flags.get(did, []):
            a_n += 1
            ctrl[c][1] += 1
            if f in (a_key, "both_problem"):
                a_prob += 1
            if f in (c_key, "both_problem"):
                ctrl[c][0] += 1
    return {"A": [a_prob, a_n], "controls": ctrl}


def _fmt(cell):
    if cell is None:
        return "   -   "
    m, lo, hi, _n = cell
    return f"{m:.2f}[{lo:.2f},{hi:.2f}]"


def report(choices, kept, truth, stratum):
    tab = per_task(choices, kept, truth, stratum)
    print(f"\n===== {stratum.upper()} stratum — A-win rate vs each control, by task =====")
    print(f"{'task':>5} | {'A_vs_X':>16} {'A_vs_C':>16} {'A_vs_D':>16} {'A_vs_S':>16} {'A_vs_R':>16}")
    uniq_R = []
    for task in sorted(tab):
        row = tab[task]
        print(f"{task:>5} | {_fmt(row['X']):>16} {_fmt(row['C']):>16} {_fmt(row['D']):>16} "
              f"{_fmt(row['S']):>16} {_fmt(row['R']):>16}")
        r = row.get("R")
        if r and r[1] > 0.5:            # A beats R on this task (CI lower bound > 0.5)
            uniq_R.append((task, r))
    return tab, uniq_R


def main():
    ok, bad = S.verify_frozen()
    print(f"[{'ok' if ok else 'FAIL'}] frozen integrity (read-only diagnostic; verdict UNCHANGED)")
    choices, kept, attn = S.load_judges()
    truth = S.load_truth()
    print(f"[ok] judges kept: {kept}")

    _tp, uniqP = report(choices, kept, truth, "primary")
    _tv, uniqV = report(choices, kept, truth, "privative")

    print("\n----- R vs X (NOT measured: no control-vs-control packets exist) -----")
    print("  The design judged A vs each control only. Since A ~= R overall "
          "(A_vs_R 0.514, CI straddles 0.5), R's lift over X is INFERRED to be ~equal to A's "
          "lift over X (A_vs_X 0.627). Not a measured value.")

    print("\n----- T4 correctness flags per arm (accuracy tradeoff) -----")
    t4 = t4_correctness_by_arm(kept, truth)
    ap, an = t4["A"]
    print(f"  A: {ap}/{an} T4 judgements flagged with a correctness problem "
          f"({100*ap/an:.1f}%)" if an else "  A: no T4 judgements")
    for c in B.CO_PRIMARIES:
        p, n = t4["controls"][c]
        print(f"  {c}: {p}/{n} ({100*p/n:.1f}%)" if n else f"  {c}: n/a")

    print("\n----- diagnostic read -----")
    print(f"  Tasks where A UNIQUELY beats R (CI_lo>0.5): "
          f"primary={[t for t,_ in uniqP] or 'NONE'} privative={[t for t,_ in uniqV] or 'NONE'}")
    print("  Conditioning improved generation vs neutral X on some tasks (esp. creative/reflective),")
    print("  but the improvement is NOT H2-specific: A ~= R overall, so random resonance produced")
    print("  similar gains. Where A shows a correctness cost on T4, the accuracy tradeoff is reported.")
    print("  This is exploratory; the pre-registered verdict RANDOM_OR_SCRAMBLED_MATCHES stands.")
    print("  Track B remains BLOCKED. Structure, not validated meaning.")


if __name__ == "__main__":
    main()
