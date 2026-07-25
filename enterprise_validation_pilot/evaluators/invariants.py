"""Required safety invariants (Task 110).

Fifteen invariants are verified over the full scenario set plus static import
analysis. Any invariant failure fails the pilot regardless of aggregate metrics.
Each invariant returns the offending scenario ids so a failure is diagnosable.
"""
from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass

from ..runners.workflow import ScenarioRun
from ..schemas.scenario import Scenario

Pair = tuple[Scenario, ScenarioRun]
_AUTHORIZED = {"AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"}
_REPO = pathlib.Path(__file__).resolve().parents[2]
_SECRET_TOKENS = ("password", "secret", "api_key", "apikey", "token", "private_key")


@dataclass(frozen=True)
class InvariantResult:
    id: str
    description: str
    passed: bool
    offenders: tuple[str, ...] = ()
    detail: str = ""


def _pkg_imports(pkg: str):
    root = _REPO / pkg
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield node.module


def check_invariants(pairs: list[Pair]) -> list[InvariantResult]:
    out: list[InvariantResult] = []

    def inv(iid, desc, offenders, detail=""):
        offenders = tuple(offenders)
        out.append(InvariantResult(iid, desc, not offenders, offenders, detail))

    # I1: UNSUPPORTED never becomes supported downstream
    inv("I1", "TAP UNSUPPORTED never becomes supported downstream",
        [r.scenario_id for s, r in pairs if r.tap_outcome == "UNSUPPORTED"
         and (r.proceeded_to_action or r.dispatched
              or r.recommendation_posture == "ADVANCE")])

    # I2: INDETERMINATE never becomes supported without new authority/evidence
    inv("I2", "TAP INDETERMINATE never proceeds without new evidence/authority",
        [r.scenario_id for s, r in pairs if r.tap_outcome == "INDETERMINATE"
         and (r.proceeded_to_action or r.dispatched)])

    # I3: DENIED never dispatches
    inv("I3", "ActionGate DENIED never dispatches",
        [r.scenario_id for s, r in pairs if r.actiongate_outcome == "DENIED" and r.dispatched])

    # I4: INDETERMINATE action never dispatches
    inv("I4", "ActionGate INDETERMINATE never dispatches",
        [r.scenario_id for s, r in pairs
         if r.actiongate_outcome == "INDETERMINATE" and r.dispatched])

    # I5: provider timeout never authorizes or supports
    off5 = []
    for s, r in pairs:
        if s.tap_policy.fail == "timeout" and r.tap_outcome == "SUPPORTED":
            off5.append(r.scenario_id)
        if s.action_policy.fail == "timeout" and r.actiongate_outcome in _AUTHORIZED:
            off5.append(r.scenario_id)
    inv("I5", "Provider timeout never authorizes or supports", off5)

    # I6: unknown provider outcome never authorizes or supports
    off6 = []
    for s, r in pairs:
        if s.tap_policy.emit_unknown and r.tap_outcome == "SUPPORTED":
            off6.append(r.scenario_id)
        if s.action_policy.mode == "unknown" and r.actiongate_outcome in _AUTHORIZED:
            off6.append(r.scenario_id)
    inv("I6", "Unknown provider outcome never authorizes or supports", off6)

    # I7: constraints survive authorization into enforcement
    inv("I7", "Constraints survive authorization into enforcement",
        [r.scenario_id for s, r in pairs
         if r.constraints and r.dispatched and r.enforcement_allowed is None])

    # I8: obligations survive authorization into reconciliation
    inv("I8", "Obligations survive authorization into reconciliation",
        [r.scenario_id for s, r in pairs
         if r.obligations and r.dispatched and not r.obligation_records])

    # I9: execution success does not imply governance compliance
    off9 = [r.scenario_id for s, r in pairs
            if any(o.state == "FAILED" for o in r.obligation_records)
            and r.compliance_verdict == "COMPLIANT"]
    demonstrated = any(r.dispatched and r.compliance_verdict == "NONCOMPLIANT" for s, r in pairs)
    inv("I9", "Execution success does not imply governance compliance", off9,
        detail=("distinction demonstrated by >=1 executed-but-noncompliant scenario"
                if demonstrated else "NO executed-but-noncompliant scenario present"))
    if not demonstrated:
        out[-1] = InvariantResult("I9", out[-1].description, False,
                                  ("<none-demonstrated>",), out[-1].detail)

    # I10 / I11: mechanical import isolation
    tap_imports = set(_pkg_imports("tap_provider"))
    ag_imports = set(_pkg_imports("actiongate_provider"))
    inv("I10", "TAP never invokes ActionGate",
        ["tap_provider imports actiongate_provider"]
        if any(m.split(".")[0] == "actiongate_provider" for m in tap_imports) else [])
    inv("I11", "ActionGate never invokes TAP",
        ["actiongate_provider imports tap_provider"]
        if any(m.split(".")[0] == "tap_provider" for m in ag_imports) else [])

    # I12: execution provider never decides authorization (no dispatch without auth)
    inv("I12", "ExternalExecutionProvider never decides authorization",
        [r.scenario_id for s, r in pairs
         if r.dispatched and r.actiongate_outcome not in _AUTHORIZED])

    # I13: provider selection deterministic and auditable
    inv("I13", "Provider selection is deterministic and auditable",
        [r.scenario_id for s, r in pairs
         if not r.assertion_provider_id or r.assertion_selection_rule == "UNRESOLVED"])

    # I14: human approval never fabricated by a provider
    #   a required_approval constraint with no human approval must block dispatch
    off14 = []
    for s, r in pairs:
        needs_approval = any("required_approval" in c for c in r.constraints)
        approved = bool(s.human_review and s.human_review.action == "approve_action")
        if needs_approval and not approved and r.dispatched:
            off14.append(r.scenario_id)
    inv("I14", "Human approval is never fabricated by a provider", off14)

    # I15: audit records contain no plaintext secrets
    off15 = []
    for s, r in pairs:
        blob = " ".join(str(v) for v in r.trace.values()).lower()
        blob += " " + " ".join(r.constraints + r.obligations).lower()
        if any(tok in blob for tok in _SECRET_TOKENS):
            off15.append(r.scenario_id)
    inv("I15", "Audit records contain no plaintext secrets", off15)

    return out


def invariants_passed(results: list[InvariantResult]) -> bool:
    return all(r.passed for r in results)
