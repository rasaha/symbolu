"""Packaging + boundary invariants for the RA-6 status runtime.

Verifies the one-way dependency direction, the stdlib-only leaf posture, the
declared dependency set, and — most importantly — that RA-6 introduces **no
second machine-authority artifact** (invariant I8).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

PKG = Path(__file__).resolve().parents[2]


def _pyproject() -> dict:
    with open(PKG / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)


def test_package_name_and_version():
    data = _pyproject()
    assert data["project"]["name"] == "ugence-risk-authority-status-runtime"
    from ugence_risk_authority_status_runtime import __version__

    assert __version__ == "0.1.0"


def test_declares_only_risk_authority_dependency():
    data = _pyproject()
    deps = data["project"]["dependencies"]
    # One-way dependency on the machine-authority owner only. No RA-4.5 runtime,
    # no agent-runtime, no database/framework/event-bus dependency.
    assert deps == ["ugence-risk-authority>=0.1.0"]


def test_no_infrastructure_or_framework_dependency():
    data = _pyproject()
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in (
        "sqlalchemy", "fastapi", "redis", "kafka", "boto3", "psycopg",
        "pydantic", "django", "flask", "celery",
    ):
        assert forbidden not in joined


def test_leaf_stays_stdlib_only_when_status_runtime_imported():
    import sys

    # Import the whole package; assert the RA leaf pulled in no third-party dep.
    import ugence_risk_authority_status_runtime  # noqa: F401
    import risk_authority  # noqa: F401

    thirdparty = sorted(
        {
            m.__name__.split(".")[0]
            for m in sys.modules.values()
            if getattr(m, "__file__", None) and "site-packages" in (m.__file__ or "")
        }
    )
    # pytest itself may be present; the RA family must not have pulled anything.
    forbidden = {"sqlalchemy", "fastapi", "redis", "kafka", "boto3", "psycopg", "pydantic"}
    assert forbidden.isdisjoint(set(thirdparty))


def test_no_second_authority_artifact_is_defined():
    # RA-6 adds ports/state/services only. The ONLY signed machine-authority type
    # remains RiskAuthorizationEnvelope in the leaf. Assert the status runtime
    # exposes no *Authorization/*Grant/*Envelope artifact of its own.
    import ugence_risk_authority_status_runtime as srt

    forbidden_suffixes = ("Authorization", "AuthorityGrant", "AuthorityEnvelope", "AuthorityToken")
    exported = list(srt.__all__)
    offenders = [
        name
        for name in exported
        if any(name.endswith(sfx) for sfx in forbidden_suffixes)
    ]
    assert offenders == [], f"unexpected authority-artifact exports: {offenders}"


def test_postgres_production_skeleton_raises_not_configured():
    from ugence_risk_authority_status_runtime import (
        PostgresAuthorityStoreFactory,
        PostgresNotConfiguredError,
    )

    factory = PostgresAuthorityStoreFactory("postgres://unused")
    try:
        factory.authority_store()
    except PostgresNotConfiguredError:
        return
    raise AssertionError("production skeleton must raise, not silently degrade")
