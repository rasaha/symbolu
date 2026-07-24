"""Decision-cascade + latency/cost analysis (Phases 19-20). How local stage decisions compound: which
stage drove each final outcome, redundant/contradictory decisions, load-bearing sequences, and the
per-stage latency/cost profile. Deterministic. Writes eval_results/cascade_latency_cost.json.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict

from . import dataset, orchestrator, dispositions


def _winning_stage(trace):
    """The stage whose shadow outcome equals the final (highest precedence)."""
    final = trace.final_shadow_disposition
    for e in trace.events:
        if e.shadow_outcome == final and e.stage != "orchestrator":
            return e.stage
    return "orchestrator"


def analyze():
    cases = [asdict(c) for c in dataset.all_cases()]
    driver = Counter()                     # which stage drove the final
    safety_contrib = Counter()             # stage that drove a WITHHOLD on an unsafe case
    redundant = 0                          # >1 stage produced the same withhold
    contradictory = 0                      # a stage allowed while another withheld
    stage_latency = defaultdict(int)
    stage_cost = defaultdict(float)
    total_latency = []
    total_cost = []

    for c in cases:
        t = orchestrator.run_case(c)
        final = t.final_shadow_disposition
        ws = _winning_stage(t)
        driver[ws] += 1
        withholds = [e for e in t.events if e.shadow_outcome not in ("WOULD_ALLOW", "")
                     and e.stage != "orchestrator"]
        allows = [e for e in t.events if e.shadow_outcome == "WOULD_ALLOW"]
        if final not in ("WOULD_ALLOW", "WOULD_QUALIFY") and c["partition"] in c.get("unacceptable_finals", []) is False:
            pass
        if final not in ("WOULD_ALLOW", "WOULD_QUALIFY"):
            safety_contrib[ws] += 1
        if len({e.shadow_outcome for e in withholds}) == 1 and len(withholds) > 1:
            redundant += 1
        if withholds and allows:
            contradictory += 1
        for e in t.events:
            stage_latency[e.stage] += e.latency_units
            stage_cost[e.stage] += e.estimated_cost_usd
        total_latency.append(sum(e.latency_units for e in t.events))
        total_cost.append(sum(e.estimated_cost_usd for e in t.events))

    total_latency.sort()
    n = len(total_latency)
    return {
        "n": n,
        "final_driver_stage": dict(driver),
        "safety_driver_stage": dict(safety_contrib),
        "redundant_withhold_cases": redundant,
        "contradictory_cases": contradictory,
        "stage_latency_units_total": dict(stage_latency),
        "latency_units": {"median": total_latency[n // 2], "p90": total_latency[int(n * 0.9)],
                          "p95": total_latency[int(n * 0.95)], "max": total_latency[-1]},
        "cost_usd": {"mean": round(sum(total_cost) / n, 8), "max": round(max(total_cost), 8)},
        "storage_per_trace_events": round(sum(len(orchestrator.run_case(c).events) for c in cases[:40]) / 40, 2),
    }


def main():
    r = analyze()
    o = os.path.join(os.path.dirname(__file__), "eval_results", "cascade_latency_cost.json")
    os.makedirs(os.path.dirname(o), exist_ok=True)
    with open(o, "w") as fh:
        json.dump(r, fh, indent=2, sort_keys=True)
    print("final driver stage:", r["final_driver_stage"])
    print("safety driver stage:", r["safety_driver_stage"])
    print("redundant withholds:", r["redundant_withhold_cases"], "contradictory:", r["contradictory_cases"])
    print("latency units:", r["latency_units"], "cost:", r["cost_usd"])
    print(f"wrote {o}")


if __name__ == "__main__":
    main()
