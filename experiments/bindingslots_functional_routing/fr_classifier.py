#!/usr/bin/env python3
"""Stable functional-routing Stage-1 classifier + mechanical candidate selection.

Reuses the FROZEN Stage B per-seed formation + causal rules (imported from classify_stage_b.py) and
adds address-specific routing thresholds and retention checkpoints. Pure stdlib.

Per-seed state and the Stage-1 single-arm gate are computed mechanically; a winner is selected by the
frozen tie-break order. Stage 2 (development holdout) is deferred by this focused phase.
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
import classify_stage_b as FROZEN  # noqa: E402

CLS = json.loads((HERE / "stable_classifier.json").read_text())
SEEDS = CLS["stage1_seeds"]
RT = CLS["routing_metric_thresholds"]
POST = CLS["post_scaffold_checkpoints"]
SINGLE_TIE_BREAK = ["O1", "O2", "H3", "R0"]  # focused-screen arms


def routing_at(rec, step):
    for t in rec.get("trajectory", []):
        if t["step"] == step:
            return t.get("routing", {}) or {}
    return {}


def needle_traj(rec):
    return {t["step"]: t.get("needle_d96") for t in rec.get("trajectory", []) if "needle_d96" in t}


def correct_slot_ok(rec, step):
    r = routing_at(rec, step)
    if not r:
        return False
    prob = r.get("read_prob_on_highest_write_slot")
    rank = r.get("rank_of_highest_write_slot_under_read")
    margin = r.get("address_logit_margin")
    if prob is None or rank is None or margin is None:
        return False
    return (prob >= RT["correct_slot_probability_min"] and rank <= RT["correct_slot_median_rank_max"]
            and margin >= RT["correct_slot_address_margin_min"])


def per_seed_state(cand, ap):
    """Classify one seed into a functional-routing state."""
    d96 = FROZEN.d(cand, 96)
    formed_final = FROZEN.forming(cand, ap)
    traj = needle_traj(cand)
    peak = max([v for v in traj.values() if v is not None] or [0.0])
    endpoint = d96 >= FROZEN.FORM_MIN
    at600 = (traj.get(600, 0) or 0) >= FROZEN.FORM_MIN
    at900 = (traj.get(900, 0) or 0) >= FROZEN.FORM_MIN
    retained = endpoint and at900 and at600

    if not formed_final and peak >= FROZEN.FORM_MIN:
        return "FORMED_THEN_COLLAPSED"
    if not formed_final and peak < FROZEN.FORM_MIN:
        return "NEVER_FORMED"
    # formed_final True below
    causal = FROZEN.causal_ok(cand, ap)
    routing_clean = correct_slot_ok(cand, 1200)
    if not retained:
        # endpoint forms but dipped at 600/900 then recovered
        return "TRANSIENT_RECOVERY"
    if causal and routing_clean:
        return "FORMED_FUNCTIONALLY_CLEAN_AND_RETAINED"
    if not routing_clean and endpoint and FROZEN.d(cand, 96) >= FROZEN.FORM_MIN and not causal:
        return "ROUTING_PROXY_ONLY"
    return "FORMED_FUNCTIONALLY_UNCLEAN_AND_RETAINED"


def slots_off_ok(cand, ap):
    ab = cand.get("ablation", {})
    base = ab.get("baseline", FROZEN.d(cand, 96)); ap96 = FROZEN.d(ap, 96)
    gain = base - ap96; thr = max(ap96 + 0.030, 0.050); v = ab.get("slots_off")
    if v is None:
        return False
    drop = base - v
    return (drop >= 0.050) and ((drop >= 0.5 * gain) if gain > 0 else True) and (v <= thr)


def rand_addr_ok(cand, ap):
    ab = cand.get("ablation", {})
    base = ab.get("baseline", FROZEN.d(cand, 96)); ap96 = FROZEN.d(ap, 96)
    gain = base - ap96; thr = max(ap96 + 0.030, 0.050); v = ab.get("randomized_address")
    if v is None:
        return False
    drop = base - v
    return (drop >= 0.050) and ((drop >= 0.5 * gain) if gain > 0 else True) and (v <= thr)


def arm_summary(cand_by_seed, ap_by_seed, r0_by_seed):
    states = {s: per_seed_state(cand_by_seed[s], ap_by_seed[s]) for s in SEEDS}
    clean_stable = [s for s in SEEDS if states[s] == "FORMED_FUNCTIONALLY_CLEAN_AND_RETAINED"]
    collapsed = [s for s in SEEDS if states[s] == "FORMED_THEN_COLLAPSED"]
    final_formers = [s for s in SEEDS if FROZEN.forming(cand_by_seed[s], ap_by_seed[s])]
    unclean = [s for s in final_formers if not correct_slot_ok(cand_by_seed[s], 1200)]
    causal_final = {s: (slots_off_ok(cand_by_seed[s], ap_by_seed[s]) and rand_addr_ok(cand_by_seed[s], ap_by_seed[s]))
                    for s in final_formers}
    wins_vs_r0 = sum(1 for s in SEEDS if FROZEN.d(cand_by_seed[s], 96) > FROZEN.d(r0_by_seed[s], 96))
    s256 = [cand_by_seed[s]["ppl"]["256"] for s in SEEDS]
    ap256 = [ap_by_seed[s]["ppl"]["256"] for s in SEEDS]
    ppl_ok = st.mean(s256) <= 1.20 * st.mean(ap256) and sum(1 for i in range(5) if s256[i] > 1.25 * ap256[i]) <= 2
    d16_ok = all(FROZEN.d(cand_by_seed[s], 16) >= FROZEN.d(ap_by_seed[s], 16) - 0.050 for s in SEEDS)
    d220_pos = sum(1 for s in final_formers if FROZEN.d(cand_by_seed[s], 220) - FROZEN.d(ap_by_seed[s], 220) > 0)
    dist_ok = d16_ok and d220_pos >= 3
    full_gate = (len(clean_stable) >= 4 and wins_vs_r0 >= 4 and all(causal_final.get(s, False) for s in final_formers)
                 and len(collapsed) <= 1 and len(unclean) == 0 and ppl_ok and dist_ok)
    return {
        "states": {str(s): states[s] for s in SEEDS},
        "clean_stable_count": len(clean_stable),
        "formed_then_collapsed_count": len(collapsed),
        "final_former_count": len(final_formers),
        "routing_unclean_final_formers": [str(s) for s in unclean],
        "causal_by_final_former": {str(s): causal_final[s] for s in final_formers},
        "paired_wins_vs_R0": wins_vs_r0,
        "needle_d96": {str(s): FROZEN.d(cand_by_seed[s], 96) for s in SEEDS},
        "quality_ok": ppl_ok, "distance_ok": dist_ok,
        "full_single_gate": full_gate,
    }


def load(results_dir, arm):
    p = pathlib.Path(results_dir) / f"{arm}_results.json"
    if not p.exists():
        return None
    return {r["seed"]: r for r in json.loads(p.read_text())["records"]}


def classify(results_dir, integrity_ok=True, deviations=None):
    deviations = deviations or []
    arms = {a: load(results_dir, a) for a in ("A+", "R0", "O1", "O2", "H3")}
    missing = [a for a, v in arms.items() if v is None or any(s not in v for s in SEEDS)]
    if missing:
        return {"schema": "bindingslots_functional_routing/stage1_aggregate/v1",
                "primary_verdict": "FUNCTIONAL_ROUTING_RESOURCE_BLOCKED",
                "kda_readiness": "KDA_VALIDATION_BLOCKED",
                "reason": f"incomplete Stage-1 results; missing/partial arms: {missing}"}
    ap, r0 = arms["A+"], arms["R0"]
    summaries = {a: arm_summary(arms[a], ap, r0) for a in ("R0", "O1", "O2", "H3")}

    clearing = [a for a in ("O1", "O2", "H3", "R0") if summaries[a]["full_single_gate"]]
    if not integrity_ok:
        verdict, selected, readiness = "FUNCTIONAL_ROUTING_INTEGRITY_FAILED", None, "KDA_VALIDATION_BLOCKED"
    elif deviations:
        verdict, selected, readiness = "FUNCTIONAL_ROUTING_PROTOCOL_VIOLATED", None, "KDA_VALIDATION_BLOCKED"
    elif clearing:
        # mechanical tie-break
        def key(a):
            s = summaries[a]
            return (-s["clean_stable_count"], -s["paired_wins_vs_R0"], s["formed_then_collapsed_count"],
                    SINGLE_TIE_BREAK.index(a))
        selected = sorted([a for a in clearing if a != "R0"] or clearing, key=key)[0]
        verdict = "FUNCTIONAL_ROUTING_AND_RETENTION_CANDIDATE_SELECTED"
        readiness = "KDA_VALIDATION_BLOCKED_PENDING_INDEPENDENT_CONFIRMATION"
    else:
        # diagnose why nothing cleared, for the informative sub-verdict
        any_clean_gain = any(summaries[a]["clean_stable_count"] > summaries["R0"]["clean_stable_count"]
                             for a in ("O1", "O2", "H3"))
        any_unclean = any(summaries[a]["routing_unclean_final_formers"] for a in ("O1", "O2", "H3"))
        any_collapse = any(summaries[a]["formed_then_collapsed_count"] > 1 for a in ("O1", "O2", "H3"))
        if any_unclean and not any_clean_gain:
            verdict = "ROUTING_PURITY_NOT_RESOLVED"
        elif any_collapse and not any_clean_gain:
            verdict = "RETENTION_NOT_RESOLVED"
        else:
            verdict = "NO_FUNCTIONAL_ROUTING_INTERVENTION_SELECTED"
        selected, readiness = None, "KDA_VALIDATION_BLOCKED"

    return {
        "schema": "bindingslots_functional_routing/stage1_aggregate/v1",
        "stage1_seeds": SEEDS, "arms": ["A+", "R0", "O1", "O2", "H3"],
        "summaries": summaries,
        "primary_verdict": verdict,
        "selected_candidate": selected,
        "kda_readiness": readiness,
        "protocol_deviations": deviations,
        "notes": ["Stage-2 development holdout is deferred by this focused phase.",
                  "READY_FOR_KDA_VALIDATION is never emitted.",
                  "One routing-unclean final former or >1 collapse disqualifies an arm's full gate; causal results never averaged."],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--integrity-ok", type=int, default=1)
    ap.add_argument("--deviations", default="")
    args = ap.parse_args()
    devs = [d for d in args.deviations.split(";") if d.strip()]
    out = classify(args.results_dir, integrity_ok=bool(args.integrity_ok), deviations=devs)
    print(json.dumps(out, indent=2))
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
