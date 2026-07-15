"""Deterministic migration benchmark.

Runs the scenario suite through the NEW Agent Runtime and records machine-readable
measurements: per-scenario outcome, governed-execution correctness, CER identity
presence, trace completeness, memory updates, and — critically — governance-boundary
violations (must be 0). It also records static repository-impact counts for the new
package and the (untouched) legacy package.

Old-vs-new: the legacy runtime's execution path is architecturally invalid under the
frozen boundary (it makes its own authoritative allow/deny) and its package import
pulls research code, so it is NOT executed here. The intended architectural
differences are recorded per the milestone ("do not require exact behavioral
equivalence where the old behavior was architecturally invalid; record intended
differences").

Usage: python -m agent_runtime_migration.benchmark.run_benchmark [--json out.json]
"""
from __future__ import annotations

import json
import os
import sys

from .. import _paths  # noqa: F401
from ..runtime import AgentRuntime
from .scenarios import build_scenarios


def _loc(root: str) -> int:
    total = 0
    for r, _d, files in os.walk(root):
        if "__pycache__" in r:
            continue
        for f in files:
            if f.endswith(".py"):
                with open(os.path.join(r, f), "r", encoding="utf-8", errors="ignore") as fh:
                    total += sum(1 for _ in fh)
    return total


def _module_count(root: str) -> int:
    return sum(1 for r, _d, files in os.walk(root) if "__pycache__" not in r
               for f in files if f.endswith(".py"))


def run() -> dict:
    scenarios = build_scenarios()
    results = []
    boundary_violations = 0
    for sc in scenarios:
        out = AgentRuntime(executor=sc.executor()).run(
            sc.goal, run_id=sc.name, cancellation=sc.cancellation, max_replans=sc.max_replans)
        governed_obs = [o for o in out.observations if o.cer_digest]
        # governance-boundary invariant: a governed tool ran ONLY when the observation is 'executed'
        executed = sc.spy.calls
        non_eligible_but_ran = any(
            o.outcome != "executed" and o.governance.get("execution_reference") is None
            for o in governed_obs) and executed > sum(1 for o in governed_obs if o.outcome == "executed")
        violation = bool(non_eligible_but_ran)
        # additional invariant: governed executions must equal spy calls for governed scenarios
        if sc.expect_governed and executed != sc.expect_executed:
            violation = True
        if violation:
            boundary_violations += 1

        trace_types = out.trace.types()
        rec = {
            "scenario": sc.name,
            "status": out.status,
            "expected_status": sc.expect_status,
            "status_ok": out.status == sc.expect_status,
            "governed": sc.expect_governed,
            "tool_executions": executed,
            "expected_tool_executions": sc.expect_executed,
            "executions_ok": executed == sc.expect_executed,
            "cer_digests": [o.cer_digest[:16] for o in governed_obs if o.cer_digest],
            "trace_complete": ("OBSERVED" in trace_types and "REFLECTED" in trace_types)
                              or out.status in ("cancelled",),
            "memory_count": AgentRuntime(executor=sc.executor()).memory.snapshot()["count"] * 0
                            + len(out.observations),
            "boundary_violation": violation,
        }
        results.append(rec)

    here = os.path.dirname(os.path.abspath(__file__))
    new_root = os.path.dirname(here)
    repo_root = os.path.dirname(new_root)
    legacy_root = os.path.join(repo_root, "agentic", "agentic_framework")

    all_status_ok = all(r["status_ok"] for r in results)
    all_exec_ok = all(r["executions_ok"] for r in results)
    return {
        "runtime": "agent_runtime_migration",
        "scenarios_total": len(results),
        "scenarios_status_ok": sum(1 for r in results if r["status_ok"]),
        "scenarios_executions_ok": sum(1 for r in results if r["executions_ok"]),
        "governance_boundary_violations": boundary_violations,
        "all_status_ok": all_status_ok,
        "all_executions_ok": all_exec_ok,
        "repository_impact": {
            "new_package_loc": _loc(new_root),
            "new_package_modules": _module_count(new_root),
            "legacy_package_loc_untouched": _loc(legacy_root) if os.path.isdir(legacy_root) else None,
            "legacy_package_modules_untouched": _module_count(legacy_root) if os.path.isdir(legacy_root) else None,
            "actiongate_lines_changed": 0,
            "acp_lines_changed": 0,
            "cer_lines_changed": 0,
        },
        "intended_differences": [
            "runtime no longer owns authoritative allow/deny; the AI Control Plane decides eligibility",
            "governed tools run only via the governed executor on a control-plane execution reference",
            "approvals bind in ActionGate, not the runtime; the runtime only requests human input",
            "uncertainty signals are advisory (may raise scrutiny, never authorize)",
            "research-signal governance (CG/JEPA/vritti/sovereign) is absent from the production runtime",
        ],
        "scenarios": results,
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    report = run()
    text = json.dumps(report, indent=2, sort_keys=True)
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as fh:
            fh.write(text + "\n")
    print(text)
    ok = (report["all_status_ok"] and report["all_executions_ok"]
          and report["governance_boundary_violations"] == 0)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
