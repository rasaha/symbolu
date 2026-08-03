#!/usr/bin/env python3
"""Stage B fresh-holdout classifier -> final classification + readiness.

Applies the pre-registered Stage B gates (b1..b11) to the selected candidate vs A+ and B0 on the
five FRESH seeds (8,9,10,11,12). Enforces the mandatory >=4/5 formation gate: a higher mean with
<4/5 formed DOES NOT pass. Pure stdlib.
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
FRESH_SEEDS = [8, 9, 10, 11, 12]


def d(rec, dist):
    return rec["needle_by_dist"][str(dist)]


def forming(S, Ap):
    s96, ap96 = d(S, 96), d(Ap, 96)
    return (s96 >= FORM_MIN) and (s96 - ap96 >= FORM_MARGIN) and (s96 >= CHANCE + FORM_MARGIN)


def formation_count(byseed_S, byseed_Ap):
    return sum(forming(byseed_S[s], byseed_Ap[s]) for s in FRESH_SEEDS)


def causal_ok(S, Ap):
    ab = S.get("ablation", {})
    base = ab.get("baseline", d(S, 96))
    ap96 = d(Ap, 96)
    gain = base - ap96
    thr = max(ap96 + 0.030, 0.050)
    for k in ("slots_off", "randomized_address"):
        v = ab.get(k)
        if v is None:
            return False
        drop_abs = base - v
        cut = (drop_abs >= 0.5 * gain) if gain > 0 else True
        if not ((drop_abs >= 0.050) and cut and (v <= thr)):
            return False
    return True


def load(results_dir, arm):
    p = pathlib.Path(results_dir) / f"{arm}_results.json"
    if not p.exists():
        return None
    return {r["seed"]: r for r in json.loads(p.read_text())["records"]}


def classify(cand, aplus, b0, candidate_name):
    seeds = FRESH_SEEDS
    forms = {s: forming(cand[s], aplus[s]) for s in seeds}
    n_form = sum(forms.values())
    margins = {s: d(cand[s], 96) - d(aplus[s], 96) for s in seeds}
    diffs = list(margins.values())
    win = sum(1 for s in seeds if d(cand[s], 96) > d(aplus[s], 96))
    b0_form = formation_count(b0, aplus)

    causal = {s: causal_ok(cand[s], aplus[s]) for s in seeds if forms[s]}
    causal_gate = all(causal.get(s, False) for s in seeds if forms[s]) and n_form >= 1

    s256 = [cand[s]["ppl"]["256"] for s in seeds]
    ap256 = [aplus[s]["ppl"]["256"] for s in seeds]
    ppl_mean_ok = st.mean(s256) <= 1.20 * st.mean(ap256)
    ppl_exceed = sum(1 for i in range(len(seeds)) if s256[i] > 1.25 * ap256[i])
    ppl_gate = ppl_mean_ok and ppl_exceed <= 2

    param_ok = all(abs(cand[s]["params"] - aplus[s]["params"]) / cand[s]["params"] <= 0.0005 for s in seeds)
    d16_ok = all(d(cand[s], 16) >= d(aplus[s], 16) - 0.050 for s in seeds)
    d220_pos = sum(1 for s in seeds if forms[s] and d(cand[s], 220) - d(aplus[s], 220) > 0)
    d220_ok = d220_pos >= 3

    b1 = n_form >= 4
    b2 = st.mean(diffs) >= STAB_MEAN
    b3 = st.median(diffs) >= STAB_MEDIAN
    b4 = win >= 4
    b5 = n_form > b0_form
    b6 = param_ok
    b7 = ppl_gate
    b8 = causal_gate
    b9 = d16_ok and d220_ok
    gates = {"b1_form_ge4": b1, "b2_mean_margin": b2, "b3_median_margin": b3, "b4_win_ge4": b4,
             "b5_beats_b0_formation": b5, "b6_param_match": b6, "b7_ppl": b7, "b8_causal": b8,
             "b9_distance": b9}
    all_pass = all(gates.values())

    if all_pass:
        final = "PROVISIONALLY_STABILIZED"
    elif not b1:
        final = "FRESH_HOLDOUT_UNSTABLE"
    else:
        final = "FRESH_HOLDOUT_UNSTABLE"
    readiness = "NOT_READY_FOR_KDA_VALIDATION"

    return {
        "stage": "B",
        "candidate": candidate_name,
        "fresh_seeds": seeds,
        "needle_d96": {str(s): {"cand": d(cand[s], 96), "A+": d(aplus[s], 96), "B0": d(b0[s], 96)} for s in seeds},
        "forming": {str(s): forms[s] for s in seeds},
        "candidate_formation_count": n_form,
        "b0_formation_count": b0_form,
        "S_minus_Aplus_d96": {str(s): round(margins[s], 4) for s in seeds},
        "mean_margin": round(st.mean(diffs), 4), "median_margin": round(st.median(diffs), 4),
        "win_count": win,
        "ppl_mean_cand256": round(st.mean(s256), 2), "ppl_mean_Aplus256": round(st.mean(ap256), 2),
        "causal_by_forming_seed": {str(s): causal.get(s) for s in seeds if forms[s]},
        "distance": {"d16_ok": d16_ok, "d220_forming_positive": d220_pos, "d220_ok": d220_ok},
        "gates": gates, "all_gates_pass": all_pass,
        "final_classification": final,
        "readiness": readiness,
        "readiness_note": "Even under PROVISIONALLY_STABILIZED the readiness is NOT_READY_FOR_KDA_VALIDATION (intervention selected over multiple candidates). Next gate: one independent confirmatory five-seed replication of the frozen winning intervention, no further tuning.",
        "mandatory_gate_note": "A higher mean with <4/5 formed does NOT pass (b1 is mandatory).",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--candidate", required=True, help="candidate arm id, e.g. O1")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cand = load(args.results_dir, args.candidate)
    aplus = load(args.results_dir, "A+")
    b0 = load(args.results_dir, "B0")
    missing = [n for n, v in [("candidate", cand), ("A+", aplus), ("B0", b0)] if v is None]
    if missing or any(s not in (cand or {}) for s in FRESH_SEEDS):
        out = {"stage": "B", "final_classification": "INTERVENTION_RESCUES_KNOWN_FAILURES_ONLY",
               "readiness": "NOT_READY_FOR_KDA_VALIDATION",
               "reason": f"Stage B incomplete/missing arms: {missing or 'partial seeds'}"}
        print(json.dumps(out, indent=2))
        if args.out:
            pathlib.Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
        return 0
    out = classify(cand, aplus, b0, args.candidate)
    print(json.dumps(out, indent=2))
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
