#!/usr/bin/env python3
"""
Single-command entry point for the full enterprise-readiness evaluation.

    python -m agentic.hybrid_handover.evaluation.run_eval

Runs every adversarial case (clean) plus the full fault-injection suite on the
control cases, under both the frozen-gates-only and augmented-validation
configurations, then writes Markdown + JSON reports and prints the verdict.

The extractor under test is pluggable; by default it is the frozen deterministic
``InHouseExtractor``. Swap it for a neural extractor to re-run identically.
"""

from __future__ import annotations

import os

from agentic.hybrid_handover.inhouse import InHouseExtractor

from .corpus import CONTROL_CASE_IDS, all_cases
from .harness import evaluate_case
from .injectors import ALL_INJECTORS
from .protocols import ExtractorProtocol
from .report import build_report, render_json, render_markdown
from .validators import DEFAULT_VALIDATORS

REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")


def run(extractor: ExtractorProtocol | None = None, validators=None) -> dict:
    extractor = extractor or InHouseExtractor()
    validators = validators or DEFAULT_VALIDATORS
    cases = all_cases()
    controls = [c for c in cases if c.case_id in CONTROL_CASE_IDS]

    gates: list = []
    augmented: list = []

    # 1) every adversarial case, clean, under both configs
    for case in cases:
        gates.append(evaluate_case(case, extractor, validators, "gates_only"))
        augmented.append(evaluate_case(case, extractor, validators, "augmented"))

    # 2) full fault-injection suite on the control cases (fail-closed testing).
    #    Expectation is derived per-run from whether the injector actually
    #    removed decisive evidence (see harness `injected=True`).
    for case in controls:
        for inj in ALL_INJECTORS:
            gates.append(evaluate_case(case, extractor, validators, "gates_only", injector=inj, injected=True))
            augmented.append(evaluate_case(case, extractor, validators, "augmented", injector=inj, injected=True))

    report = build_report(gates, augmented)

    os.makedirs(REPORT_DIR, exist_ok=True)
    md_path = os.path.join(REPORT_DIR, "evaluation_report.md")
    json_path = os.path.join(REPORT_DIR, "evaluation_report.json")
    with open(md_path, "w") as f:
        f.write(render_markdown(report))
    with open(json_path, "w") as f:
        f.write(render_json(report))
    report["_paths"] = {"markdown": md_path, "json": json_path}
    return report


def main() -> None:
    report = run()
    print("=" * 72)
    print("HYBRID HANDOVER — ENTERPRISE READINESS EVALUATION (SYNTHETIC)")
    print("=" * 72)
    print(f"Verdict: {report['verdict']}")
    for r in report["verdict_reasons"]:
        print(f"  - {r}")
    print()
    print("Unsafe Handover Rate  P(accept | decisive evidence missing):")
    print(f"  frozen gates only : {report['key_finding_unsafe_handover']['gates_only']}")
    print(f"  + independent val : {report['key_finding_unsafe_handover']['augmented']}")
    print()
    a = report["metrics"]["augmented"]
    for k in ("critical_evidence_recall", "defeater_recall", "definition_recall",
              "precedence_recall", "coverage_completeness", "fail_closed_rate"):
        print(f"  {k:26s}: {a[k]}")
    print()
    print(f"Reports written:\n  {report['_paths']['markdown']}\n  {report['_paths']['json']}")


if __name__ == "__main__":
    main()
