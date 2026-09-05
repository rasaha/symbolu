"""Make the worker, every package it composes and the sibling test harnesses
importable in a bare source checkout, mirroring the integration packages' convention.

The end-to-end test reuses the durable-execution package's real-PostgreSQL harness
and the approver-identity-jwt package's in-process issuer rather than inventing new
ones. Every instant in this suite is explicit; no test reads the wall clock.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

HERE = pathlib.Path(__file__).resolve().parent
PKG = HERE.parent
REPO = PKG.parents[1]
INTEGRATION = REPO / "packages" / "integration"

DE_TESTS = INTEGRATION / "durable-execution" / "tests"

for path in (
    PKG / "src",
    INTEGRATION / "governed-review-service" / "src",
    INTEGRATION / "approver-identity-jwt" / "src",
    INTEGRATION / "approver-identity-jwt" / "tests",
    INTEGRATION / "governed-review" / "src",
    INTEGRATION / "control-plane-root" / "src",
    INTEGRATION / "approval-workflow" / "src",
    INTEGRATION / "authority-directory" / "src",
    REPO / "packages" / "governance-contracts" / "src",
    INTEGRATION / "agent-runtime-governance" / "src",
    INTEGRATION / "risk-authority-runtime" / "src",
    INTEGRATION / "risk-authority-status-runtime" / "src",
    REPO / "packages" / "runtime" / "agent-runtime" / "src",
    REPO / "packages" / "risk_authority" / "src",
    REPO / "packages" / "capabilities" / "decision-authority" / "src",
    REPO / "packages" / "providers" / "actiongate" / "src",
    INTEGRATION / "durable-execution" / "src",
    DE_TESTS,
    HERE,
):
    p = str(path)
    if path.is_dir() and p not in sys.path:
        sys.path.insert(0, p)


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


try:
    _de_conftest = _load("de_conftest", DE_TESTS / "conftest.py")
    pg_databases = _de_conftest.pg_databases
    requires_postgres = _de_conftest.requires_postgres
    postgres_available = _de_conftest.postgres_available
except Exception as exc:  # noqa: BLE001 - surfaced by the test that needs it
    _reason = f"durable-execution harness unavailable: {exc}"
    requires_postgres = pytest.mark.skip(reason=_reason)
    postgres_available = lambda: False  # noqa: E731

    @pytest.fixture()
    def pg_databases():
        pytest.skip(_reason)


NOW = datetime(2026, 9, 5, 9, 0, tzinfo=timezone.utc)
TENANT = "tenant-a"
ROLE = "risk-approver"
DIGEST = "shadow-v1"
ISSUER = "https://issuer.test"
AUDIENCE = "ugence-governed-review-service"
TENANT_CLAIM = "ugence_tenant"
ACTOR_CLAIM = "ugence_actor"
HUMAN_VALUE = "human-sign-in"

#: A DSN pair that never connects: the configuration tests only render and validate.
APP_DSN = "postgresql+psycopg://worker:app-s3cret-pw@db.internal:5432/ugence_app"
SYS_DSN = "postgresql+psycopg://worker:sys-s3cret-pw@db.internal:5432/ugence_sys"


class Clock:
    """One settable instant in both shapes the worker needs."""

    def __init__(self, start: datetime = NOW) -> None:
        self.now = start

    def datetime(self) -> datetime:
        return self.now

    def epoch(self) -> float:
        return self.now.timestamp()

    def advance(self, **kwargs) -> None:
        self.now = self.now + timedelta(**kwargs)


def tls_pair(tmp_path) -> tuple[str, str]:
    """Two readable files standing in for a certificate and key: ``validate`` checks
    presence and readability, never contents (the listener does that at bind)."""

    cert, key = tmp_path / "tls.crt", tmp_path / "tls.key"
    cert.write_text("placeholder certificate\n")
    key.write_text("placeholder key\n")
    return str(cert), str(key)


def config_for(tmp_path, mode: str = "test", **over):
    """An admissible configuration of ``mode``; production gets TLS files and an
    https issuer so a test changes exactly one thing at a time."""

    from governed_runtime_worker import WorkerConfig

    base = dict(
        deployment_mode=mode, app_database_url=APP_DSN, system_database_url=SYS_DSN,
        data_dir=str(tmp_path), tenant_id=TENANT, required_role=ROLE,
        definition_digest=DIGEST, bind_host="127.0.0.1", port=8444,
    )
    if mode == "production":
        cert, key = tls_pair(tmp_path)
        base.update(tls_cert_file=cert, tls_key_file=key, identity_issuer=ISSUER,
                    identity_audience=AUDIENCE, identity_jwks_url=ISSUER + "/jwks.json",
                    identity_tenant_claim=TENANT_CLAIM, identity_actor_type_claim=ACTOR_CLAIM,
                    identity_human_actor_value=HUMAN_VALUE)
    base.update(over)
    return WorkerConfig(**base)
