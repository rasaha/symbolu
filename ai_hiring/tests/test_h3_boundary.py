"""H3 — architectural boundary tests.

Guards the H3 invariants: the governance layer reaches the kernel only via
`decision_governance.api`, never imports ActionGate / action-request / execution
internals, and provides no Recommendation → Action path. Human decisions remain
human-only; the flow stops at the recorded DecisionRecord (execution is H4).
"""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

H3_MODULES = [
    "ai_hiring/governance/binding.py", "ai_hiring/governance/outcomes.py",
    "ai_hiring/governance/linked_record.py", "ai_hiring/governance/reconstruction.py",
    "ai_hiring/governance/views.py",
    "ai_hiring/repositories/governance_repositories.py",
    "ai_hiring/services/governance_integration_service.py",
    "ai_hiring/api/governance_contracts.py",
]


def test_h3_imports_only_public_kernel_api():
    violations = []
    for rel in H3_MODULES:
        tree = ast.parse((REPO / rel).read_text(), filename=rel)
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                targets.append(node.module)
            elif isinstance(node, ast.Import):
                targets.extend(a.name for a in node.names)
            for t in targets:
                top = t.split(".")[0]
                if top == "decision_governance" and not t.startswith("decision_governance.api"):
                    violations.append(f"{rel}:{node.lineno} kernel-internal -> {t}")
                if top == "governance_providers" and not t.startswith("governance_providers.api"):
                    violations.append(f"{rel}:{node.lineno} provider-internal -> {t}")
    assert not violations, "H3 import-boundary violations:\n" + "\n".join(violations)


def test_h3_never_imports_actiongate_or_execution():
    """No H3 module may *import* ActionGate/execution/action-request symbols (H4)."""
    banned_modules = ("actiongate_provider", "tap_provider")
    banned_symbols = {"ActionRequest", "ActionGate", "ActionControlPlanePort", "ExecutionService",
                      "ExecutionIntent", "ExternalExecutionPort", "CompensationService",
                      "ActionAuthorizationService", "ActionRequestService", "ReconciliationService"}
    violations = []
    for rel in H3_MODULES:
        tree = ast.parse((REPO / rel).read_text(), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in banned_modules:
                    violations.append(f"{rel}:{node.lineno} -> {node.module}")
                for a in node.names:
                    if a.name in banned_symbols:
                        violations.append(f"{rel}:{node.lineno} imports {a.name}")
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in banned_modules:
                        violations.append(f"{rel}:{node.lineno} -> {a.name}")
    assert not violations, "H3 imports H4/execution symbols:\n" + "\n".join(violations)


def test_no_recommendation_to_action_path():
    """The governance service must not expose any authorize/execute/action method."""
    from ai_hiring.services.governance_integration_service import GovernanceIntegrationService
    banned = {"authorize", "execute", "dispatch", "create_action", "create_action_request",
              "offer", "reject_candidate", "reconcile", "compensate"}
    methods = {m for m in dir(GovernanceIntegrationService) if not m.startswith("_")}
    assert not (methods & banned), methods & banned


def test_decision_outcomes_are_kernel_neutral_not_execution():
    from ai_hiring.governance.outcomes import HiringDecisionIntent
    assert {i.value for i in HiringDecisionIntent} == {"ADVANCE", "HOLD", "REJECT", "DEFER"}
