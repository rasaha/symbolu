"""Legacy-vs-new parity runner.

Drives BOTH the legacy ``decompose_goal`` and the new ``ModelPlanner`` with the SAME
deterministic model (so the comparison isolates the runtimes, not the model), and
compares decomposition structure, tool selection, and arguments. For governed
scenarios it also runs the new side through the AI Control Plane and records the
governance outcome — the legacy in-runtime governance is an INTENTIONAL difference and
is not executed (it violates the new ownership boundary).

Deterministic. Usage: python -m agent_runtime_migration.parity.runner [--json out.json]
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

from .. import _paths  # noqa: F401
from ..contracts.goal import Goal
from ..control_plane import ControlPlaneClient, GovernedExecutor
from ..model import ReplayModel
from ..planning import ModelPlanner
from ..runtime import AgentRuntime
from ..tools import ToolRegistry
from .corpus import ParityScenario, build_corpus, PARITY

# legacy decomposition (importable; runs with a mock model)
from agentic.agentic_framework.goal_decomposition import decompose_goal  # noqa: E402

NOW = "2026-01-01T00:10:00.000Z"


def _shared_model(sc: ParityScenario) -> ReplayModel:
    payload = json.dumps({"purpose_type": "task", "actions": sc.plan})
    return ReplayModel({}, default=payload, name="shared")


def _registry(sc: ParityScenario, spy) -> ToolRegistry:
    reg = ToolRegistry()
    for tool, (risk, profile, fast) in sc.tools.items():
        reg.register(tool, spy, risk, profile=profile, fast_path_permitted=fast)
    return reg


class _Spy:
    def __init__(self, fail=False):
        self.calls = 0
        self._fail = fail

    def __call__(self, a):
        self.calls += 1
        if self._fail:
            raise RuntimeError("tool failure")
        return "OK"


def _legacy_steps(sc: ParityScenario) -> List[Dict[str, Any]]:
    gs = decompose_goal(sc.task, _shared_model(sc))
    return [{"tool": a.action_type, "args": a.parameters} for a in gs.actions]


def _new_steps(sc: ParityScenario, spy) -> List[Dict[str, Any]]:
    reg = _registry(sc, spy)
    plan = ModelPlanner(_shared_model(sc), reg).plan(Goal(goal_id=sc.name, objective=sc.task))
    return [{"tool": a.tool_name, "args": a.arguments} for a in plan.steps]


def run() -> Dict[str, Any]:
    scenarios = build_corpus()
    results: List[Dict[str, Any]] = []
    m = {"scenarios": len(scenarios), "plan_agreement": 0, "tool_agreement": 0,
         "argument_agreement": 0, "parity_expected": 0, "parity_met": 0,
         "intentional_differences": 0, "unexplained_regressions": 0,
         "new_governance_outcome_correct": 0, "governed_scenarios": 0}

    for sc in scenarios:
        spy = _Spy()
        legacy = _legacy_steps(sc)
        new = _new_steps(sc, spy)
        plan_agree = len(legacy) == len(new)
        tool_agree = plan_agree and [s["tool"] for s in legacy] == [s["tool"] for s in new]
        arg_agree = plan_agree and [s["args"] for s in legacy] == [s["args"] for s in new]
        if plan_agree:
            m["plan_agreement"] += 1
        if tool_agree:
            m["tool_agreement"] += 1
        if arg_agree:
            m["argument_agreement"] += 1

        rec: Dict[str, Any] = {"scenario": sc.name, "label": sc.label,
                               "legacy_tools": [s["tool"] for s in legacy],
                               "new_tools": [s["tool"] for s in new],
                               "plan_agreement": plan_agree, "tool_agreement": tool_agree,
                               "argument_agreement": arg_agree}

        # governed scenarios: run the NEW side through the control plane
        if sc.governed:
            m["governed_scenarios"] += 1
            ex = GovernedExecutor(registry=_registry(sc, spy),
                                  client=ControlPlaneClient(auto_evidence=sc.auto_evidence),
                                  now_provider=lambda: NOW)
            goal = Goal(goal_id=sc.name, objective=sc.task)
            out = AgentRuntime(executor=ex, planner=ModelPlanner(_shared_model(sc),
                               _registry(sc, spy))).run(goal, max_replans=0)
            composed = out.observations[0].governance.get("composed") if out.observations else None
            rec["new_composed_outcome"] = composed
            rec["expected_new_outcome"] = sc.expect_new_outcome
            if composed == sc.expect_new_outcome:
                m["new_governance_outcome_correct"] += 1

        # parity accounting
        if sc.label == PARITY:
            m["parity_expected"] += 1
            met = plan_agree and tool_agree and arg_agree
            rec["parity_met"] = met
            if met:
                m["parity_met"] += 1
            elif not (plan_agree and tool_agree):
                m["unexplained_regressions"] += 1   # a parity scenario that diverged unexpectedly
        else:
            m["intentional_differences"] += 1

        results.append(rec)

    all_parity_met = m["parity_met"] == m["parity_expected"]
    gov_ok = m["new_governance_outcome_correct"] == m["governed_scenarios"]
    return {
        "shared_model": "deterministic replay (same model drives legacy + new)",
        "metrics": m,
        "all_parity_met": all_parity_met,
        "governance_outcomes_correct": gov_ok,
        "unexplained_regressions": m["unexplained_regressions"],
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
    ok = (report["all_parity_met"] and report["governance_outcomes_correct"]
          and report["unexplained_regressions"] == 0)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
