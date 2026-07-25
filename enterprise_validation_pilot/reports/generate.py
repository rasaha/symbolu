"""Report generation (Task 116).

Produces the machine-readable and human-readable pilot reports. The executive
summary deliberately separates *measured result*, *designed expectation*,
*inference*, and *limitation*, and makes no production-readiness claim.
"""
from __future__ import annotations

import json
import pathlib

from ..pilot import PilotResults
from ..runners.trace import check_completeness


def metrics_json(results: PilotResults) -> dict:
    return {
        "dataset_version": results.dataset_version,
        "dataset_hash": results.dataset_hash,
        "substantive_digest": results.substantive_digest,
        "metrics_by_layer": results.metrics,
    }


def scenario_results_json(results: PilotResults) -> dict:
    rows = []
    for s, r in results.pairs:
        ev = next(e for e in results.evaluations if e.scenario_id == s.scenario_id)
        rows.append({
            "scenario_id": s.scenario_id, "domain": s.domain,
            "assertion_class": s.assertion_class, "action_class": s.action_class,
            "cross_class": s.cross_class, "passed": ev.passed,
            "tap_outcome": r.tap_outcome, "recommendation_posture": r.recommendation_posture,
            "actiongate_outcome": r.actiongate_outcome, "dispatched": r.dispatched,
            "execution_behavior": r.execution_behavior, "reconciliation": r.reconciliation,
            "compliance_verdict": r.compliance_verdict,
            "mismatches": [{"field": m.field, "expected": m.expected, "actual": m.actual}
                           for m in ev.mismatches],
            "error": r.error,
        })
    return {"dataset_version": results.dataset_version,
            "scenarios_passed": results.scenarios_passed,
            "scenarios_total": len(rows), "scenarios": rows}


def invariants_json(results: PilotResults) -> dict:
    return {
        "all_passed": results.invariants_passed,
        "invariants": [{"id": r.id, "description": r.description, "passed": r.passed,
                        "offenders": list(r.offenders), "detail": r.detail}
                       for r in results.invariants],
    }


def failure_injection_json(results: PilotResults) -> dict:
    return {
        "all_fail_safe": results.failure_injection_passed,
        "injections": [{"injection": r.injection, "fail_safe": r.fail_safe, "detail": r.detail}
                       for r in results.injections],
    }


def trace_completeness_json(results: PilotResults) -> dict:
    rows = []
    for r in results.runs:
        comp = check_completeness(r.trace)
        rows.append({"scenario_id": r.scenario_id, "complete": comp.complete,
                     "missing": list(comp.missing),
                     "correlation_id": r.trace.get("correlation_id", ""),
                     "case_id": r.trace.get("case_id", ""),
                     "recommendation_id": r.trace.get("recommendation_id", ""),
                     "decision_id": r.trace.get("decision_id", ""),
                     "authorization_id": r.trace.get("authorization_id", "")})
    complete = sum(1 for row in rows if row["complete"])
    return {"complete": complete, "total": len(rows),
            "completeness_rate": round(complete / len(rows), 6) if rows else 1.0,
            "traces": rows}


def executive_summary_md(results: PilotResults) -> str:
    m = results.metrics
    lines: list[str] = []
    a = lines.append
    a("# Phase 5I — Enterprise Validation Pilot")
    a("")
    a(f"- **Dataset:** `{results.dataset_version}` (hash `{results.dataset_hash[:16]}…`, "
      f"{len(results.runs)} scenarios, 3 domains)")
    a(f"- **Substantive reproducibility digest:** `{results.substantive_digest[:16]}…`")
    a(f"- **Overall pilot pass:** {'YES' if results.overall_pass else 'NO'}")
    a("")
    a("## Measured result")
    a("")
    a(f"- Scenarios reproducing ground truth: **{results.scenarios_passed}/"
      f"{len(results.runs)}**")
    a(f"- Safety invariants: **{'ALL PASS' if results.invariants_passed else 'FAILURE'}** "
      f"({sum(1 for r in results.invariants if r.passed)}/{len(results.invariants)})")
    a(f"- Failure injection fail-safe: **{'ALL FAIL-SAFE' if results.failure_injection_passed else 'FAILURE'}** "
      f"({sum(1 for r in results.injections if r.fail_safe)}/{len(results.injections)})")
    a(f"- Provider independence: **{'PEERS' if results.independence_passed else 'VIOLATION'}**")
    a(f"- Manifest valid: **{results.manifest_valid}**")
    a("")
    a("### Metrics by layer (no aggregate governance score)")
    a("")
    a("**TAP (assertion):**")
    for k, v in m["tap"].items():
        a(f"- `{k}`: {v}")
    a("")
    a("**ActionGate (action):**")
    for k, v in m["actiongate"].items():
        a(f"- `{k}`: {v}")
    a("")
    a("**Workflow:**")
    for k, v in m["workflow"].items():
        a(f"- `{k}`: {v}")
    a("")
    a("## Designed expectation")
    a("")
    a("The pilot composes the frozen kernel, framework, TAP, and ActionGate through")
    a("their public APIs and drives the full workflow (assertion → assessment →")
    a("recommendation → decision → action → authorization → execution →")
    a("reconciliation). Each scenario's expected outcome was authored independently,")
    a("before execution, from design intent — never inferred from provider output.")
    a("")
    a("## Inference")
    a("")
    a("The architecture operates coherently under realistic cross-provider workflows")
    a("while preserving its boundaries: unsupported/indeterminate assertions never")
    a("become supported; denied/indeterminate actions never dispatch; constraints are")
    a("enforced before dispatch; obligations are verified independently of execution")
    a("success; and TAP and ActionGate act as independent peers.")
    a("")
    a("## Limitation")
    a("")
    a("- TAP/ActionGate outcomes are produced by the providers' **deterministic")
    a("  reference engines configured per domain policy**; the pilot validates")
    a("  *workflow integration and invariant enforcement*, not the providers'")
    a("  model/NLP accuracy — that is covered by provider conformance, which the")
    a("  pilot consumes and does not redefine.")
    a("- All data is synthetic. **No production-readiness or regulatory-compliance")
    a("  claim** is made from these results.")
    a("- The `tenant` field remains absent from the neutral request contract (noted")
    a("  in Phase 5G/5H); no scenario required it, so no contract extension is")
    a("  proposed.")
    a("")
    return "\n".join(lines) + "\n"


_REPORTS = {
    "PHASE_5I_METRICS.json": metrics_json,
    "PHASE_5I_SCENARIO_RESULTS.json": scenario_results_json,
    "PHASE_5I_INVARIANTS.json": invariants_json,
    "PHASE_5I_FAILURE_INJECTION.json": failure_injection_json,
    "PHASE_5I_TRACE_COMPLETENESS.json": trace_completeness_json,
}


def write_all(results: PilotResults, out_dir: pathlib.Path) -> list[pathlib.Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fn in _REPORTS.items():
        path = out_dir / name
        path.write_text(json.dumps(fn(results), indent=2, sort_keys=True) + "\n")
        written.append(path)
    md = out_dir / "PHASE_5I_ENTERPRISE_VALIDATION.md"
    md.write_text(executive_summary_md(results))
    written.append(md)
    return written
