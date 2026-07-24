"""Phase 15-16 - Latency, cost, and reviewer burden on natural artifacts.

Measures the governance overhead (NOT the model call, which the pilot never makes) and the human-review
burden the runtime would impose on natural traffic.

Determinism note: the frozen artifact stores only DETERMINISTIC content - governance latency in the
trace's deterministic units, cost estimates, and review-burden counts. Wall-clock is reported live at
runtime (instrumentation, never a decision input, never frozen) so the JSON stays byte-reproducible.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from governed_inference_pilot import orchestrator as gip_orch

from bounded_shadow_pilot import case_builder

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "natural_pilot_v1")
_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

# dispositions that impose human-review burden
_REVIEW_TRIGGERS = {"WOULD_ESCALATE", "INDETERMINATE", "WOULD_REJECT", "EVIDENCE_UNAVAILABLE"}


def _load():
    corpus = json.load(open(os.path.join(_DATA, "corpus.json")))
    gt = json.load(open(os.path.join(_DATA, "ground_truth.json")))
    return corpus["artifacts"], {g["artifact_id"]: g for g in gt["labels"]}


def _percentile(sorted_vals: List[int], p: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, int(p * (len(sorted_vals) - 1)))
    return sorted_vals[idx]


def compute() -> Dict[str, Any]:
    artifacts, gts = _load()
    artifacts = sorted(artifacts, key=lambda x: x["artifact_id"])

    latency_units: List[int] = []
    cost_total = 0.0
    review_burden = 0
    burden_by_use_case: Dict[str, int] = {}
    burden_by_disposition: Dict[str, int] = {}
    minimized_bytes = 0

    for a in artifacts:
        gt = gts[a["artifact_id"]]
        case = case_builder.build_case(a, gt)
        trace = gip_orch.run_case(case, config="FULL_STACK_HIGH_RISK")
        total_units = sum(e.latency_units for e in trace.events)
        latency_units.append(total_units)
        cost_total += sum(e.estimated_cost_usd for e in trace.events)

        final = trace.final_shadow_disposition
        needs_review = final in _REVIEW_TRIGGERS or trace.human_review_state == "required"
        if needs_review:
            review_burden += 1
            burden_by_use_case[a["use_case"]] = burden_by_use_case.get(a["use_case"], 0) + 1
            burden_by_disposition[final] = burden_by_disposition.get(final, 0) + 1

        # minimized shadow record size (data-minimized: dispositions + codes + signature only)
        rec = {"artifact_id": a["artifact_id"], "final": final,
               "reason_codes": [c for e in trace.events for c in e.reason_codes][:10],
               "replay_signature": trace.replay_signature}
        minimized_bytes += len(json.dumps(rec))

    latency_units.sort()
    n = len(artifacts)
    return {
        "corpus_id": "natural_pilot_v1",
        "n": n,
        "config": "FULL_STACK_HIGH_RISK",
        "governance_latency_units": {
            "median": _percentile(latency_units, 0.5),
            "p95": _percentile(latency_units, 0.95),
            "max": latency_units[-1] if latency_units else 0,
            "note": "deterministic units from the frozen trace; excludes the (never-made) model call",
        },
        "governance_cost": {
            "total_estimated_usd": round(cost_total, 6),
            "per_artifact_usd": round(cost_total / n, 8) if n else 0.0,
            "note": "governance overhead only; the real cost is the un-made model call (out of scope)",
        },
        "storage": {
            "minimized_total_bytes": minimized_bytes,
            "minimized_per_artifact_bytes": round(minimized_bytes / n, 1) if n else 0.0,
            "note": "data-minimized shadow record: dispositions + reason codes + replay signature only",
        },
        "reviewer_burden": {
            "artifacts_routed_to_review": review_burden,
            "burden_rate": round(review_burden / n, 4) if n else 0.0,
            "by_use_case": dict(sorted(burden_by_use_case.items(), key=lambda kv: -kv[1])),
            "by_disposition": burden_by_disposition,
            "note": "over-qualified deliveries do NOT add review burden (they deliver with caveats); "
                    "burden comes from withholds/escalations/indeterminate",
        },
    }


def freeze() -> Dict[str, Any]:
    m = compute()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "perf_cost_burden.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


def _wall_clock_probe(n: int = 200) -> Dict[str, float]:
    """Live wall-clock instrumentation (NOT frozen). Median/p95 ms of the governance pipeline."""
    import time
    artifacts, gts = _load()
    artifacts = sorted(artifacts, key=lambda x: x["artifact_id"])[:n]
    times: List[float] = []
    for a in artifacts:
        case = case_builder.build_case(a, gts[a["artifact_id"]])
        t0 = time.perf_counter()
        gip_orch.run_case(case, config="FULL_STACK_HIGH_RISK")
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    return {"median_ms": round(times[len(times)//2], 4),
            "p95_ms": round(times[min(len(times)-1, int(0.95*(len(times)-1)))], 4),
            "n": len(times)}


if __name__ == "__main__":
    m = freeze()
    lu = m["governance_latency_units"]
    print(f"governance latency units: median={lu['median']} p95={lu['p95']} max={lu['max']}")
    print(f"governance cost: total=${m['governance_cost']['total_estimated_usd']} "
          f"per-artifact=${m['governance_cost']['per_artifact_usd']}")
    print(f"storage: {m['storage']['minimized_per_artifact_bytes']} bytes/artifact (minimized)")
    rb = m["reviewer_burden"]
    print(f"reviewer burden: {rb['artifacts_routed_to_review']}/{m['n']} "
          f"({rb['burden_rate']*100:.1f}%) by_disposition={rb['by_disposition']}")
    wc = _wall_clock_probe()
    print(f"[live, not frozen] wall-clock governance: median={wc['median_ms']}ms p95={wc['p95_ms']}ms "
          f"(n={wc['n']}; excludes model call)")
