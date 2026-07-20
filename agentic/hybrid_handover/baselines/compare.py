#!/usr/bin/env python3
"""
Baseline comparison runner.

Runs every registered baseline extractor through the UNCHANGED SEEB v1.0.0
benchmark and emits COMPARISON_RESULTS.json + PER_CASE_RESULTS.csv. It replicates
the exact evaluation loop of ``run_eval.run`` (same cases, same injectors, same
configs) but does NOT write to the benchmark's frozen ``reports/`` directory — it
only reads the benchmark, never modifies it.

    python -m agentic.hybrid_handover.baselines.compare
"""

from __future__ import annotations

import csv
import json
import os
import re

from agentic.hybrid_handover.evaluation.corpus import CONTROL_CASE_IDS, all_cases
from agentic.hybrid_handover.evaluation.harness import evaluate_case
from agentic.hybrid_handover.evaluation.injectors import ALL_INJECTORS
from agentic.hybrid_handover.evaluation.report import build_report
from agentic.hybrid_handover.evaluation.validators import DEFAULT_VALIDATORS
from agentic.hybrid_handover.evaluation.version import BENCHMARK_VERSION

from .registry import ORDER, build

OUT_DIR = os.path.dirname(__file__)

METRICS = [
    "critical_evidence_recall", "defeater_recall", "definition_recall",
    "precedence_recall", "packet_sufficiency", "coverage_completeness",
    "unsupported_claim_rate", "unsafe_handover_rate", "fail_closed_rate",
    "routing_accuracy",
]


def _evaluate_extractor(extractor):
    """Exact replica of run_eval.run()'s loop, parameterised by extractor,
    without writing the benchmark's frozen report files."""
    cases = all_cases()
    controls = [c for c in cases if c.case_id in CONTROL_CASE_IDS]
    gates, augmented = [], []
    for case in cases:
        gates.append(evaluate_case(case, extractor, DEFAULT_VALIDATORS, "gates_only"))
        augmented.append(evaluate_case(case, extractor, DEFAULT_VALIDATORS, "augmented"))
    for case in controls:
        for inj in ALL_INJECTORS:
            gates.append(evaluate_case(case, extractor, DEFAULT_VALIDATORS, "gates_only", injector=inj, injected=True))
            augmented.append(evaluate_case(case, extractor, DEFAULT_VALIDATORS, "augmented", injector=inj, injected=True))
    return build_report(gates, augmented), augmented


def _pct(s: str):
    m = re.match(r"([0-9.]+)%", s or "")
    return float(m.group(1)) if m else None


def run_all():
    results = {}
    per_case_rows = []
    for name in ORDER:
        ex = build(name)
        report, augmented = _evaluate_extractor(ex)
        results[name] = {
            "mode": getattr(ex, "mode", "n/a"),
            "verdict": report["verdict"],
            "unsafe_handover": report["key_finding_unsafe_handover"],
            "metrics_augmented": report["metrics"]["augmented"],
            "metrics_gates_only": report["metrics"]["gates_only"],
        }
        for r in augmented:
            per_case_rows.append({
                "extractor": name, "case_id": r.case_id, "injector": r.injector,
                "config": "augmented", "decision": r.system_decision,
                "expected": r.expected_routing,
                "decisive": f"{r.decisive[0]}/{r.decisive[1]}",
                "defeater": f"{r.defeater[0]}/{r.defeater[1]}",
                "definition": f"{r.definition[0]}/{r.definition[1]}",
                "precedence": f"{r.precedence[0]}/{r.precedence[1]}",
                "decisive_missing": int(r.decisive_missing),
                "accepted": int(r.accepted), "unsafe": int(r.unsafe_handover),
                "sufficient": int(r.packet_sufficient), "coverage_ok": int(r.coverage_ok),
            })

    matrix = {m: {name: _pct(results[name]["metrics_augmented"][m]) for name in ORDER} for m in METRICS}
    out = {
        "benchmark": "Sovereign Evidence Extraction Benchmark (SEEB)",
        "benchmark_version": BENCHMARK_VERSION,
        "synthetic": True,
        "note": ("All corpora synthetic. Embedding/Hybrid ran in char-ngram "
                 "fallback (no neural model available); their numbers are a "
                 "conservative lower bound for dense retrieval. All baselines "
                 "share the frozen relationship-resolution module and vary only "
                 "the retrieval front-end."),
        "extractors": results,
        "metric_matrix_augmented_pct": matrix,
    }
    return out, per_case_rows


def write(out, per_case_rows):
    json_path = os.path.join(OUT_DIR, "COMPARISON_RESULTS.json")
    csv_path = os.path.join(OUT_DIR, "PER_CASE_RESULTS.csv")
    with open(json_path, "w") as f:
        json.dump(out, f, indent=2)
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_case_rows[0].keys()))
        w.writeheader()
        w.writerows(per_case_rows)
    return json_path, csv_path


def _bar(pct, width=24):
    if pct is None:
        return "n/a"
    n = int(round(pct / 100 * width))
    return "█" * n + "·" * (width - n) + f" {pct:5.1f}%"


def main():
    out, rows = run_all()
    jp, cp = write(out, rows)
    print("=" * 78)
    print(f"SEEB v{out['benchmark_version']} — CONVENTIONAL BASELINE COMPARISON (SYNTHETIC)")
    print("=" * 78)
    print(f"{'metric':28s} " + " ".join(f"{n[:11]:>11s}" for n in ORDER))
    for m in METRICS:
        row = out["metric_matrix_augmented_pct"][m]
        print(f"{m:28s} " + " ".join(f"{(str(row[n]) if row[n] is not None else 'n/a'):>11s}" for n in ORDER))
    print()
    print("Unsafe Handover Rate (augmented) — lower is better:")
    for n in ORDER:
        print(f"  {n:16s} {_bar(_pct(out['extractors'][n]['metrics_augmented']['unsafe_handover_rate']))}")
    print()
    for n in ORDER:
        print(f"  {n:16s} verdict={out['extractors'][n]['verdict']}  ({out['extractors'][n]['mode']})")
    print()
    print(f"Wrote:\n  {jp}\n  {cp}")


if __name__ == "__main__":
    main()
