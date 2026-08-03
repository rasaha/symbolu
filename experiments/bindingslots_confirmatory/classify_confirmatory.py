#!/usr/bin/env python3
"""Mechanical confirmatory classifier for the BindingSlots frozen-CR1 replication.

Reuses the FROZEN Stage B per-seed rules (`forming`, `causal_ok`, `d`) imported directly from the
merged classify_stage_b.py (sha256 pinned in classifier.json) so no threshold can drift. Only the
fresh-seed set (13-17) and the final confirmatory verdict mapping are new. Pure stdlib.

Emits exactly one primary verdict from:
  REPLICATED_SLOT_FORMATION_STABILIZATION | CONFIRMATORY_REPLICATION_FAILED |
  CONFIRMATORY_PROTOCOL_VIOLATED | CONFIRMATORY_INTEGRITY_FAILED |
  CONFIRMATORY_ENVIRONMENT_MISMATCH | CONFIRMATORY_RESOURCE_BLOCKED
plus a separate KDA readiness state.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics as st
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
sys.path.insert(0, str(SBS))
sys.path.insert(0, str(HERE))

import classify_stage_b as FROZEN  # noqa: E402  (frozen per-seed rules)
import retention as RET  # noqa: E402

CONF_SEEDS = [13, 14, 15, 16, 17]


def load(results_dir, arm):
    p = pathlib.Path(results_dir) / f"{arm}_results.json"
    if not p.exists():
        return None
    return {r["seed"]: r for r in json.loads(p.read_text())["records"]}


def classify(cand, aplus, b0, integrity_ok=True, protocol_deviations=None):
    seeds = CONF_SEEDS
    protocol_deviations = protocol_deviations or []

    forms = {s: FROZEN.forming(cand[s], aplus[s]) for s in seeds}
    n_form = sum(forms.values())
    margins = {s: FROZEN.d(cand[s], 96) - FROZEN.d(aplus[s], 96) for s in seeds}
    diffs = list(margins.values())
    win = sum(1 for s in seeds if FROZEN.d(cand[s], 96) > FROZEN.d(aplus[s], 96))
    b0_form = sum(FROZEN.forming(b0[s], aplus[s]) for s in seeds)
    aplus_form = sum(FROZEN.forming(aplus[s], aplus[s]) for s in seeds)  # A+ vs itself margin 0 -> 0

    # causal per forming seed (slots_off AND randomized_address), never averaged
    causal = {s: FROZEN.causal_ok(cand[s], aplus[s]) for s in seeds if forms[s]}
    slots_off_ok = {}
    rand_addr_ok = {}
    for s in seeds:
        if not forms[s]:
            continue
        ab = cand[s].get("ablation", {})
        base = ab.get("baseline", FROZEN.d(cand[s], 96))
        ap96 = FROZEN.d(aplus[s], 96)
        gain = base - ap96
        thr = max(ap96 + 0.030, 0.050)
        for key, store in (("slots_off", slots_off_ok), ("randomized_address", rand_addr_ok)):
            v = ab.get(key)
            if v is None:
                store[s] = False
            else:
                drop = base - v
                cut = (drop >= 0.5 * gain) if gain > 0 else True
                store[s] = (drop >= 0.050) and cut and (v <= thr)

    s256 = [cand[s]["ppl"]["256"] for s in seeds]
    ap256 = [aplus[s]["ppl"]["256"] for s in seeds]
    ppl_mean_ok = st.mean(s256) <= 1.20 * st.mean(ap256)
    ppl_exceed = sum(1 for i in range(len(seeds)) if s256[i] > 1.25 * ap256[i])
    ppl_gate = ppl_mean_ok and ppl_exceed <= 2

    param_ok = all(abs(cand[s]["params"] - aplus[s]["params"]) / cand[s]["params"] <= 0.0005 for s in seeds)
    d16_ok = all(FROZEN.d(cand[s], 16) >= FROZEN.d(aplus[s], 16) - 0.050 for s in seeds)
    d220_pos = sum(1 for s in seeds if forms[s] and FROZEN.d(cand[s], 220) - FROZEN.d(aplus[s], 220) > 0)
    d220_ok = d220_pos >= 3

    # confirmatory gates C1..C11
    C1 = n_form >= 4
    C2 = n_form > b0_form
    C3 = win >= 4
    C4 = st.mean(diffs) >= FROZEN.STAB_MEAN
    C5 = st.median(diffs) >= FROZEN.STAB_MEDIAN
    C6 = ppl_gate
    C7 = d16_ok and d220_ok
    C8 = all(slots_off_ok.get(s, False) for s in seeds if forms[s]) and n_form >= 1
    C9 = all(rand_addr_ok.get(s, False) for s in seeds if forms[s]) and n_form >= 1
    C10 = bool(integrity_ok) and param_ok
    C11 = len(protocol_deviations) == 0

    gates = {"C1_form_ge4": C1, "C2_form_gt_B0": C2, "C3_win_ge4": C3, "C4_mean_margin": C4,
             "C5_median_margin": C5, "C6_quality": C6, "C7_distance": C7,
             "C8_slots_off": C8, "C9_randomized_address": C9,
             "C10_integrity_param": C10, "C11_no_deviation": C11}

    scientific = [C1, C2, C3, C4, C5, C6, C7, C8, C9]
    all_pass = all(gates.values())

    if not C11:
        verdict = "CONFIRMATORY_PROTOCOL_VIOLATED"
    elif not C10:
        verdict = "CONFIRMATORY_INTEGRITY_FAILED"
    elif all_pass:
        verdict = "REPLICATED_SLOT_FORMATION_STABILIZATION"
    else:
        verdict = "CONFIRMATORY_REPLICATION_FAILED"

    if verdict == "REPLICATED_SLOT_FORMATION_STABILIZATION":
        slot_status = "SLOT_FORMATION_REPLICATED"
        readiness = "ELIGIBLE_FOR_NEXT_VALIDATION_LADDER"
    elif verdict == "CONFIRMATORY_REPLICATION_FAILED":
        slot_status = "SLOT_FORMATION_NOT_REPLICATED"
        readiness = "KDA_VALIDATION_BLOCKED"
    else:
        slot_status = "UNDETERMINED"
        readiness = "KDA_VALIDATION_BLOCKED"

    retention = {}
    for s in seeds:
        series = RET.trajectory_d96(cand[s])
        retention[str(s)] = RET.classify(series, forms[s])

    return {
        "schema": "bindingslots_confirmatory/aggregate_result/v1",
        "candidate": "CR1",
        "fresh_seeds": seeds,
        "needle_d96": {str(s): {"CR1": FROZEN.d(cand[s], 96), "A+": FROZEN.d(aplus[s], 96),
                                "B0": FROZEN.d(b0[s], 96)} for s in seeds},
        "forming": {str(s): forms[s] for s in seeds},
        "cr1_formation_count": n_form,
        "b0_formation_count": b0_form,
        "aplus_formation_count": aplus_form,
        "S_minus_Aplus_d96": {str(s): round(margins[s], 4) for s in seeds},
        "mean_margin": round(st.mean(diffs), 4),
        "median_margin": round(st.median(diffs), 4),
        "win_count": win,
        "causal_by_forming_seed": {str(s): {"combined": causal.get(s),
                                            "slots_off": slots_off_ok.get(s),
                                            "randomized_address": rand_addr_ok.get(s)}
                                   for s in seeds if forms[s]},
        "quality": {"ppl_mean_cand256": round(st.mean(s256), 2),
                    "ppl_mean_Aplus256": round(st.mean(ap256), 2),
                    "n_exceed_25pct": ppl_exceed, "pass": ppl_gate},
        "distance": {"d16_ok": d16_ok, "d220_forming_positive": d220_pos, "d220_ok": d220_ok},
        "retention_by_seed": retention,
        "gates": gates,
        "all_gates_pass": all_pass,
        "scientific_gates_pass": all(scientific),
        "primary_verdict": verdict,
        "slot_formation_status": slot_status,
        "kda_readiness": readiness,
        "protocol_deviations": protocol_deviations,
        "notes": [
            "3/5 is NOT 'nearly replicated'.",
            "One causally-unclean forming seed fails the whole replication; causal results never averaged.",
            "No best-checkpoint selection; classifier uses only the step-1200 evaluation.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--integrity-ok", type=int, default=1)
    ap.add_argument("--deviations", default="")
    args = ap.parse_args()

    cand = load(args.results_dir, "CR1")
    aplus = load(args.results_dir, "A+")
    b0 = load(args.results_dir, "B0")
    missing = [n for n, v in [("CR1", cand), ("A+", aplus), ("B0", b0)] if v is None]
    incomplete = missing or any(any(s not in (v or {}) for s in CONF_SEEDS) for v in (cand, aplus, b0))
    if incomplete:
        out = {"schema": "bindingslots_confirmatory/aggregate_result/v1",
               "primary_verdict": "CONFIRMATORY_RESOURCE_BLOCKED",
               "slot_formation_status": "UNDETERMINED",
               "kda_readiness": "KDA_VALIDATION_BLOCKED",
               "reason": f"incomplete results: missing arms {missing or 'partial seeds'}; "
                         f"training did not complete for all 3 arms x seeds {CONF_SEEDS}."}
        print(json.dumps(out, indent=2))
        if args.out:
            pathlib.Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
        return 0
    devs = [d for d in args.deviations.split(";") if d.strip()]
    out = classify(cand, aplus, b0, integrity_ok=bool(args.integrity_ok), protocol_deviations=devs)
    print(json.dumps(out, indent=2))
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
