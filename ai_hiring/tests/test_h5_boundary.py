"""H5 — validation-phase boundary tests.

The validation tooling adds no platform/product architecture, imports only public
APIs (no vendor SDKs, no provider internals), invokes no production adapter, and
grants no new decision/authorization authority.
"""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

VALIDATION_MODULES = [
    "ai_hiring/validation/composition.py", "ai_hiring/validation/lifecycle.py",
    "ai_hiring/validation/pilot.py", "ai_hiring/validation/fairness.py",
    "ai_hiring/validation/metrics.py", "ai_hiring/validation/audit_completeness.py",
    "ai_hiring/validation/performance.py",
]

VENDOR_SDKS = ("openai", "anthropic", "mistralai", "boto3", "smtplib", "sendgrid", "twilio",
               "workday", "greenhouse", "lever", "googleapiclient", "requests", "httpx",
               "sqlalchemy", "psycopg2")


def test_validation_imports_only_public_apis_no_vendor_sdks():
    violations = []
    for rel in VALIDATION_MODULES:
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
                if top == "governance_providers" and not (
                        t.startswith("governance_providers.api")
                        or t.startswith("governance_providers.reference")
                        or t.startswith("governance_providers.contracts")):
                    violations.append(f"{rel}:{node.lineno} provider-internal -> {t}")
                if top in ("tap_provider", "actiongate_provider"):
                    violations.append(f"{rel}:{node.lineno} provider-impl -> {t}")
                if top in VENDOR_SDKS:
                    violations.append(f"{rel}:{node.lineno} vendor-sdk -> {t}")
    assert not violations, "H5 boundary violations:\n" + "\n".join(violations)


def test_validation_adds_no_new_lifecycle_states_or_authorities():
    # H5 must not introduce new statuses/authorities; it only consumes existing ones.
    from ai_hiring.actions.status import ActionProposalStatus
    from ai_hiring.recommendations.status import RecommendationStatus
    assert len(list(ActionProposalStatus)) == 13
    assert len(list(RecommendationStatus)) == 6


def test_execution_uses_only_in_memory_deterministic_adapter():
    # the lifecycle harness constructs only the deterministic in-memory adapter
    src = (REPO / "ai_hiring/validation/lifecycle.py").read_text()
    assert "DeterministicHiringExecutionAdapter" in src
    assert "DeterministicActionGovernanceProvider" in src
    # no real transport/SDK usage anywhere in validation tooling
    for rel in VALIDATION_MODULES + ["ai_hiring/validation/lifecycle.py"]:
        s = (REPO / rel).read_text()
        for banned in ("requests.", "smtplib", "urllib.request", "socket.socket", "boto3"):
            assert banned not in s, f"{rel} uses {banned}"


def test_validation_is_read_only_wrt_frozen_platform():
    # every validation module reaches the platform only through public api/reference/contracts
    for rel in VALIDATION_MODULES:
        s = (REPO / rel).read_text()
        assert "decision_governance.services" not in s
        assert "decision_governance.actions" not in s
        assert "decision_governance.execution" not in s
