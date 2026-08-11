"""Packaging + boundary invariants for the RA-7 runtime assurance package.

Verifies the one-way dependency direction, the stdlib-only leaf posture, the
declared dependency set, and — most importantly — that RA-7 introduces **no second
machine-authority artifact** (spec §21 I1/I2/I15) and imports no Agent Runtime
(N8/I11).
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
    assert data["project"]["name"] == "ugence-risk-authority-runtime-assurance"
    from ugence_risk_authority_runtime_assurance import __version__

    assert __version__ == "0.1.0"


def test_declares_only_ra_leaf_and_ra6_dependencies():
    data = _pyproject()
    deps = data["project"]["dependencies"]
    # One-way dependency on the machine-authority owner (neutral signal types) and
    # the RA-6 status-runtime intake. NO agent-runtime, NO db/framework/event-bus.
    assert deps == [
        "ugence-risk-authority>=0.1.0",
        "ugence-risk-authority-status-runtime>=0.1.0",
    ]


def test_no_agent_runtime_or_infrastructure_dependency():
    data = _pyproject()
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in (
        "agent-runtime",
        "agent_runtime",
        "sqlalchemy", "fastapi", "redis", "kafka", "boto3", "psycopg",
        "pydantic", "django", "flask", "celery",
    ):
        assert forbidden not in joined


def test_ra7_import_does_not_pull_in_agent_runtime():
    # Importing RA-7 must not import the Agent Runtime (N8/I11): RA-7 observes it
    # through a neutral duck-typed event contract, never a concrete dependency.
    import ugence_risk_authority_runtime_assurance  # noqa: F401

    assert "ugence_agent_runtime" not in sys.modules


def test_leaf_stays_stdlib_only_when_ra7_imported():
    import ugence_risk_authority_runtime_assurance  # noqa: F401
    import risk_authority  # noqa: F401

    thirdparty = sorted(
        {
            m.__name__.split(".")[0]
            for m in sys.modules.values()
            if getattr(m, "__file__", None) and "site-packages" in (m.__file__ or "")
        }
    )
    forbidden = {"sqlalchemy", "fastapi", "redis", "kafka", "boto3", "psycopg", "pydantic"}
    assert forbidden.isdisjoint(set(thirdparty))


def test_no_second_authority_artifact_is_defined():
    # RA-7 adds observer/evaluator/ingress/handoff contracts only. The ONLY signed
    # machine-authority type remains RiskAuthorizationEnvelope in the leaf.
    import ugence_risk_authority_runtime_assurance as ra7

    forbidden_suffixes = (
        "Authorization",
        "AuthorityGrant",
        "AuthorityEnvelope",
        "AuthorityToken",
        "Grant",
        "Credential",
        "Envelope",
    )
    offenders = [
        name
        for name in ra7.__all__
        if any(name.endswith(sfx) for sfx in forbidden_suffixes)
    ]
    assert offenders == [], f"unexpected authority-artifact exports: {offenders}"


def test_ra7_reuses_leaf_signal_not_a_new_signal_type():
    # The handoff must reuse the leaf AuthorityReassessmentSignal; RA-7 defines no
    # RuntimeAuthorization / TrajectoryAuthorization / AssuranceAuthorization.
    import ugence_risk_authority_runtime_assurance as ra7

    for banned in (
        "RuntimeAuthorization",
        "TrajectoryAuthorization",
        "AssuranceAuthorization",
        "TrajectoryGrant",
    ):
        assert banned not in ra7.__all__
        assert not hasattr(ra7, banned)


def test_handoff_imports_leaf_signal():
    from ugence_risk_authority_runtime_assurance.handoff import (
        AuthorityReassessmentSignal,
    )
    from risk_authority.domain.authority_signal import (
        AuthorityReassessmentSignal as LeafSignal,
    )

    assert AuthorityReassessmentSignal is LeafSignal


def test_no_acp_or_ra8_reconciliation_symbols():
    # RA-7 is not ACP and not RA-8: no actuator/reconciliation/effect-receipt API.
    import ugence_risk_authority_runtime_assurance as ra7

    joined = " ".join(ra7.__all__).lower()
    for banned in ("actuator", "reconcil", "executionreceipt", "effectmismatch", "compensat"):
        assert banned not in joined


def test_source_tree_does_not_import_agent_runtime():
    src = PKG / "src" / "ugence_risk_authority_runtime_assurance"
    for py in src.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "ugence_agent_runtime" not in text, f"{py} references the Agent Runtime"
        assert "import agent_runtime" not in text, f"{py} imports agent runtime"
