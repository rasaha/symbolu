"""Deployment preflight against a real PostgreSQL database (round PR-C).

Preflight is what stands between a misconfigured pilot and a half-working one:
it must catch an unreachable database, a process running as the WRONG role
(role separation is a deployment property — DEC-3C-4 / I6), and a schema that
does not match the code's migration head.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.postgres

_DB_URL = os.environ.get("DILCHAT_TEST_DATABASE_URL")
if not _DB_URL or "postgresql" not in _DB_URL:
    pytest.skip("DILCHAT_TEST_DATABASE_URL (PostgreSQL) not set", allow_module_level=True)

from ugence_dilchat.config import Environment, Settings  # noqa: E402
from ugence_dilchat.scripts_preflight import _head_revision, preflight  # noqa: E402


def _settings(**kw) -> Settings:
    kw.setdefault("database_url", _DB_URL)
    return Settings(environment=Environment.TEST, **kw)


async def test_preflight_passes_against_a_migrated_database():
    checks, ok = await preflight(_settings())
    assert ok, checks
    assert checks["configuration"] == "OK"
    assert checks["database"] == "OK"
    assert checks["schema"].startswith("OK at=")
    # The posture summary an operator reads before starting a pilot.
    assert checks["retention_purge_enabled"] == "False"


async def test_preflight_reports_the_code_head():
    checks, ok = await preflight(_settings())
    assert ok
    assert _head_revision() is not None
    assert _head_revision() in checks["schema"]


async def test_wrong_expected_role_fails_preflight():
    """The web process must never be running on the worker's credentials."""
    checks, ok = await preflight(_settings(), expect_role="dilchat_worker")
    assert not ok
    assert checks["db_role"].startswith("MISMATCH expected=dilchat_worker")


async def test_matching_expected_role_passes():
    actual = (await preflight(_settings()))[0]["db_role"]
    checks, ok = await preflight(_settings(), expect_role=actual)
    assert ok, checks
    assert checks["db_role"] == actual


async def test_unreachable_database_fails_closed_without_echoing_the_dsn():
    secret = "SENTINEL_preflight_password_7c1e"
    settings = _settings(
        database_url=f"postgresql+asyncpg://nobody:{secret}@127.0.0.1:1/dilchat_absent"
    )
    checks, ok = await preflight(settings)
    assert not ok
    assert checks["database"] == "UNREACHABLE"
    assert secret not in repr(checks)


async def test_invalid_configuration_fails_before_touching_the_database(monkeypatch):
    """A guard violation is reported as configuration, not as a database error."""
    # production without a signing key: a fail-fast guard from round PR-A.
    monkeypatch.setenv("DILCHAT_ENVIRONMENT", "production")
    monkeypatch.setenv("DILCHAT_DATABASE_URL", _DB_URL)
    monkeypatch.delenv("DILCHAT_ACCESS_TOKEN_PRIVATE_KEY_PEM", raising=False)

    checks, ok = await preflight()  # constructs Settings from the environment
    assert not ok
    assert checks["configuration"].startswith("INVALID")
    assert "database" not in checks  # never reached the database
