"""Evaluation harness (Phases 9-11). Deterministic; no live credentials.

Simulates each baseline's attempt sequence against per-candidate GROUND TRUTH, then
aggregates the Phase-9 metrics. False-eligibility on critical (non-permitted) constraints
is reported separately and treated as the most severe error.
"""
from __future__ import annotations

import os
from typing import Dict, List

import baselines as bl
from scenarios import SCENARIOS, Scenario, GroundTruth
from states import EligibilityState

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
VIOLATION_QUALITY_PENALTY = 1.0   # a policy violation is worse than a plain failure


def _best_safe_quality(scn: Scenario) -> float:
    """Oracle: best capability among truly-eligible AND permitted candidates."""
    q = [scn.quality.get(mid, 0.0) for mid, gt in scn.ground_truth.items() if gt.executable and gt.permitted]
    return max(q) if q else 0.0


def simulate(scn: Scenario, attempt_seq: List[str], abstained: bool, overhead_ms: float) -> Dict:
    """Run an attempt sequence against ground truth -> one outcome record."""
    best = _best_safe_quality(scn)
    out = {"attempts": 0, "failed_calls": 0, "success": False, "used": None, "quality": 0.0,
           "cost": 0.0, "wasted_cost": 0.0, "latency_ms": overhead_ms, "violation": False,
           "abstained": abstained, "first_attempt_success": False}
    if abstained:
        # abstain is correct iff there is truly no safe option; regret = best (0 if none exists)
        out["regret"] = best
        out["correct_abstain"] = (best == 0.0)
        return out
    for i, mid in enumerate(attempt_seq):
        gt = scn.ground_truth[mid]
        out["attempts"] += 1
        if gt.executable:
            out["used"] = mid
            out["latency_ms"] += gt.latency_ms
            out["cost"] += gt.cost_per_call
            if gt.permitted:
                out["success"] = True
                out["quality"] = gt.quality
                out["first_attempt_success"] = (i == 0)
            else:
                out["violation"] = True   # used a working-but-prohibited model
                out["quality"] = 0.0
            break
        else:
            out["failed_calls"] += 1
            out["latency_ms"] += gt.error_latency_ms
            out["wasted_cost"] += gt.cost_per_call  # ~0 for errored calls
    # regret: best safe quality minus achieved; a violation is penalized below zero-quality failure
    achieved = out["quality"] if out["success"] else (-VIOLATION_QUALITY_PENALTY if out["violation"] else 0.0)
    out["regret"] = round(best - achieved, 4)
    out["correct_abstain"] = False
    return out


def eligibility_confusion(scn: Scenario, decisions) -> Dict:
    """Compare gate decisions to ground truth (truly eligible = executable AND permitted)."""
    tp = fp = fn = tn = fp_critical = 0
    for mid, dec in (decisions or {}).items():
        gt = scn.ground_truth[mid]
        truly = gt.executable and gt.permitted
        selectable = dec.state in (EligibilityState.ELIGIBLE, EligibilityState.CONDITIONALLY_ELIGIBLE)
        if selectable and truly: tp += 1
        elif selectable and not truly:
            fp += 1
            if not gt.permitted: fp_critical += 1   # false-eligible on a compliance constraint (severe)
        elif not selectable and truly: fn += 1
        else: tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "fp_critical": fp_critical}


def run() -> Dict:
    per_baseline: Dict[str, List[Dict]] = {b: [] for b in bl.BASELINES}
    confusion: Dict[str, Dict[str, int]] = {b: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "fp_critical": 0}
                                            for b in bl.BASELINES}
    for scn in SCENARIOS:
        for bname, fn in bl.BASELINES.items():
            seq, abstained, decisions = fn(scn)
            overhead = bl.GATE_OVERHEAD_MS.get(bname, 0.0)
            outcome = simulate(scn, seq, abstained, overhead)
            outcome["scenario"] = scn.id
            outcome["category"] = scn.category
            per_baseline[bname].append(outcome)
            if decisions is not None:
                c = eligibility_confusion(scn, decisions)
                for k in confusion[bname]:
                    confusion[bname][k] += c[k]

    agg = {}
    n = len(SCENARIOS)
    for bname, outs in per_baseline.items():
        succ = [o for o in outs if o["success"]]
        agg[bname] = {
            "n_scenarios": n,
            "execution_success_rate": round(sum(o["success"] for o in outs) / n, 4),
            "first_attempt_success_rate": round(sum(o["first_attempt_success"] for o in outs) / n, 4),
            "policy_violation_rate": round(sum(o["violation"] for o in outs) / n, 4),
            "mean_failed_calls": round(sum(o["failed_calls"] for o in outs) / n, 4),
            "fallback_rate": round(sum(o["attempts"] > 1 for o in outs) / n, 4),
            "abstention_rate": round(sum(o["abstained"] for o in outs) / n, 4),
            "mean_selection_regret": round(sum(o["regret"] for o in outs) / n, 4),
            "mean_latency_ms": round(sum(o["latency_ms"] for o in outs) / n, 1),
            "mean_cost_per_success": round(sum(o["cost"] for o in succ) / len(succ), 6) if succ else None,
            "mean_wasted_cost": round(sum(o["wasted_cost"] for o in outs) / n, 6),
        }
        conf = confusion[bname]
        tp, fp, fn2 = conf["tp"], conf["fp"], conf["fn"]
        if tp + fp + fn2 > 0:
            agg[bname]["eligibility_precision"] = round(tp / (tp + fp), 4) if (tp + fp) else None
            agg[bname]["eligibility_recall"] = round(tp / (tp + fn2), 4) if (tp + fn2) else None
            agg[bname]["false_eligible_critical"] = conf["fp_critical"]
            agg[bname]["false_ineligible"] = fn2
    return {"scenarios": n, "aggregate": agg, "per_scenario": per_baseline,
            "categories": sorted({s.category for s in SCENARIOS})}


def print_summary(res: Dict):
    print(f"\nscenarios: {res['scenarios']}  categories: {res['categories']}")
    cols = [("execution_success_rate", "succ"), ("first_attempt_success_rate", "1st"),
            ("policy_violation_rate", "viol"), ("mean_selection_regret", "regret"),
            ("mean_failed_calls", "fails"), ("fallback_rate", "fbk"),
            ("abstention_rate", "abst"), ("mean_latency_ms", "lat_ms"),
            ("false_eligible_critical", "FE!"), ("false_ineligible", "FI")]
    hdr = f"{'baseline':>22} " + "".join(f"{c[1]:>8}" for c in cols)
    print(hdr)
    for b, m in res["aggregate"].items():
        print(f"{b:>22} " + "".join(f"{str(m.get(c[0],'-')):>8}" for c in cols))


if __name__ == "__main__":
    from common_io import save_json  # noqa
    r = run()
    save_json(os.path.join(RESULTS_DIR, "evaluation.json"), r)
    print_summary(r)
