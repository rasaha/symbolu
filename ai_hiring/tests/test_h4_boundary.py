"""H4 — architectural boundary tests.

Guards: authorization only via the Action Governance Provider contract (no ActionGate
internals), execution only via the external port (no vendor SDKs), kernel/provider
reached only via public `.api`, and no Recommendation → Action / Decision → direct-
execution path.
"""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

H4_MODULES = [
    "ai_hiring/actions/action_types.py", "ai_hiring/actions/status.py",
    "ai_hiring/actions/proposal.py", "ai_hiring/actions/records.py",
    "ai_hiring/actions/actiongate_integration.py", "ai_hiring/actions/execution_port.py",
    "ai_hiring/actions/read_models.py",
    "ai_hiring/repositories/action_repositories.py",
    "ai_hiring/services/hiring_action_proposal_service.py",
    "ai_hiring/services/hiring_action_authorization_service.py",
    "ai_hiring/services/hiring_action_execution_service.py",
    "ai_hiring/services/hiring_reconciliation_service.py",
    "ai_hiring/services/hiring_compensation_service.py",
    "ai_hiring/services/hiring_action_reconstruction_service.py",
    "ai_hiring/api/action_contracts.py",
]

VENDOR_SDKS = ("openai", "anthropic", "mistralai", "boto3", "smtplib", "sendgrid", "twilio",
               "workday", "greenhouse", "lever", "googleapiclient", "google", "requests",
               "httpx", "sqlalchemy", "psycopg2")


def test_h4_imports_only_public_apis():
    violations = []
    for rel in H4_MODULES:
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
                if top in ("tap_provider", "actiongate_provider"):
                    violations.append(f"{rel}:{node.lineno} provider-impl -> {t}")
                if top in VENDOR_SDKS:
                    violations.append(f"{rel}:{node.lineno} vendor-sdk -> {t}")
    assert not violations, "H4 import-boundary violations:\n" + "\n".join(violations)


def test_no_direct_execution_without_authorization_in_service():
    """The execution service must load and require an authorization before dispatch."""
    src = (REPO / "ai_hiring/services/hiring_action_execution_service.py").read_text()
    assert "latest_for_proposal" in src and "ActionNotAuthorizedError" in src
    assert "not auth.authorized" in src


def test_proposal_service_requires_a_decision():
    """No recommendation-only path: the proposal service requires a DECIDED binding."""
    src = (REPO / "ai_hiring/services/hiring_action_proposal_service.py").read_text()
    assert "GovernanceBindingStatus.DECIDED" in src
    assert "IneligibleActionSourceError" in src


def test_services_expose_no_grant_or_waive_method():
    from ai_hiring.services.hiring_action_authorization_service import HiringActionAuthorizationService
    from ai_hiring.services.hiring_action_execution_service import HiringActionExecutionService
    banned = {"grant", "waive_obligation", "expand_authorization", "self_authorize", "waive"}
    for svc in (HiringActionAuthorizationService, HiringActionExecutionService):
        methods = {m for m in dir(svc) if not m.startswith("_")}
        assert not (methods & banned), (svc.__name__, methods & banned)


def test_prepare_offer_is_not_issue_offer():
    from ai_hiring.actions.action_types import HiringActionType
    values = {a.value for a in HiringActionType}
    assert "PREPARE_OFFER" in values and "ISSUE_OFFER" not in values
    assert "PREPARE_REJECTION" in values and "SEND_REJECTION" not in values
