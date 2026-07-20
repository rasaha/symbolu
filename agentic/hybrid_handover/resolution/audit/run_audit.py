#!/usr/bin/env python3
"""
Relationship-benchmark audit orchestrator.

    python -m agentic.hybrid_handover.resolution.audit.run_audit

Runs: adversarial-resolver gaming, hidden mirror generalisation, ground-truth
structural + necessity checks, leakage probe, and robustness stress. Writes
AUDIT_RESULTS.json and prints a verdict-oriented summary. Reads SEEB / resolution;
modifies nothing frozen.
"""

from __future__ import annotations

import inspect
import json
import os

from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.resolution import resolvers as _resmod
from agentic.hybrid_handover.resolution.gold import GOLD
from agentic.hybrid_handover.resolution.harness import evaluate_resolver
from agentic.hybrid_handover.resolution.resolvers import ALL_RESOLVERS, RESOLVER_ORDER

from .adversarial import ADVERSARIAL, ADVERSARIAL_ORDER
from .groundtruth import run_groundtruth
from .mirrors import run_mirrors
from .robustness import run_robustness

OUT_DIR = os.path.dirname(__file__)


def adversarial_audit():
    n_abstain = sum(1 for g in GOLD.values() if g.abstain)
    rows = {}
    for name in ADVERSARIAL_ORDER:
        rep = evaluate_resolver(ADVERSARIAL[name](), "A_oracle")
        m = rep["metrics"]
        false_abstain = sum(1 for pc in rep["per_case"]
                            if pc["abstained"] and not GOLD[pc["case_id"]].abstain)
        rows[name] = {"n_correct": rep["n_correct"], "metrics": m,
                      "false_abstention": f"{false_abstain}/{16 - n_abstain}"}
    # which metrics are gamed: a metric is gameable if some cheat scores >= 0.99
    metric_keys = set()
    for name in ADVERSARIAL_ORDER:
        metric_keys |= set(rows[name]["metrics"])
    gameable = {}
    for k in sorted(metric_keys):
        best = max((rows[n]["metrics"].get(k) or 0) for n in ADVERSARIAL_ORDER)
        winners = [n for n in ADVERSARIAL_ORDER if (rows[n]["metrics"].get(k) or 0) >= 0.99]
        if best >= 0.99:
            gameable[k] = {"max_by_cheat": best, "cheats": winners}
    return {"per_resolver": rows, "gameable_metrics": gameable}


def leakage_probe():
    """Static probe: baseline resolvers must not reference gold / case identity."""
    findings = []
    for name in RESOLVER_ORDER:
        cls = ALL_RESOLVERS[name]
        for meth in ("resolve", "resolve_relationships", "resolve_governance"):
            src = inspect.getsource(getattr(cls, meth)) if hasattr(cls, meth) else ""
            for banned in ("GOLD", "case_id", "expected_answer", ".gold"):
                if banned in src:
                    findings.append(f"{name}.{meth} references {banned!r}")
    # interface signatures carry no case identity
    sig_ok = True
    for name in RESOLVER_ORDER:
        s = str(inspect.signature(ALL_RESOLVERS[name].resolve))
        if "case" in s or "gold" in s:
            sig_ok = False
    return {"leak_findings": findings, "signature_clean": sig_ok}


def mirror_audit():
    out = {}
    for name in RESOLVER_ORDER:
        rows = run_mirrors(ALL_RESOLVERS[name]())
        ent = [r for r in rows if r["family"] == "entity"]
        wrd = [r for r in rows if r["family"] == "wording"]
        out[name] = {
            "entity_detected": f"{sum(r['edge_detected'] for r in ent)}/{len(ent)}",
            "wording_detected": f"{sum(r['edge_detected'] for r in wrd)}/{len(wrd)}",
            "rows": rows,
        }
    return out


def run():
    return {
        "benchmark": "SEEB relationship-resolution layer", "synthetic": True,
        "adversarial": adversarial_audit(),
        "mirrors": mirror_audit(),
        "ground_truth": run_groundtruth(),
        "leakage": leakage_probe(),
        "robustness": run_robustness(),
    }


def main():
    out = run()
    with open(os.path.join(OUT_DIR, "AUDIT_RESULTS.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    print("=" * 78)
    print("RELATIONSHIP BENCHMARK AUDIT (synthetic)")
    print("=" * 78)
    print("\n[1] Adversarial gaming — metrics a trivial cheat maxes (>=0.99):")
    for k, v in out["adversarial"]["gameable_metrics"].items():
        print(f"    GAMEABLE  {k:32s} by {v['cheats']}")
    print("    false-abstention of always_abstain:",
          out["adversarial"]["per_resolver"]["always_abstain"]["false_abstention"])

    print("\n[2] Mirror generalisation (edge detection):")
    for name in RESOLVER_ORDER:
        m = out["mirrors"][name]
        print(f"    {name:18s} entity {m['entity_detected']}   wording {m['wording_detected']}")

    print("\n[3] Ground-truth structural issues:", out["ground_truth"]["structural_issues"] or "none")
    nonnec = [r["edge"] for r in out["ground_truth"]["necessity"] if not r["governance_necessary"]]
    print(f"    edges NOT necessary for governance (justificatory/packet): {len(nonnec)}")
    for e in nonnec:
        print(f"      · {e}")

    print("\n[4] Leakage probe:", "CLEAN" if not out["leakage"]["leak_findings"] and out["leakage"]["signature_clean"]
          else out["leakage"])

    print("\n[5] Robustness observations:")
    for k, v in out["robustness"].items():
        print(f"    {k:20s} {v['result']}")

    print(f"\nWrote {os.path.join(OUT_DIR, 'AUDIT_RESULTS.json')}")


if __name__ == "__main__":
    main()
