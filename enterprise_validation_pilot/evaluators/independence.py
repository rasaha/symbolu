"""Mechanical provider-independence verification (Task 113).

Proves TAP and ActionGate remain peers: neither package imports the other, and no
native provider type crosses directly between them — cross-provider coordination
happens only through neutral DGM / provider-framework records. The pilot
composition layer is permitted to import both.
"""
from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass

_REPO = pathlib.Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class IndependenceResult:
    check: str
    passed: bool
    detail: str


def _imports(pkg: str) -> set[str]:
    root = _REPO / pkg
    mods: set[str] = set()
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Import):
                mods.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods.add(node.module)
    return mods


def check_independence() -> list[IndependenceResult]:
    tap = _imports("tap_provider")
    ag = _imports("actiongate_provider")
    tap_to_ag = [m for m in tap if m.split(".")[0] == "actiongate_provider"]
    ag_to_tap = [m for m in ag if m.split(".")[0] == "tap_provider"]

    results = [
        IndependenceResult("tap_does_not_import_actiongate", not tap_to_ag,
                           f"offenders={tap_to_ag}"),
        IndependenceResult("actiongate_does_not_import_tap", not ag_to_tap,
                           f"offenders={ag_to_tap}"),
    ]

    # native types must not cross directly: the workflow passes only neutral
    # AssertionGovernance* / ActionGovernance* records between the layers. Verify
    # the runner never references a provider-native result type name.
    workflow_src = (_REPO / "enterprise_validation_pilot" / "runners" / "workflow.py").read_text()
    native_leaks = [name for name in ("TapEvaluationResult", "ActionGateDecision")
                    if name in workflow_src]
    results.append(IndependenceResult(
        "no_native_result_types_in_workflow", not native_leaks,
        f"native types referenced in workflow: {native_leaks}"))
    return results


def independence_passed(results: list[IndependenceResult]) -> bool:
    return all(r.passed for r in results)


def isolation_violation_count(results: list[IndependenceResult]) -> int:
    return sum(1 for r in results if not r.passed)
