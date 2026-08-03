#!/usr/bin/env python3
"""Apply the pre-registered five-seed gates to a results file -> classification + readiness.

Pure stdlib. Reports every seed; never averages away a failed causal seed. Emits the final
classification, the readiness decision, and a per-gate pass/fail record.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics as st

CHANCE = 0.02
FORM_MIN = 0.075
FORM_MARGIN = 0.050
STAB_MEAN = 0.080
STAB_MEDIAN = 0.050


def d(rec, dist):
    return rec["needle_by_dist"][str(dist)]


def classify(res):
    arms = res["arms"]
    seeds = [r["seed"] for r in arms["S"]]
    byseed = {}
    for i, seed in enumerate(seeds):
        A, Ap, S = arms["A"][i], arms["A+"][i], arms["S"][i]
        byseed[seed] = {"A": A, "A+": Ap, "S": S}

    # parameter match
    param_match = all(abs(arms["S"][i]["params"] - arms["A+"][i]["params"]) / arms["S"][i]["params"] <= 0.0005
                      for i in range(len(seeds)))

    # forming
    forming = {}
    for seed in seeds:
        S, Ap = byseed[seed]["S"], byseed[seed]["A+"]
        s96, ap96 = d(S, 96), d(Ap, 96)
        forming[seed] = (s96 >= FORM_MIN) and (s96 - ap96 >= FORM_MARGIN) and (s96 >= CHANCE + FORM_MARGIN)
    n_form = sum(forming.values())

    s_minus_ap = {seed: d(byseed[seed]["S"], 96) - d(byseed[seed]["A+"], 96) for seed in seeds}
    diffs = list(s_minus_ap.values())
    win = sum(1 for seed in seeds if d(byseed[seed]["S"], 96) > d(byseed[seed]["A+"], 96))
    stability = (n_form >= 4 and st.mean(diffs) >= STAB_MEAN and
                 st.median(diffs) >= STAB_MEDIAN and win >= 4)

    # causal gate on every FORMING seed
    causal_by_seed = {}
    for seed in seeds:
        if not forming[seed]:
            continue
        S, Ap = byseed[seed]["S"], byseed[seed]["A+"]
        ab = S.get("ablation", {})
        base = ab.get("baseline", d(S, 96))
        ap96 = d(Ap, 96)
        gain = base - ap96
        thr = max(ap96 + 0.030, 0.050)
        ok = True
        for k in ("slots_off", "randomized_address"):
            v = ab.get(k)
            if v is None:
                ok = False; break
            drop_abs = base - v
            cut = (base - v) >= 0.5 * gain if gain > 0 else True
            ok = ok and (drop_abs >= 0.050) and cut and (v <= thr)
        causal_by_seed[seed] = ok
    causal_gate = all(causal_by_seed.get(seed, False) for seed in seeds if forming[seed]) and n_form >= 1

    # PPL quality gate
    s256 = [byseed[seed]["S"]["ppl"]["256"] for seed in seeds]
    ap256 = [byseed[seed]["A+"]["ppl"]["256"] for seed in seeds]
    ppl_mean_ok = st.mean(s256) <= 1.20 * st.mean(ap256)
    ppl_seed_exceed = sum(1 for i in range(len(seeds)) if s256[i] > 1.25 * ap256[i])
    ppl_gate = ppl_mean_ok and ppl_seed_exceed <= 2

    # parameter-control: S beats A+
    param_control = st.mean(diffs) > 0 and win >= (len(seeds) // 2 + 1)

    # context distance
    d16_ok = all(d(byseed[seed]["S"], 16) >= d(byseed[seed]["A+"], 16) - 0.050 for seed in seeds)
    d220_forming_positive = sum(1 for seed in seeds if forming[seed]
                                and d(byseed[seed]["S"], 220) - d(byseed[seed]["A+"], 220) > 0)
    d220_ok = d220_forming_positive >= 3

    # relational EMERGING (non-gate)
    def relational(metric_fn):
        s = [metric_fn(byseed[seed]["S"]) for seed in seeds]
        ap = [metric_fn(byseed[seed]["A+"]) for seed in seeds]
        above = sum(1 for x in s if x > CHANCE + 0.02)
        emerging = above >= 4 and (st.mean(s) - st.mean(ap)) >= 0.050
        return {"S_mean": round(st.mean(s), 4), "above_chance_seeds": above,
                "label": "EMERGING" if emerging else "AT_CHANCE"}
    relational_summary = {
        "binding_k2": relational(lambda r: r["binding_by_k"]["2"]),
        "supersession": relational(lambda r: r["supersession"]["current_acc"]),
        "source": relational(lambda r: r["source"]),
        "multihop": relational(lambda r: r["multihop"]),
    }

    # final classification
    if not param_control:
        final = "PARAMETER_BUDGET_EXPLAINS_GAIN"
    elif n_form >= 1 and not causal_gate:
        final = "NOT_CAUSALLY_ATTRIBUTED"
    elif n_form < 3:
        final = "UNSTABLE"
    elif stability and causal_gate:
        final = "FIVE_SEED_STABLE" if ppl_gate else "STABLE_RETRIEVAL_WITH_QUALITY_REGRESSION"
    else:
        final = "PARTIALLY_STABLE"

    ready = "READY_FOR_KDA_VALIDATION" if final in (
        "FIVE_SEED_STABLE", "STABLE_RETRIEVAL_WITH_QUALITY_REGRESSION") else "NOT_READY_FOR_KDA_VALIDATION"

    return {
        "holdout_seeds": seeds,
        "param_match_ok": param_match,
        "needle_d96": {seed: {"A": d(byseed[seed]["A"], 96), "A+": d(byseed[seed]["A+"], 96),
                              "S": d(byseed[seed]["S"], 96)} for seed in seeds},
        "S_minus_Aplus_d96": {seed: round(s_minus_ap[seed], 4) for seed in seeds},
        "forming": forming, "n_forming": n_form,
        "mean_S_minus_Aplus": round(st.mean(diffs), 4), "median_S_minus_Aplus": round(st.median(diffs), 4),
        "win_count_S_gt_Aplus": win,
        "stability_gate": stability,
        "causal_by_seed": causal_by_seed, "causal_gate": causal_gate,
        "ppl_gate": ppl_gate, "ppl_mean_S256": round(st.mean(s256), 2), "ppl_mean_Aplus256": round(st.mean(ap256), 2),
        "param_control_gate": param_control,
        "context_distance": {"d16_ok": d16_ok, "d220_forming_positive": d220_forming_positive, "d220_ok": d220_ok},
        "relational": relational_summary,
        "final_classification": final,
        "readiness": ready,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    p = pathlib.Path(args.results)
    if not p.exists():
        print(f"NOT_YET_RUN: {p} missing")
        return 0
    out = classify(json.loads(p.read_text()))
    print(json.dumps(out, indent=2))
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
