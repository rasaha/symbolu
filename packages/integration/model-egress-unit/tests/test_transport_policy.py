"""Transport protection on the exchange's DSNs: verify-full in production, or refused."""

from __future__ import annotations

import pytest

from ugence_model_egress_unit.postgres import (
    REQUIRED_SSLMODE,
    TransportUnprotected,
    protected_connect,
    require_transport_protection,
    sslmode_of,
)


@pytest.mark.parametrize("dsn, mode", [
    ("postgresql://u@h:5432/db?sslmode=verify-full", "verify-full"),
    ("postgresql://u@h/db?application_name=x&sslmode=require", "require"),
    ("postgres://u@h/db", None),
    ("postgresql://u@h/db?sslmode=", None),
    ("host=h dbname=db sslmode=verify-full", "verify-full"),
    ("host=h dbname=db sslmode='prefer'", "prefer"),
    ("host=h dbname=db", None),
    ("", None),
])
def test_sslmode_is_read_from_both_libpq_forms(dsn, mode):
    assert sslmode_of(dsn) == mode


def test_production_requires_verify_full_and_nothing_weaker():
    assert REQUIRED_SSLMODE == "verify-full"
    ok = "postgresql://u@h/db?sslmode=verify-full"
    assert require_transport_protection(ok, production=True) == ok
    for weaker in ("postgresql://u@h/db", "postgresql://u@h/db?sslmode=require",
                   "postgresql://u@h/db?sslmode=verify-ca", "host=h sslmode=disable"):
        with pytest.raises(TransportUnprotected, match="verify-full"):
            require_transport_protection(weaker, production=True)
    with pytest.raises(TransportUnprotected, match="a DSN is required"):
        require_transport_protection("  ", production=False)


def test_outside_production_nothing_is_refused_but_the_policy_still_runs():
    loopback = "postgresql://postgres@127.0.0.1:5433/postgres"
    assert require_transport_protection(loopback, production=False) == loopback


def test_the_error_never_echoes_the_dsn():
    secret_dsn = "postgresql://user:hunter2-not-a-real-password@db.internal/exchange?sslmode=require"
    with pytest.raises(TransportUnprotected) as excinfo:
        require_transport_protection(secret_dsn, production=True)
    assert "hunter2" not in str(excinfo.value) and "db.internal" not in str(excinfo.value)


def test_protected_connect_checks_first_and_defers_the_driver():
    opened = []
    connect = protected_connect("postgresql://u@h/db?sslmode=verify-full", production=True,
                                connect=lambda dsn: opened.append(dsn) or "conn")
    assert opened == [], "nothing is opened until the exchange asks"
    assert connect() == "conn" and opened == ["postgresql://u@h/db?sslmode=verify-full"]
    with pytest.raises(TransportUnprotected):
        protected_connect("postgresql://u@h/db", production=True, connect=lambda dsn: None)
