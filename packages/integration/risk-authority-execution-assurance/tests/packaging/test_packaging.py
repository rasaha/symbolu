"""Packaging + boundary invariants for the RA-8 execution-assurance package.

Verifies the declared one-way dependency set, the no-second-authority-artifact and
no-third-ledger properties, that pydantic enters only as a transitive DA dependency
(RA-8 defines no pydantic models of its own), and that the source tree imports no
Agent Runtime (spec §8, §28, §33, §37).
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

PKG = Path(__file__).resolve().parents[2]


def _pyproject() -> dict:
    with open(PKG / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)


def test_package_name_and_version():
    data = _pyproject()
    assert data["project"]["name"] == "ugence-risk-authority-execution-assurance"
    from ugence_risk_authority_execution_assurance import __version__

    assert __version__ == "0.1.0"


def test_declares_the_ratified_dependency_set():
    deps = _pyproject()["project"]["dependencies"]
    assert deps == [
        "ugence-risk-authority>=0.1.0",
        "ugence-risk-authority-status-runtime>=0.1.0",
        "ugence-decision-authority>=1.0.0",
        "ugence-governance-contracts>=0.1.0",
    ]


def test_no_agent_runtime_or_infrastructure_dependency():
    joined = " ".join(_pyproject()["project"]["dependencies"]).lower()
    for forbidden in (
        "agent-runtime",
        "agent_runtime",
        "sqlalchemy", "fastapi", "redis", "kafka", "boto3", "psycopg", "django", "flask", "celery",
    ):
        assert forbidden not in joined
    # pydantic is NOT a direct dependency — it arrives only transitively via DA.
    assert "pydantic" not in joined


def test_import_does_not_pull_in_agent_runtime():
    import ugence_risk_authority_execution_assurance  # noqa: F401

    assert "ugence_agent_runtime" not in sys.modules


def test_no_second_authority_artifact_is_defined():
    import ugence_risk_authority_execution_assurance as ra8

    forbidden_suffixes = (
        "Authorization", "AuthorityGrant", "AuthorityEnvelope", "AuthorityToken",
        "Grant", "Credential", "Envelope", "Token", "Permit", "Capability",
    )
    offenders = [n for n in ra8.__all__ if any(n.endswith(s) for s in forbidden_suffixes)]
    assert offenders == [], f"unexpected authority-artifact exports: {offenders}"


def test_handoff_reuses_leaf_signal():
    from ugence_risk_authority_execution_assurance.handoff import AuthorityReassessmentSignal
    from risk_authority.domain.authority_signal import (
        AuthorityReassessmentSignal as LeafSignal,
    )

    assert AuthorityReassessmentSignal is LeafSignal


def test_no_third_ledger_symbols():
    import ugence_risk_authority_execution_assurance as ra8

    joined = " ".join(ra8.__all__).lower()
    for banned in ("repository", "ledger", "executionstore", "attemptstore"):
        assert banned not in joined


def test_source_tree_does_not_import_agent_runtime():
    src = PKG / "src" / "ugence_risk_authority_execution_assurance"
    for py in src.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "ugence_agent_runtime" not in text, f"{py} references the Agent Runtime"
        assert "import agent_runtime" not in text, f"{py} imports agent runtime"


def test_reuses_da_reconciliation_types_not_a_fork():
    # RA-8 imports the DA reconciliation kernel rather than forking ExecutionIntent /
    # ExecutionRecord / ReconciliationResult (spec §9, §14; matrix 38).
    from ugence_risk_authority_execution_assurance.reconciler import (
        ExecutionIntent,
        ExecutionRecord,
        ReconciliationResult,
    )
    from ugence_decision_authority.execution.execution_intent import (
        ExecutionIntent as DAIntent,
    )

    assert ExecutionIntent is DAIntent
    assert ExecutionRecord.__module__.startswith("ugence_decision_authority")
    assert ReconciliationResult.__module__.startswith("ugence_decision_authority")
