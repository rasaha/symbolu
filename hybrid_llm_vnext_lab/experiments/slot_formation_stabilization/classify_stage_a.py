#!/usr/bin/env python3
"""Stage A scoring + candidate eligibility for the slot-formation-stabilization phase.

Applies the FROZEN formation rule (inherited from PR #1300) and the pre-registered arm-eligibility
criteria (e1..e8) to each intervention arm's diagnostic-seed results (seeds 3,6,7). A+ for the
diagnostic seeds is reused from the frozen five-seed artifacts (frozen_aplus_seeds_367.json).

Pure stdlib. Development-set only: selecting a candidate here is NOT a fresh holdout result.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics as st

HERE = pathlib.Path(__file__).resolve().parent
CHANCE = 0.02
FORM_MIN = 0.075
FORM_MARGIN = 0.050
DIAG_SEEDS = [3, 6, 7]
HIST_NONFORMERS = [3, 7]
HIST_MARGINAL = 6


def d(rec, dist):
    return rec["needle_by_dist"][str(dist)]


def load_arm(results_dir, arm):
    p = pathlib.Path(results_dir) / f"{arm}_results.json"
    if not p.exists():
        return None
    recs = json.loads(p.read_text())["records"]
    return {r["seed"]: r for r in recs}


def forming(S, Ap):
    s96, ap96 = d(S, 96), d(Ap, 96)
    return (s96 >= FORM_MIN) and (s96 - ap96 >= FORM_MARGIN) and (s96 >= CHANCE + FORM_MARGIN)


def causal_ok(S, Ap):
    """slots_off AND randomized_address each collapse the forming seed (frozen rule)."""
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


def score_arm(arm, byseed, aplus):
    seeds = DIAG_SEEDS
    forms = {}
    margins = {}
    causal = {}
    for s in seeds:
        S = byseed[s]; Ap = aplus[str(s)]
        forms[s] = forming(S, Ap)
        margins[s] = d(S, 96) - d(Ap, 96)
        if forms[s]:
            causal[s] = causal_ok(S, Ap)
    n_form = sum(forms.values())
    rescued = [s for s in HIST_NONFORMERS if forms[s]]
    seed6_formed = forms[HIST_MARGINAL]
    # PPL quality (mean over 3 seeds)
    s256 = [byseed[s]["ppl"]["256"] for s in seeds]
    ap256 = [aplus[str(s)]["ppl"]["256"] for s in seeds]
    ppl_ok = st.mean(s256) <= 1.20 * st.mean(ap256)
    # parameter match
    param_ok = all(abs(byseed[s]["params"] - aplus[str(s)]["params"]) / byseed[s]["params"] <= 0.0005
                   for s in seeds)
    causal_all_forming = all(causal.get(s, False) for s in seeds if forms[s]) and n_form >= 1
    # eligibility e1..e8 (e6 no-NxN and e8 no-Phase/KDA/MLA enforced structurally by tests/boundaries;
    # asserted True here and independently verified by the boundary test suite + complexity report)
    e1 = n_form >= 2
    e2 = len(rescued) >= 1
    e3 = seed6_formed or (len(rescued) == 2)
    e4 = ppl_ok
    e5 = causal_all_forming
    e6 = True
    e7 = param_ok
    e8 = True
    eligible = all([e1, e2, e3, e4, e5, e6, e7, e8])
    return {
        "arm": arm,
        "forming": {str(s): forms[s] for s in seeds},
        "n_forming": n_form,
        "rescued_nonformers": rescued,
        "seed6_formed": seed6_formed,
        "needle_d96": {str(s): {"S": d(byseed[s], 96), "A+": d(aplus[str(s)], 96)} for s in seeds},
        "S_minus_Aplus_d96": {str(s): round(margins[s], 4) for s in seeds},
        "min_margin": round(min(margins.values()), 4),
        "median_margin": round(st.median(list(margins.values())), 4),
        "mean_margin": round(st.mean(list(margins.values())), 4),
        "ppl_mean_S256": round(st.mean(s256), 2),
        "ppl_mean_Aplus256": round(st.mean(ap256), 2),
        "ppl_ok": ppl_ok,
        "param_ok": param_ok,
        "causal_by_forming_seed": {str(s): causal.get(s) for s in seeds if forms[s]},
        "causal_all_forming": causal_all_forming,
        "distance_d16": {str(s): {"S": d(byseed[s], 16), "A+": d(aplus[str(s)], 16)} for s in seeds},
        "distance_d220": {str(s): {"S": d(byseed[s], 220), "A+": d(aplus[str(s)], 220)} for s in seeds},
        "eligibility": {"e1_forms_ge2": e1, "e2_rescues_nonformer": e2,
                        "e3_seed6_ok": e3, "e4_ppl": e4, "e5_causal": e5,
                        "e6_no_nxn": e6, "e7_param_match": e7, "e8_no_phase_kda_mla": e8},
        "eligible": eligible,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True, help="dir with {arm}_results.json files")
    ap.add_argument("--aplus", default=str(HERE / "frozen_aplus_seeds_367.json"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    aplus = json.loads(pathlib.Path(args.aplus).read_text())
    arms = ["B0", "O1", "O2", "K1", "C1", "R1", "CR1"]
    scored = {}
    b0 = load_arm(args.results_dir, "B0")
    b0_repro = None
    if b0:
        b0_repro = {str(s): {"S_d96": d(b0[s], 96)} for s in DIAG_SEEDS if s in b0}
    for arm in arms:
        byseed = load_arm(args.results_dir, arm)
        if not byseed or any(s not in byseed for s in DIAG_SEEDS):
            scored[arm] = {"arm": arm, "status": "MISSING_OR_INCOMPLETE"}
            continue
        sc = score_arm(arm, byseed, aplus)
        if arm == "B0":
            sc["eligible"] = False
            sc["note"] = "control (frozen baseline) — not eligible for selection"
        scored[arm] = sc

    eligible = [a for a in arms if scored[a].get("eligible")]
    out = {
        "stage": "A",
        "diagnostic_seeds": DIAG_SEEDS,
        "development_set_disclaimer": "Stage A seeds 3,6,7 are a DEVELOPMENT set. Results here may select a candidate but are NOT a fresh holdout result.",
        "b0_reproduction": b0_repro,
        "b0_reproduction_targets_frozen_S": {"3": 0.0, "6": 0.075, "7": 0.0417},
        "per_arm": scored,
        "eligible_arms": eligible,
    }
    print(json.dumps(out, indent=2))
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
